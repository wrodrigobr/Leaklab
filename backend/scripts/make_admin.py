"""make_admin.py — promove (ou rebaixa) um usuário a admin pelo e-mail.

Usa o backend configurado por DATABASE_URL (Postgres/Neon em prod) ou o SQLite local
se DATABASE_URL não estiver setada. Idempotente e mostra antes/depois.

Uso:
    python scripts/make_admin.py rodrigo.phpro@gmail.com            # promove a admin
    python scripts/make_admin.py rodrigo.phpro@gmail.com --role player   # rebaixa
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn        # respeita DATABASE_URL (prod) ou SQLite (dev)
from database.repositories import _adapt     # ? -> %s quando Postgres


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: python scripts/make_admin.py <email> [--role admin|player|coach]")
        return 2
    email = sys.argv[1].strip().lower()
    role = 'admin'
    if '--role' in sys.argv:
        role = sys.argv[sys.argv.index('--role') + 1].strip().lower()
    if role not in ('admin', 'player', 'coach'):
        print(f"role inválido: {role!r} (use admin|player|coach)")
        return 2

    backend = 'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite (dev)'
    conn = get_conn()
    try:
        row = conn.execute(_adapt("SELECT id, username, email, role FROM users WHERE email = ?"),
                           (email,)).fetchone()
        if not row:
            print(f"[{backend}] usuário não encontrado: {email}")
            return 1
        u = dict(row)
        print(f"[{backend}] antes: id={u['id']} username={u['username']} role={u['role']}")
        if u['role'] == role:
            print(f"já é '{role}', nada a fazer.")
            return 0
        conn.execute(_adapt("UPDATE users SET role = ? WHERE id = ?"), (role, u['id']))
        conn.commit()
        after = dict(conn.execute(_adapt("SELECT role FROM users WHERE id = ?"), (u['id'],)).fetchone())
        print(f"[{backend}] depois: role={after['role']}  OK")
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
