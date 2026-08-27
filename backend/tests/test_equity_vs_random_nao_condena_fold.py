# -*- coding: utf-8 -*-
"""Equity vs mão ALEATÓRIA não condena um FOLD pós-flop.

── O caso que originou (26/08) ────────────────────────────────────────────────────────────

Um juiz de poker leu o sintoma na tela: o produto manda PAGAR com nove-alto sem projeto porque
"32% > 27,7% exigidos". Os 32% são contra mão **aleatória**; contra quem aposta 57% do pote essa
mão tem uns 10%.

A ablação (mesmo input, mexendo SÓ na equity) desmentiu metade da leitura dele e confirmou a
outra: a equity **não move a recomendação** — em 55 casos, trocar 0,99 por 0,01 não mudou o
`bestAction` nenhuma vez. Ela move o **rótulo**: é ela que transforma o fold em erro.

Medido no acervo inteiro:

    77 acusações de FOLD pós-flop      74 usam equity vs_random
    55 têm custo medido                22 NÃO têm
    nessas 22, derrubar a equity para 0,01 faz a acusação SUMIR em 22 de 22

Ou seja, nas 22 a equity vs aleatória é a **única** evidência sustentando a acusação.

── Por que a regra existente não pegava ───────────────────────────────────────────────────

`sem gabarito não é erro` (04/08) já capa o fold em `marginal` — mas só quando não há cobertura
NENHUMA. As 22 têm nó de solver, então passavam por ela e eram acusadas por um número medido
contra outra coisa.

E já havia DOIS guardas de `equitySource == 'vs_random'` — os dois preflop e os dois na direção do
CALL (tirar absolvição). Este é o simétrico deles.

── A direção é o argumento inteiro ────────────────────────────────────────────────────────

    equity inflada CONDENA quem folda  e  ABSOLVE quem paga

Por isso o conserto anda só num sentido: tira culpa, nunca cria. E rebaixa para `marginal` —
"não temos base para chamar de erro" — em vez de absolver.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_o_fold_sustentado_so_por_equity_vs_random_nao_e_erro():
    from leaklab.verdict import equity_vs_random_nao_condena_fold as regra
    assert regra('small_mistake', 'flop', 'vs_random', 'fold', False) == 'marginal', (
        'voltou a acusar um fold pós-flop tendo como única evidência a equity contra mão '
        'aleatória — o número que condena quem folda por construção')
    assert regra('clear_mistake', 'river', 'vs_random', 'fold', False) == 'marginal'
    print('OK  test_o_fold_sustentado_so_por_equity_vs_random_nao_e_erro')


def test_com_CUSTO_medido_nada_muda():
    """A contraprova mais importante. 55 das 77 acusações de fold pós-flop TÊM custo medido — uma
    regra que rebaixasse todas apagaria 55 acusações legítimas para consertar 22."""
    from leaklab.verdict import equity_vs_random_nao_condena_fold as regra
    assert regra('small_mistake', 'flop', 'vs_random', 'fold', True) == 'small_mistake', (
        'a regra passou a rebaixar acusação COM custo medido: virou peneira')
    assert regra('clear_mistake', 'turn', 'vs_random', 'fold', True) == 'clear_mistake'
    print('OK  test_com_CUSTO_medido_nada_muda')


def test_a_regra_NAO_pega_o_que_nao_e_dela():
    """Cada condição existe por um motivo, e cada uma precisa ser conferida sozinha — senão a
    regra vira um cap genérico com nome específico."""
    from leaklab.verdict import equity_vs_random_nao_condena_fold as regra
    # equity contra o range de quem apostou: a conta é honesta, pode condenar
    assert regra('small_mistake', 'flop', 'vs_range', 'fold', False) == 'small_mistake'
    # o CALL é a outra direção — inflar equity absolve quem paga, não condena
    assert regra('small_mistake', 'flop', 'vs_random', 'call', False) == 'small_mistake'
    # preflop já tem os dois guardas próprios
    assert regra('small_mistake', 'preflop', 'vs_random', 'fold', False) == 'small_mistake'
    # o que não é acusação não é assunto desta regra
    assert regra('standard', 'flop', 'vs_random', 'fold', False) == 'standard'
    assert regra('marginal', 'flop', 'vs_random', 'fold', False) == 'marginal'
    print('OK  test_a_regra_NAO_pega_o_que_nao_e_dela')


def test_o_motor_aplica_a_regra():
    """Fiação. Regra que existe e não é chamada é o defeito mais recorrente deste projeto."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    codigo = '\n'.join(l.split('#')[0] for l in fonte.split('\n'))
    assert 'equity_vs_random_nao_condena_fold(' in codigo, (
        'o motor parou de aplicar a regra: volta a acusar fold com equity contra mão aleatória')
    print('OK  test_o_motor_aplica_a_regra')


