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

// Frequency por ação (estilo solver — soma 1.0 entre raise+call+allin; resto é fold)
export interface HandFreq {
  raise?: number;   // 3-bet sized (verde escuro)
  call?:  number;   // call (azul)
  allin?: number;   // jam (vermelho/laranja)
  fold?:  number;   // implicito = 1 - sum(outros)
}

export interface RangeSet {
  raise: Set<string>;
  call?:  Set<string>;
  allin?: Set<string>;
  label:  string;
  // Frequências por mão pra renderização GW-style (multi-cor proporcional).
  // Quando ausente, fallback usa sets (raise/call/allin) com 100% cada.
  frequencies?: Record<string, HandFreq>;
}

export function getCellAction(hand: string, range: RangeSet): CellAction {
  const inR = range.raise.has(hand) || (range.allin?.has(hand) ?? false);
  const inC = range.call?.has(hand) ?? false;
  if (inR && inC) return 'rc';
  if (inR) return 'r';
  if (inC) return 'c';
  return '';
}

// Frequências da mão pra renderização multi-cor. Fallback: deduz do RangeSet
// quando `frequencies` ausente (cada ação 100% se mão presente no respectivo set).
export function getHandFreq(hand: string, range: RangeSet): HandFreq {
  if (range.frequencies?.[hand]) return range.frequencies[hand];
  const inR = range.raise.has(hand);
  const inC = range.call?.has(hand) ?? false;
  const inA = range.allin?.has(hand) ?? false;
  if (!inR && !inC && !inA) return { fold: 1 };
  // Sem frequencies → split uniforme entre sets presentes
  const n = (inR ? 1 : 0) + (inC ? 1 : 0) + (inA ? 1 : 0);
  return {
    raise: inR ? 1 / n : 0,
    call:  inC ? 1 / n : 0,
    allin: inA ? 1 / n : 0,
  };
}

/**
 * Ações REALMENTE presentes na range — varre as 169 células pela MESMA fonte que
 * pinta a grade (`getHandFreq`). A legenda DEVE derivar daqui.
 *
 * Por quê: a legenda antes olhava os Sets (`range.allin.size`) enquanto as células
 * pintavam por `frequencies` — fontes diferentes. Na aba OPEN o RangeSet vem sem o
 * Set `allin` (só `raise` + `frequencies`), então em stack curto (push/fold) a grade
 * ficava toda VERMELHA (allin) sem nenhuma entrada "Shove" na legenda. Mesmo princípio
 * do invariante do backend: o que é exibido tem que cobrir o que existe de fato.
 */
export function rangeActionPresence(
  range: RangeSet,
  minFreq = 0.001,
): { raise: boolean; call: boolean; allin: boolean; fold: boolean } {
  const out = { raise: false, call: false, allin: false, fold: false };
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      const f = getHandFreq(cellHand(r, c), range);
      if ((f.raise ?? 0) > minFreq) out.raise = true;
      if ((f.call  ?? 0) > minFreq) out.call  = true;
      if ((f.allin ?? 0) > minFreq) out.allin = true;
      const active = (f.raise ?? 0) + (f.call ?? 0) + (f.allin ?? 0);
      if (1 - active > minFreq) out.fold = true;
      if (out.raise && out.call && out.allin && out.fold) return out;   // early-out
    }
  }
  return out;
}

/** Combinações de uma LISTA de mãos em notação ("AKs", "77", "QJo").
 *
 *  Par = 6, suited = 4, offsuit = 12 — a mesma regra que `rangeStats` aplica varrendo a grade.
 *  Existe separada porque o treino de fronteira trabalha com uma lista de mãos, não com um
 *  `RangeSet`, e converter só para contar seria caro e indireto.
 *
 *  O percentual é sobre as 1326 combinações do baralho, e NÃO sobre a família: é o que liga este
 *  exercício à noção de largura de range ("UTG abre ~20%"). Percentual da família diria "marquei
 *  metade dos Áses suited", que não se conecta a nada que o jogador use na mesa. */
export function combosDeMaos(hands: string[]): { combos: number; pct: string } {
  let combos = 0;
  for (const h of hands) {
    if (h.length === 2 && h[0] === h[1]) combos += 6;
    else if (h.endsWith('s')) combos += 4;
    else if (h.endsWith('o')) combos += 12;
  }
  return { combos, pct: (combos / 1326 * 100).toFixed(1) };
}

