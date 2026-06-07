/**
 * Gerador de hand history no formato PokerStars.
 *
 * Recebe entrada estruturada (jogadores, ações por street, etc) e produz
 * o texto em formato PokerStars que pode ser parseado pelo parser do backend
 * sem nenhuma adaptação — round-trip garantido.
 *
 * Formato de referência:
 *   PokerStars Hand #ID: Tournament #TID, $X+$Y USD Hold'em No Limit - Level N (sb/bb) - DATE
 *   Table 'TID' Nmax Seat #B is the button
 *   Seat 1: Player1 (3000 in chips)
 *   ...
 *   Player: posts the ante X
 *   ...
 *   Player1: posts small blind 40
 *   Player2: posts big blind 80
 *   *** HOLE CARDS ***
 *   Dealt to Hero [Ah Kd]
 *   Player: folds | calls X | raises X to Y | checks | bets X | raises X to Y and is all-in
 *   *** FLOP *** [As 2c 7d]
 *   *** TURN *** [As 2c 7d] [Kh]
 *   *** RIVER *** [As 2c 7d Kh] [3s]
 *   *** SHOW DOWN ***
 *   Player: shows [Ah Kd] (...)
 *   Player collected X from pot
 *   *** SUMMARY ***
 *   Total pot X | Rake 0
 *   Board [As 2c 7d Kh 3s]
 *   Seat N: Player ... (button/small blind/big blind) won (X) / folded / mucked
 */

export interface PlayerInput {
  seat: number;        // 1..9
  name: string;
  stack: number;       // em chips
  bounty?: number;     // PKO opcional
}

export type Street = 'preflop' | 'flop' | 'turn' | 'river';

export type ActionType =
  | 'fold' | 'check' | 'call'
  | 'bet' | 'raise' | 'allin';

export interface HandAction {
  player: string;      // nome do jogador
  street: Street;
  action: ActionType;
  amount?: number;     // pra bet/call/raise/allin: total que o jogador colocou no pote naquela rodada
}

export interface HandInput {
  // Metadata
  handId:        string;       // numérico
  tournamentId:  string;       // numérico
  buyIn?:        string;       // ex "0.98+0.12"
  level?:        string;       // ex "VII"
  sb:            number;
  bb:            number;
  ante:          number;
  dateIso?:      string;       // ISO datetime (default: now)
  tableId?:      string;       // default: tournamentId
  maxSeats?:     2 | 6 | 8 | 9;// default 9

  // Mesa
  players:       PlayerInput[];
  buttonSeat:    number;
  heroName:      string;       // qual player é o hero
  heroCards:     string;       // ex "Ah Kd" (espaço entre cartas)

  // Ação
  actions:       HandAction[]; // em ordem cronológica
  board:         { flop?: string[]; turn?: string; river?: string };

