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
    # a Fold to PF 3Bet GERAL do PT4 (inclui 3-bet a frio): so para o gabarito congelado; a
    # tela nao lista (AY-18, 06/09). Sem regua: a de STAT_REFERENCES e da After Raise.
    ('fold3bet_any', 'fold3bet_any', 'fold3bet_any_opp', None, 100.0),
    ('cbet',      'cbet',      'cbet_opp',     'cbet_pct',     100.0),
    # C-Bet IP / OOP (AY-19): heads-up no flop; sem regua propria, vive no tooltip do C-Bet
    ('cbet_ip',   'cbet_ip',   'cbet_ip_opp',  None,           100.0),
    ('cbet_oop',  'cbet_oop',  'cbet_oop_opp', None,           100.0),
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

    # ── AF: razão, não taxa (agressões postflop / calls postflop) ────────────────────────────
    #
    # Zero call NÃO é zero oportunidade, e essa confusão era um defeito: o dono olhou um torneio
    # de 17 mãos com C-Bet 100% (1/1) e o AF dizendo "sem spot", e perguntou se estava certo. Não
    # estava. Forjado o caso (herói abre, leva call, dá c-bet no flop e o vilão folda), o
    # acumulador tinha `pf_aggr=1` e `pf_calls=0`, e a célula reportava `num=0, den=0,
    # no_opportunity`: ela CONTOU a agressão e depois jogou fora, dizendo que não houve spot.
    #
    # São três estados, e não dois:
    #
    #   nenhuma ação postflop            -> não há o que medir      (`no_opportunity`)
    #   agrediu e NUNCA pagou            -> a razão é indefinida    (`so_agressao`)
    #   agrediu e pagou                  -> a razão existe
    #
    # O terceiro é o único que vira número. O segundo não pode virar número nenhum: dividir por
    # zero não dá "infinito" numa tela, dá um valor inventado -- e a casa tem a cicatriz do
    # "célula sem dado nunca vira 0". Aqui é a mesma regra na direção oposta: célula COM dado não
    # pode dizer que não tem dado. Ela mostra a amostra (1/0) e a palavra.
    aggr = c.get('pf_aggr', 0) or 0
    calls = c.get('pf_calls', 0) or 0
    if calls > 0:
        af = round(aggr / calls, 2)
        cls = classify_stat('af', af, sample=calls)
        stats['af'] = {'value': af, 'num': aggr, 'den': calls,
                       'band': (cls or {}).get('band') or 'low_sample',
                       'healthy': list((cls or {}).get('healthy') or ()) or None}
    elif aggr > 0:
        stats['af'] = {'value': None, 'num': aggr, 'den': 0, 'band': 'so_agressao'}
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