/**
 * Quantos combos a range JOGA, contado pela MESMA fonte que pinta a célula.
 *
 * ── O defeito que originou (28/08) ────────────────────────────────────────────────────────
 *
 * Contava por `getCellAction`, que lê os Sets, enquanto as células e o `resumoDoSpot` leem
 * `getHandFreq`. Duas contas para o mesmo fato, e as duas na MESMA linha do JSX: o rodapé da
 * grade dizia `62,6% · 830 combos` e o resumo ao lado somava 1.158 não-fold (87,3%). Vinte e
 * cinco pontos de diferença.
 *
 * Medido sobre a carta: **9 de 112 spots de RFI divergiam, todos no SB** — é a range de LIMP.
 * `buildRangeFromApi` monta `raise: new Set(resp.rfi.hands)` e o endpoint nunca lê `call_hands`
 * do registro de RFI, então as mãos de limp existem em `frequencies` (e são pintadas de azul) e
 * não existem em Set nenhum (e sumiam da conta).
 *
 * É o mesmo conserto que `rangeActionPresence` recebeu para a LEGENDA, com o comentário
 * explicando por quê — o contador ao lado ficou lendo os Sets.
 */
export function rangeStats(range: RangeSet): { combos: number; pct: string } {
  let combos = 0;
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      const f = getHandFreq(cellHand(r, c), range);
      const ativo = (f.raise ?? 0) + (f.call ?? 0) + (f.allin ?? 0);
      if (ativo > 0.001) combos += r === c ? 6 : r < c ? 4 : 12;
    }
  }
  return { combos, pct: (combos / 1326 * 100).toFixed(1) };
}

// ── Resumo do spot: a mistura vira CATEGORIA com nome, não gradiente para adivinhar ──────────
//
// Nasceu do benchmark de 27/08. O visor do concorrente não deixa a estratégia mista como uma cor
// intermediária que o olho tem que decifrar: ele nomeia cada combinação de ações e diz quantos
// combos tem dentro ("Raise ou Call: 62 combos · 4,7%"). É a diferença entre um mapa de calor e
// um vocabulário, e não custa dado novo — sai de contar o que a grade já pinta.
//
// O peso do combo é o mesmo de `rangeStats` (par = 6, suited = 4, offsuit = 12) e a leitura da
// frequência passa por `getHandFreq`, que é a MESMA fonte que pinta a célula. Contar por outro
// caminho seria a segunda fonte para o mesmo fato — o defeito que este projeto passa a semana
// consertando.

/** Uma categoria do resumo: as ações que a mão toma, com quantos combos caem nela. */
export interface CategoriaDoSpot {
  chave:  string;        // 'raise' | 'raise+fold' | 'call+raise' ...
  acoes:  AcaoDaCelula[];   // para o chip usar o MESMO gradiente da célula
  combos: number;
  pct:    string;
}

export type AcaoDaCelula = 'raise' | 'call' | 'allin' | 'fold';

// Termos de poker ficam em inglês — regra do projeto, e por isso vivem aqui. O CONECTOR
// ("ou") não vive: ele é idioma, e camada de dados não sabe idioma. Quem junta é a tela, com
// `t()`. A 1ª versão juntava aqui e o guarda de i18n pegou na hora.
export const ROTULO_ACAO: Record<AcaoDaCelula, string> = {
  raise: 'Raise',
  call:  'Call',
  allin: 'All-in',
  fold:  'Fold',
};

// Ordem de leitura: agressão primeiro, fold por último. Vale para ordenar as categorias E para
// nomear a mistura sempre na mesma sequência ("Raise ou Fold", nunca "Fold ou Raise").
const ORDEM: AcaoDaCelula[] = ['allin', 'raise', 'call', 'fold'];

// Mesmo limiar de `buildGradient`: abaixo disto a ação não é pintada, então não pode ser contada.
const MINIMO = 0.001;

/**
 * Agrupa as 169 células por COMBINAÇÃO de ações e devolve as categorias com combos e %.
 *
 * Devolve só categorias não vazias, na ordem de leitura (agressão → fold). A soma dos combos é
 * sempre 1.326 — se não for, alguma célula ficou de fora e o resumo estaria mentindo.
 */
