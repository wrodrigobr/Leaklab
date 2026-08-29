# -*- coding: utf-8 -*-
"""HUD do HERÓI num torneio só: os indicadores da sessão, com a amostra na cara.

── O que originou (29/08) ───────────────────────────────────────────────────────────────────

Pedido do dono: na tela de detalhes do torneio, mostrar como ELE se comportou — VPIP, PFR,
agressão — "mesmo que o número de amostras seja baixo, apenas para o usuário ter ideia".

── Por que NÃO reusar `finalize()` ─────────────────────────────────────────────────────────

`opponent_stats.finalize` aplica gates de amostra (VPIP 100+, 3-bet 750+) porque perfil de
OPONENTE vira read de exploit, e read sem amostra é ruído perigoso. Um torneio tem 50-150 mãos:
com os gates, a tela nasceria vazia sempre.

Aqui o contrato é outro: o número é DESCRITIVO da sessão ("você pagou 31% das mãos NESTE
torneio"), não um read. A honestidade não vem de esconder, vem de declarar: cada stat sai com
numerador, denominador e banda — e `classify_stat` marca `low_sample` quando a amostra não
sustenta comparação com a referência. A célula nunca vira zero mudo, nem some.
"""
from __future__ import annotations

from typing import Optional

from leaklab.opponent_stats import (MIN_HANDS_FOR_TYPE, STAT_REFERENCES, accumulate,
                                    classify_stat, finalize)

#: (chave da resposta, numerador, denominador, chave em STAT_REFERENCES, escala)
_STATS = (
    ('vpip',      'vpip',      'hands',        'vpip',         100.0),
    ('pfr',       'pfr',       'hands',        'pfr',          100.0),
    ('threebet',  'threebet',  'threebet_opp', 'three_bet',    100.0),
    ('fold3bet',  'fold3bet',  'fold3bet_opp', 'fold_to_3bet', 100.0),
    ('cbet',      'cbet',      'cbet_opp',     'cbet_pct',     100.0),
    ('foldcbet',  'foldcbet',  'foldcbet_opp', None,           100.0),
    ('wtsd',      'wtsd',      'saw_flop',     'wtsd',         100.0),
)


def hud_do_heroi(hands, hero: str) -> Optional[dict]:
    """Perfil DESCRITIVO do herói nas mãos dadas. `None` se o herói não aparece."""
    if not hero:
        return None
    acc = accumulate(hands)
    c = acc.get(hero)
    if not c or not c.get('hands'):
        return None

    stats = {}
    for chave, num_k, den_k, ref_k, escala in _STATS:
        num, den = c.get(num_k, 0), c.get(den_k, 0)
        if den <= 0:
            # Sem oportunidade não há taxa: a célula declara a ausência, nunca vira 0.
            stats[chave] = {'value': None, 'num': 0, 'den': 0, 'band': 'no_opportunity'}
            continue
        valor = round(num / den * escala, 1)
        cls = classify_stat(ref_k, valor, sample=den) if ref_k else None
        stats[chave] = {
            'value': valor, 'num': num, 'den': den,
            'band': (cls or {}).get('band') or 'low_sample',
            'healthy': list((cls or {}).get('healthy') or ()) or None,
        }

    # AF: razão, não taxa (agressões / calls preflop+postflop do acumulador).
    af_den = c.get('pf_calls', 0)
    if af_den > 0:
        af = round(c.get('pf_aggr', 0) / af_den, 2)
        cls = classify_stat('af', af, sample=af_den)
        stats['af'] = {'value': af, 'num': c.get('pf_aggr', 0), 'den': af_den,
                       'band': (cls or {}).get('band') or 'low_sample',
                       'healthy': list((cls or {}).get('healthy') or ()) or None}
    else:
        stats['af'] = {'value': None, 'num': 0, 'den': 0, 'band': 'no_opportunity'}

    # Arquétipo SÓ com a amostra que o classificador exige — aqui a régua de oponente vale,
    # porque arquétipo é rótulo comparativo, não descrição.
    arquetipo = None
    if c.get('hands', 0) >= MIN_HANDS_FOR_TYPE:
        perfil = finalize({hero: c}).get(hero) or {}
        if perfil.get('archetype') and perfil['archetype'] != 'unknown':
            arquetipo = perfil['archetype']

    return {'hands': c.get('hands', 0), 'stats': stats, 'archetype': arquetipo}
