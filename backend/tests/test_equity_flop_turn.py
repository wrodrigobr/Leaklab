# -*- coding: utf-8 -*-
"""Equity de flop/turn contra a range que continua: a irmã da conta do river.

── Por que existe (28/08) ──────────────────────────────────────────────────────────────────

Frente pedida pelo dono: "atacar a equity de flop/turn antes de escalar a base". O river virou
conta exata em 24/08; no flop e no turn o estimador por CLASSE sobreviveu porque ainda falta carta.
Mas o defeito é o mesmo: a tabela é calibrada contra MÃO ALEATÓRIA, e o vilão que segue na mão não
tem mão aleatória.

── O que estes guardas protegem ────────────────────────────────────────────────────────────

O número entra no veredito. Um erro de amostragem que ninguém mediu, ou uma semente que muda entre
boots, produz a mesma decisão saindo `standard` num acesso e `small_mistake` no outro -- que já
aconteceu neste projeto e levou um dia para ser encontrado.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _tem_eval7():
    try:
        import eval7  # noqa: F401
        return True
    except Exception:                                          # noqa: BLE001
        return False


def _densa(hero, board, saidas_max=None):
    """A conta que varre TODAS as saídas contra TODOS os combos. Lenta de propósito: é o oráculo
    contra o qual a amostragem se justifica."""
    import eval7
    from itertools import combinations
    from leaklab.equity_real import _BARALHO
    from leaklab.range_de_continuacao import categoria_do_board, continua

    mortas = set(hero) | set(board)
    livres = [c for c in _BARALHO if c not in mortas]
    bc = [eval7.Card(c) for c in board]
    cat = categoria_do_board(bc)
    vilao = [v for v in combinations(livres, 2)
             if continua((eval7.Card(v[0]), eval7.Card(v[1])), bc, cat, com_draws=True)]

    def forca(cs):
        return eval7.evaluate([eval7.Card(c) for c in cs])

    faltam = 5 - len(board)
    if faltam == 1:
        saidas = [(c,) for c in livres]
    else:
        # EMBARALHA antes de cortar. A 1a versao fazia `list(combinations(...))[:300]`, e
        # `combinations` sai ORDENADO: as 300 primeiras saidas comecam todas pelas cartas mais
        # baixas do baralho. O oraculo virou "equity quando o board sempre empareja baixo" e
        # acusou o amostrador de desviar 0,17 -- **o defeito estava no medidor**, que e o erro
        # mais caro que este projeto ja cometeu. Semente fixa para o teste nao piscar.
        import random as _r
        todas = list(combinations(livres, 2))
        _r.Random(20260828).shuffle(todas)
        saidas = todas[:saidas_max] if saidas_max else todas
    w = t = n = 0
    for saida in saidas:
        usadas = set(saida)
        meu = forca(hero + list(saida) + board)
        for v in vilao:
            if v[0] in usadas or v[1] in usadas:
                continue
            dele = forca(list(v) + list(saida) + board)
            n += 1
            if meu > dele:
                w += 1
            elif meu == dele:
                t += 1
    return (w + t * 0.5) / n if n else None


def test_a_amostragem_do_flop_bate_com_a_conta_densa():
    """MEDE o erro em vez de confiar na fórmula do erro padrão.

    A versão original varria todas as saídas contra todos os combos e levava 8 a 10 SEGUNDOS por
    decisão de flop, o que é impossível para um acervo de milhares. A troca por amostragem
    conjunta do par (saída, mão do vilão) só se justifica se o número não se mexer -- e "não se
    mexer" é uma afirmação que precisa de número, não de confiança.
    """
    if not _tem_eval7():
        print('PULADO test_a_amostragem_do_flop_bate_com_a_conta_densa (sem eval7)')
        return
    from leaklab.equity_real import equity_flop_turn_vs_continuacao as eq

    casos = [
        (['As', 'Ks'], ['Qs', 'Js', '2d']),
        (['2c', '2d'], ['Ah', 'Kd', 'Qs']),
        (['Ah', 'Ad'], ['Ac', '7d', '2s']),
        (['7h', '6h'], ['Kd', 'Qc', '2s']),
    ]
    piores = []
    for hero, board in casos:
        amostrado = eq(hero, board)
        # 1.000 saídas, e não 300. Com 300 o ORÁCULO tinha ruído próprio de ~0,02 e o teste
        # passava com limite de 0,02 medindo o ruído do medidor, não o erro do amostrador.
        # Contra 1.200 saídas o erro real é 0,0002 a 0,0036, então o limite abaixo mede mesmo.
        denso = _densa(hero, board, saidas_max=1000)
        assert amostrado is not None and denso is not None
        piores.append((abs(amostrado - denso), hero, board, amostrado, denso))
    erro, hero, board, a, d = max(piores)
    assert erro <= 0.008, (
        'amostragem desviou %.4f da conta densa em %s / %s (%.4f vs %.4f). O erro medido em '
        '28/08 era 0,0036 no pior caso; acima de 0,008 alguma coisa mudou no amostrador.'
        % (erro, hero, board, a, d))
    print('OK  test_a_amostragem_do_flop_bate_com_a_conta_densa (pior erro %.4f)' % erro)


def test_o_turn_ENUMERA_e_nao_amostra():
    """No turn falta uma carta só: a conta é fechada e não tem por que ter erro.

    O guarda ancora na CONDIÇÃO (o resultado é idêntico à enumeração completa) e não no tempo de
    execução, que varia com a máquina.
    """
    if not _tem_eval7():
        print('PULADO test_o_turn_ENUMERA_e_nao_amostra (sem eval7)')
        return
    from leaklab.equity_real import equity_flop_turn_vs_continuacao as eq
    hero, board = ['As', 'Ks'], ['Qs', 'Js', '2d', '7h']
    assert abs(eq(hero, board) - round(_densa(hero, board), 4)) < 1e-9, (
        'o turn divergiu da enumeração completa: virou amostragem sem ninguém pedir')
    print('OK  test_o_turn_ENUMERA_e_nao_amostra')


def test_o_numero_NAO_muda_entre_processos():
    """`hash()` de string é salgado por processo desde o PEP 456.

    Isto não é zelo teórico: em 27/08 a mesma decisão multiway saiu `small_mistake` com score
    0,19 num boot e `standard` com 0,0 no outro, sem nada entre eles além de um restart. Um Monte
    Carlo semeado com `hash()` faz exatamente isso, e é invisível olhando a tela.
    """
    if not _tem_eval7():
        print('PULADO test_o_numero_NAO_muda_entre_processos (sem eval7)')
        return
    codigo = (
        'import sys; sys.path.insert(0, %r);'
        'from leaklab.equity_real import equity_flop_turn_vs_continuacao as eq;'
        "print(eq(['As','Ks'], ['Qs','Js','2d']))"
        % os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    )
    vistos = set()
    for semente in ('0', '1', '12345'):
        env = dict(os.environ, PYTHONHASHSEED=semente)
        r = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, env=env)
        vistos.add((r.stdout or '').strip())
    assert len(vistos) == 1, (
        'a equity mudou entre processos com PYTHONHASHSEED diferente: %s. A semente do Monte '
        'Carlo voltou a depender de `hash()`.' % sorted(vistos))
    print('OK  test_o_numero_NAO_muda_entre_processos (%s em 3 processos)' % vistos.pop())


def test_o_projeto_CONTA_como_mao_que_continua():
    """`com_draws=True` é a diferença para o river, e some sem deixar rastro num refactor.

    No river não há carta por vir e projeto não existe. No flop e no turn um projeto de flush é uma
    mão que continua de verdade; excluí-la estreitaria a range do vilão para algo que ele não joga,
    e a equity do herói sairia INFLADA -- errando para o lado que acusa menos, que é o mais difícil
    de notar.
    """
    if not _tem_eval7():
        print('PULADO test_o_projeto_CONTA_como_mao_que_continua (sem eval7)')
        return
    import eval7
    from leaklab.range_de_continuacao import categoria_do_board, continua
    board = ['Qs', 'Js', '2d']
    bc = [eval7.Card(c) for c in board]
    cat = categoria_do_board(bc)
    projeto = (eval7.Card('9s'), eval7.Card('4s'))     # projeto de flush, sem par nenhum
    assert continua(projeto, bc, cat, com_draws=True), (
        'projeto de flush deixou de contar como mão que continua no flop')
    assert not continua(projeto, bc, cat, com_draws=False), (
        'o controle falhou: com_draws=False deveria excluir o projeto, senão o teste acima não '
        'prova nada')
    print('OK  test_o_projeto_CONTA_como_mao_que_continua')


def test_a_ordem_das_maos_faz_sentido_de_poker():
    """A afirmação pedagógica: trinca > par mínimo > nada. Se inverter, o motor passa a acusar o
    contrário do que o jogo faz, com cara de número medido."""
    if not _tem_eval7():
        print('PULADO test_a_ordem_das_maos_faz_sentido_de_poker (sem eval7)')
        return
    from leaklab.equity_real import equity_flop_turn_vs_continuacao as eq
    trinca = eq(['Ah', 'Ad'], ['Ac', '7d', '2s'])
    par    = eq(['2c', '2d'], ['Ah', 'Kd', 'Qs'])
    nada   = eq(['7h', '6h'], ['Kd', 'Qc', '2s'])
    assert trinca > par > nada, (
        'ordem sem sentido: trinca %.3f, par mínimo %.3f, nada %.3f' % (trinca, par, nada))
    assert trinca > 0.90, 'trinca de ases com %.3f contra quem continua' % trinca
    assert nada < 0.20, 'mão sem nada com %.3f contra quem continua' % nada
    print('OK  test_a_ordem_das_maos_faz_sentido_de_poker (%.2f > %.2f > %.2f)'
          % (trinca, par, nada))


def test_sem_condicao_de_afirmar_devolve_None():
    """Board de tamanho errado, mão incompleta ou range vazia não viram número chutado."""
    from leaklab.equity_real import equity_flop_turn_vs_continuacao as eq
    assert eq(['As', 'Ks'], ['Qs', 'Js']) is None, 'aceitou board de 2 cartas'
    assert eq(['As', 'Ks'], ['Qs', 'Js', '2d', '7h', '3c']) is None, 'aceitou board de river'
    assert eq(['As'], ['Qs', 'Js', '2d']) is None, 'aceitou mão de 1 carta'
    assert eq([], []) is None
    print('OK  test_sem_condicao_de_afirmar_devolve_None')


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
