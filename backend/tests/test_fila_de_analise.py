# -*- coding: utf-8 -*-
"""test_fila_de_analise.py — fila de análise GTO por plano (02/09, decisão do dono).

Trava: upload SEMPRE entra; free tem 3 análises simultâneas e o resto AGUARDA; a promoção
preenche a vaga na ordem de chegada quando os spots do torneio drenam; Pro não espera;
stale de 24h solta a trava; DDL válida nas duas gramáticas.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_fila_analise_test.db'
if os.path.exists('_fila_analise_test.db'):
    os.remove('_fila_analise_test.db')

import database.schema as schema
schema.init_db()

from datetime import datetime, timedelta
from database.repositories import _adapt
from database.schema import get_conn
from leaklab import fila_de_analise as fa

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


def _torneio(conn, uid, n):
    conn.execute(_adapt(
        "INSERT INTO tournaments (user_id, tournament_id, site, tournament_name, hero) "
        "VALUES (?,?,?,?,?)"), (uid, f'T-{uid}-{n}', 'PokerStars', f'Torneio {n}', 'heroi'))
    return conn.execute(_adapt(
        "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
        (uid, f'T-{uid}-{n}')).fetchone()['id']


def _spot_ativo(conn, tid, h, quando=None):
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (?,?)"), (tid, h))
    conn.execute(_adapt(
        "INSERT INTO gto_solver_queue (spot_hash, spot_json, status, priority, requested_at) "
        "VALUES (?, '{}', 'pending', 5, ?)"),
        (h, (quando or datetime.utcnow()).isoformat(sep=' ')))


# ── DDL nas duas gramáticas (regra: guarda estrutural sem servidor PG) ────────
for pg in (True, False):
    ddl = ' '.join(fa._stmts(pg))
    check('gto_analysis_waitlist' in ddl, f'DDL {pg} cria a tabela')
    check(('SERIAL' in ddl) == pg, f'DDL {pg} usa o autoincrement da gramática certa')

# ── setup: free com 3 análises ativas, 2 aguardando; pro com 4 ativas ─────────
conn = get_conn()
conn.execute("INSERT INTO users (id, username, email, password_hash, plan) VALUES (10,'freeu','f@e','h','free')")
conn.execute("INSERT INTO users (id, username, email, password_hash, plan) VALUES (11,'prou','p@e','h','pro')")
tids = [_torneio(conn, 10, i) for i in range(1, 6)]
for i, t in enumerate(tids[:3]):
    _spot_ativo(conn, t, f'hash-free-{i}')
# decisões postflop dos que vão aguardar (a promoção pede análise a partir DELAS)
for t in tids[3:]:
    conn.execute(_adapt(
        "INSERT INTO decisions (tournament_id, hand_id, street, position, action_taken, best_action, label, score) "
        "VALUES (?, ?, 'flop', 'BTN', 'call', 'call', 'ok', 0)"), (t, f'H-{t}'))
ptids = [_torneio(conn, 11, i) for i in range(1, 5)]
for i, t in enumerate(ptids):
    _spot_ativo(conn, t, f'hash-pro-{i}')
conn.commit()
conn.close()

# ── free: 3 ativas = cheio; pro: nunca espera ────────────────────────────────
check(len(fa.em_analise(10)) == 3, 'free tem 3 em análise')
check(fa.deve_esperar(10) is True, 'free com 3 ativas deve esperar')
check(fa.deve_esperar(11) is False, 'pro com 4 ativas NÃO espera (sem limite)')

fa.entrar_na_espera(tids[3], 10)
fa.entrar_na_espera(tids[4], 10)
fa.entrar_na_espera(tids[3], 10)   # idempotente (INSERT OR IGNORE)
check(fa.em_espera_ids(10) == [tids[3], tids[4]], 'espera em ordem de chegada, sem duplicar')

# ── promoção: sem vaga, nada acontece ────────────────────────────────────────
check(fa.promover_aguardando() == 0, 'sem vaga aberta, promove 0')
check(fa.em_espera_ids(10) == [tids[3], tids[4]], 'fila intacta sem vaga')

# ── abre UMA vaga (spots do 1º torneio drenam) → promove SÓ o mais antigo ────
conn = get_conn()
conn.execute(_adapt("UPDATE gto_solver_queue SET status='done' WHERE spot_hash='hash-free-0'"))
conn.commit()
conn.close()
check(fa.promover_aguardando() == 1, 'uma vaga → promove exatamente 1')
check(fa.em_espera_ids(10) == [tids[4]], 'promoveu o mais antigo; o outro segue na fila')
conn = get_conn()
req = conn.execute(_adapt(
    "SELECT COUNT(*) n FROM gto_hand_requests WHERE tournament_id=?"), (tids[3],)).fetchone()['n']
conn.close()
check(req == 1, 'promoção criou o gto_hand_request da mão postflop gravada')
# o request não-terminal do promovido OCUPA a vaga (sem isso o promotor soltaria >3)
check(fa.deve_esperar(10) is True, 'vaga preenchida pelo promovido: free volta a esperar')

# ── stale 24h: fila do solver presa não prende o usuário ─────────────────────
conn = get_conn()
velho = (datetime.utcnow() - timedelta(hours=25)).isoformat(sep=' ')
conn.execute(_adapt("UPDATE gto_solver_queue SET requested_at=?"), (velho,))
conn.execute(_adapt("UPDATE gto_hand_requests SET created_at=?"), (velho,))
conn.commit()
conn.close()
check(fa.deve_esperar(10) is False, 'tudo stale (>24h) → não prende o upload novo')
check(fa.promover_aguardando() == 1, 'stale libera vaga → o último aguardando é promovido')
check(fa.em_espera_ids(10) == [], 'fila esvaziou')

if os.path.exists('_fila_analise_test.db'):
    try:
        os.remove('_fila_analise_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
