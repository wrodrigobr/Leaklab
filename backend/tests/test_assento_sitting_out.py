# -*- coding: utf-8 -*-
"""Assento "is sitting out" sumia de `players`, mas contava na posicao — duas mesas na mesma mao.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

`ACR_SEAT_RE` terminava em `$`, entao a linha

    Seat 6: Bitemee126 (74900.00) is sitting out

nao casava e o jogador sumia de `hand.players` e `hand.seats`. Mas `_infer_position` conta
assento por `line.startswith('Seat ')` **sem exigir "in chips"**, entao ELE contava o mesmo
jogador. Resultado: a posicao era calculada num anel de 7 e o tamanho da mesa reportado como 6.

Medido no acervo de producao: **362 linhas** com esse sufixo. Em 9 maos o jogador descartado
chegou a POSTAR ANTE E AGIR — ou seja, estava na mao para todos os efeitos.

Foi assim que sobrou a ultima das 11 divergencias sync x motor: o sync lia `num_players` do banco
(que vem de `active_players`, contagem de ASSENTOS = 7) e o motor passava `len(hand.players)` = 6.

── A armadilha do conserto, que eu cai nela ───────────────────────────────────────────────────

A primeira versao aceitava qualquer sufixo (`(?P<sufixo>\\s+\\S.*)?$`). Isso fez a linha de SUMMARY

    Seat 3: b75bd8ef (button) showed [8c 8h] and won (780) with three of a kind

**casar** — o `(780)` passa por stack — e injetaria um jogador fantasma chamado
"b75bd8ef (button) showed [8c 8h] and won". Um conserto que cria dano que o bug nao tinha.

Por isso o sufixo aceito e SO `is sitting out`, o unico que existe no acervo (362 de 362), e o
nome nao pode conter `(` nem `[`. Cobrir o que existe, nao adivinhar o que nao existe.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import ACR_SEAT_RE, parse_hand_history

_MAO = """Game Hand #2789038946 - Tournament #35598158 - Holdem (No Limit) - Level 4 (750.00/1500.00) - 2026/07/29 21:01:55 UTC
Table '2' 8-max Seat #3 is the button
Seat 1: MusashiBR (32920.00)
Seat 2: elvin6161 (30000.00)
Seat 3: JAMESHARPER (55597.00)
Seat 4: MoneyFunnel (58928.00)
Seat 5: Simplysim (28200.00)
Seat 6: Bitemee126 (74900.00) is sitting out
Seat 7: Rushgar (29700.00)
MusashiBR posts ante 150.00
Bitemee126 posts ante 150.00
Rushgar posts ante 150.00
MoneyFunnel posts the small blind 750.00
Simplysim posts the big blind 1500.00
*** HOLE CARDS ***
Dealt to MusashiBR [7c 3d]
Bitemee126 folds
Rushgar raises 5250.00 to 5250.00
MusashiBR folds
elvin6161 folds
JAMESHARPER folds
MoneyFunnel folds
Simplysim folds
*** SUMMARY ***
Total pot 4800.00
Seat 1: MusashiBR folded on the Pre-Flop and did not bet
Seat 3: JAMESHARPER (button) showed [8c 8h] and won (780) with three of a kind
Seat 4: MoneyFunnel (big blind) mucked [Qc 8c]
"""


def test_assento_sitting_out_entra_na_mesa():
    """Ele postou ante e agiu: esta na mao e ocupa posicao."""
    h = parse_hand_history(_MAO)[0]
    assert 'Bitemee126' in (h.players or []), (
        f'jogador sitting out sumiu de players: {h.players}')
    assert len(h.players) == 7, f'a mesa deveria ter 7, tem {len(h.players)}: {h.players}'
    assert any(s.get('name') == 'Bitemee126' for s in (h.seats or [])), 'sumiu de seats'


def test_linha_de_summary_nao_vira_jogador():
    """A armadilha da primeira versao do conserto: `(780)` passa por stack."""
    h = parse_hand_history(_MAO)[0]
    for p in (h.players or []):
        assert '[' not in p and '(' not in p and 'showed' not in p, (
            f'linha de SUMMARY virou jogador: {p!r}')
    assert len(h.players) == len(set(h.players)), f'jogador duplicado: {h.players}'


def test_o_regex_aceita_so_o_sufixo_que_existe():
    """Cobrir o que existe (362 de 362 sao `is sitting out`), nao adivinhar o resto."""
    assert ACR_SEAT_RE.match('Seat 6: Bitemee126 (74900.00) is sitting out')
    assert ACR_SEAT_RE.match('Seat 1: MusashiBR (32920.00)')
    assert not ACR_SEAT_RE.match(
        'Seat 3: b75bd8ef (button) showed [8c 8h] and won (780) with three of a kind')
    assert not ACR_SEAT_RE.match('Seat 4: phpro (big blind) mucked [Qc 8c]')
    assert not ACR_SEAT_RE.match('Seat 1: MusashiBR (button) folded on the Pre-Flop and did not bet')


def test_as_duas_contagens_da_mesa_batem():
    """O invariante que faltava: quem conta assento para POSICAO e quem conta para TAMANHO tem que
    ver a mesma mesa. Enquanto discordavam, a posicao saia de um anel e o tamanho de outro."""
    from leaklab.hand_state_builder import _infer_position
    h = parse_hand_history(_MAO)[0]
    # todo jogador de `players` recebe posicao (nenhum 'unknown' por estar fora da contagem)
    for p in h.players:
        pos = _infer_position(h, p)
        assert pos != 'unknown', f'{p} ficou sem posicao'
    # e as posicoes sao todas distintas — se a mesa fosse contada de dois jeitos, colidiriam
    posicoes = [_infer_position(h, p) for p in h.players]
    assert len(set(posicoes)) == len(posicoes), f'posicao repetida: {posicoes}'


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
