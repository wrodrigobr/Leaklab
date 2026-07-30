# -*- coding: utf-8 -*-
"""
Nome da posicao por assento — a mesma regra nos DOIS caminhos que a usam.

── O bug reportado ────────────────────────────────────────────────────────────────────────────────

Usuario, numa mao heads-up da ACR: "no torneio acr as blinds nao estao sendo exibidas".

Medido no payload real de producao (torneio 35598158, mao 2789068082, MusashiBR no botao):

    posicoes servidas:  {seat 4: 'SB', seat 3: 'BTN'}
    posicoes corretas:  {seat 3: 'SB', seat 4: 'BB'}     (heads-up: o botao E o small blind)

O rotulo BB simplesmente NAO EXISTIA, e o 'SB' aparecia sobre quem havia postado a big blind. Na
mesa isso se le exatamente como "as blinds nao estao sendo exibidas".

── A causa, e ela e reincidente ───────────────────────────────────────────────────────────────────

A regra vivia em DUAS copias. `hand_state_builder._position_names` tinha o caso de heads-up. A
copia do `_build_replay_data` nao tinha, e o comentario dela afirmava ser "a mesma derivacao do
engine (_infer_position) e do builder". Comentario nao e evidencia.

O mecanismo: com n=2 o dict literal `{0:'SB', 1:'BB', n-1:'BTN'}` tem `n-1 == 1`, entao a chave 1
e escrita duas vezes e 'BTN' sobrescreve 'BB'.

── O que este arquivo trava ───────────────────────────────────────────────────────────────────────

Que os dois caminhos concordem em TODO tamanho de mesa (2 a 9), com uma unica divergencia
declarada: o nome do miolo em 9-max ('LJ' no replay, para casar com o Decision Card e o GTO
Solver; 'MP1' no builder, historico). Divergencia declarada em teste e decisao; divergencia
silenciosa e o bug.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.posicoes import nomes_de_posicao
from leaklab.hand_state_builder import _position_names


def test_heads_up_o_botao_e_o_small_blind():
    """O caso do usuario. Indice 1 = botao (o chamador poe o botao por ultimo)."""
    assert nomes_de_posicao(2) == {0: 'BB', 1: 'SB'}


def test_heads_up_tem_os_DOIS_rotulos_de_blind():
    """O sintoma exato: o 'BB' desaparecia porque 'BTN' sobrescrevia a mesma chave."""
    v = set(nomes_de_posicao(2).values())
    assert v == {'SB', 'BB'}, v
    assert 'BB' in v, 'o rotulo da big blind desapareceu — e o bug reportado'


def test_os_dois_caminhos_concordam_de_2_a_9():
    """Rule do projeto: regra em N lugares vira funcao, com teste que varre os N+1.

    A unica divergencia permitida e o nome do miolo em 9-max, e ela e declarada.
    """
    divergencias = {}
    for n in range(2, 10):
        r = nomes_de_posicao(n, miolo='LJ')
        b = _position_names(n)
        assert set(r.keys()) == set(b.keys()) == set(range(n)), n
        dif = {k: (r[k], b[k]) for k in r if r[k] != b[k]}
        if dif:
            divergencias[n] = dif
    assert divergencias == {9: {5: ('LJ', 'MP1')}}, divergencias


def test_blinds_e_botao_em_todo_tamanho_de_mesa():
    """SB age primeiro pos-flop, BB e o ultimo a agir preflop, botao age por ultimo pos-flop.
    Em heads-up SB e botao sao a MESMA pessoa, e e so por isso que o 'BTN' nao aparece la."""
    for n in range(3, 10):
        p = nomes_de_posicao(n)
        assert p[0] == 'SB' and p[1] == 'BB' and p[n - 1] == 'BTN', (n, p)
    hu = nomes_de_posicao(2)
    assert 'BTN' not in hu.values(), hu   # o botao e rotulado SB; a ficha de dealer vem do `button`


def test_nomes_sao_unicos_em_toda_mesa():
    """Duas pessoas com a mesma posicao quebraria lookup de range e o rotulo da mesa. Era
    exatamente o que acontecia em heads-up, pela via da chave sobrescrita."""
    for n in range(2, 10):
        for miolo in ('LJ', 'MP1'):
            p = nomes_de_posicao(n, miolo=miolo)
            assert len(set(p.values())) == n, (n, miolo, p)


def test_mesa_de_um_e_vazia_nao_estouram():
    assert nomes_de_posicao(1) == {0: 'BTN'}
    assert nomes_de_posicao(0) == {}


# ── O payload real, ponta a ponta ──────────────────────────────────────────────────────────────

def test_payload_real_de_heads_up_da_ACR():
    """Reproduz a derivacao do `_build_replay_data` com os dados reais da mao reportada:
    2 assentos (3 e 4), botao no assento 3. Antes: {4:'SB', 3:'BTN'}. Agora: {3:'SB', 4:'BB'}."""
    seat_nums = [3, 4]
    button_seat = 3
    n = len(seat_nums)
    btn_idx = seat_nums.index(button_seat)
    ordered = [seat_nums[(btn_idx + 1 + k) % n] for k in range(n)]   # [nao-botao, botao]
    pn = nomes_de_posicao(n, miolo='LJ')
    positions = {ordered[k]: pn[k] for k in range(n)}
    assert positions == {3: 'SB', 4: 'BB'}, positions


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
