"""
preflop_gto_ranges.py — Análise GTO de preflop a partir do JSON validado.

Cobre três cenários:
  RFI     — Raise First In: primeira a abrir em determinada posição
  vs_RFI  — defendendo contra abertura de outro jogador
  vs_3bet — respondendo a um re-raise após sua abertura
"""
from __future__ import annotations
import json, logging, os
from typing import Optional

log = logging.getLogger(__name__)

_RANGES_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'leaklab_gto_ranges.json')
_data: Optional[dict] = None


def _load() -> dict:
    global _data
    if _data is None:
        with open(_RANGES_FILE, 'r', encoding='utf-8') as f:
            _data = json.load(f)
    return _data


def _stack_bucket(stack_bb: float) -> str:
    data = _load()
    for label, bounds in data.get('stack_buckets', {}).items():
        if bounds['min'] <= stack_bb <= bounds['max']:
            return label
    return '100bb'


def _expand_range(notation: str) -> set[str]:
    """Expande notação de range separada por vírgula em conjunto de hand_types."""
    if not notation or 'N/A' in notation.upper():
        return set()
    from leaklab.gto_utils import expand_range_notation
    hands: set[str] = set()
    for part in notation.split(','):
        part = part.strip()
        if not part:
            continue
        for h in expand_range_notation(part):
            if len(h) == 2:
                hands.add(h)                         # par: 'AA', 'KK'
            elif len(h) >= 3 and h[-1] not in ('s', 'o'):
                hands.add(h + 's')                   # sem sufixo → ambos
                hands.add(h + 'o')
            else:
                hands.add(h)
    return hands


def _in_range(hand_type: str, notation: str) -> bool:
    if not hand_type or not notation:
        return False
    return hand_type in _expand_range(notation)


_ACT = {'ALLIN': 'jam', 'RFI': 'raise', 'THREBET': 'raise', 'CALL': 'call', 'FOLD': 'fold'}
_POS = {
    'BTN': 'Button', 'CO': 'Cutoff', 'HJ': 'HiJack', 'LJ': 'LoJack',
    'UTG': 'UTG', 'UTG1': 'UTG+1', 'SB': 'Small Blind', 'BB': 'Big Blind',
}

# Pipeline e banco usam nomes distintos do JSON — normalizamos antes do lookup
_POS_NORM = {
    'UTG+1': 'UTG1',   # 2º a agir pós-BB (8-max)
    'UTG+2': 'LJ',     # 3º a agir = LoJack
    'LJ':    'LJ',
    'MP':    'LJ',     # Middle Position genérico → LoJack
    'MP1':   'LJ',
    'MP2':   'HJ',
    'HJ':    'HJ',
}


def _norm_pos(position: str) -> str:
    """Normaliza nome de posição do pipeline/banco para chave do JSON."""
    p = position.upper()
    return _POS_NORM.get(p, p)


