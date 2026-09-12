import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";

/**
 * Cenário novo na tela de ranges leva rótulo nas 3 locales, e o papel do vilão é nomeado certo.
 *
 * ── O caso que originou ─────────────────────────────────────────────────────────────────────
 *
 * A carta (`docs/leaklab_gto_ranges.json`) tem seis seções e a tela servia quatro. As 2.520
 * células de `vs_4bet` (36 pares fechados em 30, 40, 50, 75 e 100bb, com as mãos por ação)
 * estavam no acervo e não chegavam à tela desde 28/08 — e o buraco estava **documentado num
 * comentário deste mesmo arquivo**. Comentário registra e descansa: não conserta e não avisa.
 *
 * ── O segundo defeito, que só apareceu ao acrescentar o cenário ─────────────────────────────
 *
 * O rótulo da linha do vilão era um ternário de duas vias (`abridor ? "Contra" : "3-bet de"`),
 * repetido em DOIS lugares: a barra flutuante e o seletor. Com um terceiro papel, os dois
 * cairiam em "3-bet de" e a tela nomearia o spot errado — o jogador leria "3-bet de BTN" numa
 * grade que é sobre o 4-bet dele. Virou um mapa por papel, em um lugar só (regra 5).
 *
 * Os guardas abaixo defendem as duas coisas, e o de i18n vale para as TRÊS locales de propósito:
 * conferir só o pt-BR deixa en e es envelhecerem calados, que é como copy traduzida apodrece.
 */
const LOCALES = ["pt-BR", "en", "es"] as const;
const TELA = "src/pages/Ranges.tsx";

/** Os ids de cenário lidos do FONTE, não uma lista copiada para o teste. */
function cenariosDaTela(): string[] {
  const src = readFileSync(TELA, "utf-8");
  const bloco = src.match(/const CENARIOS: Cenario\[\] = \[([\s\S]*?)\n\];/);
  expect(bloco, "não achei o bloco CENARIOS em Ranges.tsx").toBeTruthy();
  return [...bloco![1].matchAll(/id:\s*"([a-z0-9_]+)"/g)].map((m) => m[1]);
}

const ranges = (loc: string) =>
  JSON.parse(readFileSync(`src/i18n/locales/${loc}/study.json`, "utf-8")).ranges;

describe("tela de ranges — cenários e o papel do vilão", () => {
  it("todo cenário da tela tem rótulo nas 3 locales", () => {
    const cen = cenariosDaTela();
    expect(cen.length, "a varredura não achou cenário nenhum").toBeGreaterThanOrEqual(5);
    for (const loc of LOCALES) {
      const dic = ranges(loc).cen ?? {};
      const faltando = cen.filter((c) => !dic[c]);
      expect(faltando, `${loc}: cenário sem rótulo: ${faltando.join(", ")}`).toEqual([]);
    }
  });

  it("o vs_4bet está na tela e lê a seção certa da resposta", () => {
    const cen = cenariosDaTela();
    expect(cen, "o vs_4bet saiu da tela").toContain("vs_4bet");
    const src = readFileSync(TELA, "utf-8");
    // Ler `resp.vs_4bet` é o que faz a matriz aparecer: sem isto o cenário existe e vem vazio.
    expect(src, "o cenário existe mas a tela não lê `resp.vs_4bet`").toContain("resp.vs_4bet");
  });

  it("cada papel de vilão tem rótulo próprio, e o mapa é a fonte única", () => {
    const src = readFileSync(TELA, "utf-8");
    const mapa = src.match(/const ROTULO_DO_VILAO[^=]*=\s*\{([\s\S]*?)\};/);
    expect(mapa, "o mapa de rótulo do vilão desapareceu").toBeTruthy();
    const papeis = [...mapa![1].matchAll(/"?([a-z0-9]+)"?:\s*"([^"]+)"/g)];
    const porPapel = Object.fromEntries(papeis.map((m) => [m[1], m[2]]));
    for (const p of ["abridor", "3bettor", "4bettor"]) {
      expect(porPapel[p], `papel sem rótulo: ${p}`).toBeTruthy();
    }
    // Os três apontam para chaves DIFERENTES: dois papéis com a mesma chave é o defeito de volta.
    const chaves = new Set(Object.values(porPapel));
    expect(chaves.size, `papéis compartilhando rótulo: ${JSON.stringify(porPapel)}`)
      .toBe(Object.keys(porPapel).length);
    // E o ternário antigo não pode voltar: ele é o que nomeava o spot errado.
    expect(src).not.toContain('cenario.contra === "abridor" ? "ranges.contra"');
  });

  it("as chaves que o mapa aponta existem nas 3 locales", () => {
    const src = readFileSync(TELA, "utf-8");
    const mapa = src.match(/const ROTULO_DO_VILAO[^=]*=\s*\{([\s\S]*?)\};/);
    const chaves = [...mapa![1].matchAll(/:\s*"ranges\.([a-zA-Z]+)"/g)].map((m) => m[1]);
    expect(chaves.length).toBeGreaterThanOrEqual(3);
    for (const loc of LOCALES) {
      const dic = ranges(loc);
      const faltando = chaves.filter((k) => !dic[k]);
      expect(faltando, `${loc}: chave do mapa sem tradução: ${faltando.join(", ")}`).toEqual([]);
    }
  });
});