export function resumoDoSpot(range: RangeSet): CategoriaDoSpot[] {
  const acc = new Map<string, { acoes: AcaoDaCelula[]; combos: number }>();

  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      const hand = cellHand(r, c);
      const f    = getHandFreq(hand, range);
      const ativo = (f.raise ?? 0) + (f.call ?? 0) + (f.allin ?? 0);

      const acoes: AcaoDaCelula[] = [];
      if ((f.allin ?? 0) > MINIMO) acoes.push('allin');
      if ((f.raise ?? 0) > MINIMO) acoes.push('raise');
      if ((f.call  ?? 0) > MINIMO) acoes.push('call');
      // Fold é o RESTO, exatamente como a célula é pintada. Ler `f.fold` daria outro número
      // quando a soma não fecha 1.0, e a tela mostraria uma coisa e o resumo outra.
      if (1 - ativo > MINIMO) acoes.push('fold');
      if (!acoes.length) acoes.push('fold');

      const chave = acoes.join('+');
      const peso  = r === c ? 6 : r < c ? 4 : 12;
      const atual = acc.get(chave);
      if (atual) atual.combos += peso;
      else acc.set(chave, { acoes, combos: peso });
    }
  }

  return [...acc.entries()]
    .map(([chave, v]) => ({
      chave,
      acoes:  v.acoes,
      combos: v.combos,
      pct:    ((v.combos / 1326) * 100).toFixed(1),
    }))
    .sort((a, b) => {
      // categoria pura antes de mista; dentro do mesmo tamanho, pela ação mais agressiva
      const pa = a.acoes.length - b.acoes.length;
      if (pa !== 0) return pa;
      return ORDEM.indexOf(a.acoes[0]) - ORDEM.indexOf(b.acoes[0]);
    });
}

// ── Open Ranges ───────────────────────────────────────────────────────────────

const UTG_OPEN: RangeSet = {
  label: 'Open UTG',
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
  label: 'Open MP',
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
  label: 'Open HJ',
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
  label: 'Open CO',
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
  label: 'Open BTN',
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
  label: 'Open SB',
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
  label: '3-Bet (IP)',
  raise: mk(
    'AA-QQ', 'JJ-TT',
    'AKs', 'AKo', 'AQs',
    'KQs',
    'A5s-A3s',
    'QJs', 'J9s', '87s', '76s',
  ),
};

const THREEBET_OOP: RangeSet = {
  label: '3-Bet (OOP)',
  raise: mk(
    'AA-QQ', 'JJ-TT',
    'AKs', 'AKo', 'AQs', 'AJs',
    'KQs',
    'A5s-A3s',
  ),
};

// ── Call Ranges ───────────────────────────────────────────────────────────────

const CALL_IP: RangeSet = {
  label: 'Call (IP)',
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
  label: 'BB Defense',
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

export type Position = 'UTG' | 'UTG+1' | 'UTG+2' | 'LJ' | 'MP' | 'HJ' | 'CO' | 'BTN' | 'SB' | 'BB';
export type RangeType = 'open' | 'call' | '3bet' | 'shove';

export const RANGES: Record<Position, Partial<Record<RangeType, RangeSet>>> = {
  UTG: { open: UTG_OPEN, '3bet': THREEBET_OOP },
  'UTG+1': { '3bet': THREEBET_OOP },  // open/call served by API (GW 9-max tem chave própria)
  'UTG+2': { '3bet': THREEBET_OOP },  // open/call served by API (GW 9-max tem chave própria)
  LJ:  { '3bet': THREEBET_OOP },  // open/call served by API
  MP:  { open: MP_OPEN,  '3bet': THREEBET_OOP },
  HJ:  { open: HJ_OPEN,  '3bet': THREEBET_IP,  call: CALL_IP },
  CO:  { open: CO_OPEN,  '3bet': THREEBET_IP,  call: CALL_IP },
  BTN: { open: BTN_OPEN, '3bet': THREEBET_IP,  call: CALL_IP },
  SB:  { open: SB_OPEN,  '3bet': THREEBET_OOP },
  BB:  { call: BB_DEFEND, '3bet': THREEBET_OOP },
};

// Ordem canônica de TODAS as posições nomeáveis (dialeto do replay = GW 9-max, + MP legado).
export const POSITIONS: Position[] = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'MP', 'HJ', 'CO', 'BTN', 'SB', 'BB'];

