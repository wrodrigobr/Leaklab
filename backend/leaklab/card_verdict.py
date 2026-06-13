"""
Veredito do Decision Card a partir das estratégias do solver — fonte PURA e testável
da reconciliação que o `/replay` faz ao vivo (antes inline em `api/app.py`, sem teste
direto; era a camada onde o bug A2s/mão 5 morava).

Invariante central: quando existe a estratégia da MÃO específica do hero
(`hand_strategy`), o veredito vem DELA, NUNCA da ação modal do range agregado
(`strategy`). O range descreve o CONJUNTO de mãos ("fold 63%" = % do range que
desiste); a mão decide a jogada do hero ("A2s raise 93%"). Num nó multiway aproximado
os dois divergem fortemente — julgar pelo range marcava "GTO recomenda Fold" numa mão
que o solver LEVANTA 93%.

Espelha a regra do frontend `cardLogic.verdictStrategy` + a reconciliação do app.
"""
from __future__ import annotations


def norm_action(a) -> str:
    """rstrip 's' + unifica all-in/allin/jam/shove → 'allin'. Mantém sizing
    (bet_75pct, raise_2.5bb) — o matching de prefixo cuida da equivalência base."""
    a = (a or '').strip().lower()
    if not a:
        return ''
    a = a[:-1] if a.endswith('s') else a
    return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a


def _matches(played_norm: str, act_norm: str) -> bool:
    if not played_norm or not act_norm:
        return False
    return (act_norm == played_norm
            or played_norm.startswith(act_norm)
            or act_norm.startswith(played_norm))


def label_for_freq(freq: float) -> str:
    """gto_label pela FREQUÊNCIA da ação na estratégia (mesma régua do app/frontend)."""
    if freq >= 0.60:
        return 'gto_correct'
    if freq >= 0.30:
        return 'gto_mixed'
    if freq >= 0.10:
        return 'gto_minor_deviation'
    return 'gto_critical'


def reconcile_verdict(strategy, hand_strategy, played_action, stored_gto_action=None):
    """
    strategy:          lista [{'action','frequency'}, ...] — RANGE agregado do nó (ou None)
    hand_strategy:     lista [{'action','frequency'}, ...] — MÃO específica do hero (ou None)
    played_action:     ação que o hero tomou
    stored_gto_action: gto_action do banco (fallback p/ recommended quando não há modal)

    Retorna None quando não há nenhuma estratégia. Senão, dict:
      source         : 'hand' (mão tem prioridade) | 'range'
      played_freq    : freq da ação jogada na estratégia escolhida
      live_top_act   : ação modal (a recomendada)
      top_freq       : freq da modal
      gto_label      : label por played_freq
      is_error       : played_freq < 0.30 (fora da estratégia mista)
      reconciled_best: ação jogada (normalizada) se não-erro; senão a modal
      gto_action     : live_top_act or stored_gto_action
    """
    src = hand_strategy if hand_strategy else strategy
    source = 'hand' if hand_strategy else 'range'
    if not src:
        return None

    played_norm = norm_action(played_action)
    played_freq = 0.0
    live_top_act = None
    top_freq = -1.0
    for item in src:
        act = item.get('action', '')
        f = float(item.get('frequency') or 0.0)
        if _matches(played_norm, norm_action(act)):
            played_freq = f
        if f > top_freq:
            top_freq = f
            live_top_act = act
    if live_top_act is None:
        return None

    is_error = played_freq < 0.30
    return {
        'source': source,
        'played_freq': played_freq,
        'live_top_act': live_top_act,
        'top_freq': max(top_freq, 0.0),
        'gto_label': label_for_freq(played_freq),
        'is_error': is_error,
        'reconciled_best': played_norm if not is_error else live_top_act,
        'gto_action': live_top_act or stored_gto_action,
    }
