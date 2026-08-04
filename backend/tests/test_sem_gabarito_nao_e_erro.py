# -*- coding: utf-8 -*-
"""
Sem gabarito, o motor nao acusa um FOLD — e o "so o fold" tem razao de ser.

── A regra ────────────────────────────────────────────────────────────────────────────────────────

O motor ja enunciava, em outro ponto: "sem gabarito nao e erro; a decisao sai da conta em vez de
virar acusacao". Nao estava aplicada aqui. Medido no acervo: das 196 decisoes acusadas de erro,
**44 (22,4%) nao tem cobertura NENHUMA** — nem solver, nem range preflop. Sem gabarito, tudo que
sobra e o estimador heuristico de equity.

── Por que SO o fold, e nao um cap cego de "sem GTO" ──────────────────────────────────────────────

Este arquivo ja rejeitou o cap cego uma vez (Tema 2): "uma violacao de pot odds limpa e
clear_mistake legitimo mesmo sem solver". A regra nova nao atropela isso, e a razao e a DIRECAO do
erro do estimador.

O estimador SUPERVALORIZA quem nao tem nada — medido: postflop sem gabarito, 21 das 32 acusacoes
sao de mao `air`. Equity inflada so fabrica erro num sentido:

    acusar quem FOLDOU  ->  "voce tinha equity e desistiu"   <- equity inflada CONDENA
    acusar quem PAGOU   ->  "voce pagou sem equity"          <- equity inflada ABSOLVE

Ou seja: no sentido do call, a inflacao e conservadora. E por isso que a "violacao de pot odds
limpa" do Tema 2 segue podendo condenar — ela condena quem pos dinheiro.

── Por que postflop exige mao `air` ───────────────────────────────────────────────────────────────

Com par+ o estimador esta no regime oposto, em que ele SUBvaloriza (e o Tema 2 cobre esse lado).
Ali um fold acusado pode ser acusacao boa. Sem essa condicao, **foldar o nuts no river viraria
"aceitavel"** — o teste `test_fold_com_mao_feita_continua_acusado` existe por isso.

── O cap e 'marginal', nao 'standard' ─────────────────────────────────────────────────────────────

`marginal` e "subotimo mas defensavel" e NAO conta como erro no veredito de 3 niveis. E exatamente
"sair da conta" sem afirmar que a jogada estava perfeita.

Medido: 13 vereditos mudam, TODOS folds, TODOS mais brandos, zero mais graves. Acusacoes do acervo
caem de 196 para 183.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import evaluate_decision          # noqa: E402


def _decisao(acao='fold', street='flop', hero_cards=None, board=None,
             equity=0.44, pot_odds=0.20, recomendada='call'):
    """Spot SEM cobertura nenhuma (nem solver, nem range preflop) — e ai que a regra vale.

    `equity` acima de `pot_odds` e o que faz o motor acusar o fold: e a equity do estimador
    heuristico, e e ela que a regra desconfia."""
    return dict(
        hand_id='t', street=street, player_action=acao,
        hero_cards=hero_cards if hero_cards is not None else ['7d', '6h'],
        spot=dict(isInPosition=False, isMultiway=False, effectiveStackBb=20.0,
                  position='BB', villainPosition='BTN', board=board if board is not None
                  else ['Qs', '3c', '3d'],
                  facingToBb=3.0, facingSize=3.0, potSize=10.0, potBb=10.0,
                  nActiveOpponents=1, preflopRaisesFaced=1),
        hand_profile=dict(handClass='unpaired'),
        math=dict(potOddsEquity=pot_odds, estimatedHandEquity=equity,
                  impliedOddsFactor=0.0, reverseImpliedOddsFactor=0.0, pressureScore=0.3,
                  equitySource='vs_random'),
        range_evaluation=dict(recommendedPrimaryAction=recomendada,
                              alternativeActions=[], rangeZone='borderline_range',
                              confidence=0.6, mixWeight=0.0),
        context=dict(icmPressure='low', bountyDynamic=False, readsAvailable=False,
                     tournamentStage='middle', heroStackBb=20.0, levelBb=200.0),
    )


def _label(inp):
    return (evaluate_decision(inp).get('evaluation') or {}).get('label')


def _sem_cobertura(r):
    return not (r.get('gto') or {}).get('available') and not (r.get('preflop_gto') or {}).get('available')


# ── a regra ────────────────────────────────────────────────────────────────────────────────────────

def test_fold_sem_gabarito_nao_vira_erro():
    """76o em Q-3-3: o hero nao tem par nenhum, e o estimador o avalia em 44%."""
    inp = _decisao(acao='fold')
    r = evaluate_decision(inp)
    assert _sem_cobertura(r), 'o teste so faz sentido num spot SEM cobertura'
    lab = (r.get('evaluation') or {}).get('label')
    assert lab not in ('small_mistake', 'clear_mistake'), \
        f'fold sem gabarito nao pode virar acusacao, veio {lab}'


def test_o_cap_e_marginal_e_nao_standard():
    """Sair da conta nao e dizer que estava perfeito."""
    assert _label(_decisao(acao='fold')) == 'marginal'


def test_fold_com_mao_feita_continua_acusado():
    """O guarda que impede o absurdo: foldar mao feita NAO vira 'aceitavel'.

    Com par+ o estimador esta no regime em que SUBvaloriza, e ali a acusacao pode ser boa."""
    inp = _decisao(acao='fold', hero_cards=['Qd', 'Jh'], board=['Qs', '3c', '9d'],
                   equity=0.62)
    r = evaluate_decision(inp)
    assert _sem_cobertura(r)
    lab = (r.get('evaluation') or {}).get('label')
    assert lab in ('small_mistake', 'clear_mistake'), \
        f'top pair foldado sem gabarito deve seguir acusado, veio {lab}'


def test_CALL_sem_gabarito_continua_podendo_ser_erro():
    """A regra e so do fold. Equity inflada ABSOLVE quem paga, entao condenar um call
    continua legitimo — e a "violacao de pot odds limpa" que o Tema 2 defende."""
    inp = _decisao(acao='call', equity=0.10, pot_odds=0.45, recomendada='fold')
    r = evaluate_decision(inp)
    assert _sem_cobertura(r)
    lab = (r.get('evaluation') or {}).get('label')
    assert lab in ('small_mistake', 'clear_mistake'), \
        f'call com equity muito abaixo do exigido deve seguir acusado, veio {lab}'


def test_preflop_sem_cobertura_tambem_vale():
    """Preflop quase sempre TEM range, entao o caso sem cobertura precisa ser construido:
    aqui o vilao e desconhecido, e sem ele a consulta nao roteia para cenario nenhum.
    (Descobri isso porque a primeira versao deste teste falhou na propria premissa — o spot
    que eu achei descoberto tinha `preflop_gto.available = True`.)"""
    inp = _decisao(acao='fold', street='preflop', hero_cards=['7d', '6h'], board=[],
                   equity=0.55, pot_odds=0.25)
    inp['spot']['villainPosition'] = ''
    r = evaluate_decision(inp)
    assert _sem_cobertura(r), 'a premissa do teste e o spot NAO ter cobertura'
    lab = (r.get('evaluation') or {}).get('label')
    assert lab not in ('small_mistake', 'clear_mistake'), lab


def test_fold_COM_gabarito_continua_acusado():
    """A condicao "sem cobertura" precisa mesmo estar la. Foldar AA contra um open e erro, e
    a range diz isso — a regra nao pode absolver quem TEM gabarito.

    Este teste nasceu de uma cobertura falsa: na primeira rodada de verificacao, tirar a
    condicao `not gto and not preflop_gto` nao derrubava teste nenhum."""
    inp = _decisao(acao='fold', street='preflop', hero_cards=['Ad', 'Ah'], board=[],
                   equity=0.85, pot_odds=0.25)
    r = evaluate_decision(inp)
    assert (r.get('preflop_gto') or {}).get('available'), 'a premissa e o spot TER cobertura'
    lab = (r.get('evaluation') or {}).get('label')
    assert lab in ('small_mistake', 'clear_mistake'), \
        f'foldar AA com a range dizendo raise deve seguir acusado, veio {lab}'


def test_sem_cartas_a_regra_NAO_dispara():
    """`made_hand_category(None, None)` devolve 'air'. Sem cartas ou sem board nao da para
    AFIRMAR que o hero nao tem nada, e a regra inteira se apoia nisso.

    Isto nao foi hipotese: a suite acusou. `test_clear_fold_error` e o controle do gate de ICM
    montam o spot SEM cartas, e a regra os absolvia lendo a ausencia de dado como 'air' — a
    cicatriz "desconhecido lido como o caso bom" que este projeto ja pagou duas vezes."""
    inp = _decisao(acao='fold')
    inp['hero_cards'] = None
    inp['spot']['board'] = None
    r = evaluate_decision(inp)
    assert _sem_cobertura(r)
    lab = (r.get('evaluation') or {}).get('label')
    assert lab in ('small_mistake', 'clear_mistake'), \
        f'sem cartas a regra nao pode absolver — veio {lab}'


def test_a_regra_nao_inventa_severidade():
    """Nunca AGRAVA: o que ja era standard/marginal continua onde estava."""
    inp = _decisao(acao='fold', equity=0.05, pot_odds=0.40, recomendada='fold')
    lab = _label(inp)
    assert lab in ('standard', 'marginal'), lab


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
