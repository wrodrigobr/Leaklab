"""
repositories.py — Camada de acesso ao banco de dados.
Funções puras: recebem dados, persistem, retornam.
Sem lógica de negócio aqui.
"""
from __future__ import annotations
import json
import hashlib
import logging
from typing import Optional, List, Dict

try:
    import bcrypt as _bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

log = logging.getLogger(__name__)
from .schema import get_conn, USE_POSTGRES, now_sql, interval_sql


# ── Query adapter ─────────────────────────────────────────────────────────────

def _adapt(sql: str) -> str:
    """
    Adapta uma query SQLite para PostgreSQL se necessário.
    Converte ? → %s e datetime() → NOW().
    """
    if not USE_POSTGRES:
        return sql
    import re
    # Substituir placeholders ? por %s
    sql = re.sub(r'(?<!\w)\?(?!\w)', '%s', sql)
    # Substituir datetime('now')
    sql = sql.replace("datetime('now')", 'NOW()')
    # Substituir datetime('now', '-N days')
    sql = re.sub(
        r"datetime\('now',\s*'(-?\d+)\s*days?'\)",
        lambda m: f"NOW() + INTERVAL '{m.group(1)} days'",
        sql
    )
    # Substituir || (concat) — igual nos dois
    return sql


def _execute(conn, sql: str, params=None):
    """Executa query usando o _AdaptedConn wrapper."""
    # conn.execute() já adapta SQL e gerencia cursor internamente
    return conn.execute(sql, params or ())


def _fetchall(conn, sql: str, params=None) -> list:
    """Executa query SELECT e retorna lista de dicts."""
    result = conn.execute(sql, params or ())
    rows = result.fetchall()
    return [dict(r) for r in rows]


def _fetchone(conn, sql: str, params=None) -> Optional[dict]:
    """Executa query SELECT e retorna um dict ou None."""
    result = conn.execute(sql, params or ())
    row = result.fetchone()
    return dict(row) if row else None


def _insert(conn, sql: str, params=None) -> int:
    """Executa INSERT e retorna o ID gerado."""
    if USE_POSTGRES:
        if 'RETURNING' not in sql.upper():
            sql = sql.rstrip().rstrip(';') + ' RETURNING id'
        result = conn.execute(sql, params or ())
        row = result.fetchone()
        return dict(row)['id'] if row else None
    else:
        result = conn.execute(sql, params or ())
        return result.lastrowid


# ── Users ─────────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    if _BCRYPT_AVAILABLE:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    return hashlib.sha256(password.encode()).hexdigest()


def _check_password(password: str, stored_hash: str) -> bool:
    """Verifica senha — suporta hashes bcrypt e SHA-256 legados."""
    is_legacy = len(stored_hash) == 64 and all(c in '0123456789abcdef' for c in stored_hash)
    if is_legacy:
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    if _BCRYPT_AVAILABLE:
        try:
            return _bcrypt.checkpw(password.encode(), stored_hash.encode())
        except Exception:
            return False
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash


