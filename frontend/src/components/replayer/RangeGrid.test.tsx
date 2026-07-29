// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { RangeGrid } from "./RangeGrid";
import type { RangeSet } from "@/data/ranges";

// Prova de RENDER da legenda (o bug era visual, não de lógica).
// Reportado 2026-07-25: BTN @13.3bb no Replayer — grade toda VERMELHA (shove) com a
// legenda mostrando só "Raise / Fold". Nenhuma indicação de que vermelho = all-in.

/** Como a aba OPEN monta a range em push/fold: `hands` (raise+allin juntos) + frequencies
 *  com allin, e SEM o Set `allin` — exatamente o shape que quebrava a legenda. */
const PUSH_FOLD_OPEN: RangeSet = {
  label: "Open BTN (13bb)",
  raise: new Set(["AA", "KK", "QTo"]),
  frequencies: {
    AA:  { allin: 1.0 },
    KK:  { allin: 1.0 },
    QTo: { allin: 1.0 },
  },
};

const OPEN_100BB: RangeSet = {
  label: "Open BTN (100bb)",
  raise: new Set(["AA", "KK"]),
  frequencies: { AA: { raise: 1.0 }, KK: { raise: 1.0 } },
};

// Sem setupFiles global no vitest, o cleanup do testing-library não roda sozinho —
// sem isto o DOM do teste anterior vaza e "Shove" aparece na asserção do próximo.
afterEach(() => cleanup());

describe("RangeGrid — legenda renderizada", () => {
  it("push/fold: mostra SHOVE na legenda (o bug reportado)", () => {
    render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    expect(screen.getByText("Shove")).toBeTruthy();
    expect(screen.getByText("Fold")).toBeTruthy();
    // e não anuncia Raise, que não existe nesta grade
    expect(screen.queryByText("Raise")).toBeNull();
  });

  it("open 100bb: mostra Raise e não inventa Shove", () => {
    render(<RangeGrid range={OPEN_100BB} />);
    expect(screen.getByText("Raise")).toBeTruthy();
    expect(screen.queryByText("Shove")).toBeNull();
  });

  it("usa o rótulo canônico do projeto (Shove, nunca 'Allin'/'Jam')", () => {
    const { container } = render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    expect(container.textContent).not.toMatch(/allin/i);
    expect(container.textContent).not.toMatch(/\bjam\b/i);
  });
});

/**
 * A grade tem que dizer, na própria célula, se a mão é suited ou offsuit.
 *
 * Antes, `cellLabel` descartava o naipe de propósito — o comentário dele dizia "no suit suffix" —
 * e "AK" aparecia em DUAS células diferentes com cores diferentes. A única pista era a posição
 * em relação à diagonal, explicada num rodapé de 8px a 60% de opacidade.
 *
 * Isso importa mais do que parece: a range cresce SUITED primeiro e offsuit por último (medido
 * nas ranges capturadas: de UTG para HJ entram 16 suited contra 9 offsuit). Quem não distingue
 * os dois triângulos não consegue enxergar o padrão que precisa memorizar.
 */
describe("RangeGrid — suited × offsuit legível na célula", () => {
  it("marca s e o nas células, e não marca nada nos pares", () => {
    const { container } = render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    const celulas = Array.from(container.querySelectorAll("div.aspect-square"));
    expect(celulas.length).toBe(169);

    const comS = celulas.filter((c) => c.textContent?.endsWith("s"));
    const comO = celulas.filter((c) => c.textContent?.endsWith("o"));
    // 13x13: 13 pares na diagonal, 78 suited e 78 offsuit.
    expect(comS.length).toBe(78);
    expect(comO.length).toBe(78);

    // O par não recebe sufixo: "AA" e não "AAs".
    const pares = celulas.filter((c) => /^([2-9TJQKA])\1$/.test(c.textContent ?? ""));
    expect(pares.length).toBe(13);
  });

  it("a MESMA dupla de cartas aparece distinguível nas duas células", () => {
    const { container } = render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    const textos = Array.from(container.querySelectorAll("div.aspect-square"))
      .map((c) => c.textContent ?? "");
    // O bug era exatamente este: "AK" duas vezes, indistinguível.
    expect(textos.filter((t) => t === "AK").length).toBe(0);
    expect(textos).toContain("AKs");
    expect(textos).toContain("AKo");
  });

  it("a legenda explica a geometria em tamanho legível", () => {
    const { container } = render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    const legenda = Array.from(container.querySelectorAll("p"))
      .find((p) => p.textContent?.includes("suited"));
    expect(legenda).toBeTruthy();
    // 8px a 60% de opacidade era o mesmo que não existir.
    expect(legenda?.className).not.toMatch(/text-\[8px\]|text-\[6px\]/);
    expect(legenda?.className).not.toMatch(/muted-foreground\/\d/);
  });

  it("o sufixo s/o e legivel, e nao um risco de 7px", () => {
    // Reportado pelo usuario olhando a tela: "o s e o o estao muito pequenos e com dificil
    // leitura". Medido na celula de 40px: rank a 10px e sufixo a 7,2px com 70% de opacidade.
    //
    // A intencao original estava certa (o par de cartas e a informacao principal, o naipe e a
    // qualificacao) e a execucao nao: hierarquia se faz com diferenca perceptivel, nao com uma
    // que apaga o texto. Este teste existe porque o numero ja encolheu uma vez em silencio.
    const { container } = render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    const sufixos = Array.from(container.querySelectorAll("span"))
      .filter((sp) => sp.textContent === "s" || sp.textContent === "o");
    expect(sufixos.length).toBeGreaterThan(50);
    for (const sp of sufixos.slice(0, 5)) {
      const em = sp.className.match(/text-\[([\d.]+)em\]/);
      expect(em, `sufixo sem tamanho relativo: ${sp.className}`).toBeTruthy();
      expect(Number(em![1])).toBeGreaterThanOrEqual(0.8);
      const op = sp.className.match(/opacity-(\d+)/);
      expect(Number(op?.[1] ?? 100)).toBeGreaterThanOrEqual(85);
    }
  });

  it("a celula nao volta a ter fonte ilegivel", () => {
    // O corte e 8px, e nao "qualquer valor de um digito": `text-[9px]` e a base deliberada de
    // telas estreitas, onde a celula tem uns 26px e 12px ficaria apertado. O que este teste
    // impede e a volta ao 7px que originou o relato.
    const { container } = render(<RangeGrid range={PUSH_FOLD_OPEN} />);
    const classes = container.querySelector("div.aspect-square")?.className ?? "";
    const tamanhos = Array.from(classes.matchAll(/text-\[(\d+)px\]/g)).map((m) => Number(m[1]));
    expect(tamanhos.length).toBeGreaterThan(0);
    for (const t of tamanhos) expect(t).toBeGreaterThanOrEqual(9);
  });
});