  // Showdown (opcional)
  shows?:        { player: string; cards: string }[];  // "Ah Kd"
  winner?:       { player: string; amount: number; handDesc?: string };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso?: string): string {
  const d = iso ? new Date(iso) : new Date();
  // "2025/07/22 10:10:49 ET"
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${yyyy}/${mm}/${dd} ${hh}:${mi}:${ss} ET`;
}

function romanLevel(level?: string): string {
  return level && level.trim() ? level.trim() : 'I';
}

function seatLine(p: PlayerInput): string {
  const bountyStr = p.bounty != null ? ` bounty $${p.bounty.toFixed(2)}` : '';
  return `Seat ${p.seat}: ${p.name} (${p.stack} in chips)${bountyStr}`;
}

function actionLine(a: HandAction, runningStreetBet: Map<string, number>): string {
  switch (a.action) {
    case 'fold':  return `${a.player}: folds`;
    case 'check': return `${a.player}: checks`;
    case 'call': {
      // PokerStars: "calls X" — X = INCREMENTO (o que falta pra igualar), não o total.
      // Sem subtrair o já investido na street (ex.: o próprio open), o call somaria de
      // novo o open (open 200 + "calls 857" = 1057 em vez de igualar a 857).
      const prev = runningStreetBet.get(a.player) ?? 0;
      const total = a.amount ?? 0;
      return `${a.player}: calls ${Math.max(0, total - prev)}`;
    }
    case 'bet':   return `${a.player}: bets ${a.amount ?? 0}`;
    case 'raise': {
      // PokerStars: "raises X to Y" — X = increment, Y = total apostado nesta street
      const prev = runningStreetBet.get(a.player) ?? 0;
      const total = a.amount ?? 0;
      const increment = Math.max(0, total - prev);
      return `${a.player}: raises ${increment} to ${total}`;
    }
    case 'allin': {
      const prev = runningStreetBet.get(a.player) ?? 0;
      const total = a.amount ?? 0;
      const increment = Math.max(0, total - prev);
      // Se total > 0 e houve aposta prévia, é raise all-in; senão bet all-in.
      const anyPrevBetInStreet = Array.from(runningStreetBet.values()).some(v => v > 0);
      if (anyPrevBetInStreet && prev < total) {
        return `${a.player}: raises ${increment} to ${total} and is all-in`;
      }
      return `${a.player}: bets ${total} and is all-in`;
    }
  }
}

// ── Generator ─────────────────────────────────────────────────────────────────

export function generateHandHistory(input: HandInput): string {
  const lines: string[] = [];
  const maxSeats = input.maxSeats ?? 9;
  const tableId  = input.tableId  ?? input.tournamentId;
  const buyIn    = input.buyIn    ? `$${input.buyIn} USD ` : '';

  // 1. Header
  lines.push(
    `PokerStars Hand #${input.handId}: Tournament #${input.tournamentId}, ${buyIn}Hold'em No Limit - Level ${romanLevel(input.level)} (${input.sb}/${input.bb}) - ${fmtDate(input.dateIso)}`
  );
  lines.push(`Table '${tableId}' ${maxSeats}-max Seat #${input.buttonSeat} is the button`);

  // 2. Seats
  for (const p of input.players) {
    lines.push(seatLine(p));
  }

  // 3. Antes
  if (input.ante > 0) {
    for (const p of input.players) {
      lines.push(`${p.name}: posts the ante ${input.ante}`);
    }
  }

  // 4. Blinds — derivadas da ordem cronológica clockwise do button
  const sbPlayer = findSbPlayer(input);
  const bbPlayer = findBbPlayer(input);
  if (sbPlayer) lines.push(`${sbPlayer.name}: posts small blind ${input.sb}`);
  if (bbPlayer) lines.push(`${bbPlayer.name}: posts big blind ${input.bb}`);

  // 5. Hole cards
  lines.push(`*** HOLE CARDS ***`);
  lines.push(`Dealt to ${input.heroName} [${input.heroCards}]`);

  // 6. Ações por street
  const streets: Street[] = ['preflop', 'flop', 'turn', 'river'];
  for (const street of streets) {
    if (street !== 'preflop') {
      const boardLine = buildBoardLine(street, input.board);
      if (!boardLine) break;  // sem cartas dessa street → mão parou antes
      lines.push(boardLine);
    }

    // Reset bets running pra esta street; SB/BB já contam no preflop
    const runningStreetBet = new Map<string, number>();
    if (street === 'preflop') {
      if (sbPlayer) runningStreetBet.set(sbPlayer.name, input.sb);
      if (bbPlayer) runningStreetBet.set(bbPlayer.name, input.bb);
    }

    const streetActions = input.actions.filter(a => a.street === street);
    for (const a of streetActions) {
      lines.push(actionLine(a, runningStreetBet));
      // Atualiza running bet do player nesta street (pra próximas linhas de raise)
      if (a.action === 'call' || a.action === 'bet' || a.action === 'raise' || a.action === 'allin') {
        runningStreetBet.set(a.player, Math.max(runningStreetBet.get(a.player) ?? 0, a.amount ?? 0));
      }
    }
  }

  // 7. Showdown
  if (input.shows && input.shows.length > 0) {
    lines.push(`*** SHOW DOWN ***`);
    for (const s of input.shows) {
      lines.push(`${s.player}: shows [${s.cards}]`);
    }
  }
  if (input.winner) {
    lines.push(`${input.winner.player} collected ${input.winner.amount} from pot`);
  }

  // 8. Summary
  lines.push(`*** SUMMARY ***`);
  const totalPot = computeTotalPot(input);
  lines.push(`Total pot ${totalPot} | Rake 0`);
  const fullBoard = buildFullBoardString(input.board);
  if (fullBoard) lines.push(`Board [${fullBoard}]`);

  for (const p of input.players) {
    const tag =
      p.seat === input.buttonSeat ? ' (button)' :
      sbPlayer?.name === p.name   ? ' (small blind)' :
      bbPlayer?.name === p.name   ? ' (big blind)' : '';
    const folded = input.actions.some(a =>
      a.player === p.name && a.action === 'fold'
    );
    if (input.winner?.player === p.name) {
      lines.push(`Seat ${p.seat}: ${p.name}${tag} collected (${input.winner.amount})`);
    } else if (folded) {
      lines.push(`Seat ${p.seat}: ${p.name}${tag} folded before Flop (didn't bet)`);
    } else {
      lines.push(`Seat ${p.seat}: ${p.name}${tag} mucked`);
    }
  }

  return lines.join('\n');
}