def create_user(username: str, email: str, password: str,
                role: str = 'player', coach_id: int | None = None) -> int:
    pw_hash = _hash_password(password)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, role, coach_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, email, pw_hash, role, coach_id)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            _adapt("SELECT * FROM users WHERE email = ?"), (email,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            _adapt("SELECT id, username, role FROM users WHERE username = ?"), (username,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def verify_password(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not row:
            return None
        user = dict(row)
        stored = user['password_hash']
        if not _check_password(password, stored):
            return None
        # Migrate legacy SHA-256 hash to bcrypt on successful login
        is_legacy = len(stored) == 64 and all(c in '0123456789abcdef' for c in stored)
        if is_legacy and _BCRYPT_AVAILABLE:
            new_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (new_hash, user['id']))
            conn.commit()
            log.info("Migrated user %s from SHA-256 to bcrypt", user['id'])
        return user
    finally:
        conn.close()


def get_students(coach_id: int) -> List[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, username, email, created_at, last_login "
            "FROM users WHERE coach_id = ?", (coach_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Tournaments ───────────────────────────────────────────────────────────────

def save_tournament(user_id: int, tournament_id: str, hero: str,
                    metrics: dict, site: str = 'pokerstars',
                    played_at: str | None = None,
                    result: str | None = None,
                    place: int | None = None,
                    buy_in: float | None = None,
                    prize: float | None = None,
                    profit: float | None = None,
                    raw_text: str | None = None,
                    tournament_name: str | None = None) -> int:
    conn = get_conn()
    lp = metrics.get('label_pct', {})
    try:
        # Upsert — INSERT ou UPDATE se já existe
        conn.execute("""
            INSERT INTO tournaments
              (user_id, tournament_id, site, tournament_name, hero, played_at, imported_at,
               hands_count, decisions_count, avg_score,
               standard_pct, marginal_pct, small_pct, clear_pct,
               result, place, buy_in, prize, profit, raw_text)
            VALUES (?,?,?,?,?,?,datetime('now'),?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id, tournament_id) DO UPDATE SET
              imported_at    = datetime('now'),
              tournament_name= excluded.tournament_name,
              hands_count    = excluded.hands_count,
              decisions_count= excluded.decisions_count,
              avg_score      = excluded.avg_score,
              standard_pct   = excluded.standard_pct,
              marginal_pct   = excluded.marginal_pct,
              small_pct      = excluded.small_pct,
              clear_pct      = excluded.clear_pct,
              result         = excluded.result,
              place          = excluded.place,
              buy_in         = excluded.buy_in,
              prize          = excluded.prize,
              profit         = excluded.profit,
              raw_text       = excluded.raw_text
        """, (
            user_id, tournament_id, site, tournament_name, hero, played_at,
            metrics.get('total_hands', 0),
            metrics.get('total_decisions', 0),
            metrics.get('avg_mistake_score'),
            lp.get('standard'), lp.get('marginal'),
            lp.get('small_mistake'), lp.get('clear_mistake'),
            result, place, buy_in, prize, profit, raw_text,
        ))
        conn.commit()
        # Buscar o ID (seja novo ou existente) — SELECT separado
        row = conn.execute(
            "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?",
            (user_id, tournament_id)
        ).fetchone()
        return row['id']
    finally:
        conn.close()


def save_decisions(tournament_db_id: int, results: List[dict]):
    """Salva todas as decisões de uma análise. Limpa as antigas primeiro."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM decisions WHERE tournament_id = ?",
                     (tournament_db_id,))
        rows = []
        for r in results:
            bd  = r.get('evaluation', {}).get('scoreBreakdown', {})
            ctx = r.get('context', {})
            level_bb_val = r.get('level_bb', 0) or 1
            spot_ctx     = r.get('spot', {})
            raw_pot  = spot_ctx.get('potSize') or 0
            raw_face = spot_ctx.get('facingSize') or 0
            pot_size_bb   = round(raw_pot  / level_bb_val, 1) if raw_pot  else None
            facing_bet_bb = round(raw_face / level_bb_val, 1) if raw_face else None
            rows.append((
                tournament_db_id,
                r.get('handId', ''),
                r.get('street', ''),
                r.get('hero_cards', ''),
                json.dumps(r.get('board', [])),
                r.get('actionTaken', r.get('action_taken', '')),
                r.get('bestAction',  r.get('best_action',  '')),
                r.get('evaluation', {}).get('label', ''),
                r.get('evaluation', {}).get('mistakeScore', 0),
                bd.get('mathPenalty', 0),
                bd.get('rangePenalty', 0),
                ctx.get('mRatio'),
                ctx.get('icmPressure'),
                ctx.get('heroStackBb'),
                r.get('draw_profile', ctx.get('drawProfile', '')),
                r.get('position', ''),
                r.get('num_players', 0),
                r.get('level_sb', 0),
                r.get('level_bb', 0),
                r.get('level_num', 0),
                r.get('note', ''),
                1 if r.get('is_3bet') else 0,
                r.get('showdown_result'),
                pot_size_bb,
                facing_bet_bb,
            ))
        conn.executemany("""
            INSERT INTO decisions
              (tournament_id, hand_id, street, hero_cards, board,
               action_taken, best_action, label, score,
               math_penalty, range_penalty, m_ratio, icm_pressure,
               stack_bb, draw_profile, position, num_players,
               level_sb, level_bb, level_num, note, is_3bet, showdown_result,
               pot_size, facing_bet)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()
    finally:
        conn.close()


def get_tournaments(user_id: int, limit: int = 50) -> List[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT t.id, t.tournament_id, t.site, t.tournament_name, t.hero, t.played_at, t.imported_at,
                   t.hands_count, t.decisions_count, t.avg_score,
                   t.standard_pct, t.clear_pct, t.result, t.place, t.llm_summary,
                   t.buy_in, t.prize, t.profit,
                   COUNT(CASE WHEN d.label = 'clear_mistake' THEN 1 END) AS clear_count,
                   COUNT(CASE WHEN d.label = 'small_mistake' THEN 1 END) AS small_count
            FROM tournaments t
            LEFT JOIN decisions d ON d.tournament_id = t.id
            WHERE t.user_id = ?
            GROUP BY t.id
            ORDER BY t.imported_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tournament(user_id: int, tournament_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM tournaments WHERE user_id=? AND tournament_id=?",
            (user_id, tournament_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_tournament_by_db_id(user_id: int, db_id: int) -> Optional[dict]:
    """Busca torneio pelo ID interno do banco (int), verificando ownership."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM tournaments WHERE id=? AND user_id=?",
            (db_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_llm_summary(tournament_db_id: int, summary: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE tournaments SET llm_summary=? WHERE id=?",
            (summary, tournament_db_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_decisions(tournament_db_id: int) -> List[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE tournament_id=? ORDER BY id",
            (tournament_db_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Tournament comparison ─────────────────────────────────────────────────────

def get_tournaments_comparison(user_id: int, tournament_ids: list) -> list:
    """Retorna dados agregados de múltiplos torneios para comparação lado a lado."""
    if not tournament_ids or len(tournament_ids) < 2:
        return []

    conn = get_conn()
    try:
        placeholders = ','.join('?' * len(tournament_ids))
        rows = conn.execute(
            f"SELECT * FROM tournaments WHERE user_id=? AND tournament_id IN ({placeholders})",
            [user_id] + list(tournament_ids)
        ).fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        t = dict(row)
        phases    = get_phase_analysis(t['id'])
        decisions = get_decisions(t['id'])
        top_leaks = _compute_comparison_leaks(decisions)
        result.append({
            'tournament_id':   t['tournament_id'],
            'tournament_name': t.get('tournament_name'),
            'played_at':       t.get('played_at') or t.get('imported_at'),
            'site':            t.get('site'),
            'standard_pct':    t.get('standard_pct'),
            'avg_score':       t.get('avg_score'),
            'clear_pct':       t.get('clear_pct'),
            'hands_count':     t.get('hands_count'),
            'decisions_count': t.get('decisions_count'),
            'profit':          t.get('profit'),
            'buy_in':          t.get('buy_in'),
            'place':           t.get('place'),
            'phases':          phases,
            'top_leaks':       top_leaks,
        })

    result.sort(key=lambda x: x.get('played_at') or '')
    return result


def _compute_comparison_leaks(decisions: list) -> list:
    from collections import defaultdict
    spot_scores: dict = defaultdict(list)
    for d in decisions:
        key = f"{d.get('street', '?')}/{d.get('best_action', '?')}"
        spot_scores[key].append(d.get('score', 0) or 0)
    return sorted(
        [(k, round(sum(v) / len(v), 3), len(v)) for k, v in spot_scores.items() if len(v) >= 2],
        key=lambda x: x[1], reverse=True
    )[:5]


# ── Evolution metrics (queries para o dashboard) ──────────────────────────────

def get_evolution_metrics(user_id: int, days: int = 90) -> List[dict]:
    """Retorna métricas por torneio para o gráfico de evolução."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT tournament_id, site, played_at, imported_at,
                   hands_count, decisions_count, avg_score,
                   standard_pct, clear_pct,
                   buy_in, prize, profit, place, result
            FROM tournaments
            WHERE user_id = ?
              AND imported_at >= ?
            ORDER BY imported_at ASC
        """, (user_id, since)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_leak_summary(user_id: int, days: int = 90) -> List[dict]:
    """Agrega leaks por street/ação no período."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT
                d.street || '/' || d.best_action AS spot,
                COUNT(*)                          AS n,
                AVG(d.score)                      AS avg_score,
                SUM(d.score)                      AS total_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND t.imported_at >= ?
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
            HAVING COUNT(*) >= 2
            ORDER BY avg_score DESC
            LIMIT 10
        """, (user_id, since)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_leak_roi_impact(user_id: int, days: int = 90) -> list:
    """Leaks enriquecidos com ROI estimado, priority_score e trend de progressão."""
    from datetime import datetime, timedelta
    now   = datetime.utcnow()
    since = (now - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    # Trend: compare last 30 days vs. previous 30 days
    recent_since = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    prev_since   = (now - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT
                d.street || '/' || d.best_action  AS spot,
                COUNT(*)                           AS n,
                AVG(d.score)                       AS avg_score,
                SUM(d.score)                       AS total_score,
                AVG(COALESCE(t.buy_in, 0))         AS avg_buy_in,
                COUNT(*) * AVG(d.score)            AS priority_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND t.imported_at >= ?
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
            HAVING COUNT(*) >= 2
            ORDER BY priority_score DESC
            LIMIT 10
        """), (user_id, since)).fetchall()

        # Recent period scores for trend comparison
        recent_rows = conn.execute(_adapt("""
            SELECT d.street || '/' || d.best_action AS spot, AVG(d.score) AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
        """), (user_id, recent_since)).fetchall()
        recent_map = {r['spot']: r['avg_score'] for r in recent_rows}

        # Previous period scores
        prev_rows = conn.execute(_adapt("""
            SELECT d.street || '/' || d.best_action AS spot, AVG(d.score) AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ? AND t.imported_at < ?
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
        """), (user_id, prev_since, recent_since)).fetchall()
        prev_map = {r['spot']: r['avg_score'] for r in prev_rows}

        # Drill stats per spot (last 30 days)
        drill_rows = conn.execute(_adapt("""
            SELECT
                dec.street || '/' || dec.best_action  AS spot,
                COUNT(*)                               AS drill_count,
                SUM(CASE WHEN ds.delta < 0 THEN 1 ELSE 0 END) AS drill_correct
            FROM drill_sessions ds
            JOIN decisions dec ON dec.id = ds.decision_id
            WHERE ds.user_id = ? AND ds.drilled_at >= datetime('now', '-30 days')
            GROUP BY spot
        """), (user_id,)).fetchall()
        drill_map = {
            r['spot']: {
                'count':    r['drill_count'],
                'accuracy': round(r['drill_correct'] / r['drill_count'] * 100, 1) if r['drill_count'] else None,
            }
            for r in drill_rows
        }

        result = []
        for rank, row in enumerate(rows, 1):
            r = dict(row)
            n_monthly = r['n'] * (30.0 / days)
            r['ev_loss_monthly'] = round(n_monthly * r['avg_score'] * (r['avg_buy_in'] or 0) * 0.10, 2)
            r['priority_rank'] = rank
            # Trend from tournament decisions
            s_recent = recent_map.get(r['spot'])
            s_prev   = prev_map.get(r['spot'])
            if s_recent is None or s_prev is None:
                r['trend'] = 'new'
            elif s_recent < s_prev * 0.85:
                r['trend'] = 'improving'
            elif s_recent > s_prev * 1.15:
                r['trend'] = 'regressing'
            else:
                r['trend'] = 'stagnant'
            # Ghost Table drill activity for this spot
            d = drill_map.get(r['spot'], {})
            r['drill_count']    = d.get('count', 0)
            r['drill_accuracy'] = d.get('accuracy')
            result.append(r)
        return result
    finally:
        conn.close()


def get_pressure_profile(user_id: int, days: int = 90) -> dict:
    """PERF-004 — Detecta colapso técnico sob pressão ICM."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        # Per-pressure avg_score (baseline = all decisions, not just mistakes)
        rows = conn.execute(_adapt("""
            SELECT
                COALESCE(d.icm_pressure, 'none') AS pressure,
                COUNT(*)                          AS n,
                AVG(d.score)                      AS avg_score,
                AVG(CASE WHEN d.label='standard' THEN 1.0 ELSE 0.0 END) AS standard_rate
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
            GROUP BY pressure
            HAVING COUNT(*) >= 3
        """), (user_id, since)).fetchall()

        pressure_map = {r['pressure']: dict(r) for r in rows}

        baseline_row = conn.execute(_adapt("""
            SELECT AVG(d.score) AS avg_score, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
        """), (user_id, since)).fetchone()

        baseline_score = baseline_row['avg_score'] if baseline_row else None

        score_high = pressure_map.get('high', {}).get('avg_score')
        score_none = pressure_map.get('none', {}).get('avg_score')
        collapse_delta = None
        if score_high is not None and score_none is not None:
            collapse_delta = round(score_high - score_none, 4)

        return {
            'baseline_score':  round(baseline_score, 4) if baseline_score else None,
            'by_pressure':     pressure_map,
            'collapse_delta':  collapse_delta,
            'has_collapse':    collapse_delta is not None and collapse_delta > 0.08,
        }
    finally:
        conn.close()


def get_confidence_drift(user_id: int, days: int = 30) -> dict:
    """PERF-005 — Detecta sessões com degradação técnica (possível tilt)."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        # Per-tournament avg_score
        tourn_rows = conn.execute(_adapt("""
            SELECT
                t.id              AS tournament_id,
                t.tournament_name AS name,
                t.played_at,
                COUNT(d.id)       AS n_decisions,
                AVG(d.score)      AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
            GROUP BY t.id
            HAVING COUNT(d.id) >= 3
            ORDER BY t.played_at DESC
        """), (user_id, since)).fetchall()

        if not tourn_rows:
            return {'drift_detected': False, 'affected_sessions': 0, 'severity': None, 'sessions': []}

        scores = [r['avg_score'] for r in tourn_rows if r['avg_score'] is not None]
        if not scores:
            return {'drift_detected': False, 'affected_sessions': 0, 'severity': None, 'sessions': []}

        baseline = sum(scores) / len(scores)
        threshold = baseline * 1.30

        flagged = [
            {
                'tournament_id': r['tournament_id'],
                'name':          r['name'],
                'played_at':     r['played_at'],
                'avg_score':     round(r['avg_score'], 4),
                'delta_pct':     round((r['avg_score'] - baseline) / baseline * 100, 1) if baseline else 0,
            }
            for r in tourn_rows
            if r['avg_score'] is not None and r['avg_score'] > threshold
        ]

        n = len(flagged)
        severity = None
        if n >= 5:   severity = 'severe'
        elif n >= 3: severity = 'moderate'
        elif n >= 1: severity = 'mild'

        return {
            'drift_detected':   n > 0,
            'affected_sessions': n,
            'severity':         severity,
            'baseline_score':   round(baseline, 4),
            'sessions':         flagged[:5],
        }
    finally:
        conn.close()


def get_drill_spots(user_id: int, limit: int = 10, street: str = None, spot: str = None) -> list:
    """Sprint R — Retorna spots disponíveis para drill respeitando SRS (next_drill_at <= now)."""
    from datetime import datetime
    now_str = datetime.utcnow().isoformat()
    conn = get_conn()
    try:
        street_filter = "AND d.street = ?" if street else ""
        spot_filter   = "AND (d.street || '/' || d.best_action) = ?" if spot else ""
        params = [user_id, user_id, now_str]
        if street: params.append(street)
        if spot:   params.append(spot)
        params.append(limit)

        rows = conn.execute(_adapt(f"""
            SELECT
                d.id, d.hand_id, d.street, d.hero_cards, d.board,
                d.action_taken, d.best_action, d.label, d.score,
                d.m_ratio, d.icm_pressure, d.stack_bb, d.position,
                d.num_players, d.is_3bet, d.level_bb, d.note, d.draw_profile,
                d.pot_size, d.facing_bet,
                t.tournament_name, t.played_at, t.buy_in,
                ds_last.next_drill_at, ds_last.srs_interval_days
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            LEFT JOIN (
                SELECT ds1.decision_id, ds1.next_drill_at, ds1.srs_interval_days
                FROM drill_sessions ds1
                WHERE ds1.user_id = ?
                  AND ds1.drilled_at = (
                      SELECT MAX(ds2.drilled_at) FROM drill_sessions ds2
                      WHERE ds2.decision_id = ds1.decision_id AND ds2.user_id = ds1.user_id
                  )
            ) ds_last ON ds_last.decision_id = d.id
            WHERE t.user_id = ?
              AND d.label IN ('small_mistake','clear_mistake')
              AND (ds_last.next_drill_at IS NULL OR ds_last.next_drill_at <= ?)
              {street_filter}
              {spot_filter}
            ORDER BY
                CASE WHEN ds_last.next_drill_at IS NULL THEN 0 ELSE 1 END ASC,
                ds_last.next_drill_at ASC,
                d.score DESC
            LIMIT ?
        """), params).fetchall()

        now = datetime.utcnow()
        result = []
        for row in rows:
            r = dict(row)
            nda = r.get('next_drill_at')
            if nda:
                try:
                    nda_dt = datetime.fromisoformat(str(nda).split('.')[0])
                    r['days_overdue'] = max(0, (now - nda_dt).days)
                except Exception:
                    r['days_overdue'] = 0
            else:
                r['days_overdue'] = None  # never drilled
            result.append(r)
        return result
    finally:
        conn.close()


_SRS_INTERVALS = [3, 7, 14, 28, 60]


def save_drill_session(user_id: int, decision_id: int, new_action: str,
                       new_score: float, original_score: float) -> dict:
    """Sprint R — Salva drill com lógica SRS: acerto dobra intervalo, erro reseta para 3 dias."""
    from datetime import datetime, timedelta
    delta      = round(new_score - original_score, 4)
    is_correct = delta < 0  # score melhorou = acerto

    conn = get_conn()
    try:
        last = conn.execute(_adapt("""
            SELECT srs_interval_days FROM drill_sessions
            WHERE user_id = ? AND decision_id = ?
            ORDER BY drilled_at DESC LIMIT 1
        """), (user_id, decision_id)).fetchone()

        last_interval = (last['srs_interval_days'] or 3) if last else 3

        if is_correct:
            try:
                idx = _SRS_INTERVALS.index(last_interval)
                new_interval = _SRS_INTERVALS[min(idx + 1, len(_SRS_INTERVALS) - 1)]
            except ValueError:
                new_interval = min(last_interval * 2, _SRS_INTERVALS[-1])
        else:
            new_interval = _SRS_INTERVALS[0]

        next_drill_at = (datetime.utcnow() + timedelta(days=new_interval)).isoformat()

        conn.execute(_adapt("""
            INSERT INTO drill_sessions
                (user_id, decision_id, new_action, new_score, original_score, delta, next_drill_at, srs_interval_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """), (user_id, decision_id, new_action, new_score, original_score,
               delta, next_drill_at, new_interval))
        conn.commit()
        return {
            'decision_id':       decision_id,
            'new_action':        new_action,
            'new_score':         new_score,
            'original_score':    original_score,
            'delta':             delta,
            'is_correct':        is_correct,
            'next_drill_at':     next_drill_at,
            'srs_interval_days': new_interval,
        }
    finally:
        conn.close()


def get_drill_stats(user_id: int, days: int = 30) -> dict:
    """Sprint K — Estatísticas de drill dos últimos N dias."""
    conn = get_conn()
    try:
        row = conn.execute(_adapt("""
            SELECT
                COUNT(*)                                          AS total,
                AVG(delta)                                        AS avg_delta,
                SUM(CASE WHEN delta < 0 THEN 1 ELSE 0 END)       AS correct,
                SUM(CASE WHEN delta >= 0 THEN 1 ELSE 0 END)      AS incorrect
            FROM drill_sessions
            WHERE user_id = ? AND drilled_at >= datetime('now', ? || ' days')
        """), (user_id, f'-{days}')).fetchone()
        if not row or not row['total']:
            return {'total': 0, 'correct': 0, 'incorrect': 0, 'accuracy': None, 'avg_delta': None}
        total = row['total'] or 0
        correct = row['correct'] or 0
        return {
            'total':     total,
            'correct':   correct,
            'incorrect': row['incorrect'] or 0,
            'accuracy':  round(correct / total * 100, 1) if total > 0 else None,
            'avg_delta': round(row['avg_delta'], 4) if row['avg_delta'] is not None else None,
        }
    finally:
        conn.close()


def get_decision_for_drill(user_id: int, decision_id: int) -> dict | None:
    """Sprint K — Busca decisão verificando que pertence ao usuário (dados completos para análise)."""
    conn = get_conn()
    try:
        row = conn.execute(_adapt("""
            SELECT d.id, d.best_action, d.score, d.label,
                   d.street, d.hero_cards, d.board, d.action_taken,
                   d.m_ratio, d.icm_pressure, d.stack_bb, d.draw_profile,
                   d.position, d.num_players, d.level_sb, d.level_bb,
                   d.level_num, d.note, d.is_3bet, d.pot_size, d.facing_bet
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.id = ? AND t.user_id = ?
        """), (decision_id, user_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_icm_performance(user_id: int, days: int = 90) -> dict:
    """Performance separada por nível de ICM pressure."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT
                d.icm_pressure,
                COUNT(*)          AS n,
                AVG(d.score)      AS avg_score,
                AVG(CASE WHEN d.label='standard' THEN 1.0 ELSE 0.0 END) AS standard_rate
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND t.imported_at >= ?
            GROUP BY d.icm_pressure
        """, (user_id, since)).fetchall()
        return {r['icm_pressure']: dict(r) for r in rows if r['icm_pressure']}
    finally:
        conn.close()

def get_breakdown(user_id: int, days: int = 90) -> dict:
    """Agrega decisões por street, posição e label para os HUDs do dashboard."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        base = """
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
        """
        by_street = conn.execute(f"""
            SELECT d.street,
                   COUNT(*) AS n,
                   AVG(d.score) AS avg_score,
                   AVG(CASE WHEN d.label='standard' THEN 1.0 ELSE 0.0 END) AS standard_rate
            {base} AND d.street IS NOT NULL
            GROUP BY d.street
        """, (user_id, since)).fetchall()

        by_position = conn.execute(f"""
            SELECT d.position,
                   COUNT(*) AS n,
                   AVG(d.score) AS avg_score,
                   AVG(CASE WHEN d.label='standard' THEN 1.0 ELSE 0.0 END) AS standard_rate
            {base} AND d.position IS NOT NULL
            GROUP BY d.position
            ORDER BY standard_rate DESC
        """, (user_id, since)).fetchall()

        by_label = conn.execute(f"""
            SELECT d.label, COUNT(*) AS n
            {base}
            GROUP BY d.label
        """, (user_id, since)).fetchall()

        return {
            'by_street':   {r['street']:   dict(r) for r in by_street},
            'by_position': {r['position']: dict(r) for r in by_position if r['position']},
            'by_label':    {r['label']:    r['n']   for r in by_label   if r['label']},
        }
    finally:
        conn.close()


def get_player_stats(user_id: int, days: int = 90) -> dict:
    """Computes poker HUD stats from stored decisions."""
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        # ── Preflop basics (VPIP, PFR) ───────────────────────────────────────
        preflop = conn.execute("""
            SELECT
                COUNT(DISTINCT d.hand_id) AS total_hands,
                COUNT(DISTINCT CASE WHEN d.action_taken IN ('call','raise','jam') THEN d.hand_id END) AS vpip_hands,
                COUNT(DISTINCT CASE WHEN d.action_taken IN ('raise','jam') THEN d.hand_id END) AS pfr_hands
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ? AND d.street = 'preflop'
        """, (user_id, since)).fetchone()

        # ── Postflop aggression (AF) ─────────────────────────────────────────
        postflop = conn.execute("""
            SELECT
                COUNT(CASE WHEN d.action_taken IN ('bet','raise','jam') THEN 1 END) AS aggressive,
                COUNT(CASE WHEN d.action_taken = 'call' THEN 1 END) AS passive
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ? AND d.street != 'preflop'
        """, (user_id, since)).fetchone()

        # ── Flop bet frequency ───────────────────────────────────────────────
        flop_row = conn.execute("""
            SELECT
                COUNT(*) AS total_flop,
                COUNT(CASE WHEN d.action_taken IN ('bet','raise','jam') THEN 1 END) AS flop_bets
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ? AND d.street = 'flop'
        """, (user_id, since)).fetchone()

        # ── Fold-to-3BET: hands where hero raised preflop THEN folded ────────
        # Pattern: 2 preflop decisions — first is raise/jam, second is fold (= faced 3-bet)
        # faced_3bet_n = hands where hero raised AND had any second preflop action
        f3b_row = conn.execute("""
            SELECT
                SUM(CASE WHEN sub.first_raise_id IS NOT NULL
                          AND sub.fold_after_raise_id IS NOT NULL
                          AND sub.fold_after_raise_id > sub.first_raise_id
                     THEN 1 ELSE 0 END) AS fold_to_3bet_n,
                COUNT(*) AS faced_3bet_n
            FROM (
                SELECT d.hand_id,
                       MIN(CASE WHEN d.action_taken IN ('raise','jam') THEN d.id END) AS first_raise_id,
                       MIN(CASE WHEN d.action_taken = 'fold' THEN d.id END)            AS fold_after_raise_id
                FROM decisions d
                JOIN tournaments t ON t.id = d.tournament_id
                WHERE t.user_id = ? AND t.imported_at >= ? AND d.street = 'preflop'
                GROUP BY d.hand_id
                HAVING COUNT(*) > 1
                   AND MIN(CASE WHEN d.action_taken IN ('raise','jam') THEN d.id END) IS NOT NULL
            ) sub
        """, (user_id, since)).fetchone()

        # ── WTSD approx: hands reaching river / hands seeing flop ────────────
        wtsd_row = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN d.street = 'flop'  THEN d.hand_id END) AS saw_flop,
                COUNT(DISTINCT CASE WHEN d.street = 'river' THEN d.hand_id END) AS saw_river
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
        """, (user_id, since)).fetchone()

        # ── 3BET%: hands where hero 3-bet / total preflop hands ──────────────
        tbet_row = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN d.is_3bet = 1 THEN d.hand_id END) AS three_bet_n,
                COUNT(DISTINCT d.hand_id) AS total_n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ? AND d.street = 'preflop'
        """, (user_id, since)).fetchone()

        # ── W$SD: hands won at showdown / total showdown hands ───────────────
        wsd_row = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN d.showdown_result = 'won'  THEN d.hand_id END) AS sd_won,
                COUNT(DISTINCT CASE WHEN d.showdown_result IS NOT NULL THEN d.hand_id END) AS sd_total
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
        """, (user_id, since)).fetchone()

        # ── Compute stats ────────────────────────────────────────────────────
        pf   = dict(preflop)  if preflop  else {}
        po   = dict(postflop) if postflop else {}
        fb   = dict(flop_row) if flop_row else {}
        f3b  = dict(f3b_row)  if f3b_row  else {}
        wt   = dict(wtsd_row) if wtsd_row else {}
        tb   = dict(tbet_row) if tbet_row else {}
        wsd  = dict(wsd_row)  if wsd_row  else {}

        total       = pf.get('total_hands', 0) or 0
        vpip_h      = pf.get('vpip_hands', 0) or 0
        pfr_h       = pf.get('pfr_hands', 0) or 0
        aggressive  = po.get('aggressive', 0) or 0
        passive     = po.get('passive', 0) or 0
        flop_total  = fb.get('total_flop', 0) or 0
        flop_bets_n = fb.get('flop_bets', 0) or 0
        f3b_n       = f3b.get('fold_to_3bet_n', 0) or 0
        faced_3b_n  = f3b.get('faced_3bet_n', 0) or 0
        saw_flop    = wt.get('saw_flop', 0) or 0
        saw_river   = wt.get('saw_river', 0) or 0
        three_bet_n = tb.get('three_bet_n', 0) or 0
        pf_total    = tb.get('total_n', 0) or 0
        sd_won      = wsd.get('sd_won', 0) or 0
        sd_total    = wsd.get('sd_total', 0) or 0

        return {
            'total_hands':  total,
            'vpip':         round(vpip_h / total * 100, 1)           if total > 0      else None,
            'pfr':          round(pfr_h  / total * 100, 1)           if total > 0      else None,
            'af':           round(aggressive / passive, 2)            if passive > 0    else None,
            'flop_bet_pct': round(flop_bets_n / flop_total * 100, 1) if flop_total > 0 else None,
            'fold_to_3bet': round(f3b_n / faced_3b_n * 100, 1)      if faced_3b_n > 0 else None,
            'wtsd':         round(saw_river / saw_flop * 100, 1)     if saw_flop > 0   else None,
            'three_bet':    round(three_bet_n / pf_total * 100, 1)   if pf_total > 0   else None,
            'w_at_sd':      round(sd_won / sd_total * 100, 1)        if sd_total > 0   else None,
        }
    finally:
        conn.close()


def get_player_level(user_id: int, min_tournaments: int = 5, days: int = 30) -> dict:
    """
    Calcula o nível de gamificação do jogador baseado na média de standard_pct.
    Usa os últimos N torneios (min 5, ou dentro dos últimos `days` dias).
    standard_pct está em escala 0-100 no banco.
    """
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    LEVELS = [
        {"name": "Iniciante", "icon": "🎯", "min": 0,    "max": 60},
        {"name": "Estudante", "icon": "📖", "min": 60,   "max": 70},
        {"name": "Grinder",   "icon": "⚙️", "min": 70,   "max": 77},
        {"name": "Regular",   "icon": "📈", "min": 77,   "max": 86},
        {"name": "Sólido",    "icon": "🔷", "min": 86,   "max": 92},
        {"name": "Expert",    "icon": "♠",  "min": 92,   "max": 96},
        {"name": "Elite",     "icon": "👑", "min": 96,   "max": 100},
    ]

    conn = get_conn()
    try:
        # Pega os últimos min_tournaments ou todos do período (o que for maior)
        rows = conn.execute("""
            SELECT standard_pct, avg_score, imported_at
            FROM tournaments
            WHERE user_id = ? AND standard_pct IS NOT NULL
            ORDER BY imported_at DESC
            LIMIT 20
        """, (user_id,)).fetchall()

        if not rows:
            return {"level": None, "tournament_count": 0}

        # Garante mínimo de min_tournaments tourneys
        recent_rows = [r for r in rows
                       if (r['imported_at'] or '') >= since]
        use = recent_rows if len(recent_rows) >= min_tournaments else list(rows[:max(min_tournaments, len(rows))])

        std_values = [r['standard_pct'] for r in use if r['standard_pct'] is not None]
        if not std_values:
            return {"level": None, "tournament_count": 0}

        avg_std = round(sum(std_values) / len(std_values), 2)

        # Determina nível atual
        current = LEVELS[0]
        for lv in LEVELS:
            if avg_std >= lv["min"]:
                current = lv

        next_lv = next((lv for lv in LEVELS if lv["min"] > current["min"]), None)
        span = current["max"] - current["min"]
        progress = round((avg_std - current["min"]) / span, 3) if span > 0 else 1.0
        progress = max(0.0, min(1.0, progress))

        # Top leaks que bloqueiam o avanço (spots com mais erros)
        top_leaks_rows = conn.execute("""
            SELECT d.street || '/' || d.best_action AS spot,
                   COUNT(*) AS n,
                   AVG(d.score) AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND d.label IN ('small_mistake', 'clear_mistake')
              AND t.imported_at >= ?
            GROUP BY spot
            HAVING COUNT(*) >= 2
            ORDER BY n DESC
            LIMIT 3
        """, (user_id, since)).fetchall()

        return {
            "level":            current["name"],
            "icon":             current["icon"],
            "standard_pct":     avg_std,
            "level_min":        current["min"],
            "level_max":        current["max"],
            "next_level":       next_lv["name"] if next_lv else None,
            "next_level_icon":  next_lv["icon"] if next_lv else None,
            "next_pct":         next_lv["min"] if next_lv else None,
            "progress":         progress,
            "tournament_count": len(use),
            "top_blocking_leaks": [{"spot": r["spot"], "n": r["n"], "avg_score": round(r["avg_score"], 1)}
                                    for r in top_leaks_rows],
        }
    finally:
        conn.close()


def get_llm_cache(user_id: int, cache_key: str) -> Optional[str]:
    """Retorna análise cacheada ou None se não existir."""
    conn = get_conn()
    try:
        row = _fetchone(conn,
            "SELECT analysis FROM llm_cache WHERE user_id=? AND cache_key=?",
            (user_id, cache_key))
        return row['analysis'] if row else None
    finally:
        conn.close()


def set_llm_cache(user_id: int, cache_key: str, analysis: str) -> None:
    """Salva ou atualiza análise no cache."""
    conn = get_conn()
    try:
        if USE_POSTGRES:
            conn.execute("""
                INSERT INTO llm_cache (user_id, cache_key, analysis)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, cache_key) DO UPDATE SET
                    analysis   = excluded.analysis,
                    created_at = NOW()
            """, (user_id, cache_key, analysis))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO llm_cache (user_id, cache_key, analysis)
                VALUES (?, ?, ?)
            """, (user_id, cache_key, analysis))
        conn.commit()
    finally:
        conn.close()


# ── Coach system ──────────────────────────────────────────────────────────────

import secrets
import json as _json


def generate_invite_key() -> str:
    """Gera chave única no formato COACH-XXXXX."""
    token = secrets.token_hex(3).upper()
    return f"COACH-{token}"


def assign_invite_key(user_id: int) -> str:
    """Atribui chave de convite a um coach. Idempotente."""
    conn = get_conn()
    try:
        # Verificar se já tem chave
        row = conn.execute(
            "SELECT invite_key FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if row and row['invite_key']:
            return row['invite_key']
        # Gerar nova chave única
        while True:
            key = generate_invite_key()
            exists = conn.execute(
                "SELECT 1 FROM users WHERE invite_key=?", (key,)
            ).fetchone()
            if not exists:
                break
        conn.execute(
            "UPDATE users SET invite_key=? WHERE id=?", (key, user_id)
        )
        conn.commit()
        return key
    finally:
        conn.close()


def get_coach_by_invite_key(key: str) -> Optional[dict]:
    """Busca coach pela chave de convite."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, email, role FROM users WHERE invite_key=?",
            (key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def link_student_to_coach(student_id: int, invite_key: str) -> dict:
    """
    Vincula aluno ao coach via chave de convite.
    Retorna {'ok': True, 'coach': {...}} ou {'ok': False, 'error': '...'}
    """
    coach = get_coach_by_invite_key(invite_key)
    if not coach:
        return {'ok': False, 'error': 'Chave de convite inválida'}
    if coach['id'] == student_id:
        return {'ok': False, 'error': 'Você não pode se vincular a si mesmo'}

    conn = get_conn()
    try:
        # Verificar limite de alunos do coach
        profile = conn.execute(
            "SELECT max_students FROM coach_profiles WHERE user_id=?",
            (coach['id'],)
        ).fetchone()
        max_s = profile['max_students'] if profile else 5
        current = conn.execute(
            "SELECT COUNT(*) as n FROM users WHERE coach_id=?",
            (coach['id'],)
        ).fetchone()['n']
        if current >= max_s:
            return {'ok': False, 'error': f'Coach atingiu o limite de {max_s} alunos no plano atual'}

        conn.execute(
            "UPDATE users SET coach_id=?, invited_by_key=? WHERE id=?",
            (coach['id'], invite_key, student_id)
        )
        conn.commit()
        return {'ok': True, 'coach': coach}
    finally:
        conn.close()


# ── Coach profile ──────────────────────────────────────────────────────────────

def upsert_coach_profile(user_id: int, display_name: str = '',
                          bio: str = '', specialties: list | None = None,
                          contact_email: str | None = None,
                          contact_link: str | None = None,
                          is_public: bool = True,
                          max_students: int = 5,
                          # Sprint 7 — campos estendidos
                          photo_url: str | None = None,
                          experience_years: int | None = None,
                          stakes: str | None = None,
                          coaching_style: str | None = None,
                          languages: list | None = None,
                          biggest_results: list | None = None,
                          price_per_session: float | None = None,
                          price_monthly: float | None = None,
                          trial_available: bool = False,
                          availability: str | None = None,
                          social_youtube: str | None = None,
                          social_twitch: str | None = None,
                          social_twitter: str | None = None) -> dict:
    """Cria ou atualiza perfil público do coach."""
    specs_json = _json.dumps(specialties or [])
    langs_json = _json.dumps(languages or ['pt'])
    results_json = _json.dumps(biggest_results or [])
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO coach_profiles
              (user_id, display_name, bio, specialties, contact_email,
               contact_link, is_public, max_students,
               photo_url, experience_years, stakes, coaching_style,
               languages, biggest_results, price_per_session, price_monthly,
               trial_available, availability,
               social_youtube, social_twitch, social_twitter,
               updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
              display_name      = excluded.display_name,
              bio               = excluded.bio,
              specialties       = excluded.specialties,
              contact_email     = excluded.contact_email,
              contact_link      = excluded.contact_link,
              is_public         = excluded.is_public,
              max_students      = excluded.max_students,
              photo_url         = excluded.photo_url,
              experience_years  = excluded.experience_years,
              stakes            = excluded.stakes,
              coaching_style    = excluded.coaching_style,
              languages         = excluded.languages,
              biggest_results   = excluded.biggest_results,
              price_per_session = excluded.price_per_session,
              price_monthly     = excluded.price_monthly,
              trial_available   = excluded.trial_available,
              availability      = excluded.availability,
              social_youtube    = excluded.social_youtube,
              social_twitch     = excluded.social_twitch,
              social_twitter    = excluded.social_twitter,
              updated_at        = datetime('now')
        """, (user_id, display_name, bio, specs_json,
              contact_email, contact_link, int(is_public), max_students,
              photo_url, experience_years, stakes, coaching_style,
              langs_json, results_json, price_per_session, price_monthly,
              int(trial_available), availability,
              social_youtube, social_twitch, social_twitter))
        conn.commit()
        return get_coach_profile(user_id)
    finally:
        conn.close()


def _parse_profile(d: dict) -> dict:
    d['specialties']    = _json.loads(d.get('specialties')    or '[]')
    d['languages']      = _json.loads(d.get('languages')      or '["pt"]')
    d['biggest_results'] = _json.loads(d.get('biggest_results') or '[]')
    d['trial_available'] = bool(d.get('trial_available', 0))
    return d


def get_coach_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT cp.*, u.username, u.email, u.invite_key, u.plan,
                   (SELECT COUNT(*) FROM users WHERE coach_id = u.id) as student_count,
                   (SELECT ROUND(AVG(CAST(rating AS REAL)),1)
                    FROM coach_reviews WHERE coach_id = u.id) as avg_rating,
                   (SELECT COUNT(*) FROM coach_reviews WHERE coach_id = u.id) as review_count
            FROM coach_profiles cp
            JOIN users u ON u.id = cp.user_id
            WHERE cp.user_id = ?
        """, (user_id,)).fetchone()
        if not row:
            return None
        return _parse_profile(dict(row))
    finally:
        conn.close()


# ── Coach Reviews (BACK-006) ──────────────────────────────────────────────────

def upsert_review(coach_id: int, student_id: int,
                  rating: int, review_text: str | None = None) -> dict:
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO coach_reviews (coach_id, student_id, rating, review_text, updated_at)
            VALUES (?,?,?,?,datetime('now'))
            ON CONFLICT(coach_id, student_id) DO UPDATE SET
              rating      = excluded.rating,
              review_text = excluded.review_text,
              updated_at  = datetime('now')
        """, (coach_id, student_id, rating, review_text))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM coach_reviews WHERE coach_id=? AND student_id=?",
            (coach_id, student_id),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def delete_review(coach_id: int, student_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM coach_reviews WHERE coach_id=? AND student_id=?",
            (coach_id, student_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_reviews(coach_id: int, limit: int = 20) -> dict:
    """Retorna reviews do coach com stats de rating."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT r.*, u.username
            FROM coach_reviews r
            JOIN users u ON u.id = r.student_id
            WHERE r.coach_id = ?
            ORDER BY r.updated_at DESC
            LIMIT ?
        """, (coach_id, limit)).fetchall()
        items = [dict(r) for r in rows]
        stats = conn.execute("""
            SELECT ROUND(AVG(CAST(rating AS REAL)), 1) as avg_rating,
                   COUNT(*) as total,
                   SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END) as r5,
                   SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END) as r4,
                   SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END) as r3,
                   SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END) as r2,
                   SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) as r1
            FROM coach_reviews WHERE coach_id=?
        """, (coach_id,)).fetchone()
        return {'reviews': items, 'stats': dict(stats) if stats else {}}
    finally:
        conn.close()


def get_my_review(coach_id: int, student_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM coach_reviews WHERE coach_id=? AND student_id=?",
            (coach_id, student_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_public_coaches(specialty: str | None = None,
                        language: str | None = None,
                        trial_only: bool = False,
                        max_price: float | None = None,
                        search: str | None = None,
                        sort: str = 'rating',
                        limit: int = 20) -> List[dict]:
    """Lista coaches públicos com filtros e ordenação."""
    sort_clause = {
        'rating':   'avg_rating DESC NULLS LAST, student_count DESC',
        'students': 'student_count DESC, avg_rating DESC NULLS LAST',
        'price':    'cp.price_per_session ASC NULLS LAST',
    }.get(sort, 'avg_rating DESC NULLS LAST, student_count DESC')

    conn = get_conn()
    try:
        rows = conn.execute(f"""
            SELECT cp.*, u.username, u.invite_key,
                   (SELECT COUNT(*) FROM users WHERE coach_id = u.id) as student_count,
                   (SELECT ROUND(AVG(CAST(rating AS REAL)),1)
                    FROM coach_reviews WHERE coach_id = u.id) as avg_rating,
                   (SELECT COUNT(*) FROM coach_reviews WHERE coach_id = u.id) as review_count,
                   (SELECT AVG(t.avg_score)
                    FROM tournaments t
                    JOIN users s ON s.id = t.user_id
                    WHERE s.coach_id = u.id
                      AND t.imported_at >= datetime('now', '-30 days')
                   ) as students_avg_score
            FROM coach_profiles cp
            JOIN users u ON u.id = cp.user_id
            WHERE cp.is_public = 1
            ORDER BY {sort_clause}
            LIMIT ?
        """, (limit * 3,)).fetchall()   # fetch extra para post-filter em Python
        result = []
        for r in rows:
            d = _parse_profile(dict(r))
            if specialty and specialty.lower() not in [s.lower() for s in d['specialties']]:
                continue
            if language and language.lower() not in [l.lower() for l in d.get('languages', [])]:
                continue
            if trial_only and not d.get('trial_available'):
                continue
            if max_price is not None:
                price = d.get('price_per_session')
                if price is not None and price > max_price:
                    continue
            if search:
                needle = search.lower()
                if needle not in (d.get('display_name') or '').lower() \
                   and needle not in (d.get('username') or '').lower():
                    continue
            result.append(d)
            if len(result) >= limit:
                break
        return result
    finally:
        conn.close()


def get_public_coach_reviews(coach_id: int, limit: int = 10) -> list:
    """Reviews públicas de um coach (sem dados sensíveis do aluno)."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT r.rating, r.review_text, r.updated_at, u.username
            FROM coach_reviews r
            JOIN users u ON u.id = r.student_id
            WHERE r.coach_id = ?
            ORDER BY r.updated_at DESC
            LIMIT ?
        """, (coach_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Coach impact metrics ───────────────────────────────────────────────────────

def get_coach_impact_metrics(coach_id: int, days: int = 30) -> dict:
    """
    Métricas de impacto do coach sobre seus alunos:
    - Evolução do score médio dos alunos
    - Comparação antes/depois do vínculo
    - Leaks mais melhorados
    - Aluno com maior evolução
    """
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    since2 = (datetime.utcnow() - timedelta(days=days*2)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        students = conn.execute(
            "SELECT id, username FROM users WHERE coach_id=?",
            (coach_id,)
        ).fetchall()
        if not students:
            return {'students': [], 'summary': {}}

        student_ids = [s['id'] for s in students]
        placeholders = ','.join('?' * len(student_ids))

        # Evolução por aluno: média do score nos últimos N dias
        evolution = conn.execute(f"""
            SELECT
                u.id as student_id,
                u.username,
                COUNT(t.id)         as tournament_count,
                AVG(t.avg_score)    as avg_score,
                MIN(t.avg_score)    as best_score,
                AVG(t.standard_pct) as standard_pct,
                MAX(t.imported_at)  as last_activity
            FROM users u
            LEFT JOIN tournaments t ON t.user_id = u.id
              AND t.imported_at >= datetime('now', '-30 days')
            WHERE u.id IN ({placeholders})
            GROUP BY u.id
        """, student_ids)

        # Comparar com período anterior (dobro do período)
        prev_period = conn.execute(f"""
            SELECT
                u.id as student_id,
                AVG(t.avg_score) as prev_avg_score
            FROM users u
            LEFT JOIN tournaments t ON t.user_id = u.id
              AND t.imported_at < ?
              AND t.imported_at >= ?
            WHERE u.id IN ({placeholders})
            GROUP BY u.id
        """, [since, since2] + student_ids).fetchall()
        prev_map = {r['student_id']: r['prev_avg_score'] for r in prev_period}

        # Top leaks dos alunos (para o coach saber o que focar)
        top_leaks = conn.execute(f"""
            SELECT
                d.street || '/' || d.best_action AS spot,
                COUNT(*)                          AS n,
                AVG(d.score)                      AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id IN ({placeholders})
              AND t.imported_at >= ?
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
            HAVING COUNT(*) >= 1
            ORDER BY avg_score DESC
            LIMIT 5
        """, student_ids + [since]).fetchall()

        # Montar resultado por aluno
        students_data = []
        total_improvement = 0
        improved_count = 0
        for row in evolution:
            d = dict(row)
            prev = prev_map.get(d['student_id'])
            improvement = None
            if prev and d['avg_score']:
                improvement = round((prev - d['avg_score']) / prev * 100, 1)
                total_improvement += improvement
                improved_count += 1
            d['prev_avg_score'] = prev
            d['improvement_pct'] = improvement
            students_data.append(d)

        # Ordenar: maior melhora primeiro
        students_data.sort(key=lambda x: x['improvement_pct'] or 0, reverse=True)

        return {
            'students': students_data,
            'top_leaks': [dict(r) for r in top_leaks],
            'summary': {
                'total_students': len(students),
                'active_students': sum(1 for s in students_data if s['tournament_count'] and s['tournament_count'] > 0),
                'avg_improvement_pct': round(total_improvement / improved_count, 1) if improved_count else None,
                'best_student': students_data[0]['username'] if students_data else None,
            }
        }
    finally:
        conn.close()


def recommend_coaches_for_leaks(user_id: int, limit: int = 3) -> List[dict]:
    """
    Recomenda coaches da base baseado nos leaks do aluno.
    Cruza os leaks do aluno com as especialidades dos coaches.
    """
    conn = get_conn()
    try:
        # Pegar top leaks do aluno
        leaks = conn.execute("""
            SELECT d.street || '/' || d.best_action AS spot, AVG(d.score) as avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND d.label IN ('small_mistake','clear_mistake')
              AND t.imported_at >= datetime('now', '-90 days')
            GROUP BY spot
            ORDER BY avg_score DESC
            LIMIT 3
        """, (user_id,)).fetchall()

        if not leaks:
            return get_public_coaches(limit=limit)

        # Extrair streets/ações dos leaks para matching
        leak_streets = list(set(l['spot'].split('/')[0] for l in leaks))

        # Buscar coaches com especialidades relevantes
        coaches = get_public_coaches(limit=20)
        scored = []
        for coach in coaches:
            if coach['user_id'] == user_id:
                continue
            specs = [s.lower() for s in coach['specialties']]
            # Score de relevância: quantos leaks do aluno o coach cobre
            match_score = sum(
                1 for street in leak_streets
                if any(street in spec or spec in street for spec in specs)
            )
            coach['relevance_score'] = match_score
            coach['matching_leaks'] = [
                l['spot'] for l in leaks
                if any(l['spot'].split('/')[0] in spec or spec in l['spot'] for spec in specs)
            ]
            scored.append(coach)

        # Ordenar por relevância, depois por popularidade
        scored.sort(key=lambda x: (x['relevance_score'], x['student_count']), reverse=True)
        return scored[:limit]
    finally:
        conn.close()


# ── Coach Study Overrides ─────────────────────────────────────────────────────

def get_study_overrides(coach_id: int, student_id: int) -> List[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM coach_study_overrides WHERE coach_id=? AND student_id=? ORDER BY created_at",
            (coach_id, student_id)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_study_override(coach_id: int, student_id: int, card_spot: str,
                        status: str, note: str | None = None,
                        custom_card: str | None = None) -> dict:
    conn = get_conn()
    try:
        if USE_POSTGRES:
            conn.execute("""
                INSERT INTO coach_study_overrides
                    (coach_id, student_id, card_spot, status, note, custom_card)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(coach_id, student_id, card_spot) DO UPDATE SET
                    status      = excluded.status,
                    note        = excluded.note,
                    custom_card = excluded.custom_card,
                    created_at  = NOW()
            """, (coach_id, student_id, card_spot, status, note, custom_card))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO coach_study_overrides
                    (coach_id, student_id, card_spot, status, note, custom_card)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (coach_id, student_id, card_spot, status, note, custom_card))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM coach_study_overrides WHERE coach_id=? AND student_id=? AND card_spot=?",
            (coach_id, student_id, card_spot)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def delete_study_override(coach_id: int, student_id: int, card_spot: str) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM coach_study_overrides WHERE coach_id=? AND student_id=? AND card_spot=?",
            (coach_id, student_id, card_spot)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ── User profile management ───────────────────────────────────────────────────

def update_user_email(user_id: int, new_email: str, current_password: str) -> str | None:
    """Atualiza email após verificar senha. Retorna 'ok', 'wrong_password' ou 'email_taken'."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not _check_password(current_password, dict(row)['password_hash']):
            return 'wrong_password'
        try:
            conn.execute("UPDATE users SET email=? WHERE id=?", (new_email, user_id))
            conn.commit()
            return 'ok'
        except Exception:
            return 'email_taken'
    finally:
        conn.close()