def analyze_preflop(
    position: str,
    hero_hand_type: str,      # ex: 'AKo', 'AKs', 'AA'
    stack_bb: float,
    action_taken: str,        # 'fold', 'call', 'raise', 'jam'
    facing_size: float = 0.0,
    vs_position: str = '',    # posição de quem abriu
    is_3bet_pot: bool = False,
) -> dict:
    """
    Retorna análise GTO completa de uma decisão preflop.

    Keys retornadas:
      available, scenario, hand_type, stack_bucket, stack_bb,
      position, vs_position, in_range, range_pct, range_hands,
      recommended_actions, action_quality, pro_notes,
      rfi_pct (RFI), hands_4bet/hands_call (vs_3bet)
    """
    data    = _load()
    bucket  = _stack_bucket(stack_bb)
    bk_data = data.get('ranges', {}).get(bucket, {})
    pos     = _norm_pos(position)
    vs_pos  = _norm_pos(vs_position) if vs_position else ''

    base = {
        'available': False, 'scenario': 'rfi',
        'hand_type': hero_hand_type, 'stack_bucket': bucket,
        'stack_bb': round(stack_bb, 1), 'position': pos,
        'vs_position': vs_pos or None,
        'in_range': False, 'range_pct': 0.0, 'range_hands': '',
        'recommended_actions': [], 'action_quality': 'unknown',
        'action_taken': action_taken, 'pro_notes': [],
    }

    if is_3bet_pot and vs_pos:
        scenario = 'vs_3bet'
    elif facing_size > 0:
        # vs_pos pode ser '' quando opener não foi detectado — lookup retornará None → available=False
        scenario = 'vs_rfi'
    else:
        scenario = 'rfi'
    base['scenario'] = scenario

    # BB checando em pot não contestado = free play, não é decisão de range
    if scenario == 'rfi' and pos == 'BB' and action_taken.lower() == 'check':
        return base  # available=False — sem análise

    # ── RFI ──────────────────────────────────────────────────────────────────
    if scenario == 'rfi':
        rfi = bk_data.get('RFI', {}).get(pos)
        if not rfi:
            return base
        pct       = float(rfi.get('pct', 0))
        hands_str = rfi.get('hands', '')
        acoes     = rfi.get('acoes', [])
        in_rng    = _in_range(hero_hand_type, hands_str)
        rec       = [_ACT.get(a, a.lower()) for a in acoes] if in_rng else ['fold']
        quality   = _rfi_quality(action_taken, in_rng, stack_bb)
        base.update({
            'available': True, 'in_range': in_rng,
            'range_pct': pct, 'range_hands': hands_str,
            'recommended_actions': rec, 'rfi_pct': pct,
            'action_quality': quality,
            'pro_notes': _rfi_notes(pos, hero_hand_type, stack_bb, pct, in_rng, action_taken),
        })

    # ── vs RFI ───────────────────────────────────────────────────────────────
    elif scenario == 'vs_rfi':
        vs_rfi     = bk_data.get('vs_RFI', {})
        opener_key = _find_opener_key(vs_rfi, vs_pos)
        defender   = vs_rfi.get(opener_key, {}).get(pos) if opener_key else None
        if not defender:
            return base
        pct_play  = float(defender.get('pct_play', 0))
        hands_str = defender.get('hands', '')
        acoes     = defender.get('acoes', [])
        in_rng    = _in_range(hero_hand_type, hands_str)
        rec       = [_ACT.get(a, a.lower()) for a in acoes] if in_rng else ['fold']
        quality   = _vs_rfi_quality(action_taken, in_rng, acoes)
        base.update({
            'available': True, 'in_range': in_rng,
            'range_pct': pct_play, 'range_hands': hands_str,
            'recommended_actions': rec, 'action_quality': quality,
            'pro_notes': _vs_rfi_notes(pos, vs_pos, hero_hand_type, stack_bb,
                                        pct_play, in_rng, action_taken, acoes),
        })

    # ── vs 3bet ───────────────────────────────────────────────────────────────
    elif scenario == 'vs_3bet':
        vs3  = bk_data.get('vs_3bet', {})
        spot = vs3.get(f'{pos}_RFI_vs_3bet') or next(
            (v for k, v in vs3.items() if k.endswith('_RFI_vs_3bet')), None
        )
        if not spot:
            return base
        pct        = float(spot.get('pct_continua', 0))
        hands_4bet = spot.get('hands_4bet', '')
        hands_call = spot.get('hands_call', '')
        in_4b      = _in_range(hero_hand_type, hands_4bet)
        in_cl      = _in_range(hero_hand_type, hands_call)
        in_rng     = in_4b or in_cl
        rec        = ['raise', 'jam'] if in_4b else (['call'] if in_cl else ['fold'])
        quality    = _vs_3bet_quality(action_taken, in_4b, in_cl)
        base.update({
            'available': True, 'in_range': in_rng,
            'range_pct': pct,
            'range_hands': f"4bet: {hands_4bet} | call: {hands_call}",
            'recommended_actions': rec, 'action_quality': quality,
            'hands_4bet': hands_4bet, 'hands_call': hands_call,
            'pro_notes': _vs_3bet_notes(pos, hero_hand_type, stack_bb,
                                         pct, in_4b, in_cl, action_taken),
        })

    return base


# ── Quality classifiers ──────────────────────────────────────────────────────

def _rfi_quality(action: str, in_rng: bool, stack_bb: float) -> str:
    act = action.lower()
    if in_rng and act in ('raise', 'jam'):    return 'correct'
    if in_rng and act == 'call':              return 'acceptable'
    if in_rng and act == 'fold':              return 'leak'
    if not in_rng and act == 'fold':          return 'correct'
    if not in_rng and act in ('raise', 'jam'):
        return 'major_leak' if stack_bb > 25 else 'leak'
    if not in_rng and act == 'call':          return 'leak'
    return 'acceptable'


def _vs_rfi_quality(action: str, in_rng: bool, acoes: list) -> str:
    act  = action.lower()
    acts = {_ACT.get(a, a.lower()) for a in acoes}
    if in_rng and act in acts:                  return 'correct'
    if in_rng and act == 'fold':                return 'leak'
    if in_rng and act not in acts:              return 'leak'   # desvio dentro do range
    if not in_rng and act == 'fold':            return 'correct'
    if not in_rng and act in ('raise', 'jam'):  return 'major_leak'
    if not in_rng and act == 'call':            return 'leak'
    return 'acceptable'


