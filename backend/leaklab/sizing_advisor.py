"""
sizing_advisor.py — análise de TAMANHO de aposta do hero (Fase 1: open preflop).

Teoria do open (RFI), MTT/online moderno:
  - padrão é um open PEQUENO: ~2–2,5bb (na prática um min-raise). Com ante, ainda
    menor é correto; sem ante, no topo da banda.
  - SBxBB é a exceção: se o SB abre min, o BB fecha a ação com preço bom demais e
    defende larguíssimo. O SB SOBE (~2,5–3bb) pra negar o complete barato do BB.
  - sobre limpers (iso-raise): sobe mais (~+1bb por limper).

Sem GTO de tamanho no preflop (as ranges do GW só dão quais mãos, não o size), então
aqui é HEURÍSTICA de teoria — um guia, não um veredito de solver. (Postflop, a Fase 2
compara com o tamanho do próprio nó GTO.)
"""
from typing import Optional

# Bandas de tamanho do open (em bb).
_STD_LO, _STD_HI = 2.0, 2.5         # open padrão (qualquer posição exceto SBxBB)
_SB_LO,  _SB_HI  = 2.5, 3.5         # SBxBB: pode/deve forçar mais
_TOL = 0.10                          # tolerância pra não flagrar 2,0/2,5 no limite


def analyze_open_sizing(*, to_bb: Optional[float], position: str,
                        facing_limp: bool = False) -> Optional[dict]:
    """Classifica o tamanho de um OPEN (RFI) do hero. Retorna {key, status, params} ou None.

      key: open_ok | open_big | open_sb_small | open_iso_small
      status: 'ok' | 'warn'
    """
    if to_bb is None or to_bb <= 0:
        return None
    pos = (position or '').upper().strip()
    is_sb = pos == 'SB'

    if is_sb:
        lo, hi, ideal = _SB_LO, _SB_HI, '2,5–3bb'
    else:
        lo, hi, ideal = _STD_LO, _STD_HI, '2–2,5bb'
    # Iso sobre limpers: a banda sobe (não dá pra contar limpers aqui — abre a folga).
    if facing_limp:
        hi += 2.0
        ideal = '3bb+ (iso sobre limp)'

    p = {'to': round(to_bb, 1), 'ideal': ideal}
    if to_bb > hi + _TOL:
        return {'key': 'open_big', 'status': 'warn', 'params': p}
    if is_sb and to_bb < lo - _TOL:
        # SB abrindo pequeno demais vs BB → suba pra negar o complete
        return {'key': 'open_sb_small', 'status': 'warn', 'params': p}
    if facing_limp and to_bb < 3.0 - _TOL:
        return {'key': 'open_iso_small', 'status': 'warn', 'params': p}
    return {'key': 'open_ok', 'status': 'ok', 'params': p}


# ── Fase 2: sizing POSTFLOP vs o tamanho do próprio nó GTO ────────────────────────

def _size_label_to_pct(action: str, pot_bb: Optional[float]) -> Optional[float]:
    """Converte o label de tamanho do solver pra % do pote. 'bet_50pct'→50; 'bet_6.4bb'
    →6.4/pot; 'bet_1.5x'→150 (x = x vezes o pote). 'allin'/sem size → None."""
    import re
    a = (action or '').lower()
    m = re.search(r'(\d+(?:\.\d+)?)\s*pct', a)
    if m:
        return float(m.group(1))
    m = re.search(r'(\d+(?:\.\d+)?)\s*bb', a)
    if m and pot_bb and pot_bb > 0:
        return float(m.group(1)) / pot_bb * 100.0
    m = re.search(r'(\d+(?:\.\d+)?)\s*x', a)
    if m:
        return float(m.group(1)) * 100.0
    return None


def gto_main_bet_size_pct(strategy, pot_bb: Optional[float] = None) -> Optional[int]:
    """Tamanho de aposta (% do pote) da ação agressiva de MAIOR frequência no nó GTO.
    None se o nó não aposta / não dá pra extrair o tamanho."""
    best_pct, best_freq = None, -1.0
    for s in strategy or []:
        a = (s.get('action') or '').lower()
        if not (a.startswith('bet') or a.startswith('raise')):
            continue
        pct = _size_label_to_pct(a, pot_bb)
        f = float(s.get('frequency') or 0.0)
        if pct is not None and f > best_freq:
            best_freq, best_pct = f, pct
    return round(best_pct) if best_pct is not None else None


# ── #3: sizing do 3-BET (relativo ao open enfrentado) ────────────────────────────

_3BET_IP_LO,  _3BET_IP_HI  = 2.6, 3.6      # IP  ~3x o open
_3BET_OOP_LO, _3BET_OOP_HI = 3.4, 4.6      # OOP ~4x o open (cobra mais, nega realização)
_SQUEEZE_BONUS = 1.0                        # cold caller no meio: sobe ~1x por caller


def analyze_3bet_sizing(*, to_bb: Optional[float], open_to_bb: Optional[float],
                        is_ip: bool, squeeze: bool = False) -> Optional[dict]:
    """Classifica o tamanho de um 3-BET do hero, medido como múltiplo do OPEN enfrentado.

    Teoria: 3-bet IP ~3x o open; OOP ~4x (OOP cobra mais p/ negar realização e levar fold).
    Squeeze (cold caller no meio) sobe ~1x por caller. 3-bet JAM (shove) não entra — o
    tamanho é forçado.

      key: 3bet_ok | 3bet_big | 3bet_small ; status: ok | warn
    """
    if to_bb is None or open_to_bb is None or open_to_bb <= 0 or to_bb <= 0:
        return None
    ratio = to_bb / open_to_bb
    if is_ip:
        lo, hi, ideal = _3BET_IP_LO, _3BET_IP_HI, '~3x'
    else:
        lo, hi, ideal = _3BET_OOP_LO, _3BET_OOP_HI, '~4x'
    if squeeze:
        lo += _SQUEEZE_BONUS
        hi += _SQUEEZE_BONUS
        ideal = ('~4x' if is_ip else '~5x') + ' (squeeze)'

    p = {'ratio': round(ratio, 1), 'ideal': ideal, 'pos': 'IP' if is_ip else 'OOP'}
    if ratio > hi:
        return {'key': '3bet_big', 'status': 'warn', 'params': p}
    if ratio < lo:
        return {'key': '3bet_small', 'status': 'warn', 'params': p}
    return {'key': '3bet_ok', 'status': 'ok', 'params': p}


def analyze_postflop_sizing(*, hero_pct: Optional[float], gto_pct: Optional[float]) -> Optional[dict]:
    """Compara o tamanho da aposta do hero (% pote) com o tamanho principal do nó GTO.
    Tolerância relativa (~25%) — sizing é por famílias, não valor exato."""
    if hero_pct is None or gto_pct is None or gto_pct <= 0:
        return None
    p = {'hero': round(hero_pct), 'gto': round(gto_pct)}
    ratio = hero_pct / gto_pct
    if ratio >= 1.5:
        return {'key': 'postflop_too_big', 'status': 'warn', 'params': p}
    if ratio <= 0.6:
        return {'key': 'postflop_too_small', 'status': 'warn', 'params': p}
    return {'key': 'postflop_ok', 'status': 'ok', 'params': p}
