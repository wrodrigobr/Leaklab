# -*- coding: utf-8 -*-
"""Um guarda do PREFLOP disparava em TODO postflop e apagava o veredito do solver.

── O que acontecia ────────────────────────────────────────────────────────────────────────────

O guarda existe para um caso real: um call que JA E o all-in nao pode virar erro por ausencia de
dado. Ele dispara quando o facing cobre o stack efetivo (>= 95%) E nao ha gabarito.

So que `_sem_gabarito` era `not preflop_gto.get('available')`, e `_enrich_preflop_gto` devolve
`available=False` para toda street diferente de preflop. No postflop o segundo gatilho era
SEMPRE verdadeiro, e o guarda virava aritmetica pura.

Medido no acervo de producao em 10/08:

    149  linhas postflop em que o guarda dispara
     19  delas com gto_critical (solver: frequencia ZERO) devolvidas como 'standard', score 0.0
    108  em que `best_action` deixou de ser recomendacao e virou eco da acao do hero

O solver acusa e o produto absolve. E o piso do proprio motor (`_gto_label_cap`: gto_critical ->
minimo small_mistake) roda ANTES, entao o guarda o desfazia.

── Por que a coorte de controle e o que prova a atribuicao ────────────────────────────────────

Postflop com gto_critical e facing ABAIXO de 50% do stack (o guarda nao dispara): 135 linhas,
ZERO com label 'standard'. Esse zero e o que atribui as 19 ao gatilho, e nao a outra causa.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import evaluate_decision


def _entrada(street, facing_bb, stack_bb, acao='fold', gto=None):
    """Spot postflop em que o facing cobre o stack — o gatilho aritmetico do guarda."""
    d = {
        'hand_id': 'H-GUARDA', 'street': street, 'player_action': acao,
        'hero_cards': ['Ad', '6d'],
        'spot': {'position': 'CO', 'heroStackBb': stack_bb, 'effectiveStackBb': stack_bb,
                 'facingToBb': facing_bb, 'facingSize': facing_bb, 'potSize': 8.0,
                 'nPlayers': 6, 'board': ['7h', 'Td', '4c']},
        'hand_profile': {'handType': 'A6s', 'category': 'suited_ace'},
        # A equity precisa ficar ABAIXO da requerida (0,30 neste spot) para reproduzir o caso
        # real: so ai o guarda colapsa `best_action` em 'fold', que e a acao do hero, e SO ENTAO
        # ele sobrescreve o label para 'standard'. Com 0,34 o guarda escolhia 'call', a acao
        # divergia, o label sobrevivia — e a mutacao "volta ao guarda so-preflop" PASSAVA. Foi a
        # mutacao que denunciou; a primeira versao deste teste era vacua.
        'math': {'potOddsEquity': 0.30, 'estimatedEquity': 0.20},
        'range_evaluation': {'rangeZone': 'core_range', 'inRange': True,
                             'recommendedPrimaryAction': 'call', 'alternativeActions': []},
        'context': {'mRatio': 12.0, 'icmPressure': 'medium', 'levelBb': 1.0},
    }
    return d


def _com_solver(monkey_gto):
    """Roda `evaluate_decision` com `_enrich_gto` dublado — o unico jeito de exercitar o ramo
    'postflop COM cobertura' sem depender do banco de nos."""
    import leaklab.decision_engine_v11 as eng
    original = eng._enrich_gto
    eng._enrich_gto = lambda _i: dict(monkey_gto)
    try:
        yield_ = evaluate_decision(_entrada('flop', facing_bb=30.0, stack_bb=30.0))
    finally:
        eng._enrich_gto = original
    return yield_


def test_com_cobertura_do_solver_o_guarda_NAO_apaga_o_veredito():
    """Com o solver dizendo frequencia ZERO, o guarda nao pode zerar o score nem trocar a
    recomendacao pela acao do proprio hero.

    ── Por que NAO se asserta o `label` aqui ──────────────────────────────────────────────────
    A primeira versao deste teste assertava `label != 'standard'` e a mutacao "volta ao guarda
    so-preflop" PASSAVA: neste spot sintetico o label e reposto por outro caminho depois do
    guarda, entao ele nao discrimina. As outras duas consequencias discriminam, medidas com o
    guarda antigo:

        score        0.0   (zerado)          <- deveria ser 0.22
        best_action  'fold' (eco do hero)    <- deveria ser 'call', o que o solver recomenda

    Assertar o sintoma que o proprio caso nao produz e cobertura sem cobrir. As 19 linhas de
    producao com `label='standard'` sao a terceira consequencia, e quem as vigia e a invariante
    `MUDO` da varredura do acervo, nao este teste.
    """
    r = _com_solver({'available': True, 'gto_label': 'gto_critical', 'gto_action': 'call',
                     'gto_freq': 1.0, 'played_freq': 0.0, 'ev_loss_bb': 3.0,
                     'ev_loss_source': 'solver_hand'})
    ev = r['evaluation']
    assert r['bestAction'] == 'call', (
        f"best_action virou eco da acao do hero em vez da recomendacao do solver: {r['bestAction']}")
    assert ev['mistakeScore'] > 0.0, f"o guarda zerou o score com o solver acusando: {ev}"
    assert ev['label'] in ('small_mistake', 'clear_mistake'), ev['label']
    print('OK  test_com_cobertura_do_solver_o_guarda_NAO_apaga_o_veredito')


def test_SEM_cobertura_nenhuma_o_guarda_continua_valendo():
    """CONTROLE, e o motivo de o guarda existir: sem gabarito, o produto nao acusa.

    Sem este teste, o conserto poderia ter sido "desligar o guarda", que reintroduziria o bug
    original — um call que JA E o all-in virando erro por ausencia de dado.
    """
    r = _com_solver({'available': False})
    ev = r['evaluation']
    assert ev['label'] == 'standard', f"o guarda parou de proteger o caso sem gabarito: {ev}"
    assert ev['mistakeScore'] == 0.0, ev
    print('OK  test_SEM_cobertura_nenhuma_o_guarda_continua_valendo')


def test_o_gatilho_continua_sendo_o_facing_que_COBRE_o_stack():
    """CONTROLE de fronteira: sem gabarito e com facing pequeno, o guarda nao deve disparar —
    senao ele viraria um passe livre para todo fold postflop sem cobertura."""
    import leaklab.decision_engine_v11 as eng
    original = eng._enrich_gto
    eng._enrich_gto = lambda _i: {'available': False}
    try:
        curto = evaluate_decision(_entrada('flop', facing_bb=3.0, stack_bb=30.0))
        cobre = evaluate_decision(_entrada('flop', facing_bb=30.0, stack_bb=30.0))
    finally:
        eng._enrich_gto = original
    assert cobre['evaluation']['mistakeScore'] == 0.0, cobre['evaluation']
    assert cobre['bestAction'] == 'fold', cobre['bestAction']
    # O facing pequeno NAO passa pelo guarda: a decisao segue a heuristica normal.
    assert curto['bestAction'] != 'fold' or curto['evaluation']['mistakeScore'] > 0.0, (
        'o guarda disparou com facing de 3bb num stack de 30bb — virou passe livre')
    print('OK  test_o_gatilho_continua_sendo_o_facing_que_COBRE_o_stack')


def test_no_PREFLOP_a_mudanca_e_inerte():
    """`_enrich_gto` retorna available=False fora de flop/turn/river, entao o `and` novo nao
    pode alterar nada no preflop. Verificado chamando a funcao, nao lendo o codigo."""
    from leaklab.decision_engine_v11 import _enrich_gto
    for street in ('preflop', 'flop', 'turn', 'river'):
        d = _entrada(street, 6.0, 30.0)
        disponivel = _enrich_gto(d).get('available')
        if street == 'preflop':
            assert disponivel is False, 'o enrichment postflop passou a responder no preflop'
    print('OK  test_no_PREFLOP_a_mudanca_e_inerte')


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
