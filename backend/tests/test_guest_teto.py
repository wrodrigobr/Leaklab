# -*- coding: utf-8 -*-
"""/analyze/guest tem teto proprio de bytes e de maos, conferido ANTES de gastar CPU.

-- O defeito (auditoria SEG-1, 15/09) -----------------------------------------------------

A rota e publica (sem login), faz o parse e o motor de decisao inteiros dentro da requisicao,
e o unico freio era o MAX_CONTENT_LENGTH global (5 MB) mais "10 per hour" por IP, com o balde
do limiter na memoria de cada processo. Medido pela rota real: 4,4 MB de maos validas =
54,5 s de CPU (107,6 s noutra maquina) por requisicao. Um IP comprava ~1000 s de CPU por
hora, e o gunicorn corta em 120 s: a CPU ja foi gasta quando o worker morre.

Nenhum consumidor legitimo manda isso: o front nao chama a rota; quem experimenta manda uma
mao. O teto de 200 KB e 50 maos (as primeiras) cabe em qualquer uso real e a resposta diz o
que fazer ("faca login para analisar o arquivo inteiro"), nao "erro".

-- O que este arquivo defende -------------------------------------------------------------

1. Corpo acima do teto de bytes: 413, com a mensagem que manda logar, e o parse NAO roda.
2. Arquivo com mais maos que o teto: analisa as primeiras N e a resposta declara quantas
   ficaram de fora (`hands_in_file`, `hands_omitted`, `note`).
3. Arquivo pequeno: comportamento de sempre (nada omitido, nota de sempre).
4. Os padroes de producao sao os declarados (o test_api afrouxa os tetos de forma explicita;
   se alguem afrouxar o PADRAO, este teste acusa).
5. O medidor prova que acha (regra 1): com o teto desligado, o mesmo corpo grande passa pelo
   parse. Sem esse controle, um parse que nunca rodasse passaria verde.
"""
import io
import os
import re
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import api.app as A  # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'revalidation_mini.txt')


def _um_torneio():
    return io.open(_FIX, encoding='utf-8').read()


def _blocos(raw):
    return [b for b in re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]


def _varios_torneios(n, base_tid=999900001, base_hand=100000000001, hands_por_torneio=5):
    bs = _blocos(_um_torneio())[:hands_por_torneio]
    saida = []
    for k in range(n):
        tid = base_tid + k
        for i, b in enumerate(bs):
            b2 = re.sub(r'Tournament #\d+', 'Tournament #%d' % tid, b)
            b2 = re.sub(r'PokerStars Hand #\d+',
                        'PokerStars Hand #%d' % (base_hand + k * 100 + i), b2)
            b2 = b2.replace("Table '999900001", "Table '%d" % tid)
            saida.append(b2)
    return ''.join(saida)


def _cliente():
    A.app.config['TESTING'] = True
    A.app.config['GUEST_MAX_BYTES'] = A.GUEST_MAX_BYTES_PADRAO
    A.app.config['GUEST_MAX_HANDS'] = A.GUEST_MAX_HANDS_PADRAO
    return A.app.test_client()


def test_padroes_de_producao_sao_os_declarados():
    assert A.GUEST_MAX_BYTES_PADRAO == 200 * 1024, A.GUEST_MAX_BYTES_PADRAO
    assert A.GUEST_MAX_HANDS_PADRAO == 50, A.GUEST_MAX_HANDS_PADRAO
    # O setdefault no boot e o que vale em producao: ninguem afrouxou antes do primeiro request.
    fonte = io.open(os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py'),
                    encoding='utf-8').read()
    assert "app.config.setdefault('GUEST_MAX_BYTES', GUEST_MAX_BYTES_PADRAO)" in fonte
    assert "app.config.setdefault('GUEST_MAX_HANDS', GUEST_MAX_HANDS_PADRAO)" in fonte


def test_corpo_acima_do_teto_e_recusado_antes_do_parse():
    c = _cliente()
    corpo = _varios_torneios(80)                      # ~300 KB de maos VALIDAS
    assert len(corpo.encode('utf-8')) > A.GUEST_MAX_BYTES_PADRAO
    with mock.patch.object(A, 'parse_pokerstars_file_from_text',
                           wraps=A.parse_pokerstars_file_from_text) as parse:
        r = c.post('/analyze/guest', json={'content': corpo})
        assert r.status_code == 413, (r.status_code, r.get_json())
        j = r.get_json()
        assert j['code'] == 'guest_limite_tamanho'
        assert 'login' in j['error'].lower(), j['error']
        assert j['max_bytes'] == A.GUEST_MAX_BYTES_PADRAO
        assert parse.call_count == 0, 'o parse rodou %d vez(es) num corpo recusado' % parse.call_count


def test_o_medidor_acha_com_o_teto_desligado():
    """Regra 1: o mesmo corpo, com o teto de bytes desligado, PASSA pelo parse."""
    c = _cliente()
    A.app.config['GUEST_MAX_BYTES'] = None
    try:
        corpo = _varios_torneios(80)
        with mock.patch.object(A, 'parse_pokerstars_file_from_text',
                               wraps=A.parse_pokerstars_file_from_text) as parse:
            r = c.post('/analyze/guest', json={'content': corpo})
            assert r.status_code == 200, (r.status_code, r.get_json())
            assert parse.call_count == 1
            assert r.get_json()['hands_in_file'] == 400
    finally:
        A.app.config['GUEST_MAX_BYTES'] = A.GUEST_MAX_BYTES_PADRAO


def test_maos_alem_do_teto_ficam_de_fora_e_a_resposta_diz():
    c = _cliente()
    corpo = _varios_torneios(30)                      # 150 maos, ~115 KB: cabe em bytes
    assert len(corpo.encode('utf-8')) <= A.GUEST_MAX_BYTES_PADRAO
    with mock.patch.object(A, '_analyze_hands', wraps=A._analyze_hands) as motor:
        r = c.post('/analyze/guest', json={'content': corpo})
        assert r.status_code == 200, (r.status_code, r.get_json())
        j = r.get_json()
        assert j['hands_in_file'] == 150, j['hands_in_file']
        assert j['total_hands'] == 50, j['total_hands']
        assert j['hands_omitted'] == 100, j['hands_omitted']
        assert '100' in j['note'] and 'login' in j['note'].lower(), j['note']
        assert len(j['hands']) <= 50
        maos_no_motor = len(motor.call_args[0][0])
        assert maos_no_motor == 50, 'o motor recebeu %d maos' % maos_no_motor


def test_arquivo_pequeno_segue_igual():
    c = _cliente()
    corpo = _varios_torneios(2)                       # 10 maos
    r = c.post('/analyze/guest', json={'content': corpo})
    assert r.status_code == 200, (r.status_code, r.get_json())
    j = r.get_json()
    assert j['total_hands'] == 10 and j['hands_in_file'] == 10 and j['hands_omitted'] == 0
    assert j['note'] == 'Análise não salva. Faça login para manter histórico.'
    for chave in ('session_id', 'hero', 'metrics', 'leaks', 'hands'):
        assert chave in j, chave


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