def _vs_3bet_quality(action: str, in_4b: bool, in_cl: bool) -> str:
    act = action.lower()
    if in_4b and act in ('raise', 'jam'):  return 'correct'
    if in_cl and act == 'call':            return 'correct'
    if (in_4b or in_cl) and act == 'fold': return 'leak'
    if not (in_4b or in_cl) and act == 'fold': return 'correct'
    return 'major_leak'


# ── Professional notes ────────────────────────────────────────────────────────

def _rfi_notes(pos, hand, stack, pct, in_rng, action) -> list[str]:
    notes = []
    label = _POS.get(pos, pos)
    pct_s = f"{pct*100:.0f}%"
    act   = action.lower()
    if in_rng:
        notes.append(f"{label} abre {pct_s} das mãos a {stack:.0f}bb — {hand} está no range de abertura.")
        if act == 'fold':
            notes.append(f"Foldar {hand} do {label} é um leak evidente: a mão tem equity e posição para abrir.")
        elif act == 'call':
            notes.append("Limp desperdiça vantagem posicional. Raise/jam é a linha mais lucrativa aqui.")
        else:
            notes.append(f"Raise correto. {hand} é uma abertura sólida do {label} neste stack.")
    else:
        notes.append(f"{hand} está fora do range GTO do {label} a {stack:.0f}bb (range: top {pct_s}).")
        if act in ('raise', 'jam'):
            if stack <= 20:
                notes.append(f"Com {stack:.0f}bb o jogo é push/fold — {hand} não tem equity suficiente para shove aqui.")
            else:
                notes.append(f"Abrir {hand} do {label} é loose: perde EV contra os ranges de defesa dos oponentes.")
        elif act == 'fold':
            notes.append(f"Fold correto. {hand} não justifica entrada desta posição neste stack.")
        # check/call em limped pot — sem julgamento negativo
    if stack <= 15:
        notes.append(f"Com {stack:.0f}bb: jogo essencialmente push/fold — use tabelas ICM para decisões marginais.")
    elif stack <= 25:
        notes.append(f"Com {stack:.0f}bb a jogabilidade pós-flop é limitada — equity de mão e posição são prioridade.")
    return notes


def _vs_rfi_notes(pos, vs_pos, hand, stack, pct, in_rng, action, acoes) -> list[str]:
    notes  = []
    label  = _POS.get(pos, pos)
    vs_lbl = _POS.get(vs_pos, vs_pos)
    pct_s  = f"{pct*100:.0f}%"
    acts_s = '/'.join(a.title() for a in acoes if a != 'FOLD')
    act    = action.lower()
    if in_rng:
        notes.append(f"{label} continua com {pct_s} das mãos vs open do {vs_lbl} — {hand} está no range de {acts_s}.")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs {vs_lbl} open é excessivamente tight e perde EV no longo prazo.")
    else:
        notes.append(f"{hand} está fora do range de defesa do {label} vs {vs_lbl} open a {stack:.0f}bb.")
        if act == 'fold':
            notes.append(f"Fold correto. {hand} não tem equity suficiente para continuar vs o range de abertura do {vs_lbl}.")
        elif act in ('raise', 'jam'):
            notes.append(f"3bet com {hand} aqui não é sustentado pelo GTO — range de 3bet do {label} vs {vs_lbl} é mais apertado.")
    return notes


def _vs_3bet_notes(pos, hand, stack, pct, in_4b, in_cl, action) -> list[str]:
    notes = []
    label = _POS.get(pos, pos)
    pct_s = f"{pct*100:.0f}%"
    act   = action.lower()
    if in_4b:
        notes.append(f"{hand} do {label} faz 4bet vs 3bet — mão no topo do range de continuação ({pct_s} continuam).")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs 3bet é grande erro de EV: esta mão está no range de 4bet.")
    elif in_cl:
        notes.append(f"{hand} do {label} faz call vs 3bet — range de continuação é {pct_s} das mãos.")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs 3bet é tight demais — a mão tem equity para continuar.")
    else:
        notes.append(f"{hand} do {label} deve foldar vs 3bet — fora do range de continuação ({pct_s} continuam).")
        if act in ('raise', 'jam', 'call'):
            notes.append(f"Continuar com {hand} vs 3bet perde EV: a mão não tem equity vs o range de 3bet do oponente.")
    return notes


def _find_opener_key(vs_rfi: dict, opener_pos: str) -> Optional[str]:
    if not opener_pos:
        return None
    key = f"{opener_pos}_open"
    return key if key in vs_rfi else None
