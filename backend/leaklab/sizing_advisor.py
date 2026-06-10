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
