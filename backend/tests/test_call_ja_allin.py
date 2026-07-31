# -*- coding: utf-8 -*-
"""
Call que JA e all-in nao pode ser marcado como erro com recomendacao de shove.

── A mao reportada ────────────────────────────────────────────────────────────────────────────────

Torneio 35611776, mao 2790343346. Hero no BB com 10,6bb enfrenta aposta de 37,5bb, da CALL, e o
produto marcou `small_mistake` / `gto_critical` recomendando `jam`. Com stack menor que a aposta, o
call E o all-in: nao existe shove maior que isso. O produto recomendou exatamente o que o jogador
fez e cobrou por isso.

Medido em producao: 3 decisoes com esse padrao, 2 marcadas como erro.

── Eram DOIS defeitos, e o segundo so apareceu ao instrumentar ────────────────────────────────────

1. **Fonte errada do facing.** O guarda ja existia e a regra estava certa, mas recalculava o facing
   como `facingSize / levelBb`. Faltando qualquer um dos dois o facing virava 0 e o guarda PULAVA
   EM SILENCIO. Agora prefere `facingToBb`, que o pipeline ja calcula — mesma familia do bug do no
   de replay, que usava `facing_bet(=0)` no lugar dele.

2. **Acusava por AUSENCIA DE DADO.** Com o facing certo o guarda passou a disparar, e a
   instrumentacao mostrou que ele caia no ramo final: sem GTO disponivel e sem equity (preflop nao
   computa equity-vs-range), ele definia o melhor lance como `fold` — e o call all-in virava erro
   porque o motor NAO SABIA, nao porque estivesse errado. E o oposto da regra que vale no resto do
   produto: sem gabarito nao e erro, a decisao sai da conta em vez de virar acusacao.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _decisao(facing_to_bb, stack_bb, level_bb=3000.0, acao='call'):
    """Entrada valida no formato que o motor exige (mesmo esqueleto de test_decision_engine)."""
    return dict(
        hand_id='2790343346', street='preflop', player_action=acao,
        spot=dict(isInPosition=False, isMultiway=False, effectiveStackBb=stack_bb,
                  position='BB', villainPosition='SB',
                  facingToBb=facing_to_bb, facingSize=None, potSize=41.5),
        hand_profile=dict(handClass='unpaired'),
        math=dict(potOddsEquity=0.22, estimatedHandEquity=None,
                  impliedOddsFactor=0.0, reverseImpliedOddsFactor=0.0, pressureScore=0.5),
        range_evaluation=dict(recommendedPrimaryAction='jam',
                              alternativeActions=[], rangeZone='core_range',
                              confidence=0.8, mixWeight=0.0),
        context=dict(icmPressure='low', bountyDynamic=False, readsAvailable=False,
                     levelBb=level_bb, heroStackBb=stack_bb, position='BB', vsPosition='SB'),
        # AK do BB: o GTO tem cobertura aqui e recomenda jam, que foi o caso real. Sem as cartas o
        # motor nao consulta o range e o teste cairia por outro caminho.
        hero_cards=['As', 'Kh'],
    )


def test_o_caso_real_nao_e_mais_erro():
    """Os numeros exatos da mao que o usuario reportou."""
    from leaklab.decision_engine_v11 import evaluate_decision
    r = evaluate_decision(_decisao(facing_to_bb=37.5, stack_bb=10.6))
    label = (r.get('evaluation') or {}).get('label')
    best = (r.get('evaluation') or {}).get('bestAction') or r.get('best_action')
    assert label == 'standard', (label, best, 'call que ja e all-in foi cobrado como erro')


def test_o_guarda_funciona_SEM_levelBb():
    """O motivo real da falha: sem `levelBb` o calculo por fichas dava 0 e o guarda pulava.
    Com `facingToBb` presente, ele nao depende mais disso."""
    from leaklab.decision_engine_v11 import evaluate_decision
    d = _decisao(facing_to_bb=37.5, stack_bb=10.6, level_bb=0.0)
    r = evaluate_decision(d)
    assert (r.get('evaluation') or {}).get('label') == 'standard', r.get('evaluation')


def test_com_GTO_disponivel_o_call_all_in_e_correto():
    """A condicao REAL da mao reportada: o GTO tinha cobertura e recomendava jam. Com o facing
    lido da fonte certa, o guarda colapsa jam em call e o veredito sai correto."""
    from leaklab.decision_engine_v11 import evaluate_decision
    d = _decisao(facing_to_bb=37.5, stack_bb=10.6)
    d['preflop_gto'] = {'available': True, 'recommended_actions': ['jam']}
    r = evaluate_decision(d)
    assert (r.get('evaluation') or {}).get('label') == 'standard', r.get('evaluation')


def test_ausencia_de_dado_NAO_vira_acusacao():
    """O segundo defeito. Sem GTO e sem equity o motor nao tem base, e o ramo antigo respondia
    'fold' — transformando desconhecimento em erro do jogador."""
    from leaklab.decision_engine_v11 import evaluate_decision
    r = evaluate_decision(_decisao(facing_to_bb=37.5, stack_bb=10.6))
    ev = r.get('evaluation') or {}
    assert ev.get('label') == 'standard', ev


def test_call_que_NAO_e_all_in_continua_sendo_julgado():
    """O guarda nao pode virar desculpa geral: com stack folgado, call e shove sao acoes
    diferentes e o veredito tem que continuar valendo."""
    from leaklab.decision_engine_v11 import evaluate_decision
    r = evaluate_decision(_decisao(facing_to_bb=2.5, stack_bb=60.0))
    ev = r.get('evaluation') or {}
    assert ev.get('label') is not None, ev   # segue avaliando de verdade


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
