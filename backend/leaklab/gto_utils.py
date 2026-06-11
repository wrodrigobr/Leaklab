"""
gto_utils.py — Hashing determinístico de spots + normalização de mãos GTO.

Contrato compartilhado entre o engine e o bot externo que popula gto_nodes.
Mesmo input → mesmo hash em Python e em qualquer linguagem que implemente
json.dumps com sort_keys=True + sha256.
"""
from __future__ import annotations
import hashlib
import json
from typing import Optional

STACK_BUCKETS = [
    (0,   10,  "0-10bb"),
    (10,  20,  "10-20bb"),
    (20,  35,  "20-35bb"),
    (35,  60,  "35-60bb"),
    # Stacks >= 60bb usam '60-100bb' como bucket de referência. As soluções
    # do arquivo de ranges (preflop_gto_ranges) e do solver postflop são
    # calibradas até 100bb — stacks acima usam 100bb como profundidade
    # efetiva (cap implícito). Evita criar bucket '100bb+' sem cobertura
    # e mantém lookup consistente para cash deep + MTT early stages.
    (60,  float("inf"), "60-100bb"),
]

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_IDX = {r: i for i, r in enumerate(RANKS)}

VALID_POSITIONS = {'UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}

_ACTION_NORM: dict[str, str] = {
    'shove': 'jam', 'allin': 'jam', 'all-in': 'jam', 'all_in': 'jam', 'all in': 'jam',
    'open': 'raise', 'openraise': 'raise',
    'x': 'check', 'limp': 'call',
}
VALID_GTO_ACTIONS = {'fold', 'check', 'call', 'bet', 'raise', 'jam'}


def normalize_gto_action(action: str) -> str:
    """Normaliza string de ação GTO para o conjunto canônico {fold,check,call,bet,raise,jam}.

    Cobre também os labels PARAMETRIZADOS do solver (bet_50pct, raise_119pct, raise_2.5x,
    *pct, *x → bet/raise). Sem isso, o strategy_json do solver_cli era rejeitado em
    insert_gto_nodes por 'ações inválidas' → nó não persistia (causa de ~89% dos jobs
    'done' sem nó). O strategy_json ARMAZENADO mantém o size original; só a validação e o
    gto_action canônico usam a forma colapsada."""
    a = (action or '').lower().strip()
    if a in _ACTION_NORM:
        return _ACTION_NORM[a]
    if a in VALID_GTO_ACTIONS:
        return a
    if a.startswith('bet'):
        return 'bet'
    if (a.startswith('raise') or a.startswith('3bet') or a.startswith('4bet')
            or a.startswith('5bet') or a.endswith('pct') or a.endswith('x')):
        return 'raise'
    return a


def stack_bucket(bb: float) -> str:
    """Converte stack em BBs para bucket discreto. Stacks >= 60bb cap em '60-100bb'."""
    for lo, hi, label in STACK_BUCKETS:
        if lo <= bb < hi:
            return label
    return "60-100bb"


BET_BUCKETS = [
    (0,    0,    "no_bet"),
    (0,    3,    "0-3bb"),
    (3,    8,    "3-8bb"),
    (8,    20,   "8-20bb"),
    (20,   40,   "20-40bb"),
    (40,   float("inf"), "40bb+"),
]


def bet_bucket(facing_size_bb: float) -> str:
    """Converte aposta enfrentada em bucket discreto. 0 = spot sem aposta."""
    if facing_size_bb <= 0:
        return "no_bet"
    for lo, hi, label in BET_BUCKETS[1:]:
        if lo < facing_size_bb <= hi:
            return label
    return "40bb+"


def normalize_cards(hand) -> list[str]:
    """Normaliza uma mão para lista de cartas de 2 chars (ex.: ['4d','Ad']).

    Aceita e conserta as 3 formas que apareceram na base:
      - lista correta ['4d','Ad'] → inalterada
      - string '4dAd' (ou 'Ad 4d') → ['4d','Ad']   (evita sorted('4dAd')=['4','A','d','d'])
      - lista char-split ['4','A','d','d'] (corrupção [r1,r2,s1,s2]) → ['4d','Ad']
    Lista vazia / None → []. Robusto contra hero_hand mal-formado na ingestão de nós.
    """
    if not hand:
        return []
    if isinstance(hand, str):
        s = hand.replace(" ", "")
        return [s[i:i+2] for i in range(0, len(s), 2)]
    cards = list(hand)
    if cards and len(cards) % 2 == 0 and all(isinstance(x, str) and len(x) == 1 for x in cards):
        half = len(cards) // 2  # [r1,r2,...,s1,s2,...] → [r1s1, r2s2, ...]
        return [r + s for r, s in zip(cards[:half], cards[half:])]
    return [str(x) for x in cards]


def compute_spot_hash(
    street: str,
    position: str,
    board: list[str],
    hero_hand: list[str],
    hero_stack_bb: float,
    facing_size_bb: float = 0.0,
    pot_type: str = '',
) -> str:
    """
    Retorna hash SHA256[:16] determinístico do spot.
    Normalização: street minúsculo, position maiúsculo, listas ordenadas, hero_hand
    normalizado para cartas de 2 chars (string/char-split são consertados).
    facing_size_bb distingue spots "sem aposta" de "facing bet" e seus tamanhos.

    pot_type distingue a estrutura preflop (ranges diferentes): '' / 'srp' = pote
    single-raised (chave OMITIDA → hash IDÊNTICO ao legado, backward-compat); '3bet'/
    '4bet' = pote re-raised (chave incluída → hash distinto, não colide com os nós SRP).
    """
    canonical = {
        "street":       street.lower(),
        "position":     position.upper(),
        "board":        sorted(board),
        "hand":         sorted(normalize_cards(hero_hand)),
        "stack_bucket": stack_bucket(hero_stack_bb),
        "bet_bucket":   bet_bucket(facing_size_bb),
    }
    _pt = (pot_type or '').lower().strip()
    if _pt in ('3bet', '4bet'):          # SRP/limped/'' → omite (hash legado preservado)
        canonical["pot_type"] = _pt
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode()
    ).hexdigest()[:16]