def change_user_password(user_id: int, current_password: str, new_password: str) -> bool:
    """Troca senha após verificar a atual. Retorna True se ok."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not _check_password(current_password, dict(row)['password_hash']):
            return False
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                     (_hash_password(new_password), user_id))
        conn.commit()
        return True
    finally:
        conn.close()


def check_password(user_id: int, password: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return False
        return _check_password(password, dict(row)['password_hash'])
    finally:
        conn.close()


def unlink_student_coach(student_id: int) -> bool:
    """Remove o vínculo coach_id do aluno."""
    conn = get_conn()
    try:
        conn.execute("UPDATE users SET coach_id=NULL WHERE id=?", (student_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ── Coach hand annotations ────────────────────────────────────────────────────

def get_annotations(coach_id: int, student_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT a.*, d.hand_id, d.street, d.action_taken, d.best_action,
                      d.label, d.score, d.hero_cards, d.board, d.position,
                      t.tournament_id
               FROM coach_hand_annotations a
               JOIN decisions d ON d.id = a.decision_id
               JOIN tournaments t ON t.id = d.tournament_id
               WHERE a.coach_id=? AND a.student_id=?
               ORDER BY a.created_at DESC""",
            (coach_id, student_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_annotations_for_decisions(decision_ids: list) -> list:
    """Retorna anotações para um conjunto de decision_ids (usado pelo replayer)."""
    if not decision_ids:
        return []
    conn = get_conn()
    try:
        placeholders_str = ','.join(['?' for _ in decision_ids])
        rows = conn.execute(
            f"SELECT * FROM coach_hand_annotations WHERE decision_id IN ({placeholders_str})",
            tuple(decision_ids),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_annotation(coach_id: int, student_id: int, decision_id: int,
                      comment: str, mode: str = 'complement',
                      coach_action: Optional[str] = None,
                      coach_override_label: Optional[str] = None) -> dict:
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO coach_hand_annotations
                   (coach_id, student_id, decision_id, comment, mode,
                    coach_action, coach_override_label)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(coach_id, student_id, decision_id)
               DO UPDATE SET comment=excluded.comment, mode=excluded.mode,
                             coach_action=excluded.coach_action,
                             coach_override_label=excluded.coach_override_label""",
            (coach_id, student_id, decision_id, comment, mode,
             coach_action, coach_override_label),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM coach_hand_annotations WHERE coach_id=? AND student_id=? AND decision_id=?",
            (coach_id, student_id, decision_id),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def delete_annotation(coach_id: int, student_id: int, decision_id: int) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM coach_hand_annotations WHERE coach_id=? AND student_id=? AND decision_id=?",
            (coach_id, student_id, decision_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def decision_belongs_to_student(decision_id: int, student_id: int) -> bool:
    """Verifica se decision_id pertence a um torneio do student_id (IDOR guard)."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT d.id FROM decisions d "
            "JOIN tournaments t ON t.id = d.tournament_id "
            "WHERE d.id = ? AND t.user_id = ?",
            (decision_id, student_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_reviewed_tournament_ids(student_id: int) -> set:
    """IDs de banco dos torneios do aluno que têm pelo menos uma anotação de coach."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT DISTINCT d.tournament_id
               FROM coach_hand_annotations a
               JOIN decisions d ON d.id = a.decision_id
               WHERE a.student_id=?""",
            (student_id,),
        ).fetchall()
        return {r[0] if not isinstance(r, dict) else r['tournament_id'] for r in rows}
    finally:
        conn.close()


def get_all_students_worst_decisions(
    coach_id: int,
    n: int = 20,
    student_id_filter: Optional[int] = None,
    street_filter: Optional[str] = None,
    label_filter: Optional[str] = None,
) -> List[dict]:
    """Piores decisões de todos os alunos do coach — visão multi-aluno."""
    students = get_students(coach_id)
    if not students:
        return []
    student_map = {s['id']: s['username'] for s in students}
    filtered_ids = [s['id'] for s in students]
    if student_id_filter and student_id_filter in student_map:
        filtered_ids = [student_id_filter]

    conn = get_conn()
    try:
        placeholders = ','.join(['?' for _ in filtered_ids])
        where = [f"t.user_id IN ({placeholders})", "d.label IN ('clear_mistake','small_mistake')"]
        params: list = list(filtered_ids)
        if street_filter:
            where.append("d.street = ?")
            params.append(street_filter)
        if label_filter:
            where.append("d.label = ?")
            params.append(label_filter)
        rows = conn.execute(
            f"""SELECT d.id, d.hand_id, d.street, d.hero_cards, d.board,
                       d.action_taken, d.best_action, d.label, d.score,
                       d.position, d.icm_pressure, d.m_ratio, d.stack_bb,
                       t.tournament_id, t.site, t.user_id AS student_id
                FROM decisions d
                JOIN tournaments t ON t.id = d.tournament_id
                WHERE {' AND '.join(where)}
                ORDER BY d.score DESC
                LIMIT ?""",
            params + [n],
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d['username'] = student_map.get(d['student_id'], f'Aluno #{d["student_id"]}')
            result.append(d)
        return result
    finally:
        conn.close()


def get_common_leaks(coach_id: int, days: int = 30) -> List[dict]:
    """Leaks em comum entre alunos — retorna spots com lista de alunos afetados."""
    students = get_students(coach_id)
    if not students:
        return []
    student_ids = [s['id'] for s in students]
    student_map = {s['id']: s['username'] for s in students}
    placeholders = ','.join(['?' for _ in student_ids])
    conn = get_conn()
    try:
        rows = conn.execute(
            f"""SELECT d.street || '/' || d.best_action AS spot,
                       t.user_id AS student_id,
                       COUNT(*) AS n,
                       AVG(d.score) AS avg_score
                FROM decisions d
                JOIN tournaments t ON t.id = d.tournament_id
                WHERE t.user_id IN ({placeholders})
                  AND t.imported_at >= {interval_sql(days)}
                  AND d.label IN ('small_mistake','clear_mistake')
                GROUP BY spot, t.user_id
                ORDER BY avg_score DESC""",
            student_ids,
        ).fetchall()
        spot_map: Dict[str, dict] = {}
        for row in rows:
            spot = row['spot'] if isinstance(row, dict) else row[0]
            sid  = row['student_id'] if isinstance(row, dict) else row[1]
            cnt  = row['n'] if isinstance(row, dict) else row[2]
            sc   = row['avg_score'] if isinstance(row, dict) else row[3]
            if spot not in spot_map:
                spot_map[spot] = {'spot': spot, 'students': [], 'total_n': 0, 'scores': []}
            spot_map[spot]['students'].append({
                'id': sid,
                'username': student_map.get(sid, f'Aluno #{sid}'),
                'n': int(cnt),
                'avg_score': round(float(sc), 1),
            })
            spot_map[spot]['total_n'] += int(cnt)
            spot_map[spot]['scores'].append(float(sc))
        result = []
        for data in spot_map.values():
            data['avg_score'] = round(sum(data['scores']) / len(data['scores']), 1)
            data['num_students'] = len(data['students'])
            del data['scores']
            result.append(data)
        result.sort(key=lambda x: (-x['num_students'], x['avg_score']))
        return result[:15]
    finally:
        conn.close()


# ── Coach Baselines (BACK-002) ────────────────────────────────────────────────

def get_coach_baseline(coach_id: int, student_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM coach_baselines WHERE coach_id=? AND student_id=?",
            (coach_id, student_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_coach_baseline(coach_id: int, student_id: int,
                       baseline_date: str, note: Optional[str] = None) -> dict:
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO coach_baselines (coach_id, student_id, baseline_date, note)
               VALUES (?,?,?,?)
               ON CONFLICT(coach_id, student_id)
               DO UPDATE SET baseline_date=excluded.baseline_date,
                             note=excluded.note,
                             updated_at=CURRENT_TIMESTAMP""",
            (coach_id, student_id, baseline_date, note),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM coach_baselines WHERE coach_id=? AND student_id=?",
            (coach_id, student_id),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def delete_coach_baseline(coach_id: int, student_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM coach_baselines WHERE coach_id=? AND student_id=?",
            (coach_id, student_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_student_activity_feed(student_id: int, limit: int = 30) -> List[dict]:
    """Feed de atividade do aluno: torneios + marcos de performance."""
    conn = get_conn()
    try:
        tours = conn.execute(
            """SELECT tournament_id, site, avg_score, standard_pct,
                      hands_count, played_at, imported_at, buy_in, profit
               FROM tournaments
               WHERE user_id=? AND avg_score IS NOT NULL
               ORDER BY COALESCE(played_at, imported_at) DESC
               LIMIT ?""",
            (student_id, limit),
        ).fetchall()
        events = []
        prev_score = None
        for t in tours:
            d = dict(t)
            ts = d.get('played_at') or d.get('imported_at') or ''
            ev = {
                'type': 'tournament',
                'ts': ts,
                'tournament_id': d['tournament_id'],
                'site': d['site'],
                'avg_score': d['avg_score'],
                'standard_pct': d['standard_pct'],
                'hands_count': d['hands_count'],
                'profit': d['profit'],
                'buy_in': d['buy_in'],
            }
            # Detect milestones
            score = d['avg_score'] or 0
            if prev_score is not None:
                delta = prev_score - score  # lower = better for score (lower mistake score)
                if delta >= 5:
                    ev['milestone'] = 'improvement'
                elif delta <= -5:
                    ev['milestone'] = 'regression'
            std = (d['standard_pct'] or 0) * 100
            if std >= 80:
                ev['milestone'] = ev.get('milestone') or 'high_standard'
            prev_score = score
            events.append(ev)
        return events
    finally:
        conn.close()


def get_baseline_comparison(coach_id: int, student_id: int) -> Optional[dict]:
    """Compara métricas antes/depois da baseline de coaching."""
    baseline = get_coach_baseline(coach_id, student_id)
    if not baseline:
        return None
    bdate = baseline['baseline_date']
    conn = get_conn()
    try:
        def _query(op: str):
            return conn.execute(
                f"""SELECT COUNT(*) as n,
                           AVG(avg_score) as avg_score,
                           AVG(standard_pct) as standard_pct,
                           SUM(profit) as total_profit
                    FROM tournaments
                    WHERE user_id=? AND avg_score IS NOT NULL
                      AND COALESCE(played_at, imported_at) {op} ?""",
                (student_id, bdate),
            ).fetchone()

        before = dict(_query('<'))
        after  = dict(_query('>='))

        def _leaks(op: str):
            return conn.execute(
                f"""SELECT d.street || '/' || d.best_action AS spot, COUNT(*) AS n
                     FROM decisions d
                     JOIN tournaments t ON t.id=d.tournament_id
                     WHERE t.user_id=? AND d.label IN ('clear_mistake','small_mistake')
                       AND COALESCE(t.played_at, t.imported_at) {op} ?
                     GROUP BY spot ORDER BY n DESC LIMIT 5""",
                (student_id, bdate),
            ).fetchall()

        leaks_before = [dict(r) for r in _leaks('<')]
        leaks_after  = [dict(r) for r in _leaks('>=')]
        fixed = [l for l in leaks_before
                 if not any(a['spot'] == l['spot'] for a in leaks_after)]

        return {
            'baseline': baseline,
            'before': before,
            'after': after,
            'leaks_before': leaks_before,
            'leaks_after': leaks_after,
            'fixed_leaks': fixed,
        }
    finally:
        conn.close()


# ── BACK-010: Quota / freemium ─────────────────────────────────────────────────

PLAN_LIMITS: dict = {
    'free':    {'tournaments': 3,    'ai_calls': 10},
    'starter': {'tournaments': 20,   'ai_calls': 40},
    'pro':     {'tournaments': None, 'ai_calls': 150},
    'coach':   {'tournaments': None, 'ai_calls': 150},
}


def get_quota_status(user_id: int) -> dict:
    """Retorna plano, contadores e limites do usuário."""
    conn = get_conn()
    try:
        row = _fetchone(
            conn,
            """SELECT plan, tournaments_this_month, ai_calls_this_month, quota_reset_at
               FROM users WHERE id = ?""",
            (user_id,),
        )
    finally:
        conn.close()

    if not row:
        return {'plan': 'free', 'tournaments_used': 0, 'ai_calls_used': 0, 'limits': PLAN_LIMITS['free']}

    plan   = row.get('plan') or 'free'
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])
    return {
        'plan':             plan,
        'tournaments_used': row.get('tournaments_this_month') or 0,
        'ai_calls_used':    row.get('ai_calls_this_month')    or 0,
        'limits':           limits,
    }


def _maybe_reset_quota(conn, user_id: int) -> None:
    """Se o mês virou, zera os contadores e atualiza quota_reset_at."""
    from datetime import date
    today = date.today()
    current_month = today.strftime('%Y-%m')

    row = _fetchone(conn, "SELECT quota_reset_at FROM users WHERE id = ?", (user_id,))
    if not row:
        return

    stored = (row.get('quota_reset_at') or '')[:7]  # 'YYYY-MM'
    if stored != current_month:
        conn.execute(
            """UPDATE users
               SET tournaments_this_month = 0,
                   ai_calls_this_month    = 0,
                   quota_reset_at         = ?
               WHERE id = ?""",
            (today.isoformat(), user_id),
        )


def increment_tournament_count(user_id: int) -> None:
    conn = get_conn()
    try:
        _maybe_reset_quota(conn, user_id)
        conn.execute(
            "UPDATE users SET tournaments_this_month = tournaments_this_month + 1 WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def increment_ai_calls(user_id: int) -> None:
    conn = get_conn()
    try:
        _maybe_reset_quota(conn, user_id)
        conn.execute(
            "UPDATE users SET ai_calls_this_month = ai_calls_this_month + 1 WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ── BACK-015: Payments ────────────────────────────────────────────────────────

def save_payment(
    user_id: int,
    plan: str,
    amount_cents: int,
    status: str,
    gateway_id: str | None = None,
    gateway_sub_id: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    currency: str = 'BRL',
    gateway: str = 'mercadopago',
) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO payments (user_id, plan, amount_cents, currency, status, "
            "gateway, gateway_id, gateway_sub_id, period_start, period_end) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user_id, plan, amount_cents, currency, status,
             gateway, gateway_id, gateway_sub_id, period_start, period_end),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_payments(user_id: int, limit: int = 20) -> List[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_user_plan(user_id: int, plan: str, subscription_id: str | None = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            _adapt("UPDATE users SET plan = ?, mp_subscription_id = ? WHERE id = ?"),
            (plan, subscription_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_subscription(sub_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE mp_subscription_id = ?", (sub_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_phase_analysis(tournament_db_id: int) -> list:
    """Agrupa decisões do torneio por fase derivada do m_ratio."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT m_ratio, label, score FROM decisions WHERE tournament_id = ? AND m_ratio IS NOT NULL",
            (tournament_db_id,)
        ).fetchall()
    finally:
        conn.close()

    phases = [
        {'label': 'Deep Stack',  'range': 'M ≥ 20',  'decs': []},
        {'label': 'Mid Stack',   'range': 'M 10–20', 'decs': []},
        {'label': 'Short Stack', 'range': 'M 6–10',  'decs': []},
        {'label': 'Push/Fold',   'range': 'M < 6',   'decs': []},
    ]

    for row in rows:
        m = float(row['m_ratio'] or 0)
        d = {'label': row['label'], 'score': float(row['score'] or 0)}
        if m >= 20:
            phases[0]['decs'].append(d)
        elif m >= 10:
            phases[1]['decs'].append(d)
        elif m >= 6:
            phases[2]['decs'].append(d)
        else:
            phases[3]['decs'].append(d)

    result = []
    for ph in phases:
        decs = ph['decs']
        n = len(decs)
        if n == 0:
            continue
        mistakes = [d for d in decs if d['label'] in ('small_mistake', 'clear_mistake')]
        result.append({
            'phase':        ph['label'],
            'range':        ph['range'],
            'n':            n,
            'mistake_rate': round(len(mistakes) / n * 100, 1),
            'avg_score':    round(sum(d['score'] for d in decs) / n, 3),
        })
    return result


def get_texture_analysis(tournament_db_id: int) -> list:
    """Agrupa decisões pós-flop do torneio por textura do board."""
    from leaklab.board_texture import classify_board_texture
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT board, label, score FROM decisions "
            "WHERE tournament_id = ? AND street != 'preflop' AND board IS NOT NULL AND board != '[]'",
            (tournament_db_id,)
        ).fetchall()
    finally:
        conn.close()

    buckets: Dict[str, list] = {}
    for row in rows:
        tex = classify_board_texture(row['board'])
        if tex == 'unknown':
            continue
        if tex not in buckets:
            buckets[tex] = []
        buckets[tex].append({'label': row['label'], 'score': float(row['score'] or 0)})

    LABELS = {
        'dry':         'Seco',
        'coordinated': 'Coordenado',
        'wet':         'Molhado',
        'monotone':    'Monocromático',
        'paired':      'Pareado',
    }

    result = []
    for tex, decs in sorted(buckets.items(), key=lambda x: -len(x[1])):
        n = len(decs)
        mistakes = [d for d in decs if d['label'] in ('small_mistake', 'clear_mistake')]
        result.append({
            'texture':      tex,
            'label':        LABELS.get(tex, tex),
            'n':            n,
            'mistake_rate': round(len(mistakes) / n * 100, 1),
            'avg_score':    round(sum(d['score'] for d in decs) / n, 3),
        })
    return result


# ── Admin & Coach Finance — BACK-014 + BACK-017 ───────────────────────────────

def calculate_coach_payout(active_students: int) -> int:
    """Revenue share em centavos (BRL). 1-3: mensalidade zerada; 4-9: R$15/aluno; 10+: R$20/aluno."""
    if active_students >= 10: return active_students * 2000
    if active_students >= 4:  return active_students * 1500
    return 0


def get_admin_dashboard_stats() -> dict:
    """Stats executivos para o painel admin."""
    conn = get_conn()
    try:
        total_users   = _fetchone(conn, "SELECT COUNT(*) AS n FROM users WHERE role = 'player'")['n']
        total_coaches = _fetchone(conn, "SELECT COUNT(*) AS n FROM users WHERE role = 'coach'")['n']
        active_30d    = _fetchone(conn, f"""
            SELECT COUNT(DISTINCT user_id) AS n FROM tournaments
            WHERE imported_at >= {interval_sql(30)}
        """)['n']
        plan_rows = _fetchall(conn, """
            SELECT plan, COUNT(*) AS n FROM users
            WHERE role IN ('player','coach') GROUP BY plan
        """)
        plans = {r['plan']: r['n'] for r in plan_rows}
        pending_payouts = _fetchone(conn, """
            SELECT COALESCE(SUM(amount_cents), 0) AS total FROM coach_payments
            WHERE status = 'pending'
        """)['total']
        # MRR estimado: pro users pagam ~R$49/mês (4900 centavos)
        pro_users = plans.get('pro', 0)
        mrr_cents = pro_users * 4900
        return {
            'total_users':          total_users,
            'total_coaches':        total_coaches,
            'active_users_30d':     active_30d,
            'plans':                plans,
            'mrr_cents':            mrr_cents,
            'pending_payouts_cents': int(pending_payouts),
        }
    finally:
        conn.close()


def get_all_users(limit: int = 50, offset: int = 0, plan: str = None,
                  role: str = None, search: str = None) -> list:
    """Lista paginada de usuários para o admin."""
    conn = get_conn()
    try:
        filters, params = [], []
        if plan:
            filters.append("u.plan = ?"); params.append(plan)
        if role:
            filters.append("u.role = ?"); params.append(role)
        if search:
            filters.append("(u.username ILIKE ? OR u.email ILIKE ?)") if USE_POSTGRES else \
            filters.append("(LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ?)")
            term = f'%{search.lower()}%'
            params.extend([term, term])
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.extend([limit, offset])
        return _fetchall(conn, f"""
            SELECT u.id, u.username, u.email, u.role, u.plan,
                   u.created_at, u.last_login, u.suspended,
                   c.username AS coach_username,
                   (SELECT MAX(imported_at) FROM tournaments WHERE user_id = u.id) AS last_import,
                   (SELECT COUNT(*) FROM tournaments WHERE user_id = u.id) AS tournament_count
            FROM users u
            LEFT JOIN users c ON c.id = u.coach_id
            {where}
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
    finally:
        conn.close()


def get_all_users_count(plan: str = None, role: str = None, search: str = None) -> int:
    conn = get_conn()
    try:
        filters, params = [], []
        if plan:
            filters.append("plan = ?"); params.append(plan)
        if role:
            filters.append("role = ?"); params.append(role)
        if search:
            filters.append("(LOWER(username) LIKE ? OR LOWER(email) LIKE ?)")
            term = f'%{search.lower()}%'
            params.extend([term, term])
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        return _fetchone(conn, f"SELECT COUNT(*) AS n FROM users {where}", params)['n']
    finally:
        conn.close()


def update_user_admin(user_id: int, plan: str = None, suspended: bool = None) -> None:
    conn = get_conn()
    try:
        if plan is not None:
            conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
        if suspended is not None:
            val = 1 if suspended else 0
            conn.execute("UPDATE users SET suspended = ? WHERE id = ?", (val, user_id))
        conn.commit()
    finally:
        conn.close()


def get_coaches_with_payout_status(period: str) -> list:
    """Coaches com contagem de alunos ativos e status de repasse para o período."""
    conn = get_conn()
    try:
        coaches = _fetchall(conn, """
            SELECT u.id, u.username, cp.display_name, u.plan,
                   (SELECT COUNT(*) FROM users WHERE coach_id = u.id) AS total_students
            FROM users u
            LEFT JOIN coach_profiles cp ON cp.user_id = u.id
            WHERE u.role = 'coach'
            ORDER BY u.username
        """)
        for coach in coaches:
            # alunos ativos: importaram torneio nos últimos 30 dias + plano pro
            active = _fetchone(conn, f"""
                SELECT COUNT(DISTINCT s.id) AS n
                FROM users s
                INNER JOIN tournaments t ON t.user_id = s.id
                WHERE s.coach_id = ? AND s.plan = 'pro'
                  AND t.imported_at >= {interval_sql(30)}
            """, (coach['id'],))['n']
            coach['active_students'] = active
            coach['amount_cents']    = calculate_coach_payout(active)
            # busca pagamento existente para o período
            pay = _fetchone(conn, """
                SELECT id, status, paid_at FROM coach_payments
                WHERE coach_id = ? AND period = ?
            """, (coach['id'], period))
            coach['payment_id'] = pay['id']    if pay else None
            coach['status']     = pay['status'] if pay else 'pending'
            coach['paid_at']    = pay['paid_at'] if pay else None
        return coaches
    finally:
        conn.close()


def upsert_coach_payment(coach_id: int, period: str, active_students: int, amount_cents: int) -> int:
    """Cria ou atualiza o registro de repasse para o coach no período."""
    conn = get_conn()
    try:
        existing = _fetchone(conn, """
            SELECT id FROM coach_payments WHERE coach_id = ? AND period = ?
        """, (coach_id, period))
        if existing:
            conn.execute("""
                UPDATE coach_payments SET active_students = ?, amount_cents = ?
                WHERE id = ?
            """, (active_students, amount_cents, existing['id']))
            conn.commit()
            return existing['id']
        else:
            pid = _insert(conn, """
                INSERT INTO coach_payments (coach_id, period, active_students, amount_cents, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (coach_id, period, active_students, amount_cents))
            conn.commit()
            return pid
    finally:
        conn.close()


def mark_coach_payment_paid(payment_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(f"""
            UPDATE coach_payments SET status = 'paid', paid_at = {now_sql()}
            WHERE id = ?
        """, (payment_id,))
        conn.commit()
    finally:
        conn.close()


def get_coach_finance_summary(coach_id: int) -> dict:
    """Resumo financeiro do coach para o período atual."""
    import datetime
    period = datetime.date.today().strftime('%Y-%m')
    conn = get_conn()
    try:
        total_students = _fetchone(conn,
            "SELECT COUNT(*) AS n FROM users WHERE coach_id = ?", (coach_id,))['n']
        active_students = _fetchone(conn, f"""
            SELECT COUNT(DISTINCT s.id) AS n
            FROM users s
            INNER JOIN tournaments t ON t.user_id = s.id
            WHERE s.coach_id = ? AND s.plan = 'pro'
              AND t.imported_at >= {interval_sql(30)}
        """, (coach_id,))['n']
        amount_cents = calculate_coach_payout(active_students)
        pay = _fetchone(conn, """
            SELECT id, status, paid_at FROM coach_payments
            WHERE coach_id = ? AND period = ?
        """, (coach_id, period))
        monthly_fee_waived = total_students >= 1
        return {
            'period':             period,
            'total_students':     total_students,
            'active_students':    active_students,
            'amount_cents':       amount_cents,
            'status':             pay['status'] if pay else 'pending',
            'paid_at':            pay['paid_at'] if pay else None,
            'monthly_fee_waived': monthly_fee_waived,
        }
    finally:
        conn.close()


def get_coach_finance_students(coach_id: int) -> list:
    """Alunos do coach com status de atividade para fins de revenue share."""
    conn = get_conn()
    try:
        students = _fetchall(conn, f"""
            SELECT s.id, s.username, s.plan,
                   (SELECT MAX(imported_at) FROM tournaments WHERE user_id = s.id) AS last_import,
                   (SELECT COUNT(*) FROM tournaments WHERE user_id = s.id) AS tournament_count
            FROM users s
            WHERE s.coach_id = ?
            ORDER BY last_import DESC NULLS LAST
        """, (coach_id,))
        cutoff_sql = interval_sql(30)
        for s in students:
            last = s.get('last_import') or ''
            # ativo = tem importação recente e plano pro
            s['is_active'] = bool(
                s['plan'] == 'pro' and last and
                _fetchone(conn, f"""
                    SELECT 1 FROM tournaments
                    WHERE user_id = ? AND imported_at >= {cutoff_sql}
                    LIMIT 1
                """, (s['id'],))
            )
        return students
    finally:
        conn.close()


def get_coach_finance_history(coach_id: int) -> list:
    """Histórico de repasses do coach (todos os períodos)."""
    conn = get_conn()
    try:
        return _fetchall(conn, """
            SELECT id, period, active_students, amount_cents, status, paid_at, created_at
            FROM coach_payments
            WHERE coach_id = ?
            ORDER BY period DESC
        """, (coach_id,))
    finally:
        conn.close()


def get_admin_activity_logs(limit: int = 50) -> list:
    """Últimas importações de torneios (para log de atividade do admin)."""
    conn = get_conn()
    try:
        return _fetchall(conn, """
            SELECT t.id, t.tournament_id, t.site, t.hands_count, t.imported_at,
                   u.username, u.plan
            FROM tournaments t
            INNER JOIN users u ON u.id = t.user_id
            ORDER BY t.imported_at DESC
            LIMIT ?
        """, (limit,))
    finally:
        conn.close()


def get_user_by_external_ref(ext_ref: str) -> tuple[Optional[dict], str]:
    """
    Extrai user_id e plan_name do external_reference 'user_<id>_<plan>'.
    Retorna (user_dict, plan_name) ou (None, '').
    """
    try:
        parts   = ext_ref.split('_')
        user_id = int(parts[1])
        plan    = parts[2]
    except (IndexError, ValueError):
        return None, ''
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return (dict(row) if row else None), plan
    finally:
        conn.close()


# ── WhatsApp — BACK-016 ───────────────────────────────────────────────────────

def get_user_by_phone(phone: str) -> Optional[dict]:
    """Retorna usuário pelo número de WhatsApp (E.164 sem +)."""
    conn = get_conn()
    try:
        row = conn.execute(
            _adapt("SELECT * FROM users WHERE whatsapp_phone = ?"), (phone,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_phone(user_id: int, phone: str | None) -> None:
    """Vincula ou desvincula número de WhatsApp ao perfil do usuário."""
    conn = get_conn()
    try:
        conn.execute(
            _adapt("UPDATE users SET whatsapp_phone = ? WHERE id = ?"),
            (phone, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Decision DNA — PERF-007 ───────────────────────────────────────────────────

def _classify_archetype(aggression: float, fold_freq: float, three_bet: float, discipline: float) -> str:
    if fold_freq >= 55 and aggression >= 35:
        return "TAG"
    if fold_freq >= 55:
        return "Nit"
    if fold_freq <= 28 and aggression >= 40:
        return "LAG"
    if fold_freq <= 28:
        return "Calling Station"
    if discipline >= 70 and 28 < fold_freq < 55:
        return "Balanced"
    if aggression >= 48:
        return "LAG"
    return "TAG"


def get_coach_effectiveness_report(coach_id: int) -> dict:
    """Sprint T — Agrega evolução de todos os alunos com baseline. Retorna resumo + por aluno."""
    students = get_students(coach_id)
    per_student = []

    for s in students:
        cmp = get_baseline_comparison(coach_id, s['id'])
        if not cmp:
            continue
        before = cmp.get('before') or {}
        after  = cmp.get('after')  or {}
        std_before = before.get('standard_pct')
        std_after  = after.get('standard_pct')
        if std_before is None or std_after is None:
            continue
        delta = round(float(std_after) - float(std_before), 2)
        per_student.append({
            'student_id':       s['id'],
            'username':         s['username'],
            'baseline_date':    cmp['baseline']['baseline_date'],
            'std_before':       round(float(std_before), 2),
            'std_after':        round(float(std_after),  2),
            'delta':            delta,
            'score_before':     round(float(before.get('avg_score') or 0), 3),
            'score_after':      round(float(after.get('avg_score')  or 0), 3),
            'fixed_leaks':      len(cmp.get('fixed_leaks') or []),
            'tournaments_after': int(after.get('n') or 0),
        })

    per_student.sort(key=lambda x: x['delta'], reverse=True)

    if not per_student:
        return {
            'students': [],
            'summary':  {'students_analyzed': 0, 'median_delta': None,
                         'positive_pct': None, 'badge': None},
        }

    deltas = sorted(x['delta'] for x in per_student)
    n = len(deltas)
    median = deltas[n // 2] if n % 2 == 1 else round((deltas[n // 2 - 1] + deltas[n // 2]) / 2, 2)
    positive_pct = round(sum(1 for d in deltas if d > 0) / n * 100, 1)

    badge = None
    if n >= 3 and median > 0:
        badge = f"Alunos melhoram +{median:.1f}pp em standard_pct"

    return {
        'students': per_student,
        'summary': {
            'students_analyzed': n,
            'median_delta':      median,
            'positive_pct':      positive_pct,
            'badge':             badge,
        },
    }


def get_leak_graph_data(user_id: int, days: int = 90) -> dict:
    """Sprint S — Retorna grafo causal de leaks: nós, arestas e narrativa LLM."""
    from datetime import datetime, timedelta
    from leaklab.leak_causal_graph import build_leak_graph
    from leaklab.llm_explainer import explain_leak_causality

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT
                t.id                                   AS tournament_id,
                d.street || '/' || d.best_action       AS spot,
                d.score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND d.label IN ('small_mistake','clear_mistake')
              AND t.imported_at >= ?
        """), (user_id, cutoff)).fetchall()
    finally:
        conn.close()

    if not rows:
        return {'nodes': [], 'edges': [], 'narrative': ''}

    graph = build_leak_graph([dict(r) for r in rows])

    hero = ''
    try:
        u = get_user_by_id(user_id)
        hero = (u or {}).get('username', '') or ''
    except Exception:
        pass

    narrative = explain_leak_causality(graph['edges'], hero=hero or 'você')
    return {**graph, 'narrative': narrative}


def get_player_dna(user_id: int, days: int = 90) -> dict:
    """
    Computa a assinatura estratégica do jogador a partir dos padrões de decisão.
    Retorna métricas normalizadas 0-100 + arquétipo classificado.
    """
    from datetime import datetime, timedelta
    conn = get_conn()
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = _fetchall(conn, _adapt("""
            SELECT d.action_taken, d.street, d.position, d.is_3bet,
                   d.label, d.icm_pressure
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
        """), (user_id, cutoff))

        total = len(rows)
        if total < 10:
            return {"dna": None, "sample_size": total}

        _agg  = {'raise', 'bet', 'jam'}
        _fold = {'fold'}

        n_agg  = sum(1 for r in rows if (r['action_taken'] or '').lower() in _agg)
        n_fold = sum(1 for r in rows if (r['action_taken'] or '').lower() in _fold)

        fold_freq = round(n_fold / total * 100, 1)
        non_fold  = total - n_fold
        aggr_idx  = round(n_agg / non_fold * 100, 1) if non_fold else 0.0

        # 3-bet preflop
        pf     = [r for r in rows if r['street'] == 'preflop']
        n_3bet = sum(1 for r in pf if r['is_3bet'])
        three_bet_pct = round(n_3bet / len(pf) * 100, 1) if pf else 0.0

        # Positional awareness: aggression% in LP vs EP
        lp = {'BTN', 'CO'}
        ep = {'UTG', 'UTG+1', 'UTG+2', 'MP1', 'MP2', 'MP3', 'HJ'}
        lp_nf = [r for r in rows if (r['position'] or '') in lp and (r['action_taken'] or '').lower() not in _fold]
        ep_nf = [r for r in rows if (r['position'] or '') in ep and (r['action_taken'] or '').lower() not in _fold]
        lp_aggr = sum(1 for r in lp_nf if (r['action_taken'] or '').lower() in _agg)
        ep_aggr = sum(1 for r in ep_nf if (r['action_taken'] or '').lower() in _agg)
        lp_pct = (lp_aggr / len(lp_nf) * 100) if lp_nf else aggr_idx
        ep_pct = (ep_aggr / len(ep_nf) * 100) if ep_nf else aggr_idx
        pos_awareness = round(min(100.0, max(0.0, 50.0 + (lp_pct - ep_pct) * 2)), 1)

        # Disciplina técnica — standard%
        n_std     = sum(1 for r in rows if r['label'] == 'standard')
        discipline = round(n_std / total * 100, 1)

        # ICM awareness — standard% sob alta pressão vs sem pressão
        high_icm = [r for r in rows if r['icm_pressure'] == 'high']
        no_icm   = [r for r in rows if r['icm_pressure'] == 'none']
        hi_std   = sum(1 for r in high_icm if r['label'] == 'standard')
        no_std   = sum(1 for r in no_icm   if r['label'] == 'standard')
        if high_icm and no_icm and no_std:
            ratio = (hi_std / len(high_icm)) / (no_std / len(no_icm))
            icm_awareness: float | None = round(min(100.0, ratio * 100), 1)
        else:
            icm_awareness = None

        archetype = _classify_archetype(aggr_idx, fold_freq, three_bet_pct, discipline)

        return {
            "dna": {
                "aggression_index":    aggr_idx,
                "fold_frequency":      fold_freq,
                "three_bet_pct":       three_bet_pct,
                "positional_awareness": pos_awareness,
                "discipline":          discipline,
                "icm_awareness":       icm_awareness,
                "archetype":           archetype,
            },
            "sample_size": total,
        }
    finally:
        conn.close()


# ── Sprint Q — FEAT-02: Daily Focus ──────────────────────────────────────────

def get_daily_focus(user_id: int) -> dict:
    """Retorna 1 ação primária + até 2 secundárias para o foco do dia. Zero LLM."""
    from datetime import datetime
    today = datetime.now().date().isoformat()
    conn = get_conn()
    try:
        user = conn.execute(
            "SELECT daily_focus_done_at, xp_streak FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        completed = bool(user and user['daily_focus_done_at'] == today)
        streak    = int(user['xp_streak'] or 0) if user else 0
    finally:
        conn.close()

    actions: list = []

    # 1. Top EV-loss leak → primary drill action
    leaks = get_leak_roi_impact(user_id, days=90)
    if leaks:
        top   = leaks[0]
        spot  = top.get('spot', '')
        label = spot.replace('/', ' / ').replace('_', ' ')
        n     = top.get('n', 0)
        actions.append({
            'type':        'leak',
            'priority':    'primary',
            'label':       f'Drill: {label}',
            'description': f'{n} erros recentes — score médio {top.get("avg_score", 0):.3f}',
            'link':        '/ghost',
        })

    # 2. Most overdue drill spot → secondary
    spots = get_drill_spots(user_id, limit=3)
    if spots:
        s    = spots[0]
        slbl = f"{(s.get('street') or '?').capitalize()} / {s.get('best_action') or '?'}"
        actions.append({
            'type':        'drill',
            'priority':    'secondary',
            'label':       f'Ghost Table: {slbl}',
            'description': f'Score: {s.get("score", 0):.3f} — spot a revisitar',
            'link':        '/ghost',
        })

    # 3. Most recent unreviewed tournament → secondary
    tourns = get_tournaments(user_id, limit=5)
    unreviewed = [t for t in tourns if not t.get('llm_summary')]
    if unreviewed:
        t    = unreviewed[0]
        tid  = t.get('tournament_id', '')
        name = (t.get('tournament_name') or f'#{tid}')[:35]
        actions.append({
            'type':        'tournament',
            'priority':    'secondary',
            'label':       f'Revisar: {name}',
            'description': f'{t.get("hands_count", 0)} mãos · {t.get("site", "")}',
            'link':        f'/tournaments/{tid}',
        })

    if not actions:
        return {
            'primary':   {'type': 'none', 'label': '', 'description': '', 'link': ''},
            'secondary': [],
            'valid_until': f'{today}T23:59:59',
            'completed': completed, 'streak': streak,
        }

    primary   = next((a for a in actions if a['priority'] == 'primary'), actions[0])
    secondary = [a for a in actions if a is not primary][:2]
    return {
        'primary':     primary,
        'secondary':   secondary,
        'valid_until': f'{today}T23:59:59',
        'completed':   completed,
        'streak':      streak,
    }


def mark_daily_focus_done(user_id: int) -> None:
    from datetime import datetime
    today = datetime.now().date().isoformat()
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET daily_focus_done_at = ? WHERE id = ?", (today, user_id)
        )
        conn.commit()
    finally:
        conn.close()


# ── Sprint Q — FEAT-03: XP Server-Side ───────────────────────────────────────

_XP_AMOUNTS: dict = {
    'tournament_imported': 50,
    'exercise_correct':    10,
    'drill_completed':     25,
    'drill_mastered':     100,
}

_ACHIEVEMENT_DEFS = [
    ('first_tournament', '🎯 Primeira Análise',  'Importou e analisou o primeiro torneio'),
    ('decisions_100',    '📊 100 Decisões',       '100 decisões analisadas'),
    ('first_drill',      '🎮 Primeiro Drill',     'Completou o primeiro drill no Ghost Table'),
    ('streak_7',         '🔥 Semana de Foco',     '7 dias consecutivos de atividade'),
    ('tournaments_10',   '🏆 10 Torneios',        '10 torneios importados e analisados'),
]

_ACH_META = {k: {'title': t, 'desc': d} for k, t, d in _ACHIEVEMENT_DEFS}


def add_xp(user_id: int, event_type: str, amount: int | None = None) -> dict:
    """Adiciona XP, atualiza streak e verifica conquistas."""
    from datetime import datetime, timedelta
    xp_gain   = amount if amount is not None else _XP_AMOUNTS.get(event_type, 10)
    today     = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

    conn = get_conn()
    try:
        user = conn.execute(
            "SELECT xp_total, xp_streak, xp_last_activity FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return {}

        xp_total = (user['xp_total'] or 0) + xp_gain
        last     = user['xp_last_activity'] or ''
        streak   = user['xp_streak'] or 0

        if last == today:
            new_streak = streak
        elif last == yesterday:
            new_streak = streak + 1
        else:
            new_streak = 1

        conn.execute(
            "UPDATE users SET xp_total = ?, xp_streak = ?, xp_last_activity = ? WHERE id = ?",
            (xp_total, new_streak, today, user_id)
        )
        new_achievements = _check_and_grant_achievements(conn, user_id, event_type, xp_total, new_streak)
        conn.commit()
        return {
            'xp_total':         xp_total,
            'xp_gained':        xp_gain,
            'streak':           new_streak,
            'new_achievements': new_achievements,
        }
    finally:
        conn.close()


def get_xp_status(user_id: int) -> dict:
    conn = get_conn()
    try:
        user = conn.execute(
            "SELECT xp_total, xp_streak, xp_last_activity FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return {'xp_total': 0, 'streak': 0, 'achievements': []}
        return {
            'xp_total':      user['xp_total'] or 0,
            'streak':        user['xp_streak'] or 0,
            'last_activity': user['xp_last_activity'],
            'achievements':  get_achievements(user_id),
        }
    finally:
        conn.close()


def get_achievements(user_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT achievement_key, earned_at FROM achievements WHERE user_id = ? ORDER BY earned_at",
            (user_id,)
        ).fetchall()
        result = []
        for r in rows:
            key  = r['achievement_key']
            meta = _ACH_META.get(key, {'title': key, 'desc': ''})
            result.append({'key': key, 'title': meta['title'],
                           'desc': meta['desc'], 'earned_at': r['earned_at']})
        return result
    finally:
        conn.close()


# ── Coach Plan Templates — FEAT-09 ───────────────────────────────────────────

def get_coach_templates(coach_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, target_archetype, cards_json, created_at "
        "FROM coach_plan_templates WHERE coach_id = ? ORDER BY created_at DESC",
        (coach_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_coach_template(coach_id: int, name: str,
                          target_archetype: Optional[str], cards_json: str) -> dict:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO coach_plan_templates (coach_id, name, target_archetype, cards_json) "
        "VALUES (?, ?, ?, ?)",
        (coach_id, name, target_archetype, cards_json)
    )
    template_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": template_id, "name": name,
            "target_archetype": target_archetype, "cards_json": cards_json}


def delete_coach_template(template_id: int, coach_id: int) -> bool:
    conn = get_conn()
    conn.execute(
        "DELETE FROM coach_plan_templates WHERE id = ? AND coach_id = ?",
        (template_id, coach_id)
    )
    conn.commit()
    conn.close()
    return True


# ── Coach Messages — FEAT-10 ──────────────────────────────────────────────────

def send_coach_message(coach_id: int, student_id: int, body: str,
                       sender_role: str = 'coach',
                       decision_id: Optional[int] = None) -> dict:
    from datetime import datetime
    conn = get_conn()
    now_str = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO coach_messages (coach_id, student_id, body, sender_role, decision_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (coach_id, student_id, body, sender_role, decision_id, now_str)
    )
    msg_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": msg_id, "body": body, "sender_role": sender_role,
            "created_at": now_str, "read_at": None, "decision_id": decision_id}


def get_coach_messages(coach_id: int, student_id: int, limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, body, sender_role, decision_id, read_at, created_at "
        "FROM coach_messages WHERE coach_id = ? AND student_id = ? "
        "ORDER BY created_at ASC LIMIT ?",
        (coach_id, student_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_messages_read(coach_id: int, student_id: int, reader_role: str) -> None:
    """Marca como lidas as mensagens enviadas pelo papel oposto ao leitor."""
    from datetime import datetime
    sender = 'coach' if reader_role == 'student' else 'student'
    now_str = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE coach_messages SET read_at = ? "
        "WHERE coach_id = ? AND student_id = ? AND sender_role = ? AND read_at IS NULL",
        (now_str, coach_id, student_id, sender)
    )
    conn.commit()
    conn.close()


def get_unread_message_count(user_id: int, role: str) -> int:
    """Conta mensagens não lidas recebidas pelo usuário."""
    conn = get_conn()
    if role in ('student', 'player'):
        # player/student recebe mensagens com sender_role='coach'
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM coach_messages "
            "WHERE student_id = ? AND sender_role = 'coach' AND read_at IS NULL",
            (user_id,)
        ).fetchone()
    else:
        # coach recebe mensagens com sender_role='student'
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM coach_messages "
            "WHERE coach_id = ? AND sender_role = 'student' AND read_at IS NULL",
            (user_id,)
        ).fetchone()
    conn.close()
    return (row['n'] or 0) if row else 0


# ── Coach Inbox — UX-015 ─────────────────────────────────────────────────────

def get_coach_inbox(coach_id: int) -> list:
    """Aggregated conversations for coach inbox, sorted by most recent."""
    conn = get_conn()
    rows = conn.execute(_adapt("""
        SELECT
            m.student_id,
            u.username AS student_username,
            MAX(m.created_at) AS last_message_at,
            (SELECT body FROM coach_messages
             WHERE coach_id = m.coach_id AND student_id = m.student_id
             ORDER BY created_at DESC LIMIT 1) AS last_message_body,
            (SELECT sender_role FROM coach_messages
             WHERE coach_id = m.coach_id AND student_id = m.student_id
             ORDER BY created_at DESC LIMIT 1) AS last_sender_role,
            SUM(CASE WHEN m.sender_role = 'student' AND m.read_at IS NULL THEN 1 ELSE 0 END) AS unread_count
        FROM coach_messages m
        JOIN users u ON u.id = m.student_id
        WHERE m.coach_id = ?
        GROUP BY m.student_id, u.username
        ORDER BY last_message_at DESC
    """), (coach_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Digest semanal — FEAT-11 ──────────────────────────────────────────────────

def get_digest_subscribers() -> list:
    """Retorna usuários com digest_subscribed=1 que fizeram login nos últimos 30 dias."""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, email, username FROM users "
        "WHERE digest_subscribed = 1 "
        "AND last_login >= datetime('now', '-30 days')",
    )
    conn.close()
    return rows


def update_digest_subscription(user_id: int, subscribed: bool) -> None:
    """Ativa ou desativa o digest semanal para um usuário."""
    conn = get_conn()
    _execute(conn,
        "UPDATE users SET digest_subscribed = ? WHERE id = ?",
        (1 if subscribed else 0, user_id),
    )
    conn.commit()
    conn.close()


# ── Session Goals — FEAT-08 ───────────────────────────────────────────────────

def create_session_goal(user_id: int, goal_leak_spot: str | None,
                        target_standard_pct: float | None, notes: str | None) -> dict:
    """Creates a pre-session goal. Returns the created goal."""
    conn = get_conn()
    from datetime import datetime
    now_str = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO session_goals (user_id, goal_leak_spot, target_standard_pct, notes, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, goal_leak_spot, target_standard_pct, notes, now_str)
    )
    goal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": goal_id, "goal_leak_spot": goal_leak_spot,
            "target_standard_pct": target_standard_pct, "notes": notes}


def link_session_goal(goal_id: int, user_id: int, tournament_id: int) -> bool:
    """Links a pending goal to a newly imported tournament. Returns True if linked."""
    conn = get_conn()
    from datetime import datetime
    now_str = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE session_goals SET tournament_id = ?, linked_at = ? "
        "WHERE id = ? AND user_id = ? AND tournament_id IS NULL",
        (tournament_id, now_str, goal_id, user_id)
    )
    conn.commit()
    conn.close()
    return True


def get_pending_session_goal(user_id: int) -> Optional[dict]:
    """Returns the most recent unlinked session goal for the user."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, goal_leak_spot, target_standard_pct, notes, created_at "
        "FROM session_goals WHERE user_id = ? AND tournament_id IS NULL "
        "ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id":                  row['id'],
        "goal_leak_spot":      row['goal_leak_spot'],
        "target_standard_pct": row['target_standard_pct'],
        "notes":               row['notes'],
        "created_at":          row['created_at'],
    }


def get_session_goal_by_tournament(user_id: int, tournament_id: int) -> Optional[dict]:
    """Returns the session goal linked to a tournament, or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, goal_leak_spot, target_standard_pct, notes, llm_review, created_at, linked_at "
        "FROM session_goals WHERE user_id = ? AND tournament_id = ? LIMIT 1",
        (user_id, tournament_id)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id":                  row['id'],
        "goal_leak_spot":      row['goal_leak_spot'],
        "target_standard_pct": row['target_standard_pct'],
        "notes":               row['notes'],
        "llm_review":          row['llm_review'],
        "created_at":          row['created_at'],
        "linked_at":           row['linked_at'],
    }


def save_session_review(goal_id: int, review_text: str) -> None:
    """Persists the LLM-generated review into session_goals.llm_review."""
    conn = get_conn()
    conn.execute(
        "UPDATE session_goals SET llm_review = ? WHERE id = ?",
        (review_text, goal_id)
    )
    conn.commit()
    conn.close()


def _check_and_grant_achievements(conn, user_id: int, event_type: str,
                                   xp_total: int, streak: int) -> list:
    existing = {r['achievement_key'] for r in conn.execute(
        "SELECT achievement_key FROM achievements WHERE user_id = ?", (user_id,)
    ).fetchall()}

    candidates: list = []
    if event_type == 'tournament_imported' and 'first_tournament' not in existing:
        candidates.append('first_tournament')
    if 'decisions_100' not in existing:
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM decisions d "
            "JOIN tournaments t ON t.id = d.tournament_id WHERE t.user_id = ?",
            (user_id,)
        ).fetchone()
        if cnt and (cnt['n'] or 0) >= 100:
            candidates.append('decisions_100')
    if event_type in ('drill_completed', 'drill_mastered') and 'first_drill' not in existing:
        candidates.append('first_drill')
    if streak >= 7 and 'streak_7' not in existing:
        candidates.append('streak_7')
    if 'tournaments_10' not in existing:
        tc = conn.execute(
            "SELECT COUNT(*) AS n FROM tournaments WHERE user_id = ?", (user_id,)
        ).fetchone()
        if tc and (tc['n'] or 0) >= 10:
            candidates.append('tournaments_10')

    new_ach = []
    for key in candidates:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO achievements (user_id, achievement_key) VALUES (?, ?)",
                (user_id, key)
            )
            meta = _ACH_META.get(key, {'title': key, 'desc': ''})
            new_ach.append({'key': key, 'title': meta['title'], 'desc': meta['desc']})
        except Exception:
            pass
    return new_ach


# ── Coach Applications — BACK-018 ─────────────────────────────────────────────

def create_coach_application(user_id: int, instagram_handle: str, bio: str,
                              specialties: str, experience_years: int,
                              biggest_results: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO coach_applications "
            "(user_id, instagram_handle, bio, specialties, experience_years, biggest_results) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, instagram_handle, bio, specialties, experience_years, biggest_results)
        )
        conn.commit()
    finally:
        conn.close()


def get_coach_applications(status: str = 'pending') -> List[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ca.*, u.username, u.email FROM coach_applications ca "
            "JOIN users u ON u.id = ca.user_id "
            "WHERE ca.status = ? ORDER BY ca.created_at DESC",
            (status,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve_coach_application(app_id: int, admin_note: str = '') -> Optional[dict]:
    """Aprova candidatura: muda role para 'coach', cria coach_profile. Retorna dados do user."""
    conn = get_conn()
    try:
        app = conn.execute(
            "SELECT ca.*, u.email, u.username FROM coach_applications ca "
            "JOIN users u ON u.id = ca.user_id WHERE ca.id = ?",
            (app_id,)
        ).fetchone()
        if not app:
            return None
        app = dict(app)
        user_id = app['user_id']

        conn.execute(
            "UPDATE coach_applications SET status = 'approved', admin_note = ?, "
            "reviewed_at = ? WHERE id = ?",
            (admin_note, _now(), app_id)
        )
        conn.execute("UPDATE users SET role = 'coach' WHERE id = ?", (user_id,))
        # Create coach_profile if not exists
        conn.execute(
            "INSERT OR IGNORE INTO coach_profiles (user_id, display_name) VALUES (?, ?)",
            (user_id, app['username'])
        )
        conn.commit()
        return app
    finally:
        conn.close()


def reject_coach_application(app_id: int, admin_note: str = '') -> Optional[dict]:
    """Rejeita candidatura: mantém role 'coach_pending'. Retorna dados do user."""
    conn = get_conn()
    try:
        app = conn.execute(
            "SELECT ca.*, u.email, u.username FROM coach_applications ca "
            "JOIN users u ON u.id = ca.user_id WHERE ca.id = ?",
            (app_id,)
        ).fetchone()
        if not app:
            return None
        app = dict(app)
        conn.execute(
            "UPDATE coach_applications SET status = 'rejected', admin_note = ?, "
            "reviewed_at = ? WHERE id = ?",
            (admin_note, _now(), app_id)
        )
        conn.commit()
        return app
    finally:
        conn.close()


def _now() -> str:
    from database.schema import USE_POSTGRES, now_sql
    import datetime
    return datetime.datetime.utcnow().isoformat()


# ── Demographic Profile — BACK-019 ────────────────────────────────────────────

_DEMO_COLS = [
    'birth_year', 'country', 'state_province', 'city',
    'poker_experience_years', 'main_game_type', 'usual_buyin_range',
    'profile_completed_at',
]

def get_user_demographics(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            _adapt(f"SELECT {', '.join(_DEMO_COLS)} FROM users WHERE id = ?"),
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def update_user_demographics(user_id: int, **fields) -> dict:
    """Updates allowed demographic fields. Marks profile_completed_at when all core fields set."""
    allowed = set(_DEMO_COLS) - {'profile_completed_at'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {}
    import datetime
    conn = get_conn()
    try:
        for col, val in updates.items():
            conn.execute(_adapt(f"UPDATE users SET {col} = ? WHERE id = ?"), (val, user_id))
        # mark completed if all core fields are now filled
        core = ['birth_year', 'country', 'poker_experience_years', 'main_game_type', 'usual_buyin_range']
        row = conn.execute(
            _adapt(f"SELECT {', '.join(core + ['profile_completed_at'])} FROM users WHERE id = ?"),
            (user_id,)
        ).fetchone()
        if row and all(row[c] not in (None, '') for c in core) and not row['profile_completed_at']:
            conn.execute(
                _adapt("UPDATE users SET profile_completed_at = ? WHERE id = ?"),
                (_now(), user_id)
            )
        conn.commit()
        return dict(row) if row else {}
    finally:
        conn.close()


def get_demographics_aggregate() -> dict:
    """Anonymized aggregates for admin panel."""
    conn = get_conn()
    try:
        total = (conn.execute("SELECT COUNT(*) FROM users WHERE role = 'player'").fetchone() or [0])[0]
        completed = (conn.execute(
            "SELECT COUNT(*) FROM users WHERE profile_completed_at IS NOT NULL"
        ).fetchone() or [0])[0]
        countries = conn.execute(
            "SELECT country, COUNT(*) AS n FROM users WHERE country IS NOT NULL GROUP BY country ORDER BY n DESC LIMIT 10"
        ).fetchall()
        game_types = conn.execute(
            "SELECT main_game_type, COUNT(*) AS n FROM users WHERE main_game_type IS NOT NULL GROUP BY main_game_type"
        ).fetchall()
        buyin_ranges = conn.execute(
            "SELECT usual_buyin_range, COUNT(*) AS n FROM users WHERE usual_buyin_range IS NOT NULL GROUP BY usual_buyin_range"
        ).fetchall()
        return {
            'total_players': total,
            'profiles_completed': completed,
            'completion_rate': round(completed / total * 100, 1) if total else 0,
            'top_countries': [dict(r) for r in countries],
            'game_types': [dict(r) for r in game_types],
            'buyin_ranges': [dict(r) for r in buyin_ranges],
        }
    finally:
        conn.close()


# ── Dashboard preferences ─────────────────────────────────────────────────────

def get_user_preferences(user_id: int) -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT dashboard_layout FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        layout = None
        if row and row['dashboard_layout']:
            try:
                layout = json.loads(row['dashboard_layout'])
            except Exception:
                pass
        return {'dashboard_layout': layout}
    finally:
        conn.close()


def save_user_preferences(user_id: int, dashboard_layout: dict) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET dashboard_layout = ? WHERE id = ?",
            (json.dumps(dashboard_layout), user_id)
        )
        conn.commit()
    finally:
        conn.close()