// Abas sempre visíveis do painel de ranges. UTG+1/UTG+2 entram só quando são a posição da
// mão/veredito: dez abas fixas não cabem na régua, e nas mesas curtas essas posições nem existem.
export const CORE_TAB_POSITIONS: Position[] = ['UTG', 'LJ', 'MP', 'HJ', 'CO', 'BTN', 'SB', 'BB'];

export const RANGE_TYPES: { id: RangeType; label: string }[] = [
  { id: 'shove', label: 'Shove' },
  { id: 'open',  label: 'Open'  },
  { id: 'call',  label: 'Call'  },
  { id: '3bet',  label: '3-Bet' },
];

// ── Nash Push/Fold Ranges (6-max, approximate) ───────────────────────────────
// BB entry uses `call` field (call vs shove). All other positions use `raise` (shove range).

export type StackBucket = '≤8bb' | '≤10bb' | '≤15bb' | '≤20bb';

export function getPushFoldBucket(stackBb: number): StackBucket | null {
  if (stackBb <= 8)  return '≤8bb';
  if (stackBb <= 10) return '≤10bb';
  if (stackBb <= 15) return '≤15bb';
  if (stackBb <= 20) return '≤20bb';
  return null;
}

export const PUSH_FOLD: Record<StackBucket, Partial<Record<Position, RangeSet>>> = {
  '≤8bb': {
    UTG: { label: 'Shove UTG (≤8bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A5o','KQs-K5s','KQo-K9o','QJs-Q7s','QJo-Q9o','JTs-J7s','JTo','T9s-T6s','T9o','98s-96s','87s-86s','76s','65s','54s') },
    MP:  { label: 'Shove MP (≤8bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A4o','KQs-K4s','KQo-K8o','QJs-Q5s','QJo-Q8o','JTs-J5s','JTo-J9o','T9s-T4s','T9o-T8o','98s-95s','98o','87s-83s','87o','76s-73s','65s-63s','54s-53s','43s') },
    HJ:  { label: 'Shove HJ (≤8bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A3o','KQs-K3s','KQo-K7o','QJs-Q3s','QJo-Q7o','JTs-J3s','JTo-J8o','T9s-T2s','T9o-T7o','98s-92s','98o-96o','87s-82s','87o-85o','76s-72s','76o-74o','65s-62s','65o','54s-52s','43s-42s','32s') },
    CO:  { label: 'Shove CO (≤8bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K5o','QJs-Q2s','QJo-Q5o','JTs-J2s','JTo-J6o','T9s-T2s','T9o-T4o','98s-92s','98o-93o','87s-82s','87o-83o','76s-72s','76o-72o','65s-62s','65o-63o','54s-52s','54o','43s-42s','32s') },
    BTN: { label: 'Shove BTN (≤8bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K2o','QJs-Q2s','QJo-Q3o','JTs-J2s','JTo-J4o','T9s-T2s','T9o-T2o','98s-92s','98o-92o','87s-82s','87o-82o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o-52o','43s-42s','32s') },
    SB:  { label: 'Shove SB (≤8bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K2o','QJs-Q2s','QJo-Q2o','JTs-J2s','JTo-J2o','T9s-T2s','T9o-T2o','98s-92s','98o-92o','87s-82s','87o-82o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o-52o','43s-42s','32s') },
    BB:  { label: 'Call vs Shove BB (≤8bb)',
      raise: mk(), call: mk('AA-22','AKs-A3s','AKo-A6o','KQs-K7s','KQo-KTo','QJs-Q7s','QJo-Q9o','JTs-J7s','JTo','T9s-T7s','T9o','98s-97s','87s-86s','76s') },
  },
  '≤10bb': {
    UTG: { label: 'Shove UTG (≤10bb)',
      raise: mk('AA-33','AKs-A5s','AKo-A8o','KQs-K7s','KQo-KJo','QJs-Q8s','QJo','JTs-J7s','JTo','T9s-T6s','T9o','98s-95s','87s-85s','76s-74s','65s-63s','54s') },
    MP:  { label: 'Shove MP (≤10bb)',
      raise: mk('AA-22','AKs-A3s','AKo-A6o','KQs-K5s','KQo-K9o','QJs-Q6s','QJo-Q9o','JTs-J5s','JTo','T9s-T4s','T9o-T8o','98s-93s','98o','87s-82s','87o','76s-72s','65s-62s','54s-52s','43s') },
    HJ:  { label: 'Shove HJ (≤10bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A4o','KQs-K4s','KQo-K7o','QJs-Q4s','QJo-Q7o','JTs-J3s','JTo-J8o','T9s-T2s','T9o-T6o','98s-92s','98o-95o','87s-82s','87o-84o','76s-72s','76o-73o','65s-62s','65o','54s-52s','43s-42s','32s') },
    CO:  { label: 'Shove CO (≤10bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K5o','QJs-Q2s','QJo-Q4o','JTs-J2s','JTo-J6o','T9s-T2s','T9o-T3o','98s-92s','98o-93o','87s-82s','87o-82o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o','43s-42s','32s') },
    BTN: { label: 'Shove BTN (≤10bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K2o','QJs-Q2s','QJo-Q2o','JTs-J2s','JTo-J5o','T9s-T2s','T9o-T2o','98s-92s','98o-92o','87s-82s','87o-82o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o-52o','43s-42s','32s') },
    SB:  { label: 'Shove SB (≤10bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K2o','QJs-Q2s','QJo-Q2o','JTs-J2s','JTo-J2o','T9s-T2s','T9o-T2o','98s-92s','98o-92o','87s-82s','87o-82o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o-52o','43s-42s','32s') },
    BB:  { label: 'Call vs Shove BB (≤10bb)',
      raise: mk(), call: mk('AA-55','AKs-A7s','AKo-A9o','KQs-K8s','KQo-KJo','QJs-Q8s','QJo','JTs-J8s','T9s-T7s','98s-97s','87s') },
  },
  '≤15bb': {
    UTG: { label: 'Shove UTG (≤15bb)',
      raise: mk('AA-55','AKs-A9s','AKo-ATo','KQs-K9s','KQo','QJs-QTs','JTs-J9s','T9s','98s-97s') },
    MP:  { label: 'Shove MP (≤15bb)',
      raise: mk('AA-44','AKs-A7s','AKo-A9o','KQs-K7s','KQo-KJo','QJs-Q8s','QJo','JTs-J7s','JTo','T9s-T7s','T9o','98s-96s','87s-86s','76s','65s') },
    LJ:  { label: 'Shove LJ (≤15bb)',
      raise: mk('AA-33','AKs-A4s','AKo-A7o','KQs-K5s','KQo-K9o','QJs-Q7s','QJo-Q9o','JTs-J5s','JTo-J9o','T9s-T5s','T9o','98s-95s','98o','87s-83s','87o','76s-73s','65s-63s','54s-52s','43s') },
    HJ:  { label: 'Shove HJ (≤15bb)',
      raise: mk('AA-33','AKs-A5s','AKo-A7o','KQs-K5s','KQo-K9o','QJs-Q7s','QJo-Q9o','JTs-J5s','JTo-J9o','T9s-T5s','T9o','98s-95s','98o','87s-83s','87o','76s-73s','65s-63s','54s-53s') },
    CO:  { label: 'Shove CO (≤15bb)',
      raise: mk('AA-22','AKs-A3s','AKo-A5o','KQs-K3s','KQo-K8o','QJs-Q3s','QJo-Q7o','JTs-J3s','JTo-J8o','T9s-T2s','T9o-T7o','98s-92s','98o-95o','87s-82s','87o-84o','76s-72s','76o-73o','65s-62s','65o','54s-52s','43s-42s','32s') },
    BTN: { label: 'Shove BTN (≤15bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K5o','QJs-Q2s','QJo-Q5o','JTs-J2s','JTo-J6o','T9s-T2s','T9o-T4o','98s-92s','98o-93o','87s-82s','87o-83o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o-52o','43s-42s','32s') },
    SB:  { label: 'Shove SB (≤15bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A2o','KQs-K2s','KQo-K3o','QJs-Q2s','QJo-Q2o','JTs-J2s','JTo-J3o','T9s-T2s','T9o-T2o','98s-92s','98o-92o','87s-82s','87o-82o','76s-72s','76o-72o','65s-62s','65o-62o','54s-52s','54o-52o','43s-42s','32s') },
    BB:  { label: 'Call vs Shove BB (≤15bb)',
      raise: mk(), call: mk('AA-66','AKs-A7s','AKo-A9o','KQs-K8s','KQo-KJo','QJs-Q8s','QJo','JTs-J8s','T9s-T7s','98s-97s','87s') },
  },
  '≤20bb': {
    UTG: { label: 'Shove UTG (≤20bb)',
      raise: mk('AA-77','AKs-A4s','AKo-AJo','KQs-K9s','KQo-KJo','QJs-QTs','JTs','T9s') },
    MP:  { label: 'Shove MP (≤20bb)',
      raise: mk('AA-55','AKs-A9s','AKo-ATo','KQs-K9s','KQo','QJs-QTs','JTs-J9s','T9s','98s') },
    LJ:  { label: 'Shove LJ (≤20bb)',
      raise: mk('AA-44','AKs-A6s','AKo-A8o','KQs-K7s','KQo-KTo','QJs-Q8s','QJo-Q9o','JTs-J7s','JTo','T9s-T7s','T9o','98s-96s','87s-85s','76s-74s','65s') },
    HJ:  { label: 'Shove HJ (≤20bb)',
      raise: mk('AA-44','AKs-A7s','AKo-A9o','KQs-K8s','KQo-KJo','QJs-Q9s','QJo','JTs-J8s','T9s-T8s','98s-97s','87s') },
    CO:  { label: 'Shove CO (≤20bb)',
      raise: mk('AA-33','AKs-A5s','AKo-A7o','KQs-K6s','KQo-KTo','QJs-Q7s','QJo-Q9o','JTs-J6s','JTo','T9s-T6s','T9o','98s-96s','87s-85s','76s-74s','65s-63s','54s') },
    BTN: { label: 'Shove BTN (≤20bb)',
      raise: mk('AA-22','AKs-A3s','AKo-A5o','KQs-K5s','KQo-K8o','QJs-Q5s','QJo-Q8o','JTs-J5s','JTo-J9o','T9s-T4s','T9o-T8o','98s-93s','98o','87s-82s','87o','76s-72s','76o','65s-62s','54s-52s','43s-42s') },
    SB:  { label: 'Shove SB (≤20bb)',
      raise: mk('AA-22','AKs-A2s','AKo-A3o','KQs-K3s','KQo-K7o','QJs-Q3s','QJo-Q6o','JTs-J2s','JTo-J8o','T9s-T2s','T9o-T6o','98s-92s','98o-95o','87s-82s','87o-84o','76s-72s','76o-73o','65s-62s','65o','54s-52s','43s-42s','32s') },
    BB:  { label: 'Call vs Shove BB (≤20bb)',
      raise: mk(), call: mk('AA-77','AKs-A9s','AKo-ATo','KQs-KTs','KQo','QJs-QTs','JTs','T9s') },
  },
};

/** UTG+1/UTG+2 passam VERBATIM: são chaves próprias do GW 9-max e o backend
 *  (`_norm_pos`) as aceita como estão. Achatar aqui (UTG+2→LJ, UTG+1→UTG) era uma
 *  segunda cópia da regra de normalização discordando da primeira — caso real
 *  (19/08): veredito calculado em UTG+2 20bb dizia "K6s fora do range, Fold 100%"
 *  e a grade na mesma tela renderizava LJ 20bb, onde K6s é raise. */
export function normalizePosition(pos: string): Position | null {
  const p = pos.toUpperCase();
  if (p === 'BTN') return 'BTN';
  if (p === 'CO') return 'CO';
  if (p === 'HJ') return 'HJ';
  if (p === 'LJ') return 'LJ';
  if (p === 'MP' || p === 'MP1' || p.startsWith('MP')) return 'MP';
  if (p === 'UTG+2' || p === 'UTG2') return 'UTG+2';
  if (p === 'UTG+1' || p === 'UTG1') return 'UTG+1';
  if (p === 'UTG') return 'UTG';
  if (p === 'SB') return 'SB';
  if (p === 'BB') return 'BB';
  return null;
}
