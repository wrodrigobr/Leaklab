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
SQLITE_PATH = os.environ.get('LEAKLAB_DB', _LOCAL_DB)

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
            id                      SERIAL PRIMARY KEY,
            username                TEXT    NOT NULL UNIQUE,
            email                   TEXT    NOT NULL UNIQUE,
            password_hash           TEXT    NOT NULL,
            role                    TEXT    NOT NULL DEFAULT 'player',
            coach_id                INTEGER REFERENCES users(id),
            invite_key              TEXT    UNIQUE,
            plan                    TEXT    NOT NULL DEFAULT 'free',
            invited_by_key          TEXT,
            created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
            last_login              TIMESTAMP,
            tournaments_this_month  INTEGER NOT NULL DEFAULT 0,
            ai_calls_this_month     INTEGER NOT NULL DEFAULT 0,
            quota_reset_at          DATE
        );
        CREATE TABLE IF NOT EXISTS tournaments (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            tournament_id   TEXT    NOT NULL,
            site            TEXT    NOT NULL DEFAULT 'pokerstars',
            tournament_name TEXT,
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
            buy_in          REAL,
            prize           REAL,
            profit          REAL,
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
            position        TEXT,
            num_players     INTEGER,
            level_sb        REAL,
            level_bb        REAL,
            level_num       INTEGER,
            note            TEXT,
            is_3bet         BOOLEAN NOT NULL DEFAULT FALSE,
            showdown_result TEXT,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS coach_profiles (
            id                  SERIAL PRIMARY KEY,
            user_id             INTEGER NOT NULL UNIQUE REFERENCES users(id),
            display_name        TEXT    NOT NULL DEFAULT '',
            bio                 TEXT    NOT NULL DEFAULT '',
            specialties         TEXT    NOT NULL DEFAULT '[]',
            contact_email       TEXT,
            contact_link        TEXT,
            is_public           INTEGER NOT NULL DEFAULT 1,
            plan                TEXT    NOT NULL DEFAULT 'free',
            max_students        INTEGER NOT NULL DEFAULT 5,
            photo_url           TEXT,
            experience_years    INTEGER,
            stakes              TEXT,
            coaching_style      TEXT,
            languages           TEXT    NOT NULL DEFAULT '["pt"]',
            biggest_results     TEXT    NOT NULL DEFAULT '[]',
            price_per_session   REAL,
            price_monthly       REAL,
            trial_available     INTEGER NOT NULL DEFAULT 0,
            availability        TEXT,
            social_youtube      TEXT,
            social_twitch       TEXT,
            social_twitter      TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS coach_reviews (
            id           SERIAL PRIMARY KEY,
            coach_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating       INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            review_text  TEXT,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(coach_id, student_id)
        );
        CREATE INDEX IF NOT EXISTS idx_reviews_coach ON coach_reviews(coach_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_tournament ON decisions(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_label      ON decisions(label);
        CREATE INDEX IF NOT EXISTS idx_decisions_street     ON decisions(street);
        CREATE INDEX IF NOT EXISTS idx_tournaments_user     ON tournaments(user_id);
        CREATE INDEX IF NOT EXISTS idx_tournaments_played   ON tournaments(played_at);
        CREATE INDEX IF NOT EXISTS idx_coach_profiles_public ON coach_profiles(is_public);

        CREATE TABLE IF NOT EXISTS llm_cache (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            cache_key    TEXT NOT NULL,
            analysis     TEXT NOT NULL,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, cache_key)
        );
        CREATE INDEX IF NOT EXISTS idx_llm_cache_key ON llm_cache(user_id, cache_key);

        CREATE TABLE IF NOT EXISTS coach_study_overrides (
            id          SERIAL PRIMARY KEY,
            coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            card_spot   TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'validated',
            note        TEXT,
            custom_card TEXT,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(coach_id, student_id, card_spot)
        );
        CREATE TABLE IF NOT EXISTS coach_hand_annotations (
            id                   SERIAL PRIMARY KEY,
            coach_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            decision_id          INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
            comment              TEXT    NOT NULL,
            mode                 TEXT    NOT NULL DEFAULT 'complement',
            coach_action         TEXT,
            coach_override_label TEXT,
            created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(coach_id, student_id, decision_id)
        );
        CREATE INDEX IF NOT EXISTS idx_annotations_decision ON coach_hand_annotations(decision_id);
        CREATE INDEX IF NOT EXISTS idx_annotations_student  ON coach_hand_annotations(student_id);
        CREATE TABLE IF NOT EXISTS coach_baselines (
            id            SERIAL PRIMARY KEY,
            coach_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            baseline_date DATE    NOT NULL,
            note          TEXT,
            created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(coach_id, student_id)
        );
    """)


def _init_sqlite(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            username                TEXT    NOT NULL UNIQUE,
            email                   TEXT    NOT NULL UNIQUE,
            password_hash           TEXT    NOT NULL,
            role                    TEXT    NOT NULL DEFAULT 'player',
            coach_id                INTEGER REFERENCES users(id),
            invite_key              TEXT    UNIQUE,
            plan                    TEXT    NOT NULL DEFAULT 'free',
            invited_by_key          TEXT,
            created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login              TEXT,
            tournaments_this_month  INTEGER NOT NULL DEFAULT 0,
            ai_calls_this_month     INTEGER NOT NULL DEFAULT 0,
            quota_reset_at          TEXT
        );
        CREATE TABLE IF NOT EXISTS tournaments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            tournament_id   TEXT    NOT NULL,
            site            TEXT    NOT NULL DEFAULT 'pokerstars',
            tournament_name TEXT,
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
            buy_in          REAL,
            prize           REAL,
            profit          REAL,
            llm_summary     TEXT,
            raw_text        TEXT,
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
            position        TEXT,
            num_players     INTEGER,
            level_sb        REAL,
            level_bb        REAL,
            level_num       INTEGER,
            note            TEXT,
            is_3bet         INTEGER NOT NULL DEFAULT 0,
            showdown_result TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS coach_profiles (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL UNIQUE REFERENCES users(id),
            display_name        TEXT    NOT NULL DEFAULT '',
            bio                 TEXT    NOT NULL DEFAULT '',
            specialties         TEXT    NOT NULL DEFAULT '[]',
            contact_email       TEXT,
            contact_link        TEXT,
            is_public           INTEGER NOT NULL DEFAULT 1,
            plan                TEXT    NOT NULL DEFAULT 'free',
            max_students        INTEGER NOT NULL DEFAULT 5,
            photo_url           TEXT,
            experience_years    INTEGER,
            stakes              TEXT,
            coaching_style      TEXT,
            languages           TEXT    NOT NULL DEFAULT '["pt"]',
            biggest_results     TEXT    NOT NULL DEFAULT '[]',
            price_per_session   REAL,
            price_monthly       REAL,
            trial_available     INTEGER NOT NULL DEFAULT 0,
            availability        TEXT,
            social_youtube      TEXT,
            social_twitch       TEXT,
            social_twitter      TEXT,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS coach_reviews (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating       INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            review_text  TEXT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(coach_id, student_id)
        );
        CREATE INDEX IF NOT EXISTS idx_reviews_coach ON coach_reviews(coach_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_tournament ON decisions(tournament_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_label      ON decisions(label);
        CREATE INDEX IF NOT EXISTS idx_decisions_street     ON decisions(street);
        CREATE INDEX IF NOT EXISTS idx_tournaments_user     ON tournaments(user_id);
        CREATE INDEX IF NOT EXISTS idx_tournaments_played   ON tournaments(played_at);
        CREATE INDEX IF NOT EXISTS idx_coach_profiles_public ON coach_profiles(is_public);

        CREATE TABLE IF NOT EXISTS llm_cache (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            cache_key    TEXT NOT NULL,
            analysis     TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, cache_key)
        );
        CREATE INDEX IF NOT EXISTS idx_llm_cache_key ON llm_cache(user_id, cache_key);

        CREATE TABLE IF NOT EXISTS coach_study_overrides (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            card_spot   TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'validated',
            note        TEXT,
            custom_card TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(coach_id, student_id, card_spot)
        );
        CREATE TABLE IF NOT EXISTS coach_hand_annotations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            decision_id          INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
            comment              TEXT    NOT NULL,
            mode                 TEXT    NOT NULL DEFAULT 'complement',
            coach_action         TEXT,
            coach_override_label TEXT,
            created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(coach_id, student_id, decision_id)
        );
        CREATE INDEX IF NOT EXISTS idx_annotations_decision ON coach_hand_annotations(decision_id);
        CREATE INDEX IF NOT EXISTS idx_annotations_student  ON coach_hand_annotations(student_id);
        CREATE TABLE IF NOT EXISTS coach_baselines (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            student_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            baseline_date TEXT    NOT NULL,
            note          TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(coach_id, student_id)
        );
    """)


def _run_migrations(conn):
    if USE_POSTGRES:
        for sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_key     TEXT UNIQUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan           TEXT NOT NULL DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by_key TEXT",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS buy_in REAL",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS prize  REAL",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS profit REAL",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS raw_text TEXT",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tournament_name TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS position    TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS num_players INTEGER",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS level_sb    REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS level_bb    REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS level_num   INTEGER",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS note        TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS is_3bet         BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS showdown_result TEXT",
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS coach_override_label TEXT",
            # Sprint 9 — BACK-010: quota tracking
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS tournaments_this_month INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_calls_this_month     INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_reset_at          DATE",
            # Sprint 7 — BACK-006: perfil estendido + reviews
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS photo_url         TEXT",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS experience_years  INTEGER",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS stakes            TEXT",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS coaching_style    TEXT",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS languages         TEXT NOT NULL DEFAULT '[\"pt\"]'",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS biggest_results   TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS price_per_session REAL",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS price_monthly     REAL",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS trial_available   INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS availability      TEXT",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS social_youtube    TEXT",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS social_twitch     TEXT",
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS social_twitter    TEXT",
            # Sprint 12 — BACK-011 pt.2: content moderation
            "ALTER TABLE coach_profiles          ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved'",
            "ALTER TABLE coach_reviews            ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved'",
            "ALTER TABLE coach_hand_annotations   ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved'",
            # Sprint 15 — BACK-015: Mercado Pago
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mp_subscription_id TEXT",
        ]:
            try: conn.execute(sql)
            except Exception: pass
        # coach_reviews table (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_reviews (
                    id                SERIAL PRIMARY KEY,
                    coach_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    student_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    rating            INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    review_text       TEXT,
                    moderation_status TEXT    NOT NULL DEFAULT 'approved',
                    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(coach_id, student_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_coach ON coach_reviews(coach_id)")
        except Exception: pass
        # payments table (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id             SERIAL PRIMARY KEY,
                    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    plan           TEXT    NOT NULL,
                    amount_cents   INTEGER NOT NULL,
                    currency       TEXT    NOT NULL DEFAULT 'BRL',
                    status         TEXT    NOT NULL,
                    gateway        TEXT    NOT NULL DEFAULT 'mercadopago',
                    gateway_id     TEXT,
                    gateway_sub_id TEXT,
                    period_start   DATE,
                    period_end     DATE,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)")
        except Exception: pass
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_baselines (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                baseline_date TEXT    NOT NULL,
                note          TEXT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(coach_id, student_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_hand_annotations (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                decision_id          INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                comment              TEXT    NOT NULL,
                mode                 TEXT    NOT NULL DEFAULT 'complement',
                coach_action         TEXT,
                coach_override_label TEXT,
                created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(coach_id, student_id, decision_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_annotations_decision ON coach_hand_annotations(decision_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_annotations_student  ON coach_hand_annotations(student_id)")
        # coach_study_overrides (SQLite CREATE IF NOT EXISTS handles it)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_study_overrides (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                card_spot   TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'validated',
                note        TEXT,
                custom_card TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(coach_id, student_id, card_spot)
            )
        """)
        existing = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        for col, sql in [
            ("invite_key",              "ALTER TABLE users ADD COLUMN invite_key              TEXT UNIQUE"),
            ("plan",                    "ALTER TABLE users ADD COLUMN plan                    TEXT NOT NULL DEFAULT 'free'"),
            ("invited_by_key",          "ALTER TABLE users ADD COLUMN invited_by_key          TEXT"),
            ("tournaments_this_month",  "ALTER TABLE users ADD COLUMN tournaments_this_month  INTEGER NOT NULL DEFAULT 0"),
            ("ai_calls_this_month",     "ALTER TABLE users ADD COLUMN ai_calls_this_month     INTEGER NOT NULL DEFAULT 0"),
            ("quota_reset_at",          "ALTER TABLE users ADD COLUMN quota_reset_at          TEXT"),
            ("buy_in",          "ALTER TABLE tournaments ADD COLUMN buy_in REAL"),
            ("prize",           "ALTER TABLE tournaments ADD COLUMN prize  REAL"),
            ("profit",          "ALTER TABLE tournaments ADD COLUMN profit REAL"),
            ("raw_text",        "ALTER TABLE tournaments ADD COLUMN raw_text TEXT"),
            ("tournament_name", "ALTER TABLE tournaments ADD COLUMN tournament_name TEXT"),
        ]:
            if col not in existing:
                try: conn.execute(sql)
                except Exception: pass
        ann_existing = {r[1] for r in conn.execute('PRAGMA table_info(coach_hand_annotations)').fetchall()}
        if 'coach_override_label' not in ann_existing:
            try: conn.execute("ALTER TABLE coach_hand_annotations ADD COLUMN coach_override_label TEXT")
            except Exception: pass
        dec_existing = {r[1] for r in conn.execute('PRAGMA table_info(decisions)').fetchall()}
        for col, sql in [
            ("position",    "ALTER TABLE decisions ADD COLUMN position    TEXT"),
            ("num_players", "ALTER TABLE decisions ADD COLUMN num_players INTEGER"),
            ("level_sb",    "ALTER TABLE decisions ADD COLUMN level_sb    REAL"),
            ("level_bb",    "ALTER TABLE decisions ADD COLUMN level_bb    REAL"),
            ("level_num",   "ALTER TABLE decisions ADD COLUMN level_num   INTEGER"),
            ("note",            "ALTER TABLE decisions ADD COLUMN note            TEXT"),
            ("is_3bet",         "ALTER TABLE decisions ADD COLUMN is_3bet         INTEGER NOT NULL DEFAULT 0"),
            ("showdown_result", "ALTER TABLE decisions ADD COLUMN showdown_result TEXT"),
        ]:
            if col not in dec_existing:
                try: conn.execute(sql)
                except Exception: pass
        # Sprint 7 — BACK-006: perfil estendido
        prof_existing = {r[1] for r in conn.execute('PRAGMA table_info(coach_profiles)').fetchall()}
        for col, sql in [
            ("photo_url",         "ALTER TABLE coach_profiles ADD COLUMN photo_url         TEXT"),
            ("experience_years",  "ALTER TABLE coach_profiles ADD COLUMN experience_years  INTEGER"),
            ("stakes",            "ALTER TABLE coach_profiles ADD COLUMN stakes            TEXT"),
            ("coaching_style",    "ALTER TABLE coach_profiles ADD COLUMN coaching_style    TEXT"),
            ("languages",         "ALTER TABLE coach_profiles ADD COLUMN languages         TEXT NOT NULL DEFAULT '[\"pt\"]'"),
            ("biggest_results",   "ALTER TABLE coach_profiles ADD COLUMN biggest_results   TEXT NOT NULL DEFAULT '[]'"),
            ("price_per_session", "ALTER TABLE coach_profiles ADD COLUMN price_per_session REAL"),
            ("price_monthly",     "ALTER TABLE coach_profiles ADD COLUMN price_monthly     REAL"),
            ("trial_available",   "ALTER TABLE coach_profiles ADD COLUMN trial_available   INTEGER NOT NULL DEFAULT 0"),
            ("availability",      "ALTER TABLE coach_profiles ADD COLUMN availability      TEXT"),
            ("social_youtube",    "ALTER TABLE coach_profiles ADD COLUMN social_youtube    TEXT"),
            ("social_twitch",     "ALTER TABLE coach_profiles ADD COLUMN social_twitch     TEXT"),
            ("social_twitter",    "ALTER TABLE coach_profiles ADD COLUMN social_twitter    TEXT"),
            # Sprint 12 — BACK-011 pt.2: content moderation
            ("moderation_status", "ALTER TABLE coach_profiles ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'approved'"),
        ]:
            if col not in prof_existing:
                try: conn.execute(sql)
                except Exception: pass
        # coach_reviews (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_reviews (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                rating            INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                review_text       TEXT,
                moderation_status TEXT    NOT NULL DEFAULT 'approved',
                created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(coach_id, student_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_coach ON coach_reviews(coach_id)")
        # migrate existing coach_reviews + coach_hand_annotations
        rev_existing = {r[1] for r in conn.execute('PRAGMA table_info(coach_reviews)').fetchall()}
        if 'moderation_status' not in rev_existing:
            try: conn.execute("ALTER TABLE coach_reviews ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'approved'")
            except Exception: pass
        ann2_existing = {r[1] for r in conn.execute('PRAGMA table_info(coach_hand_annotations)').fetchall()}
        if 'moderation_status' not in ann2_existing:
            try: conn.execute("ALTER TABLE coach_hand_annotations ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'approved'")
            except Exception: pass
        # payments table (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan           TEXT    NOT NULL,
                amount_cents   INTEGER NOT NULL,
                currency       TEXT    NOT NULL DEFAULT 'BRL',
                status         TEXT    NOT NULL,
                gateway        TEXT    NOT NULL DEFAULT 'mercadopago',
                gateway_id     TEXT,
                gateway_sub_id TEXT,
                period_start   TEXT,
                period_end     TEXT,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)")
        # migrate users: mp_subscription_id
        usr_existing = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        if 'mp_subscription_id' not in usr_existing:
            try: conn.execute("ALTER TABLE users ADD COLUMN mp_subscription_id TEXT")
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
            # Pass None (not empty tuple) when no params so psycopg2 uses PQexec
            # which supports multi-statement SQL (used in _init_postgres).
            cur.execute(sql, params if params else None)
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
