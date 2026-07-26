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
