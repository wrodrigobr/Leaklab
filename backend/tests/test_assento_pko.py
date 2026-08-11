# -*- coding: utf-8 -*-
"""O bounty do PKO mora DENTRO do parentese do assento, e isso zerava a mesa inteira.

── O que aconteceu ────────────────────────────────────────────────────────────────────────────

    Seat 1: jojosetubal (7835 in chips)                       <- casava
    Seat 1: speedyman393 (5469 in chips, $1.50 bounty)        <- NAO casava

O regex exigia o ")" logo depois de "in chips". Nos 11 torneios PKO do acervo isso deu
`num_players = 0` em **2.355 decisoes, 24% do total**. E mesa de zero jogadores nao e um numero
feio numa coluna: `_detect_icm_pressure` cai no `if active_players <= 3: return 'high'` ANTES de
olhar o M, e `_ICM_EXCLUDED='high'` remove a linha do ranking de leaks e do plano de estudo.
**85 acusacoes sumiam em silencio** — o tipo de defeito que nao aparece na tela, some dela.

O mesmo texto quebrava uma SEGUNDA leitura, `_extract_all_stacks`, que alimenta o ICM real. Duas
implementacoes da mesma regra, as duas cegas ao mesmo dialeto. Hoje ha uma so:
`mesa_final.assentos_com_stack`.

── O oraculo ──────────────────────────────────────────────────────────────────────────────────

Nao foi preciso re-derivar nada: 972 das 2.355 decisoes tinham posicao HJ, MP1 ou UTG+2, que
`posicoes.py` so emite com 6 ou 7 assentos. A linha se contradizia sozinha. Esse par
(num_players, position) e o que o ultimo teste daqui verifica.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.mesa_final import assentos_com_stack, nomes_sentados
from leaklab.mtt_context import _extract_all_stacks

RAIZ = os.path.join(os.path.dirname(__file__), '..')

#: Linhas reais, uma por dialeto. As duas de PKO sao copiadas do raw_text de producao.
DIALETOS = [
    ('PS',           'Seat 1: jojosetubal (7835 in chips)',                     'jojosetubal', 7835),
    ('PS PKO',       'Seat 1: speedyman393 (5469 in chips, $1.50 bounty) ',     'speedyman393', 5469),
    ('GG PKO',       'Seat 3: phpro (1500 in chips, bounty $0.25)',             'phpro', 1500),
    ('PS PKO fora',  'Seat 3: phpro (1500 in chips) bounty $0.25',              'phpro', 1500),
    ('ACR',          'Seat 1: nome sobrenome (29150.00)',                       'nome sobrenome', 29150.0),
    ('888',          'Seat 1: fulano ( $3,548 )',                               'fulano', 3548),
    ('CoinPoker',    'Seat 2: ciclano (10,000 in chips)',                       'ciclano', 10000),
    ('out of hand',  'Seat 1: rafaela919 (1500 in chips) out of hand (moved)',  'rafaela919', 1500),
    ('sitting out',  'Seat 4: beltrano (29150.00) is sitting out',              'beltrano', 29150.0),
]


def _mao(*linhas):
    return 'PokerStars Hand #1: Tournament\n' + '\n'.join(linhas) + '\n'


def test_todo_dialeto_e_lido_com_nome_e_stack():
    for rot, linha, nome, fichas in DIALETOS:
        lidos = assentos_com_stack(_mao(linha))
        assert lidos == [(nome, float(fichas))], f'{rot}: {lidos}'
    print(f'OK  test_todo_dialeto_e_lido_com_nome_e_stack ({len(DIALETOS)} dialetos)')


def test_a_mao_PKO_INTEIRA_conta_a_mesa_certa():
    """O caso de producao: 7 assentos com bounty. Antes do conserto, zero."""
    mao = _mao(*[f'Seat {i}: jogador{i} ({1000 + i} in chips, $1.50 bounty) ' for i in range(1, 8)])
    assert len(nomes_sentados(mao)) == 7, sorted(nomes_sentados(mao))
    stacks, hero_idx = _extract_all_stacks(mao, 'jogador3')
    assert len(stacks) == 7, stacks
    assert hero_idx == 2, hero_idx
    assert stacks[hero_idx] == 1003.0
    print('OK  test_a_mao_PKO_INTEIRA_conta_a_mesa_certa')


def test_o_SUMMARY_continua_fora_da_contagem():
    """CONTROLE estrutural. As linhas de summary tambem comecam com 'Seat N:' e trazem um numero
    entre parenteses — mas ele e o valor COLETADO, nao o stack. O regex casa nelas de proposito
    (ver o comentario de `_ASSENTO_RE`); quem as exclui e o corte por bloco."""
    mao = ('PokerStars Hand #1: Tournament\n'
           'Seat 1: alfa (1000 in chips, $1.50 bounty)\n'
           'Seat 2: beta (2000 in chips, $1.50 bounty)\n'
           '*** SUMMARY ***\n'
           'Seat 1: alfa (button) won (1500)\n'
           'Seat 2: beta showed [As Ks] and lost\n')
    assert sorted(nomes_sentados(mao)) == ['alfa', 'beta'], sorted(nomes_sentados(mao))
    assert len(assentos_com_stack(mao)) == 2
    # CONTROLE do controle: sem o corte, a linha de summary ENTRARIA. Prova que o teste acima
    # nao passa por acidente de o regex nao casar.
    from leaklab.mesa_final import _ASSENTO_RE
    assert _ASSENTO_RE.match('Seat 1: alfa (button) won (1500)'), (
        'o regex deixou de casar a linha de summary — o corte estrutural virou decorativo e '
        'este teste parou de provar o que dizia provar')
    print('OK  test_o_SUMMARY_continua_fora_da_contagem')


def test_duas_maos_no_mesmo_arquivo_nao_se_misturam():
    """`nomes_sentados` recebe o arquivo INTEIRO em alguns chamadores e UMA mao em outros."""
    arquivo = (_mao('Seat 1: alfa (1000 in chips, $1 bounty)',
                    'Seat 2: beta (2000 in chips, $1 bounty)')
               + '*** SUMMARY ***\nSeat 1: alfa won (500)\n'
               + _mao('Seat 1: alfa (1500 in chips, $1 bounty)',
                      'Seat 3: gama (900 in chips, $1 bounty)'))
    assert sorted(nomes_sentados(arquivo)) == ['alfa', 'beta', 'gama']
    # A lista mantem duplicata de proposito — alfa senta nas duas maos.
    assert [n for n, _ in assentos_com_stack(arquivo)] == ['alfa', 'beta', 'alfa', 'gama']
    print('OK  test_duas_maos_no_mesmo_arquivo_nao_se_misturam')


def test_a_leitura_de_assento_tem_UM_dono():
    """A varredura dos N+1. Eram DUAS implementacoes e as duas quebravam no mesmo dialeto;
    `mtt_context` ainda carregava mais duas mortas (`_SEAT_RE`, `_STACK_RE`), tambem cegas ao PKO.

    LIMITE CONHECIDO: o parser tem regexes de assento PROPRIOS e legitimos (ele extrai bounty,
    botao, sitting out). O que nao pode existir e uma segunda leitura de (nome, stack) do roster
    fora de `mesa_final`.
    """
    donos = []
    for pasta in ('leaklab', 'database', 'api'):
        for dirpath, _, arquivos in os.walk(os.path.join(RAIZ, pasta)):
            for nome in arquivos:
                if not nome.endswith('.py'):
                    continue
                texto = open(os.path.join(dirpath, nome), encoding='utf-8').read()
                for m in re.finditer(r"re\.compile\(\s*r?['\"]([^'\"]*Seat[^'\"]*)['\"]", texto):
                    padrao = m.group(1)
                    # so interessa quem le NOME e FICHAS juntos do roster
                    if 'in chips' in padrao or 'chips' in padrao or padrao.count('(.+?)'):
                        donos.append(f'{pasta}/{nome}: {padrao[:60]}')
    fora = [d for d in donos if not d.startswith('leaklab/mesa_final.py')
            and not d.startswith('leaklab/parser.py')]
    assert not fora, ('segunda leitura de assento fora de mesa_final — use '
                      'assentos_com_stack:\n  ' + '\n  '.join(fora))
    print('OK  test_a_leitura_de_assento_tem_UM_dono')


def test_num_players_nao_pode_contradizer_a_POSICAO():
    """O oraculo que estava dentro da propria linha, virado guarda.

    Uma decisao que traga uma posicao de mesa grande e diga que a mesa era pequena se contradiz
    sozinha — foi assim que as 2.355 se denunciaram, sem fonte externa nenhuma.

    A tabela abaixo e MEDIDA de `nomes_de_posicao`, nao suposta. O agente da auditoria disse
    "MP1/UTG+2 exigem n>=7" e o numero real de UTG+2 e 8; eu supus BTN=2 e o real e 3, porque
    heads-up o botao E o small blind. Duas suposicoes, duas erradas, no mesmo par de linhas.
    """
    from leaklab.posicoes import nomes_de_posicao
    # `nomes_de_posicao` devolve {indice: nome}; o que interessa aqui sao os NOMES.
    minimo = {}
    for n in range(2, 10):
        for pos in nomes_de_posicao(n).values():
            minimo.setdefault(pos, n)
    assert minimo == {'BB': 2, 'SB': 2, 'BTN': 3, 'CO': 4, 'UTG': 5,
                      'HJ': 6, 'UTG+1': 7, 'UTG+2': 8, 'LJ': 9}, minimo
    # Confere com o jogo: 8-max e SB BB UTG UTG+1 UTG+2 HJ CO BTN — UTG+2 so existe a partir de 8.
    assert len(nomes_de_posicao(8)) == 8 and 'UTG+2' in nomes_de_posicao(8).values()
    assert 'UTG+2' not in nomes_de_posicao(7).values()
    print('OK  test_num_players_nao_pode_contradizer_a_POSICAO')

if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
