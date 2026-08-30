# -*- coding: utf-8 -*-
"""As cotas mensais do Free contam E zeram na virada — inclusive para quem fechou no teto.

── O que originou (30/08, véspera de lançamento) ────────────────────────────────────────────

O dono pediu a garantia de que as "15 explicações de IA por mês" da vitrine são contabilizadas
de verdade. A auditoria achou um DEADLOCK: o reset da virada morava só nos increments, mas o
bloqueio (402) lê get_quota_status ANTES de incrementar — quem fechou o mês em 15/15 lia 15 no
mês novo, era barrado, e o increment que zeraria nunca rodava. Preso no teto para sempre.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_TESTING', '1')


def _banco():
    from database.schema import init_db
    init_db()


def _novo():
    from database.repositories import create_user
    m = uuid.uuid4().hex[:8]
    return create_user('quota_' + m, f'quota_{m}@t.local', 'x' * 12)


def test_incrementos_contam():
    _banco()
    from database.repositories import (get_quota_status, increment_ai_calls,
                                       increment_tournament_count)
    uid = _novo()
    for _ in range(3):
        increment_ai_calls(uid)
    increment_tournament_count(uid)
    q = get_quota_status(uid)
    assert q['ai_calls_used'] == 3 and q['tournaments_used'] == 1, q
    print('OK  test_incrementos_contam')


def test_virada_de_mes_zera_NA_LEITURA():
    """O deadlock: usuário no teto (15/15) com o mês virado tem que ler ZERO na consulta —
    é a consulta que o 402 usa, e sem reset nela o bloqueio é eterno."""
    _banco()
    from database.repositories import _adapt, get_quota_status
    from database.schema import get_conn
    uid = _novo()
    conn = get_conn()
    try:
        # forja: fechou o mês PASSADO no teto de tudo
        conn.execute(_adapt(
            "UPDATE users SET ai_calls_this_month = 15, tournaments_this_month = 30, "
            "solves_this_month = 5, quota_reset_at = '2020-01-15' WHERE id = ?"), (uid,))
        conn.commit()
    finally:
        conn.close()
    q = get_quota_status(uid)
    assert q['ai_calls_used'] == 0, (
        'mês virou e a LEITURA ainda vê %s/15 — o 402 barra e o usuário fica preso '
        'para sempre' % q['ai_calls_used'])
    assert q['tournaments_used'] == 0 and q['solves_used'] == 0, q
    print('OK  test_virada_de_mes_zera_NA_LEITURA')


def test_dentro_do_mesmo_mes_NAO_zera():
    """Contraprova: o reset é da virada, não de toda leitura."""
    _banco()
    from database.repositories import get_quota_status, increment_ai_calls
    uid = _novo()
    increment_ai_calls(uid)
    increment_ai_calls(uid)
    assert get_quota_status(uid)['ai_calls_used'] == 2
    assert get_quota_status(uid)['ai_calls_used'] == 2, 'ler duas vezes apagou o contador'
    print('OK  test_dentro_do_mesmo_mes_NAO_zera')


def test_rota_da_ia_consome_e_barra_no_teto():
    """Ponta a ponta na rota que a vitrine anuncia: 15 passam, a 16a leva 402 com upsell."""
    _banco()
    import api.app as A
    from database.auth import generate_token
    from database.repositories import _adapt, increment_ai_calls
    from database.schema import get_conn
    uid = _novo()
    for _ in range(15):
        increment_ai_calls(uid)
    tok = generate_token(uid, 'player')
    c = A.app.test_client()
    r = c.post('/analyze/hand-coach', json={'hand': {'id': 'x'}, 'decisions': []},
               headers={'Authorization': 'Bearer ' + tok})
    assert r.status_code == 402, 'no teto de 15, a 16a chamada deveria levar 402: %s %s' % (
        r.status_code, r.get_data(as_text=True)[:120])
    d = r.get_json()
    assert d.get('quota_exceeded') and d.get('limit') == 15 and d.get('used') == 15, d
    print('OK  test_rota_da_ia_consome_e_barra_no_teto')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
