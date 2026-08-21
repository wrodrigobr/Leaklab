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

# ── Pool de conexões (SÓ PostgreSQL) ──────────────────────────────────────────
#
# **O problema, medido em produção 2026-08-02:** abrir uma conexão custa ~72ms e o `SELECT 1`
# depois dela custa 19ms. O custo dominante de quase toda consulta é DISCAR, não consultar. Um
# endpoint que toca o banco 6 vezes paga ~430ms só de handshake. A URL já aponta para o endpoint
# `-pooler` do Neon (PgBouncer), então o pool do lado do SERVIDOR já existe — o que se paga é o
# TCP+TLS do nosso container até ele, e só pool no CLIENTE elimina isso.
#
# **A regra de desenho é que ele nunca invente um modo de falha novo.** Pool exausto, conexão
# quebrada, driver reclamando: tudo cai no `psycopg2.connect` direto de antes. O pior caso é a
# lentidão de hoje, jamais um erro que hoje não existe. `LEAKLAB_DB_POOL=0` desliga tudo.
#
# **Três coisas que este código precisa acertar e que um pool ingênuo erra:**
#
# 1. **Aninhamento.** Medido: `get_xp_status` segura uma conexão e chama `get_achievements`, que
#    abre outra — profundidade 2 em código real. Um cache de UMA conexão por processo devolveria
#    a mesma para as duas e a de dentro a liberaria embaixo da de fora. Por isso é pool, com N.
# 2. **Transação aberta.** `_AdaptedConn.__exit__` fecha SEM commitar. Devolver assim ao pool
#    entregaria a transação suja ao próximo. O `putconn` do psycopg2 já faz rollback nesse caso;
#    dependemos disso de propósito, em vez de reimplementar.
# 3. **Conexão morta em silêncio.** Se o servidor derruba, `conn.closed` continua 0 e o status
#    continua IDLE — o cliente só descobre na próxima consulta. Daí a idade máxima ociosa e o
#    ping; ver `_pega_do_pool`.

_POOL_LIGADO = os.environ.get('LEAKLAB_DB_POOL', '1').lower() not in ('0', 'false', 'no')
_POOL_MAX = int(os.environ.get('LEAKLAB_DB_POOL_MAX', '8') or 8)

# Ociosa além disto, a conexão é DESCARTADA em vez de reusada: nunca fica pior que hoje, porque
# o pior caso é discar de novo, que é exatamente o que se fazia sempre.
_POOL_DESCARTA_APOS_S = float(os.environ.get('LEAKLAB_DB_POOL_MAX_IDLE', '60') or 60)
# Ociosa além disto, confere com um ping antes de entregar. Abaixo disto entrega direto — é o caso
# comum (mesma requisição, consultas em sequência) e onde está o ganho inteiro.
_POOL_PING_APOS_S = float(os.environ.get('LEAKLAB_DB_POOL_PING_AFTER', '5') or 5)

# Quantas ficam QUENTES. Não é enfeite: `_putconn` do psycopg2 é
# `if len(self._pool) < self.minconn and not close:` — ele RETÉM até `minconn` e **fecha** todo o
# resto. Com `minconn=1` só uma ficava quente, e toda chamada aninhada (profundidade 2, medida em
# código real) pagava os 72ms de novo. O `maxconn` é o teto de simultâneas, não o de reuso.
_POOL_MIN = max(1, min(int(os.environ.get('LEAKLAB_DB_POOL_MIN', '4') or 4), _POOL_MAX))

_pool = None
_pool_pid = None          # gunicorn dá fork: pool herdado é socket compartilhado entre processos
_pool_ocioso_desde = {}   # conexão -> instante em que voltou ao pool


def _conecta_pg():
    """A conexão crua, sem pool. É também o fallback de tudo que der errado no pool."""
    import psycopg2
    import psycopg2.extras
    raw = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    raw.autocommit = False
    return raw


def _pool_do_processo():
    """O pool DESTE processo. Recriado quando o PID muda.

    Sem isso, os workers do gunicorn herdariam do pai um pool cujos sockets são os MESMOS
    descritores em processos diferentes — dois workers escrevendo no mesmo socket é corrupção de
    protocolo, não lentidão.
    """
    global _pool, _pool_pid
    pid = os.getpid()
    if _pool is not None and _pool_pid == pid:
        return _pool
    if _pool is not None:
        # herdado de outro processo: abandona sem fechar (os sockets são do pai)
        _pool_ocioso_desde.clear()
    import psycopg2.extras
    from psycopg2.pool import ThreadedConnectionPool
    _pool = ThreadedConnectionPool(_POOL_MIN, _POOL_MAX, DATABASE_URL,
                                   cursor_factory=psycopg2.extras.RealDictCursor)
    _pool_pid = pid
    return _pool


def _descarta(pool, raw):
    _pool_ocioso_desde.pop(raw, None)
    try:
        pool.putconn(raw, close=True)
    except Exception:
        try:
            raw.close()
        except Exception:
            pass


def _viva(raw, ocioso_ha):
    """A conexão responde? Só pergunta quando vale a pena perguntar.

    Ociosa há pouco (o caso comum: várias consultas na mesma requisição) entrega sem ping — é aí
    que mora o ganho. Ociosa há mais tempo paga um round-trip, que ainda é bem menos que discar.
    """
    if raw.closed:
        return False
    try:
        import psycopg2.extensions as _ext
        if raw.get_transaction_status() == _ext.TRANSACTION_STATUS_UNKNOWN:
            return False
    except Exception:
        return False
    if ocioso_ha < _POOL_PING_APOS_S:
        return True
    try:
        cur = raw.cursor()
        cur.execute('SELECT 1')
        cur.fetchone()
        cur.close()
        # O ping ABRE uma transação (psycopg2 não é autocommit). Sem desfazê-la, a conexão sai
        # daqui dentro de uma transação já aberta — e a linha seguinte, `raw.autocommit = False`,
        # vira `set_session cannot be used inside a transaction` e derruba o worker no boot.
        # Foi o que tirou produção do ar: antes o ping quase nunca rodava, então este caminho não
        # era exercitado; consertar o ping o tornou o caminho NORMAL.
        # Além do crash, entregar conexão com transação aberta daria snapshot velho na 1a leitura.
        raw.rollback()
        return True
    except Exception:
        return False


def _pega_do_pool():
    """`(conexão, devolver)`. `devolver` é None quando a conexão não é do pool (fallback)."""
    import time
    try:
        pool = _pool_do_processo()
    except Exception:
        return _conecta_pg(), None            # pool nem subiu: segue como sempre foi
    for _ in range(_POOL_MAX + 1):
        try:
            raw = pool.getconn()
        except Exception:
            # exausto (aninhamento fundo, concorrência) ou pool em erro: nunca falha a requisição
            return _conecta_pg(), None
        # **Idade DESCONHECIDA não é idade zero.** O pool cria `minconn` conexões no construtor, e
        # essas nunca passaram por `_devolve_ao_pool` — não estão no dicionário. A primeira versão
        # daqui usava `pop(raw, time.monotonic())`, que faz o desconhecido ler como recém-criado:
        # a conexão era entregue SEM ping, viva ou morta. Derrubou o `/health` em produção com
        # `{"db": false}` e 503, cerca de uma em cinco, medido de fora.
        #
        # Desconhecido agora força o ping, sem forçar o descarte: se responder, reusa; se não,
        # descarta. Em toda decisão deste bloco, o que não se sabe pesa contra reusar.
        _marcado = _pool_ocioso_desde.pop(raw, None)
        ocioso_ha = (time.monotonic() - _marcado) if _marcado is not None else _POOL_PING_APOS_S
        if ocioso_ha > _POOL_DESCARTA_APOS_S or not _viva(raw, ocioso_ha):
            _descarta(pool, raw)
            continue
        # Só ESCREVE se precisar. Atribuir `autocommit` chama `set_session`, que o psycopg2
        # proíbe dentro de transação — ler antes custa nada e tira a chamada do caminho comum.
        if raw.autocommit:
            raw.autocommit = False
        return raw, (lambda c=raw: _devolve_ao_pool(pool, c))
    return _conecta_pg(), None


def _devolve_ao_pool(pool, raw):
    """Devolve. O `putconn` do psycopg2 faz o rollback da transação aberta e descarta a conexão
    perdida — ver o item 2 do comentário do topo."""
    import time
    try:
        _pool_ocioso_desde[raw] = time.monotonic()
        pool.putconn(raw)
        # O putconn FECHA a conexão perdida em vez de devolvê-la, e sem levantar. Sem esta linha
        # a entrada ficaria órfã no dicionário para sempre — uma por conexão quebrada, num
        # processo que vive dias.
        if raw.closed:
            _pool_ocioso_desde.pop(raw, None)
    except Exception:
        _pool_ocioso_desde.pop(raw, None)
        try:
            raw.close()
        except Exception:
            pass


# ── Conexão ───────────────────────────────────────────────────────────────────

def get_conn() -> _AdaptedConn:
    """Retorna conexão adaptada: PostgreSQL (produção) ou SQLite (dev)."""
    if USE_POSTGRES:
        if _POOL_LIGADO:
            raw, devolver = _pega_do_pool()
            return _AdaptedConn(raw, True, _devolver=devolver)
        raw = _conecta_pg()
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
            # Evita corrida de migração quando vários workers do gunicorn sobem juntos:
            # advisory lock transacional serializa — o 2º processo espera o 1º commitar
            # (e aí o schema já existe, virando no-op). Sem isso, DDLs concorrentes podem
            # dar deadlock no boot de um banco novo.
            conn.execute("SELECT pg_advisory_xact_lock(81234567)")
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
            icm_tax_pct     REAL,
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
            pot_size         REAL,
            facing_bet       REAL,
            estimated_equity REAL,
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
            social_instagram    TEXT,
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
            icm_tax_pct     REAL,
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
            pot_size         REAL,
            facing_bet       REAL,
            estimated_equity REAL,
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
            social_instagram    TEXT,
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


