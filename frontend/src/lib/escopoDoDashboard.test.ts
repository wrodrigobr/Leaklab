import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { comEscopo, queryDoEscopo, type EscopoDoDashboard } from "./api";

/**
 * O ESCOPO do dashboard: as três dimensões, e a garantia de que TODO card as recebe.
 *
 * ── O pedido, e o risco dele (17/09) ──────────────────────────────────────────────────────────
 *
 * O dono: "pensei em ao invés dos botões dos ultimos torneios, podiamos criar um icone de filtro,
 * e abrir um popup para o jogador escolher como quer filtrar 'ultimos torneios, ultimas x mãos
 * (com limite de 30 mil mãos), por data de inicio e fim (com limite de x meses)'". E depois, sobre
 * o risco: "Garanta que o Dashboard vai ser atualizado com estes filtros".
 *
 * O risco tem nome: o dashboard tem 23 chamadas que carregam o escopo, e o fragmento de query
 * `last_n=${...}` estava escrito A MÃO 24 vezes. Se UMA ficar de fora, a tela mostra números de
 * escopos diferentes sob uma faixa que declara um só -- e o jogador não tem como saber.
 *
 * A casa já tem essa cicatriz duas vezes nesta mesma frente: o sentinela `0` ensinado a uma das
 * duas implementações da janela (o bankroll vinha vazio), e o `/player/ev-summary` lendo `last_n`
 * direto da query sem passar pelo helper (achado hoje, na varredura do servidor).
 */

const API = readFileSync(join(import.meta.dirname, "api.ts"), "utf-8");
/** O montador vive em `escopo.ts` desde 18/09: constante e tipo saíram do módulo de rede porque
 *  quem mocka a API perdia as constantes junto. As CHAMADAS seguem no `api.ts`. */
const ESCOPO_TS = readFileSync(join(import.meta.dirname, "escopo.ts"), "utf-8");

/** O fonte sem comentários: comentário que cita o fragmento não é fragmento. */
function semComentarios(txt: string): string {
  return txt.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

describe("o escopo virando query", () => {
  it("cada dimensão sai com o parâmetro que o servidor lê", () => {
    expect(queryDoEscopo({ tipo: "torneios", n: 50 })).toBe("last_n=50");
    // `0` é HISTÓRICO genuíno, e não "sem escopo": ele tem de chegar ao servidor
    expect(queryDoEscopo({ tipo: "torneios", n: 0 })).toBe("last_n=0");
    expect(queryDoEscopo({ tipo: "maos", n: 5000 })).toBe("maos=5000");
    expect(queryDoEscopo({ tipo: "periodo", de: "2026-06-01", ate: "2026-06-30" }))
      .toBe("de=2026-06-01&ate=2026-06-30");
    // número cru segue aceito: `last_n` é contrato antigo e há chamador que passa o número
    expect(queryDoEscopo(50)).toBe("last_n=50");
    expect(queryDoEscopo(0)).toBe("last_n=0");
    // e sem escopo não se inventa parâmetro
    expect(queryDoEscopo(null)).toBe("");
    expect(queryDoEscopo(undefined)).toBe("");
  });

  it("o separador sai da URL, e não do chamador", () => {
    // Era o chamador que escolhia `?` ou `&`, em 24 lugares. Errar isso produz uma URL inválida
    // que o servidor ignora em silêncio -- o card volta com o escopo padrão e ninguém vê.
    expect(comEscopo("/metrics/level", { tipo: "maos", n: 300 })).toBe("/metrics/level?maos=300");
    expect(comEscopo("/history/evolution?days=90", { tipo: "maos", n: 300 }))
      .toBe("/history/evolution?days=90&maos=300");
    expect(comEscopo("/metrics/level", null)).toBe("/metrics/level");
  });
});

describe("a garantia de que TODO card recebe o escopo", () => {
  it("nenhuma função do cliente monta o fragmento do escopo a mão", () => {
    // A varredura que responde ao "garanta que o Dashboard vai ser atualizado": se alguém copiar
    // o fragmento numa função nova, ela escapa das dimensões novas e o card volta com outro
    // escopo. A exceção é declarada e nominal, não um limite afrouxado.
    // A varredura é sobre as CHAMADAS (`api.ts`). O montador mora noutro arquivo desde 18/09, e
    // por isso não precisa mais ser recortado daqui -- mas o guarda confere que ele está lá, senão
    // esta varredura passaria verde varrendo um arquivo que não tem mais o que ela procura.
    expect(ESCOPO_TS, "o montador sumiu de escopo.ts").toContain("export function queryDoEscopo");
    const fonte = semComentarios(API);
    const achados = [...fonte.matchAll(/^.*last_n=\$\{.*$/gm)].map((m) => m[0].trim());
    const permitidos = achados.filter((l) => l.includes("/player/practice/report"));
    const proibidos = achados.filter((l) => !l.includes("/player/practice/report"));

    expect(proibidos, "função montando o fragmento do escopo por conta").toEqual([]);
    // CONTROLE: o relatório do Prática TEM de continuar aparecendo -- ele é outro contrato (o
    // `last_n` dele é o número de MÃOS do relatório, e não o filtro do dashboard). Sem este, a
    // varredura passaria verde se o regex parasse de casar qualquer coisa.
    expect(permitidos.length, "o regex da varredura deixou de casar").toBe(1);
  });

  it("toda função que recebe escopo o repassa ao montador", () => {
    // O complemento: não basta não montar à mão, é preciso USAR o montador. Uma função que
    // recebesse `escopo` e o ignorasse compilaria e devolveria o escopo padrão do servidor.
    const fonte = semComentarios(API);
    const comParametro = [...fonte.matchAll(/^\s*(\w+): \([^)]*escopo\?: EscopoDoDashboard[^)]*\) =>\s*$/gm)];
    expect(comParametro.length, "a varredura não achou nenhuma função com escopo")
      .toBeGreaterThanOrEqual(20);

    const semUso: string[] = [];
    for (const m of comParametro) {
      const nome = m[1];
      // o corpo da função vai da assinatura até a próxima linha que começa uma nova chave
      const inicio = (m.index ?? 0) + m[0].length;
      const resto = fonte.slice(inicio, inicio + 700);
      const corpo = resto.split(/\n\s{2}\w+: \(/)[0];
      if (!/queryDoEscopo|comEscopo/.test(corpo)) semUso.push(nome);
    }
    expect(semUso, "funções que recebem o escopo e não o usam").toEqual([]);
  });

  it("o tipo cobre as três dimensões, e nada mais", () => {
    // Um `tipo` novo sem tratamento em `queryDoEscopo` sairia como faixa de data (o último `return`
    // não tem guarda). Este caso é o que obriga a atualizar a função junto com o tipo.
    const escopos: EscopoDoDashboard[] = [
      { tipo: "torneios", n: 20 },
      { tipo: "maos", n: 1000 },
      { tipo: "periodo", de: "2026-01-01", ate: "2026-02-01" },
    ];
    const params = escopos.map((e) => queryDoEscopo(e).split("=")[0]);
    expect(params).toEqual(["last_n", "maos", "de"]);
  });
});
