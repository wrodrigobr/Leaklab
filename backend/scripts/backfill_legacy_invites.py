"""SEC-01 — backfill: grandfather dos vínculos LEGADOS para a comp por indicação.

A comp passou a contar só alunos com `invited_via_invite_id` (convite single-use). Alunos
já vinculados (pela chave permanente antiga) têm isso NULL → deixariam de contar. Este
script cria um `coach_invites` 'legacy redeemed' por aluno já vinculado e seta
`users.invited_via_invite_id`, grandfathering as relações existentes.

DECISÃO DE PRODUTO: rode SÓ se os vínculos legados devem contar como "indicado". Caso
contrário, não rode — só novos resgates via convite contam.

Uso:
    python scripts/backfill_legacy_invites.py            # dry-run
    python scripts/backfill_legacy_invites.py --apply
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.schema import get_conn
from database.repositories import generate_single_use_invite_code, _now_str


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    conn = get_conn()
    try:
        conn.execute('PRAGMA busy_timeout=8000')
    except Exception:
        pass

    rows = conn.execute(
        "SELECT id, coach_id FROM users "
        "WHERE coach_id IS NOT NULL AND invited_via_invite_id IS NULL").fetchall()
    print(f"Vínculos legados sem atribuição de convite: {len(rows)}")
    n = 0
    for r in rows:
        student_id, coach_id = r['id'], r['coach_id']
        if not args.apply:
            n += 1
            continue
        # código único
        while True:
            code = generate_single_use_invite_code()
            if not conn.execute("SELECT 1 FROM coach_invites WHERE code=?", (code,)).fetchone():
                break
        now = _now_str()
        cur = conn.execute(
            "INSERT INTO coach_invites (coach_id, code, status, used_by, used_at, label) "
            "VALUES (?,?,?,?,?,?)",
            (coach_id, code, 'redeemed', student_id, now, '[legado]'))
        inv_id = cur.lastrowid
        conn.execute("UPDATE users SET invited_via_invite_id=? WHERE id=?", (inv_id, student_id))
        n += 1
    if args.apply:
        conn.commit()
    conn.close()
    print(f"{'Backfillados' if args.apply else 'Seriam backfillados'}: {n}")
    print('APLICADO' if args.apply else 'DRY-RUN (use --apply)')


if __name__ == '__main__':
    main()
