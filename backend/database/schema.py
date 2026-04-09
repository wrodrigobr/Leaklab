"""
schema.py — Banco de dados com suporte a PostgreSQL (produção) e SQLite (dev local).

Produção (Render): usa DATABASE_URL fornecida pelo Render PostgreSQL.
Desenvolvimento:   usa SQLite em ./data/leaklab.db automaticamente.
"""
from __future__ import annotations
import os
import sqlite3

# ── Detecção do banco ─────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Render fornece URLs no formato postgres:// — psycopg2 exige postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = bool(DATABASE_URL)

# SQLite para desenvolvimento local
_LOCAL_DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
SQLITE_PATH = os.environ.get('GAPHUNTER_DB', _LOCAL_DB)

# ── Conexão ───────────────────────────────────────────────────────────────────

def get_conn() -> _AdaptedConn:
    """Retorna conexão adaptada: PostgreSQL (produção) ou SQLite (dev)."""
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        raw = psycopg2.connect(DATABASE_URL,
                               cursor_factory=psycopg2.extras.RealDictCursor)
        raw.autocommit = False
    else:
        os.makedirs(os.path.dirname(os.path.abspath(SQLITE_PATH)), exist_ok=True)
        raw = sqlite3.connect(SQLITE_PATH)
        raw.row_factory = sqlite3.Row
        raw.execute('PRAGMA journal_mode=WAL')
        raw.execute('PRAGMA foreign_keys=ON')
    return _AdaptedConn(raw, USE_POSTGRES)


def ph(n: int = 1) -> str:
    """Placeholder para o banco ativo: $1 (Postgres) ou ? (SQLite)."""
    return f'${n}' if USE_POSTGRES else '?'


def placeholders(n: int) -> str:
    """N placeholders separados por vírgula."""
    if USE_POSTGRES:
        return ', '.join(f'${i}' for i in range(1, n + 1))
    return ', '.join(['?'] * n)


def now_sql() -> str:
    return 'NOW()' if USE_POSTGRES else "datetime('now')"


