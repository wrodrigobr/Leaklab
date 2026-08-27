# -*- coding: utf-8 -*-
"""O teto de jam desproporcional é conceito de SPR — e SPR é pós-flop.

── O caso que originou (27/08) ────────────────────────────────────────────────────────────

O teto nasceu em 25/08, certo e necessário: três juízes pegaram o card recomendando all-in de 9x,
17x, 19x e até **22x o pote**. A rede impede que a tela mande o aluno colocar o torneio inteiro
num pote de 5bb.

Mas ela não olhava a street. E no preflop o pote é só os blinds (`pot_at_decision_bb` = 1,0),
então **todo** jam acima de 3bb passa do teto. Um push de 11,2bb num pote de 1bb — a jogada mais
padrão que existe em MTT — aparecia na tela como **"aposte"**.

Medido no acervo:

    475 decisões cuja recomendação é jam
    149 seriam trocadas por "bet" pelo teto
        146 PREFLOP   (disparo errado, 10 delas acusações)
          3 postflop  (o caso para o qual a rede foi feita)

98% de disparo errado. Um juiz de poker leu o sintoma na tela — "o aluno lê `aposte` onde o motor
quis dizer all-in" — e a origem era este guarda, escrito por mim no dia anterior.

── Por que o teste tem as duas metades ────────────────────────────────────────────────────

Restringir ao pós-flop é fácil de errar para o outro lado: desligar a rede inteira devolveria o
all-in de 22x o pote à tela, que foi o defeito original. As duas asserções andam juntas.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _f():
    from api.app import _best_action_proporcional
    return _best_action_proporcional


def test_o_jam_PREFLOP_nao_vira_bet():
    """No preflop o pote é só os blinds: qualquer push passa de 3x. Push/fold é a árvore inteira
    dessa profundidade — trocar a palavra ali desinforma o aluno em 146 decisões do acervo."""
    f = _f()
    assert f('jam', 1.0, 11.2, street='preflop') == 'jam', (
        'o push/fold preflop voltou a ser exibido como "aposte" — palavra que nem existe como '
        'ação preflop')
    assert f('shove', 2.1, 32.1, street='preflop') == 'shove'
    assert f('allin', 1.0, 4.6, street='preflop') == 'allin'
    print('OK  test_o_jam_PREFLOP_nao_vira_bet')


def test_a_REDE_do_postflop_continua_de_pe():
    """A metade que protege o conserto de 25/08. Sem ela, volta o all-in de 22x o pote."""
    f = _f()
    assert f('allin', 21.3, 65.4, street='flop') == 'bet', (
        'a rede do pós-flop caiu: a tela volta a recomendar all-in desproporcional ao pote')
    assert f('jam', 5.0, 60.0, street='turn') == 'bet'
    assert f('shove', 3.0, 40.0, street='river') == 'bet'
    print('OK  test_a_REDE_do_postflop_continua_de_pe')


def test_o_jam_PROPORCIONAL_no_postflop_nao_e_tocado():
    """Contraprova da anterior: uma rede que trocasse todo jam pós-flop passaria no teste acima
    e apagaria a recomendação legítima de all-in em pote grande."""
    f = _f()
    assert f('jam', 20.0, 40.0, street='flop') == 'jam', (
        'o teto passou a trocar jam proporcional — 2x o pote é all-in legítimo')
    assert f('allin', 30.0, 30.0, street='river') == 'allin'
    print('OK  test_o_jam_PROPORCIONAL_no_postflop_nao_e_tocado')


def test_o_que_nao_e_jam_nunca_e_tocado():
    f = _f()
    for acao in ('bet', 'check', 'fold', 'call', 'raise'):
        assert f(acao, 1.0, 50.0, street='flop') == acao
    print('OK  test_o_que_nao_e_jam_nunca_e_tocado')


def test_o_replay_passa_a_STREET():
    """Fiação: a função pode saber da street e o chamador não passar. Ancora na chamada."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index('_best_action_proporcional(')
    j = codigo.index('_best_action_proporcional(', i + 10)   # a CHAMADA, não a definição
    assert 'street=' in codigo[j:j + 400], (
        'o /replay parou de passar a street: o teto volta a trocar todo push/fold preflop '
        'por "aposte"')
    print('OK  test_o_replay_passa_a_STREET')


def test_a_recusa_do_teto_NAO_acusa():
    """Coerência: acusar o aluno por não ter feito aquilo que o produto se recusa a recomendar.

    Quando o teto troca o all-in por `bet`, ele está dizendo "não endosso este jam" — e o que
    sobra na tela é uma palavra sem tamanho. Era o único `clear_mistake` do torneio 72, e um juiz
    de poker pediu para tirá-lo da tela: all-in de 3x o pote com segundo par, ENFRENTANDO uma
    aposta, exibido como "aposte".

    O guarda é de fiação porque a regra vive no `/replay`, onde não há função pura a chamar.
    """
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index('_best_exibido = ')
    trecho = codigo[i:i + 2600]
    assert 'str(_best_exibido).lower() != str(reconciled_best).lower()' in trecho, (
        'a recusa do teto voltou a conviver com acusação: o card acusa o aluno por não ter feito '
        'o jam que ele mesmo se recusou a recomendar')
    print('OK  test_a_recusa_do_teto_NAO_acusa')


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