# ── Hand normalization ─────────────────────────────────────────────────────────

def hand_to_type(cards: list[str]) -> Optional[str]:
    """
    Converte uma mão específica (ex: ['Ac', 'Kd']) para hand_type (ex: 'AKo').

    Retorna:
      'AA'  — par
      'AKs' — suited
      'AKo' — offsuit
      None  — entrada inválida
    """
    if not cards or len(cards) < 2:
        return None
    c1, c2 = cards[0], cards[1]
    if len(c1) < 2 or len(c2) < 2:
        return None

    r1, s1 = c1[0].upper(), c1[1].lower()
    r2, s2 = c2[0].upper(), c2[1].lower()

    # Garante ordem decrescente por rank
    if RANK_IDX.get(r1, -1) < RANK_IDX.get(r2, -1):
        r1, r2 = r2, r1
        s1, s2 = s2, s1

    if r1 == r2:
        return f"{r1}{r2}"       # par: "AA"
    if s1 == s2:
        return f"{r1}{r2}s"     # suited: "AKs"
    return f"{r1}{r2}o"         # offsuit: "AKo"


def expand_range_notation(notation: str) -> list[str]:
    """
    Expande notação de range poker para lista de hand_types.

    Suporta:
      'AA'       → ['AA']
      'TT+'      → ['TT','JJ','QQ','KK','AA']
      'ATs+'     → ['ATs','AJs','AQs','AKs']
      'ATo+'     → ['ATo','AJo','AQo','AKo']
      'ATs-AJs'  → ['ATs','AJs']
      'KTs+'     → ['KTs','KJs','KQs']
    """
    notation = notation.strip()
    hands: list[str] = []

    if '-' in notation and notation[-1] != '+':
        # range: ATs-AJs
        lo_str, hi_str = notation.split('-', 1)
        lo_r, lo_k, lo_s = _parse_hand_str(lo_str)
        hi_r, hi_k, hi_s = _parse_hand_str(hi_str)
        if lo_r is None or hi_r is None:
            return []
        start = min(RANK_IDX.get(lo_k, 0), RANK_IDX.get(hi_k, 0))
        end   = max(RANK_IDX.get(lo_k, 0), RANK_IDX.get(hi_k, 0))
        for i in range(start, end + 1):
            hands.append(f"{lo_r}{RANKS[i]}{lo_s}")
        return hands

    if notation.endswith('+'):
        base = notation[:-1]
        r1, r2, suit = _parse_hand_str(base)
        if r1 is None:
            return []
        if r1 == r2:
            # par+: TT+ → TT,JJ,QQ,KK,AA
            start = RANK_IDX.get(r1, 0)
            for i in range(start, len(RANKS)):
                hands.append(f"{RANKS[i]}{RANKS[i]}")
        else:
            # connector+: ATs+ → ATs,AJs,AQs,AKs
            start = RANK_IDX.get(r2, 0)
            end   = RANK_IDX.get(r1, 0) - 1
            for i in range(start, end + 1):
                hands.append(f"{r1}{RANKS[i]}{suit}")
        return hands

    # single hand
    r1, r2, suit = _parse_hand_str(notation)
    if r1 is None:
        return []
    return [notation]


