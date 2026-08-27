# -*- coding: utf-8 -*-
"""Em board PAREADO, quem só carrega o par do board não continua.

── O defeito que originou (27/08) ─────────────────────────────────────────────────────────

`multiway_advisor._continue_combos` decidia "mão feita" por `handtype(mão + board) != 'High
Card'`. Num board pareado isso é verdade para **toda** mão: o par do próprio board entra na
avaliação de 7 cartas. Medido sobre a mesma range base de 642 combos:

    board             pareado?    combos    %
    9s,Ah,8s          -              433   67%
    Kd,9c,4s          -              305   48%
    3c,3h,Qd          PAREADO        595   93%
    2h,2d,5s          PAREADO        607   95%

A range de continuação virava a range inteira — equity vs mão aleatória com nome de equity vs
range, inflando o herói exatamente onde o produto deveria ser mais cauteloso.

A metade CERTA existia desde 24/08 em `equity_river_vs_continuacao`, que compara com a categoria
do BOARD SOZINHO. Nunca foi compartilhada. Regra 5 do CLAUDE.md pela sexta vez.

── O que a ablação disse ──────────────────────────────────────────────────────────────────

1.112 decisões multiway pós-flop do acervo, 268 em board pareado, 264 ranges mudando de tamanho
(589 → 190, 569 → 161, 558 → 228). Vereditos que mudaram: **0 de 1.112**. Correção do número sem
mexer em acusação nenhuma — o mesmo desfecho do conserto do river.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _cards(txt):
    import eval7
    return [eval7.Card(c) for c in txt.split(',')]


def test_em_board_PAREADO_carregar_o_par_do_board_nao_continua():
    """O caso que originou. `7c2d` em `3c,3h,Qd` faz "par" só porque o board já é par."""
    from leaklab.range_de_continuacao import categoria_do_board, continua
    board = _cards('3c,3h,Qd')
    cat = categoria_do_board(board)
    assert cat == 'Pair', 'o board 3c,3h,Qd deveria ser categoria Pair, veio %r' % cat
    assert continua(_cards('7c,2d'), board, cat, com_draws=True) is False, (
        'lixo em board pareado voltou a "continuar" — a range de continuação vira a range '
        'inteira e a equity vs range vira equity vs aleatória')
    print('OK  test_em_board_PAREADO_carregar_o_par_do_board_nao_continua')


def test_no_MESMO_board_pareado_quem_usa_as_proprias_cartas_continua():
    """CONTRAPROVA. Um critério que só dissesse "não" passaria no teste acima e destruiria a
    range: sem ninguém continuando, o Monte Carlo não tem contra quem rodar."""
    from leaklab.range_de_continuacao import categoria_do_board, continua
    board = _cards('3c,3h,Qd')
    cat = categoria_do_board(board)
    assert continua(_cards('Qs,9d'), board, cat) is True, 'quem pareia o Q não continua?'
    assert continua(_cards('3d,8c'), board, cat) is True, 'trinca de 3 não continua?'
    assert continua(_cards('Ks,Kd'), board, cat) is True, 'par de bolso não continua?'
    print('OK  test_no_MESMO_board_pareado_quem_usa_as_proprias_cartas_continua')


def test_board_SECO_nao_foi_afetado():
    """O conserto é do board pareado. Se ele mexesse no seco, seria outra mudança, não medida."""
    from leaklab.range_de_continuacao import categoria_do_board, continua
    board = _cards('Kd,9c,4s')
    cat = categoria_do_board(board)
    assert cat == 'High Card'
    assert continua(_cards('Ks,2d'), board, cat) is True     # par de K
    assert continua(_cards('7c,2d'), board, cat) is False    # lixo
    print('OK  test_board_SECO_nao_foi_afetado')


def test_DRAW_continua_e_no_river_nao_existe_draw():
    """`com_draws` é a única diferença entre as duas portas, e ela precisa valer nos dois lados:
    no flop um projeto continua; no river não há carta por vir e projeto não é argumento."""
    from leaklab.range_de_continuacao import categoria_do_board, continua
    # board pareado COM duas do mesmo naipe, e uma mão que não pareia nada: só o projeto a
    # sustenta. `JhTh` em `3c,3h,Qd` era a minha primeira escolha e `detect_draws` diz que ali
    # não há projeto nenhum — o teste falhou e estava certo.
    board = _cards('3c,3h,Qh')
    cat = categoria_do_board(board)
    mao = _cards('9h,8h')            # flush draw, sem par próprio
    assert continua(mao, board, cat, com_draws=True) is True, 'projeto parou de continuar'
    assert continua(mao, board, cat, com_draws=False) is False, (
        'com `com_draws=False` um projeto ainda continua — no river isso conta mão que não '
        'existe mais')
    print('OK  test_DRAW_continua_e_no_river_nao_existe_draw')


def test_o_filtro_APERTA_de_verdade_em_board_pareado():
    """O número, não a intenção. Sem esta asserção o teste passaria com um filtro que aceita
    90% da range — que era exatamente o defeito."""
    import eval7
    from leaklab.multiway_advisor import _continue_combos, _BASE_RANGE
    base = len(eval7.HandRange(_BASE_RANGE).hands)
    pareado = len(_continue_combos('3c,3h,Qd'))
    seco = len(_continue_combos('Kd,9c,4s'))
    assert pareado / base < 0.60, (
        'board pareado voltou a deixar passar %d de %d (%.0f%%) — o filtro está desligado'
        % (pareado, base, 100.0 * pareado / base))
    assert 0.20 < seco / base < 0.80, (
        'board seco fora da faixa esperada: %d de %d' % (seco, base))
    print('OK  test_o_filtro_APERTA_de_verdade_em_board_pareado (pareado %d, seco %d de %d)'
          % (pareado, seco, base))


def test_as_DUAS_portas_usam_a_MESMA_fonte():
    """Regra 5 com varredura N+1. O critério viveu meses em duas cópias, uma certa e uma errada,
    e só a errada recebia board pareado."""
    base = os.path.join(os.path.dirname(__file__), '..', 'leaklab')
    n = 0
    for arq in ('multiway_advisor.py', 'equity_real.py'):
        with open(os.path.join(base, arq), encoding='utf-8') as fh:
            codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
        n += codigo.count('range_de_continuacao')
        # Duas correções que este guarda levou, as duas por ele acusar o inocente:
        #   1. varria o ARQUIVO e pegava `_realization_tax`, que usa `'High Card'` por outro
        #      motivo, legítimo;
        #   2. varria a função e pegava a própria DOCSTRING dela, que cita o defeito.
        # Por isso a âncora agora é a forma EXECUTÁVEL do código antigo, que nenhum texto tem.
        if arq == 'multiway_advisor.py':
            i = codigo.index('def _continue_combos(')
            corpo = codigo[i:codigo.index('def ', i + 10)]
            assert 'handtype(eval7.evaluate(' not in corpo, (
                '`_continue_combos` voltou a avaliar a mão de 7 cartas para decidir '
                'continuação — é o teste que dizia sim para toda mão em board pareado')
            assert 'continua(' in corpo, (
                '`_continue_combos` parou de chamar o critério compartilhado')
    assert n >= 2, 'as duas portas deixaram de compartilhar o critério: %d de 2' % n
    print('OK  test_as_DUAS_portas_usam_a_MESMA_fonte')


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
