# -*- coding: utf-8 -*-
"""O historico de torneios nao tem teto escondido (06/09).

O dono viu "TORNEIOS 50" na tela de historico e desconfiou: "suspeito que este numero de 50
esteja cravado". Estava. `get_tournaments` tinha `limit=50` por padrao e `/history/tournaments`
repetia o 50; a tela chamava sem `limit`. A faixa "torneios / investido / lucro / ROI" e os
KPIs do dashboard somavam os ultimos 50 importados e apresentavam como historico. Zero
tranquilizador nao e o pior resultado possivel; um total plausivel e redondo chega perto.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                              # noqa: E402
import database.repositories as repo                                       # noqa: E402
from database.repositories import _adapt, get_tournaments                  # noqa: E402

N = 73   # acima de 50 de proposito


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('teto', 'teto@t.local', 'senha12345', 'player')
    conn = get_conn()
    for i in range(N):
        conn.execute(_adapt("INSERT INTO tournaments (user_id,tournament_id,site,hero,played_at,imported_at,buy_in,profit) "
                            "VALUES (?,?,'pokerstars','Hero',?,?,1.0,0.5)"),
                     (uid, 'T%03d' % i, '2026-%02d-%02d' % (1 + i // 28, 1 + i % 28), '2026-09-%02d' % (1 + i % 28)))
    conn.commit(); conn.close()
    return uid


def test_sem_limit_vem_o_historico_inteiro():
    uid = _semeia()
    assert len(get_tournaments(uid)) == N


def test_limit_pedido_e_respeitado():
    uid = _semeia()
    assert len(get_tournaments(uid, limit=5)) == 5
    assert len(get_tournaments(uid, limit=1)) == 1


def test_o_endpoint_sem_limit_devolve_tudo_e_com_limit_corta():
    uid = _semeia()
    from api.app import app
    from database.auth import generate_token
    tok = generate_token(uid, 'player')
    c = app.test_client()
    h = {'Authorization': 'Bearer %s' % tok}
    r = c.get('/history/tournaments', headers=h)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert len(r.get_json()['tournaments']) == N
    r = c.get('/history/tournaments?limit=10', headers=h)
    assert len(r.get_json()['tournaments']) == 10


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
