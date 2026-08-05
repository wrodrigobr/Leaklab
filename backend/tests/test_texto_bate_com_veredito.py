# -*- coding: utf-8 -*-
"""O texto do card tem que falar do MESMO veredito que o card exibe.

── O card reportado pelo usuario ──────────────────────────────────────────────────────────────

Mao 259090752525, BB com 9d6c, nivel 175/350:

    Erro · Solver · Pre-flop: Fold, Call
    "Equity de 33.6% supera os 18.4% exigidos (+15.2pp) — linha mais agressiva era suportada."
    "A linha FOLD esta fora do range defensavel em BB no pre-flop."
    "Acao esperada: FOLD."

Tres frases que nao podem ser verdade juntas, e o cabecalho dizendo "melhor: Call".

── A causa ────────────────────────────────────────────────────────────────────────────────────

`build_interpretation` lia `range_evaluation.recommendedPrimaryAction` — a opiniao da HEURISTICA.
Mas o `bestAction` que o card exibe e `_best_action`, que o GTO SOBRESCREVE em quatro pontos do
`evaluate_decision`. Quando o solver discordava da heuristica, o cabecalho mostrava um e o texto
narrava o outro.

Medido no acervo: **263 de 657** cards acusados (40%) tinham "Acao esperada: X" com X diferente
do `bestAction`. Num deles o texto mandava fazer **exatamente o que o jogador tinha feito**,
enquanto o acusava de erro.

── A segunda frase, incoerente por construcao ─────────────────────────────────────────────────

`outside_range` fala da MAO, nao da linha. "A linha FOLD esta fora do range defensavel" nao quer
dizer nada: foldar e o default, e a mao estar fora do range **confirma** o fold em vez de conde-lo.
Eram 59 cards. A frase agora so aparece quando o hero ENTROU na mao.
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import build_interpretation

_PT = {'fold': 'FOLD', 'call': 'CALL', 'raise': 'RAISE', 'check': 'CHECK', 'bet': 'BET',
       'jam': 'ALL-IN', 'shove': 'ALL-IN', 'allin': 'ALL-IN'}


def _entrada(acao='fold', heuristica='fold', zona='outside_range'):
    return {
        'hand_id': 'H1', 'street': 'preflop', 'player_action': acao,
        'hero_cards': '9d6c',
        'range_evaluation': {'recommendedPrimaryAction': heuristica, 'rangeZone': zona},
        'math': {'estimatedHandEquity': 0.336, 'potOddsEquity': 0.184, 'drawProfile': 'none'},
        'spot': {'position': 'BB', 'facingSize': 2.0},
        'context': {},
    }


def _esperada_no_texto(interp):
    m = re.search(r'Ação esperada:\s*([A-ZÇÃÕ\-]+)\.', interp.get('strategicExplanation') or '')
    return m.group(1) if m else None


def test_o_texto_usa_o_best_do_card_e_nao_o_da_heuristica():
    """O caso reportado: solver manda CALL, heuristica dizia FOLD."""
    interp = build_interpretation(_entrada(acao='fold', heuristica='fold'), 'small_mistake', 0.184,
                                  best_action='call')
    assert _esperada_no_texto(interp) == 'CALL', (
        f"texto diz {_esperada_no_texto(interp)!r} enquanto o card exibe CALL")


def test_o_texto_nunca_manda_fazer_o_que_ja_foi_feito():
    """O caso mais absurdo do acervo: acusa o jogador e recomenda a acao dele."""
    for acao, best in (('call', 'fold'), ('fold', 'call'), ('raise', 'fold')):
        interp = build_interpretation(_entrada(acao=acao, heuristica=acao), 'clear_mistake', 0.2,
                                      best_action=best)
        esperada = _esperada_no_texto(interp)
        assert esperada != _PT[acao], (
            f'acusou {acao} e o texto mandou fazer {esperada} — a propria acao')
        assert esperada == _PT[best], f'esperava {_PT[best]}, veio {esperada}'


def test_foldar_nao_esta_fora_do_range_defensavel():
    """`outside_range` fala da MAO. Para um FOLD, a frase confirma em vez de condenar."""
    interp = build_interpretation(_entrada(acao='fold', zona='outside_range'), 'small_mistake',
                                  0.184, best_action='call')
    txt = interp.get('strategicExplanation') or ''
    assert 'fora do range defensável' not in txt, (
        f'frase incoerente sobreviveu num FOLD: {txt}')


def test_a_frase_do_range_segue_para_quem_ENTROU_na_mao():
    """Controle negativo: a frase e util quando o hero jogou uma mao fora do range."""
    interp = build_interpretation(_entrada(acao='raise', zona='outside_range'), 'clear_mistake',
                                  0.2, best_action='fold')
    assert 'fora do range defensável' in (interp.get('strategicExplanation') or ''), (
        'a frase sumiu tambem para quem entrou na mao — o conserto vazou')


def test_chamador_antigo_nao_quebra():
    """`best_action=None` cai no comportamento de antes, que e o CONHECIDO."""
    interp = build_interpretation(_entrada(acao='fold', heuristica='call'), 'small_mistake', 0.184)
    assert _esperada_no_texto(interp) == 'CALL'


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
