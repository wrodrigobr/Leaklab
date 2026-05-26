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


# Hardcoded buckets — JSON v3 (GW master) não tem stack_buckets section.
# Mantém compat com v2 que tinha campo no JSON.
_DEFAULT_BUCKETS = [
    ('10bb',  0,    12),
    ('14bb',  12,   15.5),
    ('17bb',  15.5, 18.5),
    ('20bb',  18.5, 25),
    ('30bb',  25,   35),
    ('40bb',  35,   45),
    ('50bb',  45,   62.5),
    ('75bb',  62.5, 87.5),
    ('100bb', 87.5, 9999),
]

def _stack_bucket(stack_bb: float) -> str:
    data = _load()
    # Prioriza campo do JSON se existir (v2 antigo)
    for label, bounds in data.get('stack_buckets', {}).items():
        if bounds.get('min', 0) <= stack_bb <= bounds.get('max', 0):
            return label
    # Fallback hardcoded (v3 não tem stack_buckets no JSON)
    for label, lo, hi in _DEFAULT_BUCKETS:
        if lo <= stack_bb < hi:
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

# Pipeline (hand_state_builder._position_names) e JSON v3 (GW MTTGeneralV2 9-max)
# usam nomenclaturas diferentes. Mapeamento depende do TAMANHO DA MESA (n_players).
#
# Pipeline naming por n_players (de hand_state_builder._position_names):
#   n=6: SB, BB, UTG, HJ, CO, BTN
#   n=7: SB, BB, UTG, UTG+1, HJ, CO, BTN
#   n=8: SB, BB, UTG, UTG+1, UTG+2, HJ, CO, BTN
#   n=9: SB, BB, UTG, UTG+1, UTG+2, MP1, HJ, CO, BTN
#  n=10: SB, BB, UTG, UTG+1, UTG+2, MP1, MP2, HJ, CO, BTN
#
# GW MTTGeneralV2 (sempre 9-max): SB, BB, UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN
#
# Mapping por ordem de ação (pipeline_pos → GW pos):
# Mesa de N seats, hero na ordem K (0=SB, 1=BB, 2=UTG, ...):
#   - K ∈ {0, 1}: blinds direto (SB/BB)
#   - K = 2: UTG
#   - K = N-1: BTN
#   - K = N-2: CO
#   - K = N-3: HJ
#   - K ∈ [3, N-4]: ordem early/middle → mapear pro slot equivalente em GW 9-max
#
# Em GW 9-max (N=9): ordem early = {3:UTG+1, 4:UTG+2, 5:LJ}
# Pra mesa menor (8/7/6), comprimimos: pipeline 'UTG+2' em 8-max = LJ em GW (3ª ação).

# Mapping estático default — assume GW 9-max nativo.
# Usado quando n_players desconhecido (fallback).
_POS_NORM = {
    'UTG':   'UTG',
    'UTG+1': 'UTG+1',
    'UTG+2': 'UTG+2',
    'LJ':    'LJ',
    'HJ':    'HJ',
    'CO':    'CO',
    'BTN':   'BTN',
    'SB':    'SB',
    'BB':    'BB',
    'UTG1':  'UTG+1',   # legacy v2
    'UTG2':  'UTG+2',   # legacy v2
    'MP1':   'LJ',      # 9-max pipeline: 4ª ação = LJ no GW
    'MP2':   'HJ',      # 10-max pipeline: 5ª ação (raro)
    'MP':    'LJ',      # genérico
}

# Mapping específico por n_players (preciso): pipeline N-max → GW 9-max
_POS_NORM_BY_N = {
    # Mesa 8-max — pipeline 'UTG+2' (5ª seat) é a 3ª ação preflop = LJ no GW
    8: {
        **_POS_NORM,
        'UTG+2': 'LJ',  # 3ª ação em 8-max = LJ
    },
    # Mesa 7-max — pipeline 'UTG+1' é a 2ª ação preflop. Em GW 9-max, 2ª ação = UTG+1.
    # MAS quem é early/mid em 7-max joga ranges mais wide que UTG+1 9-max.
    # Aceito imprecisão: 'UTG+1' 7-max → UTG+1 9-max (ranges aproximados).
    7: {
        **_POS_NORM,
        # UTG+1 (4º seat) é 2ª ação preflop em 7-max = UTG+1 9-max (mesma ordem)
        # HJ (5º seat) é 3ª ação preflop = LJ 9-max
        'HJ': 'LJ',
    },
    # Mesa 6-max — só 4 posições não-blind. UTG=1ª ação, HJ=2ª, CO=3ª, BTN=4ª.
    # GW 9-max 2ª ação = UTG+1. Mapear:
    6: {
        **_POS_NORM,
        # HJ (4º seat) 6-max é 2ª ação = UTG+1 no GW
        # CO permanece CO (próximo do BTN, similar)
        'HJ': 'UTG+1',
    },
}

# Push/fold bucket → lista de pf_stack keys (em ordem de preferência)
_PUSHFOLD_BUCKET_STACK = {
    '10bb': ['12bb', '10bb'],   # 12bb é o máximo do bucket; fallback 10bb
    '14bb': ['15bb'],
    '20bb': ['20bb_pf'],        # só como último fallback para 20bb
}


