import { describe, it, expect } from "vitest";
import { rangeActionPresence, getHandFreq, type RangeSet } from "./ranges";

// ── Legenda da grade de ranges deriva do que é REALMENTE pintado ──────────────
// Bug reportado 2026-07-25: no Replayer, BTN @13.3bb (zona push/fold), a grade
// ficava toda VERMELHA (allin) mas a legenda só mostrava "Raise / Fold" — nenhuma
// indicação de que vermelho = shove. Causa: as células pintavam por `frequencies`
// e a legenda olhava os Sets (`range.allin.size`), que a aba OPEN não popula.
// Invariante: o que é pintado TEM que estar na legenda (espelha menu_with_strategy
// do backend).

/** Range estilo aba OPEN em push/fold: só `raise` Set + frequencies com allin, SEM Set allin. */
const PUSH_FOLD_OPEN: RangeSet = {
  label: "Open BTN (13bb)",
  raise: new Set(["AA", "QTo", "K5s"]),        // `hands` do backend = raise + allin juntos
  // allin: AUSENTE de propósito — é exatamente o caso do bug
  frequencies: {
    AA:   { allin: 1.0 },
    QTo:  { allin: 1.0 },
    K5s:  { allin: 1.0 },
  },
};

describe("rangeActionPresence — legenda espelha o que é pintado", () => {
  it("detecta shove quando só as frequencies têm allin (aba OPEN, sem Set allin)", () => {
    const p = rangeActionPresence(PUSH_FOLD_OPEN);
    expect(p.allin).toBe(true);   // ← o bug: antes a legenda não sabia disso
    expect(p.fold).toBe(true);    // as 166 células restantes são fold
  });

  it("NÃO anuncia raise quando a range é puro push/fold", () => {
    // Anunciar "Raise" numa grade sem nenhuma célula de raise é a outra metade do bug
    expect(rangeActionPresence(PUSH_FOLD_OPEN).raise).toBe(false);
  });

  it("invariante: toda ação com frequência pintada aparece na legenda", () => {
    const mixed: RangeSet = {
      label: "mix",
      raise: new Set(["AA", "KK"]),
      frequencies: {
        AA: { raise: 0.6, allin: 0.4 },
        KK: { raise: 0.5, call: 0.5 },
      },
    };
    const p = rangeActionPresence(mixed);
    // varre as células e confere: o que getHandFreq pinta, a presença reporta
    for (const hand of ["AA", "KK"]) {
      const f = getHandFreq(hand, mixed);
      if ((f.raise ?? 0) > 0.001) expect(p.raise).toBe(true);
      if ((f.call  ?? 0) > 0.001) expect(p.call).toBe(true);
      if ((f.allin ?? 0) > 0.001) expect(p.allin).toBe(true);
    }
  });

  it("range só de raise não anuncia call nem shove", () => {
    const openOnly: RangeSet = {
      label: "open 100bb",
      raise: new Set(["AA"]),
      frequencies: { AA: { raise: 1.0 } },
    };
    const p = rangeActionPresence(openOnly);
    expect(p.raise).toBe(true);
    expect(p.call).toBe(false);
    expect(p.allin).toBe(false);
    expect(p.fold).toBe(true);
  });

  it("fallback sem frequencies: deriva dos Sets (comportamento legado preservado)", () => {
    const legacy: RangeSet = {
      label: "legacy",
      raise: new Set(["AA"]),
      call:  new Set(["KK"]),
      allin: new Set(["QQ"]),
    };
    const p = rangeActionPresence(legacy);
    expect(p.raise).toBe(true);
    expect(p.call).toBe(true);
    expect(p.allin).toBe(true);
  });
});
