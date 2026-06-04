import { describe, it, expect } from "vitest";
import {
  computeEffectiveGtoLabel,
  livePlayers,
  isMultiwayPot,
  isPpMuted,
  idealActionSource,
} from "./cardLogic";

// ── shove↔allin (varredura turn) ──────────────────────────────────────────────
describe("computeEffectiveGtoLabel — shove↔allin", () => {
  const allinDom = [
    { action: "allin", frequency: 0.96 },
    { action: "check", frequency: 0.04 },
  ];
  it("shove/jam/allin num nó allin-dominante = gto_correct (não falso crítico)", () => {
    expect(computeEffectiveGtoLabel(allinDom, null, "shove")).toBe("gto_correct");
    expect(computeEffectiveGtoLabel(allinDom, null, "jam")).toBe("gto_correct");
    expect(computeEffectiveGtoLabel(allinDom, null, "allin")).toBe("gto_correct");
  });
  it("shove num nó check-100% segue crítico (correto)", () => {
    expect(computeEffectiveGtoLabel([{ action: "check", frequency: 1 }], null, "shove")).toBe("gto_critical");
  });
  it("buckets de frequência da ação jogada", () => {
    const mk = (f: number) => [{ action: "bet", frequency: f }];
    expect(computeEffectiveGtoLabel(mk(0.7), null, "bet")).toBe("gto_correct");
    expect(computeEffectiveGtoLabel(mk(0.4), null, "bet")).toBe("gto_mixed");
    expect(computeEffectiveGtoLabel(mk(0.15), null, "bet")).toBe("gto_minor_deviation");
    expect(computeEffectiveGtoLabel(mk(0.02), null, "bet")).toBe("gto_critical");
  });
  it("sem strategy ao vivo, cai no label armazenado", () => {
    expect(computeEffectiveGtoLabel(null, "gto_mixed", "bet")).toBe("gto_mixed");
  });
});

// ── multiway (varredura postflop multiway) ────────────────────────────────────
describe("multiway", () => {
  const seats9 = Object.fromEntries(Array.from({ length: 9 }, (_, i) => [i, {}]));
  it("livePlayers = assentos − foldados", () => {
    expect(livePlayers(seats9, ["a", "b", "c", "d", "e"])).toBe(4);
    expect(livePlayers(seats9, [])).toBe(9);
    expect(livePlayers(undefined, [])).toBeNull();
  });
  it("multiway = postflop com 3+ no pote", () => {
    expect(isMultiwayPot(true, 4)).toBe(true);   // 4-way
    expect(isMultiwayPot(true, 3)).toBe(true);   // 3-way
    expect(isMultiwayPot(true, 2)).toBe(false);  // HU
    expect(isMultiwayPot(false, 4)).toBe(false); // preflop nunca
    expect(isMultiwayPot(true, null)).toBe(false);
  });
});

// ── +pp mudo (varredura postflop solver + heurística) ─────────────────────────
describe("isPpMuted", () => {
  const base = { showAuditPreflop: false, effectiveGtoLabel: null, eq: 0.6, reqShown: 0.4, isActionOk: true };
  it("mudo quando cobertura preflop (range)", () => {
    expect(isPpMuted({ ...base, showAuditPreflop: true })).toBe(true);
  });
  it("mudo quando veredito do solver (effectiveGtoLabel)", () => {
    expect(isPpMuted({ ...base, effectiveGtoLabel: "gto_critical" })).toBe(true);
  });
  it("mudo quando ficaria verde (eq≥req) mas a ação foi ERRO (heurística +EV vs ERRO)", () => {
    expect(isPpMuted({ ...base, isActionOk: false })).toBe(true);
  });
  it("COLORIDO quando ação correta e pot odds é a base (eq≥req, isActionOk)", () => {
    expect(isPpMuted(base)).toBe(false);
  });
  it("COLORIDO quando eq<req (vermelho consistente)", () => {
    expect(isPpMuted({ ...base, eq: 0.3, isActionOk: false })).toBe(false);
  });
});

// ── idealAction (varredura squeeze) ───────────────────────────────────────────
describe("idealActionSource — prioridade", () => {
  const ctx = { preflopNoCoverage: false, isShoveFb: false, isPostflop: false, pgAvailable: false, hasGto: false };
  it("sem cobertura preflop → none", () => {
    expect(idealActionSource({ ...ctx, preflopNoCoverage: true })).toBe("none");
  });
  it("vs_shove fallback → potodds", () => {
    expect(idealActionSource({ ...ctx, isShoveFb: true })).toBe("potodds");
  });
  it("preflop COBERTO usa o RANGE — mesmo com hasGto (o fix do squeeze)", () => {
    expect(idealActionSource({ ...ctx, pgAvailable: true, hasGto: true })).toBe("range");
    expect(idealActionSource({ ...ctx, pgAvailable: true, hasGto: false })).toBe("range");
  });
  it("postflop com gto_label → solver", () => {
    expect(idealActionSource({ ...ctx, isPostflop: true, hasGto: true })).toBe("solver");
  });
  it("sem nada → engine", () => {
    expect(idealActionSource({ ...ctx, isPostflop: true })).toBe("engine");
  });
});
