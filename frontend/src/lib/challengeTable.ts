// Monta um ReplayStep 9-max sintético a partir do spot do Desafio do Dia, pra renderizar
// na mesma mesa (PokerTableV3) que o Leak Trainer usa. Espelha o ramo PREFLOP do buildStep
// do Leak Trainer (o desafio é preflop: rfi / vs_rfi / vs_3bet). Mantido isolado de propósito,
// o desafio nunca deve depender do estado interno do Leak Trainer.
import type { DailyChallengeSpot, ReplayStep } from "@/lib/api";

const ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

export function buildChallengeStep(sp: DailyChallengeSpot) {
  const bb = 100;
  const heroPos = sp.position, vsPos = sp.vs_position || "", scen = sp.scenario;
  const heroIdx = ORDER.indexOf(heroPos);
  const vsIdx = vsPos ? ORDER.indexOf(vsPos) : -1;
  const stackChips = Math.round((sp.stack_bb || 50) * bb);

  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets: Record<string, number> = {};
  const folded: string[] = [];

  ORDER.forEach((pos, i) => {
    const sn = String(i + 1);
    const isHero = pos === heroPos;
    seats[sn] = { player: isHero ? "Hero" : pos, stack: stackChips, pos };
    if (pos === "SB") bets[sn] = Math.round(bb * 0.5);
    else if (pos === "BB") bets[sn] = bb;
    let isFolded = false;
    if (scen === "rfi") isFolded = i < heroIdx;
    else if (scen === "vs_rfi") isFolded = i < heroIdx && pos !== vsPos;
    else isFolded = !isHero && pos !== vsPos;
    if (isFolded) folded.push(isHero ? "Hero" : pos);
  });

  if (scen === "vs_rfi" && vsIdx >= 0) {
    bets[String(vsIdx + 1)] = Math.round((sp.facing_size || 2.2) * bb);
  } else if (scen === "vs_3bet") {
    if (heroIdx >= 0) bets[String(heroIdx + 1)] = Math.round(2.2 * bb);
    if (vsIdx >= 0) bets[String(vsIdx + 1)] = Math.round((sp.facing_size || 8) * bb);
  }

  const potChips = Object.values(bets).reduce((a, b) => a + b, 0);
  const step = {
    type: "action", street: "preflop", seats, bets, folded,
    pot_bb: potChips / bb, pot: potChips, bb,
    button: ORDER.indexOf("BTN") + 1, board: [],
    player: "Hero", seat: heroIdx + 1, is_hero: true,
    preflop_gto: { available: false, scenario: scen, vs_position: vsPos || null },
  } as unknown as ReplayStep;

  const heroCards = (sp.hero_cards ?? []).map((c) => `${c.rank}${c.suit}`);
  return { step, heroCards, bb };
}
