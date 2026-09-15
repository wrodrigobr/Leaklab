# -*- coding: utf-8 -*-
"""A mesma mao repetida no MESMO arquivo conta uma vez (auditoria NLU-9, 15/09).

Medido pela rota real: as 3 primeiras maos do fixture, uma vez, dao 4 decisoes. As mesmas 3
maos coladas duas vezes no mesmo arquivo davam `total_hands=6`, 8 decisoes no banco e
`hands_count=3` (que conta ids distintos): a resposta e o banco se desmentiam, e cada mao
repetida pesava em dobro em toda estatistica, ELO e plano de estudos. So o REIMPORT dedupava,
contra o raw ja salvo; o arquivo contra ele mesmo, nunca.

O que este arquivo defende:
1. `parse_hand_history` devolve cada `(tournament_id, hand_id)` uma vez, na ordem do arquivo.
2. Entre blocos repetidos fica o mais LONGO (export truncado perde para o inteiro).
3. Mesmo `hand_id` em torneios DIFERENTES nao e fundido (a chave inclui o torneio).
4. Mao sem id nao e deduplicada (a chave nao identificaria nada).
5. Pela rota `/analyze`, o arquivo dobrado grava as mesmas decisoes do simples, e
   `total_hands` bate com `hands_count`.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from test_arquivo_com_varios_torneios import UID, banco_de_teste   # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'revalidation_mini.txt')


def _blocos():
    raw = io.open(_FIX, encoding='utf-8').read()
    return [b for b in re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]


def test_parser_devolve_cada_mao_uma_vez_na_ordem_do_arquivo():
    from leaklab.parser import parse_hand_history
    b = _blocos()[:3]
    simples = parse_hand_history(''.join(b))
    dobrado = parse_hand_history(''.join(b) + ''.join(b))
    assert len(simples) == 3, len(simples)
    assert [h.hand_id for h in dobrado] == [h.hand_id for h in simples], (
        [h.hand_id for h in dobrado])
    # e o embaralhado (3, 1, 2, 1, 3) sai na ordem da PRIMEIRA aparicao
    misto = parse_hand_history(b[2] + b[0] + b[1] + b[0] + b[2])
    assert [h.hand_id for h in misto] == [simples[2].hand_id, simples[0].hand_id, simples[1].hand_id]


def test_entre_repetidos_fica_o_bloco_mais_longo():
    from leaklab.parser import parse_hand_history
    b = _blocos()[:2]
    inteiro = b[0]
    truncado = inteiro.split('*** SUMMARY ***')[0]        # export cortado antes do summary
    assert len(truncado) < len(inteiro)
    for arquivo in (truncado + b[1] + inteiro, inteiro + b[1] + truncado):
        hands = parse_hand_history(arquivo)
        assert len(hands) == 2, len(hands)
        assert hands[0].raw_text.strip() == inteiro.strip(), 'ficou o bloco truncado'


def test_mesmo_hand_id_em_torneios_diferentes_nao_funde():
    from leaklab.parser import parse_hand_history
    b = _blocos()[:1]
    outro = b[0].replace('Tournament #999900001', 'Tournament #999900002').replace(
        "Table '999900001", "Table '999900002")
    assert outro != b[0]
    hands = parse_hand_history(b[0] + outro)
    assert len(hands) == 2, len(hands)
    assert {h.tournament_id for h in hands} == {'999900001', '999900002'}


def test_mao_sem_id_nao_e_deduplicada():
    from leaklab.models import ParsedHand
    from leaklab.parser import deduplicar_maos
    maos = [ParsedHand(hand_id='unknown', tournament_id='1', raw_text='a'),
            ParsedHand(hand_id='unknown', tournament_id='1', raw_text='b'),
            ParsedHand(hand_id='', tournament_id='1', raw_text='c'),
            ParsedHand(hand_id='7', tournament_id='1', raw_text='d'),
            ParsedHand(hand_id='7', tournament_id='1', raw_text='dd')]
    saida = deduplicar_maos(maos)
    assert [h.raw_text for h in saida] == ['a', 'b', 'c', 'dd'], [h.raw_text for h in saida]


def test_pela_rota_o_arquivo_dobrado_grava_as_mesmas_decisoes_do_simples():
    from database.schema import get_conn
    from database.repositories import _adapt
    from database.rowutil import value
    b = _blocos()[:3]

    def _conta(tdb):
        c = get_conn()
        try:
            n = value(c.execute(_adapt(
                "SELECT COUNT(*) AS n FROM decisions WHERE tournament_id=?"), (tdb,)).fetchone(), 'n')
            hc = value(c.execute(_adapt(
                "SELECT hands_count FROM tournaments WHERE id=?"), (tdb,)).fetchone(), 'hands_count')
            return int(n), int(hc)
        finally:
            c.close()

    with banco_de_teste() as (cliente, headers):
        r0 = cliente.post('/analyze', json={'content': ''.join(b), 'filename': 'base.txt'},
                          headers=headers)
        assert r0.status_code == 200, (r0.status_code, r0.get_json())
        j0 = r0.get_json()
        dec_simples, hc_simples = _conta(j0['tournament_db_id'])
        assert dec_simples > 0 and j0['total_hands'] == 3 == hc_simples

    with banco_de_teste() as (cliente, headers):
        r = cliente.post('/analyze', json={'content': ''.join(b) + ''.join(b), 'filename': 'dup.txt'},
                         headers=headers)
        assert r.status_code == 200, (r.status_code, r.get_json())
        j = r.get_json()
        dec_dobrado, hc_dobrado = _conta(j['tournament_db_id'])
        assert j['total_hands'] == 3, j['total_hands']
        assert dec_dobrado == dec_simples, ('o arquivo dobrado gravou %d decisoes contra %d do simples'
                                            % (dec_dobrado, dec_simples))
        assert hc_dobrado == j['total_hands'] == 3


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
