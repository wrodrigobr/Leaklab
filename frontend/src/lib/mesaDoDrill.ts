import type { DrillSpot, DrillTableState, ReplayStep } from "@/lib/api";

/**
 * De um spot de treino para o `step` que a `PokerTableV3` desenha.
 *
 * ── Por que isto saiu do GhostTable ───────────────────────────────────────────────────────────
 *
 * Vivia dentro de `GhostTable.tsx`, e o modo Prática (1 a 4 mesas preflop, 16/09) precisa da
 * mesma conversão. Copiar criaria dois lugares para montar a mesma mesa, e quando eles divergem
 * o jogador vê a mesa certa num treino e a errada no outro sem nada acusar.
 *
 * ── Os dois caminhos, e qual deles vale ───────────────────────────────────────────────────────
 *
 * Com `tableState` (o Ghost Table busca em `/player/spots/drill/<id>/table`, e o Prática recebe
 * junto das mesas) a mesa é FIEL: folds, botão e stacks vêm do servidor.
 *
 * Sem ele, o fallback APROXIMA, e a aproximação tem um defeito conhecido: a aposta enfrentada vai
 * para o assento imediatamente anterior ao herói, que só por acaso é o de quem abriu. É por isso
 * que o Prática monta a mesa no servidor, onde a ordem de ação preflop já mora, em vez de usar
 * este fallback: com UTG abrindo e o herói no BTN, o fallback põe a aposta no CO.
 */

/** O que a conversão precisa do spot. Frouxo de propósito: o Ghost Table manda um `DrillSpot`
 *  inteiro, o Prática manda o mínimo, e nenhum dos dois deve moldar o outro. */
export type SpotParaMesa = Partial<DrillSpot> & { hero_cards?: string | null };

export const parseCards = (c: string | null | undefined): string[] =>
  c ? (c.trim().startsWith('[')
        ? (() => { try { return JSON.parse(c) as string[]; } catch { return []; } })()
        : (c.match(/[2-9TJQKAakqjt][shdcSHDC]/g) ?? []))
    : [];

export function buildDrillStep(spot: SpotParaMesa, tableState?: DrillTableState | null): { step: ReplayStep; hero: string; heroCards: string[]; bb: number } {
  const HERO = 'Hero';
  const bb   = spot.level_bb ?? 100;

  // ── Caminho REAL: mesa fiel reconstruída do endpoint /table (folds/botão/stacks reais) ──
  if (tableState && tableState.seats && tableState.seats.length) {
    const realBb = tableState.bb_chips || bb;
    const seats: Record<string, { player: string; stack: number; pos: string }> = {};
    const bets:  Record<string, number> = {};
    const folded: string[] = [];
    let heroSeatNum = 1;
    let villainN = 0;   // anonimiza: V1, V2, V3... (no drill o nome real não importa)
    for (const s of tableState.seats) {
      const sn = String(s.seat);
      const name = s.hero ? HERO : `V${++villainN}`;
      seats[sn] = { player: name, stack: Math.round(s.stack), pos: s.pos ?? '' };
      if (s.bet > 0) bets[sn] = Math.round(s.bet);
      if (s.folded) folded.push(name);
      if (s.hero) heroSeatNum = s.seat;
    }
    const heroCards = parseCards(tableState.hero_cards ?? spot.hero_cards);
    const step = {
      type: 'action', street: tableState.street ?? spot.street ?? 'preflop',
      seats, bets, folded,
      pot: Math.round(tableState.pot), pot_bb: Math.round((tableState.pot / realBb) * 10) / 10,
      bb: realBb, button: tableState.button ?? 1, board: tableState.board ?? [],
      player: HERO, seat: heroSeatNum, is_hero: true,
    } as unknown as ReplayStep;
    return { step, hero: HERO, heroCards, bb: realBb };
  }

  // ── Fallback: aproximação (quando o /table ainda não carregou ou falhou) ──
  const heroStack = Math.round((spot.stack_bb ?? 20) * bb);
  const isPreflop = (spot.street ?? 'preflop') === 'preflop';
  const numP = Math.max(2, Math.min(9, spot.num_players ?? 6));
  const heroPos = (spot.position ?? 'BTN').toUpperCase();

  const layouts: Record<number, string[]> = {
    2: ['BTN', 'BB'],
    3: ['BTN', 'SB', 'BB'],
    4: ['CO',  'BTN', 'SB', 'BB'],
    5: ['UTG', 'CO',  'BTN', 'SB', 'BB'],
    6: ['UTG', 'HJ',  'CO',  'BTN', 'SB', 'BB'],
  };
  const positions = layouts[numP] ?? layouts[6];
  const btnSeat   = positions.indexOf('BTN') + 1;

  let heroSeatIdx = positions.indexOf(heroPos);
  if (heroSeatIdx < 0) heroSeatIdx = positions.indexOf('BTN');
  const heroSeatNum = heroSeatIdx + 1;

  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets:  Record<string, number> = {};

  positions.forEach((pos, i) => {
    const sn    = String(i + 1);
    const isHero = (i + 1) === heroSeatNum;
    seats[sn] = { player: isHero ? HERO : `V${i + 1}`, stack: heroStack, pos };
    // Blinds só fazem sentido como bets no preflop; postflop já estão no pot_size
    if (isPreflop) {
      if (pos === 'SB') bets[sn] = Math.round(bb * 0.5);
      else if (pos === 'BB') bets[sn] = bb;
    }
  });

  // Facing bet → assign to villain seat immediately before hero
  if (spot.facing_bet && spot.facing_bet > 0) {
    const facingChips = Math.round(spot.facing_bet * bb);
    let agSeat = heroSeatNum - 1;
    if (agSeat < 1) agSeat = numP;
    if (agSeat !== heroSeatNum) bets[String(agSeat)] = facingChips;
  }

  const boardLimit = ({ preflop: 0, flop: 3, turn: 4, river: 5 } as Record<string, number>)[spot.street ?? 'preflop'] ?? 0;
  const boardRaw: string[] = (() => {
    if (!spot.board) return [];
    const s = spot.board.trim();
    if (s.startsWith('[')) { try { return JSON.parse(s) as string[]; } catch { return []; } }
    return s.split(/\s+/).filter(Boolean);
  })();
  const board     = boardRaw.slice(0, boardLimit);
  const heroCards = spot.hero_cards
    ? (spot.hero_cards.trim().startsWith('[')
        ? (() => { try { return JSON.parse(spot.hero_cards!) as string[]; } catch { return []; } })()
        : (spot.hero_cards.match(/[2-9TJQKAakqjt][shdcSHDC]/g) ?? []))
    : [];
  const potChips   = Math.round((spot.pot_size ?? 2) * bb);

  const step = {
    type: 'action', street: spot.street ?? 'preflop',
    seats, bets, folded: [] as string[],
    pot_bb: spot.pot_size ?? 2, pot: potChips,
    bb, button: btnSeat, board,
    player: HERO, seat: heroSeatNum, is_hero: true,
  } as unknown as ReplayStep;

  return { step, hero: HERO, heroCards, bb };
}
