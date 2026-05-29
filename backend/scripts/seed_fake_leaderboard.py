"""
Seed de dados FAKE para testar o leaderboard (#15) localmente.

Cria usuários fictícios (prefixo `fake_`) com perfis distintos — crusher,
improver, grinder, rookie e um abaixo do gate — gerando torneios + decisões com
`gto_label` + drills suficientes para o ranking demonstrar as 4 dimensões
(aderência GTO / evolução / engajamento / volume).

SOMENTE LOCAL/SQLite (recusa rodar em Postgres). Idempotente: limpa os `fake_`
antes de recriar. `--clean` só remove os fakes.

Uso:
    cd backend
    python scripts/seed_fake_leaderboard.py          # limpa + cria
    python scripts/seed_fake_leaderboard.py --clean   # só remove os fakes
"""
import sys
import argparse
import random
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from database.schema import get_conn, init_db, USE_POSTGRES
from database.repositories import create_user

# username, torneios, mãos totais, nº decisões, aderência início→recente, drills
PROFILES = [
    dict(username="fake_crusher",   tourneys=12, hands=1600, decisions=320, early=0.90, recent=0.93, drills=28),
    dict(username="fake_improver",  tourneys=12, hands=1300, decisions=260, early=0.55, recent=0.88, drills=16),
    dict(username="fake_grinder",   tourneys=16, hands=2600, decisions=420, early=0.72, recent=0.72, drills=34),
    dict(username="fake_rookie",    tourneys=11, hands=640,  decisions=130, early=0.60, recent=0.66, drills=4),
    dict(username="fake_belowgate", tourneys=5,  hands=220,  decisions=60,  early=0.60, recent=0.60, drills=0),
]

_ALIGNED_LABELS = ["gto_correct", "gto_mixed"]


def _clean(conn):
    rows = conn.execute("SELECT id FROM users WHERE username LIKE 'fake\\_%' ESCAPE '\\'").fetchall()
    ids = [r["id"] for r in rows]
    for uid in ids:
        conn.execute("DELETE FROM drill_sessions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM tournaments WHERE user_id = ?", (uid,))  # cascade → decisions
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    return len(ids)


def _gen_labels(n: int, early: float, recent: float, seed: int) -> list[str]:
    """n gto_labels em ordem cronológica; prob. de aderência sobe de early→recent."""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        p = early + (recent - early) * (i / max(1, n - 1))
        if rnd.random() < p:
            out.append("gto_correct" if rnd.random() < 0.7 else "gto_mixed")
        else:
            out.append("gto_minor_deviation" if rnd.random() < 0.5 else "gto_critical")
    return out


_LABEL_MAP = {  # gto_label → (engine label, score) só para satisfazer NOT NULL
    "gto_correct":         ("standard", 0.04),
    "gto_mixed":           ("marginal", 0.14),
    "gto_minor_deviation": ("small_mistake", 0.28),
    "gto_critical":        ("clear_mistake", 0.50),
}


def seed():
    if USE_POSTGRES:
        print("ABORTADO: seed é só para SQLite local (USE_POSTGRES=True detectado).")
        return
    init_db()
    conn = get_conn()
    try:
        removed = _clean(conn)
        if removed:
            print(f"Removidos {removed} usuários fake antigos.")

        now = datetime.utcnow()
        summary = []
        for prof in PROFILES:
            uid = create_user(prof["username"], f"{prof['username']}@test.local", "fakepass123")
            labels = _gen_labels(prof["decisions"], prof["early"], prof["recent"], seed=uid)
            li = 0
            per_t = prof["decisions"] // prof["tourneys"]
            hands_per = max(1, prof["hands"] // prof["tourneys"])
            dec_ids = []
            for ti in range(prof["tourneys"]):
                # torneios em ordem cronológica (mais antigo primeiro) p/ casar com evolução
                imported = (now - timedelta(days=(prof["tourneys"] - ti) * 3)).strftime("%Y-%m-%d %H:%M:%S")
                cur = conn.execute(
                    "INSERT INTO tournaments (user_id, tournament_id, hero, site, hands_count, "
                    "decisions_count, imported_at, played_at) VALUES (?,?,?,?,?,?,?,?)",
                    (uid, f"FAKE-{prof['username']}-{ti}", prof["username"], "pokerstars",
                     hands_per, per_t, imported, imported[:10]),
                )
                tdb = cur.lastrowid
                # decisões desse torneio (fatia da sequência cronológica global)
                count = per_t if ti < prof["tourneys"] - 1 else (prof["decisions"] - li)
                rows = []
                for _ in range(count):
                    gto = labels[li]; li += 1
                    eng_label, score = _LABEL_MAP[gto]
                    rows.append((tdb, f"h{li}", "preflop", "raise", "raise", eng_label, score, gto, "raise"))
                conn.executemany(
                    "INSERT INTO decisions (tournament_id, hand_id, street, action_taken, "
                    "best_action, label, score, gto_label, gto_action) VALUES (?,?,?,?,?,?,?,?,?)",
                    rows,
                )
                # coletar alguns decision ids p/ drills (do 1º torneio basta)
                if len(dec_ids) < prof["drills"]:
                    got = conn.execute(
                        "SELECT id FROM decisions WHERE tournament_id = ? LIMIT ?",
                        (tdb, prof["drills"] - len(dec_ids)),
                    ).fetchall()
                    dec_ids.extend([r["id"] for r in got])

            # drills
            drilled = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            conn.executemany(
                "INSERT INTO drill_sessions (user_id, decision_id, new_action, new_score, "
                "original_score, delta, drilled_at) VALUES (?,?,?,?,?,?,?)",
                [(uid, did, "raise", 0.05, 0.30, -0.25, drilled) for did in dec_ids[:prof["drills"]]],
            )
            summary.append((prof["username"], uid, prof["tourneys"], prof["hands"], prof["decisions"], prof["drills"]))

        conn.commit()
        print("\nUsuários fake criados:")
        for name, uid, t, h, d, dr in summary:
            print(f"  {name:16s} id={uid}  torneios={t}  mãos={h}  decisões={d}  drills={dr}")
        print("\nSenha de todos: fakepass123")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="só remove os usuários fake")
    args = ap.parse_args()
    if args.clean:
        if USE_POSTGRES:
            print("ABORTADO: só SQLite local."); sys.exit(0)
        c = get_conn()
        try:
            n = _clean(c); print(f"Removidos {n} usuários fake.")
        finally:
            c.close()
    else:
        seed()