def _parse_hand_str(s: str):
    """Retorna (high_rank, low_rank_or_same, suit_suffix) ou (None,None,None)."""
    s = s.strip()
    if len(s) == 2:
        # par: 'AA'
        return s[0].upper(), s[1].upper(), ''
    if len(s) == 3:
        r1, r2, c = s[0].upper(), s[1].upper(), s[2].lower()
        if c in ('s', 'o'):
            return r1, r2, c
    return None, None, None


# ── Fase 1 (plano solver): identidade da ÁRVORE (tree_hash) + isomorfismo ──────

_ISO_SUITS = 'cdhs'


def canonical_board_key(board) -> str:
    """Forma canônica do board sob permutação de naipes (isomorfismo de suits).

    `As Kd 2c` e `Ah Kc 2d` são o MESMO jogo estrategicamente — esta função devolve
    a mesma chave para ambos. Flop é tratado como conjunto (ordenado); turn e river
    preservam posição (são streets distintas). Implementação: aplica as 24
    permutações de naipes e retorna a menor string lexicográfica — canônica por
    construção, sem casos especiais.
    """
    from itertools import permutations
    cards = [str(c).strip() for c in (board or []) if c and len(str(c).strip()) >= 2]
    flop, rest = cards[:3], cards[3:]
    best = None
    for perm in permutations(_ISO_SUITS):
        mp = dict(zip(_ISO_SUITS, perm))
        mapped_flop = sorted(c[0].upper() + mp.get(c[1].lower(), c[1].lower()) for c in flop)
        key = ','.join(mapped_flop)
        if rest:
            key += '|' + '|'.join(c[0].upper() + mp.get(c[1].lower(), c[1].lower()) for c in rest)
        if best is None or key < best:
            best = key
    return best or ''


def compute_tree_hash(payload: dict) -> str:
    """Hash SHA256[:16] da ÁRVORE de jogo — identidade do SOLVE, não do spot.

    Diferente do spot_hash, NÃO inclui a mão do hero (ela não é input do solver —
    dois spots na mesma árvore com mãos diferentes eram re-solvados à toa) e usa o
    board CANÔNICO por isomorfismo de naipes. Os campos são exatamente o que muda
    o resultado do solve + a navegação até o nó do hero: street, board canônico,
    ranges, pot, stack efetivo, facing e hero_is_ip. max_iterations e target ficam
    de fora (afetam convergência/qualidade, não a identidade do jogo).
    `payload` = o dict enviado ao solver_cli (solver_payload do lookup_gto).
    """
    canonical = {
        'street':     (payload.get('street') or '').lower().strip(),
        'board':      canonical_board_key(payload.get('board') or []),
        'oop_range':  (payload.get('oop_range') or '').strip(),
        'ip_range':   (payload.get('ip_range') or '').strip(),
        'pot_bb':     round(float(payload.get('pot_bb') or 0.0), 2),
        'stack_bb':   round(float(payload.get('effective_stack_bb') or 0.0), 2),
        'facing_bb':  round(float(payload.get('facing_size_bb') or 0.0), 2),
        'hero_is_ip': bool(payload.get('hero_is_ip')),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode()
    ).hexdigest()[:16]


def iso_suit_map(board_from, board_to):
    """Fase 3 (plano solver): permutação de naipes que transforma `board_from` em
    `board_to` (boards isomorfos). Retorna dict {naipe_from: naipe_to} ou None se
    não são isomorfos. Flop comparado como conjunto; turn/river posicionais —
    mesma semântica do canonical_board_key."""
    from itertools import permutations

    def _norm(board):
        cards = [str(c).strip() for c in (board or []) if c and len(str(c).strip()) >= 2]
        return [c[0].upper() + c[1].lower() for c in cards]

    a, b = _norm(board_from), _norm(board_to)
    if len(a) != len(b):
        return None
    bf, br = a[:3], a[3:]
    tf, tr = b[:3], b[3:]
    for perm in permutations(_ISO_SUITS):
        mp = dict(zip(_ISO_SUITS, perm))
        if sorted(c[0] + mp[c[1]] for c in bf) == sorted(tf) and \
           [c[0] + mp[c[1]] for c in br] == tr:
            return mp
    return None


def map_cards_suits(cards, suit_map):
    """Aplica a permutação de naipes (de iso_suit_map) a uma lista de cartas."""
    out = []
    for c in cards or []:
        c = str(c).strip()
        if len(c) >= 2:
            out.append(c[0].upper() + suit_map.get(c[1].lower(), c[1].lower()))
    return out
