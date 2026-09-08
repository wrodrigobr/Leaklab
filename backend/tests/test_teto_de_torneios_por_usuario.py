# -*- coding: utf-8 -*-
"""Teto de torneios por mes ajustavel por USUARIO, pelo admin (08/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Um fundador bateu nos 200 torneios do Pro no 4o dia do mes (o outro fundador tinha 280 pelo
script de lote). O dono: "para um pro isso e pouco? Precisamos pensar uma forma de liberar por
usuario. Os fundadores eu preciso permitir pois eles estao ajudando testando a plataforma."

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. `users.tournaments_limit_override`: NULL = o teto do plano; numero = vale sobre o plano, na
   cota (`get_quota_status`) e no 402 do upload (`_check_upload_quota`). Voltar a NULL volta ao
   plano. PLAN_LIMITS (compartilhado) NAO e mutado.
2. Conceder fundador da 1.000/mes e nao rebaixa um teto maior ja dado pelo admin.
3. O PATCH do admin aceita o campo (inteiro, null, e recusa lixo e negativo); a lista do admin
   mostra usados e teto.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)
os.environ.pop('LEAKLAB_IMPORT_LOTE', None)

from database.schema import get_conn, init_db                                  # noqa: E402
import database.repositories as repo                                           # noqa: E402
from database.repositories import (PLAN_LIMITS, FOUNDER_TOURNAMENTS_LIMIT, _adapt,  # noqa: E402
                                   get_quota_status, update_user_admin, grant_founder, get_all_users)


def _usuario(plan='pro', usados=0):
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('teto', 'teto@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("UPDATE users SET plan=?, plan_source=?, tournaments_this_month=?, quota_reset_at=? WHERE id=?"),
                 (plan, 'admin' if plan == 'pro' else None, usados, __import__('datetime').date.today().strftime('%Y-%m-01'), uid))
    conn.commit(); conn.close()
    return uid


def test_o_teto_proprio_vale_sobre_o_plano_e_null_volta_ao_plano():
    uid = _usuario('pro', usados=200)
    antes = dict(PLAN_LIMITS['pro'])
    q = get_quota_status(uid)
    assert q['limits']['tournaments'] == 200 and q['tournaments_limit_override'] is None
    update_user_admin(uid, tournaments_limit_override=1000, por=1)
    q = get_quota_status(uid)
    assert q['limits']['tournaments'] == 1000 and q['tournaments_limit_override'] == 1000, q
    assert PLAN_LIMITS['pro'] == antes, 'PLAN_LIMITS e compartilhado e nao pode ser mutado'
    # o 402 do upload respeita o teto proprio
    from api.app import app, _check_upload_quota
    with app.app_context():
        assert _check_upload_quota(uid) is None
        update_user_admin(uid, tournaments_limit_override=None, por=1)
        r = _check_upload_quota(uid)
        assert r is not None and r[1] == 402 and r[0].get_json()['limit'] == 200, r
    assert get_quota_status(uid)['tournaments_limit_override'] is None
    # update_user_admin SEM o campo nao mexe no teto
    update_user_admin(uid, tournaments_limit_override=50, por=1)
    update_user_admin(uid, suspended=False, por=1)
    assert get_quota_status(uid)['limits']['tournaments'] == 50


def test_fundador_recebe_1000_e_nao_perde_teto_maior():
    assert FOUNDER_TOURNAMENTS_LIMIT == 1000
    uid = _usuario('free', usados=0)
    r = grant_founder([uid], meses=3)
    assert r['concedidos'] == [uid], r
    assert get_quota_status(uid)['limits']['tournaments'] == 1000
    update_user_admin(uid, tournaments_limit_override=5000, por=1)
    grant_founder([uid], meses=3)                                   # renovacao
    assert get_quota_status(uid)['limits']['tournaments'] == 5000, 'renovar nao pode rebaixar o teto do admin'


def test_o_patch_do_admin_aceita_null_inteiro_e_recusa_lixo_e_a_lista_mostra():
    uid = _usuario('pro', usados=7)
    from api.app import app
    from database.auth import generate_token
    admin = repo.create_user('adm', 'adm@t.local', 'senha12345', 'admin')
    conn = get_conn(); conn.execute(_adapt("UPDATE users SET role='admin' WHERE id=?"), (admin,)); conn.commit(); conn.close()
    h = {'Authorization': 'Bearer %s' % generate_token(admin, 'admin')}
    c = app.test_client()
    assert c.patch('/admin/users/%d' % uid, json={'tournaments_limit_override': 400}, headers=h).status_code == 200
    assert get_quota_status(uid)['limits']['tournaments'] == 400
    assert c.patch('/admin/users/%d' % uid, json={'tournaments_limit_override': 'muitos'}, headers=h).status_code == 400
    assert c.patch('/admin/users/%d' % uid, json={'tournaments_limit_override': -1}, headers=h).status_code == 400
    assert c.patch('/admin/users/%d' % uid, json={}, headers=h).status_code == 400
    assert get_quota_status(uid)['limits']['tournaments'] == 400
    assert c.patch('/admin/users/%d' % uid, json={'tournaments_limit_override': None}, headers=h).status_code == 200
    assert get_quota_status(uid)['limits']['tournaments'] == 200
    c.patch('/admin/users/%d' % uid, json={'tournaments_limit_override': 400}, headers=h)
    linha = next(u for u in get_all_users(limit=50, search='teto@') if u['id'] == uid)
    assert linha['tournaments_this_month'] == 7 and linha['tournaments_limit_override'] == 400, linha
    r = c.get('/admin/users?search=teto@', headers=h)
    assert r.status_code == 200 and r.get_json()['users'][0]['tournaments_limit_override'] == 400


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
