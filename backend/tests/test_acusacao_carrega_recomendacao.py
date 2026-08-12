# -*- coding: utf-8 -*-
"""Quem muda o veredito carrega a recomendacao e o score JUNTO — os quatro guardas de 11/08.

── A familia ──────────────────────────────────────────────────────────────────────────────────

O inventario de fechamento achou o mesmo defeito em quatro guardas deliberados: cada um mudava o
`label` e parava ali. O resultado no card era contradicao interna:

    G6 (pote limpado)   "Erro" com a coluna ideal repetindo o FOLD do jogador, score 0.0
    RC-B (piso por EV)  idem, no postflop, com selo `GTO Correto` ao lado
    shove≡call          score 0,1615 por gap('call','jam') — a MESMA decisao de commit
    arvore rasa (jam)   rec convertida para jam, hero JAMOU, e ficou 'marginal'

A regra unica: acusacao exige poder dizer O QUE fazer no lugar; equivalencia economica vale para
os DOIS lados da comparacao; e label novo leva o score para a banda dele (`_align_score_to_label`
so conserta no reconcile — o motor nao pode depender disso).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.decision_engine_v11 as eng


def _entrada(**kw):
    d = {
        'hand_id': 'H', 'street': 'preflop', 'player_action': 'shove',
        'hero_cards': ['Ad', 'Kd'],
        'spot': {'position': 'BTN', 'heroStackBb': 11.3, 'effectiveStackBb': 11.3,
                 'facingSize': 0.0, 'potSize': 1.5, 'nPlayers': 9},
        'hand_profile': {'handType': 'AKs', 'category': 'premium'},
        'math': {'potOddsEquity': 0.0, 'estimatedEquity': 0.6},
        'range_evaluation': {'rangeZone': 'borderline_range', 'inRange': True,
                             'recommendedPrimaryAction': 'jam', 'alternativeActions': []},
        'context': {'mRatio': 8.0, 'icmPressure': 'medium', 'levelBb': 1.0},
    }
    for k, v in kw.items():
        if isinstance(d.get(k), dict) and isinstance(v, dict):
            d[k] = {**d[k], **v}
        else:
            d[k] = v
    return d


def test_shove_equivale_call_colapsa_a_recomendacao_tambem():
    """t50 de producao: shoveEquivaleCall, rec='jam' — jam, call e shove sao o mesmo commit."""
    r = eng.evaluate_decision(_entrada(
        spot={'shoveEquivaleCall': True, 'facingSize': 9467.0, 'facingToBb': 12.0}))
    ev = r['evaluation']
    assert ev['scoreBreakdown']['baseActionGap'] == 0.0, ev['scoreBreakdown']
    assert ev['scoreBreakdown']['rangePenalty'] == 0.0, ev['scoreBreakdown']
    assert ev['label'] == 'standard', ev
    print('OK  test_shove_equivale_call_colapsa_a_recomendacao_tambem')


def test_CONTROLE_shove_equivale_call_com_rec_FOLD_segue_criticavel():
    """Recomendar fold contra um commit e critica legitima — o colapso nao pode engoli-la."""
    r = eng.evaluate_decision(_entrada(
        spot={'shoveEquivaleCall': True, 'facingSize': 9467.0, 'facingToBb': 12.0},
        range_evaluation={'recommendedPrimaryAction': 'fold', 'rangeZone': 'outside_range',
                          'inRange': False, 'alternativeActions': []},
        math={'potOddsEquity': 0.45, 'estimatedEquity': 0.2}))
    assert r['evaluation']['scoreBreakdown']['baseActionGap'] > 0.0, r['evaluation']
    print('OK  test_CONTROLE_shove_equivale_call_com_rec_FOLD_segue_criticavel')


def _sem_cobertura_preflop(fn):
    """AKs a 7.85bb TEM carta no range local — a primeira fixture deste teste passava pelo
    motivo errado (quality='correct' dava standard por cobertura real, linha 1127, e a mutacao
    do Defeito 3 sobrevivia). O tracer de runtime achou; o dublê isola o guarda de verdade."""
    original = eng._enrich_preflop_gto
    eng._enrich_preflop_gto = lambda _i: {'available': False}
    try:
        return fn()
    finally:
        eng._enrich_preflop_gto = original


def test_arvore_rasa_converteu_para_jam_e_o_hero_jamou():
    """t105: <=10bb converte rec raise->jam. Se o hero jamou, ele fez o que a arvore faz."""
    r = _sem_cobertura_preflop(lambda: eng.evaluate_decision(_entrada(
        spot={'heroStackBb': 7.85, 'effectiveStackBb': 7.85},
        range_evaluation={'recommendedPrimaryAction': 'raise', 'rangeZone': 'borderline_range',
                          'inRange': True, 'alternativeActions': []})))
    assert r['bestAction'] in ('jam', 'shove'), r['bestAction']
    assert r['evaluation']['label'] == 'standard', r['evaluation']
    # CONTROLE: quem FOLDOU nesse spot nao ganha o standard por tabela.
    r2 = _sem_cobertura_preflop(lambda: eng.evaluate_decision(_entrada(
        player_action='fold',
        spot={'heroStackBb': 7.85, 'effectiveStackBb': 7.85},
        range_evaluation={'recommendedPrimaryAction': 'raise', 'rangeZone': 'core_range',
                          'inRange': True, 'alternativeActions': []})))
    assert not (r2['evaluation']['label'] == 'standard'
                and r2['evaluation']['mistakeScore'] == 0.0
                and r2['bestAction'] == 'fold'), r2['evaluation']
    print('OK  test_arvore_rasa_converteu_para_jam_e_o_hero_jamou')


def _g6(fold_e_barato):
    """Roda o guarda do pote limpado com a equity multiway dublada — acima ou abaixo do preco."""
    import leaklab.multiway_advisor as mw
    original = mw.equity_realizada_em_pote_limpado
    mw.equity_realizada_em_pote_limpado = (
        lambda cartas, nopp, ip, n_sims=8000: (0.5, 0.40 if fold_e_barato else 0.05))
    try:
        return eng.evaluate_decision(_entrada(
            player_action='fold',
            spot={'facingLimp': True, 'facingToCallBb': 1.0, 'nCanSeeFlop': 3,
                  'isInPosition': False, 'heroStackBb': 30.0, 'effectiveStackBb': 30.0},
            math={'potOddsEquity': 0.2, 'estimatedEquity': 0.5},
            range_evaluation={'recommendedPrimaryAction': 'fold', 'rangeZone': 'borderline_range',
                              'inRange': False, 'alternativeActions': []}))
    finally:
        mw.equity_realizada_em_pote_limpado = original


def test_G6_acusa_com_recomendacao_e_score():
    r = _g6(fold_e_barato=True)
    ev = r['evaluation']
    assert ev['label'] == 'small_mistake', ev
    assert r['bestAction'] == 'call', (
        f"acusou o fold e recomendou {r['bestAction']} — a premissa do guarda e que PAGAR valia")
    assert 0.18 < ev['mistakeScore'] <= 0.35, (
        f"score {ev['mistakeScore']} fora da banda do label small_mistake")
    print('OK  test_G6_acusa_com_recomendacao_e_score')


def test_CONTROLE_G6_nao_acusa_fold_caro():
    r = _g6(fold_e_barato=False)
    assert r['evaluation']['label'] != 'small_mistake', r['evaluation']
    print('OK  test_CONTROLE_G6_nao_acusa_fold_caro')


def _rcb(com_alternativa):
    """RC-B: piso por EV hand-aware alto num no que a range aprova (gto_correct)."""
    hand_strategy = [{'action': 'check', 'frequency': 0.9, 'ev_bb': 0.0}]
    if com_alternativa:
        hand_strategy.append({'action': 'bet_50pct', 'frequency': 0.1, 'ev_bb': 2.56})
    no = {'available': True, 'gto_label': 'gto_correct', 'gto_action': 'check',
          'gto_freq': 0.9, 'played_freq': 0.9, 'strategy': hand_strategy,
          'hand_aware': True, 'hand_strategy': hand_strategy,
          'ev_loss_bb': 2.56, 'ev_loss_source': 'solver_hand'}
    original = eng._enrich_gto
    eng._enrich_gto = lambda _i: dict(no)
    try:
        return eng.evaluate_decision(_entrada(
            street='river', player_action='check',
            hero_cards=['Kh', 'Td'],
            spot={'position': 'BTN', 'board': ['Js', 'Ks', '7c', '3h', 'Jd'],
                  'heroStackBb': 30.0, 'effectiveStackBb': 30.0, 'potSize': 10.0,
                  'potBb': 10.0, 'facingSize': 0.0},
            math={'potOddsEquity': 0.0, 'estimatedEquity': 0.6},
            range_evaluation={'recommendedPrimaryAction': 'check', 'rangeZone': 'core_range',
                              'inRange': True, 'alternativeActions': []}))
    finally:
        eng._enrich_gto = original


def test_RCB_acusa_com_a_alternativa_do_hand_strategy():
    """O 315507 de producao: range checa 90%, ESTA mao perde 2,56bb checando. A acusacao vale e
    a recomendacao vem do mesmo dado que a sustenta."""
    r = _rcb(com_alternativa=True)
    ev = r['evaluation']
    assert ev['label'] == 'small_mistake', ev
    assert 'bet' in (r['bestAction'] or ''), (
        f"acusou o check e recomendou {r['bestAction']!r} — a alternativa do hand_strategy sumiu")
    assert ev['mistakeScore'] > 0.18, f"score {ev['mistakeScore']} contradiz o label"
    print('OK  test_RCB_acusa_com_a_alternativa_do_hand_strategy')


def test_RCB_sem_alternativa_NAO_acusa():
    """Acusar exige poder dizer o que fazer. Sem alternativa nomeavel, 'Erro; ideal: o que voce
    fez' e a contradicao AUTO — o piso recua."""
    r = _rcb(com_alternativa=False)
    ev = r['evaluation']
    assert ev['label'] not in ('small_mistake', 'clear_mistake'), ev
    print('OK  test_RCB_sem_alternativa_NAO_acusa')


