// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { metrics, type EscopoDoDashboard } from "./api";

/**
 * A garantia que o dono pediu: "Garanta que o Dashboard vai ser atualizado com estes filtros".
 *
 * ── Por que este arquivo existe, além do guarda de fonte ──────────────────────────────────────
 *
 * `escopoDoDashboard.test.ts` lê o FONTE e exige que nenhuma função monte o fragmento à mão. Este
 * aqui prova o COMPORTAMENTO: chama cada função de `metrics` com um escopo e olha a URL que saiu
 * no `fetch`. Os dois juntos fecham o furo de cada um -- fonte não prova que a URL sai certa, e um
 * teste de URL escrito à mão não descobre a função nova que alguém acrescentar.
 *
 * A lista de funções vem por INTROSPECÇÃO do objeto `metrics`, e não escrita aqui: função nova
 * entra na varredura sozinha. Foi assim que a varredura do servidor achou, hoje, que o
 * `/player/ev-summary` lia `last_n` direto da query e escapava das dimensões novas.
 */

/** Argumentos plausíveis por posição, para chamar funções que exigem mais que o escopo. */
const ARGS: Record<string, unknown[]> = {
  evLeakHands: ["preflop", "call", "raise"],
  playerStatsByPositionDetail: ["BTN", "three_bet"],
  playerStatsByPositionHands: ["BTN"],
  leakGraph: [90, "pt-BR"],
  career: ["pt-BR"],
  cognitiveFailures: ["pt-BR", 90],
  strategicTwin: ["pt-BR", 180],
};

/** Onde o escopo entra em cada função, quando não é o último argumento conhecido. */
const POSICAO_DO_ESCOPO: Record<string, number> = {
  evSummary: 0,
  level: 0,
  gtoQuality: 0,
  gtoAlignment: 0,
  gtoPosition: 0,
  gtoAlignmentMatrix: 0,
  resultsVsGto: 0,
  leakFinder: 0,
  evLeakHands: 3,
  playerStatsByPositionDetail: 3,
  playerStatsByPositionHands: 2,
  leakGraph: 2,
  career: 1,
  cognitiveFailures: 2,
  strategicTwin: 2,
};

const ESCOPO: EscopoDoDashboard = { tipo: "maos", n: 5000 };

let urls: string[] = [];

beforeEach(() => {
  urls = [];
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    urls.push(String(url));
    return { ok: true, status: 200, text: async () => "{}" } as unknown as Response;
  }));
});

afterEach(() => vi.unstubAllGlobals());

describe("o escopo CHEGA na URL de cada chamada do dashboard", () => {
  it("toda função de metrics que aceita escopo o manda no fetch", async () => {
    // A lista sai da DECLARAÇÃO, e não de uma heurística sobre o número de argumentos: a
    // primeira versão usava `fn.length >= 2` e acusou `addXp`, que não é do dashboard. Quem
    // aceita escopo é quem o declara, e é isso que o tipo já obriga.
    const fonte = readFileSync(join(import.meta.dirname, "api.ts"), "utf-8");
    const nomes = [...fonte.matchAll(/^\s*(\w+): \([^)]*escopo\?: EscopoDoDashboard[^)]*\) =>/gm)]
      .map((m) => m[1])
      .filter((n) => typeof (metrics as unknown as Record<string, unknown>)[n] === "function");
    expect(nomes.length, "a varredura não achou funções com escopo em `metrics`").toBeGreaterThan(15);

    const semEscopo: string[] = [];
    const naoChamadas: string[] = [];
    let conferidas = 0;

    for (const nome of nomes) {
      const fn = (metrics as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>)[nome];
      // a posição do escopo: a declarada, ou logo depois dos argumentos plausíveis, ou o padrão
      // (days, escopo) que é a forma da maioria
      const base = ARGS[nome] ?? [];
      const pos = POSICAO_DO_ESCOPO[nome] ?? (base.length ? base.length : 1);
      const args: unknown[] = [];
      for (let i = 0; i < pos; i++) args.push(base[i] ?? 90);
      args.push(ESCOPO);

      urls.length = 0;
      try {
        await fn(...args);
      } catch {
        naoChamadas.push(nome);
        continue;
      }
      if (!urls.length) { naoChamadas.push(nome); continue; }
      conferidas++;
      if (!urls[0].includes("maos=5000")) semEscopo.push(`${nome} -> ${urls[0]}`);
    }

    // CONTROLE: sem ele, um `fetch` que nunca fosse chamado deixaria a lista vazia e o teste
    // verde com zero cobertura.
    expect(conferidas, "nenhuma chamada chegou ao fetch").toBeGreaterThan(15);
    expect(semEscopo, "funções que receberam o escopo e não o mandaram na URL").toEqual([]);
    // e o que não deu para chamar fica DECLARADO: varredura que pula em silêncio é a que mente
    if (naoChamadas.length) console.log("  não chamadas:", naoChamadas.join(", "));
  });

  it("as três dimensões chegam com o parâmetro certo", async () => {
    await metrics.evolution(90, { tipo: "torneios", n: 50 });
    expect(urls.at(-1)).toContain("last_n=50");

    await metrics.evolution(90, { tipo: "maos", n: 5000 });
    expect(urls.at(-1)).toContain("maos=5000");

    await metrics.evolution(90, { tipo: "periodo", de: "2026-06-01", ate: "2026-06-30" });
    expect(urls.at(-1)).toContain("de=2026-06-01");
    expect(urls.at(-1)).toContain("ate=2026-06-30");
  });

  it("o HISTÓRICO chega como `last_n=0`, e não como ausência", async () => {
    // A cicatriz de 03/09: "Todos" mandava `null`, que caía no fallback silencioso de 90 dias no
    // servidor -- o botão mentia, e nenhum dos ~14 chamadores via o acervo de verdade.
    await metrics.evolution(90, { tipo: "torneios", n: 0 });
    expect(urls.at(-1), "o histórico virou ausência de parâmetro").toContain("last_n=0");
  });
});