def _pg_exec_isolated(conn, sql):
    """Executa 1 DDL de migração no Postgres isolando a falha por SAVEPOINT. Sem isso, um statement
    que aborta (mesmo com o erro engolido) deixa a transação inteira 'aborted' → TODAS as migrations
    seguintes viram no-op e nada commita (foi o que segurou started_at/field_size num deploy). Com o
    SAVEPOINT, o erro faz ROLLBACK só desse statement e a transação (e o advisory lock do boot)
    segue viva pros próximos."""
    try:
        conn.execute("SAVEPOINT _mig_sp")
        conn.execute(sql)
        conn.execute("RELEASE SAVEPOINT _mig_sp")
    except Exception:
        try:
            conn.execute("ROLLBACK TO SAVEPOINT _mig_sp")
        except Exception:
            pass


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
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS labels_reconciled_at TIMESTAMP",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS is_pko BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS started_at TIMESTAMP",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS ended_at   TIMESTAMP",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS field_size INTEGER",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS prize_pool REAL",
            "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS re_entries INTEGER",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS position    TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS num_players INTEGER",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS level_sb    REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS level_bb    REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS level_num   INTEGER",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS note        TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS is_3bet         BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS showdown_result TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS pot_size        REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS facing_bet      REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS n_active_opponents INTEGER",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS multiway_safe_verdict TEXT",  # #30 shadow: safe_fold|safe_value|NULL
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS coach_override_label TEXT",
            # Sprint 9 — BACK-010: quota tracking
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS tournaments_this_month INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_calls_this_month     INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS solves_this_month       INTEGER NOT NULL DEFAULT 0",  # #26 cota de solves
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_reset_at          DATE",
            # Fase 2 planos — tetos DIÁRIOS (fair-use anti-abuso) + reset diário
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_chat_today           INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS solves_today            INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_day_reset_at       DATE",
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
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS social_instagram  TEXT",
            # Sprint 12 — BACK-011 pt.2: content moderation
            "ALTER TABLE coach_profiles          ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved'",
            "ALTER TABLE coach_reviews            ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved'",
            "ALTER TABLE coach_hand_annotations   ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved'",
            # Sprint 15 — BACK-015: Mercado Pago
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mp_subscription_id TEXT",
            # Sprint C — BACK-014 + BACK-017: revenue share + admin panel
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_coach_id INTEGER REFERENCES users(id)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended BOOLEAN NOT NULL DEFAULT FALSE",
            # Sprint D — BACK-016: WhatsApp Coaching Drills
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_phone TEXT UNIQUE",
            # Sprint AI — BACK-019: demographic profile
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_year               INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS country                  TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS state_province           TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS city                     TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS poker_experience_years   INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS main_game_type           TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS usual_buyin_range        TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completed_at     TIMESTAMP",
            # Sprint AL — UX-017: dashboard layout personalizável
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS dashboard_layout         TEXT",
            # Sprint AX — FEAT-17: onboarding para novos usuários
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed     BOOLEAN NOT NULL DEFAULT FALSE",
            # SEC-01: atribuição confiável de indicação (convite single-use resgatado)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_via_invite_id    INTEGER",
            # SEC-01 fase 2: aprovação do coach (legados/existentes = approved)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS link_status              TEXT NOT NULL DEFAULT 'approved'",
            # COACH-02: Pro de cortesia do coach. plan_source: NULL=pago/legado,
            # 'coach_trial' (3 meses no onboarding), 'coach_earned' (meta de 15 batida).
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_source              TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS coach_trial_ends_at      TEXT",
            # PAY-02: vigência da assinatura (mensal=+30d, anual=+365d). NULL=sem
            # expiração (pagantes legados grandfathered). Pro expira quando passa a data.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at          TEXT",
            # Status real da assinatura Stripe: 'active' | 'past_due' | 'canceled' | NULL.
            # Antes o past_due era silenciosamente mantido como plan='pro' (dunning), então
            # coach/admin não distinguiam pagante-em-dia de atrasado. Persistido p/ a visão real.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status      TEXT",
            # GTO-005: integração solver → decisions
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS gto_label  TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS gto_action TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS gto_depth_capped INTEGER NOT NULL DEFAULT 0",  # opção B: GTO aproximado (>60bb)
            # GTO-006: armazenar equity estimada para re-avaliação
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS estimated_equity REAL",
            # GTO-007: posição do opener para spots vs_RFI
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS vs_position TEXT",
            # ICM leak detector: ICM tax (chip% − equity ICM%) na mesa final
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS icm_tax_pct REAL",
            # Squeeze/3-bet fix: nº de raises de villains enfrentados pelo hero preflop
            # (open=1, 3bet/squeeze=2…). Sinal durável p/ os syncs não tratarem squeeze como vs_RFI.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS preflop_raises_faced INTEGER",
            # Results×GTO (#5): hero coletou o pote nesta mão? (1/0/NULL) — base do
            # insight "ganhei mas joguei errado pelo GTO" (resultado ≠ processo).
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS hero_won_hand INTEGER",
            # EV-loss (#24): bb perdidos vs a melhor ação, pra a mão do hero (preflop).
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS ev_loss_bb REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS ev_loss_source TEXT",
            # Tamanho do PRÓPRIO raise do hero (raise-to em bb). facing_bet é o do VILÃO; sem
            # esta coluna o sizing do hero só existia recalculado ao vivo no /replay e não
            # podia ser agregado ao longo do tempo — logo, não virava leak nem missão.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS raise_to_bb REAL",
            # Quanto o hero precisa PAGAR, em bb. `facing_bet` é o TAMANHO da aposta do vilão
            # (to-total) e identifica o nó GTO; os dois divergem sempre que o hero já tem fichas
            # na frente. Sem esta coluna a tela do drill calculava pot odds com a aposta cheia.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS facing_to_call_bb REAL",
            # Stack EFETIVO em bb — min(eu, vilão) em heads-up. `stack_bb` guarda o
            # `heroStackBb`, que é OUTRA quantidade: medido, os dois diferem em 44% do preflop
            # (casos de 3,0bb efetivos contra 15,0bb do hero). Quem consulta range preflop a
            # partir da linha precisa do efetivo, que é o que o motor usa.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS effective_stack_bb REAL",
            # Pote LIMPADO. O pipeline calcula isto na hora do parse e o `/analyze` passa pro
            # provider preflop, mas até agora ele MORRIA ali: não havia coluna. Quem reconstrói
            # veredito a partir da linha (o `sync_gto_labels_from_ranges`, que roda depois de todo
            # DELETE+INSERT do `save_decisions`) não tinha como saber que o pote fora limpado, e
            # devolvia null MUDO — 46 decisões do acervo de produção. `facing_bet = 0` não
            # substitui: fora do BB ele também vale quando todo mundo foldou, que é RFI, não limp.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS facing_limp INTEGER",
            # Hero JA TINHA agredido nesta street antes desta decisao. O `sync` usava `is_3bet`
            # como proxy ("hero deu 3bet") e o proprio comentario dele admitia o chute. Medido em
            # 05/08 por ablacao um-a-um: o proxy era a causa de 9 das 11 divergencias entre o
            # sync e o motor no preflop — e ele decide o CENARIO (vs_3bet x vs_rfi x faces_squeeze
            # x vs_4bet), ou seja, qual range e consultada.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS hero_was_aggressor INTEGER",
            # ── Identidade ESTAVEL da anotacao do coach ────────────────────────────────────
            # `coach_hand_annotations.decision_id` tem FK ON DELETE CASCADE, e `save_decisions`
            # faz DELETE+INSERT por torneio: **todo reprocesso apagava as anotacoes do coach**.
            # Aconteceu de verdade em 05/08 — 71 comentarios sumiram e so voltaram porque eu
            # tinha um export por acaso. O `decision_id` nasce outro a cada reprocesso; estas
            # colunas descrevem a decisao de um jeito que sobrevive a reescrita.
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS tournament_id INTEGER",
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS hand_id TEXT",
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS street TEXT",
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS action_taken TEXT",
            # Ordinal DENTRO da chave: `(mao, street, acao)` NAO e unica — o hero age duas vezes
            # na mesma street sempre que paga e depois enfrenta um raise.
            "ALTER TABLE coach_hand_annotations ADD COLUMN IF NOT EXISTS ordinal INTEGER",
            # #15 leaderboard — opt-in/privacidade: aparecer no ranking público é consentido
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS leaderboard_opt_in BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS leaderboard_handle TEXT",
            # handle único, case-insensitive (só p/ quem definiu) — rede de segurança além da checagem no repo
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lb_handle ON users (LOWER(leaderboard_handle)) WHERE leaderboard_handle IS NOT NULL",
        ]:
            _pg_exec_isolated(conn, sql)
        # SEC-01: convites single-use do coach (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_invites (
                    id          SERIAL PRIMARY KEY,
                    coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    code        TEXT    NOT NULL UNIQUE,
                    status      TEXT    NOT NULL DEFAULT 'active',
                    used_by     INTEGER REFERENCES users(id),
                    used_at     TIMESTAMP,
                    expires_at  TIMESTAMP,
                    label       TEXT,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_invites_coach ON coach_invites(coach_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_invites_code  ON coach_invites(code)")
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
        # coach_payments table (Postgres) — BACK-014 revenue share
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_payments (
                    id              SERIAL PRIMARY KEY,
                    coach_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    period          TEXT    NOT NULL,
                    active_students INTEGER NOT NULL DEFAULT 0,
                    amount_cents    INTEGER NOT NULL DEFAULT 0,
                    status          TEXT    NOT NULL DEFAULT 'pending',
                    paid_at         TIMESTAMP,
                    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(coach_id, period)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_payments_coach ON coach_payments(coach_id)")
        except Exception: pass
        # ADMIN-FIN: despesas (saídas) — cockpit financeiro precisa delas p/ net real.
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id            SERIAL PRIMARY KEY,
                    category      TEXT    NOT NULL,        -- infra|llm|solver|domain|gateway_fee|ads|other
                    vendor        TEXT,
                    amount_cents  INTEGER NOT NULL DEFAULT 0,
                    currency      TEXT    NOT NULL DEFAULT 'BRL',
                    recurrence    TEXT    NOT NULL DEFAULT 'monthly',  -- monthly|annual|one_off
                    due_day       INTEGER,               -- dia do mês p/ recorrentes (calendário)
                    period        TEXT,                  -- 'YYYY-MM' do custo avulso
                    status        TEXT    NOT NULL DEFAULT 'forecast', -- forecast|due|paid
                    paid_at       TIMESTAMP,
                    note          TEXT,
                    active        INTEGER NOT NULL DEFAULT 1,  -- recorrente ativo (0=encerrado)
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_period ON expenses(period)")
        except Exception: pass
        # ADMIN-FIN: vencimento do repasse (calendário) + churn no tempo + dunning.
        for _c in [
            "ALTER TABLE coach_payments ADD COLUMN IF NOT EXISTS due_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS canceled_at    TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS past_due_since TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS cancel_reason  TEXT",  # motivo do churn (Stripe cancellation_details)
        ]:
            try: conn.execute(_c)
            except Exception: pass
        # drill_sessions table (Postgres) — Sprint K: Ghost Table Simulator
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS drill_sessions (
                    id             SERIAL PRIMARY KEY,
                    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    decision_id    INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                    new_action     TEXT    NOT NULL,
                    new_score      REAL    NOT NULL,
                    original_score REAL    NOT NULL,
                    delta          REAL    NOT NULL,
                    drilled_at     TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_drill_user ON drill_sessions(user_id, drilled_at)")
        except Exception: pass
        # Gamificação de treino (Fase 1): domínio por categoria de leak (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_skill_progress (
                    id                SERIAL PRIMARY KEY,
                    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    category_key      TEXT    NOT NULL,
                    attempts          INTEGER NOT NULL DEFAULT 0,
                    correct           INTEGER NOT NULL DEFAULT 0,
                    mastery_ema       REAL    NOT NULL DEFAULT 0,
                    mastery           REAL    NOT NULL DEFAULT 0,
                    last_practiced_at TIMESTAMP,
                    UNIQUE(user_id, category_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_training_skill_user ON training_skill_progress(user_id)")
        except Exception: pass
        # Protocolo de Progressão: tentativas COM ESTRATO (Postgres). Bloco abort-proof próprio —
        # em PG uma falha aqui aborta a transação inteira e derruba as migrações seguintes.
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS progression_attempts (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    category_key TEXT    NOT NULL,
                    stratum      TEXT    NOT NULL,
                    block_kind   TEXT,
                    correct      INTEGER NOT NULL DEFAULT 0,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prog_attempt_user_cat "
                         "ON progression_attempts(user_id, category_key, id)")
        except Exception: pass
        # Conquistas EXCLUSIVAS do treino (separadas das globais/ELO) — Postgres
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_achievements (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    achievement_key TEXT    NOT NULL,
                    earned_at       TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, achievement_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_training_ach_user ON training_achievements(user_id)")
        except Exception: pass
        # Missões diárias de treino (Fase 2) — contadores do dia + missões resgatadas (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_daily (
                    id        SERIAL PRIMARY KEY,
                    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    day       TEXT    NOT NULL,
                    spots     INTEGER NOT NULL DEFAULT 0,
                    correct   INTEGER NOT NULL DEFAULT 0,
                    claimed   TEXT    NOT NULL DEFAULT '',
                    UNIQUE(user_id, day)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_training_daily_user ON training_daily(user_id, day)")
        except Exception: pass
        # "Provar" (Fase 4): baseline de aderência REAL da categoria, congelado quando o jogador
        # começou a treinar — pro loop treino→jogo→prova comparar antes×depois (Postgres).
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_proof (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    category_key TEXT    NOT NULL,
                    baseline_pct REAL    NOT NULL DEFAULT 0,
                    baseline_n   INTEGER NOT NULL DEFAULT 0,
                    baseline_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, category_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_training_proof_user ON training_proof(user_id)")
        except Exception: pass
        # Sprint R — FEAT-05: SRS columns on drill_sessions (Postgres)
        #
        # ESTES TRÊS `ALTER` MATARAM TODA A MIGRAÇÃO DE BOOT EM PRODUÇÃO, e por meses.
        #
        # Estavam sem `IF NOT EXISTS`, dentro de `try/except: pass`. Na PRIMEIRA vez rodaram e
        # criaram as colunas. Da segunda em diante, `DuplicateColumn` — e no Postgres um erro
        # **aborta a transação inteira**. O `except` engolia o erro, e todo statement seguinte
        # virava `InFailedSqlTransaction` em silêncio, incluindo o `conn.commit()` do fim: os
        # `ALTER` que já tinham dado certo iam junto no rollback.
        #
        # Diagnosticado em 2026-08-05 instrumentando o boot em produção:
        #
        #     BLOCO#13 -> DuplicateColumn: column "next_drill_at" ... already exists
        #     BLOCO#14+ -> InFailedSqlTransaction  (cascata até o fim)
        #
        # Sintoma que isso produzia: coluna nova nunca aparecia em prod, e o deploy parecia OK.
        # `_pg_exec_isolated` existe justamente para isso — usar SEMPRE, e nunca `conn.execute`
        # cru de DDL dentro de `except: pass`. Há teste varrendo este arquivo por esse padrão.
        for _sql in (
            "ALTER TABLE drill_sessions ADD COLUMN IF NOT EXISTS next_drill_at TIMESTAMP",
            "ALTER TABLE drill_sessions ADD COLUMN IF NOT EXISTS srs_interval_days INTEGER NOT NULL DEFAULT 3",
            # Correção do acerto autoritativo (tier de frequência GTO) — antes o SRS/stats
            # rederivavam de delta<0, que marcava errado spots GTO-corretos de score já baixo.
            # INTEGER 0/1 (não BOOLEAN) p/ evitar o gotcha SQLite/Postgres; NULL = linha legada.
            "ALTER TABLE drill_sessions ADD COLUMN IF NOT EXISTS correct INTEGER",
        ):
            _pg_exec_isolated(conn, _sql)
        # Sprint Q — FEAT-02+03: XP server-side + Daily Focus
        for _col, _sql in [
            ("xp_total",            "ALTER TABLE users ADD COLUMN IF NOT EXISTS xp_total            INTEGER NOT NULL DEFAULT 0"),
            ("xp_streak",           "ALTER TABLE users ADD COLUMN IF NOT EXISTS xp_streak           INTEGER NOT NULL DEFAULT 0"),
            ("xp_last_activity",    "ALTER TABLE users ADD COLUMN IF NOT EXISTS xp_last_activity    TEXT"),
            ("daily_focus_done_at", "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_focus_done_at TEXT"),
            ("digest_subscribed",   "ALTER TABLE users ADD COLUMN IF NOT EXISTS digest_subscribed   INTEGER NOT NULL DEFAULT 0"),
            # opt-out de email de comunicado do admin (default 1 = inscrito; unsubscribe via link zera)
            ("email_opt_in",        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_in        INTEGER NOT NULL DEFAULT 1"),
            # Verificação de email no cadastro (2FA simples anti-bot). default 1 = legados verificados;
            # novos signups nascem com 0 e só completam com o código enviado por email.
            ("email_verified",      "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified      INTEGER NOT NULL DEFAULT 1"),
            ("verification_code",   "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code   TEXT"),
            ("verification_expires_at", "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_expires_at TEXT"),
            ("verification_attempts",   "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_attempts   INTEGER NOT NULL DEFAULT 0"),
            # Win-back (reengajamento de inativos): estágio já enviado (0..3) + quando saiu o último.
            ("winback_stage",       "ALTER TABLE users ADD COLUMN IF NOT EXISTS winback_stage       INTEGER NOT NULL DEFAULT 0"),
            ("winback_sent_at",     "ALTER TABLE users ADD COLUMN IF NOT EXISTS winback_sent_at     TEXT"),
            # Programa de fundadores: quando entrou (o fim vive em plan_expires_at).
            ("founder_since",       "ALTER TABLE users ADD COLUMN IF NOT EXISTS founder_since       TIMESTAMP"),
        ]:
            _pg_exec_isolated(conn, _sql)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    achievement_key TEXT    NOT NULL,
                    earned_at       TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, achievement_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id)")
        except Exception: pass
        # coach_plan_templates (Postgres) — FEAT-09
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_plan_templates (
                    id               SERIAL PRIMARY KEY,
                    coach_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name             TEXT    NOT NULL,
                    target_archetype TEXT,
                    cards_json       TEXT    NOT NULL DEFAULT '[]',
                    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_templates_coach ON coach_plan_templates(coach_id)")
        except Exception: pass
        # coach_messages (Postgres) — FEAT-10
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_messages (
                    id          SERIAL PRIMARY KEY,
                    coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    body        TEXT    NOT NULL,
                    sender_role TEXT    NOT NULL DEFAULT 'coach',
                    decision_id INTEGER REFERENCES decisions(id) ON DELETE SET NULL,
                    read_at     TIMESTAMP,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_msgs_pair ON coach_messages(coach_id, student_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_msgs_unread ON coach_messages(student_id, read_at)")
        except Exception: pass
        # coach_applications (Postgres) — BACK-018
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coach_applications (
                    id               SERIAL PRIMARY KEY,
                    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    instagram_handle TEXT,
                    bio              TEXT    NOT NULL DEFAULT '',
                    specialties      TEXT    NOT NULL DEFAULT '[]',
                    experience_years INTEGER NOT NULL DEFAULT 0,
                    biggest_results  TEXT    NOT NULL DEFAULT '',
                    status           TEXT    NOT NULL DEFAULT 'pending',
                    admin_note       TEXT,
                    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
                    reviewed_at      TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_apps_status ON coach_applications(status)")
        except Exception: pass
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    category    TEXT      NOT NULL DEFAULT 'other',
                    subject     TEXT      NOT NULL DEFAULT '',
                    message     TEXT      NOT NULL,
                    status      TEXT      NOT NULL DEFAULT 'open',
                    admin_reply TEXT,
                    replied_at  TIMESTAMP,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_support_status ON support_tickets(status)")
        except Exception: pass
        # migrate support_tickets: add missing columns (Postgres)
        for sql in [
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS admin_reply TEXT",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS replied_at  TIMESTAMP",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS read_at     TIMESTAMP",
        ]:
            _pg_exec_isolated(conn, sql)
        # Notificações in-app (genérico — type + payload JSON, render no frontend) (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    type       TEXT      NOT NULL,
                    payload    TEXT      NOT NULL DEFAULT '{}',
                    link       TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    read_at    TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, created_at)")
        except Exception: pass
        # HUD Fase 1 — perfis de comportamento de oponente (torneio × jogador) (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS opponent_profiles (
                    id            SERIAL PRIMARY KEY,
                    tournament_id INTEGER   NOT NULL,
                    player_name   TEXT      NOT NULL,
                    hands_seen    INTEGER   NOT NULL DEFAULT 0,
                    archetype     TEXT      NOT NULL DEFAULT 'unknown',
                    confidence    TEXT      NOT NULL DEFAULT 'insufficient',
                    stats_json    TEXT      NOT NULL DEFAULT '{}',
                    updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(tournament_id, player_name)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_oppprof_tourney ON opponent_profiles(tournament_id)")
        except Exception: pass
        # #15 leaderboard — snapshots diários (histórico de posição + delta). Hoje
        # gravados sob demanda (sem cron real ainda — ver memória/backlog).
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    period_days     INTEGER NOT NULL,
                    rank            INTEGER NOT NULL,
                    score           REAL    NOT NULL,
                    dimensions_json TEXT    NOT NULL DEFAULT '{}',
                    snapshot_at     TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lb_snap ON leaderboard_snapshots(user_id, period_days, snapshot_at)")
        except Exception: pass
        # Sprint GTO — gto_nodes table (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gto_nodes (
                    id           SERIAL PRIMARY KEY,
                    spot_hash    TEXT NOT NULL UNIQUE,
                    street       TEXT NOT NULL,
                    position     TEXT NOT NULL,
                    board        TEXT NOT NULL,
                    hero_hand    TEXT NOT NULL,
                    stack_bucket TEXT NOT NULL,
                    gto_action   TEXT NOT NULL,
                    gto_freq     REAL NOT NULL,
                    ev_diff      REAL,
                    source       TEXT DEFAULT 'gto_wizard',
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_nodes_hash ON gto_nodes(spot_hash)")
        except Exception: pass
        # exploitability_pct em gto_nodes (Postgres) — GTO-002: garantia de qualidade
        for sql in [
            "ALTER TABLE gto_nodes ADD COLUMN IF NOT EXISTS exploitability_pct REAL",
            "ALTER TABLE gto_nodes ADD COLUMN IF NOT EXISTS iterations INTEGER",
            "ALTER TABLE gto_nodes ADD COLUMN IF NOT EXISTS strategy_json TEXT",
            "ALTER TABLE gto_nodes ADD COLUMN IF NOT EXISTS is_aggregate BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE gto_nodes ADD COLUMN IF NOT EXISTS tree_hash TEXT",
            "CREATE INDEX IF NOT EXISTS idx_gto_nodes_tree ON gto_nodes(tree_hash)",
        ]:
            _pg_exec_isolated(conn, sql)
        # gto_preflop_ranges (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gto_preflop_ranges (
                    id               SERIAL PRIMARY KEY,
                    position         TEXT NOT NULL,
                    vs_position      TEXT NOT NULL DEFAULT '',
                    action_seq       TEXT NOT NULL,
                    hand_type        TEXT NOT NULL,
                    action           TEXT NOT NULL,
                    frequency        REAL NOT NULL,
                    ev_bb            REAL,
                    exploitability_pct REAL,
                    stack_bucket     TEXT NOT NULL DEFAULT '35-60bb',
                    source           TEXT NOT NULL DEFAULT 'solver',
                    solver_config    TEXT,
                    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(position, vs_position, action_seq, hand_type, action, stack_bucket)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_preflop_lookup ON gto_preflop_ranges(position, vs_position, action_seq, hand_type)")
        except Exception: pass
        # exploitability_pct em gto_preflop_ranges existente (Postgres)
        for sql in [
            "ALTER TABLE gto_preflop_ranges ADD COLUMN IF NOT EXISTS exploitability_pct REAL",
            "ALTER TABLE gto_preflop_ranges ADD COLUMN IF NOT EXISTS solver_config TEXT",
            # Remove dados estimados: qualquer row sem exploitability confirmada é deletada
            "DELETE FROM gto_preflop_ranges WHERE exploitability_pct IS NULL",
        ]:
            _pg_exec_isolated(conn, sql)
        # gto_solver_queue (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gto_solver_queue (
                    id           SERIAL PRIMARY KEY,
                    spot_hash    TEXT NOT NULL UNIQUE,
                    spot_json    TEXT NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'pending',
                    priority     INTEGER NOT NULL DEFAULT 5,
                    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    solved_at    TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_queue_status ON gto_solver_queue(status, priority)")
        except Exception: pass
        # Fase 1 (plano solver): tree_hash na fila — dedup de solves por árvore (Postgres)
        for sql in [
            "ALTER TABLE gto_solver_queue ADD COLUMN IF NOT EXISTS tree_hash TEXT",
        ]:
            _pg_exec_isolated(conn, sql)
        # gto_tournament_queue (Postgres) — vínculo torneio↔spot enfileirado (ver SQLite acima):
        # "Analisando" per-torneio (spot deste torneio na fila ativa), imune a upload de terceiros.
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gto_tournament_queue (
                    tournament_id INTEGER NOT NULL,
                    spot_hash     TEXT    NOT NULL,
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tournament_id, spot_hash)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gtq_hash ON gto_tournament_queue(spot_hash)")
        except Exception: pass
        # Fase 3 (plano solver): tabela por mão da árvore (Postgres)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gto_tree_strategies (
                    tree_hash   TEXT PRIMARY KEY,
                    board       TEXT NOT NULL,
                    actions     TEXT NOT NULL,
                    hand_table  TEXT NOT NULL,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
        except Exception: pass

        # player_elo_history (Postgres) — espelha SQLite
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_elo_history (
                    id                 SERIAL PRIMARY KEY,
                    user_id            INTEGER NOT NULL,
                    elo_overall        REAL NOT NULL,
                    elo_preflop        REAL,
                    elo_flop           REAL,
                    elo_turn           REAL,
                    elo_river          REAL,
                    total_decisions    INTEGER NOT NULL DEFAULT 0,
                    n_preflop          INTEGER NOT NULL DEFAULT 0,
                    n_flop             INTEGER NOT NULL DEFAULT 0,
                    n_turn             INTEGER NOT NULL DEFAULT 0,
                    n_river            INTEGER NOT NULL DEFAULT 0,
                    calculated_at      TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_elo_user_calc ON player_elo_history(user_id, calculated_at)")
        except Exception: pass

        # gw_raw_cache (Postgres) — espelha o SQLite (cache de responses /gw-spot)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gw_raw_cache (
                    id              SERIAL PRIMARY KEY,
                    cache_key       TEXT NOT NULL UNIQUE,
                    gametype        TEXT NOT NULL,
                    depth_used      REAL NOT NULL,
                    preflop_actions TEXT NOT NULL,
                    hero_position   TEXT,
                    payload_json    TEXT NOT NULL,
                    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gw_raw_cache_key ON gw_raw_cache(cache_key)")
        except Exception: pass
        # gto_hand_requests (Postgres) — solicitações GTO por mão
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gto_hand_requests (
                    id              SERIAL PRIMARY KEY,
                    tournament_id   INTEGER NOT NULL,
                    hand_id         TEXT NOT NULL,
                    requested_by    INTEGER NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    decisions_found INTEGER,
                    decisions_done  INTEGER,
                    error_msg       TEXT,
                    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                    processed_at    TIMESTAMP,
                    UNIQUE(hand_id, requested_by)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_hand_req_status ON gto_hand_requests(status)")
        except Exception: pass
        # session_goals table (Postgres) — FEAT-08
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_goals (
                    id                  SERIAL PRIMARY KEY,
                    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    goal_leak_spot      TEXT,
                    target_standard_pct REAL,
                    notes               TEXT,
                    tournament_id       INTEGER REFERENCES tournaments(id) ON DELETE SET NULL,
                    llm_review          TEXT,
                    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
                    linked_at           TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_goals_user    ON session_goals(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_goals_tourney ON session_goals(tournament_id)")
        except Exception: pass
        # revalidation suite — auditoria sistemática engine vs oracle (M3)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revalidation_runs (
                    id                   SERIAL PRIMARY KEY,
                    scope                TEXT NOT NULL,
                    total_tournaments    INTEGER NOT NULL DEFAULT 0,
                    total_hands          INTEGER NOT NULL DEFAULT 0,
                    total_decisions      INTEGER NOT NULL DEFAULT 0,
                    category_counts_json TEXT,
                    llm_judge_used       BOOLEAN NOT NULL DEFAULT FALSE,
                    notes                TEXT,
                    created_at           TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revalidation_findings (
                    id                 SERIAL PRIMARY KEY,
                    run_id             INTEGER NOT NULL REFERENCES revalidation_runs(id) ON DELETE CASCADE,
                    tournament_db_id   INTEGER,
                    hand_id            TEXT,
                    decision_index     INTEGER,
                    street             TEXT,
                    position           TEXT,
                    action_taken       TEXT,
                    engine_best        TEXT,
                    gto_action         TEXT,
                    oracle_action      TEXT,
                    category           TEXT NOT NULL,
                    severity_score     REAL NOT NULL,
                    opp_cost_bb        REAL,
                    oracle_source      TEXT,
                    oracle_confidence  TEXT,
                    reasons_json       TEXT,
                    llm_verdict        TEXT,
                    llm_reasoning      TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS ix_revfindings_run_cat ON revalidation_findings(run_id, category)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_revfindings_severity ON revalidation_findings(run_id, severity_score DESC)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revalidation_llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    response  TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
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
            ("solves_this_month",       "ALTER TABLE users ADD COLUMN solves_this_month       INTEGER NOT NULL DEFAULT 0"),
            ("quota_reset_at",          "ALTER TABLE users ADD COLUMN quota_reset_at          TEXT"),
            ("ai_chat_today",           "ALTER TABLE users ADD COLUMN ai_chat_today           INTEGER NOT NULL DEFAULT 0"),
            ("solves_today",            "ALTER TABLE users ADD COLUMN solves_today            INTEGER NOT NULL DEFAULT 0"),
            ("quota_day_reset_at",      "ALTER TABLE users ADD COLUMN quota_day_reset_at       TEXT"),
            ("invited_via_invite_id",   "ALTER TABLE users ADD COLUMN invited_via_invite_id   INTEGER"),
            ("link_status",             "ALTER TABLE users ADD COLUMN link_status             TEXT NOT NULL DEFAULT 'approved'"),
            ("plan_source",             "ALTER TABLE users ADD COLUMN plan_source             TEXT"),
            ("coach_trial_ends_at",     "ALTER TABLE users ADD COLUMN coach_trial_ends_at     TEXT"),
            ("plan_expires_at",         "ALTER TABLE users ADD COLUMN plan_expires_at         TEXT"),
            ("subscription_status",     "ALTER TABLE users ADD COLUMN subscription_status     TEXT"),
            ("canceled_at",             "ALTER TABLE users ADD COLUMN canceled_at             TEXT"),
            ("past_due_since",          "ALTER TABLE users ADD COLUMN past_due_since           TEXT"),
            ("cancel_reason",           "ALTER TABLE users ADD COLUMN cancel_reason            TEXT"),
            ("buy_in",          "ALTER TABLE tournaments ADD COLUMN buy_in REAL"),
            ("prize",           "ALTER TABLE tournaments ADD COLUMN prize  REAL"),
            ("profit",          "ALTER TABLE tournaments ADD COLUMN profit REAL"),
            ("raw_text",        "ALTER TABLE tournaments ADD COLUMN raw_text TEXT"),
            ("tournament_name", "ALTER TABLE tournaments ADD COLUMN tournament_name TEXT"),
            ("labels_reconciled_at", "ALTER TABLE tournaments ADD COLUMN labels_reconciled_at TEXT"),
            ("is_pko",          "ALTER TABLE tournaments ADD COLUMN is_pko BOOLEAN NOT NULL DEFAULT 0"),
            ("started_at",      "ALTER TABLE tournaments ADD COLUMN started_at TEXT"),
            ("ended_at",        "ALTER TABLE tournaments ADD COLUMN ended_at   TEXT"),
            ("field_size",      "ALTER TABLE tournaments ADD COLUMN field_size INTEGER"),
            ("prize_pool",      "ALTER TABLE tournaments ADD COLUMN prize_pool REAL"),
            ("re_entries",      "ALTER TABLE tournaments ADD COLUMN re_entries INTEGER"),
        ]:
            if col not in existing:
                try: conn.execute(sql)
                except Exception: pass
        ann_existing = {r[1] for r in conn.execute('PRAGMA table_info(coach_hand_annotations)').fetchall()}
        if 'coach_override_label' not in ann_existing:
            try: conn.execute("ALTER TABLE coach_hand_annotations ADD COLUMN coach_override_label TEXT")
            except Exception: pass
        # Identidade ESTAVEL da anotacao — espelha o bloco PG. Estes ALTER precisam ficar AQUI,
        # sob o PRAGMA de `coach_hand_annotations`: postos na lista de `decisions` (onde eu os
        # coloquei primeiro) o guard `col not in dec_existing` via `tournament_id` ja presente em
        # `decisions` e PULAVA a migracao inteira, em silencio.
        for _c, _sql in [
            ("tournament_id", "ALTER TABLE coach_hand_annotations ADD COLUMN tournament_id INTEGER"),
            ("hand_id",       "ALTER TABLE coach_hand_annotations ADD COLUMN hand_id TEXT"),
            ("street",        "ALTER TABLE coach_hand_annotations ADD COLUMN street TEXT"),
            ("action_taken",  "ALTER TABLE coach_hand_annotations ADD COLUMN action_taken TEXT"),
            ("ordinal",       "ALTER TABLE coach_hand_annotations ADD COLUMN ordinal INTEGER"),
        ]:
            if _c not in ann_existing:
                try: conn.execute(_sql)
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
            ("pot_size",        "ALTER TABLE decisions ADD COLUMN pot_size        REAL"),
            ("facing_bet",       "ALTER TABLE decisions ADD COLUMN facing_bet       REAL"),
            ("gto_label",        "ALTER TABLE decisions ADD COLUMN gto_label        TEXT"),
            ("gto_action",       "ALTER TABLE decisions ADD COLUMN gto_action       TEXT"),
            ("gto_depth_capped", "ALTER TABLE decisions ADD COLUMN gto_depth_capped INTEGER NOT NULL DEFAULT 0"),
            ("estimated_equity", "ALTER TABLE decisions ADD COLUMN estimated_equity REAL"),
            ("vs_position",      "ALTER TABLE decisions ADD COLUMN vs_position      TEXT"),
            ("icm_tax_pct",      "ALTER TABLE decisions ADD COLUMN icm_tax_pct      REAL"),
            ("preflop_raises_faced", "ALTER TABLE decisions ADD COLUMN preflop_raises_faced INTEGER"),
            ("hero_won_hand",    "ALTER TABLE decisions ADD COLUMN hero_won_hand    INTEGER"),
            ("ev_loss_bb",       "ALTER TABLE decisions ADD COLUMN ev_loss_bb       REAL"),
            ("ev_loss_source",   "ALTER TABLE decisions ADD COLUMN ev_loss_source   TEXT"),
            ("n_active_opponents", "ALTER TABLE decisions ADD COLUMN n_active_opponents INTEGER"),
            ("multiway_safe_verdict", "ALTER TABLE decisions ADD COLUMN multiway_safe_verdict TEXT"),  # #30 shadow
            ("raise_to_bb",      "ALTER TABLE decisions ADD COLUMN raise_to_bb      REAL"),   # sizing do hero
            # Custo de pagar (bb) — espelha o bloco PG. Ver o comentário de lá.
            ("facing_to_call_bb", "ALTER TABLE decisions ADD COLUMN facing_to_call_bb REAL"),
            # Stack efetivo (bb) — espelha o bloco PG. Ver o comentário de lá.
            ("effective_stack_bb", "ALTER TABLE decisions ADD COLUMN effective_stack_bb REAL"),
            # Pote limpado — espelha o bloco PG. Ver o comentário de lá.
            ("facing_limp", "ALTER TABLE decisions ADD COLUMN facing_limp INTEGER"),
            # Espelha o bloco PG. Ver o comentario de la.
            ("hero_was_aggressor", "ALTER TABLE decisions ADD COLUMN hero_was_aggressor INTEGER"),
            # Pureza da estratégia — espelha o bloco PG à prova de abort. `gto_top_freq` é o que
            # separa decisão AUTOMÁTICA (modal ~100%) de decisão de VERDADE (estratégia mista).
            ("gto_played_freq",  "ALTER TABLE decisions ADD COLUMN gto_played_freq  REAL"),
            ("gto_top_freq",     "ALTER TABLE decisions ADD COLUMN gto_top_freq     REAL"),
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
            ("social_instagram",  "ALTER TABLE coach_profiles ADD COLUMN social_instagram  TEXT"),
            # Sprint 12 — BACK-011 pt.2: content moderation
            ("moderation_status", "ALTER TABLE coach_profiles ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'approved'"),
            # Parceria: taxa fixa por aluno (legado) + taxa % em basis points (modelo atual).
            ("commission_cents",    "ALTER TABLE coach_profiles ADD COLUMN commission_cents    INTEGER"),
            ("commission_rate_bps", "ALTER TABLE coach_profiles ADD COLUMN commission_rate_bps INTEGER"),
        ]:
            if col not in prof_existing:
                try: conn.execute(sql)
                except Exception: pass
        # SEC-01: convites single-use do coach (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_invites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code        TEXT    NOT NULL UNIQUE,
                status      TEXT    NOT NULL DEFAULT 'active',
                used_by     INTEGER REFERENCES users(id),
                used_at     TEXT,
                expires_at  TEXT,
                label       TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_invites_coach ON coach_invites(coach_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_invites_code  ON coach_invites(code)")
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
        # coach_payments table (SQLite) — BACK-014 revenue share
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                period          TEXT    NOT NULL,
                active_students INTEGER NOT NULL DEFAULT 0,
                amount_cents    INTEGER NOT NULL DEFAULT 0,
                status          TEXT    NOT NULL DEFAULT 'pending',
                paid_at         TEXT,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(coach_id, period)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_payments_coach ON coach_payments(coach_id)")
        # Comissão por PAGAMENTO (accrual) — modelo %; 1 linha por cobrança comissionável (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_commissions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                payment_ref   TEXT    NOT NULL UNIQUE,
                base_cents    INTEGER NOT NULL,
                rate_bps      INTEGER NOT NULL,
                amount_cents  INTEGER NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                payable_at    TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                paid_at       TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_commissions_coach ON coach_commissions(coach_id)")
        # ADMIN-FIN: despesas (saídas) — net real do cockpit (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                category      TEXT    NOT NULL,
                vendor        TEXT,
                amount_cents  INTEGER NOT NULL DEFAULT 0,
                currency      TEXT    NOT NULL DEFAULT 'BRL',
                recurrence    TEXT    NOT NULL DEFAULT 'monthly',
                due_day       INTEGER,
                period        TEXT,
                status        TEXT    NOT NULL DEFAULT 'forecast',
                paid_at       TEXT,
                note          TEXT,
                active        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_period ON expenses(period)")
        # ADMIN-FIN: vencimento do repasse (calendário) — SQLite
        _cp_cols = {r[1] for r in conn.execute('PRAGMA table_info(coach_payments)').fetchall()}
        if 'due_at' not in _cp_cols:
            try: conn.execute("ALTER TABLE coach_payments ADD COLUMN due_at TEXT")
            except Exception: pass
        # drill_sessions table (SQLite) — Sprint K: Ghost Table Simulator
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drill_sessions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                decision_id    INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                new_action     TEXT    NOT NULL,
                new_score      REAL    NOT NULL,
                original_score REAL    NOT NULL,
                delta          REAL    NOT NULL,
                drilled_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_drill_user ON drill_sessions(user_id, drilled_at)")
        # Gamificação de treino (Fase 1): domínio por categoria de leak (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_skill_progress (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_key      TEXT    NOT NULL,
                attempts          INTEGER NOT NULL DEFAULT 0,
                correct           INTEGER NOT NULL DEFAULT 0,
                mastery_ema       REAL    NOT NULL DEFAULT 0,
                mastery           REAL    NOT NULL DEFAULT 0,
                last_practiced_at TEXT,
                UNIQUE(user_id, category_key)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_training_skill_user ON training_skill_progress(user_id)")
        # Protocolo de Progressão: log append-only de tentativas COM ESTRATO (SQLite).
        # Por que tabela nova e não colunas em training_skill_progress: o gate de domínio é uma
        # JANELA MÓVEL (últimas N tentativas) e precisa saber ONDE o jogador acertou — na parte
        # fácil da range ou na fronteira. Contadores acumulados não respondem isso, e a duração
        # de sessão é variável (o gate tem que ser por acumulado, não por sessão).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS progression_attempts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_key TEXT    NOT NULL,
                stratum      TEXT    NOT NULL,   -- nucleo | fronteira | lixo
                block_kind   TEXT,               -- active | review | contrast
                correct      INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prog_attempt_user_cat "
                     "ON progression_attempts(user_id, category_key, id)")
        # Conquistas EXCLUSIVAS do treino (separadas das globais/ELO) — SQLite
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_achievements (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                achievement_key TEXT    NOT NULL,
                earned_at       TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, achievement_key)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_training_ach_user ON training_achievements(user_id)")
        # Missões diárias de treino (Fase 2) — SQLite
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_daily (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                day       TEXT    NOT NULL,
                spots     INTEGER NOT NULL DEFAULT 0,
                correct   INTEGER NOT NULL DEFAULT 0,
                claimed   TEXT    NOT NULL DEFAULT '',
                UNIQUE(user_id, day)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_training_daily_user ON training_daily(user_id, day)")
        # "Provar" (Fase 4): baseline de aderência REAL da categoria (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_proof (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_key TEXT    NOT NULL,
                baseline_pct REAL    NOT NULL DEFAULT 0,
                baseline_n   INTEGER NOT NULL DEFAULT 0,
                baseline_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, category_key)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_training_proof_user ON training_proof(user_id)")
        # Analytics de uso (MVP): 1 linha por (dia, feature, user) com contador de hits (SQLite).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feature_usage (
                day         TEXT    NOT NULL,
                feature_key TEXT    NOT NULL,
                user_id     INTEGER NOT NULL,
                hits        INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, feature_key, user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feature_usage_day ON feature_usage(day)")
        # Desafio do Dia (#42): pool VETADO de spots + agenda diária + tentativas (SQLite).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_challenge_pool (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_json   TEXT    NOT NULL,
                answer      TEXT    NOT NULL,
                note        TEXT,
                explanation TEXT,
                status      TEXT    NOT NULL DEFAULT 'pending',
                used_on     TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        _dcp_cols = {r[1] for r in conn.execute('PRAGMA table_info(daily_challenge_pool)').fetchall()}
        if 'explanation' not in _dcp_cols:
            try: conn.execute("ALTER TABLE daily_challenge_pool ADD COLUMN explanation TEXT")
            except Exception: pass
        if 'difficulty' not in _dcp_cols:
            try: conn.execute("ALTER TABLE daily_challenge_pool ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'facil'")
            except Exception: pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_challenge_schedule (
                day     TEXT    PRIMARY KEY,
                pool_id INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_challenge_attempts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                day           TEXT    NOT NULL,
                chosen_action TEXT    NOT NULL,
                verdict       TEXT    NOT NULL,
                correct       INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, day)
            )
        """)
        # Retratos datados do relatório de evolução (espelha o bloco PG à prova de abort).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_reports (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                motivo     TEXT    NOT NULL,
                snapshot   TEXT    NOT NULL,
                n_decisoes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evolution_reports_user "
                     "ON evolution_reports(user_id, created_at DESC)")
        # SRS das cartas de memorizacao de range (espelha o bloco PG a prova de abort).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS range_card_srs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                card_key       TEXT    NOT NULL,
                position       TEXT    NOT NULL,
                familia        TEXT    NOT NULL,
                stack_bb       INTEGER NOT NULL,
                interval_days  INTEGER NOT NULL DEFAULT 0,
                due_at         TEXT,
                streak         INTEGER NOT NULL DEFAULT 0,
                seen           INTEGER NOT NULL DEFAULT 0,
                last_ok        INTEGER,
                updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE (user_id, card_key)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_range_card_due "
                     "ON range_card_srs(user_id, due_at)")
        # Chaves de agregacao da decisao (espelha a lista SAVEPOINT do PG)
        for _sql in ("ALTER TABLE decisions ADD COLUMN spot_family_key TEXT",
                     "ALTER TABLE decisions ADD COLUMN spot_hash TEXT"):
            try:
                conn.execute(_sql)
            except Exception:
                pass   # SQLite nao tem IF NOT EXISTS em ADD COLUMN
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dec_family ON decisions(spot_family_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dec_spot_hash ON decisions(spot_hash)")
        # Colocacao final por jogador (espelha a lista SAVEPOINT do PG)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tournament_finishes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                player        TEXT    NOT NULL,
                place         INTEGER,
                prize         REAL,
                UNIQUE (tournament_id, player)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tfinish_tour ON tournament_finishes(tournament_id)")
        # Meta semanal declarada (espelha a lista SAVEPOINT do PG)
        _ucols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        if 'weekly_training_goal' not in _ucols:
            try: conn.execute("ALTER TABLE users ADD COLUMN weekly_training_goal INTEGER")
            except Exception: pass
        # Envios de e-mail de cobrança (espelha a lista SAVEPOINT do PG)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS engagement_emails (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                tipo       TEXT    NOT NULL,
                enviado_em TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_engagement_email_user "
                     "ON engagement_emails(user_id, enviado_em DESC)")
        # Origem da tentativa (espelha a lista SAVEPOINT do PG)
        pa_cols = {r[1] for r in conn.execute('PRAGMA table_info(progression_attempts)').fetchall()}
        if 'origem' not in pa_cols:
            try: conn.execute("ALTER TABLE progression_attempts ADD COLUMN origem TEXT")
            except Exception: pass
        # Fase 3 (trilho lento): reabertura por regressão no jogo real (SQLite)
        proof_existing = {r[1] for r in conn.execute('PRAGMA table_info(training_proof)').fetchall()}
        for col, sql in [
            ("reopened_at",  "ALTER TABLE training_proof ADD COLUMN reopened_at  TEXT"),
            ("reopen_count", "ALTER TABLE training_proof ADD COLUMN reopen_count INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in proof_existing:
                try: conn.execute(sql)
                except Exception: pass
        # Sprint R — FEAT-05: SRS columns on drill_sessions (SQLite)
        drill_existing = {r[1] for r in conn.execute('PRAGMA table_info(drill_sessions)').fetchall()}
        for col, sql in [
            ("next_drill_at",     "ALTER TABLE drill_sessions ADD COLUMN next_drill_at     TEXT"),
            ("srs_interval_days", "ALTER TABLE drill_sessions ADD COLUMN srs_interval_days INTEGER NOT NULL DEFAULT 3"),
            ("correct",           "ALTER TABLE drill_sessions ADD COLUMN correct           INTEGER"),
        ]:
            if col not in drill_existing:
                try: conn.execute(sql)
                except Exception: pass
        # migrate users: mp_subscription_id + BACK-014 fields + FEAT-02/03 XP
        usr_existing = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        for col, sql in [
            ("mp_subscription_id",  "ALTER TABLE users ADD COLUMN mp_subscription_id  TEXT"),
            ("referral_coach_id",   "ALTER TABLE users ADD COLUMN referral_coach_id   INTEGER REFERENCES users(id)"),
            ("suspended",           "ALTER TABLE users ADD COLUMN suspended            INTEGER NOT NULL DEFAULT 0"),
            # SQLite NÃO aceita ADD COLUMN ... UNIQUE via ALTER (falha e o except engolia →
            # coluna nunca criada → 500 ao salvar o telefone). Unicidade garantida no endpoint.
            ("whatsapp_phone",      "ALTER TABLE users ADD COLUMN whatsapp_phone       TEXT"),
            ("xp_total",            "ALTER TABLE users ADD COLUMN xp_total            INTEGER NOT NULL DEFAULT 0"),
            ("xp_streak",           "ALTER TABLE users ADD COLUMN xp_streak           INTEGER NOT NULL DEFAULT 0"),
            ("xp_last_activity",    "ALTER TABLE users ADD COLUMN xp_last_activity    TEXT"),
            ("daily_focus_done_at",   "ALTER TABLE users ADD COLUMN daily_focus_done_at   TEXT"),
            ("digest_subscribed",          "ALTER TABLE users ADD COLUMN digest_subscribed          INTEGER NOT NULL DEFAULT 0"),
            ("email_opt_in",               "ALTER TABLE users ADD COLUMN email_opt_in               INTEGER NOT NULL DEFAULT 1"),
            ("email_verified",             "ALTER TABLE users ADD COLUMN email_verified             INTEGER NOT NULL DEFAULT 1"),
            ("verification_code",          "ALTER TABLE users ADD COLUMN verification_code          TEXT"),
            ("verification_expires_at",    "ALTER TABLE users ADD COLUMN verification_expires_at    TEXT"),
            ("verification_attempts",      "ALTER TABLE users ADD COLUMN verification_attempts      INTEGER NOT NULL DEFAULT 0"),
            ("winback_stage",              "ALTER TABLE users ADD COLUMN winback_stage              INTEGER NOT NULL DEFAULT 0"),
            ("winback_sent_at",            "ALTER TABLE users ADD COLUMN winback_sent_at            TEXT"),
            ("founder_since",              "ALTER TABLE users ADD COLUMN founder_since              TIMESTAMP"),
            ("birth_year",                "ALTER TABLE users ADD COLUMN birth_year                INTEGER"),
            ("country",                   "ALTER TABLE users ADD COLUMN country                   TEXT"),
            ("state_province",            "ALTER TABLE users ADD COLUMN state_province            TEXT"),
            ("city",                      "ALTER TABLE users ADD COLUMN city                      TEXT"),
            ("poker_experience_years",    "ALTER TABLE users ADD COLUMN poker_experience_years    INTEGER"),
            ("main_game_type",            "ALTER TABLE users ADD COLUMN main_game_type            TEXT"),
            ("usual_buyin_range",         "ALTER TABLE users ADD COLUMN usual_buyin_range         TEXT"),
            ("profile_completed_at",      "ALTER TABLE users ADD COLUMN profile_completed_at      TEXT"),
            ("dashboard_layout",          "ALTER TABLE users ADD COLUMN dashboard_layout          TEXT"),
            ("onboarding_completed",      "ALTER TABLE users ADD COLUMN onboarding_completed      INTEGER NOT NULL DEFAULT 0"),
            ("acquisition_source",        "ALTER TABLE users ADD COLUMN acquisition_source        TEXT"),
            # #15 leaderboard — opt-in/privacidade
            ("leaderboard_opt_in",        "ALTER TABLE users ADD COLUMN leaderboard_opt_in        INTEGER NOT NULL DEFAULT 0"),
            ("leaderboard_handle",        "ALTER TABLE users ADD COLUMN leaderboard_handle         TEXT"),
        ]:
            if col not in usr_existing:
                try: conn.execute(sql)
                except Exception: pass
        # #15 leaderboard — handle único, case-insensitive (só p/ quem definiu)
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lb_handle "
                         "ON users(leaderboard_handle COLLATE NOCASE) "
                         "WHERE leaderboard_handle IS NOT NULL")
        except Exception: pass
        # achievements table (SQLite) — FEAT-03
        conn.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                achievement_key TEXT    NOT NULL,
                earned_at       TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, achievement_key)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id)")
        # session_goals table (SQLite) — FEAT-08
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_goals (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_leak_spot      TEXT,
                target_standard_pct REAL,
                notes               TEXT,
                tournament_id       INTEGER REFERENCES tournaments(id) ON DELETE SET NULL,
                llm_review          TEXT,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
                linked_at           TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_goals_user    ON session_goals(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_goals_tourney ON session_goals(tournament_id)")
        # coach_plan_templates (SQLite) — FEAT-09
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_plan_templates (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name             TEXT    NOT NULL,
                target_archetype TEXT,
                cards_json       TEXT    NOT NULL DEFAULT '[]',
                created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_templates_coach ON coach_plan_templates(coach_id)")
        # coach_messages (SQLite) — FEAT-10
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body        TEXT    NOT NULL,
                sender_role TEXT    NOT NULL DEFAULT 'coach',
                decision_id INTEGER REFERENCES decisions(id) ON DELETE SET NULL,
                read_at     TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_msgs_pair   ON coach_messages(coach_id, student_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_msgs_unread ON coach_messages(student_id, read_at)")
        # coach_applications (SQLite) — BACK-018
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coach_applications (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                instagram_handle TEXT,
                bio              TEXT    NOT NULL DEFAULT '',
                specialties      TEXT    NOT NULL DEFAULT '[]',
                experience_years INTEGER NOT NULL DEFAULT 0,
                biggest_results  TEXT    NOT NULL DEFAULT '',
                status           TEXT    NOT NULL DEFAULT 'pending',
                admin_note       TEXT,
                created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
                reviewed_at      TEXT,
                UNIQUE(user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coach_apps_status ON coach_applications(status)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                category    TEXT    NOT NULL DEFAULT 'other',
                subject     TEXT    NOT NULL DEFAULT '',
                message     TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'open',
                admin_reply TEXT,
                replied_at  TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_support_status ON support_tickets(status)")
        # migrate support_tickets: add missing columns
        st_existing = {r[1] for r in conn.execute('PRAGMA table_info(support_tickets)').fetchall()}
        for col, sql in [
            ("admin_reply", "ALTER TABLE support_tickets ADD COLUMN admin_reply TEXT"),
            ("replied_at",  "ALTER TABLE support_tickets ADD COLUMN replied_at  TEXT"),
            ("read_at",     "ALTER TABLE support_tickets ADD COLUMN read_at     TEXT"),
        ]:
            if col not in st_existing:
                try: conn.execute(sql)
                except Exception: pass
        # Notificações in-app (genérico — type + payload JSON) (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type       TEXT    NOT NULL,
                payload    TEXT    NOT NULL DEFAULT '{}',
                link       TEXT,
                created_at TEXT    NOT NULL DEFAULT (datetime('now')),
                read_at    TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, created_at)")
        # HUD Fase 1 — perfis de comportamento de oponente (torneio × jogador) (SQLite)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opponent_profiles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                player_name   TEXT    NOT NULL,
                hands_seen    INTEGER NOT NULL DEFAULT 0,
                archetype     TEXT    NOT NULL DEFAULT 'unknown',
                confidence    TEXT    NOT NULL DEFAULT 'insufficient',
                stats_json    TEXT    NOT NULL DEFAULT '{}',
                updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(tournament_id, player_name)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_oppprof_tourney ON opponent_profiles(tournament_id)")
        # #15 leaderboard — snapshots diários (histórico de posição + delta).
        # Gravados sob demanda por enquanto (sem cron real ainda — ver backlog).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                period_days     INTEGER NOT NULL,
                rank            INTEGER NOT NULL,
                score           REAL    NOT NULL,
                dimensions_json TEXT    NOT NULL DEFAULT '{}',
                snapshot_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lb_snap ON leaderboard_snapshots(user_id, period_days, snapshot_at)")
        # gto_nodes (SQLite) — Sprint GTO
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gto_nodes (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_hash          TEXT NOT NULL UNIQUE,
                street             TEXT NOT NULL,
                position           TEXT NOT NULL,
                board              TEXT NOT NULL,
                hero_hand          TEXT NOT NULL,
                stack_bucket       TEXT NOT NULL,
                gto_action         TEXT NOT NULL,
                gto_freq           REAL NOT NULL,
                ev_diff            REAL,
                exploitability_pct REAL,
                iterations         INTEGER,
                source             TEXT DEFAULT 'solver',
                created_at         TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_nodes_hash ON gto_nodes(spot_hash)")
        # migrate gto_nodes: adicionar campos de qualidade + strategy_json
        gto_existing = {r[1] for r in conn.execute('PRAGMA table_info(gto_nodes)').fetchall()}
        for col, sql in [
            ("exploitability_pct", "ALTER TABLE gto_nodes ADD COLUMN exploitability_pct REAL"),
            ("iterations",         "ALTER TABLE gto_nodes ADD COLUMN iterations INTEGER"),
            ("strategy_json",      "ALTER TABLE gto_nodes ADD COLUMN strategy_json TEXT"),
            ("is_aggregate",       "ALTER TABLE gto_nodes ADD COLUMN is_aggregate INTEGER NOT NULL DEFAULT 0"),
            ("tree_hash",          "ALTER TABLE gto_nodes ADD COLUMN tree_hash TEXT"),
        ]:
            if col not in gto_existing:
                try: conn.execute(sql)
                except Exception: pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_nodes_tree ON gto_nodes(tree_hash)")
        # Fase 3 (plano solver): tabela por mão da ÁRVORE (freq+EV por ação por combo).
        # Keyed por tree_hash: 1 row por solve; qualquer spot isomorfo extrai a SUA mão
        # daqui via iso_suit_map (veredito hand-aware + EV loss em bb).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gto_tree_strategies (
                tree_hash   TEXT PRIMARY KEY,
                board       TEXT NOT NULL,
                actions     TEXT NOT NULL,
                hand_table  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # gto_preflop_ranges (SQLite) — populada APENAS por solver verificado
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gto_preflop_ranges (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                position           TEXT NOT NULL,
                vs_position        TEXT NOT NULL DEFAULT '',
                action_seq         TEXT NOT NULL,
                hand_type          TEXT NOT NULL,
                action             TEXT NOT NULL,
                frequency          REAL NOT NULL,
                ev_bb              REAL,
                exploitability_pct REAL,
                stack_bucket       TEXT NOT NULL DEFAULT '35-60bb',
                source             TEXT NOT NULL DEFAULT 'solver',
                solver_config      TEXT,
                created_at         TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(position, vs_position, action_seq, hand_type, action, stack_bucket)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_preflop_lookup ON gto_preflop_ranges(position, vs_position, action_seq, hand_type)")
        # migrate gto_preflop_ranges e limpar estimativas
        pfr_existing = {r[1] for r in conn.execute('PRAGMA table_info(gto_preflop_ranges)').fetchall()}
        for col, sql in [
            ("exploitability_pct", "ALTER TABLE gto_preflop_ranges ADD COLUMN exploitability_pct REAL"),
            ("solver_config",      "ALTER TABLE gto_preflop_ranges ADD COLUMN solver_config TEXT"),
        ]:
            if col not in pfr_existing:
                try: conn.execute(sql)
                except Exception: pass
        # Purge: remove qualquer linha sem exploitability confirmada (dados estimados)
        try: conn.execute("DELETE FROM gto_preflop_ranges WHERE exploitability_pct IS NULL")
        except Exception: pass
        # gto_solver_queue (SQLite) — spots pendentes de solve on-demand
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gto_solver_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_hash   TEXT NOT NULL UNIQUE,
                spot_json   TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                priority    INTEGER NOT NULL DEFAULT 5,
                requested_at TEXT NOT NULL DEFAULT (datetime('now')),
                solved_at   TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_queue_status ON gto_solver_queue(status, priority)")
        # Fase 1 (plano solver): tree_hash na fila — dedup de solves por árvore
        q_existing = {r[1] for r in conn.execute('PRAGMA table_info(gto_solver_queue)').fetchall()}
        if 'tree_hash' not in q_existing:
            try: conn.execute("ALTER TABLE gto_solver_queue ADD COLUMN tree_hash TEXT")
            except Exception: pass

        # gto_tournament_queue (SQLite) — vínculo torneio↔spot_hash enfileirado. A fila é global e
        # dedup por spot_hash (sem dono); sem esse mapa, o sinal "Analisando" tinha de usar a fila
        # GLOBAL como proxy → o upload de um usuário acendia o torneio recente de outro. Com o mapa,
        # "Analisando" = um spot DESTE torneio está na fila ativa (per-torneio, imune a terceiros).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gto_tournament_queue (
                tournament_id INTEGER NOT NULL,
                spot_hash     TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (tournament_id, spot_hash)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gtq_hash ON gto_tournament_queue(spot_hash)")

        # player_elo_history (SQLite) — snapshots de ELO calculados ao longo do
        # tempo. Cada linha é o estado do ELO do user em um momento (apos
        # processar X decisoes). Permite gráfico de evolução + diff semanal.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_elo_history (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id            INTEGER NOT NULL,
                elo_overall        REAL NOT NULL,
                elo_preflop        REAL,
                elo_flop           REAL,
                elo_turn           REAL,
                elo_river          REAL,
                total_decisions    INTEGER NOT NULL DEFAULT 0,
                n_preflop          INTEGER NOT NULL DEFAULT 0,
                n_flop             INTEGER NOT NULL DEFAULT 0,
                n_turn             INTEGER NOT NULL DEFAULT 0,
                n_river            INTEGER NOT NULL DEFAULT 0,
                calculated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_elo_user_calc ON player_elo_history(user_id, calculated_at)")

        # gw_raw_cache (SQLite) — cache de responses do /gw-spot (multiway / squeeze /
        # cold-callers via GTO Wizard). Separado de gto_nodes (que tem validacoes
        # estritas pra HU postflop). Chave inclui gametype/depth/preflop_actions
        # (mais flop/turn/river quando postflop suportado).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gw_raw_cache (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key       TEXT NOT NULL UNIQUE,
                gametype        TEXT NOT NULL,
                depth_used      REAL NOT NULL,
                preflop_actions TEXT NOT NULL,
                hero_position   TEXT,
                payload_json    TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gw_raw_cache_key ON gw_raw_cache(cache_key)")
        # gto_hand_requests — solicitações de análise GTO por mão específica (user-triggered)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gto_hand_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id   INTEGER NOT NULL,
                hand_id         TEXT NOT NULL,
                requested_by    INTEGER NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                decisions_found INTEGER,
                decisions_done  INTEGER,
                error_msg       TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                processed_at    TEXT,
                UNIQUE(hand_id, requested_by)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gto_hand_req_status ON gto_hand_requests(status)")
        # revalidation suite — auditoria sistemática engine vs oracle (M3)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revalidation_runs (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                scope                TEXT NOT NULL,
                total_tournaments    INTEGER NOT NULL DEFAULT 0,
                total_hands          INTEGER NOT NULL DEFAULT 0,
                total_decisions      INTEGER NOT NULL DEFAULT 0,
                category_counts_json TEXT,
                llm_judge_used       INTEGER NOT NULL DEFAULT 0,
                notes                TEXT,
                created_at           TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revalidation_findings (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id             INTEGER NOT NULL REFERENCES revalidation_runs(id) ON DELETE CASCADE,
                tournament_db_id   INTEGER,
                hand_id            TEXT,
                decision_index     INTEGER,
                street             TEXT,
                position           TEXT,
                action_taken       TEXT,
                engine_best        TEXT,
                gto_action         TEXT,
                oracle_action      TEXT,
                category           TEXT NOT NULL,
                severity_score     REAL NOT NULL,
                opp_cost_bb        REAL,
                oracle_source      TEXT,
                oracle_confidence  TEXT,
                reasons_json       TEXT,
                llm_verdict        TEXT,
                llm_reasoning      TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_revfindings_run_cat ON revalidation_findings(run_id, category)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_revfindings_severity ON revalidation_findings(run_id, severity_score DESC)")
        # Cache compartilhado do llm_judge (não amarrado a user — runs são globais)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revalidation_llm_cache (
                cache_key TEXT PRIMARY KEY,
                response  TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

    # ── À prova de transação abortada (Postgres, autocommit=False) ──────────────
    # As migrações acima rodam numa transação única; se UMA falha, o Postgres aborta
    # TODA a transação e os CREATE/ALTER seguintes (em try/except) falham silenciosamente.
    # Foi assim que a tabela `expenses` (e colunas novas) não foram criadas em prod. Aqui
    # recriamos os objetos recentes com COMMIT ISOLADO por statement, garantindo que sobrevivam
    # a uma migração anterior que falhou.
    #
    # ⚠️ ESTA LINHA JÁ FOI UM `conn.rollback()`, e era ELA que impedia TODA migração nova de
    # aplicar em produção (achado em 2026-08-05, instrumentando o boot real). O rollback era
    # INCONDICIONAL: rodava mesmo com a transação limpa, e jogava fora os ~240 statements do
    # bloco principal a cada boot. Sobreviviam só as colunas listadas em `_safe` logo abaixo,
    # que commitam uma a uma — e é exatamente por isso que o remendo parecia funcionar: cada
    # coluna que faltava em prod era adicionada AQUI, o que confirmava o remendo e escondia a
    # causa. O sintoma pelo qual se reconhece: o `ALTER` executa sem erro no log do boot e
    # mesmo assim a coluna não existe depois.
    #
    # `commit()` é seguro nos dois estados: com a transação sã ele PERSISTE o bloco principal;
    # com ela abortada o Postgres executa o COMMIT como ROLLBACK sem levantar erro, ou seja,
    # cai no mesmo comportamento de antes. Nunca é pior, e no caso normal é o conserto.
    # O advisory lock do boot é liberado aqui igual era antes — a janela não mudou.
    if USE_POSTGRES:
        try: conn.commit()
        except Exception: pass
        _safe = [
            """CREATE TABLE IF NOT EXISTS expenses (
                   id SERIAL PRIMARY KEY, category TEXT NOT NULL, vendor TEXT,
                   amount_cents INTEGER NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'BRL',
                   recurrence TEXT NOT NULL DEFAULT 'monthly', due_day INTEGER, period TEXT,
                   status TEXT NOT NULL DEFAULT 'forecast', paid_at TIMESTAMP, note TEXT,
                   active INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP NOT NULL DEFAULT NOW())""",
            "CREATE INDEX IF NOT EXISTS idx_expenses_period ON expenses(period)",
            "ALTER TABLE coach_payments ADD COLUMN IF NOT EXISTS due_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS canceled_at    TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS past_due_since TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS cancel_reason  TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_coach_id INTEGER",
            # drill_sessions: SRS + acerto autoritativo. A coluna `correct` não existia em prod
            # (migração abortada) → get_drill_stats fazia "WHERE correct = 1" e dava 500 no Ghost Table.
            "ALTER TABLE drill_sessions ADD COLUMN IF NOT EXISTS correct INTEGER",
            "ALTER TABLE drill_sessions ADD COLUMN IF NOT EXISTS next_drill_at TIMESTAMP",
            "ALTER TABLE drill_sessions ADD COLUMN IF NOT EXISTS srs_interval_days INTEGER NOT NULL DEFAULT 3",
            # Perfil demográfico (admin_demographics) — o loop que as adiciona não commita por
            # statement, então um abort anterior pode deixá-las faltando em prod → 500 no /admin/demographics.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS country              TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS main_game_type       TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS usual_buyin_range    TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completed_at TIMESTAMP",
            # As demais colunas do perfil + o whatsapp_phone estavam SÓ no bloco regular
            # (transação única) → um abort anterior as deixava faltando em prod, e salvar o
            # perfil dava 500 (no such column birth_year/state_province/city/whatsapp_phone).
            # whatsapp_phone sem UNIQUE aqui de propósito (a unicidade é garantida no endpoint
            # /profile/phone via get_user_by_phone); IF NOT EXISTS preserva o UNIQUE se já existir.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_phone         TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_year             INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS state_province         TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS city                   TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS poker_experience_years INTEGER",
            # Atribuição de aquisição: utm_source capturado no cadastro (ex.: 'instagram').
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS acquisition_source   TEXT",
            # Parceria (legado fixo, mantido p/ retrocompat): taxa fixa por aluno em cents.
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS commission_cents INTEGER",
            # Parceria (modelo %): taxa de comissão POR COACH em basis points (3000 = 30%).
            # NULL = escada por volume (15%/20%/25%). Parceiro Fundador (Felipe) = 3000.
            "ALTER TABLE coach_profiles ADD COLUMN IF NOT EXISTS commission_rate_bps INTEGER",
            # SRS das cartas de MEMORIZAÇÃO de range (posição × família × profundidade).
            #
            # Mora AQUI, na lista isolada por SAVEPOINT, e não num `try/except` no meio das
            # migrações. Eu tinha posto lá primeiro, copiando o formato dos vizinhos que se
            # descrevem como "bloco abort-proof próprio" — e o deploy provou que não são: o
            # `CREATE` é válido (roda sozinho em produção), mas a transação já chegava abortada
            # e o `except` engolia o erro. A tabela simplesmente não existia, calada.
            #
            # Tabela própria e não `drill_sessions`: aquela é chaveada por `decision_id`, uma
            # decisão REAL de uma mão do jogador. A carta de range não é uma decisão.
            """CREATE TABLE IF NOT EXISTS range_card_srs (
                id             SERIAL PRIMARY KEY,
                user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                card_key       TEXT    NOT NULL,
                position       TEXT    NOT NULL,
                familia        TEXT    NOT NULL,
                stack_bb       INTEGER NOT NULL,
                interval_days  INTEGER NOT NULL DEFAULT 0,
                due_at         TIMESTAMP,
                streak         INTEGER NOT NULL DEFAULT 0,
                seen           INTEGER NOT NULL DEFAULT 0,
                last_ok        INTEGER,
                updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, card_key)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_range_card_due ON range_card_srs(user_id, due_at)",
            # Origem da tentativa (dashboard/sino/email/pos_upload/espontanea) — métrica 1 da
            # spec de cobrança: % de sessões iniciadas por trigger. Na lista SAVEPOINT pela
            # mesma razão da tabela acima: try/except no meio da transação não é abort-proof.
            "ALTER TABLE progression_attempts ADD COLUMN IF NOT EXISTS origem TEXT",
            # Envios de e-mail de COBRANÇA (Fase 2 da spec). Na lista SAVEPOINT pela regra dura:
            # try/except no meio da transação não sobrevive a um abort (custou `range_card_srs`
            # não existir em produção depois de um deploy verde).
            #
            # A tabela É o teto semanal: sem ela, "já cobrei este aluno?" não tem resposta e o
            # sistema manda e-mail a cada varredura do worker.
            """CREATE TABLE IF NOT EXISTS engagement_emails (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tipo       TEXT    NOT NULL,
                enviado_em TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS idx_engagement_email_user "
            "ON engagement_emails(user_id, enviado_em DESC)",
            # Chaves de agregacao da decisao (Protocolo de Progressao, Fase 0):
            #   spot_family_key = chave GROSSA da validacao no jogo real (leaklab/familia_spot.py)
            #   spot_hash       = chave FINA do no GTO (gto_utils.compute_spot_hash)
            # Materializadas porque a serie temporal por familia agrupa por elas em toda consulta,
            # e recalcular por linha exigiria reparsear board + cartas a cada query.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS spot_family_key TEXT",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS spot_hash TEXT",
            "CREATE INDEX IF NOT EXISTS idx_dec_family ON decisions(spot_family_key)",
            "CREATE INDEX IF NOT EXISTS idx_dec_spot_hash ON decisions(spot_hash)",
            # Colocacao final de CADA jogador do torneio (vem do arquivo de resumo, nao do hand
            # history). E o que permite detectar MESA FINAL de MTT: quando restam S jogadores no
            # torneio, as colocacoes deles sao exatamente 1..S — entao a mesa e a final quando a
            # MAIOR colocacao entre os sentados iguala o numero de sentados.
            #
            # Ideia do usuario: "no summary tem a colocacao do torneio, poderiamos detectar
            # quando os 8 ou 9 jogadores vencedores estao na mesma mesa". Antes disso o unico
            # gate era `field_size <= 9`, que so abre em torneio de mesa unica e NUNCA numa mesa
            # final de MTT (o field_size continua sendo o total de inscritos para sempre).
            """CREATE TABLE IF NOT EXISTS tournament_finishes (
                id            SERIAL PRIMARY KEY,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
                player        TEXT    NOT NULL,
                place         INTEGER,
                prize         REAL,
                UNIQUE (tournament_id, player)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_tfinish_tour ON tournament_finishes(tournament_id)",
            # Meta semanal DECLARADA pelo aluno (Fase 3): em quantos dias por semana ele se
            # compromete a treinar. NULL = ainda não perguntamos, e é esse NULL que dispara a
            # pergunta na tela. Na lista SAVEPOINT pela regra dura das colunas novas.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_training_goal INTEGER",
            # Comissão por PAGAMENTO (accrual): 1 linha por cobrança comissionável.
            """CREATE TABLE IF NOT EXISTS coach_commissions (
                id            SERIAL PRIMARY KEY,
                coach_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                payment_ref   TEXT    NOT NULL UNIQUE,
                base_cents    INTEGER NOT NULL,
                rate_bps      INTEGER NOT NULL,
                amount_cents  INTEGER NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                payable_at    TIMESTAMP NOT NULL,
                created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                paid_at       TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_coach_commissions_coach ON coach_commissions(coach_id)",
            # Protocolo de Progressão: tentativas COM ESTRATO — abort-proof.
            # Confirmado em PROD (2026-07-26): a tabela NÃO foi criada pelo bloco regular
            # (transação abortada por uma migração anterior), e o painel do protocolo ficava
            # com todos os indicadores zerados — o jogador treinava e nada subia.
            """CREATE TABLE IF NOT EXISTS progression_attempts (
                id           SERIAL PRIMARY KEY,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_key TEXT    NOT NULL,
                stratum      TEXT    NOT NULL,
                block_kind   TEXT,
                correct      INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS idx_prog_attempt_user_cat "
            "ON progression_attempts(user_id, category_key, id)",
            # Sizing do hero (raise-to em bb) — mesma razão: sem ela o leak de tamanho não agrega.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS raise_to_bb REAL",
            # Gamificação de treino (Fase 1): domínio por categoria — abort-proof p/ existir em prod.
            """CREATE TABLE IF NOT EXISTS training_skill_progress (
                id                SERIAL PRIMARY KEY,
                user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_key      TEXT    NOT NULL,
                attempts          INTEGER NOT NULL DEFAULT 0,
                correct           INTEGER NOT NULL DEFAULT 0,
                mastery_ema       REAL    NOT NULL DEFAULT 0,
                mastery           REAL    NOT NULL DEFAULT 0,
                last_practiced_at TIMESTAMP,
                UNIQUE(user_id, category_key)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_training_skill_user ON training_skill_progress(user_id)",
            # Conquistas do treino — abort-proof p/ existir em prod.
            """CREATE TABLE IF NOT EXISTS training_achievements (
                id              SERIAL PRIMARY KEY,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                achievement_key TEXT    NOT NULL,
                earned_at       TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, achievement_key)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_training_ach_user ON training_achievements(user_id)",
            # Missões diárias de treino — abort-proof p/ existir em prod.
            """CREATE TABLE IF NOT EXISTS training_daily (
                id        SERIAL PRIMARY KEY,
                user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                day       TEXT    NOT NULL,
                spots     INTEGER NOT NULL DEFAULT 0,
                correct   INTEGER NOT NULL DEFAULT 0,
                claimed   TEXT    NOT NULL DEFAULT '',
                UNIQUE(user_id, day)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_training_daily_user ON training_daily(user_id, day)",
            # "Provar" (Fase 4): baseline de aderência da categoria — abort-proof p/ existir em prod.
            """CREATE TABLE IF NOT EXISTS training_proof (
                id           SERIAL PRIMARY KEY,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_key TEXT    NOT NULL,
                baseline_pct REAL    NOT NULL DEFAULT 0,
                baseline_n   INTEGER NOT NULL DEFAULT 0,
                baseline_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, category_key)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_training_proof_user ON training_proof(user_id)",
            # Fase 3 (trilho lento): momento em que o leak REABRIU por regressão comprovada no
            # jogo. Zera a janela do gate (o jogador re-prova a partir daqui) e move o baseline,
            # senão a mesma evidência antiga reabriria o leak para sempre.
            "ALTER TABLE training_proof ADD COLUMN IF NOT EXISTS reopened_at TIMESTAMP",
            "ALTER TABLE training_proof ADD COLUMN IF NOT EXISTS reopen_count INTEGER NOT NULL DEFAULT 0",
            # #30 multiway (shadow): veredito da cauda segura por decisão. Estava só no
            # bloco regular (transação única) → um abort anterior pulava o ADD e a coluna
            # faltava em prod (UndefinedColumn no backfill). Aqui sobrevive com commit isolado.
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS multiway_safe_verdict TEXT",
            # Email de comunicado do admin (opt-out). Mesmo motivo: no bloco regular a coluna
            # ficava atrás do `xp_total` (já existente), que aborta a transação → email_opt_in
            # nunca era criada em prod e o get_email_recipients dava 500. Commit isolado resolve.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_in INTEGER NOT NULL DEFAULT 1",
            # Verificação de email no cadastro (2FA simples). default 1 = legados verificados.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_expires_at TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_attempts INTEGER NOT NULL DEFAULT 0",
            # Win-back de inativos (reengajamento por email escalonado)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS winback_stage INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS winback_sent_at TEXT",
            # Analytics de uso (MVP): agregado por (dia, feature, user). Abort-proof p/ existir em prod.
            """CREATE TABLE IF NOT EXISTS feature_usage (
                day         TEXT    NOT NULL,
                feature_key TEXT    NOT NULL,
                user_id     INTEGER NOT NULL,
                hits        INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, feature_key, user_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_feature_usage_day ON feature_usage(day)",
            # Desafio do Dia (#42): pool VETADO + agenda + tentativas. Abort-proof p/ existir em prod.
            """CREATE TABLE IF NOT EXISTS daily_challenge_pool (
                id          SERIAL PRIMARY KEY,
                spot_json   TEXT    NOT NULL,
                answer      TEXT    NOT NULL,
                note        TEXT,
                explanation TEXT,
                status      TEXT    NOT NULL DEFAULT 'pending',
                used_on     TEXT,
                created_at  TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "ALTER TABLE daily_challenge_pool ADD COLUMN IF NOT EXISTS explanation TEXT",
            # Dificuldade do desafio (facil|medio|dificil). Coluna nova → bloco de commit
            # isolado, senão um abort anterior a engole em silêncio (ver expenses/progression).
            "ALTER TABLE daily_challenge_pool ADD COLUMN IF NOT EXISTS difficulty TEXT NOT NULL DEFAULT 'facil'",
            """CREATE TABLE IF NOT EXISTS daily_challenge_schedule (
                day     TEXT    PRIMARY KEY,
                pool_id INTEGER NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS daily_challenge_attempts (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER NOT NULL,
                day           TEXT    NOT NULL,
                chosen_action TEXT    NOT NULL,
                verdict       TEXT    NOT NULL,
                correct       INTEGER NOT NULL DEFAULT 0,
                created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, day)
            )""",
            # PUREZA da estratégia. `gto_label` só diz a FAIXA de frequência da ação JOGADA, então
            # um fold `gto_correct` pode ser 100% (decisão automática, ninguém erra) ou 65%
            # (decisão de verdade). Sem distinguir, a taxa de erro de RFI dilui: ~84% das decisões
            # são folds óbvios e um "0% de erro" pode esconder um limp que erra 3 de 3.
            #   gto_played_freq = frequência GTO da ação que o jogador escolheu
            #   gto_top_freq    = frequência da ação modal → é ELA que mede a pureza do spot
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS gto_played_freq REAL",
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS gto_top_freq REAL",
            # Retratos datados do relatório de evolução. Guarda os NÚMEROS, não o HTML: o visual
            # pode melhorar sem invalidar relatório antigo, e comparar julho com agosto continua
            # válido porque compara dados, não páginas.
            """CREATE TABLE IF NOT EXISTS evolution_reports (
                id           SERIAL PRIMARY KEY,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                motivo       TEXT    NOT NULL,
                snapshot     TEXT    NOT NULL,
                n_decisoes   INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS idx_evolution_reports_user "
            "ON evolution_reports(user_id, created_at DESC)",
            # Programa de fundadores: quem entrou e quando. O FIM da vigência já mora em
            # `plan_expires_at` e a coorte em `plan_source='founder'`; falta o INÍCIO, que é
            # o que permite ler "está no 2º ciclo" em vez de só "vence em novembro".
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS founder_since TIMESTAMP",
        ]
        for _stmt in _safe:
            try:
                conn.execute(_stmt)
                conn.commit()
            except Exception:
                try: conn.rollback()
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

    def __init__(self, raw_conn, is_postgres: bool, _devolver=None):
        self._conn = raw_conn
        self._pg = is_postgres
        # Como esta conexão volta: ao pool (callable) ou fechando de verdade (None).
        self._devolver = _devolver
        self._solta = False

    def _adapt(self, sql: str) -> str:
        if not self._pg:
            return sql
        import re
        # ? → %s só FORA de strings literais ('...'). Um '?' literal (ex.: COALESCE(pos,'?')) não é
        # placeholder; convertê-lo dava um %s a mais → "tuple index out of range" no psycopg2.
        _parts = re.split(r"('(?:[^']|'')*')", sql)
        for _i in range(0, len(_parts), 2):
            _parts[_i] = re.sub(r'(?<![\$%])\?', '%s', _parts[_i])
        sql = ''.join(_parts)
        sql = sql.replace("datetime('now')", 'NOW()')
        # days/hours/minutes/seconds (antes só days; horas/minutos ficavam crus e quebravam no PG).
        sql = re.sub(
            r"datetime\('now',\s*'(-?\d+)\s+(days?|hours?|minutes?|seconds?)'\)",
            lambda m: f"(NOW() + INTERVAL '{m.group(1)} {m.group(2)}')",
            sql
        )
        # INSERT OR IGNORE (SQLite) → ON CONFLICT DO NOTHING (Postgres). Sem alvo de coluna:
        # o Postgres aplica a qualquer violação de unique/PK. INSERT OR REPLACE NÃO é convertido
        # aqui (precisa de alvo p/ DO UPDATE) — esses já são branchados por USE_POSTGRES no repo.
        if re.match(r'\s*INSERT\s+OR\s+IGNORE\s+INTO', sql, re.IGNORECASE):
            sql = re.sub(r'^(\s*)INSERT\s+OR\s+IGNORE\s+INTO', r'\1INSERT INTO', sql, flags=re.IGNORECASE)
            sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        return sql

    # Tabelas sem coluna `id` (chave natural): não acrescentar RETURNING id nelas.
    #
    # ⚠️ Esquecer uma tabela aqui quebra TODO INSERT nela — mas SÓ em Postgres, e com
    # `UndefinedColumn: column "id" does not exist`. Em SQLite passa liso, então o bug só
    # aparece em produção. Foi o que manteve o painel de Uso zerado: `feature_usage` ficou
    # de fora, cada INSERT falhava e o `except: pass` do gravador engolia o erro.
    # `tests/test_no_id_tables.py` audita esta lista contra o schema real — se você criar uma
    # tabela de chave natural e esquecer daqui, o teste cai antes de ir pra prod.
    _NO_ID_TABLES = {'revalidation_llm_cache', 'gto_preflop_capture', 'gto_tree_strategies',
                     'daily_challenge_schedule', 'gto_tournament_queue', 'feature_usage'}

    def _pg_insert_returning(self, sql: str) -> str:
        """Postgres não popula lastrowid. Para INSERTs em tabelas com `id`, acrescenta
        RETURNING id pra o _PgResult.lastrowid recuperar o id gerado (no SQLite o
        lastrowid nativo já funciona, então este caminho é só Postgres)."""
        import re
        s = sql.lstrip()
        if s[:6].upper() != 'INSERT' or 'RETURNING' in sql.upper():
            return sql
        m = re.match(r'INSERT\s+INTO\s+"?(\w+)"?', s, re.IGNORECASE)
        if m and m.group(1).lower() in self._NO_ID_TABLES:
            return sql
        return sql.rstrip().rstrip(';') + ' RETURNING id'

    def execute(self, sql: str, params=None):
        sql = self._adapt(sql)
        if self._pg:
            sql = self._pg_insert_returning(sql)
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

    def rollback(self):
        self._conn.rollback()

    def _soltar(self):
        """Devolve ao pool, ou fecha. **Idempotente, e isso não é zelo: é o requisito.**

        `close()` e `__exit__` são dois caminhos para o mesmo lugar, e `with get_conn() as c:` com
        um `c.close()` dentro dispara os dois. Sem a trava, a conexão voltaria DUAS vezes para a
        fila livre e o pool a entregaria a dois donos ao mesmo tempo — duas requisições escrevendo
        no mesmo socket. Não é lentidão, é corrupção, e silenciosa.
        """
        if self._solta:
            return
        self._solta = True
        if self._devolver is not None:
            self._devolver()
        else:
            self._conn.close()

    def close(self):
        self._soltar()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._soltar()

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

    @property
    def rowcount(self):
        # psycopg2 expõe rowcount (linhas afetadas pelo último execute) — sqlite também.
        # Sem isto, DELETE/UPDATE que leem cur.rowcount estouravam AttributeError no PG
        # (ex.: reset_drill_sessions → "nada acontece" no botão de reiniciar).
        return self._cur.rowcount

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
