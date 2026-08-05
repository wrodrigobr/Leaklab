# -*- coding: utf-8 -*-
"""Shove sobre all-in cujo excesso NINGUEM pode pagar: a jogada E o call.

── A mao reportada pelo usuario ───────────────────────────────────────────────────────────────

Torneio 3960586609, mao 259090647211, flop [7s 9c Ad], hero com AK:

    Gazsi100: bets 7046 and is all-in
    CSM96:    raises 2728 to 9774 and is all-in     <- hero
    Uncalled bet (2728) returned to CSM96

O produto marcava `marginal` com `best_action = call`. O usuario: *"eu cobria todo mundo... a
sugestao e de call e nao shove, mas nesta mao dava na mesma"*. Ele esta certo, e da para PROVAR
sem olhar o resultado: o terceiro jogador vivo tinha ~2.550 atras, contra 7.046 ja all-in. O
excesso era impagavel por qualquer um.

── O criterio e de DECISAO, nao de resultado ──────────────────────────────────────────────────

**Nao** usa "Uncalled bet returned", que depende do que o vilao fez depois. Usa: o teto de cada
oponente vivo (o que ja pos nesta street + o que sobra atras) contra o valor ja all-in. Se
ninguem passa desse valor, aumentar nao extrai nada e a jogada e identica ao call.

A diferenca entre os dois criterios e grande e importa: no acervo, **24** decisoes tiveram o bet
devolvido, mas so **10** eram provavelmente impagaveis na hora de decidir. Nas outras 14 alguem
PODIA ter pago mais e escolheu foldar — ali o raise tem fold equity, e trata-lo como call seria
apagar uma diferenca que existe.

── O que muda ─────────────────────────────────────────────────────────────────────────────────

A decisao e gradeada como CALL (o custo real e o do call) e a acao EXIBIDA segue sendo a de
verdade — o jogador deu shove e a tela tem que dizer isso. Quando o melhor seria `call`, passa a
exibir a acao dele, porque sao a MESMA jogada: "melhor: call" ao lado de "voce deu shove" e uma
correcao fantasma.

`best_action = fold` NAO e afetado: ali a critica e legitima (o leak e entrar na mao, nao o
tamanho), e isso sai de graca porque so mexemos quando o melhor e o call.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

# Reducao da mao real. Hero (CSM96) cobre; bambos12345 fica com 2550 atras contra 7046 all-in.
_MAO = """PokerStars Hand #259090647211: Tournament #3960586609, $1.47+$1.47+$0.36 USD Hold'em No Limit - Level VII (150/300) - 2025/12/29 16:16:00 BRT
Table '3960586609 5' 8-max Seat #6 is the button
Seat 3: bambos12345 (5000 in chips)
Seat 4: Gazsi100 (9496 in chips)
Seat 5: CSM96 (12224 in chips)
Seat 7: Maddin101-M! (4562 in chips)
Seat 8: snakevenin (4764 in chips)
bambos12345: posts the ante 50
Gazsi100: posts the ante 50
CSM96: posts the ante 50
Maddin101-M!: posts the ante 50
snakevenin: posts the ante 50
Maddin101-M!: posts small blind 150
snakevenin: posts big blind 300
*** HOLE CARDS ***
Dealt to CSM96 [Kd Ah]
bambos12345: calls 300
Gazsi100: raises 300 to 600
CSM96: raises 1800 to 2400
Maddin101-M!: folds
snakevenin: folds
bambos12345: calls 2100
Gazsi100: calls 1800
*** FLOP *** [7s 9c Ad]
bambos12345: checks
Gazsi100: bets 7046 and is all-in
CSM96: raises 2728 to 9774 and is all-in
bambos12345: folds
Uncalled bet (2728) returned to CSM96
*** SUMMARY ***
Total pot 21238
"""


def _decisoes(txt=_MAO):
    hand = parse_hand_history(txt)[0]
    return {(di.get('street'), (di.get('player_action') or '').lower()): di
            for di in build_decision_inputs_for_hand(hand)}


def test_a_mao_reportada_marca_a_equivalencia():
    di = _decisoes()[('flop', 'shove')]
    assert (di.get('spot') or {}).get('facingAllin') is True
    assert (di.get('spot') or {}).get('shoveEquivaleCall') is True, (
        'o excesso era impagavel (2550 atras contra 7046 all-in) e nao foi reconhecido')


def test_a_mao_reportada_nao_recebe_correcao_fantasma():
    """O que o usuario viu: `best = call` do lado de "voce deu shove"."""
    r = evaluate_decision(_decisoes()[('flop', 'shove')])
    assert r.get('actionTaken') == 'shove', 'a acao exibida tem que ser a REAL'
    assert (r.get('bestAction') or '').lower() != 'call', (
        f"ainda recomenda call para uma jogada identica ao call: best={r.get('bestAction')}")
    assert (r.get('evaluation') or {}).get('label') == 'standard', (
        f"veredito: {(r.get('evaluation') or {}).get('label')}")


def test_o_criterio_e_de_decisao_e_nao_de_resultado():
    """Se um vivo PODE pagar mais que o all-in, o raise e de verdade e nao pode ser suavizado.

    Sem esta guarda o conserto viraria "todo shove sobre all-in e call", que apagaria fold equity
    real. Aqui bambos12345 comeca com 40.000 e sobra muito acima dos 7.046.
    """
    rico = _MAO.replace('Seat 3: bambos12345 (5000 in chips)',
                        'Seat 3: bambos12345 (40000 in chips)')
    di = _decisoes(rico)[('flop', 'shove')]
    assert (di.get('spot') or {}).get('shoveEquivaleCall') is False, (
        'com um vivo que cobre o all-in, o raise NAO e equivalente ao call')


def test_sem_all_in_na_frente_nada_muda():
    """Controle negativo: a regra e do all-in enfrentado, nao de todo raise."""
    for chave, di in _decisoes().items():
        if chave == ('flop', 'shove'):
            continue
        assert not (di.get('spot') or {}).get('shoveEquivaleCall'), (
            f'{chave} foi marcado como equivalente sem enfrentar all-in')


def test_stack_desconhecido_nao_afirma_equivalencia():
    """`_fichas_restantes_de` devolve None quando o stack inicial nao foi lido. Sem saber o resto
    de alguem, o excesso PODE ser pagavel — afirmar equivalencia ali apagaria veredito legitimo."""
    sem_stack = _MAO.replace('Seat 3: bambos12345 (5000 in chips)\n', '')
    di = _decisoes(sem_stack).get(('flop', 'shove'))
    if di is not None:
        assert not (di.get('spot') or {}).get('shoveEquivaleCall'), (
            'afirmou equivalencia sem conhecer o stack de um dos vivos')


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