def _norm_pos(position: str, n_players: int | None = None) -> str:
    """Normaliza nome de posição do pipeline/banco para chave do JSON v3 (9-max GW).

    Quando n_players conhecido, usa mapping específico (mais accurate).
    Sem n_players, usa default (assume 9-max).
    """
    p = position.upper()
    if n_players in _POS_NORM_BY_N:
        return _POS_NORM_BY_N[n_players].get(p, p)
    return _POS_NORM.get(p, p)


def analyze_preflop(
    position: str,
    hero_hand_type: str,      # ex: 'AKo', 'AKs', 'AA'
    stack_bb: float,
    action_taken: str,        # 'fold', 'call', 'raise', 'jam'
    facing_size: float = 0.0,
    vs_position: str = '',    # posição de quem abriu (opener)
    is_3bet_pot: bool = False,
    caller_position: str = '', # posição do cold caller (se houver, ativa squeeze lookup)
    n_players: int | None = None,  # tamanho da mesa — usado pra mapping correto pipeline→GW
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
    pos     = _norm_pos(position, n_players)
    vs_pos  = _norm_pos(vs_position, n_players) if vs_position else ''
    cal_pos = _norm_pos(caller_position, n_players) if caller_position else ''

    base = {
        'available': False, 'scenario': 'rfi',
        'hand_type': hero_hand_type, 'stack_bucket': bucket,
        'stack_bb': round(stack_bb, 1), 'position': pos,
        'vs_position': vs_pos or None,
        'in_range': False, 'range_pct': 0.0, 'range_hands': '',
        'recommended_actions': [], 'action_quality': 'unknown',
        'action_taken': action_taken, 'pro_notes': [],
    }

    # Squeeze: hero é squeezador (raise sobre open + cold caller). Distingue de vs_3bet HU.
    if is_3bet_pot and vs_pos and cal_pos:
        scenario = 'squeeze'
    elif is_3bet_pot and vs_pos:
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
            # Push/fold fallback para stacks curtos (10bb, 14bb; 20bb como último recurso)
            pf_section = bk_data.get('push_fold', {}).get(pos)
            if pf_section:
                pf_entry = None
                for pf_key in _PUSHFOLD_BUCKET_STACK.get(bucket, []):
                    pf_entry = pf_section.get(pf_key)
                    if pf_entry:
                        break
                if pf_entry:
                    shove_hands = pf_entry.get('shove_hands', '')
                    shove_pct   = float(pf_entry.get('shove_pct', 0))
                    in_shove    = _in_range(hero_hand_type, shove_hands)
                    rec         = ['jam'] if in_shove else ['fold']
                    quality     = _pushfold_quality(action_taken, in_shove)
                    base.update({
                        'available': True, 'in_range': in_shove,
                        'range_pct': shove_pct, 'range_hands': shove_hands,
                        'range_grid_pct': shove_pct,
                        'recommended_actions': rec, 'action_quality': quality,
                        'source': pf_entry.get('_source', 'pushfold_gto'),
                        'pro_notes': _pushfold_notes(pos, hero_hand_type, stack_bb,
                                                     shove_pct, in_shove, action_taken),
                    })
                    return base
            return base
        # Detecta formato v3 (GW master) vs v2 (RegLife antigo)
        is_v3 = 'open_pct' in rfi or 'raise_hands' in rfi

        if is_v3:
            # v3: campos open_pct/raise_pct/allin_pct + raise_hands/allin_hands
            pct         = float(rfi.get('open_pct', 0))
            grid_pct    = pct
            raise_hs    = rfi.get('raise_hands', '')
            allin_hs    = rfi.get('allin_hands', '')
            # range total não-fold = raise + allin (em stacks rasos quase tudo é allin)
            all_hands_parts = [h for h in [raise_hs, allin_hs] if h]
            hands_str   = ','.join(all_hands_parts)
            acoes       = []  # v3 deriva ação por hand_in (in_raise vs in_allin)
            limp_str    = ''   # v3 não tem limp (RegLife antigo tinha SB limp)
            limp_pct    = 0.0
            in_raise    = bool(raise_hs) and _in_range(hero_hand_type, raise_hs)
            in_allin    = bool(allin_hs) and _in_range(hero_hand_type, allin_hs)
            in_rng      = in_raise or in_allin
            in_limp     = False

            # Ordem por freq da MÃO específica quando disponível (hand_freqs do GW v3)
            # Inclui FOLD quando freq fold >= 20% (mão mista que GTO frequentemente folda)
            _hf_rfi = rfi.get('hand_freqs', {}).get(hero_hand_type, {})
            _hf_raise_w = 0.0; _hf_allin_w = 0.0; _hf_fold_w = 0.0
            for code, f in _hf_rfi.items():
                if code == 'RAI':                _hf_allin_w += float(f)
                elif code == 'F':                _hf_fold_w  += float(f)
                elif code.startswith('R'):       _hf_raise_w += float(f)
            _opts = []
            if in_allin:
                _opts.append(('jam',   _hf_allin_w if _hf_allin_w > 0 else float(rfi.get('allin_pct', 0) or 0)))
            if in_raise:
                _opts.append(('raise', _hf_raise_w if _hf_raise_w > 0 else float(rfi.get('raise_pct', 0) or 0)))
            # Fold como opção GTO quando freq significativa (mão mista entre fold/raise)
            if _hf_fold_w >= 0.20:
                _opts.append(('fold', _hf_fold_w))
            _opts.sort(key=lambda x: -x[1])
            rec = [a for a, _ in _opts] or ['fold']
        else:
            # v2 (RegLife antigo): pct + hands + acoes
            pct         = float(rfi.get('combo_pct') or rfi.get('pct', 0))
            grid_pct    = float(rfi.get('grid_pct') or rfi.get('pct', 0))
            hands_str   = rfi.get('hands', '')
            acoes       = rfi.get('acoes', [])
            limp_str    = rfi.get('limp_hands', '')   # SB limp range (quando presente)
            limp_pct    = float(rfi.get('limp_combo_pct') or rfi.get('limp_pct', 0))
            in_rng      = _in_range(hero_hand_type, hands_str)
            in_limp     = bool(limp_str) and _in_range(hero_hand_type, limp_str)

            # Recomendação: raise se no raise range, call/limp se no limp range, fold caso contrário
            if in_rng:
                rec = [_ACT.get(a, a.lower()) for a in acoes]
            elif in_limp:
                rec = ['call']   # limp from SB
            else:
                rec = ['fold']

        # hand_freq exato pra RFI (v3 GW) — usado pelo quality classifier por freq
        hand_freq = None
        if is_v3:
            hand_freq_raw = rfi.get('hand_freqs', {}).get(hero_hand_type, {})
            if hand_freq_raw:
                hand_freq = {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 0.0}
                for code, f in hand_freq_raw.items():
                    if code == 'F':       hand_freq['fold']  += float(f)
                    elif code == 'C':     hand_freq['call']  += float(f)
                    elif code == 'RAI':   hand_freq['allin'] += float(f)
                    elif code.startswith('R'):  hand_freq['raise'] += float(f)
                hand_freq = {k: round(v, 4) for k, v in hand_freq.items()}

        quality = _rfi_quality(action_taken, in_rng, stack_bb,
                               in_limp=in_limp, is_sb=(pos == 'SB'),
                               hand_freq=hand_freq)
        base.update({
            'available': True, 'in_range': in_rng or in_limp,
            'range_pct': pct, 'range_hands': hands_str,
            'hand_freq': hand_freq,  # freq exata da mão hero (para barra Decision Card)
            'range_grid_pct': grid_pct,
            'recommended_actions': rec, 'rfi_pct': pct,
            'action_quality': quality,
            'in_limp_range': in_limp,
            'limp_pct': limp_pct,
            'pro_notes': _rfi_notes(pos, hero_hand_type, stack_bb, pct, in_rng, action_taken,
                                     in_limp=in_limp, hand_freq=hand_freq),
        })

    # ── vs RFI ───────────────────────────────────────────────────────────────
    elif scenario == 'vs_rfi':
        vs_rfi = bk_data.get('vs_RFI', {})
        # JSON v3 (GW master) usa 9-max nativo. vs_pos e pos já foram normalizados
        # pelo _POS_NORM (UTG+1, UTG+2, etc).
        # Tentar lookup direto; fallback p/ aliases legacy ("{opener}_open", "MP")
        opener_data = vs_rfi.get(vs_pos)
        if not isinstance(opener_data, dict):
            # Fallback v2 antigo: usava "MP" no lugar de "UTG+1"
            for alt in (f"{vs_pos}_open", 'MP' if vs_pos == 'UTG+1' else None):
                if alt and isinstance(vs_rfi.get(alt), dict):
                    opener_data = vs_rfi.get(alt)
                    break
        defender = opener_data.get(pos) if isinstance(opener_data, dict) else None
        if defender is None and isinstance(opener_data, dict):
            # Fallback: tentar 'MP' se pos for UTG+1 (legacy)
            if pos == 'UTG+1':
                defender = opener_data.get('MP')
        if not defender or not isinstance(defender, dict):
            # Push/fold reshove fallback para stacks curtos sem dados RegLife vs_RFI
            pf_section = bk_data.get('push_fold', {}).get(pos)
            if pf_section:
                pf_entry = None
                for pf_key in _PUSHFOLD_BUCKET_STACK.get(bucket, []):
                    pf_entry = pf_section.get(pf_key)
                    if pf_entry:
                        break
                if pf_entry:
                    shove_hands = pf_entry.get('shove_hands', '')
                    shove_pct   = float(pf_entry.get('shove_pct', 0))
                    in_shove    = _in_range(hero_hand_type, shove_hands)
                    # vs raise: reshove com o range de shove; fold o restante
                    rec     = ['jam'] if in_shove else ['fold']
                    quality = _pushfold_quality(action_taken, in_shove)
                    base.update({
                        'available': True, 'in_range': in_shove,
                        'range_pct': shove_pct, 'range_hands': shove_hands,
                        'recommended_actions': rec, 'action_quality': quality,
                        'source': pf_entry.get('_source', 'pushfold_gto') + '_reshove',
                        'pro_notes': _pushfold_notes(pos, hero_hand_type, stack_bb,
                                                     shove_pct, in_shove, action_taken,
                                                     is_reshove=True),
                    })
                    return base
            return base

        if 'fold_pct' in defender:
            # Formato novo (RegLife v2 e v3 GW master): fold/call/raise/allin separados
            call_pct    = float(defender.get('call_pct', 0))
            raise_pct   = float(defender.get('raise_pct', 0))
            allin_pct   = float(defender.get('allin_pct', 0))
            fold_hands  = defender.get('fold_hands', '')
            call_hands  = defender.get('call_hands', '')
            raise_hands = defender.get('raise_hands', '')
            allin_hands = defender.get('allin_hands', '')

            in_call  = bool(call_hands)  and _in_range(hero_hand_type, call_hands)
            in_raise = bool(raise_hands) and _in_range(hero_hand_type, raise_hands)
            in_allin = bool(allin_hands) and _in_range(hero_hand_type, allin_hands)
            in_rng   = in_call or in_raise or in_allin

            # Recomendação preserva TODAS as ações válidas (mãos mistas). ORDEM por
            # freq da MÃO específica (hand_freqs do GW v3) quando disponível.
            # Inclui FOLD quando hand_freq.fold ≥ 20% (mão mista que GTO frequentemente folda).
            _hf_vs = defender.get('hand_freqs', {}).get(hero_hand_type, {})
            _hf_call_w = 0.0; _hf_raise_w = 0.0; _hf_allin_w = 0.0; _hf_fold_w = 0.0
            for code, f in _hf_vs.items():
                if code == 'C':                  _hf_call_w  += float(f)
                elif code == 'RAI':              _hf_allin_w += float(f)
                elif code == 'F':                _hf_fold_w  += float(f)
                elif code.startswith('R'):       _hf_raise_w += float(f)
            has_hf_vs = (_hf_call_w + _hf_raise_w + _hf_allin_w) > 0
            _options = []
            if in_allin:
                _options.append(('jam',   _hf_allin_w if has_hf_vs else float(defender.get('allin_pct', 0) or 0)))
            if in_raise:
                _options.append(('raise', _hf_raise_w if has_hf_vs else float(defender.get('raise_pct', 0) or 0)))
            if in_call:
                _options.append(('call',  _hf_call_w  if has_hf_vs else float(defender.get('call_pct',  0) or 0)))
            if _hf_fold_w >= 0.20:
                _options.append(('fold', _hf_fold_w))
            _agg_order = {'jam': 4, 'raise': 3, 'call': 2, 'fold': 1}
            _options.sort(key=lambda x: (-x[1], -_agg_order[x[0]]))
            rec = [a for a, _ in _options] or ['fold']

            # aggr_pct: campo v2 (RegLife) ou computado em v3 (call+raise+allin = não-fold)
            aggr_pct = float(defender.get('aggr_pct', call_pct + raise_pct + allin_pct))

            # hand_freq: frequência EXATA da mão do hero (vem do JSON v3 hand_freqs).
            # Permite mostrar 28/72 pra 88 em vez de 13/5 (% global do range).
            # Códigos brutos do GW (C, R5, R6, RAI, F) — normalizar pra call/raise/allin/fold.
            hand_freq_raw = defender.get('hand_freqs', {}).get(hero_hand_type, {})
            hand_freq = {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 0.0}
            for code, f in hand_freq_raw.items():
                if code == 'F':       hand_freq['fold']  += float(f)
                elif code == 'C':     hand_freq['call']  += float(f)
                elif code == 'RAI':   hand_freq['allin'] += float(f)
                elif code.startswith('R'):  hand_freq['raise'] += float(f)
            hand_freq = {k: round(v, 4) for k, v in hand_freq.items()}
            has_hf = sum(hand_freq.values()) > 0.001

            # Quality classifier usa hand_freq (freq EXATA) quando disponível —
            # mais preciso que verificar in/out range. Fallback pro modo rec/in_rng.
            quality = _vs_rfi_quality_new(action_taken, in_rng, rec, hand_freq if has_hf else None)

            base.update({
                'available': True, 'in_range': in_rng,
                'range_pct':    aggr_pct,
                'range_hands':  allin_hands or raise_hands or call_hands,
                'recommended_actions': rec, 'action_quality': quality,
                'fold_pct':   float(defender.get('fold_pct', 0)),
                'call_pct':   call_pct,
                'raise_pct':  raise_pct,
                'allin_pct':  allin_pct,
                'hand_freq':  hand_freq,  # freq EXATA da mão hero (use no Decision Card)
                'fold_hands': fold_hands, 'call_hands': call_hands,
                'raise_hands': raise_hands, 'allin_hands': allin_hands,
                'pro_notes':  _vs_rfi_notes_new(pos, vs_pos, hero_hand_type, stack_bb,
                                                 aggr_pct, in_rng, rec, action_taken),
            })
        else:
            # Old format: pct_play / hands / acoes
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

    # ── Squeeze (hero é squeezador em pot 3-way com open + cold call) ────────
    elif scenario == 'squeeze':
        key = f"{pos}_squeeze_vs_{vs_pos}_open_{cal_pos}_call"
        # Lookup: tenta bucket exato primeiro, depois fallback para buckets adjacentes
        # (vs_squeeze cobre 40/50/75/100bb; 30bb cai pra 40bb, 20bb pra 40bb).
        candidate_buckets = [bucket]
        # Fallback inferior (mais conservador) — squeeze cobre 40/50/75/100bb
        bucket_fallbacks = {
            '20bb': ['40bb'], '30bb': ['40bb'],  # sobem (único caminho)
            '40bb': ['50bb'],                     # 40 → 50 (não há inferior em squeeze)
            '50bb': ['40bb'],                     # 50 → 40 (inferior)
            '75bb': ['50bb'],                     # 75 → 50 (inferior)
            '100bb': ['75bb'],                    # 100 → 75 (inferior)
        }
        candidate_buckets += bucket_fallbacks.get(bucket, [])
        spot = None
        used_bucket = bucket
        for bk_try in candidate_buckets:
            vs_sq_try = data.get('ranges', {}).get(bk_try, {}).get('vs_squeeze', {})
            if key in vs_sq_try:
                spot = vs_sq_try[key]
                used_bucket = bk_try
                break
        if not spot:
            return base  # available=False — sem cobertura para essa combinação
        pct_sq     = float(spot.get('pct_squeeze', 0))
        pct_call   = float(spot.get('pct_call', 0))
        hands_4bet = spot.get('hands_4bet', '')
        hands_call = spot.get('hands_call', '')
        in_4b      = _in_range(hero_hand_type, hands_4bet)
        in_cl      = _in_range(hero_hand_type, hands_call)
        in_rng     = in_4b or in_cl
        rec        = ['raise', 'jam'] if in_4b else (['call'] if in_cl else ['fold'])
        quality    = _vs_3bet_quality(action_taken, in_4b, in_cl)  # mesma lógica de 3bet aplicável
        base.update({
            'available': True, 'in_range': in_rng,
            'range_pct': pct_sq,
            'range_hands': f"squeeze: {hands_4bet} | call: {hands_call}",
            'recommended_actions': rec, 'action_quality': quality,
            'hands_4bet': hands_4bet, 'hands_call': hands_call,
            'pro_notes': [
                f"Spot multiway: {vs_pos} abriu, {cal_pos} pagou. Hero {pos} decide "
                f"squeeze/call/fold. Squeeze frequência GTO: {pct_sq:.1%}, call: {pct_call:.1%}."
            ],
        })

    # ── vs 3bet ───────────────────────────────────────────────────────────────
    elif scenario == 'vs_3bet':
        # Formato GW v3: ranges[stack][vs_3bet][hero_pos][vs_pos] = spot
        # Estrutura do spot: raise_hands (4bet), call_hands, allin_hands, hand_freqs.
        bucket_fallbacks = {
            '14bb': ['10bb', '20bb'], '17bb': ['20bb', '14bb'],
            '40bb': ['30bb', '50bb'], '60bb': ['50bb', '75bb'],
            '75bb': ['100bb', '50bb'],
        }
        candidate_buckets = [bucket] + bucket_fallbacks.get(bucket, [])
        spot = None
        actual_vs = vs_pos
        for bk_try in candidate_buckets:
            vs3_try = data.get('ranges', {}).get(bk_try, {}).get('vs_3bet', {})
            hero_dict = vs3_try.get(pos, {})
            if not hero_dict:
                continue
            # Tenta vs_pos exato, depois qualquer 3bettor disponível
            spot = hero_dict.get(vs_pos)
            if not spot and hero_dict:
                actual_vs = next(iter(hero_dict.keys()))
                spot = hero_dict[actual_vs]
            if spot:
                break
        if not spot:
            return base
        hands_4bet  = spot.get('raise_hands', '')
        hands_call  = spot.get('call_hands', '')
        hands_allin = spot.get('allin_hands', '')
        hand_freqs  = spot.get('hand_freqs') or {}
        in_4b   = _in_range(hero_hand_type, hands_4bet)
        in_cl   = _in_range(hero_hand_type, hands_call)
        in_jam  = _in_range(hero_hand_type, hands_allin)
        in_rng  = in_4b or in_cl or in_jam
        # Ordem recomendada pela freq da mão específica (quando disponível)
        hf = hand_freqs.get(hero_hand_type, {}) if hand_freqs else {}
        actions_freq = [
            ('raise', float(hf.get('raise', 0)) or (1.0 if in_4b else 0)),
            ('call',  float(hf.get('call',  0)) or (1.0 if in_cl else 0)),
            ('jam',   float(hf.get('allin', 0)) or (1.0 if in_jam else 0)),
            ('fold',  float(hf.get('fold',  0))),
        ]
        rec = [a for a, f in sorted(actions_freq, key=lambda x: -x[1]) if f >= 0.10]
        if not rec:
            rec = ['fold']
        quality = _vs_3bet_quality(action_taken, in_4b, in_cl, in_jam=in_jam, hand_freq=hf)
        pct_continua = (float(spot.get('raise_pct', 0))
                        + float(spot.get('call_pct', 0))
                        + float(spot.get('allin_pct', 0)))
        base.update({
            'available': True, 'in_range': in_rng,
            'range_pct': pct_continua / 100.0 if pct_continua > 1 else pct_continua,
            'range_hands': f"4bet: {hands_4bet} | call: {hands_call} | jam: {hands_allin}",
            'recommended_actions': rec, 'action_quality': quality,
            'hands_4bet': hands_4bet, 'hands_call': hands_call, 'hands_allin': hands_allin,
            'hand_freq': {
                'fold':  float(hf.get('fold', 0)),
                'call':  float(hf.get('call', 0)),
                'raise': float(hf.get('raise', 0)),
                'allin': float(hf.get('allin', 0)),
            } if hf else None,
            'vs_position': actual_vs,
            'pro_notes':   _vs_3bet_notes(pos, hero_hand_type, stack_bb,
                                          pct_continua, in_4b, in_cl, action_taken),
        })

    return base


# ── Quality classifiers ──────────────────────────────────────────────────────

def _rfi_quality(action: str, in_rng: bool, stack_bb: float, *,
                 in_limp: bool = False, is_sb: bool = False,
                 hand_freq: dict | None = None) -> str:
    """Quality classifier RFI.

    Quando hand_freq disponível (freq EXATA da mão pelo GTO Wizard), classifica
    pela frequência GTO da ação tomada:
      >= 30% → correct (ação dominante)
      10–30% → acceptable (ação válida do mix, minoritária)
      3–10%  → leak (raramente GTO — ex: QQ shove 4% quando raise é 96%)
      < 3%   → major_leak (fora do GTO)
    """
    act = action.lower()
    # Normalizar 'shove'/'allin'/'all-in' → 'jam' (forma canônica)
    if act in ('shove', 'allin', 'all-in'): act = 'jam'

    # 1. Usa hand_freq quando disponível (preciso por mão)
    if hand_freq:
        key_map = {
            'fold': 'fold', 'call': 'call', 'check': 'call',
            'raise': 'raise', 'bet': 'raise',
            'jam': 'allin',
        }
        key = key_map.get(act, act)
        freq = float(hand_freq.get(key, 0))
        if   freq >= 0.30: return 'correct'
        elif freq >= 0.10: return 'acceptable'
        elif freq >= 0.03: return 'leak'
        else:              return 'major_leak'

    # 2. Fallback (sem hand_freq): lógica binária original
    if in_rng and act in ('raise', 'jam'):    return 'correct'
    if in_rng and act == 'call':              return 'acceptable'
    if in_rng and act == 'fold':              return 'leak'
    if in_limp and act == 'call':             return 'correct'
    if in_limp and act in ('raise', 'jam'):   return 'acceptable'
    if in_limp and act == 'fold':             return 'leak'
    if not in_rng and not in_limp:
        if act == 'fold':                     return 'correct'
        if act in ('raise', 'jam'):
            return 'leak' if is_sb else ('major_leak' if stack_bb > 25 else 'leak')
        if act == 'call':
            return 'acceptable' if is_sb else 'leak'
    return 'acceptable'


def _vs_rfi_quality_new(action: str, in_rng: bool, rec: list, hand_freq: dict | None = None) -> str:
    """Quality classifier vs_RFI.

    Quando hand_freq disponível (freq EXATA da mão hero pelo GTO Wizard), classifica
    pela frequência GTO da ação tomada — mais preciso que verificar in/out range:
      freq >= 30%  → correct      (ação dominante ou frequente do GTO)
      10–30%       → acceptable   (ação válida do GTO mix, minoritária)
      3–10%        → leak         (ação raramente GTO)
      < 3%         → major_leak   (ação fora do GTO)

    Sem hand_freq, fallback pro classificador binário (in_rng/rec) original.
    """
    act = action.lower()
    if hand_freq:
        # Mapear action → key em hand_freq
        key_map = {
            'fold': 'fold',
            'call': 'call', 'check': 'call',
            'raise': 'raise', 'bet': 'raise',
            'jam': 'allin', 'allin': 'allin', 'shove': 'allin', 'all-in': 'allin',
        }
        key = key_map.get(act, act)
        freq = float(hand_freq.get(key, 0))
        if   freq >= 0.30: return 'correct'
        elif freq >= 0.10: return 'acceptable'
        elif freq >= 0.03: return 'leak'
        else:              return 'major_leak'

    # Fallback (sem hand_freq): lógica binária original
    if in_rng and act in rec:                     return 'correct'
    if in_rng and act == 'fold':                  return 'leak'
    if in_rng and act not in rec:                 return 'leak'
    if not in_rng and act == 'fold':              return 'correct'
    if not in_rng and act in ('raise', 'jam'):    return 'major_leak'
    if not in_rng and act == 'call':              return 'leak'
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


def _vs_3bet_quality(action: str, in_4b: bool, in_cl: bool, *,
                     in_jam: bool = False, hand_freq: dict | None = None) -> str:
    act = action.lower()
    if act in ('shove', 'allin', 'all-in'):
        act = 'jam'
    # Classifica pela freq exata da mão quando disponível (mesma lógica do RFI)
    if hand_freq:
        key_map = {'fold': 'fold', 'call': 'call', 'check': 'call',
                   'raise': 'raise', 'bet': 'raise', 'jam': 'allin'}
        freq = float(hand_freq.get(key_map.get(act, act), 0))
        if   freq >= 0.30: return 'correct'
        elif freq >= 0.10: return 'acceptable'
        elif freq >= 0.03: return 'leak'
        else:              return 'major_leak'
    # Fallback binário (sem hand_freq)
    if in_4b and act in ('raise', 'jam'):       return 'correct'
    if in_cl and act == 'call':                  return 'correct'
    if in_jam and act == 'jam':                  return 'correct'
    if (in_4b or in_cl or in_jam) and act == 'fold': return 'leak'
    if not (in_4b or in_cl or in_jam) and act == 'fold': return 'correct'
    return 'major_leak'


# ── Professional notes ────────────────────────────────────────────────────────

def _rfi_notes(pos, hand, stack, pct, in_rng, action, *, in_limp: bool = False,
               hand_freq: dict | None = None) -> list[str]:
    notes = []
    label = _POS.get(pos, pos)
    pct_s = f"{pct*100:.0f}%"
    act   = action.lower()
    if in_rng:
        notes.append(f"{label} abre {pct_s} das mãos a {stack:.0f}bb — {hand} está no range de abertura.")
        # Pro_note baseado na freq EXATA da ação tomada (vs. dominante)
        hf_fold  = float(hand_freq.get('fold', 0))  if hand_freq else 0.0
        hf_raise = float(hand_freq.get('raise', 0)) if hand_freq else 0.0
        hf_allin = float(hand_freq.get('allin', 0)) if hand_freq else 0.0
        # Mapear ação → freq da ação tomada
        act_freq_map = {'fold': hf_fold, 'raise': hf_raise, 'bet': hf_raise,
                        'jam': hf_allin, 'shove': hf_allin, 'allin': hf_allin, 'call': 0.0}
        act_freq = act_freq_map.get(act, 0.0)
        # Ação dominante
        action_pcts = [('Fold', hf_fold), ('Raise', hf_raise), ('Shove', hf_allin)]
        action_pcts.sort(key=lambda x: -x[1])
        dom_name, dom_freq = action_pcts[0]
        act_label = {'fold': 'Fold', 'raise': 'Raise', 'bet': 'Raise',
                     'jam': 'Shove', 'shove': 'Shove', 'allin': 'Shove', 'call': 'Limp/Call'}.get(act, act.title())

        if hand_freq and (hf_raise > 0 or hf_allin > 0 or hf_fold > 0):
            if act_freq >= 0.50:
                notes.append(f"{act_label} é a ação dominante GTO pra {hand} ({act_freq*100:.0f}%).")
            elif act_freq >= 0.20:
                notes.append(f"{act_label} é GTO válido pra {hand} ({act_freq*100:.0f}%), mas {dom_name.lower()} é dominante ({dom_freq*100:.0f}%).")
            elif act_freq >= 0.03:
                notes.append(f"{act_label} é GTO raramente ({act_freq*100:.0f}%) pra {hand}. GTO prefere {dom_name.lower()} ({dom_freq*100:.0f}%).")
            else:
                notes.append(f"{act_label} com {hand} é leak — GTO sempre escolhe {dom_name.lower()} ({dom_freq*100:.0f}%) neste spot.")
        else:
            # Sem hand_freq: textos genéricos antigos
            if act == 'fold':
                notes.append(f"Foldar {hand} do {label} é um leak: GTO sempre joga essa mão neste spot.")
            elif act == 'call':
                notes.append("Limp desperdiça vantagem posicional. Raise/shove é a linha mais lucrativa aqui.")
            else:
                notes.append(f"Raise correto. {hand} é uma abertura sólida do {label} neste stack.")
    elif in_limp:
        notes.append(f"{hand} do {label} a {stack:.0f}bb — mão no range de limp (call) da small blind.")
        if act == 'call':
            notes.append(f"Limp correto. {hand} se beneficia de ver flop barato antes de agir após o BB.")
        elif act in ('raise', 'jam'):
            notes.append(f"Raise com {hand} é aceitável mas não optimal — o GTO prefere limp para explorar posição pós-flop.")
        elif act == 'fold':
            notes.append(f"Foldar {hand} do SB é um leak: a mão tem equity para limp e ver flop barato.")
    else:
        notes.append(f"{hand} está fora do range GTO do {label} a {stack:.0f}bb (range: top {pct_s}).")
        if act in ('raise', 'jam'):
            if stack <= 20:
                notes.append(f"Com {stack:.0f}bb o jogo é push/fold — {hand} não tem equity suficiente para shove aqui.")
            else:
                notes.append(f"Abrir {hand} do {label} é loose: perde EV contra os ranges de defesa dos oponentes.")
        elif act == 'fold':
            notes.append(f"Fold correto. {hand} não justifica entrada desta posição neste stack.")
    # Nota sobre stack — usa hand_freq quando disponível pra ser preciso.
    # Evita "essencialmente push/fold" quando GW indica raise sized é dominante (ex: QQ BTN 8bb).
    if hand_freq and in_rng:
        hf_r = float(hand_freq.get('raise', 0))
        hf_a = float(hand_freq.get('allin', 0))
        if hf_r > 0.7:
            # Raise sized é claramente dominante pra essa mão — não é push/fold puro
            if stack <= 15:
                notes.append(f"Mesmo com {stack:.0f}bb, GTO prefere raise sized ({hf_r*100:.0f}%) — {hand} mantém valor pós-flop.")
        elif hf_a > 0.7:
            # Allin é dominante — push/fold de fato
            notes.append(f"Com {stack:.0f}bb, GTO faz shove ({hf_a*100:.0f}%) com {hand} — maximiza fold equity.")
        elif hf_r > 0.2 and hf_a > 0.2:
            # Mix significativo entre raise e shove — zona transição
            notes.append(f"Stack {stack:.0f}bb em zona de transição: GTO mistura raise ({hf_r*100:.0f}%) e shove ({hf_a*100:.0f}%) com {hand}.")
    elif stack <= 15:
        # Fallback sem hand_freq (mão fora do range, ou v2 legacy) — genérico
        notes.append(f"Com {stack:.0f}bb a jogabilidade pós-flop é limitada — equity de mão e posição são prioridade.")
    elif stack <= 25:
        notes.append(f"Com {stack:.0f}bb a jogabilidade pós-flop é limitada — equity de mão e posição são prioridade.")
    return notes


def _vs_rfi_notes_new(pos, vs_pos, hand, stack, aggr_pct, in_rng, rec, action) -> list[str]:
    """Pro notes for RegLife vs_RFI format."""
    notes  = []
    label  = _POS.get(pos, pos)
    vs_lbl = _POS.get(vs_pos, vs_pos)
    aggr_s = f"{aggr_pct*100:.0f}%"
    act    = action.lower()
    rec_s  = '/'.join(r.title() for r in rec if r != 'fold')
    if in_rng:
        notes.append(f"{label} continua com {aggr_s} das mãos vs open do {vs_lbl} a {stack:.0f}bb — {hand} está no range de {rec_s or 'defesa'}.")
        if act == 'fold':
            notes.append(f"Foldar {hand} vs {vs_lbl} open é excessivamente tight e perde EV no longo prazo.")
        elif act in ('raise', 'jam') and rec == ['call']:
            notes.append(f"3bet com {hand} aqui não é optimal: GTO preconiza call (flat) neste spot.")
        elif act == 'call' and rec in (['raise'], ['jam']):
            notes.append(f"Call com {hand} é passivo: GTO preconiza 3bet neste spot.")
    else:
        notes.append(f"{hand} está fora do range de defesa do {label} vs {vs_lbl} open a {stack:.0f}bb (defende {aggr_s}).")
        if act == 'fold':
            notes.append(f"Fold correto. {hand} não tem equity suficiente para continuar vs range do {vs_lbl}.")
        elif act in ('raise', 'jam'):
            notes.append(f"3bet com {hand} não é sustentado pelo GTO: range de 3bet do {label} vs {vs_lbl} é mais apertado.")
        elif act == 'call':
            notes.append(f"Flat com {hand} fora do range perde EV no longo prazo.")
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


def _pushfold_quality(action: str, in_shove: bool) -> str:
    act = action.lower()
    if in_shove and act in ('jam', 'raise'):     return 'correct'
    if in_shove and act == 'fold':               return 'major_leak'  # foldar mão shove = máxima perda de EV
    if in_shove and act == 'call':               return 'acceptable'
    if not in_shove and act == 'fold':           return 'correct'
    if not in_shove and act in ('jam', 'raise'): return 'major_leak'
    if not in_shove and act == 'call':           return 'leak'
    return 'acceptable'


def _pushfold_notes(pos, hand, stack, shove_pct, in_shove, action, *, is_reshove=False) -> list[str]:
    notes = []
    label  = _POS.get(pos, pos)
    pct_s  = f"{shove_pct*100:.0f}%"
    act    = action.lower()
    verb   = "reshove" if is_reshove else "shove"
    if in_shove:
        notes.append(f"{label} faz {verb} com {pct_s} das mãos a {stack:.0f}bb (GTO push/fold) — {hand} está no range.")
        if act == 'fold':
            notes.append(f"Foldar {hand} a {stack:.0f}bb é um leak: a mão tem equity suficiente para {verb}.")
        elif act == 'call':
            notes.append(f"Call a {stack:.0f}bb é passivo — {verb}/shove maximiza fold equity e EV esperado.")
    else:
        notes.append(f"{hand} está fora do range de {verb} do {label} a {stack:.0f}bb (range: top {pct_s}).")
        if act in ('jam', 'raise'):
            notes.append(f"{verb.capitalize()} com {hand} não é lucrativo neste stack — a mão não tem equity vs calls dos oponentes.")
        elif act == 'fold':
            notes.append(f"Fold correto. {hand} não justifica {verb} desta posição a {stack:.0f}bb.")
    notes.append(f"Stack de {stack:.0f}bb: jogo é essencialmente push/fold — ranges baseados em GTO sem ICM.")
    return notes


def _find_opener_key(vs_rfi: dict, opener_pos: str) -> Optional[str]:
    if not opener_pos:
        return None
    # New format: direct position key
    if opener_pos in vs_rfi and isinstance(vs_rfi[opener_pos], dict):
        return opener_pos
    # Old format: "{pos}_open"
    key = f"{opener_pos}_open"
    return key if key in vs_rfi else None
