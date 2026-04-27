export const RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2'] as const;
export type Rank = typeof RANKS[number];

const RI: Record<string, number> = {};
(RANKS as readonly string[]).forEach((r, i) => { RI[r] = i; });

// Expand "AA-77", "AKs-A2s", "AKo-A2o", or single hand like "AKs"
function ex(notation: string): string[] {
  const d = notation.indexOf('-');
  if (d < 0) return [notation];
  const hi = notation.slice(0, d);
  const lo = notation.slice(d + 1);
  if (hi.length === 2 && hi[0] === hi[1]) {
    // Pair range: AA-77
    return (RANKS as readonly string[]).slice(RI[hi[0]], RI[lo[0]] + 1).map(r => r + r);
  }
  // Suited/offsuit: AKs-A2s, KQo-K9o, etc.
  const suit = hi.slice(-1);
  const top = hi[0];
  const from = RI[hi[1]], to = RI[lo[1]];
  return (RANKS as readonly string[]).slice(from, to + 1).map(k => top + k + suit);
}

function mk(...notations: string[]): Set<string> {
  return new Set(notations.flatMap(ex));
}

// Hand string for a grid cell (row, col)
// row == col → pair; row < col → suited (upper-right); row > col → offsuit (lower-left)
export function cellHand(row: number, col: number): string {
  if (row === col) return RANKS[row] + RANKS[row];
  if (row < col)  return RANKS[row] + RANKS[col] + 's';
  return RANKS[col] + RANKS[row] + 'o';
}

// Display label for a cell (always high card first, no suit suffix)
export function cellLabel(row: number, col: number): string {
  if (row === col) return RANKS[row] + RANKS[row];
  const hi = Math.min(row, col);
  const lo = Math.max(row, col);
  return RANKS[hi] + RANKS[lo];
}

// Convert raw hero card strings like ["Ah", "Kd"] → hand notation like "AKo"
export function heroHand(cards: string[]): string | null {
  if (cards.length < 2) return null;
  const r1 = cards[0].slice(0, -1), s1 = cards[0].slice(-1);
  const r2 = cards[1].slice(0, -1), s2 = cards[1].slice(-1);
  if (RI[r1] === RI[r2]) return r1 + r2;
  const [hi, lo] = RI[r1] < RI[r2] ? [r1, r2] : [r2, r1];
  return hi + lo + (s1 === s2 ? 's' : 'o');
}

export type CellAction = 'r' | 'c' | 'rc' | '';

export interface RangeSet {
  raise: Set<string>;
  call?: Set<string>;
  label: string;
  description?: string;
}

export function getCellAction(hand: string, range: RangeSet): CellAction {
  const inR = range.raise.has(hand);
  const inC = range.call?.has(hand) ?? false;
  if (inR && inC) return 'rc';
  if (inR) return 'r';
  if (inC) return 'c';
  return '';
}

export function rangeStats(range: RangeSet): { combos: number; pct: string } {
  let combos = 0;
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      if (getCellAction(cellHand(r, c), range) !== '') {
        combos += r === c ? 6 : r < c ? 4 : 12;
      }
    }
  }
  return { combos, pct: (combos / 1326 * 100).toFixed(1) };
}

// ── Open Ranges ───────────────────────────────────────────────────────────────

const UTG_OPEN: RangeSet = {
  label: 'Open UTG', description: '~17% das mãos',
  raise: mk(
    'AA-77',
    'AKs-A2s', 'AKo-AQo',
    'KQs-K9s', 'KQo',
    'QJs-QTs', 'QJo',
    'JTs-J9s',
    'T9s-T8s',
    '98s-97s',
    '87s-86s',
    '76s-75s',
    '65s', '54s',
  ),
};

const MP_OPEN: RangeSet = {
  label: 'Open MP', description: '~23% das mãos',
  raise: mk(
    'AA-55',
    'AKs-A2s', 'AKo-AJo',
    'KQs-K8s', 'KQo-KJo',
    'QJs-Q8s', 'QJo',
    'JTs-J8s', 'JTo',
    'T9s-T7s', 'T9o',
    '98s-96s',
    '87s-85s',
    '76s-74s',
    '65s-63s',
    '54s-53s', '43s',
  ),
};

const HJ_OPEN: RangeSet = {
  label: 'Open HJ', description: '~30% das mãos',
  raise: mk(
    'AA-33',
    'AKs-A2s', 'AKo-ATo',
    'KQs-K6s', 'KQo-KTo',
    'QJs-Q5s', 'QJo-QTo',
    'JTs-J7s', 'JTo-J9o',
    'T9s-T6s', 'T9o',
    '98s-95s', '98o',
    '87s-84s',
    '76s-73s',
    '65s-62s',
    '54s-52s',
    '43s-42s', '32s',
  ),
};

const CO_OPEN: RangeSet = {
  label: 'Open CO', description: '~38% das mãos',
  raise: mk(
    'AA-22',
    'AKs-A2s', 'AKo-A8o',
    'KQs-K4s', 'KQo-K9o',
    'QJs-Q3s', 'QJo-Q9o',
    'JTs-J5s', 'JTo-J9o',
    'T9s-T4s', 'T9o-T8o',
    '98s-93s', '98o-97o',
    '87s-82s', '87o',
    '76s-72s', '76o',
    '65s-62s',
    '54s-52s',
    '43s-42s', '32s',
  ),
};