// ── Helpers internos ──────────────────────────────────────────────────────────

function findSbPlayer(input: HandInput): PlayerInput | undefined {
  // Após o button, o próximo seat ocupado clockwise é SB.
  return nextOccupiedSeat(input, input.buttonSeat);
}

function findBbPlayer(input: HandInput): PlayerInput | undefined {
  const sb = findSbPlayer(input);
  if (!sb) return undefined;
  return nextOccupiedSeat(input, sb.seat);
}

function nextOccupiedSeat(input: HandInput, fromSeat: number): PlayerInput | undefined {
  const maxSeats = input.maxSeats ?? 9;
  const seats = new Set(input.players.map(p => p.seat));
  for (let i = 1; i <= maxSeats; i++) {
    const s = ((fromSeat - 1 + i) % maxSeats) + 1;
    if (seats.has(s)) return input.players.find(p => p.seat === s);
  }
  return undefined;
}

function buildBoardLine(street: Street, board: HandInput['board']): string | null {
  if (street === 'flop') {
    if (!board.flop || board.flop.length !== 3) return null;
    return `*** FLOP *** [${board.flop.join(' ')}]`;
  }
  if (street === 'turn') {
    if (!board.turn || !board.flop) return null;
    return `*** TURN *** [${board.flop.join(' ')}] [${board.turn}]`;
  }
  if (street === 'river') {
    if (!board.river || !board.turn || !board.flop) return null;
    return `*** RIVER *** [${board.flop.join(' ')}] [${board.turn}] [${board.river}]`;
  }
  return null;
}

function buildFullBoardString(board: HandInput['board']): string {
  const parts: string[] = [];
  if (board.flop) parts.push(...board.flop);
  if (board.turn) parts.push(board.turn);
  if (board.river) parts.push(board.river);
  return parts.join(' ');
}

function computeTotalPot(input: HandInput): number {
  // Antes + blinds + tudo que entrou via call/bet/raise/allin.
  let pot = input.ante * input.players.length;
  pot += input.sb + input.bb;
  // Para call/bet/raise/allin: o valor "amount" representa total apostado naquela street pelo player.
  // Somar increments por player+street.
  const byStreetPlayer = new Map<string, number>();
  for (const a of input.actions) {
    if (a.action === 'fold' || a.action === 'check') continue;
    const k = `${a.street}|${a.player}`;
    const prev = byStreetPlayer.get(k) ?? 0;
    const incoming = Math.max(0, (a.amount ?? 0) - prev);
    pot += incoming;
    byStreetPlayer.set(k, a.amount ?? 0);
  }
  // SB/BB já apostaram antes — descontar pra evitar dupla contagem no preflop
  const sbP = findSbPlayer(input);
  const bbP = findBbPlayer(input);
  if (sbP) {
    const k = `preflop|${sbP.name}`;
    if (byStreetPlayer.has(k)) pot -= input.sb;
  }
  if (bbP) {
    const k = `preflop|${bbP.name}`;
    if (byStreetPlayer.has(k)) pot -= input.bb;
  }
  return Math.round(pot);
}
