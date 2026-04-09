"""
schema.py — Definição do banco de dados SQLite via sqlite3 puro.
Sem ORM — mantém dependências zero além da stdlib.

Tabelas:
  users        — jogadores/coaches
  tournaments  — torneios analisados
  decisions    — cada decisão individual (coração do histórico)
  sessions     — agregado de análise por torneio (cache de métricas)
"""
import sqlite3
import os

DB_PATH = os.environ.get('GAPHUNTER_DB', os.path.join(
    os.path.dirname(__file__), '..', 'data', 'gaphunter.db'
))


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    """Cria todas as tabelas se não existirem."""
    conn = get_conn()
    conn.executescript("""

    -- Usuários
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

    -- Torneios
    CREATE TABLE IF NOT EXISTS tournaments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL REFERENCES users(id),
        tournament_id   TEXT    NOT NULL,   -- ID do PokerStars/GGPoker
        site            TEXT    NOT NULL DEFAULT 'pokerstars',
        hero            TEXT    NOT NULL,
        played_at       TEXT,               -- data do torneio
        imported_at     TEXT    NOT NULL DEFAULT (datetime('now')),
        hands_count     INTEGER NOT NULL DEFAULT 0,
        decisions_count INTEGER NOT NULL DEFAULT 0,
        avg_score       REAL,
        standard_pct    REAL,
        marginal_pct    REAL,
        small_pct       REAL,
        clear_pct       REAL,
        result          TEXT,               -- itm | elim
        place           INTEGER,
        llm_summary     TEXT,               -- cache do resumo LLM
        UNIQUE(user_id, tournament_id)
    );

    -- Decisões individuais (granular — base do histórico)
    CREATE TABLE IF NOT EXISTS decisions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id   INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
        hand_id         TEXT    NOT NULL,
        street          TEXT    NOT NULL,
        hero_cards      TEXT,
        board           TEXT,               -- JSON array
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

    -- Índices para queries de evolução
    CREATE INDEX IF NOT EXISTS idx_decisions_tournament ON decisions(tournament_id);
    CREATE INDEX IF NOT EXISTS idx_decisions_label      ON decisions(label);
    CREATE INDEX IF NOT EXISTS idx_decisions_street     ON decisions(street);
    CREATE INDEX IF NOT EXISTS idx_tournaments_user     ON tournaments(user_id);
    CREATE INDEX IF NOT EXISTS idx_tournaments_played   ON tournaments(played_at);

    -- Perfil público do coach
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

    CREATE INDEX IF NOT EXISTS idx_coach_profiles_public ON coach_profiles(is_public);

    """)

    _run_migrations(conn)
    conn.commit()
    conn.close()
    return DB_PATH


def _run_migrations(conn):
    """Aplica migrações incrementais sem recriar tabelas existentes."""
    existing_cols = {
        row[1] for row in
        conn.execute("PRAGMA table_info(users)").fetchall()
    }
    migrations = [
        ("invite_key",     "ALTER TABLE users ADD COLUMN invite_key     TEXT UNIQUE"),
        ("plan",           "ALTER TABLE users ADD COLUMN plan           TEXT NOT NULL DEFAULT 'free'"),
        ("invited_by_key", "ALTER TABLE users ADD COLUMN invited_by_key TEXT"),
    ]
    for col, sql in migrations:
        if col not in existing_cols:
            try:
                conn.execute(sql)
            except Exception:
                pass


if __name__ == '__main__':
    path = init_db()
    print(f'Banco criado em: {path}')
    conn = get_conn()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f'Tabelas: {[t[0] for t in tables]}')
    conn.close()