const BTN_OPEN: RangeSet = {
  label: 'Open BTN', description: '~48% das mãos',
  raise: mk(
    'AA-22',
    'AKs-A2s', 'AKo-A3o',
    'KQs-K2s', 'KQo-K7o',
    'QJs-Q2s', 'QJo-Q8o',
    'JTs-J3s', 'JTo-J8o',
    'T9s-T2s', 'T9o-T8o',
    '98s-92s', '98o-97o',
    '87s-82s', '87o',
    '76s-72s', '76o',
    '65s-62s', '65o',
    '54s-52s', '54o',
    '43s-42s', '32s',
  ),
};

const SB_OPEN: RangeSet = {
  label: 'Open SB', description: '~55% das mãos',
  raise: mk(
    'AA-22',
    'AKs-A2s', 'AKo-A2o',
    'KQs-K2s', 'KQo-K5o',
    'QJs-Q2s', 'QJo-Q7o',
    'JTs-J2s', 'JTo-J7o',
    'T9s-T2s', 'T9o-T6o',
    '98s-92s', '98o-96o',
    '87s-82s', '87o-85o',
    '76s-72s', '76o-75o',
    '65s-62s', '65o',
    '54s-52s', '54o',
    '43s-42s', '32s',
  ),
};

// ── 3-Bet Ranges ──────────────────────────────────────────────────────────────

const THREEBET_IP: RangeSet = {
  label: '3-Bet (IP)', description: 'Em posição, vs abertura',
  raise: mk(
    'AA-QQ', 'JJ-TT',
    'AKs', 'AKo', 'AQs',
    'KQs',
    'A5s-A3s',
    'QJs', 'J9s', '87s', '76s',
  ),
};

const THREEBET_OOP: RangeSet = {
  label: '3-Bet (OOP)', description: 'Sem posição, vs abertura',
  raise: mk(
    'AA-QQ', 'JJ-TT',
    'AKs', 'AKo', 'AQs', 'AJs',
    'KQs',
    'A5s-A3s',
  ),
};

// ── Call Ranges ───────────────────────────────────────────────────────────────

const CALL_IP: RangeSet = {
  label: 'Call (IP)', description: 'Cold call em posição',
  raise: mk(),
  call: mk(
    'JJ-22',
    'AJs-A2s', 'AQo-AJo',
    'KQs-K9s', 'KQo-KJo',
    'QJs-Q9s', 'QJo',
    'JTs-J9s', 'JTo',
    'T9s-T8s', 'T9o',
    '98s-97s',
    '87s-86s',
    '76s-75s',
    '65s-64s', '54s',
  ),
};

const BB_DEFEND: RangeSet = {
  label: 'BB Defense', description: 'Defesa do BB vs abertura',
  raise: mk(),
  call: mk(
    'TT-22',
    'AJs-A2s', 'AQo-A2o',
    'KQs-K2s', 'KQo-K2o',
    'QJs-Q2s', 'QJo-Q4o',
    'JTs-J2s', 'JTo-J5o',
    'T9s-T2s', 'T9o-T5o',
    '98s-92s', '98o-95o',
    '87s-82s', '87o-84o',
    '76s-72s', '76o-73o',
    '65s-62s', '65o',
    '54s-52s', '54o',
    '43s-42s', '32s',
  ),
};

// ── Lookup ────────────────────────────────────────────────────────────────────

export type Position = 'UTG' | 'MP' | 'HJ' | 'CO' | 'BTN' | 'SB' | 'BB';
export type RangeType = 'open' | 'call' | '3bet';

export const RANGES: Record<Position, Partial<Record<RangeType, RangeSet>>> = {
  UTG: { open: UTG_OPEN, '3bet': THREEBET_OOP },
  MP:  { open: MP_OPEN,  '3bet': THREEBET_OOP },
  HJ:  { open: HJ_OPEN,  '3bet': THREEBET_IP,  call: CALL_IP },
  CO:  { open: CO_OPEN,  '3bet': THREEBET_IP,  call: CALL_IP },
  BTN: { open: BTN_OPEN, '3bet': THREEBET_IP,  call: CALL_IP },
  SB:  { open: SB_OPEN,  '3bet': THREEBET_OOP },
  BB:  { call: BB_DEFEND, '3bet': THREEBET_OOP },
};

export const POSITIONS: Position[] = ['UTG', 'MP', 'HJ', 'CO', 'BTN', 'SB', 'BB'];

export const RANGE_TYPES: { id: RangeType; label: string }[] = [
  { id: 'open', label: 'Open' },
  { id: 'call', label: 'Call' },
  { id: '3bet', label: '3-Bet' },
];

export function normalizePosition(pos: string): Position | null {
  const p = pos.toUpperCase();
  if (p === 'BTN') return 'BTN';
  if (p === 'CO') return 'CO';
  if (p === 'HJ') return 'HJ';
  if (p === 'MP' || p.startsWith('UTG+') || p.startsWith('MP')) return 'MP';
  if (p === 'UTG') return 'UTG';
  if (p === 'SB') return 'SB';
  if (p === 'BB') return 'BB';
  return null;
}
