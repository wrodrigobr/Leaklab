// hhAutoFinish.ts — quando o hero JÁ foldou, o resto da mão não afeta a análise
// (só decisões do hero contam). Resolve a mão de forma válida e aleatória: todos os
// jogadores ativos restantes foldam para UM vencedor aleatório (acaba na street
// atual, sem precisar de board/showdown). Pure/testável.
import type { HandAction, PlayerInput, Street } from "./hhGenerator";

interface FinishInput {
  players: PlayerInput[];
  buttonSeat: number;
  actions: HandAction[];
  sb: number; bb: number; ante: number;
  board: { flop: string[]; turn: string; river: string };
}

export interface FinishResult {
  actions: HandAction[];   // ações originais + folds dos villains restantes
  winnerName: string;
  potChips: number;
}

// Ordem clockwise a partir do SB (depois do button): [SB, BB, …, BTN].
export function clockwiseFromSb(players: PlayerInput[], buttonSeat: number): PlayerInput[] {
  if (players.length === 0) return [];
  const seatNums = players.map(p => p.seat).sort((a, b) => a - b);
  const btnIdx = seatNums.indexOf(buttonSeat);
  if (btnIdx === -1) return [...players];
  const out: PlayerInput[] = [];
  for (let i = 1; i <= seatNums.length; i++) {
    const seat = seatNums[(btnIdx + i) % seatNums.length];
    const p = players.find(x => x.seat === seat);
    if (p) out.push(p);
  }
  return out;
}

export function deriveStreet(board: { flop: string[]; turn: string; river: string }): Street {
  if (board.river) return "river";
  if (board.turn) return "turn";
  if (board.flop.length === 3) return "flop";
  return "preflop";
}

// Pote total em fichas: antes + blinds + maior comprometido por jogador em cada street.
export function totalPot(s: FinishInput): number {
  let pot = s.ante * s.players.length;
  const cw = clockwiseFromSb(s.players, s.buttonSeat);
  for (const st of ["preflop", "flop", "turn", "river"] as Street[]) {
    const committed = new Map<string, number>();
    if (st === "preflop") {
      if (cw[0]) committed.set(cw[0].name, s.sb);
      if (cw[1]) committed.set(cw[1].name, s.bb);
    }
    for (const a of s.actions.filter(x => x.street === st)) {
      if (a.action === "fold" || a.action === "check") continue;
      committed.set(a.player, Math.max(committed.get(a.player) ?? 0, a.amount ?? 0));
    }
    for (const v of committed.values()) pot += v;
  }
  return pot;
}

// Finaliza a mão: villains ativos restantes foldam pra um vencedor aleatório.
// `rand` injetável pra teste (default Math.random).
export function autoFinishAfterFold(s: FinishInput, rand: () => number = Math.random): FinishResult | null {
  const cw = clockwiseFromSb(s.players, s.buttonSeat);
  if (cw.length < 2) return null;
  const folded = new Set(s.actions.filter(a => a.action === "fold").map(a => a.player));
  const active = cw.filter(p => !folded.has(p.name));
  const street = deriveStreet(s.board);
  const actions = [...s.actions];
  let winner: PlayerInput;
  if (active.length <= 1) {
    winner = active[0] ?? cw[cw.length - 1];
  } else {
    winner = active[Math.floor(rand() * active.length) % active.length];
    for (const p of active) {
      if (p.seat !== winner.seat) actions.push({ player: p.name, street, action: "fold" });
    }
  }
  return { actions, winnerName: winner.name, potChips: totalPot(s) };
}
