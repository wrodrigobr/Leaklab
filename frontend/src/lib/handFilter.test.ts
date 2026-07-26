import { describe, it, expect } from "vitest";
import { summarizeHandsForFilter, matchesResultFilter, filterHandIds, parseResultFilter } from "./handFilter";
import type { TournamentDecision } from "@/lib/api";

// A lista de mãos e a navegação do Replayer PRECISAM concordar sobre "isto é um erro?".
// Se divergirem, o filtro "erros" abre um replay que pula mãos diferentes — a mesma classe
// de bug (duas fontes) que já mordeu o menu do trainer e a legenda de ranges.

function dec(over: Partial<TournamentDecision>): TournamentDecision {
  return {
    id: 1, hand_id: "h1", street: "preflop", action_taken: "fold", best_action: "fold",
    label: "standard", score: 0, position: "BTN", hero_cards: "AhKh",
    gto_label: null, gto_action: null, n_active_opponents: null, adherence: null,
    ...over,
  } as unknown as TournamentDecision;
}

describe("summarizeHandsForFilter — elege a decisão PIOR da mão", () => {
  it("uma mão com erro no turn é classificada como erro (não pela 1ª decisão)", () => {
    const s = summarizeHandsForFilter([
      dec({ id: 1, hand_id: "h1", street: "preflop", label: "standard", score: 0 }),
      dec({ id: 2, hand_id: "h1", street: "turn", label: "clear_mistake", score: 0.8 }),
    ]);
    expect(s).toHaveLength(1);
    expect(s[0].category).toBe("error");
  });

  it("mão só com decisões corretas fica correct", () => {
    const s = summarizeHandsForFilter([
      dec({ id: 1, hand_id: "h2", label: "standard", score: 0 }),
      dec({ id: 2, hand_id: "h2", street: "flop", label: "standard", score: 0.01 }),
    ]);
    expect(s[0].category).toBe("correct");
  });

  it("detecta postflop e gto_label (base do filtro 'pendente')", () => {
    const s = summarizeHandsForFilter([
      dec({ hand_id: "h3", street: "flop", label: "standard", gto_label: null }),
    ]);
    expect(s[0].hasPostflop).toBe(true);
    expect(s[0].gtoLabel).toBeNull();
  });
});

describe("matchesResultFilter", () => {
  const err  = { category: "error" as const,      hasPostflop: false, gtoLabel: null };
  const ok   = { category: "correct" as const,    hasPostflop: false, gtoLabel: null };
  const att  = { category: "acceptable" as const, hasPostflop: false, gtoLabel: null };
  const heur = { category: "correct" as const,    hasPostflop: true,  gtoLabel: null };

  it("'all' aceita tudo", () => {
    [err, ok, att, heur].forEach((h) => expect(matchesResultFilter(h, "all")).toBe(true));
  });
  it("'error' só erros", () => {
    expect(matchesResultFilter(err, "error")).toBe(true);
    expect(matchesResultFilter(ok, "error")).toBe(false);
    expect(matchesResultFilter(att, "error")).toBe(false);
  });
  it("'attention' só aceitáveis", () => {
    expect(matchesResultFilter(att, "attention")).toBe(true);
    expect(matchesResultFilter(err, "attention")).toBe(false);
  });
  it("'pending' = postflop sem gto_label (heurística), independe da severidade", () => {
    expect(matchesResultFilter(heur, "pending")).toBe(true);
    expect(matchesResultFilter(ok, "pending")).toBe(false);
    expect(matchesResultFilter({ ...heur, gtoLabel: "gto_correct" }, "pending")).toBe(false);
  });
});

describe("filterHandIds — a playlist de navegação do Replayer", () => {
  const decisions = [
    dec({ id: 1, hand_id: "hA", label: "standard",      score: 0 }),
    dec({ id: 2, hand_id: "hB", label: "clear_mistake", score: 0.9 }),
    dec({ id: 3, hand_id: "hC", label: "standard",      score: 0 }),
    dec({ id: 4, hand_id: "hD", label: "small_mistake", score: 0.5 }),
  ];

  it("'all' mantém TODAS na ordem cronológica", () => {
    expect(filterHandIds(decisions, "all")).toEqual(["hA", "hB", "hC", "hD"]);
  });

  it("'error' devolve só as mãos com erro — é o que faz 'avançar' pular as corretas", () => {
    expect(filterHandIds(decisions, "error")).toEqual(["hB", "hD"]);
  });

  it("preserva a ordem cronológica (não reordena por severidade)", () => {
    const ids = filterHandIds(decisions, "error");
    expect(ids.indexOf("hB")).toBeLessThan(ids.indexOf("hD"));
  });

  it("filtro sem correspondência devolve lista vazia (navegação some, não quebra)", () => {
    expect(filterHandIds([dec({ hand_id: "hZ", label: "standard", score: 0 })], "error")).toEqual([]);
  });

  it("INVARIANTE: o que a lista mostra é exatamente o que o replay navega", () => {
    // simula a lista: resumo + matchesResultFilter (caminho do TournamentDetail)
    const daLista = summarizeHandsForFilter(decisions)
      .filter((h) => matchesResultFilter(h, "error"))
      .map((h) => h.id);
    // caminho do Replayer
    const doReplay = filterHandIds(decisions, "error");
    expect(doReplay).toEqual(daLista);
  });
});

describe("parseResultFilter — sanitiza o parâmetro da URL", () => {
  it("aceita os válidos", () => {
    expect(parseResultFilter("error")).toBe("error");
    expect(parseResultFilter("pending")).toBe("pending");
  });
  it("cai em 'all' no lixo/ausente", () => {
    expect(parseResultFilter(null)).toBe("all");
    expect(parseResultFilter("")).toBe("all");
    expect(parseResultFilter("drop table")).toBe("all");
  });
});
