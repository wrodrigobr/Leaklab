# -*- coding: utf-8 -*-
"""test_board_da_street_no_pool.py — nó solvado com o board errado não pode virar exercício.

**O defeito, medido em produção 2026-08-03:** 1.977 dos 5.030 nós servíveis pelo trainer pool
(39,3%) foram solvados com o board COMPLETO da mão. Um nó de `flop` cujo solve viu as cinco cartas
do river; um de `turn` que viu as cinco.

Todos nasceram antes de 2026-07-28, quando o enfileiramento passou a cortar o board pela street.
**Zero depois** — o código está certo, o estrago é legado.

**Por que ninguém tinha visto:** enquanto só o `lookup_gto` consultava esses nós eles eram
inofensivos, porque ele recalcula o hash a partir do board cortado e nunca os encontrava. O pool
passou a ler `gto_nodes` DIRETO, por SQL, e entrou pela porta que o hash fechava.

**E o corte de exibição escondia o resto:** a mesa desenhava 3 cartas no flop e 4 no turn, com
aparência perfeitamente correta, enquanto o veredito vinha de um solve que já conhecia o river. O
jogador decidia um flop e era corrigido por estratégia de river.

O CLAUDE.md registra a versão anterior deste mesmo bug e a regra que ela deixou: *"bug que some com
a resposta é honesto; conserto que a troca não é"*. Aqui não se re-chaveia nó nenhum — ele
simplesmente não é servível, e quem descobre isso é a SELEÇÃO.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.trainer_pool import _monta_spot
from leaklab.gto_utils import board_for_street

_ESPERADO = {'flop': 3, 'turn': 4, 'river': 5}


def _linha(street, board_solvado, **kw):
    """Uma linha como a consulta do pool a devolve. `board_solvado` é o que FOI ao solver."""
    base = {
        'spot_hash': 'h1',
        'street': street,
        'position': 'BTN',
        'board': json.dumps(sorted(board_solvado)),      # gto_nodes guarda ordenado
        'hero_hand': json.dumps(['Ah', 'Kd']),
        'stack_bucket': '20-35bb',
        'gto_action': 'call',
        'gto_freq': 0.6,
        'exploitability_pct': 1.5,
        'tree_hash': 't1',
        'actions': json.dumps(['fold', 'call', 'raise_50pct']),
        'spot_json': json.dumps({
            'board': board_solvado,
            'hero_hand': ['Ah', 'Kd'],
            'hero_stack_bb': 30.0,
            'effective_stack_bb': 30.0,
            'facing_size_bb': 2.0,
            'pot_bb': 6.0,
            '_meta': {'position': 'BTN', 'vs_position': 'CO'},
        }),
    }
    base.update(kw)
    return base


# ── o guarda prova que DETECTA ────────────────────────────────────────────────

def test_no_solvado_com_board_da_street_e_servido():
    """O contraponto, e ele vem primeiro: se tudo fosse rejeitado, os testes abaixo passariam
    medindo o vazio e o acervo teria ido a zero em silêncio."""
    for street, n in _ESPERADO.items():
        board = ['2c', '7d', 'Th', 'Js', 'Ad'][:n]
        spot = _monta_spot(_linha(street, board))
        assert spot is not None, f'{street} com {n} cartas foi rejeitado — o pool ficaria vazio'
        assert len(spot['board']) == n, f'{street}: mesa com {len(spot["board"])} cartas'
    print('OK  test_no_solvado_com_board_da_street_e_servido')


def test_no_solvado_com_board_MAIOR_e_recusado():
    """O caso de produção: `street=flop` com o solve tendo visto as cinco cartas."""
    casos = [
        ('flop', ['3h', 'Jh', 'Ac', 'As', '9h']),        # o do relato
        ('flop', ['3h', 'Jh', 'Ac', 'As']),
        ('turn', ['6s', '2s', 'Jc', 'Ac', '7c']),        # medido no acervo
    ]
    for street, board in casos:
        spot = _monta_spot(_linha(street, board))
        assert spot is None, (
            f'{street} solvado com {len(board)} cartas virou exercicio: a tela mostraria '
            f'{_ESPERADO[street]} cartas e o veredito viria do solve de {len(board)}')
    print('OK  test_no_solvado_com_board_MAIOR_e_recusado')


def test_a_mesa_NUNCA_mostra_menos_do_que_o_solve_viu():
    """A varredura que define o invariante inteiro, sem enumerar casos: para todo nó servido, o
    que o solver viu e o que a mesa desenha são o MESMO board.

    É o guarda que importa. Um teste que só cobrisse `flop` com 5 cartas deixaria `turn` livre —
    e turn era 697 dos 1.977 nós ruins."""
    cartas = ['2c', '7d', 'Th', 'Js', 'Ad']
    violacoes = []
    for street in _ESPERADO:
        for n in range(3, 6):
            board = cartas[:n]
            spot = _monta_spot(_linha(street, board))
            if spot is None:
                continue
            if list(spot['board']) != list(board):
                violacoes.append((street, board, spot['board']))
    assert not violacoes, f'mesa diferente do que o solver viu: {violacoes}'
    print('OK  test_a_mesa_NUNCA_mostra_menos_do_que_o_solve_viu')


def test_o_corte_de_exibicao_usa_a_FUNCAO_e_nao_uma_copia():
    """A regra de corte por street vivia copiada em cada chamador, e foi assim que o bug de
    2026-07-28 nasceu: dois lugares cortavam, o enfileiramento não. Esta era a QUINTA cópia."""
    import re
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'trainer_pool.py')
    with open(caminho, encoding='utf-8') as f:
        src = re.sub(r'#[^\n]*', '', f.read())          # fora comentários
    assert 'board_for_street' in src, 'o pool voltou a nao usar a funcao unica de corte'
    assert not re.search(r"\{\s*'flop'\s*:\s*3\s*,\s*'turn'\s*:\s*4", src), \
        'voltou a existir uma copia inline da tabela de cartas por street'
    print('OK  test_o_corte_de_exibicao_usa_a_FUNCAO_e_nao_uma_copia')


def test_board_for_street_corta_o_que_deve():
    """A função em si — se ela mentisse, todo o resto acima passaria medindo errado."""
    cinco = ['2c', '7d', 'Th', 'Js', 'Ad']
    assert board_for_street(cinco, 'flop') == cinco[:3]
    assert board_for_street(cinco, 'turn') == cinco[:4]
    assert board_for_street(cinco, 'river') == cinco
    assert board_for_street(cinco[:3], 'flop') == cinco[:3]     # já certo, não mexe
    assert board_for_street([], 'flop') == []
    print('OK  test_board_for_street_corta_o_que_deve')


def test_o_diagnostico_CONTA_os_descartados():
    """`contar_acervo` contava as linhas do SQL e teria reportado 5.030 servíveis quando 1.977
    eram inservíveis. Número tranquilizador é pior que número nenhum: encerra a pergunta."""
    import inspect
    from leaklab import trainer_pool
    src = inspect.getsource(trainer_pool.contar_acervo)
    assert '_monta_spot' in src, 'o diagnostico voltou a contar pelo SQL cru'
    assert '_descartados' in src, 'o diagnostico nao diz quantos nos caiu'
    print('OK  test_o_diagnostico_CONTA_os_descartados')


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
    raise SystemExit(1 if fail else 0)
