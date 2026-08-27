# -*- coding: utf-8 -*-
"""A recomendação exibida não contradiz a carta exibida ao lado dela.

── Os dois casos que originaram (27/08) ───────────────────────────────────────────────────

**1. Recomendação com frequência ZERO na própria carta.** Um juiz de QA achou 7 de 391 decisões
com `best_action: raise` logo acima de `hand_freq: {fold: 1.0, raise: 0.0}`. O veredito estava
certo — o hero foldou, a carta folda, `action_quality: correct`. Errada era só a palavra, que vinha
do heurístico (`verdict_source: motor`) enquanto a carta dizia outra coisa na mesma tela. Zero
acusações, mas a vitrine se contradizendo.

**2. Multiway não alcançava o all-in.** `api/app.py` filtrava os verbos de decisão por
`('bets','raises','calls','checks','folds')` e o parser normaliza o shove como **`'all-in'`**.
O bloco inteiro era pulado: `_mw_spot` ficava False, `gto_label` não era suprimido e
`pode_falar_como_gto` LIBERAVA. Medido: 9 all-ins pós-flop sem `n_active_opponents`, **5 multiway
de verdade**, 4 deles exibindo veredito de solver heads-up com autorização para falar como GTO.

O all-in é justamente o spot em que o conselho errado custa o torneio.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_a_recomendacao_nao_nomeia_acao_de_frequencia_zero():
    from leaklab.verdict import recomendacao_coerente_com_a_carta as regra
    assert regra('raise', {'allin': 0.0, 'call': 0.0, 'fold': 1.0, 'raise': 0.0}) == 'fold', (
        'a recomendação voltou a nomear uma ação que a carta exibida joga 0% das vezes')
    assert regra('bet', {'fold': 1.0, 'raise': 0.0}) == 'fold', 'bet≡raise não foi reconhecido'
    print('OK  test_a_recomendacao_nao_nomeia_acao_de_frequencia_zero')


def test_recomendacao_COM_frequencia_nao_e_tocada():
    """Contraprova. Uma regra que reescrevesse sempre pela modal apagaria a recomendação legítima
    de estratégia mista — 23 decisões do torneio 72 são `gto_mixed` com best diferente da modal."""
    from leaklab.verdict import recomendacao_coerente_com_a_carta as regra
    assert regra('raise', {'fold': 0.7, 'raise': 0.3}) == 'raise', (
        'a regra passou a reescrever recomendação que a carta JOGA — mata estratégia mista')
    assert regra('call', {'call': 0.05, 'fold': 0.95}) == 'call'
    print('OK  test_recomendacao_COM_frequencia_nao_e_tocada')


def test_sem_dado_a_regra_NAO_inventa():
    """Sem frequência utilizável não se troca a palavra: na dúvida, não se inventa recomendação."""
    from leaklab.verdict import recomendacao_coerente_com_a_carta as regra
    assert regra('raise', None) == 'raise'
    assert regra('raise', {}) == 'raise'
    assert regra('raise', {'fold': 0.0, 'raise': 0.0}) == 'raise'
    print('OK  test_sem_dado_a_regra_NAO_inventa')


def test_o_motor_aplica_a_coerencia():
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    assert 'recomendacao_coerente_com_a_carta(' in codigo, (
        'o motor parou de conferir a recomendação contra a carta exibida')
    print('OK  test_o_motor_aplica_a_coerencia')


def test_o_multiway_alcanca_o_ALL_IN():
    """O verbo que faltava. O parser normaliza o shove como `'all-in'`; sem ele na lista, o
    guarda de multiway não roda justamente no spot mais caro da mão."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index('_VERBOS_DE_DECISAO')
    trecho = codigo[i:i + 300]
    for verbo in ("'all-in'", "'shove'"):
        assert verbo in trecho, (
            'o verbo %s saiu da lista de decisões: o guarda de multiway volta a pular os '
            'all-ins pós-flop, e com eles a supressão do veredito heads-up' % verbo)
    print('OK  test_o_multiway_alcanca_o_ALL_IN')


def test_a_coerencia_vale_SO_no_cenario_rfi():
    """A restrição que um guarda antigo me impôs, e o motivo dela.

    A 1ª versão aplicava a regra em qualquer cenário com carta. Fora do RFI o `hand_freq` tem
    chaves próprias — `vs_3bet` fala em 4bet/call, não em `allin` — e a regra reescreveu o `jam`
    de KK enfrentando 3-bet só porque não achou a chave. `test_recent_regressions.py
    ::test_allin_guard_converts_facing_chips_to_bb` acusou, e estava certo.

    Os 7 casos medidos são todos `scenario: rfi` com `verdict_source: motor`.
    """
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index('recomendacao_coerente_com_a_carta(')
    trecho = codigo[max(0, i - 300):i + 100]
    assert "scenario') == 'rfi'" in trecho, (
        'a coerência voltou a valer fora do RFI: em vs_3bet o `hand_freq` tem outras chaves e a '
        'regra reescreve recomendação legítima por não achar a que procura')
    print('OK  test_a_coerencia_vale_SO_no_cenario_rfi')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