def test_os_guardas_PREFLOP_de_vs_random_continuam_de_pe():
    """Os dois guardas irmãos, na direção oposta. Se alguém "unificar" as três regras num cap só,
    a direção se perde — e a direção é o argumento inteiro."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = '\n'.join(l.split('#')[0] for l in fh.read().split('\n'))
    n = codigo.count("equitySource') == 'vs_random'")
    assert n >= 2, (
        'os guardas preflop de `vs_random` (direção do CALL) sumiram: sobraram %d de 2' % n)
    print('OK  test_os_guardas_PREFLOP_de_vs_random_continuam_de_pe')


def test_a_classe_da_mao_decide_a_direcao_do_estimador():
    """A condição que faltava na minha 1ª versão, e que TRÊS guardas antigos acusaram.

    A direção do erro do estimador depende da CLASSE DA MÃO:
        `air` (nada feito)  -> ele INFLA        -> acusar o fold é falso
        par+ / value        -> ele SUBvaloriza  -> a acusação pode ser boa

    Minha primeira versão capava qualquer fold pós-flop e rebaixou o fold de TOP PAIR.
    `test_fold_com_mao_feita_continua_acusado` pegou, e estava certo.
    """
    from leaklab.verdict import estimador_infla_a_equity as infla

    # nada feito: o estimador infla, a regra pode agir
    assert infla(['7c', '2d'], ['As', 'Kh', '9d'], 'flop') is True
    # top pair: o estimador subvaloriza, a acusação pode ser legítima
    assert infla(['Qd', 'Jh'], ['Qs', '3c', '9d'], 'flop') is False, (
        'a regra voltaria a rebaixar o fold de top pair')
    print('OK  test_a_classe_da_mao_decide_a_direcao_do_estimador')


def test_ausencia_de_dado_NAO_e_lida_como_o_caso_que_convem():
    """A armadilha, escrita no lugar de origem e agora dentro da função: sem cartas ou sem board
    não dá para AFIRMAR que o hero não tem nada — e `made_hand_category(None, None)` devolve
    exatamente `'air'`. Ler isso como "air" seria a ausência de dado virando argumento."""
    from leaklab.verdict import estimador_infla_a_equity as infla

    assert infla(None, ['As', 'Kh', '9d'], 'flop') is False, 'sem cartas, a regra disparou'
    assert infla(['7c', '2d'], None, 'flop') is False, 'sem board, a regra disparou'
    assert infla(None, None, 'flop') is False
    print('OK  test_ausencia_de_dado_NAO_e_lida_como_o_caso_que_convem')


def test_as_DUAS_regras_usam_a_MESMA_condicao():
    """Regra 5 com varredura N+1. A condição de classe de mão vive em dois consumidores — o
    guarda `sem gabarito não é erro` e o de `vs_random` no fold. Se alguém reintroduzir a versão
    inline num deles, as duas se separam e só uma recebe o próximo conserto."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    n = codigo.count('estimador_infla_a_equity(')
    assert n >= 2, (
        'a condição de classe de mão deixou de ser compartilhada: %d consumidor(es) em vez de 2'
        % n)
    assert "not in ('value', 'middle')" not in codigo, (
        'a condição voltou a ser inline no motor — as duas regras podem divergir em silêncio')
    print('OK  test_as_DUAS_regras_usam_a_MESMA_condicao')


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
