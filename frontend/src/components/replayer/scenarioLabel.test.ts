// Sigla interna nao chega a tela.
//
// O card exibiu, em producao: "33 esta no range **hu_rfi** (9880%) @ 17bb". Duas coisas erradas
// numa frase so, e as duas de mesma natureza: dado interno vazando para o usuario.
//
//   `hu_rfi`  — identificador de cenario do motor. Os seis cenarios de heads-up criados em
//               07/08 nao tinham rotulo humano, e o fallback do card era `?? scenKey`: ou seja,
//               **garantia** de vazamento para todo cenario novo.
//   `9880%`   — `range_pct` em escala errada (ver `test_range_pct_unidade.py` no backend).
//
// O guarda abaixo nao lista os cenarios: ele le a lista DO MOTOR (o arquivo Python) e exige que
// cada um tenha rotulo. Um teste com a lista escrita a mao envelheceria junto com o mapa, que e
// exatamente como o defeito nasceu.
import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const RAIZ = path.resolve(__dirname, "../../..", "..");
const MOTOR = path.join(RAIZ, "backend", "leaklab", "preflop_gto_ranges.py");
const CARD = path.join(RAIZ, "frontend", "src", "components", "replayer", "SidePanels.tsx");
const PTBR = path.join(RAIZ, "frontend", "src", "i18n", "locales", "pt-BR", "replayer.json");

/** Cenarios que o motor consegue emitir, lidos das atribuicoes `base['scenario'] = '...'`. */
function cenariosDoMotor(): string[] {
  const src = fs.readFileSync(MOTOR, "utf-8");
  const achados = new Set<string>();
  for (const m of src.matchAll(/base\['scenario'\]\s*=\s*'([a-z0-9_]+)'/g)) achados.add(m[1]);
  for (const m of src.matchAll(/=\s*'[A-Z0-9_]+',\s*'([a-z0-9_]+)'/g)) achados.add(m[1]);
  return [...achados].filter((c) => c !== "hu_uncovered");   // motivo de ausencia, nao cenario
}

describe("rotulo de cenario", () => {
  it("a leitura do motor encontra cenarios (senao o teste e vacuo)", () => {
    expect(cenariosDoMotor().length).toBeGreaterThanOrEqual(5);
  });

  it("todo cenario do motor tem rotulo humano no card", () => {
    const card = fs.readFileSync(CARD, "utf-8");
    const bloco = card.slice(card.indexOf("const scenarioLabel"), card.indexOf("rangeLabelKey"));
    const semRotulo = cenariosDoMotor().filter((c) => !bloco.includes(`${c}:`));
    expect(semRotulo, `cenarios sem rotulo humano: ${semRotulo.join(", ")}`).toEqual([]);
  });

  it("o fallback NAO e a sigla — o vazamento nasceu dele", () => {
    const card = fs.readFileSync(CARD, "utf-8");
    const linha = card.split("\n").find((l) => l.includes("scen: scenarioLabel["));
    expect(linha, "a linha do fallback sumiu; o teste precisa ser reapontado").toBeTruthy();
    expect(linha).not.toMatch(/\?\?\s*whyChoice\.params\.scenKey/);
    expect(linha).toContain("scenGenerico");
  });

  it("os rotulos de heads-up existem em pt-BR e sao legiveis", () => {
    const pt = JSON.parse(fs.readFileSync(PTBR, "utf-8")).card as Record<string, string>;
    for (const k of ["scenHuRfi", "scenHuVsRfi", "scenHuVsLimp", "scenHuVs3bet",
                     "scenHuVs3betJam", "scenHuVs4bet", "scenGenerico"]) {
      expect(pt[k], `falta ${k}`).toBeTruthy();
      expect(pt[k], `${k} ainda parece sigla`).not.toMatch(/^[a-z0-9_]+$/);
    }
  });
});
