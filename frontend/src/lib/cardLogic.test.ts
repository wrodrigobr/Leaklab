import { describe, it, expect } from "vitest";
import {
  computeEffectiveGtoLabel,
  livePlayers,
  isMultiwayPot,
  isPpMuted,
  idealActionSource,
  verdictStrategy,
  verdictLevel,
} from "./cardLogic";

// ── FEAT-20: veredito de display em 3 níveis (Correto/Aceitável/Erro) ──────────
describe("verdictLevel — colapso 4 severidades → 3 níveis", () => {
  it("standard → correct", () => expect(verdictLevel("standard")).toBe("correct"));
  it("marginal → acceptable", () => expect(verdictLevel("marginal")).toBe("acceptable"));
  it("small_mistake → error", () => expect(verdictLevel("small_mistake")).toBe("error"));
  it("clear_mistake → error", () => expect(verdictLevel("clear_mistake")).toBe("error"));
  it("desconhecido/None → null", () => {
    expect(verdictLevel(null)).toBeNull();
    expect(verdictLevel(undefined)).toBeNull();
    expect(verdictLevel("")).toBeNull();
    expect(verdictLevel("gto_critical")).toBeNull(); // frequência NÃO é veredito
  });
  it("normaliza caixa/espaço", () => {
    expect(verdictLevel(" Small_Mistake ")).toBe("error");
  });
});

// ── veredito vem da MÃO, não do range agregado (bug mão 5: A2s) ────────────────
describe("verdictStrategy — mão específica > range agregado", () => {
  // Nó multiway aproximado: o RANGE folda 63%, mas A2s (bloqueador + draw) LEVANTA 93%.
  const range = [
    { action: "fold", frequency: 0.63, ev_bb: 0 },
    { action: "raise", frequency: 0.34, ev_bb: 0.4 },
    { action: "call", frequency: 0.03, ev_bb: -0.8 },
  ];
  const hand = [
    { action: "raise", frequency: 0.93, ev_bb: 1.5 },
    { action: "call", frequency: 0.06, ev_bb: -0.8 },
    { action: "fold", frequency: 0.01, ev_bb: -1.5 },
  ];

  it("postflop com hand_strategy → recomenda a ação modal da MÃO (raise), não do range (fold)", () => {
    const v = verdictStrategy(true, hand, [...range].sort((a, b) => b.frequency - a.frequency));
    expect(v[0].action).toBe("raise");           // header diria "GTO recomenda Raise"
    expect(v[0].frequency).toBeCloseTo(0.93);
    // e o call do hero é julgado pela freq DELE na mão (6%), não no range (3%)
    expect(computeEffectiveGtoLabel(v, null, "call")).toBe("gto_critical"); // 6% < 10%
  });

  it("postflop SEM hand_strategy → cai no range", () => {
    const sorted = [...range].sort((a, b) => b.frequency - a.frequency);
    expect(verdictStrategy(true, null, sorted)).toBe(sorted);
    expect(verdictStrategy(true, [], sorted)).toBe(sorted);
  });

  it("preflop (range estático) nunca usa hand_strategy", () => {
    const sorted = [...range].sort((a, b) => b.frequency - a.frequency);
    expect(verdictStrategy(false, hand, sorted)).toBe(sorted);
  });
});

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
