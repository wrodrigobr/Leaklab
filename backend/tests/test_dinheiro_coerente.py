# -*- coding: utf-8 -*-
"""test_dinheiro_coerente.py — o produto não pode pedir decisão contra dinheiro impossível.

**Reportado pelo usuário, olhando a tela:** *"aposta de 0.1bb?"* — o treino serviu uma decisão
contra uma aposta de 0,1bb num pote de 4,1bb, 2,4% do pote. Medindo o acervo depois disso, o outro
extremo era pior: **116.000% do pote**.

Nenhum dos dois é jogada. É erro de UNIDADE: `spot.potSize` do pipeline vem em FICHAS e
`decisions.pot_size` já está em BB — dois campos com o mesmo nome e escalas diferentes, a mesma
armadilha do `facingSize` × `facingToBb` que este projeto já pagou três vezes.

**O que a medição mostrou, e que corrigiu a hipótese inicial:** eu apostei no fallback
`_level_bb = float(d.get('level_bb') or 1) or 1`, que faria valor em fichas ser lido como BB quando
o nível faltasse. **Refutado:** zero decisions têm `level_bb` nulo, zero ou 1 — o fallback nunca
dispara. As linhas ruins são legado, e o enfileiramento de hoje converte certo.

**E 13 delas foram reenfileiradas HOJE, pelo meu próprio script de recuperação**, que copiava o
payload e só trocava o board. Copiar sem olhar transforma defeito legado em defeito de hoje. Por
isso o guarda é uma função só, usada por quem SERVE e por quem ENFILEIRA: a procedência do dado
não pode ser critério de confiança.

**As regras são de impossibilidade ESTRUTURAL, não de julgamento estratégico** — e o teste
`test_shove_legitimo_nao_e_rejeitado` existe para provar isso. Medido: as quatro regras reprovam
6,3% do acervo e preservam os 28 shoves legítimos.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.gto_utils import dinheiro_coerente


def _ok(*a):
    return dinheiro_coerente(*a)[0]


def test_spot_normal_passa():
    """O contraponto, e vem primeiro: se tudo fosse reprovado, os testes abaixo passariam com o
    acervo em zero e ninguém notaria."""
    casos = [
        (4.0, 2.0, 30.0),      # meio pote
        (6.0, 3.0, 25.0),
        (12.0, 12.0, 40.0),    # pote inteiro
        (8.0, 0.0, 20.0),      # ninguém apostou
        (2.5, 1.2, 15.0),
    ]
    for pot, fac, stack in casos:
        ok, motivo = dinheiro_coerente(pot, fac, stack)
        assert ok, f'spot normal reprovado (pote {pot}, aposta {fac}, stack {stack}): {motivo}'
    print('OK  test_spot_normal_passa')


def test_shove_legitimo_nao_e_rejeitado():
    """**O teste que impede o conserto de causar dano que o bug não causava.**

    Um shove de 28bb num pote de 4bb é 700% do pote e é perfeitamente real — acontece toda vez que
    alguém empurra o stack curto. Uma regra escrita como "aposta > 3x o pote é absurda" mataria
    exatamente os spots mais instrutivos do acervo.
    """
    casos = [
        (4.0, 28.0, 30.0),     # 700% do pote, dentro do stack
        (2.0, 20.0, 20.0),     # 1000% do pote, all-in exato
        (3.0, 33.0, 35.0),
    ]
    for pot, fac, stack in casos:
        ok, motivo = dinheiro_coerente(pot, fac, stack)
        assert ok, f'shove legitimo rejeitado (pote {pot}, shove {fac}, stack {stack}): {motivo}'
    print('OK  test_shove_legitimo_nao_e_rejeitado')


def test_o_caso_do_relato_e_recusado():
    """A aposta de 0,08bb que o usuário viu na tela."""
    ok, motivo = dinheiro_coerente(4.08, 0.08, 28.5)
    assert not ok, 'a aposta de 0,08bb passou'
    assert motivo == 'aposta_menor_que_meio_blind', motivo
    print('OK  test_o_caso_do_relato_e_recusado')


def test_pote_menor_que_os_blinds_e_recusado():
    """O pote pós-flop carrega os blinds do preflop: abaixo de 1bb é erro de unidade, não mesa."""
    for pot in (0.01, 0.02, 0.04, 0.4, 0.99):
        ok, motivo = dinheiro_coerente(pot, 2.0, 33.0)
        assert not ok, f'pote de {pot}bb passou'
        assert motivo == 'pote_menor_que_os_blinds', (pot, motivo)
    print('OK  test_pote_menor_que_os_blinds_e_recusado')


def test_pote_maior_que_a_mesa_inteira_e_recusado():
    """Os dois extremos medidos no acervo: pote de 36.177bb e 91.117bb com stack de ~13bb. Nem
    todos os jogadores all-in chegam perto disso."""
    for pot, stack in ((91117.0, 12.6), (36177.0, 16.7), (1000.0, 20.0)):
        ok, motivo = dinheiro_coerente(pot, 4.0, stack)
        assert not ok, f'pote de {pot}bb com stack {stack}bb passou'
        assert motivo == 'pote_maior_que_a_mesa_inteira', (pot, motivo)
    print('OK  test_pote_maior_que_a_mesa_inteira_e_recusado')


def test_aposta_maior_que_o_stack_e_recusada():
    """Enfrentar aposta de 3x o seu stack não muda nada — o efetivo é o seu. Acima disso é
    unidade errada, não pressão."""
    ok, motivo = dinheiro_coerente(10.0, 200.0, 20.0)
    assert not ok and motivo == 'aposta_maior_que_o_stack', motivo
    # e a borda: exatamente o stack continua valendo (all-in de quem cobre)
    assert _ok(10.0, 20.0, 20.0), 'all-in exato foi rejeitado'
    print('OK  test_aposta_maior_que_o_stack_e_recusada')


def test_sem_stack_conhecido_nao_inventa_reprovacao():
    """Stack ausente é DESCONHECIDO. As regras que dependem dele ficam de fora; as que não
    dependem seguem valendo. Reprovar por falta de dado seria punir o spot pelo que não se sabe."""
    assert _ok(6.0, 3.0, 0), 'spot são reprovado por stack ausente'
    assert _ok(6.0, 999.0, 0), 'regra de stack aplicada sem stack'
    assert not _ok(0.02, 3.0, 0), 'a regra do pote independe do stack e deveria valer'
    print('OK  test_sem_stack_conhecido_nao_inventa_reprovacao')


def test_entrada_estranha_nao_levanta():
    """Está no caminho quente da seleção: levantar aqui derrubaria o treino inteiro."""
    for a in ((None, None, None), ('x', 2, 30), (4.0, 'y', 30), ([], {}, ())):
        ok, motivo = dinheiro_coerente(*a)
        assert isinstance(ok, bool), a
    print('OK  test_entrada_estranha_nao_levanta')


def test_o_motivo_e_devolvido_e_nao_so_um_booleano():
    """Acervo que encolhe sem dizer por quê vira mistério: quem conta descartados precisa saber
    de qual defeito está falando."""
    _, m = dinheiro_coerente(0.01, 2.0, 30.0)
    assert m and isinstance(m, str) and ' ' not in m, m
    ok, m2 = dinheiro_coerente(6.0, 3.0, 30.0)
    assert ok and m2 is None, 'spot bom devolveu motivo'
    print('OK  test_o_motivo_e_devolvido_e_nao_so_um_booleano')


def test_o_pool_e_o_script_usam_a_MESMA_funcao():
    """A regra em dois lugares vira duas regras, e uma delas envelhece. Aqui isso teria custado
    caro: o pool filtra na hora de servir, mas foi o SCRIPT que reenfileirou os 13 ruins."""
    import re
    raiz = os.path.join(os.path.dirname(__file__), '..')
    for caminho in (os.path.join(raiz, 'leaklab', 'trainer_pool.py'),
                    os.path.join(raiz, 'scripts', 'reenfileirar_board_da_street.py')):
        with open(caminho, encoding='utf-8') as f:
            src = re.sub(r'#[^\n]*', '', f.read())
        assert 'dinheiro_coerente' in src, f'{os.path.basename(caminho)} nao usa a funcao unica'
    print('OK  test_o_pool_e_o_script_usam_a_MESMA_funcao')


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
