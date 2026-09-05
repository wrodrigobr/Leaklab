"""
Desafio do Dia (#42): CERTEZA do gabarito (só spot dominante + heurística concorda),
pool vetado (só aprovado vai ao ar), 1 tentativa/dia, veredito + stats. Via endpoints.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import api.app as A
from database.auth import generate_token
from leaklab.daily_challenge import build_candidates, grade_challenge
client = A.app.test_client()


def test_candidates_are_dominant_and_gradeable():
    """Todo candidato tem resposta DOMINANTE (o gabarito grada como 'correct')."""
    cands = build_candidates(6)
    assert cands, "não gerou candidatos"
    for c in cands:
        g = grade_challenge(c['spot_json'], c['answer'])
        assert g['is_correct'] and g['gto_tier'] == 'correct', (c['note'], g)
    print("OK  test_candidates_are_dominant_and_gradeable")


def test_only_approved_goes_live():
    """Pool com pendentes NÃO serve; só depois de aprovar aparece o desafio."""
    # limpa o pool pra isolar
    conn = repo.get_conn(); conn.execute("DELETE FROM daily_challenge_pool"); conn.execute("DELETE FROM daily_challenge_schedule"); conn.commit(); conn.close()
    repo.add_challenge_candidates(build_candidates(3))
    assert repo.get_today_challenge('2030-01-01') is None, "serviu sem aprovação!"
    pid = repo.list_challenge_candidates('pending')[0]['id']
    repo.set_challenge_status(pid, 'approved')
    ch = repo.get_today_challenge('2030-01-01')
    assert ch and ch['id'] == pid
    print("OK  test_only_approved_goes_live")


def _admin():
    uid = repo.create_user('adm_dc', 'admdc@t.com', 'pass1234', 'admin')
    return {'Authorization': f'Bearer {generate_token(uid, "admin")}'}


def _player(sfx):
    uid = repo.create_user(f'pl_dc{sfx}', f'pldc{sfx}@t.com', 'pass1234', 'player')
    return {'Authorization': f'Bearer {generate_token(uid, "player")}'}, uid


def test_endpoint_flow_generate_approve_play():
    """O fluxo do JOGADOR: aprovado -> ve sem gabarito -> responde -> 2a tentativa barrada.

    05/09: este teste esperava `generated` na resposta do /generate e ficou vermelho quando a
    geracao virou THREAD em 31/08 (dezenas de chamadas de LLM sequenciais dentro do request
    faziam o gunicorn matar o worker por timeout; o SystemExit nem era capturavel). O endpoint
    passou a devolver `202 {started: True}`. Como o arquivo estava FORA da suite, ninguem viu.

    Alem de destravar, o teste deixou de DEPENDER do LLM: o contrato assincrono e conferido a
    parte, e o pool e semeado direto pelo repositorio. Teste de fluxo que chama modelo e lento,
    caro e intermitente — e a intermitencia treina todo mundo a ignorar o vermelho.
    """
    h = _admin()
    # 1) o contrato ATUAL do generate: acusa recebimento e trabalha em thread
    r = client.post('/admin/daily-challenge/generate', headers=h, json={'n': 4})
    assert r.status_code == 202, "esperava 202 (assincrono), veio %s" % r.status_code
    body = r.get_json()
    assert body.get('started') is True, body
    assert 'generated' not in body, "voltou a ser sincrono? o teste precisa ser revisto: %s" % body

    # 2) o fluxo do jogador, sem depender da thread nem do LLM
    conn = repo.get_conn()
    conn.execute("DELETE FROM daily_challenge_pool"); conn.execute("DELETE FROM daily_challenge_schedule")
    conn.commit(); conn.close()
    repo.add_challenge_candidates(build_candidates(1, with_explanation=False))
    cand = repo.list_challenge_candidates('pending')[0]
    pid, answer = cand['id'], cand['answer']
    assert client.post(f'/admin/daily-challenge/{pid}/status', headers=h,
                       json={'status': 'approved'}).status_code == 200

    ph, _uid = _player('A')
    got = client.get('/player/daily-challenge', headers=ph).get_json()
    assert got['available'] and not got['answered'], got
    assert 'options' in got['spot'] and 'answer' not in got['spot']   # NAO vaza o gabarito
    sub = client.post('/player/daily-challenge/submit', headers=ph, json={'action': answer})
    assert sub.status_code == 200 and sub.get_json()['result']['is_correct'], sub.get_json()
    again = client.post('/player/daily-challenge/submit', headers=ph, json={'action': 'fold'})
    assert again.status_code == 409, again.status_code
    print("OK  test_endpoint_flow_generate_approve_play")


def test_challenge_reuses_when_pool_runs_dry():
    """Com ≥1 aprovado, o desafio NUNCA some: consumido num dia, o próximo dia REUSA
    (LRU) em vez de retornar None. Regressão do 'tenho 1 aprovado mas não aparece'."""
    conn = repo.get_conn()
    conn.execute("DELETE FROM daily_challenge_pool"); conn.execute("DELETE FROM daily_challenge_schedule")
    conn.commit(); conn.close()
    repo.add_challenge_candidates(build_candidates(1, with_explanation=False))
    pid = repo.list_challenge_candidates('pending')[0]['id']
    repo.set_challenge_status(pid, 'approved')
    a = repo.get_today_challenge('2031-01-01')          # consome no dia A
    assert a and dict(a)['id'] == pid
    b = repo.get_today_challenge('2031-01-02')          # dia B: sem 'unused', mas reusa
    assert b and dict(b)['id'] == pid, "desafio sumiu quando o pool 'novo' acabou"
    print("OK  test_challenge_reuses_when_pool_runs_dry")


def test_schedule_registered_as_no_id_table():
    """Regressão PG (bug do 500 em prod): daily_challenge_schedule tem PK NATURAL (day),
    sem coluna `id`. O wrapper de INSERT do Postgres anexa 'RETURNING id' por padrão e
    quebra nessa tabela (SQLite tolera, por isso os outros testes não pegam). Ela DEVE
    estar registrada em _NO_ID_TABLES."""
    conn = repo.get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_challenge_schedule)").fetchall()}
    conn.close()
    assert 'id' not in cols, "schedule não deveria ter coluna id (PK é day)"
    assert 'daily_challenge_schedule' in sch._AdaptedConn._NO_ID_TABLES, \
        "schedule sem id precisa estar em _NO_ID_TABLES senão o INSERT 500 no Postgres"
    print("OK  test_schedule_registered_as_no_id_table")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
    raise SystemExit(1 if failed else 0)
