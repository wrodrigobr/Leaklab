"""test_nota_da_mao_postflop.py — o texto didático não pode contradizer o board na tela.

**Reportado pelo usuário, com print:** flop `K♣ 9♣ 3♠`, herói no BB com `2♦ 3♦` — par do 3 — e o
feedback dizia *"conector suited quase nunca acerta na hora, ele vive de implied odds"*.

A nota era escolhida SÓ por `hand_class`, que olha o hand type e nada mais. E a tabela `_HAND_NOTES`
inteira é escrita em linguagem de preflop: "quase nunca acerta na hora", "erra o flop e fica sem
plano", "precisa acertar muito pra valer alguma coisa". Todas pressupõem que o flop não veio.

**Por que isso é pior que um texto feio:** o jogador confia. Ele veio aprender, está vendo um par
no board, e o produto afirma que a mão não acertou. O veredito de GTO do mesmo print estava CERTO
(conferido no dado: 2d3d e 2h3h com estratégia idêntica, exploitability 1,44%) — quem mentia era a
camada didática.

O guarda principal aqui é o `test_nenhuma_frase_de_preflop_escapa_no_postflop`: ele varre a tabela
de preflop INTEIRA contra spots de pós-flop. Guarda que testasse só o caso do print deixaria as
outras nove frases livres para reaparecer.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.progression import (concept_for_spot, _mao_no_board, _HAND_NOTES, _NOTAS_POSTFLOP)


def _spot(**kw):
    base = {'scenario': 'postflop', 'position': 'BB', 'vs_position': 'UTG', 'stack_bb': 30.0,
            'street': 'flop', 'board': ['3s', '9c', 'Kc'], 'hand': '2d3d'}
    base.update(kw)
    return base


# ── o caso do relato ──────────────────────────────────────────────────────────

def test_o_caso_exato_do_relato():
    """Board K93, herói com 32s: a mão TEM par do 3. O texto não pode dizer que ela não acertou."""
    c = concept_for_spot(_spot())
    nota = c.get('nota_mao') or ''
    assert 'implied odds' not in nota, f'a nota de preflop sobreviveu no flop: {nota!r}'
    assert 'quase nunca acerta' not in nota, nota
    assert c.get('classe') == 'par_baixo', f'a mão foi classificada como {c.get("classe")!r}'
    print('OK  test_o_caso_exato_do_relato')


def test_nenhuma_frase_de_preflop_escapa_no_postflop():
    """A varredura que importa: NENHUMA das frases de preflop pode sair em spot de pós-flop,
    em nenhuma street, com nenhuma mão."""
    maos = ['2d3d', 'AhKh', '7c7d', 'KdQc', '9h9s', 'Ac2d', 'JsTs', '5c4c', 'QdQh', '8h2c']
    boards = [['3s', '9c', 'Kc'], ['As', 'Kd', '2h'], ['7h', '7d', 'Qc'],
              ['3s', '9c', 'Kc', '4d'], ['3s', '9c', 'Kc', '4d', 'Jh']]
    frases = {v for v in _HAND_NOTES.values() if v}
    vazou = []
    for street in ('flop', 'turn', 'river'):
        for m in maos:
            for b in boards:
                nota = (concept_for_spot(_spot(street=street, hand=m, board=b)) or {}).get('nota_mao') or ''
                if nota in frases:
                    vazou.append((street, m, ''.join(b), nota[:40]))
    assert not vazou, f'{len(vazou)} spots de pós-flop receberam frase de preflop: {vazou[:3]}'
    print(f'OK  test_nenhuma_frase_de_preflop_escapa_no_postflop ({len(maos)*len(boards)*3} spots varridos)')


def test_o_preflop_continua_com_a_nota_de_preflop():
    """O contraponto. Se eu tivesse simplesmente apagado a nota, o teste acima passaria e o
    produto teria perdido a camada inteira sem ninguém notar."""
    c = concept_for_spot({'scenario': 'rfi', 'position': 'UTG', 'stack_bb': 50.0,
                          'street': 'preflop', 'hand': '54s'})
    assert (c.get('nota_mao') or '') in _HAND_NOTES.values(), \
        f'o preflop perdeu a nota da família de mão: {c.get("nota_mao")!r}'
    assert c.get('nota_mao'), 'nota vazia no preflop'
    print('OK  test_o_preflop_continua_com_a_nota_de_preflop')


def test_postflop_recebe_nota_de_verdade_e_nao_so_silencio():
    """Sem isto, suprimir tudo passaria como conserto. A nota tem que EXISTIR nos casos claros."""
    casos = [('2d3d', ['3s', '9c', 'Kc'], 'par_baixo'),
             ('Kh2c', ['3s', '9c', 'Kc'], 'top_par'),
             ('9d9h', ['3s', '9c', 'Kc'], 'set'),
             ('AdAc', ['3s', '9c', '2h'], 'overpar'),
             ('KdQc', ['3s', '9c', 'Kc'], 'top_par'),
             ('AhQd', ['3s', '9c', '2h'], 'duas_over')]
    for mao, board, esperado in casos:
        c = concept_for_spot(_spot(hand=mao, board=board))
        assert c.get('classe') == esperado, f'{mao} em {board}: veio {c.get("classe")!r}, esperado {esperado!r}'
        assert c.get('nota_mao'), f'{mao} em {board} ficou sem nota nenhuma'
        assert c['nota_mao'] == _NOTAS_POSTFLOP[esperado]
    print('OK  test_postflop_recebe_nota_de_verdade_e_nao_so_silencio')


# ── a classificação em si ─────────────────────────────────────────────────────

def test_classifica_o_que_e_certo():
    casos = [
        (['2d', '3d'], ['3s', '9c', 'Kc'], 'par_baixo'),
        (['9d', '2c'], ['3s', '9c', 'Kc'], 'par_medio'),
        (['Kd', '2c'], ['3s', '9c', 'Kc'], 'top_par'),
        (['Kd', '9h'], ['3s', '9c', 'Kc'], 'dois_pares'),
        (['9d', '9h'], ['3s', '9c', 'Kc'], 'set'),
        (['Ad', 'Ac'], ['3s', '9c', '2h'], 'overpar'),
        (['5d', '5c'], ['3s', '9c', 'Kc'], 'par_na_mao'),
        (['Ad', 'Qc'], ['3s', '9c', '2h'], 'duas_over'),
        (['7d', '5c'], ['3s', '9c', 'Kc'], 'sem_par'),
        (['Kd', '2c'], ['Ks', 'Kh', '9c'], 'trinca'),
    ]
    for mao, board, esperado in casos:
        got = _mao_no_board(mao, board)
        assert got == esperado, f'{mao} em {board}: {got!r} != {esperado!r}'
    print('OK  test_classifica_o_que_e_certo')


def test_se_CALA_quando_nao_tem_certeza():
    """A regra do bloco: straight, flush e entrada estranha devolvem `None`. Chamar de "par baixo"
    uma mão que fechou flush seria a afirmação confiante e falsa que isto existe pra evitar."""
    mudos = [
        (['2d', '3d'], ['4d', '5d', 'Kd']),      # flush
        (['2d', '3c'], ['4s', '5h', '6c']),      # straight 2-6
        (['6d', '7c'], ['3s', '4h', '5c']),      # straight 3-7
        (['Ad', '2c'], ['3s', '4h', '5c']),      # straight com ás baixo
        (['2d', '3d'], ['3s', '9c']),            # board incompleto
        (['2d'], ['3s', '9c', 'Kc']),            # mão incompleta
        ('lixo', ['3s', '9c', 'Kc']),            # entrada que não é mão
        (['Zz', '3d'], ['3s', '9c', 'Kc']),      # rank inexistente
    ]
    for mao, board in mudos:
        got = _mao_no_board(mao, board)
        assert got is None, f'{mao} em {board} deveria ser None, veio {got!r}'
    print('OK  test_se_CALA_quando_nao_tem_certeza')


def test_mao_muda_de_classe_quando_o_board_cresce():
    """Turn e river são a mesma função; a nota tem que acompanhar o board, não a mão."""
    assert _mao_no_board(['2d', '3d'], ['3s', '9c', 'Kc']) == 'par_baixo'
    assert _mao_no_board(['2d', '3d'], ['3s', '9c', 'Kc', '2h']) == 'dois_pares'
    assert _mao_no_board(['2d', '3d'], ['3s', '9c', 'Kc', '2h', '3c']) == 'trinca'
    print('OK  test_mao_muda_de_classe_quando_o_board_cresce')


def test_toda_classe_tem_nota():
    """Classe sem nota vira silêncio invisível: o código acha que ensinou e não ensinou."""
    faltam = []
    for mao, board in [(['2d', '3d'], ['3s', '9c', 'Kc']), (['9d', '2c'], ['3s', '9c', 'Kc']),
                       (['Kd', '2c'], ['3s', '9c', 'Kc']), (['Kd', '9h'], ['3s', '9c', 'Kc']),
                       (['9d', '9h'], ['3s', '9c', 'Kc']), (['Ad', 'Ac'], ['3s', '9c', '2h']),
                       (['5d', '5c'], ['3s', '9c', 'Kc']), (['Ad', 'Qc'], ['3s', '9c', '2h']),
                       (['7d', '5c'], ['3s', '9c', 'Kc']), (['Kd', '2c'], ['Ks', 'Kh', '9c'])]:
        k = _mao_no_board(mao, board)
        if k and not _NOTAS_POSTFLOP.get(k):
            faltam.append(k)
    assert not faltam, f'classes sem nota: {set(faltam)}'
    print('OK  test_toda_classe_tem_nota')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