def test_EV_sem_fonte_nao_sai_do_motor():
    """PROCED: o overlay preflop devolvia ev_loss_bb=0.0 com fonte None — numero orfao."""
    original = eng._enrich_preflop_gto
    eng._enrich_preflop_gto = lambda _i: {
        'available': True, 'action_quality': 'correct', 'recommended_actions': ['call'],
        'ev_loss_bb': 0.0, 'ev_loss_source': None}
    try:
        r = eng.evaluate_decision(_entrada(player_action='call'))
    finally:
        eng._enrich_preflop_gto = original
    g = r.get('gto') or {}
    assert g.get('ev_loss_bb') is None, f"EV sem fonte vazou: {g.get('ev_loss_bb')}"
    # CONTROLE: com fonte, o numero sai.
    eng._enrich_preflop_gto = lambda _i: {
        'available': True, 'action_quality': 'correct', 'recommended_actions': ['call'],
        'ev_loss_bb': 0.0, 'ev_loss_source': 'preflop_overlay'}
    try:
        r2 = eng.evaluate_decision(_entrada(player_action='call'))
    finally:
        eng._enrich_preflop_gto = original
    assert (r2.get('gto') or {}).get('ev_loss_bb') == 0.0, r2.get('gto')
    print('OK  test_EV_sem_fonte_nao_sai_do_motor')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
