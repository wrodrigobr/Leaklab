# -*- coding: utf-8 -*-
"""Posicao de mesa pequena vira a posicao 9-max com os MESMOS jogadores atras.

── O caso (09/08) ─────────────────────────────────────────────────────────────────────────────

`_POS_NORM_BY_N` misturava duas filosofias. CO e BTN eram mapeados por JOGADORES ATRAS (certo);
UTG e HJ, por INDICE DE ACAO (errado). Numa mesa de 6 o HJ tem 4 jogadores atras — o equivalente
9-max e o HJ, que abre 29,3% a 40bb — mas a tabela mandava `'HJ': 'UTG+1'`, que abre 17,7%. Sao
11,6 pontos de range a menos e 17 tipos de mao que a carta equivalente abre 100% e a usada abre
0%. Abrir KTo do segundo assento 6-max, que qualquer regular faz, saia `gto_critical`
(`small_mistake`, score 0,181) com "GTO manda FOLD".

Pior: mesas de 3, 4 e 5 nao tinham entrada nenhuma e caiam no default 9-max. O 3o assento de uma
mesa de 5 (4 jogadores atras = HJ) recebia a carta de UTG 9-max: 15,7% contra os 29,3% que a
posicao pede.

── Por que o teste e por CONTA, e nao por tabela ──────────────────────────────────────────────

Uma tabela por tamanho de mesa e o que estava errado: mesa nova nasce sem entrada e ninguem
percebe. A regra virou uma conta (`n + 1 - indice`), e o teste varre TODOS os tamanhos de 2 a 10.
O oraculo e a propria ordem de acao que o pipeline usa para batizar o assento
(`leaklab.posicoes`), nao uma segunda copia escrita aqui.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.posicoes import nomes_de_posicao                       # noqa: E402
from leaklab.preflop_gto_ranges import _norm_pos, analyze_preflop   # noqa: E402

# Quantos agem DEPOIS de cada posicao na mesa cheia de 9 (blinds agem por ULTIMO preflop).
_ATRAS_9MAX = {'UTG': 8, 'UTG+1': 7, 'UTG+2': 6, 'LJ': 5, 'HJ': 4, 'CO': 3, 'BTN': 2,
               'SB': 1, 'BB': 0}


def test_todo_assento_de_toda_mesa_cai_na_carta_com_os_mesmos_jogadores_atras():
    """A varredura dos N (2..10) — a tabela estatica cobria 3 e errava em 3 deles."""
    ruins = []
    for n in range(2, 11):
        for vocab in ('LJ', 'MP1'):
            for i, nome in nomes_de_posicao(n, miolo=vocab).items():
                gw = _norm_pos(nome, n)
                if nome in ('SB', 'BB'):
                    if gw != nome:
                        ruins.append(f'n={n} {nome} -> {gw}')
                    continue
                atras_real = n + 1 - i          # (n-1-i) na mesa + os dois blinds
                atras_carta = _ATRAS_9MAX.get(gw)
                # 10-max UTG tem 9 atras, mais que o maximo da base (8) — a carta mais tight e o
                # unico teto honesto. Fora esse clamp, tem que bater exatamente.
                esperado = min(atras_real, 8)
                if atras_carta != esperado:
                    ruins.append(f'n={n} {nome} (atras={atras_real}) -> {gw} (atras={atras_carta})')
    assert not ruins, 'posicoes pareadas com a carta errada: ' + '; '.join(ruins)


def test_a_mesa_de_9_continua_sendo_identidade():
    """CONTROLE do conserto: se a conta nova mexesse na mesa cheia, ela estaria errada — o
    vocabulario 9-max do pipeline JA e o do GW. Este e o caso em que nada podia mudar."""
    for vocab in ('LJ', 'MP1'):
        for _i, nome in nomes_de_posicao(9, miolo=vocab).items():
            esperado = 'LJ' if nome == 'MP1' else nome
            assert _norm_pos(nome, 9) == esperado, f'{nome} 9-max virou {_norm_pos(nome, 9)}'


def test_o_segundo_assento_de_6max_abre_como_HJ_e_nao_como_UTG1():
    """O sintoma reportado, ponta a ponta pela porta unica."""
    for mao in ('KTo', 'JTo', 'A8o', 'QTo', '33'):
        seis = analyze_preflop(position='HJ', hero_hand_type=mao, stack_bb=40.0,
                               action_taken='raise', n_players=6)
        nove = analyze_preflop(position='HJ', hero_hand_type=mao, stack_bb=40.0,
                               action_taken='raise', n_players=9)
        assert seis['position'] == 'HJ', f'{mao}: carta usada = {seis["position"]}'
        assert seis['action_quality'] == nove['action_quality'] == 'correct', (mao, seis, nove)
        assert 'raise' in seis['recommended_actions'], (mao, seis['recommended_actions'])


def test_mesas_de_3_4_e_5_nao_caem_mais_no_default_9max():
    """O 3o assento de uma mesa de 5 tem 4 atras = HJ. Antes recebia a carta de UTG 9-max."""
    assert _norm_pos('UTG', 5) == 'HJ'
    assert _norm_pos('CO', 4) == 'CO' and _norm_pos('BTN', 4) == 'BTN'
    assert _norm_pos('BTN', 3) == 'BTN'
    r = analyze_preflop(position='UTG', hero_hand_type='KTo', stack_bb=40.0,
                        action_taken='raise', n_players=5)
    assert r['position'] == 'HJ' and r['action_quality'] == 'correct', r


def test_CONTROLE_a_carta_continua_ACUSANDO_lixo_na_posicao_certa():
    """Sem este controle, "tudo virou correct" passaria por conserto. 72o nao abre de lugar
    nenhum, em mesa de tamanho nenhum."""
    for n in (5, 6, 8, 9):
        pos = 'UTG' if n == 5 else ('HJ' if n in (6, 7) else 'UTG+1')
        r = analyze_preflop(position=pos, hero_hand_type='72o', stack_bb=40.0,
                            action_taken='raise', n_players=n)
        assert r['action_quality'] == 'major_leak', (n, pos, r['action_quality'])


def test_sem_n_players_o_nome_e_lido_como_dialeto_9max():
    """Comportamento CONHECIDO de quem chama sem o tamanho da mesa — nao um terceiro caminho."""
    assert _norm_pos('HJ') == 'HJ'
    assert _norm_pos('MP1') == 'LJ'
    assert _norm_pos('UTG1') == 'UTG+1'


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
