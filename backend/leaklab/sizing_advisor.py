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
