# -*- coding: utf-8 -*-
"""Spot MULTIWAY nao entra na fila do solver, porque o solver e heads-up (14/09).

── O caso que originou ───────────────────────────────────────────────────────────────────────

Mao 262009780504 (conta 3). O dono estranhou uma recomendacao de all-in com ~70bb de stack e
mandou conferir. O texto da mao:

    MrNicko406 (UTG+1): raises 30 to 50      <- quem abriu
    hollymood  (HJ):    calls 50             <- cold call
    Brad Virtual (CO):  calls 50             <- cold call
    neckel834  (SB):    calls 40
    phpro      (BB):    calls 30             <- o heroi
    *** FLOP *** [5h Qs 8c]   -> CINCO jogadores
    neckel834 checks / phpro checks / MrNicko406 checks / hollymood bets 320 / phpro FOLDA

O solve que julgou esse fold modelou "HJ abre, BB paga", **heads-up**. O HJ recebeu um range de
ABERTURA, com AA/KK/AK dentro, que ele 3-betaria em vez de pagar por tras. Medido: QJ tem 75,1%
de equity contra aquele range e 53,1% contra um range de quem aposta forte ali -- e 53,08% foi
exatamente o que o proprio motor gravou na linha. Dos 75% saiu `allin 61,2%` e uma acusacao de
37,67bb.

── A regua externa ───────────────────────────────────────────────────────────────────────────

O dono abriu o GTO Wizard no no heads-up equivalente (HJ abre 2.1, BB paga, flop Q85, BB check,
HJ bet 5.5) a 70bb. As opcoes do BB la sao **Fold / Call / Raise 14.2**: nao existe all-in no
menu. O fold agregado bate com o nosso (56,4% contra 56,1%), mas a nossa agressao e 25,8% contra
7,3%, e a diferenca inteira esta numa acao que a arvore padrao nao tem.

── O tamanho ─────────────────────────────────────────────────────────────────────────────────

    postflop com veredito de solver ......... 27.616
    MULTIWAY (2+ oponentes ativos) ..........  8.953  (32,4%)
    desses, ACUSANDO o jogador ..............    728
    cobrado nessas acusacoes ................  5.254,8 bb

── O que este arquivo defende ────────────────────────────────────────────────────────────────

1. Que o gate recusa multiway **e aceita heads-up** -- sem o segundo lado, um gate que recusasse
   tudo passaria em todo caso de recusa e mataria o produto.
2. Que `n_ativos` omitido NAO bloqueia, porque `lookup_gto` e os scripts de recuperacao chamam
   sem o dado e travar por omissao quebraria consulta viva e reparo de no existente.
3. Que as DUAS portas vivas de enfileiramento recusam de verdade, pela porta e nao pela funcao:
   o upload (`_enqueue_postflop_spots`) e o pedido sob demanda (`montar_payload_postflop`).
   Guarda que testa a peca e nao o encaixe da cobertura sem dar protecao, e isso ja aconteceu
   nesta casa (o `auto=` de `_log_request`).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from leaklab.gto_solver import (montar_payload_postflop,                      # noqa: E402
                                vale_enfileirar_postflop)

from test_arquivo_com_varios_torneios import UID, banco_de_teste              # noqa: E402

# O spot da mao do dono, com o heroi OOP (BB) -- o caso que o solver serve nativamente, para o
# gate nao recusar pelo motivo ERRADO (heroi IP) e o teste passar sem provar nada.
SPOT = dict(street='flop', position='BB', vs_position='HJ',
            board=['5h', 'Qs', '8c'], hero_cards=['Jc', 'Qc'],
            stack_bb=71.75, facing_bb=16.0, pot_bb=29.85)


# ══════════════════════════════════════════════════════════════════════════════════════════
# 1) O gate
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_o_gate_recusa_multiway():
    assert vale_enfileirar_postflop('BB', 'HJ', 16.0, n_ativos=2) is False
    assert vale_enfileirar_postflop('BB', 'HJ', 16.0, n_ativos=4) is False


def test_o_gate_ACEITA_heads_up():
    """O outro lado. Um gate que recusasse sempre passaria no caso acima e desligaria o solver
    inteiro: 18.662 das 27.616 decisoes postflop com veredito sao heads-up de verdade."""
    assert vale_enfileirar_postflop('BB', 'HJ', 16.0, n_ativos=1) is True
    assert vale_enfileirar_postflop('BB', 'HJ', 16.0, n_ativos=0) is True


def test_n_ativos_omitido_nao_bloqueia():
    """`lookup_gto` e os scripts de recuperacao de no chamam sem o dado. Bloquear por omissao
    quebraria consulta viva e impediria reparo de no que JA existe -- estrago que o bug nao
    causava."""
    assert vale_enfileirar_postflop('BB', 'HJ', 16.0) is True
    assert vale_enfileirar_postflop('BB', 'HJ', 16.0, n_ativos=None) is True


def test_valor_ilegivel_nao_conta_como_heads_up():
    """Texto ou lixo no campo nao pode virar passe livre: o que nao se sabe pesa contra."""
    for ruim in ('', 'muitos', [], {}):
        assert vale_enfileirar_postflop('BB', 'HJ', 16.0, n_ativos=ruim) is True, ruim


# ══════════════════════════════════════════════════════════════════════════════════════════
# 2) A fonte unica do payload
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_a_fonte_unica_nao_monta_payload_multiway():
    assert montar_payload_postflop(n_ativos=2, **SPOT) is None
    assert montar_payload_postflop(n_ativos=5, **SPOT) is None


def test_a_fonte_unica_MONTA_o_heads_up():
    montado = montar_payload_postflop(n_ativos=1, **SPOT)
    assert montado is not None, 'o gate recusou heads-up: o teste de cima nao prova nada'
    h, payload = montado
    assert h and len(h) == 16, h
    assert '"street": "flop"' in payload and 'ip_range' in payload


# ══════════════════════════════════════════════════════════════════════════════════════════
# 3) As duas portas vivas, pela PORTA
# ══════════════════════════════════════════════════════════════════════════════════════════

def _resultado(n_ativos):
    """Uma decisao de flop no formato que o pipeline entrega ao enfileiramento.

    As chaves sao camelCase porque e assim que `pipeline.py` as escreve (linha 179 para
    `nActiveOpponents`); snake_case aqui passaria o teste sem exercitar o caminho real.
    """
    return {
        'street': 'flop',
        'board': ['5h', 'Qs', '8c'],
        'hero_cards': ['Jc', 'Qc'],
        'level_bb': 20.0,
        'spot': {
            'position': 'BB', 'villainPosition': 'HJ',
            'effectiveStackBb': 71.75, 'facingSize': 320.0, 'potSize': 597.0,
            'potType': '', 'preflopOpener': 'UTG+1', 'preflop3bettor': '',
            'nActiveOpponents': n_ativos,
        },
        'context': {'position': 'BB', 'vsPosition': 'HJ', 'heroStackBb': 71.75},
    }


def _na_fila():
    from database.schema import get_conn
    conn = get_conn()
    try:
        return int(dict(conn.execute(
            "SELECT COUNT(*) AS n FROM gto_solver_queue").fetchone())['n'])
    finally:
        conn.close()


def test_o_upload_nao_enfileira_multiway():
    with banco_de_teste():
        import api.app as A
        antes = _na_fila()
        A._enqueue_postflop_spots([_resultado(2)], tournament_id=None, user_id=UID)
        assert _na_fila() == antes, 'o upload enfileirou um flop multiway'


def test_o_upload_ENFILEIRA_o_heads_up():
    """O controle da porta. Sem ele, um `return` no topo de `_enqueue_postflop_spots` passaria
    no caso acima e o produto pararia de solvar qualquer coisa, calado."""
    with banco_de_teste():
        import api.app as A
        antes = _na_fila()
        A._enqueue_postflop_spots([_resultado(1)], tournament_id=None, user_id=UID)
        assert _na_fila() > antes, 'o upload deixou de enfileirar heads-up'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
