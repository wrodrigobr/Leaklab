import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { CHAVES_DE_TORNEIO, CHAVES_NAO_DERIVADAS } from "@/lib/refreshOnImport";

/**
 * Toda query do app foi CLASSIFICADA como derivada de torneio ou não?
 *
 * ── O bug que originou ────────────────────────────────────────────────────────────────────────
 *
 * Usuário: "por mais que eu esteja jogando torneios, nem todos os indicadores estão sendo
 * modificados". A varredura achou quatro chaves que mostram número de torneio e não recarregavam
 * no import: `bankroll-evolution` (o gráfico de banca), `progression-status`, `proximo-passo` e
 * `training-daily-status`. Cada uma num componente que busca por conta própria, com `staleTime` de
 * 30 a 60 segundos e sem escutar nada.
 *
 * As queries do `Index` estavam certas porque carregam uma chave de refresh. As dos
 * componentes-filhos não tinham nada, e ninguém percebeu por meses.
 *
 * ── Por que uma CATRACA e não uma lista ───────────────────────────────────────────────────────
 *
 * Uma lista de "o que recarregar" envelhece calada: o próximo card criado não entra nela, e o bug
 * volta exatamente igual. Este teste varre o código e exige que TODA chave esteja numa das duas
 * listas. Chave nova sem classificação FALHA aqui, e o autor é obrigado a decidir se ela deriva de
 * torneio. É o mesmo padrão da catraca de migração do PG.
 *
 * Falhou? Não adicione às cegas em `CHAVES_NAO_DERIVADAS` para calar o teste. A pergunta é: **o
 * número que essa query mostra muda quando o jogador sobe um torneio?** Se muda, a chave vai em
 * `CHAVES_DE_TORNEIO`.
 */

function arquivosFonte(dir: string, saida: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const p = join(dir, nome);
    if (statSync(p).isDirectory()) {
      arquivosFonte(p, saida);
    } else if (/\.tsx?$/.test(nome) && !nome.includes(".test.")) {
      saida.push(p);
    }
  }
  return saida;
}

function chavesDoCodigo(): Map<string, string[]> {
  const achadas = new Map<string, string[]>();
  for (const p of arquivosFonte("src")) {
    const src = readFileSync(p, "utf-8");
    if (!src.includes("queryKey")) continue;
    for (const m of src.matchAll(/queryKey:\s*\[\s*"([^"]+)"/g)) {
      const lista = achadas.get(m[1]) ?? [];
      lista.push(p.replace(/\\/g, "/"));
      achadas.set(m[1], lista);
    }
  }
  return achadas;
}

describe("refreshOnImport — catraca de classificação", () => {
  it("toda queryKey do app está classificada", () => {
    const classificadas = new Set<string>([...CHAVES_DE_TORNEIO, ...CHAVES_NAO_DERIVADAS]);
    const orfas: string[] = [];
    for (const [chave, arquivos] of chavesDoCodigo()) {
      if (!classificadas.has(chave)) orfas.push(`${chave}  (${arquivos[0]})`);
    }
    expect(
      orfas,
      "queryKey nova sem classificacao. Pergunte: o numero que ela mostra muda quando o jogador " +
      "sobe um torneio? Se muda, va em CHAVES_DE_TORNEIO; se nao, em CHAVES_NAO_DERIVADAS.\n  " +
      orfas.join("\n  "),
    ).toEqual([]);
  });

  it("nenhuma chave está nas DUAS listas", () => {
    const nas2 = CHAVES_DE_TORNEIO.filter((k) => (CHAVES_NAO_DERIVADAS as readonly string[]).includes(k));
    expect(nas2).toEqual([]);
  });

  it("as quatro chaves do bug reportado estão marcadas como de torneio", () => {
    // Regressão nominal: se alguem mover qualquer uma destas para a outra lista, o gráfico de
    // banca volta a congelar depois do upload e o teste acima não acusaria (ela continuaria
    // classificada).
    for (const k of ["bankroll-evolution", "progression-status", "proximo-passo", "training-daily-status"]) {
      expect(CHAVES_DE_TORNEIO as readonly string[], k).toContain(k);
    }
  });

  it("a lista não contém chave que não existe mais no código", () => {
    // O outro lado da catraca: chave removida do app fica na lista para sempre e a invalidacao
    // passa a mirar em nada, sem ninguem notar.
    const noCodigo = new Set(chavesDoCodigo().keys());
    const mortas = [...CHAVES_DE_TORNEIO, ...CHAVES_NAO_DERIVADAS].filter((k) => !noCodigo.has(k));
    expect(mortas, `chave na lista mas ausente do codigo: ${mortas.join(", ")}`).toEqual([]);
  });
});

describe("refreshOnImport — a recarga acontece por LOTE", () => {
  it("a fila de upload invalida uma vez, e nao por arquivo", () => {
    // Medido: um ciclo completo do dashboard custa ~17s de backend, e em 28/07 houve 14 uploads.
    // Por arquivo seriam 14 ciclos. O efeito tem que estar preso ao ESVAZIAMENTO da fila.
    const src = readFileSync("src/components/hud/UploadQueue.tsx", "utf-8");
    expect(src).toContain("invalidarAposImport");
    expect(src).toContain("EVENTO_LOTE");
    // o gatilho e "nao ha mais nada em andamento", nao o SET_STATUS de um item
    expect(src).toMatch(/emAndamento[\s\S]{0,400}invalidarAposImport/);
  });

  it("o dashboard escuta o evento de LOTE, nao o de arquivo", () => {
    const src = readFileSync("src/pages/Index.tsx", "utf-8");
    expect(src).toContain("EVENTO_LOTE");
    expect(src).not.toContain('addEventListener("leaklab:tournament-imported"');
  });
});