def interval_sql(days: int) -> str:
    if USE_POSTGRES:
        return f"NOW() - INTERVAL '{days} days'"
    return f"datetime('now', '-{days} days')"


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    try:
        if USE_POSTGRES:
            _init_postgres(conn)
        else:
            _init_sqlite(conn)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def _init_postgres(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              SERIAL PRIMARY KEY,
            username        TEXT    NOT NULL UNIQUE,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            role            TEXT    NOT NULL DEFAULT 'player',
            coach_id        INTEGER REFERENCES users(id),
            invite_key      TEXT    UNIQUE,
            plan            TEXT    NOT NULL DEFAULT 'free',
            invited_by_key  TEXT,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            last_login      TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tournaments (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            tournament_id   TEXT    NOT NULL,
            site            TEXT    NOT NULL DEFAULT 'pokerstars',
            hero            TEXT    NOT NULL,
            played_at       DATE,
            imported_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            hands_count     INTEGER NOT NULL DEFAULT 0,
            decisions_count INTEGER NOT NULL DEFAULT 0,
            avg_score       REAL,
            standard_pct    REAL,
            marginal_pct    REAL,
            small_pct       REAL,
            clear_pct       REAL,
            result          TEXT,
            place           INTEGER,
            llm_summary     TEXT,
            UNIQUE(user_id, tournament_id)
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id              SERIAL PRIMARY KEY,
            tournament_id   INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            hand_id         TEXT    NOT NULL,
            street          TEXT    NOT NULL,
            hero_cards      TEXT,
            board           TEXT,
            action_taken    TEXT    NOT NULL,
            best_action     TEXT    NOT NULL,
            label           TEXT    NOT NULL,
            score           REAL    NOT NULL,
            math_penalty    REAL    NOT NULL DEFAULT 0,
            range_penalty   REAL    NOT NULL DEFAULT 0,
            m_ratio         REAL,
            icm_pressure    TEXT,
            stack_bb        REAL,
            draw_profile    TEXT,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS coach_profiles (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id),
            display_name    TEXT    NOT NULL DEFAULT '',
            bio             TEXT    NOT NULL DEFAULT '',
            specialties     TEXT    NOT NULL DEFAULT '[]',
            contact_email   TEXT,
            contact_link    TEXT,
            is_public       INTEGER NOT NULL DEFAULT 1,
            plan            TEXT    NOT NULL DEFAULT 'free',
            max_students    INTEGER NOT NULL DEFAULT 5,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_tournament ON decisions(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_label      ON decisions(label);
        CREATE INDEX IF NOT EXISTS idx_decisions_street     ON decisions(street);
        CREATE INDEX IF NOT EXISTS idx_tournaments_user     ON tournaments(user_id);
        CREATE INDEX IF NOT EXISTS idx_tournaments_played   ON tournaments(played_at);
        CREATE INDEX IF NOT EXISTS idx_coach_profiles_public ON coach_profiles(is_public);
    """)


def _init_sqlite(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    NOT NULL UNIQUE,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            role            TEXT    NOT NULL DEFAULT 'player',
            coach_id        INTEGER REFERENCES users(id),
            invite_key      TEXT    UNIQUE,
            plan            TEXT    NOT NULL DEFAULT 'free',
            invited_by_key  TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login      TEXT
        );
        CREATE TABLE IF NOT EXISTS tournaments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            tournament_id   TEXT    NOT NULL,
            site            TEXT    NOT NULL DEFAULT 'pokerstars',
            hero            TEXT    NOT NULL,
            played_at       TEXT,
            imported_at     TEXT    NOT NULL DEFAULT (datetime('now')),
            hands_count     INTEGER NOT NULL DEFAULT 0,
            decisions_count INTEGER NOT NULL DEFAULT 0,
            avg_score       REAL,
            standard_pct    REAL,
            marginal_pct    REAL,
            small_pct       REAL,
            clear_pct       REAL,
            result          TEXT,
            place           INTEGER,
            llm_summary     TEXT,
            UNIQUE(user_id, tournament_id)
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id   INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            hand_id         TEXT    NOT NULL,
            street          TEXT    NOT NULL,
            hero_cards      TEXT,
            board           TEXT,
            action_taken    TEXT    NOT NULL,
            best_action     TEXT    NOT NULL,
            label           TEXT    NOT NULL,
            score           REAL    NOT NULL,
            math_penalty    REAL    NOT NULL DEFAULT 0,
            range_penalty   REAL    NOT NULL DEFAULT 0,
            m_ratio         REAL,
            icm_pressure    TEXT,
            stack_bb        REAL,
            draw_profile    TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS coach_profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id),
            display_name    TEXT    NOT NULL DEFAULT '',
            bio             TEXT    NOT NULL DEFAULT '',
            specialties     TEXT    NOT NULL DEFAULT '[]',
            contact_email   TEXT,
            contact_link    TEXT,
            is_public       INTEGER NOT NULL DEFAULT 1,
            plan            TEXT    NOT NULL DEFAULT 'free',
            max_students    INTEGER NOT NULL DEFAULT 5,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_tournament ON decisions(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_label      ON decisions(label);
        CREATE INDEX IF NOT EXISTS idx_decisions_street     ON decisions(street);
        CREATE INDEX IF NOT EXISTS idx_tournaments_user     ON tournaments(user_id);
        CREATE INDEX IF NOT EXISTS idx_tournaments_played   ON tournaments(played_at);
        CREATE INDEX IF NOT EXISTS idx_coach_profiles_public ON coach_profiles(is_public);
    """)


def _run_migrations(conn):
    if USE_POSTGRES:
        for sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_key     TEXT UNIQUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan           TEXT NOT NULL DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by_key TEXT",
        ]:
            try: conn.execute(sql)
            except Exception: pass
    else:
        existing = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        for col, sql in [
            ("invite_key",     "ALTER TABLE users ADD COLUMN invite_key     TEXT UNIQUE"),
            ("plan",           "ALTER TABLE users ADD COLUMN plan           TEXT NOT NULL DEFAULT 'free'"),
            ("invited_by_key", "ALTER TABLE users ADD COLUMN invited_by_key TEXT"),
        ]:
            if col not in existing:
                try: conn.execute(sql)
                except Exception: pass


# ── Connection Wrapper ────────────────────────────────────────────────────────

class _AdaptedConn:
    """
    Wrapper que normaliza a interface entre SQLite e PostgreSQL.
    - Traduz ? → %s para Postgres
    - Traduz datetime('now') → NOW()
    - Garante que rows retornam como dict em ambos os bancos
    - Expõe .execute(), .executemany(), .executescript(), .commit(), .close()
    """

    def __init__(self, raw_conn, is_postgres: bool):
        self._conn = raw_conn
        self._pg = is_postgres

    def _adapt(self, sql: str) -> str:
        if not self._pg:
            return sql
        import re
        sql = re.sub(r'(?<![\$%])\?', '%s', sql)
        sql = sql.replace("datetime('now')", 'NOW()')
        sql = re.sub(
            r"datetime\('now',\s*'(-?\d+)\s+days?'\)",
            lambda m: f"NOW() + INTERVAL '{m.group(1)} days'",
            sql
        )
        return sql

    def execute(self, sql: str, params=None):
        sql = self._adapt(sql)
        if self._pg:
            cur = self._conn.cursor()
            cur.execute(sql, params or ())
            return _PgResult(cur)
        else:
            return self._conn.execute(sql, params or ())

    def executemany(self, sql: str, params_list):
        sql = self._adapt(sql)
        if self._pg:
            cur = self._conn.cursor()
            cur.executemany(sql, params_list)
            return cur
        else:
            return self._conn.executemany(sql, params_list)

    def executescript(self, sql: str):
        if self._pg:
            cur = self._conn.cursor()
            cur.execute(sql)
            return cur
        else:
            return self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._conn.close()

    # row_factory compat
    @property
    def row_factory(self):
        return getattr(self._conn, 'row_factory', None)


class _PgResult:
    """Emula a interface sqlite3 para resultados PostgreSQL."""

    def __init__(self, cur):
        self._cur = cur

    @property
    def lastrowid(self):
        try:
            row = self._cur.fetchone()
            if row and 'id' in dict(row):
                return dict(row)['id']
        except Exception:
            pass
        return None

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in self._cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


if __name__ == '__main__':
    mode = 'PostgreSQL' if USE_POSTGRES else 'SQLite'
    print(f'Modo: {mode}')
    init_db()
    print('Banco inicializado com sucesso')
