# -*- coding: utf-8 -*-
"""
REPRODUCAO DE BUG ABERTO — call que ja e all-in marcado como erro.

*** ESTE ARQUIVO FALHA DE PROPOSITO E NAO ESTA NO RUNNER. ***
Ele documenta um bug REAL ainda nao consertado. Registra-lo assim e melhor que descrever em
prosa: quem for consertar tem o caso reproduzido e sabe quando terminou.

── A mao reportada ────────────────────────────────────────────────────────────────────────────────

Torneio 35611776, mao 2790343346. Hero no BB com 10,6bb enfrenta aposta de 37,5bb, da CALL, e o
produto marcou `small_mistake` / `gto_critical` recomendando `jam`.

Com stack menor que a aposta, o call E o all-in: nao existe shove maior que isso. O produto
recomendou exatamente o que o jogador fez e cobrou por isso.

Medido em producao: 3 decisoes com esse padrao, 2 marcadas como erro.

── O que ja foi feito ─────────────────────────────────────────────────────────────────────────────

O guarda existe (`decision_engine_v11`, ~linha 1060) e a REGRA dele esta certa: colapsa jam em call
quando o facing cobre o stack. Ele recalculava o facing como `facingSize / levelBb`, e faltando
qualquer um dos dois o facing virava 0 e o guarda pulava em silencio. Isso foi corrigido: agora ele
prefere `facingToBb`, que o pipeline ja calcula (mesma familia do bug do no de replay, que usava
`facing_bet(=0)` em vez de `facingToBb`).

── O que FALTA, e e por isso que o teste ainda falha ──────────────────────────────────────────────

Mesmo com o facing certo, o veredito continua `small_mistake` neste fixture. Ou seja, existe uma
SEGUNDA condicao no caminho que nao foi satisfeita — provavelmente o ramo que escolhe entre
'call' e 'fold' quando o GTO nao esta disponivel ou a equity vem None (preflop nao computa
equity-vs-range). Nao investiguei ate o fim.

Proximo passo para quem pegar: instrumentar o bloco do guarda com o fixture abaixo e ver qual das
tres ramificacoes ele toma.
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
