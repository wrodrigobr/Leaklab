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


def _build_tournament_filter(user_id: int, days: int = 90, last_n: int | None = None) -> tuple[str, tuple]:
    """
    Retorna (where_clause, params) para filtrar torneios por volume ou por data.

    - last_n=N  → últimos N torneios do usuário (independente de data)
    - last_n=None → torneios importados nos últimos `days` dias
    """
    if last_n is not None:
        return (
            "t.id IN (SELECT id FROM tournaments WHERE user_id = ? ORDER BY imported_at DESC LIMIT ?)",
            (user_id, last_n),
        )
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    return "t.user_id = ? AND t.imported_at >= ?", (user_id, since)


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
            "SELECT id, username, email, created_at, last_login, plan, invited_by_key, invited_via_invite_id, link_status "
            "FROM users WHERE coach_id = ?", (coach_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_students_attention_signals(coach_id: int) -> dict:
    """P1b — sinais de triagem por aluno (2 queries agregadas, sem N+1):
    `critical_pending` = decisões small/clear ainda SEM anotação deste coach; `unread` =
    mensagens do aluno não lidas. Retorna {student_id: {'critical_pending', 'unread'}}."""
    conn = get_conn()
    try:
        crit = conn.execute(_adapt("""
            SELECT t.user_id AS student_id, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id IN (SELECT id FROM users WHERE coach_id = ?)
              AND d.label IN ('small_mistake','clear_mistake')
              AND NOT EXISTS (
                  SELECT 1 FROM coach_hand_annotations a
                  WHERE a.decision_id = d.id AND a.coach_id = ?
              )
            GROUP BY t.user_id
        """), (coach_id, coach_id)).fetchall()
        crit_map = {r['student_id']: r['n'] for r in crit}
        unread = conn.execute(_adapt("""
            SELECT student_id,
                   SUM(CASE WHEN sender_role='student' AND read_at IS NULL THEN 1 ELSE 0 END) AS n
            FROM coach_messages WHERE coach_id = ? GROUP BY student_id
        """), (coach_id,)).fetchall()
        unread_map = {r['student_id']: (r['n'] or 0) for r in unread}
        ids = set(crit_map) | set(unread_map)
        return {sid: {'critical_pending': crit_map.get(sid, 0),
                      'unread': unread_map.get(sid, 0)} for sid in ids}
    finally:
        conn.close()


def get_coach_recent_activity(coach_id: int, limit: int = 20) -> list:
    """P2 — feed cross-aluno: torneios recentes de TODOS os alunos do coach, ordenados por
    importação. Um lugar pra ver 'o que meus alunos jogaram', sem entrar aluno por aluno."""
    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT t.id           AS tournament_db_id,
                   t.tournament_id,
                   t.tournament_name,
                   t.site,
                   t.avg_score,
                   t.imported_at,
                   t.user_id       AS student_id,
                   u.username      AS student_username,
                   (SELECT COUNT(*) FROM decisions d
                     WHERE d.tournament_id = t.id
                       AND d.label IN ('small_mistake','clear_mistake')) AS n_critical
            FROM tournaments t
            JOIN users u ON u.id = t.user_id
            WHERE u.coach_id = ?
            ORDER BY t.imported_at DESC
            LIMIT ?
        """), (coach_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_coach_cohort_analytics(coach_id: int) -> dict:
    """V2-2 — gráficos da turma: distribuição de qualidade (3 níveis), receita no tempo
    (coach_payments) e heatmap de leaks (street × ação, nº de alunos). Read-only."""
    conn = get_conn()
    try:
        scope = "t.user_id IN (SELECT id FROM users WHERE coach_id = ?)"
        # 1) distribuição de qualidade (colapso para 3 níveis — FEAT-20)
        qrow = conn.execute(_adapt(f"""
            SELECT
              SUM(CASE WHEN d.label='standard' THEN 1 ELSE 0 END)                     AS correct,
              SUM(CASE WHEN d.label='marginal' THEN 1 ELSE 0 END)                     AS acceptable,
              SUM(CASE WHEN d.label IN ('small_mistake','clear_mistake') THEN 1 ELSE 0 END) AS error
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE {scope}
        """), (coach_id,)).fetchone()
        q = dict(qrow) if qrow else {}
        quality = {k: int(q.get(k) or 0) for k in ('correct', 'acceptable', 'error')}
        quality['total'] = sum(quality.values())

        # 2) receita no tempo (até 6 períodos cronológicos)
        rev = conn.execute(_adapt("""
            SELECT period, amount_cents, active_students FROM coach_payments
            WHERE coach_id = ? ORDER BY period DESC LIMIT 6
        """), (coach_id,)).fetchall()
        revenue = [dict(r) for r in reversed(rev)]

        # 3) heatmap de leaks: street × melhor-ação, nº de alunos distintos com leak ali
        heat = conn.execute(_adapt(f"""
            SELECT lower(d.street) AS street, lower(d.best_action) AS action,
                   COUNT(DISTINCT t.user_id) AS n_students
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE {scope} AND d.label IN ('small_mistake','clear_mistake')
              AND lower(d.street) IN ('preflop','flop','turn','river')
            GROUP BY lower(d.street), lower(d.best_action)
        """), (coach_id,)).fetchall()
        leak_heatmap = [dict(r) for r in heat]

        return {'quality': quality, 'revenue': revenue, 'leak_heatmap': leak_heatmap}
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
                    tournament_name: str | None = None,
                    is_pko: bool = False) -> int:
    conn = get_conn()
    lp = metrics.get('label_pct', {})
    try:
        # Upsert — INSERT ou UPDATE se já existe
        conn.execute("""
            INSERT INTO tournaments
              (user_id, tournament_id, site, tournament_name, hero, played_at, imported_at,
               hands_count, decisions_count, avg_score,
               standard_pct, marginal_pct, small_pct, clear_pct,
               result, place, buy_in, prize, profit, raw_text, is_pko)
            VALUES (?,?,?,?,?,?,datetime('now'),?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
              raw_text       = excluded.raw_text,
              is_pko         = excluded.is_pko
        """, (
            user_id, tournament_id, site, tournament_name, hero, played_at,
            metrics.get('total_hands', 0),
            metrics.get('total_decisions', 0),
            metrics.get('avg_mistake_score'),
            lp.get('standard'), lp.get('marginal'),
            lp.get('small_mistake'), lp.get('clear_mistake'),
            result, place, buy_in, prize, profit, raw_text, is_pko,
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
            gto = r.get('gto', {})
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
                ctx.get('icmTaxPct'),
                ctx.get('heroStackBb'),
                r.get('draw_profile', ctx.get('drawProfile', '')),
                r.get('position', ''),
                r.get('num_players', 0),
                r.get('level_sb', 0),
                r.get('level_bb', 0),
                r.get('level_num', 0),
                r.get('note', ''),
                bool(r.get('is_3bet')),
                r.get('showdown_result'),
                pot_size_bb,
                facing_bet_bb,
                gto.get('gto_label') if gto.get('available') else None,
                gto.get('gto_action') if gto.get('available') else None,
                1 if (gto.get('available') and gto.get('depth_capped')) else 0,
                r.get('math', {}).get('estimatedHandEquity'),
                (r.get('spot', {}).get('villainPosition') or '') or None,
                r.get('spot', {}).get('preflopRaisesFaced'),
                (None if r.get('hero_won_hand') is None else (1 if r.get('hero_won_hand') else 0)),
                gto.get('ev_loss_bb'),        # #24: bb perdidos vs melhor ação (preflop)
                gto.get('ev_loss_source'),
                spot_ctx.get('nActiveOpponents'),   # oponentes vivos no momento da decisão (multiway-aware)
            ))
        conn.executemany("""
            INSERT INTO decisions
              (tournament_id, hand_id, street, hero_cards, board,
               action_taken, best_action, label, score,
               math_penalty, range_penalty, m_ratio, icm_pressure, icm_tax_pct,
               stack_bb, draw_profile, position, num_players,
               level_sb, level_bb, level_num, note, is_3bet, showdown_result,
               pot_size, facing_bet, gto_label, gto_action, gto_depth_capped, estimated_equity,
               vs_position, preflop_raises_faced, hero_won_hand,
               ev_loss_bb, ev_loss_source, n_active_opponents)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()
    finally:
        conn.close()


def get_all_tournaments_raw() -> List[dict]:
    """Retorna todos os torneios com raw_text para reprocessamento admin."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, hero, raw_text, site FROM tournaments WHERE raw_text IS NOT NULL").fetchall()
        return [dict(r) for r in rows]
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
                   t.labels_reconciled_at,
                   COUNT(CASE WHEN d.label = 'clear_mistake' THEN 1 END) AS clear_count,
                   COUNT(CASE WHEN d.label = 'small_mistake' THEN 1 END) AS small_count,
                   COUNT(d.id) AS total_decisions_count,
                   SUM(CASE WHEN d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS with_gto_count,
                   SUM(CASE WHEN lower(d.street)='preflop' THEN 1 ELSE 0 END) AS pre_total,
                   SUM(CASE WHEN lower(d.street)='preflop' AND d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS pre_gto,
                   SUM(CASE WHEN lower(d.street) IN ('flop','turn','river') THEN 1 ELSE 0 END) AS post_total,
                   SUM(CASE WHEN lower(d.street) IN ('flop','turn','river') AND d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS post_gto
            FROM tournaments t
            LEFT JOIN decisions d ON d.tournament_id = t.id
            WHERE t.user_id = ?
            GROUP BY t.id
            ORDER BY t.imported_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        result = []
        for r in rows:
            t = dict(r)
            tot = t.pop('total_decisions_count', 0) or 0
            wg = t.pop('with_gto_count', 0) or 0
            t['gto_coverage_pct'] = round(wg * 100.0 / tot, 1) if tot else 0.0
            # cobertura GTO separada por street (preflop = ranges GW ~instant; postflop = solve)
            pre_t = t.pop('pre_total', 0) or 0;  pre_g = t.pop('pre_gto', 0) or 0
            post_t = t.pop('post_total', 0) or 0; post_g = t.pop('post_gto', 0) or 0
            t['preflop_coverage_pct']  = round(pre_g * 100.0 / pre_t, 1) if pre_t else None
            t['postflop_coverage_pct'] = round(post_g * 100.0 / post_t, 1) if post_t else None
            result.append(t)
        return result
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

def get_evolution_metrics(user_id: int, days: int = 90, last_n: int | None = None) -> List[dict]:
    """Retorna métricas por torneio para o gráfico de evolução."""
    tourn_filter, tourn_params = _build_tournament_filter(user_id, days, last_n)
    # Evolution query filters tournaments directly (no decisions join needed)
    if last_n is not None:
        where = "id IN (SELECT id FROM tournaments WHERE user_id = ? ORDER BY imported_at DESC LIMIT ?)"
        params = (user_id, last_n)
    else:
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        where = "user_id = ? AND imported_at >= ?"
        params = (user_id, since)
    conn = get_conn()
    try:
        rows = conn.execute(f"""
            SELECT tournament_id, site, played_at, imported_at,
                   hands_count, decisions_count, avg_score,
                   standard_pct, clear_pct,
                   buy_in, prize, profit, place, result
            FROM tournaments
            WHERE {where}
            ORDER BY imported_at ASC
        """, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_leak_summary(user_id: int, days: int = 90, last_n: int | None = None) -> List[dict]:
    """Agrega leaks por street/ação no período."""
    tourn_filter, tourn_params = _build_tournament_filter(user_id, days, last_n)
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(f"""
            SELECT
                d.street || '/' || d.best_action AS spot,
                COUNT(*)                          AS n,
                AVG(d.score)                      AS avg_score,
                SUM(d.score)                      AS total_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tourn_filter}
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
            HAVING COUNT(*) >= 2
            ORDER BY avg_score DESC
            LIMIT 10
        """), tourn_params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_leak_roi_impact(user_id: int, days: int = 90, last_n: int | None = None) -> list:
    """Leaks enriquecidos com ROI estimado, priority_score e trend de progressão."""
    from datetime import datetime, timedelta
    tf, tp = _build_tournament_filter(user_id, days, last_n)
    now          = datetime.utcnow()
    recent_since = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    prev_since   = (now - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(f"""
            SELECT
                d.street || '/' || d.best_action  AS spot,
                COUNT(*)                           AS n,
                AVG(d.score)                       AS avg_score,
                SUM(d.score)                       AS total_score,
                AVG(COALESCE(t.buy_in, 0))         AS avg_buy_in,
                COUNT(*) * AVG(d.score)            AS priority_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
            HAVING COUNT(*) >= 2
            ORDER BY priority_score DESC
            LIMIT 10
        """), tp).fetchall()

        # Trend comparison uses fixed 30-day windows (independent of last_n)
        recent_rows = conn.execute(_adapt("""
            SELECT d.street || '/' || d.best_action AS spot, AVG(d.score) AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
              AND d.label IN ('small_mistake','clear_mistake')
            GROUP BY spot
        """), (user_id, recent_since)).fetchall()
        recent_map = {r['spot']: r['avg_score'] for r in recent_rows}

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
        # Fila de treino priorizada por impacto de EV ($/mês) p/ alinhar com o Leak Finder
        # (diagnóstico por EV-bb). Empate cai no priority_score (robusto quando buy_in=0).
        result.sort(key=lambda r: (r.get('ev_loss_monthly') or 0, r.get('priority_score') or 0), reverse=True)
        for i, r in enumerate(result, 1):
            r['priority_rank'] = i
        return result
    finally:
        conn.close()


def get_ev_leaks(user_id: int, days: int = 90, last_n: int | None = None, limit: int = 10) -> dict:
    """Leaks ranqueados por EV PERDIDO (bb) — #24/#25 (início do Leak Finder).

    Soma `ev_loss_bb` por spot (posição × street × ação ideal) e ranqueia pelo
    total de big blinds deixados na mesa — em vez de contagem de erros. Só preflop
    tem ev_loss hoje. Devolve {leaks:[...], total_ev_loss_bb, n_leaks}."""
    tf, tp = _build_tournament_filter(user_id, days, last_n)
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(f"""
            SELECT
                COALESCE(d.position,'?')      AS position,
                d.street                      AS street,
                d.best_action                 AS ideal_action,
                COUNT(*)                      AS n,
                ROUND(SUM(d.ev_loss_bb), 2)   AS total_ev_loss_bb,
                ROUND(AVG(d.ev_loss_bb), 3)   AS avg_ev_loss_bb
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.ev_loss_bb IS NOT NULL AND d.ev_loss_bb > 0.05
            GROUP BY position, street, ideal_action
            ORDER BY total_ev_loss_bb DESC
            LIMIT ?
        """), tp + (limit,)).fetchall()
        tot = conn.execute(_adapt(f"""
            SELECT ROUND(SUM(d.ev_loss_bb), 2) AS tot, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf} AND d.ev_loss_bb IS NOT NULL AND d.ev_loss_bb > 0.05
        """), tp).fetchone()
        return {
            'leaks': [dict(r) for r in rows],
            'total_ev_loss_bb': (tot['tot'] or 0.0) if tot else 0.0,
            'n_leaks':          (tot['n'] or 0) if tot else 0,
        }
    finally:
        conn.close()


def get_consolidated_leak_report(user_id: int, days: int = 90, last_n: int | None = None,
                                 limit: int = 6) -> dict:
    """#25 — Leak Finder consolidado (carro-chefe "LeakLab").

    Síntese priorizada dos vazamentos por **EV perdido** (reusa get_ev_leaks):
    severidade por bb, total deixado na mesa, e o top leak em destaque. Cada leak
    traz (posição, street, ação ideal, n, total/avg bb) p/ o card linkar pro
    drill/revisão. Os rótulos legíveis e o CTA ficam no front (i18n)."""
    ev = get_ev_leaks(user_id, days, last_n, limit=limit)

    def _sev(bb: float) -> str:
        return 'high' if bb >= 5 else ('medium' if bb >= 1.5 else 'low')

    leaks = [{**l, 'severity': _sev(l.get('total_ev_loss_bb') or 0)} for l in ev['leaks']]
    return {
        'total_ev_loss_bb': ev['total_ev_loss_bb'],
        'n_leaks':          ev['n_leaks'],
        'leaks':            leaks,
        'top_leak':         leaks[0] if leaks else None,
        'has_ev':           bool(leaks),
    }


def get_leak_ranking_gto_first(user_id: int, days: int = 90, last_n: int | None = None,
                                limit: int = 10) -> dict:
    """Leak ranking unificado: tenta GTO primeiro (gto_label-based), fallback heurístico (label-based).

    Retorna {'source': 'gto'|'heuristic'|'empty', 'leaks': [...]}.
    Shape de cada leak é compatível entre as duas fontes (mesmos campos).
    Consumido pelo /player/leak-roi, generate_study_plan, coach_chat, /coach/context,
    /history/evolution, recommend_coaches_for_leaks.
    """
    leaks = get_gto_leak_ranking(user_id, days, last_n=last_n)
    if leaks:
        return {'source': 'gto', 'leaks': leaks[:limit]}
    leaks = get_leak_roi_impact(user_id, days, last_n=last_n)
    if leaks:
        return {'source': 'heuristic', 'leaks': leaks[:limit]}
    return {'source': 'empty', 'leaks': []}


def get_gto_leak_ranking(user_id: int, days: int = 90, last_n: int | None = None) -> list:
    """
    Leak ranking baseado em gto_label — substitui get_leak_roi_impact com fonte GTO.
    Usa score proxy: gto_critical=0.45, gto_minor_deviation=0.15.
    Mantém a mesma interface de saída (spot, n, avg_score, ev_loss_monthly,
    priority_rank, trend, drill_count, drill_accuracy).
    """
    from datetime import datetime, timedelta
    tf, tp = _build_tournament_filter(user_id, days, last_n)
    now          = datetime.utcnow()
    recent_since = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    prev_since   = (now - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(f"""
            SELECT
                d.street || '/' || d.best_action AS spot,
                COUNT(*) AS n,
                AVG(CASE
                    WHEN d.gto_label = 'gto_critical'          THEN 0.45
                    WHEN d.gto_label = 'gto_minor_deviation'   THEN 0.15
                    ELSE 0.0
                END) AS avg_score,
                AVG(COALESCE(t.buy_in, 0)) AS avg_buy_in,
                COUNT(*) * AVG(CASE
                    WHEN d.gto_label = 'gto_critical'          THEN 0.45
                    WHEN d.gto_label = 'gto_minor_deviation'   THEN 0.15
                    ELSE 0.0
                END) AS priority_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.gto_label IN ('gto_critical', 'gto_minor_deviation')
            GROUP BY spot
            HAVING COUNT(*) >= 2
            ORDER BY priority_score DESC
            LIMIT 10
        """), tp).fetchall()

        def _proxy_rows(since_val, until_val=None):
            q = """
                SELECT d.street || '/' || d.best_action AS spot,
                       AVG(CASE
                           WHEN d.gto_label = 'gto_critical'        THEN 0.45
                           WHEN d.gto_label = 'gto_minor_deviation' THEN 0.15
                           ELSE 0.0
                       END) AS avg_score
                FROM decisions d
                JOIN tournaments t ON t.id = d.tournament_id
                WHERE t.user_id = ? AND t.imported_at >= ?
                  AND d.gto_label IN ('gto_critical', 'gto_minor_deviation')
            """
            params = [user_id, since_val]
            if until_val:
                q += " AND t.imported_at < ?"
                params.append(until_val)
            q += " GROUP BY spot"
            return {r['spot']: r['avg_score'] for r in conn.execute(_adapt(q), params).fetchall()}

        recent_map = _proxy_rows(recent_since)
        prev_map   = _proxy_rows(prev_since, recent_since)

        drill_rows = conn.execute(_adapt("""
            SELECT dec.street || '/' || dec.best_action AS spot,
                   COUNT(*) AS drill_count,
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
            r['priority_rank']   = rank
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


def _drill_context(r: dict) -> dict:
    """Computa facing_desc e context_note a partir dos campos existentes de um spot de drill."""
    pos      = (r.get('position') or '').upper()
    street   = r.get('street', 'preflop')
    facing   = float(r.get('facing_bet') or 0)
    level_bb = float(r.get('level_bb') or 100)
    is_3bet  = bool(r.get('is_3bet'))

    facing_desc = None
    if facing > 0 and level_bb > 0:
        bb_size = round(facing / level_bb, 1)
        if is_3bet:
            facing_desc = f"3-Bet {bb_size}bb"
        elif street == 'preflop':
            facing_desc = f"Raise {bb_size}bb"
        else:
            facing_desc = f"Bet {bb_size}bb"
    elif facing == 0 and pos == 'BB' and street == 'preflop':
        facing_desc = "SB completou"

    context_note = 'hu_postflop' if street != 'preflop' else None

    return {'facing_desc': facing_desc, 'context_note': context_note}


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
        # Busca 3x candidatos: a diversificação (máx 2 por grupo street/ação) é
        # aplicada em Python preservando a ordem SRS — evita sessão monótona com
        # 10 repetições do mesmo tipo de spot.
        params.append(limit * 3)

        rows = conn.execute(_adapt(f"""
            SELECT
                d.id, d.hand_id, d.street, d.hero_cards, d.board,
                d.action_taken, d.best_action, d.label, d.score,
                d.m_ratio, d.icm_pressure, d.stack_bb, d.position,
                d.num_players, d.is_3bet, d.level_bb, d.note, d.draw_profile,
                d.pot_size, d.facing_bet,
                d.gto_action, d.gto_label,
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
              AND (ds_last.next_drill_at IS NULL OR ds_last.next_drill_at <= ?)
              AND NOT (d.position = 'BB' AND COALESCE(d.facing_bet, 0) = 0 AND d.best_action = 'fold')
              AND d.position IS NOT NULL AND d.position != ''
              AND d.hero_cards IS NOT NULL AND d.hero_cards != ''
              AND d.gto_label IN ('gto_minor_deviation', 'gto_critical')
              AND d.gto_action IS NOT NULL AND d.gto_action != ''
              {street_filter}
              {spot_filter}
            ORDER BY
                CASE WHEN ds_last.next_drill_at IS NULL THEN 0 ELSE 1 END ASC,
                ds_last.next_drill_at ASC,
                d.score DESC
            LIMIT ?
        """), params).fetchall()

        # Diversificação: na 1ª passada cada grupo (street, best_action) entra no
        # máximo 2x; se não encher o lote, a 2ª passada completa sem o teto.
        if not spot:
            picked, seen_groups = [], {}
            for row in rows:
                grp = (row['street'], row['best_action'])
                if seen_groups.get(grp, 0) < 2:
                    picked.append(row)
                    seen_groups[grp] = seen_groups.get(grp, 0) + 1
                if len(picked) >= limit:
                    break
            if len(picked) < limit:
                chosen_ids = {r['id'] for r in picked}
                for row in rows:
                    if row['id'] not in chosen_ids:
                        picked.append(row)
                        if len(picked) >= limit:
                            break
            rows = picked
        else:
            rows = rows[:limit]

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
            r.update(_drill_context(r))
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
            SELECT srs_interval_days, drilled_at FROM drill_sessions
            WHERE user_id = ? AND decision_id = ?
            ORDER BY drilled_at DESC LIMIT 1
        """), (user_id, decision_id)).fetchone()

        last_interval = (last['srs_interval_days'] or 3) if last else 3
        # Anti-farm de XP: 1ª vez do dia (UTC, como drilled_at) por decisão.
        today = datetime.utcnow().date().isoformat()
        first_drill_today = not (last and str(last['drilled_at'] or '')[:10] == today)

        if is_correct:
            try:
                idx = _SRS_INTERVALS.index(last_interval)
                new_interval = _SRS_INTERVALS[min(idx + 1, len(_SRS_INTERVALS) - 1)]
            except ValueError:
                new_interval = min(last_interval * 2, _SRS_INTERVALS[-1])
        else:
            new_interval = _SRS_INTERVALS[0]

        # Mastered = atingiu o intervalo máximo do SRS pela 1ª vez nesta decisão
        # (sessões antigas no teto bloqueiam re-grant — inclusive após reset por erro).
        mastered_now = False
        if new_interval == _SRS_INTERVALS[-1]:
            prior_max = conn.execute(_adapt("""
                SELECT 1 FROM drill_sessions
                WHERE user_id = ? AND decision_id = ? AND srs_interval_days = ?
                LIMIT 1
            """), (user_id, decision_id, _SRS_INTERVALS[-1])).fetchone()
            mastered_now = prior_max is None

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
            'first_drill_today': first_drill_today,
            'mastered_now':      mastered_now,
        }
    finally:
        conn.close()


def get_drill_stats(user_id: int, days: int = 30) -> dict:
    """Sprint K — Estatísticas de drill dos últimos N dias."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        row = conn.execute(_adapt("""
            SELECT
                COUNT(*)                                          AS total,
                AVG(delta)                                        AS avg_delta,
                SUM(CASE WHEN delta < 0 THEN 1 ELSE 0 END)       AS correct,
                SUM(CASE WHEN delta >= 0 THEN 1 ELSE 0 END)      AS incorrect
            FROM drill_sessions
            WHERE user_id = ? AND drilled_at >= ?
        """), (user_id, cutoff)).fetchone()
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
                   d.level_num, d.note, d.is_3bet, d.pot_size, d.facing_bet,
                   d.gto_action, d.gto_label
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

        gto_row = conn.execute(f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS with_gto
            {base}
        """, (user_id, since)).fetchone()
        total_dec = gto_row['total'] if gto_row else 0
        with_gto = gto_row['with_gto'] if gto_row else 0
        gto_coverage_pct = round(with_gto * 100.0 / total_dec, 1) if total_dec else 0.0

        return {
            'by_street':   {r['street']:   dict(r) for r in by_street},
            'by_position': {r['position']: dict(r) for r in by_position if r['position']},
            'by_label':    {r['label']:    r['n']   for r in by_label   if r['label']},
            'gto_coverage_pct': gto_coverage_pct,
            'total_decisions':  total_dec,
            'with_gto':         with_gto,
        }
    finally:
        conn.close()


def get_player_stats(user_id: int, days: int = 90, last_n: int | None = None) -> dict:
    """Computes poker HUD stats from stored decisions."""
    tf, tp = _build_tournament_filter(user_id, days, last_n)
    conn = get_conn()
    try:
        # ── Preflop basics (VPIP, PFR) ───────────────────────────────────────
        preflop = conn.execute(_adapt(f"""
            SELECT
                COUNT(DISTINCT d.hand_id) AS total_hands,
                COUNT(DISTINCT CASE WHEN d.action_taken IN ('call','raise','jam') THEN d.hand_id END) AS vpip_hands,
                COUNT(DISTINCT CASE WHEN d.action_taken IN ('raise','jam') THEN d.hand_id END) AS pfr_hands
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf} AND d.street = 'preflop'
        """), tp).fetchone()

        # ── Postflop aggression (AF) ─────────────────────────────────────────
        postflop = conn.execute(_adapt(f"""
            SELECT
                COUNT(CASE WHEN d.action_taken IN ('bet','raise','jam') THEN 1 END) AS aggressive,
                COUNT(CASE WHEN d.action_taken = 'call' THEN 1 END) AS passive
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf} AND d.street != 'preflop'
        """), tp).fetchone()

        # ── C-bet: first flop bet as preflop aggressor / PFA hands seeing flop ─
        cbet_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(DISTINCT CASE WHEN flop_d.action_taken = 'bet' THEN sub.hand_id END) AS cbet_n,
                COUNT(DISTINCT sub.hand_id) AS cbet_opp
            FROM (
                SELECT d.hand_id,
                       MIN(CASE WHEN d.street = 'flop' THEN d.id END) AS first_flop_id
                FROM decisions d
                JOIN tournaments t ON t.id = d.tournament_id
                WHERE {tf}
                GROUP BY d.hand_id
                HAVING MAX(CASE WHEN d.street = 'preflop' AND d.action_taken IN ('raise','jam') THEN 1 ELSE 0 END) = 1
                   AND MIN(CASE WHEN d.street = 'flop' THEN d.id END) IS NOT NULL
            ) sub
            JOIN decisions flop_d ON flop_d.id = sub.first_flop_id
        """), tp).fetchone()

        # ── Fold-to-3BET: hands where hero raised preflop THEN folded ────────
        f3b_row = conn.execute(_adapt(f"""
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
                WHERE {tf} AND d.street = 'preflop'
                GROUP BY d.hand_id
                HAVING COUNT(*) > 1
                   AND MIN(CASE WHEN d.action_taken IN ('raise','jam') THEN d.id END) IS NOT NULL
            ) sub
        """), tp).fetchone()

        # ── WTSD approx: hands reaching river / hands seeing flop ────────────
        wtsd_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(DISTINCT CASE WHEN d.street = 'flop'  THEN d.hand_id END) AS saw_flop,
                COUNT(DISTINCT CASE WHEN d.street = 'river' THEN d.hand_id END) AS saw_river
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
        """), tp).fetchone()

        # ── 3BET%: hands where hero 3-bet / OPORTUNIDADES (preflop enfrentando um
        # raise). Denominador padrão HM/PT = faced-a-raise (facing_bet>0), NÃO todas
        # as mãos preflop — usar todas dilui o número ~3-5× e mascara overaggression.
        tbet_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(DISTINCT CASE WHEN d.is_3bet = TRUE THEN d.hand_id END) AS three_bet_n,
                COUNT(DISTINCT CASE WHEN d.facing_bet > 0 THEN d.hand_id END) AS opp_n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf} AND d.street = 'preflop'
        """), tp).fetchone()

        # ── W$SD: hands won at showdown / total showdown hands ───────────────
        wsd_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(DISTINCT CASE WHEN d.showdown_result = 'won'  THEN d.hand_id END) AS sd_won,
                COUNT(DISTINCT CASE WHEN d.showdown_result IS NOT NULL THEN d.hand_id END) AS sd_total
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
        """), tp).fetchone()

        # ── Fold to Flop Bet (proxy for Fold to C-Bet) ────────────────────────
        ftfb_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(CASE WHEN d.action_taken = 'fold' THEN 1 END) AS ftfb_n,
                COUNT(*) AS ftfb_total
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.street = 'flop' AND d.facing_bet > 0
        """), tp).fetchone()

        # ── BB Defense Rate: BB call+3bet vs preflop open ─────────────────────
        bb_def_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(CASE WHEN d.action_taken IN ('call','raise','jam') THEN 1 END) AS bb_def_n,
                COUNT(*) AS bb_def_total
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.street = 'preflop' AND d.position = 'BB' AND d.facing_bet > 0
        """), tp).fetchone()

        # ── Steal%: raise/shove from BTN/CO/SB when not facing a raise ────────
        steal_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(CASE WHEN d.action_taken IN ('raise','jam') THEN 1 END) AS steal_n,
                COUNT(*) AS steal_total
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.street = 'preflop' AND d.position IN ('BTN','CO','SB')
              AND (d.facing_bet IS NULL OR d.facing_bet = 0)
        """), tp).fetchone()

        # ── Open Limp%: preflop calls without a raise in front (non-BB) ────────
        limp_row = conn.execute(_adapt(f"""
            SELECT
                COUNT(CASE WHEN d.action_taken = 'call' THEN 1 END) AS limp_n,
                COUNT(*) AS limp_total
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.street = 'preflop'
              AND d.position NOT IN ('BB')
              AND (d.facing_bet IS NULL OR d.facing_bet = 0)
        """), tp).fetchone()

        # ── Compute stats ────────────────────────────────────────────────────
        pf    = dict(preflop)    if preflop    else {}
        po    = dict(postflop)   if postflop   else {}
        cb    = dict(cbet_row)   if cbet_row   else {}
        f3b   = dict(f3b_row)    if f3b_row    else {}
        wt    = dict(wtsd_row)   if wtsd_row   else {}
        tb    = dict(tbet_row)   if tbet_row   else {}
        wsd   = dict(wsd_row)    if wsd_row    else {}
        ftfb  = dict(ftfb_row)   if ftfb_row   else {}
        bb_d  = dict(bb_def_row) if bb_def_row else {}
        st    = dict(steal_row)  if steal_row  else {}
        lp    = dict(limp_row)   if limp_row   else {}

        total       = pf.get('total_hands', 0) or 0
        vpip_h      = pf.get('vpip_hands', 0) or 0
        pfr_h       = pf.get('pfr_hands', 0) or 0
        aggressive  = po.get('aggressive', 0) or 0
        passive     = po.get('passive', 0) or 0
        cbet_n      = cb.get('cbet_n', 0) or 0
        cbet_opp    = cb.get('cbet_opp', 0) or 0
        f3b_n       = f3b.get('fold_to_3bet_n', 0) or 0
        faced_3b_n  = f3b.get('faced_3bet_n', 0) or 0
        saw_flop    = wt.get('saw_flop', 0) or 0
        saw_river   = wt.get('saw_river', 0) or 0
        three_bet_n   = tb.get('three_bet_n', 0) or 0
        three_bet_opp = tb.get('opp_n', 0) or 0
        sd_won      = wsd.get('sd_won', 0) or 0
        sd_total    = wsd.get('sd_total', 0) or 0
        ftfb_n      = ftfb.get('ftfb_n', 0) or 0
        ftfb_total  = ftfb.get('ftfb_total', 0) or 0
        bb_def_n    = bb_d.get('bb_def_n', 0) or 0
        bb_def_t    = bb_d.get('bb_def_total', 0) or 0
        steal_n     = st.get('steal_n', 0) or 0
        steal_t     = st.get('steal_total', 0) or 0
        limp_n      = lp.get('limp_n', 0) or 0
        limp_t      = lp.get('limp_total', 0) or 0

        return {
            'total_hands':      total,
            'vpip':             round(vpip_h / total * 100, 1)         if total > 0       else None,
            'pfr':              round(pfr_h  / total * 100, 1)         if total > 0       else None,
            'af':               round(aggressive / passive, 2)          if passive > 0     else None,
            'cbet_pct':         round(cbet_n / cbet_opp * 100, 1)      if cbet_opp > 0    else None,
            'fold_to_3bet':     round(f3b_n / faced_3b_n * 100, 1)    if faced_3b_n > 0  else None,
            'wtsd':             round(saw_river / saw_flop * 100, 1)   if saw_flop > 0    else None,
            'three_bet':        round(three_bet_n / three_bet_opp * 100, 1) if three_bet_opp >= 12 else None,
            'three_bet_opp':    three_bet_opp,
            'w_at_sd':          round(sd_won / sd_total * 100, 1)      if sd_total > 0    else None,
            'fold_to_flop_bet': round(ftfb_n / ftfb_total * 100, 1)   if ftfb_total > 0  else None,
            'bb_defense':       round(bb_def_n / bb_def_t * 100, 1)   if bb_def_t > 0    else None,
            'steal_pct':        round(steal_n / steal_t * 100, 1)     if steal_t > 0     else None,
            'open_limp_pct':    round(limp_n / limp_t * 100, 1)       if limp_t > 0      else None,
        }
    finally:
        conn.close()


def get_player_level(user_id: int, min_tournaments: int = 5, days: int = 30) -> dict:
    """
    Nível de gamificação do jogador — UNIFICADO com o ELO (2026-05-28).

    O nível agora deriva do ELO de forma recente (não mais do standard_pct
    heurístico). Os 7 níveis (Iniciante→Elite) são as bandas do ELO. Mantém
    a mesma forma de resposta pra compat com LevelCard/study/coach, mas com
    campos novos: `elo`, `elo_min`, `elo_max`, `peak_elo`.

    `standard_pct` ainda retornado (informativo), mas NÃO define mais o nível.
    """
    from datetime import datetime, timedelta
    from leaklab.elo_engine import BANDS, band_full, compute_player_elo_from_decisions
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    conn = get_conn()
    try:
        # Conta torneios (pra gating de min_tournaments / "sem dados")
        t_count_row = conn.execute(
            "SELECT COUNT(*) AS n FROM tournaments WHERE user_id = ?", (user_id,)
        ).fetchone()
        t_count = t_count_row['n'] if t_count_row else 0
        if not t_count:
            return {"level": None, "tournament_count": 0}

        # standard_pct informativo (média últimos 5)
        std_rows = conn.execute("""
            SELECT standard_pct FROM tournaments
            WHERE user_id = ? AND standard_pct IS NOT NULL
            ORDER BY imported_at DESC LIMIT 5
        """, (user_id,)).fetchall()
        std_values = [r['standard_pct'] for r in std_rows if r['standard_pct'] is not None]
        avg_std = round(sum(std_values) / len(std_values), 2) if std_values else None
    finally:
        conn.close()

    # ELO de forma recente — preferir snapshot mais recente; senão computa
    ELO_WINDOW = 25
    latest = get_latest_elo(user_id)
    if latest and latest.get('elo_overall') is not None:
        elo = float(latest['elo_overall'])
        n_dec = int(latest.get('total_decisions') or 0)
    else:
        decisions = get_decisions_for_elo(user_id, last_n_tournaments=ELO_WINDOW)
        snap = compute_player_elo_from_decisions(user_id, decisions)
        elo = snap.overall.elo
        n_dec = snap.overall.n_decisions

    peak = get_peak_elo(user_id)

    # Mapeia ELO → banda/nível (BANDS = [(threshold, icon, label, color), ...])
    cur_idx = 0
    for i, entry in enumerate(BANDS):
        if elo >= entry[0]:
            cur_idx = i
    cur = BANDS[cur_idx]
    nxt = BANDS[cur_idx + 1] if cur_idx + 1 < len(BANDS) else None

    elo_min = cur[0]
    elo_max = nxt[0] if nxt else None
    if elo_max is not None and elo_max > elo_min:
        progress = round((elo - elo_min) / (elo_max - elo_min), 3)
        progress = max(0.0, min(1.0, progress))
    else:
        progress = 1.0

    # Top leaks que bloqueiam o avanço (spots com mais erros)
    conn = get_conn()
    try:
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
    finally:
        conn.close()

    return {
        "level":            cur[2],
        "icon":             cur[1],
        "elo":              round(elo, 1),
        "elo_min":          elo_min,
        "elo_max":          elo_max,
        "peak_elo":         round(peak, 1) if peak is not None else None,
        "standard_pct":     avg_std,       # informativo (não define nível)
        # level_min/max mantidos por compat (agora em escala ELO)
        "level_min":        elo_min,
        "level_max":        elo_max if elo_max is not None else elo_min,
        "next_level":       nxt[2] if nxt else None,
        "next_level_icon":  nxt[1] if nxt else None,
        "next_pct":         nxt[0] if nxt else None,   # agora é ELO threshold
        "progress":         progress,
        "decisions_scored": n_dec,
        "tournament_count": t_count,
        "top_blocking_leaks": [{"spot": r["spot"], "n": r["n"], "avg_score": round(r["avg_score"], 1)}
                                for r in top_leaks_rows],
    }


def get_player_action_frequencies(user_id: int, days: int = 90) -> dict:
    """
    Agrega frequências de ação por street e por posição (preflop).
    Retorna dicionário com percentuais prontos para injetar no contexto do AI Coach.
    """
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    conn  = get_conn()
    try:
        # ── Frequências por street ─────────────────────────────────────────────
        rows = conn.execute("""
            SELECT d.street, d.action_taken, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON d.tournament_id = t.id
            WHERE t.user_id = ? AND t.imported_at >= ?
              AND d.action_taken IS NOT NULL AND d.action_taken != ''
            GROUP BY d.street, d.action_taken
        """, (user_id, since)).fetchall()

        by_street: dict = {}
        for r in rows:
            s = r['street'] or 'preflop'
            a = r['action_taken']
            by_street.setdefault(s, {})[a] = r['n']

        street_freqs: dict = {}
        for street in ['preflop', 'flop', 'turn', 'river']:
            acts = by_street.get(street, {})
            total = sum(acts.values())
            if total == 0:
                continue
            street_freqs[street] = {
                'total': total,
                'pcts': {a: round(n / total * 100, 1) for a, n in sorted(acts.items(), key=lambda x: -x[1])},
            }

        # ── Frequências preflop por posição ───────────────────────────────────
        pos_rows = conn.execute("""
            SELECT d.position, d.action_taken, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON d.tournament_id = t.id
            WHERE t.user_id = ? AND t.imported_at >= ?
              AND d.street = 'preflop'
              AND d.action_taken IS NOT NULL AND d.action_taken != ''
              AND d.position IS NOT NULL AND d.position != ''
            GROUP BY d.position, d.action_taken
        """, (user_id, since)).fetchall()

        by_pos: dict = {}
        for r in pos_rows:
            by_pos.setdefault(r['position'], {})[r['action_taken']] = r['n']

        pos_freqs: dict = {}
        priority = ['BTN', 'CO', 'MP', 'UTG', 'SB', 'BB']
        for pos in priority:
            acts = by_pos.get(pos, {})
            total = sum(acts.values())
            if total < 10:  # skip positions with too few samples
                continue
            pos_freqs[pos] = {
                'total': total,
                'pcts': {a: round(n / total * 100, 1) for a, n in sorted(acts.items(), key=lambda x: -x[1])},
            }

        return {'by_street': street_freqs, 'by_position': pos_freqs}
    finally:
        conn.close()


def get_career_projection(user_id: int) -> dict:
    """
    Projeta a trajetória de carreira do jogador — UNIFICADO com ELO (2026-05-28).
    Regressão linear sobre a CURVA DE ELO (torneio-a-torneio) → data estimada
    para cada nível/banda. Antes usava standard_pct heurístico; agora alinhado
    ao rating ELO oficial.
    """
    from datetime import datetime, timedelta
    from leaklab.elo_engine import BANDS, compute_elo_curve

    # name → slug (pro frontend manter cores/i18n)
    SLUG = {"Iniciante": "beginner", "Estudante": "student", "Grinder": "grinder",
            "Regular": "regular", "Sólido": "solid", "Expert": "expert", "Elite": "elite"}
    # LEVELS derivados das BANDS do ELO: (slug, name, min_elo, max_elo)
    LEVELS = []
    for i, (thr, _icon, label, _color) in enumerate(BANDS):
        nxt = BANDS[i + 1][0] if i + 1 < len(BANDS) else 9999
        LEVELS.append({"name": label, "slug": SLUG.get(label, label.lower()),
                       "min": thr, "max": nxt})

    # Curva de ELO all-time (1 ponto por torneio com gto_label)
    decisions = get_decisions_for_elo_curve(user_id)
    curve = compute_elo_curve(decisions)

    if len(curve) < 5:
        return {"insufficient_data": True, "tournament_count": len(curve)}

    # Datas dos torneios (pra cadência/estimativa)
    conn = get_conn()
    try:
        trows = conn.execute(_adapt(
            "SELECT id, imported_at FROM tournaments WHERE user_id = ?"
        ), (user_id,)).fetchall()
    finally:
        conn.close()
    date_by_tid = {r["id"]: r["imported_at"] for r in trows}

    elos = [p["elo"] for p in curve]
    n = len(elos)
    xs = list(range(n))

    # Linear regression (pure Python) sobre a curva de ELO
    sum_x  = sum(xs)
    sum_y  = sum(elos)
    sum_xy = sum(x * y for x, y in zip(xs, elos))
    sum_x2 = sum(x * x for x in xs)
    denom  = n * sum_x2 - sum_x ** 2
    slope     = (n * sum_xy - sum_x * sum_y) / denom if denom else 0.0
    intercept = (sum_y - slope * sum_x) / n

    current_projected = slope * (n - 1) + intercept
    current_avg       = round(elos[-1], 1)   # = ELO atual (all-time)

    # Tournaments per month a partir da cadência real
    try:
        d0 = date_by_tid.get(curve[0]["tournament_id"])
        d1 = date_by_tid.get(curve[-1]["tournament_id"])
        first_date = datetime.fromisoformat(str(d0).replace("Z", ""))
        last_date  = datetime.fromisoformat(str(d1).replace("Z", ""))
        months_span = max((last_date - first_date).days / 30.0, 1.0)
    except Exception:
        months_span = max(n / 4.0, 1.0)
    tourns_per_month = n / months_span

    # Nível atual (banda do ELO)
    current_level = LEVELS[0]
    for lv in LEVELS:
        if current_avg >= lv["min"]:
            current_level = lv

    # Milestones: bandas acima da atual
    milestones = []
    today = datetime.utcnow()
    for lv in LEVELS:
        if lv["min"] <= current_level["min"]:
            continue
        if slope <= 0:
            milestones.append({
                "level_name": lv["name"], "level_slug": lv["slug"],
                "threshold":  lv["min"], "reachable":  False,
            })
            continue
        tourns_needed = (lv["min"] - current_projected) / slope
        if tourns_needed <= 0:
            milestones.append({
                "level_name": lv["name"], "level_slug": lv["slug"],
                "threshold":  lv["min"], "reachable":  True,
                "tournaments_needed": 0, "months_needed": 0.0,
                "estimated_date": today.strftime("%Y-%m-%d"),
            })
        else:
            months_needed = tourns_needed / tourns_per_month
            est_date = today + timedelta(days=months_needed * 30)
            milestones.append({
                "level_name":       lv["name"], "level_slug": lv["slug"],
                "threshold":        lv["min"], "reachable":  True,
                "tournaments_needed": round(tourns_needed),
                "months_needed":    round(months_needed, 1),
                "estimated_date":   est_date.strftime("%Y-%m-%d"),
            })

    # Sparkline: ELO histórico + projeção curta
    series_history = [round(e, 1) for e in elos]
    proj_points = max(5, min(10, round(n * 0.3)))
    series_projection = []
    for i in range(1, proj_points + 1):
        proj_val = slope * (n - 1 + i) + intercept
        series_projection.append(round(max(0, proj_val), 1))

    next_milestone = next((m for m in milestones if m.get("reachable", False)), None)

    # Blocking leaks (from get_player_level logic)
    conn2 = get_conn()
    try:
        since = (datetime.utcnow() - timedelta(days=90)).isoformat()
        blocking_rows = conn2.execute(_adapt("""
            SELECT d.street || '/' || d.best_action AS spot,
                   COUNT(*) AS n, AVG(d.score) AS avg_score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND d.label IN ('small_mistake','clear_mistake')
              AND t.imported_at >= ?
            GROUP BY spot HAVING COUNT(*) >= 2
            ORDER BY n DESC LIMIT 3
        """), (user_id, since)).fetchall()
    finally:
        conn2.close()

    blocking_leaks = [
        {"spot": r["spot"], "n": r["n"], "avg_score": round(r["avg_score"], 2)}
        for r in blocking_rows
    ]

    is_top_band = current_level["max"] >= 9999
    lv_span     = current_level["max"] - current_level["min"]
    if is_top_band:
        lv_progress = 1.0
    else:
        lv_progress = round((current_avg - current_level["min"]) / lv_span, 3) if lv_span > 0 else 1.0
    lv_progress = max(0.0, min(1.0, lv_progress))

    return {
        "insufficient_data":    False,
        "metric":               "elo",   # sinaliza pro frontend que valores são ELO
        "tournament_count":     n,
        "current_level":        current_level["name"],
        "current_level_slug":   current_level["slug"],
        "current_avg":          current_avg,        # = ELO atual (all-time)
        "current_elo":          current_avg,
        "level_min":            current_level["min"],
        "level_max":            None if is_top_band else current_level["max"],
        "level_progress":       lv_progress,
        "slope_per_tournament": round(slope, 4),    # ELO/torneio
        "tourns_per_month":     round(tourns_per_month, 1),
        "milestones":           milestones,
        "next_milestone":       next_milestone,
        "series_history":       series_history,      # ELO por torneio
        "series_projection":    series_projection,
        "blocking_leaks":       blocking_leaks,
    }


def get_cognitive_failure_report(user_id: int, days: int = 90) -> dict:
    """
    Sprint AQ — Detecta padrões de falha cognitivo-emocional nas decisões do jogador.
    Analisa janelas deslizantes sobre a sequência cronológica de decisões por torneio.
    """
    from datetime import datetime, timedelta
    from leaklab.cognitive_mapper import analyze_cognitive_failures

    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT d.id, d.tournament_id, d.hand_id, d.street,
                   d.action_taken, d.best_action, d.label, d.score,
                   d.position, d.m_ratio, d.icm_pressure, d.icm_tax_pct, d.stack_bb
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
            ORDER BY d.tournament_id, d.id
        """), (user_id, cutoff)).fetchall()
    finally:
        conn.close()

    decisions = [
        {
            "id":            r["id"],
            "tournament_id": r["tournament_id"],
            "hand_id":       r["hand_id"],
            "street":        r["street"],
            "action_taken":  (r["action_taken"] or "").lower(),
            "best_action":   r["best_action"],
            "label":         r["label"],
            "score":         r["score"],
            "position":      r["position"],
            "m_ratio":       r["m_ratio"],
            "icm_pressure":  r["icm_pressure"],
            "icm_tax_pct":   r["icm_tax_pct"],
            "stack_bb":      r["stack_bb"],
        }
        for r in rows
    ]

    return analyze_cognitive_failures(decisions)


def get_strategic_twin_profile(user_id: int, days: int = 180) -> dict:
    """
    Sprint AR — Agrega spots de alta frequência e erro para o Personal Strategic Twin.
    Retorna taxa média de erro, spots de maior volume e spots mais custosos.
    """
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    try:
        total_row = conn.execute(_adapt("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN d.label IN ('small_mistake', 'clear_mistake') THEN 1 ELSE 0 END) as mistakes
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
        """), (user_id, cutoff)).fetchone()

        spot_rows = conn.execute(_adapt("""
            SELECT d.street, d.best_action, d.icm_pressure,
                   COUNT(*) as total,
                   SUM(CASE WHEN d.label IN ('small_mistake', 'clear_mistake') THEN 1 ELSE 0 END) as mistakes
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND t.imported_at >= ?
            GROUP BY d.street, d.best_action, d.icm_pressure
            HAVING COUNT(*) >= 3
            ORDER BY total DESC
        """), (user_id, cutoff)).fetchall()
    finally:
        conn.close()

    total_decisions = (total_row["total"] or 0) if total_row else 0
    total_mistakes  = (total_row["mistakes"] or 0) if total_row else 0

    if total_decisions < 30:
        return {"insufficient_data": True, "total_decisions": total_decisions}

    player_avg = total_mistakes / total_decisions if total_decisions > 0 else 0.0

    spots = []
    for r in spot_rows:
        err = r["mistakes"] / r["total"] if r["total"] > 0 else 0.0
        spots.append({
            "street":        r["street"] or "preflop",
            "best_action":   r["best_action"] or "fold",
            "icm_pressure":  r["icm_pressure"] or "low",
            "total":         r["total"],
            "mistakes":      r["mistakes"],
            "error_rate":    round(err, 3),
            "delta_from_avg": round(err - player_avg, 3),
        })

    high_volume_spots = spots[:5]

    costly_spots = sorted(
        [s for s in spots if s["total"] >= 5 and s["error_rate"] > player_avg + 0.10],
        key=lambda s: s["error_rate"],
        reverse=True,
    )[:5]

    return {
        "insufficient_data":    False,
        "total_decisions":       total_decisions,
        "player_avg_error_rate": round(player_avg, 3),
        "high_volume_spots":     high_volume_spots,
        "costly_spots":          costly_spots,
    }


def get_sparring_hand(user_id: int, hand_id: str = None, tournament_id: int = None,
                      exclude_hand_ids: list = None) -> dict:
    """
    Seleciona uma mão histórica do jogador para o modo Sparring, focada em
    spots 100% GTO: escolhe uma mão em que TODA decisão tem cobertura GTO
    (gto_action preenchido) — assim cada jogada do treino tem resposta e
    frequências confiáveis (preflop via ranges, postflop via solver nodes).
    Prioriza mãos com várias decisões (arco preflop→river) e randomiza para
    variedade. Não exige que o jogador tenha errado.
    exclude_hand_ids: hand_ids já vistos nesta sessão — evita repetição.
    Retorna todas as decisões da mão em ordem cronológica.
    """
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    try:
        if hand_id and tournament_id:
            target_hand_id      = hand_id
            target_tournament_id = tournament_id
        else:
            exclusions = [h for h in (exclude_hand_ids or []) if h]
            if exclusions:
                placeholders = ",".join(["?" for _ in exclusions])
                excl_clause  = f"AND d.hand_id NOT IN ({placeholders})"
                params = (user_id, *exclusions)
            else:
                excl_clause = ""
                params = (user_id,)

            # Foco em spots 100% GTO: mãos em que TODA decisão tem gto_action.
            # Prioriza mãos com várias decisões (arco preflop→river) e randomiza.
            def _pick_gto_hand(min_decisions, qparams, clause):
                # Leak-first: mãos que CONTÊM um erro GTO do jogador vêm antes
                # (treinar os próprios leaks); RANDOM() dentro do grupo garante
                # variedade — não é sempre a mesma mão de pior score.
                return conn.execute(_adapt(f"""
                    SELECT sub.hand_id, sub.tournament_id
                    FROM (
                        SELECT d.hand_id, d.tournament_id,
                               COUNT(*) AS total,
                               SUM(CASE WHEN d.gto_action IS NOT NULL AND d.gto_action != ''
                                        THEN 1 ELSE 0 END) AS covered,
                               SUM(CASE WHEN d.gto_label IN ('gto_minor_deviation','gto_critical')
                                        THEN 1 ELSE 0 END) AS mistakes
                        FROM decisions d
                        JOIN tournaments t ON t.id = d.tournament_id
                        WHERE t.user_id = ? {clause}
                        GROUP BY d.hand_id, d.tournament_id
                        HAVING total = covered AND total >= {int(min_decisions)}
                    ) sub
                    ORDER BY CASE WHEN sub.mistakes > 0 THEN 0 ELSE 1 END ASC, RANDOM()
                    LIMIT 1
                """), qparams).fetchone()

            best = _pick_gto_hand(2, params, excl_clause) or _pick_gto_hand(1, params, excl_clause)
            if not best and exclusions:
                # Esgotou as mãos não vistas nesta sessão — reseta as exclusões.
                best = _pick_gto_hand(2, (user_id,), "") or _pick_gto_hand(1, (user_id,), "")

            if not best:
                return {"insufficient_data": True}

            target_hand_id       = best["hand_id"]
            target_tournament_id = best["tournament_id"]

        rows = [dict(_r) for _r in conn.execute(_adapt("""
            SELECT d.id, d.hand_id, d.street, d.hero_cards, d.board,
                   d.action_taken, d.best_action, d.label, d.score,
                   d.m_ratio, d.icm_pressure, d.stack_bb, d.position,
                   d.num_players, d.pot_size, d.facing_bet, d.is_3bet,
                   d.gto_label, d.gto_action,
                   t.tournament_name, t.id AS tournament_id
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND d.hand_id = ? AND d.tournament_id = ?
            ORDER BY d.id
        """), (user_id, target_hand_id, target_tournament_id)).fetchall()]
    finally:
        conn.close()

    if not rows:
        return {"insufficient_data": True}

    gto_mistakes = [r for r in rows if r.get("gto_label") in ("gto_minor_deviation", "gto_critical")
                    and r.get("gto_action")]
    primary_id = (
        max(gto_mistakes, key=lambda r: r["score"])["id"] if gto_mistakes else rows[0]["id"]
    )

    steps = []
    for i, r in enumerate(rows):
        best = r["best_action"]
        # Guard: BB pode check grátis — fold impossível sem aposta. Outras posições: fold correto (não abrem).
        if float(r["facing_bet"] or 0) == 0 and best == "fold" and r.get("position") == "BB":
            best = "check"
        gto_lbl = r.get("gto_label") or ""
        gto_act = r.get("gto_action") or ""
        # GTO sobrescreve best_action quando disponível e confiável
        if gto_act and gto_lbl not in ("wizard_pending", ""):
            best = gto_act
        steps.append({
            "step_index":   i,
            "decision_id":  r["id"],
            "street":       r["street"],
            "hero_cards":   r["hero_cards"],
            "board":        r["board"] or "",
            "action_taken": r["action_taken"],
            "best_action":  best,
            "gto_label":    gto_lbl or None,
            "gto_action":   gto_act or None,
            "label":        r["label"],
            "score":        r["score"],
            "m_ratio":      r["m_ratio"],
            "icm_pressure": r["icm_pressure"],
            "stack_bb":     r["stack_bb"],
            "position":     r["position"],
            "num_players":  r["num_players"],
            "pot_size":     r["pot_size"],
            "facing_bet":   r["facing_bet"],
            "is_3bet":      bool(r["is_3bet"]),
        })

    return {
        "insufficient_data":    False,
        "hand_id":               rows[0]["hand_id"],
        "tournament_id":         rows[0]["tournament_id"],
        "tournament_name":       rows[0]["tournament_name"],
        "primary_decision_id":   primary_id,
        "steps":                 steps,
        "total_steps":           len(steps),
    }


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


# ── SEC-01: convites single-use do coach ──────────────────────────────────────

def generate_single_use_invite_code() -> str:
    """Código de convite de USO ÚNICO (distinto da chave permanente COACH-XXXXXX).
    Alta entropia (resgate exige acerto exato; protege contra brute-force)."""
    import re as _re
    raw = _re.sub(r'[^A-Z0-9]', '', secrets.token_urlsafe(9).upper())[:12]
    return f"INV-{raw}"


def _now_str() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def create_coach_invite(coach_id: int, expires_days: int = 30, label: Optional[str] = None) -> dict:
    """Gera um convite single-use ativo p/ o coach. Validade padrão 30d (0 = sem expirar)."""
    import datetime
    conn = get_conn()
    try:
        while True:
            code = generate_single_use_invite_code()
            if not conn.execute(_adapt("SELECT 1 FROM coach_invites WHERE code=?"), (code,)).fetchone():
                break
        exp = None
        if expires_days and expires_days > 0:
            exp = (datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(_adapt(
            "INSERT INTO coach_invites (coach_id, code, status, expires_at, label) VALUES (?,?,?,?,?)"),
            (coach_id, code, 'active', exp, label))
        conn.commit()
        return dict(conn.execute(_adapt("SELECT * FROM coach_invites WHERE code=?"), (code,)).fetchone())
    finally:
        conn.close()


def list_coach_invites(coach_id: int) -> list:
    """Convites do coach. Deriva 'expired' on-read (active com expires_at no passado)."""
    now = _now_str()
    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT ci.*, u.username AS used_by_username
            FROM coach_invites ci LEFT JOIN users u ON u.id = ci.used_by
            WHERE ci.coach_id = ? ORDER BY ci.created_at DESC
        """), (coach_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d['status'] == 'active' and d.get('expires_at') and str(d['expires_at']) < now:
                d['status'] = 'expired'
            out.append(d)
        return out
    finally:
        conn.close()


def revoke_coach_invite(coach_id: int, invite_id: int) -> bool:
    """Revoga um convite ATIVO do próprio coach. Retorna True se algo mudou."""
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "UPDATE coach_invites SET status='revoked' WHERE id=? AND coach_id=? AND status='active'"),
            (invite_id, coach_id))
        conn.commit()
        return (cur.rowcount or 0) > 0
    finally:
        conn.close()


def redeem_coach_invite(student_id: int, code: str) -> dict:
    """Resgata um convite single-use → vincula o aluno ao coach. Transacional (uso único
    garantido pelo UPDATE ... WHERE status='active'). Reusa o guard de max_students."""
    code = (code or '').strip().upper()
    conn = get_conn()
    try:
        inv = conn.execute(_adapt(
            "SELECT id, coach_id, status, expires_at FROM coach_invites WHERE code=?"), (code,)).fetchone()
        if not inv:
            return {'ok': False, 'error': 'Convite inválido'}
        inv = dict(inv)
        if inv['status'] == 'redeemed':
            return {'ok': False, 'error': 'Convite já utilizado'}
        if inv['status'] == 'revoked':
            return {'ok': False, 'error': 'Convite revogado'}
        if inv.get('expires_at') and str(inv['expires_at']) < _now_str():
            return {'ok': False, 'error': 'Convite expirado'}
        if inv['coach_id'] == student_id:
            return {'ok': False, 'error': 'Você não pode usar seu próprio convite'}
        # guard de limite de alunos (mesma regra do link por chave)
        prof = conn.execute(_adapt("SELECT max_students FROM coach_profiles WHERE user_id=?"),
                            (inv['coach_id'],)).fetchone()
        max_s = (prof['max_students'] if prof else 5) or 5
        cur = conn.execute(_adapt("SELECT COUNT(*) AS n FROM users WHERE coach_id=?"),
                           (inv['coach_id'],)).fetchone()['n']
        if cur >= max_s:
            return {'ok': False, 'error': f'Coach atingiu o limite de {max_s} alunos'}
        # resgate atômico: só vence quem mudar active → redeemed
        upd = conn.execute(_adapt(
            "UPDATE coach_invites SET status='redeemed', used_by=?, used_at=? WHERE id=? AND status='active'"),
            (student_id, _now_str(), inv['id']))
        if (upd.rowcount or 0) == 0:
            return {'ok': False, 'error': 'Convite já utilizado'}
        # fase 2: o vínculo entra PENDENTE — o coach precisa aprovar (comp só conta approved).
        conn.execute(_adapt(
            "UPDATE users SET coach_id=?, invited_by_key=?, invited_via_invite_id=?, link_status='pending' WHERE id=?"),
            (inv['coach_id'], code, inv['id'], student_id))
        conn.commit()
        coach = conn.execute(_adapt("SELECT id, username, email, role FROM users WHERE id=?"),
                             (inv['coach_id'],)).fetchone()
        return {'ok': True, 'coach': dict(coach), 'pending': True}
    finally:
        conn.close()


def list_pending_link_requests(coach_id: int) -> list:
    """Alunos que resgataram um convite do coach e aguardam aprovação (fase 2)."""
    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT u.id AS student_id, u.username, u.email, ci.code, ci.used_at, ci.label
            FROM users u
            LEFT JOIN coach_invites ci ON ci.id = u.invited_via_invite_id
            WHERE u.coach_id = ? AND u.link_status = 'pending'
            ORDER BY ci.used_at DESC
        """), (coach_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve_link_request(coach_id: int, student_id: int) -> bool:
    """Aprova o vínculo pendente do aluno (só do próprio coach)."""
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "UPDATE users SET link_status='approved' WHERE id=? AND coach_id=? AND link_status='pending'"),
            (student_id, coach_id))
        conn.commit()
        ok = (cur.rowcount or 0) > 0
    finally:
        conn.close()
    # COACH-02: aprovar um indicado pode fechar a meta de 15 pagantes → trava o Pro.
    if ok:
        maybe_promote_coach_earned(coach_id)
    return ok


def reject_link_request(coach_id: int, student_id: int) -> bool:
    """Rejeita o vínculo pendente: desvincula o aluno (coach_id/invite NULL, status rejected)."""
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "UPDATE users SET coach_id=NULL, invited_via_invite_id=NULL, link_status='rejected' "
            "WHERE id=? AND coach_id=? AND link_status='pending'"),
            (student_id, coach_id))
        conn.commit()
        return (cur.rowcount or 0) > 0
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
                          social_twitter: str | None = None,
                          social_instagram: str | None = None) -> dict:
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
               social_youtube, social_twitch, social_twitter, social_instagram,
               updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
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
              social_instagram  = excluded.social_instagram,
              updated_at        = datetime('now')
        """, (user_id, display_name, bio, specs_json,
              contact_email, contact_link, int(is_public), max_students,
              photo_url, experience_years, stakes, coaching_style,
              langs_json, results_json, price_per_session, price_monthly,
              int(trial_available), availability,
              social_youtube, social_twitch, social_twitter, social_instagram))
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
                   (SELECT ROUND(AVG(CAST(rating AS NUMERIC)),1)
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
            SELECT ROUND(AVG(CAST(rating AS NUMERIC)), 1) as avg_rating,
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
                   (SELECT ROUND(AVG(CAST(rating AS NUMERIC)),1)
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
    Usa leak ranking GTO-first (item #9 do backlog).
    """
    gto_first = get_leak_ranking_gto_first(user_id, days=90, limit=3)
    leaks = gto_first['leaks']

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


def get_annotations_for_decisions(decision_ids: list, coach_id: Optional[int] = None) -> list:
    """Retorna anotações para um conjunto de decision_ids (usado pelo replayer).
    `coach_id` opcional: quando o COACH revisa o aluno, filtra pelas anotações DELE
    (a constraint permite vários coaches por decisão — sem o filtro, um mapa por
    decision_id pegaria a anotação de outro coach). Visão do aluno passa None (mostra
    o feedback do(s) coach(es) dele)."""
    if not decision_ids:
        return []
    conn = get_conn()
    try:
        placeholders_str = ','.join(['?' for _ in decision_ids])
        sql = f"SELECT * FROM coach_hand_annotations WHERE decision_id IN ({placeholders_str})"
        params = list(decision_ids)
        if coach_id is not None:
            sql += " AND coach_id = ?"
            params.append(coach_id)
        rows = conn.execute(sql, tuple(params)).fetchall()
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
        # Notifica o aluno (mesma conexão). O link abre o REPLAYER direto na mão anotada
        # (/replayer?t=<tournament_id público>&h=<hand_id>), resolvido a partir do decision_id.
        try:
            link = '/dashboard'
            ref = conn.execute(_adapt(
                "SELECT t.tournament_id AS pub, d.hand_id AS hand "
                "FROM decisions d JOIN tournaments t ON t.id = d.tournament_id WHERE d.id = ?"),
                (decision_id,)).fetchone()
            if ref:
                pub = ref['pub'] if isinstance(ref, dict) or hasattr(ref, 'keys') else ref[0]
                hand = ref['hand'] if isinstance(ref, dict) or hasattr(ref, 'keys') else ref[1]
                if pub and hand:
                    link = f'/replayer?t={pub}&h={hand}'
            conn.execute(
                "INSERT INTO notifications (user_id, type, payload, link) VALUES (?,?,?,?)",
                (student_id, 'coach_annotation', json.dumps({'decision_id': decision_id}), link))
        except Exception:
            pass
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

# Limites por plano. None = ilimitado (mensal). 'advanced_insights' gateia os cards de
# IA avançada (Strategic Twin, Cognitive Failures, Leak Causal Map, Career). Tetos DIÁRIOS
# do Pro (ai_chat/dia, solves/dia) entram na fase 2 (fair-use anti-abuso).
PLAN_LIMITS: dict = {
    'free':    {'tournaments': 2,   'ai_calls': 15,  'ai_coach_chat': False, 'solves': 5,    'advanced_insights': False,
                'ai_chat_per_day': 0,  'solves_per_day': None, 'max_pending_solves': 3},
    'pro':     {'tournaments': 200, 'ai_calls': 300, 'ai_coach_chat': True,  'solves': None, 'advanced_insights': True,
                'ai_chat_per_day': 50, 'solves_per_day': 20,   'max_pending_solves': 10},
    'coach':   {'tournaments': None, 'ai_calls': None, 'ai_coach_chat': True, 'solves': None, 'advanced_insights': True,
                'ai_chat_per_day': None, 'solves_per_day': None, 'max_pending_solves': None},  # interno
}


def get_quota_status(user_id: int) -> dict:
    """Retorna plano, contadores e limites do usuário."""
    conn = get_conn()
    try:
        row = _fetchone(
            conn,
            """SELECT plan, plan_source, plan_expires_at,
                      tournaments_this_month, ai_calls_this_month,
                      solves_this_month, quota_reset_at
               FROM users WHERE id = ?""",
            (user_id,),
        )
    finally:
        conn.close()

    if not row:
        return {'plan': 'free', 'tournaments_used': 0, 'ai_calls_used': 0,
                'solves_used': 0, 'limits': PLAN_LIMITS['free']}

    plan = row.get('plan') or 'free'
    # PAY-02/04: só o LEGADO-PI (plan_source NULL) expira por data. Assinantes Stripe
    # ('stripe_sub') são governados pelos webhooks (renovação automática); Pro de cortesia
    # do coach (coach_trial/earned) é governado por coach_trial_ends_at. Nesses casos,
    # plan_expires_at não derruba o plano aqui.
    expired = False
    if (plan == 'pro' and row.get('plan_source') is None
            and row.get('plan_expires_at') and row['plan_expires_at'] < _now_str()):
        plan = 'free'
        expired = True
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])
    return {
        'plan':             plan,
        'tournaments_used': row.get('tournaments_this_month') or 0,
        'ai_calls_used':    row.get('ai_calls_this_month')    or 0,
        'solves_used':      row.get('solves_this_month')      or 0,
        'limits':           limits,
        'plan_expires_at':  row.get('plan_expires_at'),
        'expired':          expired,
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
                   solves_this_month      = 0,
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


def increment_solves(user_id: int) -> None:
    """#26 — conta 1 solve on-demand no MÊS e no DIA (fase 2) do usuário."""
    conn = get_conn()
    try:
        _maybe_reset_quota(conn, user_id)
        _maybe_reset_daily_quota(conn, user_id)
        conn.execute(
            "UPDATE users SET solves_this_month = solves_this_month + 1, "
            "solves_today = solves_today + 1 WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def can_request_solve(user_id: int) -> tuple:
    """#26 — (permitido, restantes) p/ o solve on-demand. Checa cota MENSAL e teto DIÁRIO
    (fase 2 — fair-use do Pro); restantes = o menor dos dois (None = ilimitado). Reseta as
    cotas (mês e dia) antes de checar."""
    conn = get_conn()
    try:
        _maybe_reset_quota(conn, user_id)
        _maybe_reset_daily_quota(conn, user_id)
        conn.commit()
        row = _fetchone(conn, "SELECT plan, solves_this_month, solves_today FROM users WHERE id = ?", (user_id,))
    finally:
        conn.close()
    plan   = (row.get('plan') if row else None) or 'free'
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])
    m_lim  = limits.get('solves')
    d_lim  = limits.get('solves_per_day')
    m_used = (row.get('solves_this_month') if row else 0) or 0
    d_used = (row.get('solves_today') if row else 0) or 0
    rem = None
    if m_lim is not None:
        if m_used >= m_lim:
            return False, 0
        rem = m_lim - m_used
    if d_lim is not None:
        if d_used >= d_lim:
            return False, 0
        d_rem = d_lim - d_used
        rem = d_rem if rem is None else min(rem, d_rem)
    return True, rem


def _maybe_reset_daily_quota(conn, user_id: int) -> None:
    """Se o dia virou, zera os contadores DIÁRIOS (ai_chat_today, solves_today)."""
    from datetime import date
    today = date.today().isoformat()
    row = _fetchone(conn, "SELECT quota_day_reset_at FROM users WHERE id = ?", (user_id,))
    if not row:
        return
    stored = (row.get('quota_day_reset_at') or '')[:10]  # 'YYYY-MM-DD'
    if stored != today:
        conn.execute(
            "UPDATE users SET ai_chat_today = 0, solves_today = 0, quota_day_reset_at = ? WHERE id = ?",
            (today, user_id),
        )


def increment_ai_chat(user_id: int) -> None:
    """Conta 1 mensagem do AI Coach Chat no dia (fase 2 — teto diário do Pro)."""
    conn = get_conn()
    try:
        _maybe_reset_daily_quota(conn, user_id)
        conn.execute("UPDATE users SET ai_chat_today = ai_chat_today + 1 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def can_send_ai_chat(user_id: int) -> tuple:
    """(permitido, restantes) p/ AI Coach Chat no DIA. None = ilimitado (coach)."""
    conn = get_conn()
    try:
        _maybe_reset_daily_quota(conn, user_id)
        conn.commit()
        row = _fetchone(conn, "SELECT plan, ai_chat_today FROM users WHERE id = ?", (user_id,))
    finally:
        conn.close()
    plan  = (row.get('plan') if row else None) or 'free'
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS['free']).get('ai_chat_per_day')
    used  = (row.get('ai_chat_today') if row else 0) or 0
    if limit is None:
        return True, None
    return used < limit, max(0, limit - used)


def count_user_pending_solves(user_id: int) -> int:
    """Jobs de solve ainda ativos do usuário (anti-flood da fila compartilhada)."""
    conn = get_conn()
    try:
        row = _fetchone(conn,
            "SELECT COUNT(*) AS n FROM gto_hand_requests "
            "WHERE requested_by = ? AND status IN ('pending', 'solver_queued')", (user_id,))
        return (row.get('n') if row else 0) or 0
    finally:
        conn.close()


def can_enqueue_solve(user_id: int) -> tuple:
    """(permitido, pendentes, cap) — limita jobs de solve simultâneos por usuário pra um
    aluno não monopolizar a fila/VM do solver. cap None = sem limite (coach)."""
    conn = get_conn()
    try:
        row = _fetchone(conn, "SELECT plan FROM users WHERE id = ?", (user_id,))
    finally:
        conn.close()
    plan = (row.get('plan') if row else None) or 'free'
    cap  = PLAN_LIMITS.get(plan, PLAN_LIMITS['free']).get('max_pending_solves')
    if cap is None:
        return True, 0, None
    pending = count_user_pending_solves(user_id)
    return pending < cap, pending, cap


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
        # PAY-01: idempotência. Um pagamento aprovado é gravado por DOIS caminhos para o
        # mesmo PaymentIntent — /subscription/activate (frontend) E o webhook
        # payment_intent.succeeded — além das retentativas de webhook do Stripe. Sem dedupe,
        # cada pagamento vira 2+ linhas (receita/invoices inflados). Dedupe por
        # (gateway_id, status): se já existe, devolve a linha existente em vez de inserir.
        if gateway_id:
            existing = conn.execute(
                _adapt("SELECT id FROM payments WHERE gateway_id = ? AND status = ?"),
                (gateway_id, status),
            ).fetchone()
            if existing:
                return existing['id'] if isinstance(existing, dict) or hasattr(existing, 'keys') else existing[0]
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


# ── PAY-03: visão financeira administrativa (todos os pagamentos) ─────────────

def admin_list_payments(status: str = None, gateway: str = None, search: str = None,
                        limit: int = 100, offset: int = 0) -> dict:
    """Lista TODOS os pagamentos (admin), com filtros e o username/email do pagante.
    Retorna {payments, total}."""
    conn = get_conn()
    try:
        where, params = [], []
        if status:
            where.append("p.status = ?"); params.append(status)
        if gateway:
            where.append("p.gateway = ?"); params.append(gateway)
        if search:
            where.append("(u.username LIKE ? OR u.email LIKE ? OR p.gateway_id LIKE ?)")
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        wsql = ("WHERE " + " AND ".join(where)) if where else ""
        total = _fetchone(conn, _adapt(
            f"SELECT COUNT(*) AS n FROM payments p JOIN users u ON u.id = p.user_id {wsql}"),
            tuple(params))['n']
        rows = conn.execute(_adapt(
            f"""SELECT p.*, u.username, u.email
                FROM payments p JOIN users u ON u.id = p.user_id
                {wsql} ORDER BY p.created_at DESC LIMIT ? OFFSET ?"""),
            tuple(params) + (limit, offset)).fetchall()
        return {'payments': [dict(r) for r in rows], 'total': total}
    finally:
        conn.close()


def admin_revenue_summary() -> dict:
    """Receita consolidada p/ o admin: bruto aprovado, por gateway, MRR, ARR estimado,
    assinantes pagantes (exclui Pro de cortesia do coach), e contagem de falhas."""
    conn = get_conn()
    try:
        gross = _fetchone(conn, "SELECT COALESCE(SUM(amount_cents),0) AS c, COUNT(*) AS n "
                                "FROM payments WHERE status='approved'")
        failed = _fetchone(conn, "SELECT COUNT(*) AS n FROM payments WHERE status='failed'")['n']
        by_gateway = [dict(r) for r in conn.execute(
            "SELECT gateway, COALESCE(SUM(amount_cents),0) AS amount_cents, COUNT(*) AS n "
            "FROM payments WHERE status='approved' GROUP BY gateway ORDER BY amount_cents DESC").fetchall()]
        # MRR: assinantes pagantes ativos (exclui cortesia do coach), R$99/mês equiv.
        paying_pro = _fetchone(conn, """
            SELECT COUNT(*) AS n FROM users
            WHERE plan='pro' AND (plan_source IS NULL OR plan_source NOT IN ('coach_trial','coach_earned'))
        """)['n']
        coach_perk = _fetchone(conn, """
            SELECT COUNT(*) AS n FROM users
            WHERE plan='pro' AND plan_source IN ('coach_trial','coach_earned')
        """)['n']
        mrr = paying_pro * 9900
        return {
            'gross_cents':       int(gross['c']),
            'approved_count':    int(gross['n']),
            'failed_count':      int(failed),
            'by_gateway':        by_gateway,
            'paying_pro':        paying_pro,
            'coach_perk_pro':    coach_perk,
            'mrr_cents':         mrr,
            'arr_cents':         mrr * 12,
        }
    finally:
        conn.close()


def admin_detect_duplicate_payments() -> list:
    """Anti-fraude/saúde: pagamentos aprovados com o MESMO gateway_id em >1 linha
    (não deveria ocorrer após o fix de idempotência — sinaliza dado legado/anômalo)."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT gateway_id, COUNT(*) AS n, SUM(amount_cents) AS total_cents "
            "FROM payments WHERE status='approved' AND gateway_id IS NOT NULL "
            "GROUP BY gateway_id HAVING COUNT(*) > 1 ORDER BY n DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def admin_payout_totals() -> dict:
    """Repasses de coach: total pendente e total já pago (todos os períodos)."""
    conn = get_conn()
    try:
        pend = _fetchone(conn, "SELECT COALESCE(SUM(amount_cents),0) AS c, COUNT(*) AS n "
                               "FROM coach_payments WHERE status='pending'")
        paid = _fetchone(conn, "SELECT COALESCE(SUM(amount_cents),0) AS c, COUNT(*) AS n "
                               "FROM coach_payments WHERE status='paid'")
        return {
            'pending_cents':  int(pend['c']), 'pending_count':  int(pend['n']),
            'paid_cents':     int(paid['c']), 'paid_count':     int(paid['n']),
        }
    finally:
        conn.close()


def update_user_plan(user_id: int, plan: str, subscription_id: str | None = None,
                     plan_expires_at: str | None = None) -> None:
    """PAY-02: `plan_expires_at` define a vigência (mensal +30d / anual +365d).
    NULL = sem expiração (downgrade p/ free, ou pagantes legados grandfathered)."""
    conn = get_conn()
    try:
        conn.execute(
            _adapt("UPDATE users SET plan = ?, mp_subscription_id = ?, plan_expires_at = ? WHERE id = ?"),
            (plan, subscription_id, plan_expires_at, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def link_subscription_id(user_id: int, sub_id: str) -> None:
    """PAY-04: vincula a Subscription ao usuário no checkout (sem mudar o plano) —
    permite que os webhooks resolvam o usuário por mp_subscription_id."""
    conn = get_conn()
    try:
        conn.execute(_adapt("UPDATE users SET mp_subscription_id = ? WHERE id = ?"), (sub_id, user_id))
        conn.commit()
    finally:
        conn.close()


def apply_stripe_subscription(user_id: int, status: str, plan_expires_at: Optional[str],
                              sub_id: Optional[str]) -> str:
    """PAY-04: aplica o estado de uma Subscription do Stripe ao plano do usuário.
    Fonte da verdade da recorrência = status da assinatura (não plan_expires_at manual).
      active/trialing → pro (plan_source='stripe_sub', vigência = current_period_end)
      canceled/unpaid/incomplete_expired → free
      past_due → mantém (Stripe está em retry/dunning) — não mexe
    Retorna a ação tomada ('activated' | 'downgraded' | 'kept')."""
    conn = get_conn()
    try:
        if status in ('active', 'trialing'):
            conn.execute(_adapt(
                "UPDATE users SET plan='pro', plan_source='stripe_sub', "
                "mp_subscription_id=?, plan_expires_at=? WHERE id=?"),
                (sub_id, plan_expires_at, user_id))
            conn.commit()
            return 'activated'
        if status in ('canceled', 'unpaid', 'incomplete_expired'):
            conn.execute(_adapt(
                "UPDATE users SET plan='free', plan_source=NULL, mp_subscription_id=NULL, "
                "plan_expires_at=NULL WHERE id=?"),
                (user_id,))
            conn.commit()
            return 'downgraded'
        return 'kept'   # past_due / incomplete → Stripe ainda resolvendo
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

# COACH-02: Pro de cortesia do coach
COACH_TRIAL_DAYS  = 90    # 3 meses de Pro ao ser aprovado
COACH_PRO_TARGET  = 15    # indicados pagantes p/ manter o Pro após o trial
# Origens de plano que são "perk" do coach (NÃO contam como receita/MRR):
COACH_PERK_SOURCES = ('coach_trial', 'coach_earned')


def get_coach_paying_referred_count(coach_id: int) -> int:
    """COACH-02: nº de indicados PAGANTES do coach — a métrica da meta dos 15.
    Indicado (invited_via_invite_id) + aprovado (link_status) + assinante (plan='pro').
    NÃO exige import em 30d (isso é a régua da comissão em dinheiro, não da meta)."""
    conn = get_conn()
    try:
        return _fetchone(conn, _adapt(
            "SELECT COUNT(*) AS n FROM users WHERE coach_id = ? "
            "AND invited_via_invite_id IS NOT NULL AND link_status = 'approved' AND plan = 'pro'"),
            (coach_id,))['n']
    finally:
        conn.close()


def maybe_promote_coach_earned(coach_id: int) -> bool:
    """COACH-02: se o coach está em trial/earned e atingiu a meta de indicados pagantes,
    trava o Pro como 'coach_earned' (permanente). Idempotente. Retorna True se promoveu."""
    if get_coach_paying_referred_count(coach_id) < COACH_PRO_TARGET:
        return False
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "UPDATE users SET plan = 'pro', plan_source = 'coach_earned' "
            "WHERE id = ? AND role = 'coach' AND plan_source IN ('coach_trial', 'coach_earned') "
            "AND plan_source != 'coach_earned'"),
            (coach_id,))
        conn.commit()
        return (cur.rowcount or 0) > 0
    finally:
        conn.close()


def expire_coach_trials() -> dict:
    """COACH-02 (job diário): para cada coach com trial VENCIDO, decide pelo destino.
    ≥15 indicados pagantes → 'coach_earned' (mantém Pro); senão → downgrade p/ Free.
    A comissão (% por aluno pagante) é independente e não é afetada."""
    conn = get_conn()
    try:
        try:
            conn.execute('PRAGMA busy_timeout=8000')
        except Exception:
            pass
        now = _now_str()
        rows = conn.execute(_adapt(
            "SELECT id FROM users WHERE role = 'coach' AND plan_source = 'coach_trial' "
            "AND coach_trial_ends_at IS NOT NULL AND coach_trial_ends_at < ?"),
            (now,)).fetchall()
        promoted, downgraded = [], []
        for r in rows:
            cid = r['id'] if isinstance(r, dict) or hasattr(r, 'keys') else r[0]
            paying = conn.execute(_adapt(
                "SELECT COUNT(*) AS n FROM users WHERE coach_id = ? "
                "AND invited_via_invite_id IS NOT NULL AND link_status = 'approved' AND plan = 'pro'"),
                (cid,)).fetchone()
            paying = paying['n'] if isinstance(paying, dict) or hasattr(paying, 'keys') else paying[0]
            if paying >= COACH_PRO_TARGET:
                conn.execute(_adapt("UPDATE users SET plan_source = 'coach_earned' WHERE id = ?"), (cid,))
                promoted.append(cid)
            else:
                conn.execute(_adapt(
                    "UPDATE users SET plan = 'free', plan_source = NULL, coach_trial_ends_at = NULL WHERE id = ?"),
                    (cid,))
                downgraded.append(cid)
        conn.commit()
        return {'promoted': promoted, 'downgraded': downgraded,
                'checked': len(rows), 'at': now}
    finally:
        conn.close()


def notify_expiring_coach_trials(days_window: int = 7) -> dict:
    """COACH-02 P3: avisa (notificação in-app) os coaches cujo trial de Pro acaba dentro de
    `days_window` dias e que ainda NÃO bateram a meta. Idempotente: 1 aviso por coach
    (não cria se já existe uma notificação 'coach_trial_ending' p/ aquele usuário)."""
    import datetime as _dt
    conn = get_conn()
    try:
        now = _dt.datetime.utcnow()
        limit = (now + _dt.timedelta(days=days_window)).strftime('%Y-%m-%d %H:%M:%S')
        now_s = now.strftime('%Y-%m-%d %H:%M:%S')
        rows = conn.execute(_adapt(
            "SELECT id, coach_trial_ends_at FROM users WHERE role='coach' AND plan_source='coach_trial' "
            "AND coach_trial_ends_at IS NOT NULL AND coach_trial_ends_at > ? AND coach_trial_ends_at <= ?"),
            (now_s, limit)).fetchall()
        notified = []
        for r in rows:
            cid = r['id'] if isinstance(r, dict) or hasattr(r, 'keys') else r[0]
            already = conn.execute(_adapt(
                "SELECT 1 FROM notifications WHERE user_id=? AND type='coach_trial_ending' LIMIT 1"),
                (cid,)).fetchone()
            if already:
                continue
            paying = conn.execute(_adapt(
                "SELECT COUNT(*) AS n FROM users WHERE coach_id=? "
                "AND invited_via_invite_id IS NOT NULL AND link_status='approved' AND plan='pro'"),
                (cid,)).fetchone()
            paying = paying['n'] if isinstance(paying, dict) or hasattr(paying, 'keys') else paying[0]
            if paying >= COACH_PRO_TARGET:
                continue  # já garantiu — não precisa avisar
            ends = r['coach_trial_ends_at'] if isinstance(r, dict) or hasattr(r, 'keys') else r[1]
            try:
                days_left = max(0, (_dt.datetime.strptime(ends, '%Y-%m-%d %H:%M:%S') - now).days)
            except (ValueError, TypeError):
                days_left = days_window
            conn.execute(_adapt(
                "INSERT INTO notifications (user_id, type, payload, link) VALUES (?,?,?,?)"),
                (cid, 'coach_trial_ending',
                 json.dumps({'days_left': days_left, 'paying': paying, 'target': COACH_PRO_TARGET}),
                 '/coach-dashboard'))
            notified.append(cid)
        conn.commit()
        return {'notified': notified, 'checked': len(rows)}
    finally:
        conn.close()


def backfill_coach_trials() -> dict:
    """COACH-02 P3: concede o trial de 3 meses aos coaches LEGADOS (aprovados antes da
    feature: role='coach' sem plan_source). Quem já tem ≥15 pagantes vira 'coach_earned'
    direto; os demais entram em trial de 90d a partir de agora. Idempotente."""
    import datetime as _dt
    conn = get_conn()
    try:
        now = _dt.datetime.utcnow()
        trial_end = (now + _dt.timedelta(days=COACH_TRIAL_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        rows = conn.execute(_adapt(
            "SELECT id FROM users WHERE role='coach' AND plan_source IS NULL")).fetchall()
        granted_trial, granted_earned = [], []
        for r in rows:
            cid = r['id'] if isinstance(r, dict) or hasattr(r, 'keys') else r[0]
            paying = conn.execute(_adapt(
                "SELECT COUNT(*) AS n FROM users WHERE coach_id=? "
                "AND invited_via_invite_id IS NOT NULL AND link_status='approved' AND plan='pro'"),
                (cid,)).fetchone()
            paying = paying['n'] if isinstance(paying, dict) or hasattr(paying, 'keys') else paying[0]
            if paying >= COACH_PRO_TARGET:
                conn.execute(_adapt(
                    "UPDATE users SET plan='pro', plan_source='coach_earned', coach_trial_ends_at=NULL WHERE id=?"),
                    (cid,))
                granted_earned.append(cid)
            else:
                conn.execute(_adapt(
                    "UPDATE users SET plan='pro', plan_source='coach_trial', coach_trial_ends_at=? WHERE id=?"),
                    (trial_end, cid))
                granted_trial.append(cid)
        conn.commit()
        return {'trial': granted_trial, 'earned': granted_earned, 'total': len(rows)}
    finally:
        conn.close()


def expire_subscriptions() -> dict:
    """PAY-02 (job diário): persiste o downgrade de assinaturas Pro com vigência vencida
    (`plan_expires_at < agora`), exceto o Pro de cortesia do coach (governado à parte).
    O get_quota_status já trata como free na leitura; este job consolida no banco
    (p/ contadores/MRR corretos). Retorna ids downgradados."""
    conn = get_conn()
    try:
        try:
            conn.execute('PRAGMA busy_timeout=8000')
        except Exception:
            pass
        now = _now_str()
        # PAY-04: só o LEGADO-PI (plan_source NULL) expira por data. Assinantes Stripe
        # (stripe_sub) e perks de coach são governados pelos seus próprios mecanismos.
        rows = conn.execute(_adapt(
            "SELECT id FROM users WHERE plan = 'pro' AND plan_expires_at IS NOT NULL "
            "AND plan_expires_at < ? AND plan_source IS NULL"),
            (now,)).fetchall()
        ids = [r['id'] if isinstance(r, dict) or hasattr(r, 'keys') else r[0] for r in rows]
        for uid in ids:
            conn.execute(_adapt(
                "UPDATE users SET plan = 'free', plan_expires_at = NULL, mp_subscription_id = NULL WHERE id = ?"),
                (uid,))
        conn.commit()
        return {'downgraded': ids, 'checked': len(ids), 'at': now}
    finally:
        conn.close()


def get_coach_trial_status(coach_id: int) -> dict:
    """COACH-02: estado do Pro de cortesia p/ o banner do cockpit."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT plan, plan_source, coach_trial_ends_at FROM users WHERE id = ?"),
            (coach_id,))
    finally:
        conn.close()
    if not row:
        return {}
    paying = get_coach_paying_referred_count(coach_id)
    source = row.get('plan_source')
    ends   = row.get('coach_trial_ends_at')
    days_left = None
    if source == 'coach_trial' and ends:
        import datetime as _dt
        try:
            delta = _dt.datetime.strptime(ends, '%Y-%m-%d %H:%M:%S') - _dt.datetime.utcnow()
            days_left = max(0, delta.days)
        except (ValueError, TypeError):
            days_left = None
    return {
        'plan':             row.get('plan') or 'free',
        'plan_source':      source,
        'trial_ends_at':    ends,
        'days_left':        days_left,
        'paying_referred':  paying,
        'target':           COACH_PRO_TARGET,
        'is_pro':           (row.get('plan') == 'pro'),
        'earned':           (source == 'coach_earned'),
        'on_trial':         (source == 'coach_trial'),
    }


def calculate_coach_payout(active_students: int) -> int:
    """Revenue share em centavos (BRL). 1-3: mensalidade zerada; 4-9: R$15/aluno; 10+: R$20/aluno."""
    if active_students >= 10: return active_students * 2000
    if active_students >= 4:  return active_students * 1500
    return 0


def coach_next_tier(active_students: int) -> Optional[dict]:
    """Próxima faixa de payout p/ o motivador do cockpit ("faltam X ativos → R$Y/aluno").
    None quando já está na faixa máxima (10+)."""
    if active_students < 4:
        return {'threshold': 4, 'rate_cents': 1500, 'needed': 4 - active_students}
    if active_students < 10:
        return {'threshold': 10, 'rate_cents': 2000, 'needed': 10 - active_students}
    return None


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
        # MRR estimado: pro users pagam R$99/mês (9900 centavos) — DEVE bater com
        # leaklab.stripe_gateway.PLAN_AMOUNTS['pro'] (99.00) e /subscription/plans (9900).
        # Antes era 4900 (R$49), subestimando o MRR pela metade. (PAY-01)
        # COACH-02: exclui o Pro de CORTESIA do coach (coach_trial/coach_earned) — não é receita.
        paying_pro = _fetchone(conn, """
            SELECT COUNT(*) AS n FROM users
            WHERE plan = 'pro' AND (plan_source IS NULL OR plan_source NOT IN ('coach_trial', 'coach_earned'))
        """)['n']
        mrr_cents = paying_pro * 9900
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
            filters.append("(u.username ILIKE ? OR u.email ILIKE ? OR cp.display_name ILIKE ?)") if USE_POSTGRES else \
            filters.append("(LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(COALESCE(cp.display_name,'')) LIKE ?)")
            term = f'%{search.lower()}%'
            params.extend([term, term, term])
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.extend([limit, offset])
        return _fetchall(conn, f"""
            SELECT u.id, u.username, u.email, u.role, u.plan,
                   u.created_at, u.last_login, u.suspended,
                   c.username AS coach_username,
                   cp.display_name,
                   (SELECT MAX(imported_at) FROM tournaments WHERE user_id = u.id) AS last_import,
                   (SELECT COUNT(*) FROM tournaments WHERE user_id = u.id) AS tournament_count
            FROM users u
            LEFT JOIN users c ON c.id = u.coach_id
            LEFT JOIN coach_profiles cp ON cp.user_id = u.id
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
            filters.append("u.plan = ?"); params.append(plan)
        if role:
            filters.append("u.role = ?"); params.append(role)
        if search:
            filters.append("(LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(COALESCE(cp.display_name,'')) LIKE ?)")
            term = f'%{search.lower()}%'
            params.extend([term, term, term])
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        return _fetchone(conn, f"""
            SELECT COUNT(*) AS n FROM users u
            LEFT JOIN coach_profiles cp ON cp.user_id = u.id
            {where}
        """, params)['n']
    finally:
        conn.close()


def update_user_admin(user_id: int, plan: str = None, suspended: bool = None) -> None:
    conn = get_conn()
    try:
        if plan is not None:
            conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
        if suspended is not None:
            conn.execute("UPDATE users SET suspended = ? WHERE id = ?", (bool(suspended), user_id))
        conn.commit()
    finally:
        conn.close()


def delete_user_admin(user_id: int) -> None:
    """Deletes a user and all their data (cascade). Do NOT call without admin password verification."""
    conn = get_conn()
    try:
        # remove all decisions + tournaments + related data before removing the user
        tournament_ids = [r['id'] for r in _fetchall(conn, "SELECT id FROM tournaments WHERE user_id = ?", (user_id,))]
        for tid in tournament_ids:
            conn.execute("DELETE FROM decisions WHERE tournament_id = ?", (tid,))
        if tournament_ids:
            placeholders = ",".join("?" * len(tournament_ids))
            conn.execute(f"DELETE FROM tournaments WHERE id IN ({placeholders})", tournament_ids)
        conn.execute("DELETE FROM llm_cache WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM support_tickets WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
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
            # SEC-01: comp por INDICADOS+ATIVOS — só conta aluno indicado via convite
            # single-use (invited_via_invite_id) + pro + importou nos últimos 30d.
            active = _fetchone(conn, f"""
                SELECT COUNT(DISTINCT s.id) AS n
                FROM users s
                INNER JOIN tournaments t ON t.user_id = s.id
                WHERE s.coach_id = ? AND s.plan = 'pro'
                  AND s.invited_via_invite_id IS NOT NULL
                  AND s.link_status = 'approved'
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
        # indicados = vinculados via convite single-use (SEC-01, atribuição confiável)
        referred_count = _fetchone(conn,
            "SELECT COUNT(*) AS n FROM users WHERE coach_id = ? AND invited_via_invite_id IS NOT NULL",
            (coach_id,))['n']
        # comp = INDICADOS + ATIVOS: indicado via convite + pro + importou nos últimos 30d
        active_students = _fetchone(conn, f"""
            SELECT COUNT(DISTINCT s.id) AS n
            FROM users s
            INNER JOIN tournaments t ON t.user_id = s.id
            WHERE s.coach_id = ? AND s.plan = 'pro'
              AND s.invited_via_invite_id IS NOT NULL
              AND s.link_status = 'approved'
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
            'referred_count':     referred_count,
            'amount_cents':       amount_cents,
            'next_tier':          coach_next_tier(active_students),
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


def get_leak_graph_data(user_id: int, days: int = 90, lang: str = 'pt-BR') -> dict:
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

    narrative = explain_leak_causality(graph['edges'], hero=hero or 'você', lang=lang)
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

    # 1. Top GTO leak → primary drill action (fallback to heuristic if no GTO data)
    gto_leaks  = get_gto_leak_ranking(user_id, days=90)
    heur_leaks = get_leak_roi_impact(user_id, days=90) if not gto_leaks else None
    leaks      = gto_leaks or heur_leaks or []
    if leaks:
        top   = leaks[0]
        spot  = top.get('spot', '')
        label = spot.replace('/', ' / ').replace('_', ' ')
        n     = top.get('n', 0)
        ev = top.get('ev_loss_monthly', 0) or 0
        if gto_leaks:
            desc = (f'~{ev:.1f} buy-ins/mês de impacto estimado · {n} ocorrências (90 dias)'
                    if ev > 0 else f'{n} ocorrências com desvio GTO (90 dias)')
        else:
            desc = f'Spot mais frequente — {n} ocorrências nos últimos 90 dias'
        actions.append({
            'type':        'leak',
            'priority':    'primary',
            'label':       f'Drill: {label}',
            'description': desc,
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


def reset_drill_sessions(user_id: int) -> int:
    """Deleta todo o histórico SRS de drill do usuário. Retorna quantidade deletada."""
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM drill_sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount
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
    # #15 badges de ranking — concedidos por grant_leaderboard_achievements (não pelo fluxo de XP)
    ('rank_top10',       '🏅 Top 10',             'Entrou no top 10 do ranking de alunos'),
    ('rank_top3',        '🥉 Pódio',              'Alcançou o top 3 do ranking de alunos'),
    ('rank_first',       '👑 Nº 1',               'Chegou ao 1º lugar do ranking de alunos'),
    ('rank_climber',     '📈 Crescente',          'Subiu de posição no ranking'),
    ('elo_expert',       '♠ Expert GTO',          'Atingiu a banda Expert no rating ELO'),
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
    # Notifica o destinatário (produtor de notificação). O link abre direto a conversa:
    # aluno → drawer de chat (?chat=1); coach → aba Mensagens do cockpit.
    try:
        if sender_role == 'coach':
            create_notification(student_id, 'coach_message', link='/dashboard?chat=1')
        elif sender_role == 'student':
            create_notification(coach_id, 'student_message', link='/coach-dashboard?tab=mensagens')
    except Exception:
        pass
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


def get_coach_message_count(coach_id: int, student_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM coach_messages WHERE coach_id = ? AND student_id = ?",
        (coach_id, student_id)
    ).fetchone()
    conn.close()
    return row['n'] if row else 0


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
            # Notificação na MESMA conexão (transação) — evita lock.
            try:
                conn.execute(
                    "INSERT INTO notifications (user_id, type, payload, link) VALUES (?,?,?,?)",
                    (user_id, 'achievement', json.dumps({'key': key, 'title': meta['title']}), '/dashboard'))
            except Exception:
                pass
        except Exception:
            pass
    return new_ach


def grant_leaderboard_achievements(user_id: int, rank: Optional[int] = None,
                                   rank_delta: Optional[int] = None,
                                   elo: Optional[float] = None) -> list:
    """Concede conquistas de RANKING (#15 badges), separado do fluxo de XP:
      - posição: top 10 / top 3 / nº 1 (rank = posição geral atual entre elegíveis)
      - `rank_climber`: subiu de posição (rank_delta > 0)
      - `elo_expert`: atingiu a banda Expert (ou acima) no rating ELO
    Idempotente (UNIQUE user_id+key) e notifica cada nova conquista. Retorna as novas."""
    conn = get_conn()
    try:
        existing = {r['achievement_key'] for r in conn.execute(
            "SELECT achievement_key FROM achievements WHERE user_id = ?", (user_id,)
        ).fetchall()}

        candidates: list = []
        if rank is not None:
            if rank <= 10 and 'rank_top10' not in existing: candidates.append('rank_top10')
            if rank <= 3  and 'rank_top3'  not in existing: candidates.append('rank_top3')
            if rank == 1  and 'rank_first' not in existing: candidates.append('rank_first')
        if rank_delta and rank_delta > 0 and 'rank_climber' not in existing:
            candidates.append('rank_climber')
        if elo is not None and 'elo_expert' not in existing:
            from leaklab.elo_engine import band_full
            if band_full(float(elo))[1] in ('Expert', 'Elite'):
                candidates.append('elo_expert')

        new_ach = []
        for key in candidates:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO achievements (user_id, achievement_key) VALUES (?, ?)",
                    (user_id, key)
                )
                meta = _ACH_META.get(key, {'title': key, 'desc': ''})
                new_ach.append({'key': key, 'title': meta['title'], 'desc': meta['desc']})
                try:
                    conn.execute(
                        "INSERT INTO notifications (user_id, type, payload, link) VALUES (?,?,?,?)",
                        (user_id, 'achievement', json.dumps({'key': key, 'title': meta['title']}), '/dashboard'))
                except Exception:
                    pass
            except Exception:
                pass
        conn.commit()
        return new_ach
    finally:
        conn.close()


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
        # COACH-02: ao aprovar, o coach ganha 3 meses de Pro de cortesia (trial) +
        # acesso pleno de aluno. Tem o trial para alcançar 15 indicados pagantes;
        # senão sofre downgrade (ver expire_coach_trials).
        import datetime as _dt
        trial_ends = (_dt.datetime.utcnow() + _dt.timedelta(days=COACH_TRIAL_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(_adapt(
            "UPDATE users SET role = 'coach', plan = 'pro', plan_source = 'coach_trial', "
            "coach_trial_ends_at = ? WHERE id = ?"), (trial_ends, user_id))
        # Create coach_profile if not exists
        conn.execute(
            "INSERT OR IGNORE INTO coach_profiles (user_id, display_name) VALUES (?, ?)",
            (user_id, app['username'])
        )
        conn.commit()
        app['trial_ends_at'] = trial_ends
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


# ── Onboarding ────────────────────────────────────────────────────────────────

def set_onboarding_completed(user_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            _adapt("UPDATE users SET onboarding_completed = TRUE WHERE id = ?"),
            (user_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ── Session Goals — FEAT-08 ───────────────────────────────────────────────────

def get_session_goal_for_tournament(user_id: int, tournament_id: int) -> Optional[dict]:
    """Returns the most recent session goal linked to a tournament for a user."""
    conn = get_conn()
    try:
        row = _fetchone(
            conn,
            _adapt("""SELECT id, goal_leak_spot, target_standard_pct, notes, llm_review
                      FROM session_goals
                      WHERE user_id = ? AND tournament_id = ?
                      ORDER BY created_at DESC LIMIT 1"""),
            (user_id, tournament_id),
        )
        return dict(row) if row else None
    finally:
        conn.close()


def save_session_goal_review(goal_id: int, review: str) -> None:
    """Persists the LLM-generated review text for a session goal."""
    conn = get_conn()
    try:
        conn.execute(
            _adapt("UPDATE session_goals SET llm_review = ? WHERE id = ?"),
            (review, goal_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── GTO Integration ───────────────────────────────────────────────────────────

def get_decision_spot(decision_id: int) -> Optional[dict]:
    """Retorna campos necessários para computar o spot_hash de uma decisão."""
    conn = get_conn()
    try:
        return _fetchone(conn,
            "SELECT street, position, board, hero_cards, stack_bb, action_taken, facing_bet, gto_action, gto_label FROM decisions WHERE id = ?",
            (decision_id,))
    finally:
        conn.close()


# Exploitability máxima para um nó ser considerado GTO confiável.
# production (Google VM 4vCPU/16GB): 10%  |  test (Oracle 1core/1GB): 50%
import os as _os
GTO_EXPLOITABILITY_THRESHOLD = (
    10.0 if (_os.environ.get('SOLVER_TIER') == 'production' or _os.environ.get('GTO_SOLVER_URL'))
    else 50.0
)


def get_gto_node(spot_hash: str) -> Optional[dict]:
    """
    Lookup de nó GTO pelo hash.
    Retorna nós do solver com exploitability confirmada OU nós do GTO Wizard (strategy_json obrigatório).
    """
    conn = get_conn()
    try:
        return _fetchone(conn, _adapt("""
            SELECT spot_hash, tree_hash, street, position, board, hero_hand, stack_bucket,
                   gto_action, gto_freq, ev_diff, exploitability_pct, iterations, source,
                   strategy_json, is_aggregate
            FROM gto_nodes
            WHERE spot_hash = ?
              AND (
                (exploitability_pct IS NOT NULL AND exploitability_pct <= ?)
                OR (source = 'gto_wizard' AND strategy_json IS NOT NULL)
              )
        """), (spot_hash, GTO_EXPLOITABILITY_THRESHOLD))
    finally:
        conn.close()


def get_gto_node_by_tree_hash(tree_hash: str) -> Optional[dict]:
    """Fase 1 (plano solver): lookup pela identidade da ÁRVORE — sem hero_hand e com
    board canônico por isomorfismo de naipes (compute_tree_hash). A mesma árvore já
    solvada (outra mão do hero, ou board isomorfo) é REUSADA em vez de re-solvada.
    Exige strategy_json (nó completo) e prefere a menor exploitability."""
    if not tree_hash:
        return None
    conn = get_conn()
    try:
        return _fetchone(conn, _adapt("""
            SELECT spot_hash, tree_hash, street, position, board, hero_hand, stack_bucket,
                   gto_action, gto_freq, ev_diff, exploitability_pct, iterations, source,
                   strategy_json, is_aggregate
            FROM gto_nodes
            WHERE tree_hash = ?
              AND strategy_json IS NOT NULL
              AND exploitability_pct IS NOT NULL AND exploitability_pct <= ?
            ORDER BY exploitability_pct ASC
            LIMIT 1
        """), (tree_hash, GTO_EXPLOITABILITY_THRESHOLD))
    finally:
        conn.close()


def get_gto_node_by_spot(street: str, board: list, position: str) -> Optional[dict]:
    """Lookup GTO usando street + board (ordenado) + posição do hero."""
    import hashlib
    n = {'flop': 3, 'turn': 4, 'river': 5}.get(street, 3)
    relevant = sorted(board[:n])
    key = f"{street}|{','.join(relevant)}|{position}"
    spot_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
    return get_gto_node(spot_hash)


_GTO_VALID_STREETS   = {'preflop', 'flop', 'turn', 'river'}
_GTO_VALID_POSITIONS = {'UTG', 'UTG1', 'UTG2', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}
_GTO_VALID_ACTIONS   = {'fold', 'check', 'call', 'bet', 'raise', 'jam', 'allin', 'shove', 'all-in', 'all_in'}
_gto_log = __import__('logging').getLogger('leaklab.gto')


def _log_gto_rejection(node: dict, reason: str) -> None:
    _gto_log.warning('GTO node rejected — %s | street=%s pos=%s action=%s',
                     reason, node.get('street'), node.get('position'), node.get('gto_action'))


def _parse_strategy_json_safe(raw) -> dict:
    """Desserializa strategy_json para dict {action: {frequency: float}}. Retorna {} em erro."""
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _strategy_freq_sum(strategy: dict) -> float:
    total = 0.0
    for v in strategy.values():
        if isinstance(v, dict):
            total += float(v.get('frequency', 0) or 0)
        elif isinstance(v, (int, float)):
            total += float(v)
    return total


def insert_gto_nodes(nodes: list[dict]) -> int:
    """
    Insere nós GTO com validação rigorosa.

    Regras de aceitação:
    - solver_cli: exploitability_pct obrigatório e <= GTO_EXPLOITABILITY_THRESHOLD
    - gto_wizard: strategy_json obrigatório (exploitability assumida 0%)
    - Todos: street/position/gto_action válidos; gto_freq in [0,1]
    - strategy_json: soma das frequências deve ser >= 0.10 (senão corrompido)
    - Nós preflop sem hero_hand: marcados automaticamente como is_aggregate=True
    """
    if not nodes:
        return 0

    from leaklab.gto_utils import compute_spot_hash, stack_bucket, normalize_gto_action, VALID_POSITIONS, normalize_cards

    conn = get_conn()
    try:
        count = 0
        rejected = 0
        for n in nodes:
            exploitability = n.get('exploitability_pct')
            source = n.get('source', 'solver_cli')

            # ── Validação de exploitability / source ─────────────────────────
            if exploitability is None:
                if source == 'gto_wizard' and n.get('strategy_json'):
                    pass  # aceitar — GTO Wizard é equilíbrio Nash
                else:
                    _log_gto_rejection(n, 'exploitability_pct ausente e sem strategy_json gto_wizard')
                    rejected += 1
                    continue
            elif float(exploitability) > GTO_EXPLOITABILITY_THRESHOLD:
                _log_gto_rejection(n, f'exploitability {exploitability:.1f}% > threshold {GTO_EXPLOITABILITY_THRESHOLD}%')
                rejected += 1
                continue

            # ── Sanity checks universais ──────────────────────────────────────
            street   = (n.get('street') or '').lower().strip()
            position = (n.get('position') or '').upper().strip()
            raw_action = (n.get('gto_action') or '').strip()
            gto_action = normalize_gto_action(raw_action)
            try:
                gto_freq = float(n.get('gto_freq', 0) or 0)
            except (TypeError, ValueError):
                gto_freq = 0.0

            fail_reason = None
            if street not in _GTO_VALID_STREETS:
                fail_reason = f'street inválido: {street!r}'
            elif position not in _GTO_VALID_POSITIONS:
                fail_reason = f'position inválido: {position!r}'
            elif not (0.0 <= gto_freq <= 1.0):
                fail_reason = f'gto_freq fora de [0,1]: {gto_freq}'
            elif gto_action not in _GTO_VALID_ACTIONS:
                fail_reason = f'gto_action inválido após normalização: {gto_action!r}'

            if fail_reason:
                _log_gto_rejection(n, fail_reason)
                rejected += 1
                continue

            # ── Validar strategy_json ─────────────────────────────────────────
            strategy_raw = (
                n.get('strategy_json')
                or (json.dumps(n['strategy_detail']) if n.get('strategy_detail') else None)
            )
            strategy = _parse_strategy_json_safe(strategy_raw)
            if strategy:
                # Validar ações no strategy
                invalid_acts = [a for a in strategy if normalize_gto_action(a) not in _GTO_VALID_ACTIONS]
                if invalid_acts:
                    _log_gto_rejection(n, f'strategy_json com ações inválidas: {invalid_acts}')
                    rejected += 1
                    continue
                # Validar soma das frequências (>= 0.10 para não ser corrompido)
                freq_sum = _strategy_freq_sum(strategy)
                if freq_sum < 0.10:
                    _log_gto_rejection(n, f'strategy_json freq_sum={freq_sum:.3f} < 0.10 (corrompido)')
                    rejected += 1
                    continue
                strategy_json = strategy_raw
            else:
                strategy_json = None

            # ── Detectar nó preflop agregado ──────────────────────────────────
            # normalize_cards conserta string '4dAd' e char-split ['4','A','d','d']
            # antes de hash/armazenamento (evita nós inalcançáveis pelo lookup).
            hero_hand = normalize_cards(n.get('hero_hand'))
            is_aggregate = False
            if street == 'preflop' and not hero_hand:
                is_aggregate = True
                # Estratégia agregada: freq_sum deve bater com 1.0 (é a distribuição do range)
                if strategy and not (0.85 <= _strategy_freq_sum(strategy) <= 1.15):
                    _log_gto_rejection(n, f'preflop aggregate freq_sum inválido: {_strategy_freq_sum(strategy):.2f}')
                    rejected += 1
                    continue

            # ── Computar hash ─────────────────────────────────────────────────
            spot_hash = n.get('spot_hash') or compute_spot_hash(
                street=street,
                position=position,
                board=n.get('board', []),
                hero_hand=hero_hand,
                hero_stack_bb=float(n.get('hero_stack_bb', 30.0)),
                facing_size_bb=float(n.get('facing_size_bb', 0.0)),
            )

            conn.execute(_adapt("""
                INSERT OR REPLACE INTO gto_nodes
                    (spot_hash, street, position, board, hero_hand, stack_bucket,
                     gto_action, gto_freq, ev_diff, exploitability_pct, iterations, source,
                     strategy_json, is_aggregate, tree_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (
                spot_hash,
                street,
                position,
                json.dumps(sorted(n.get('board', []))),
                json.dumps(sorted(hero_hand)),
                stack_bucket(float(n.get('hero_stack_bb', 30.0))),
                gto_action,
                gto_freq,
                float(n['ev_diff']) if n.get('ev_diff') is not None else None,
                float(exploitability) if exploitability is not None else None,
                int(n['iterations']) if n.get('iterations') else None,
                source,
                strategy_json,
                bool(is_aggregate),   # boolean nativo: SQLite aceita; Postgres exige (não int)
                n.get('tree_hash'),
            ))
            count += 1
        conn.commit()
        if rejected:
            _gto_log.info('insert_gto_nodes: %d inseridos, %d rejeitados', count, rejected)
    finally:
        conn.close()

    # Resync decisions labels for each newly saved node (best-effort, non-blocking)
    if count > 0:
        import threading
        for _n in nodes:
            try:
                _hash = _n.get('spot_hash')
                if not _hash:
                    from leaklab.gto_utils import compute_spot_hash as _csh2
                    _hash = _csh2(
                        _n['street'], _n['position'], _n.get('board', []),
                        _n.get('hero_hand', []),
                        float(_n.get('hero_stack_bb', 30.0)),
                        float(_n.get('facing_size_bb', 0.0)),
                    )
                threading.Thread(
                    target=resync_gto_labels_for_node, args=(_hash,), daemon=True
                ).start()
            except Exception:
                pass
    return count


# ── player_elo_history (Sistema ELO) ─────────────────────────────────────────

def insert_elo_snapshot(snapshot: dict) -> int:
    """Insere snapshot ELO. `snapshot` é dict de elo_engine.snapshot_to_dict."""
    conn = get_conn()
    try:
        overall = snapshot.get('overall') or {}
        by_st   = snapshot.get('by_street') or {}
        pre = by_st.get('preflop') or {}
        flp = by_st.get('flop')    or {}
        trn = by_st.get('turn')    or {}
        rvr = by_st.get('river')   or {}
        conn.execute(_adapt(
            "INSERT INTO player_elo_history "
            "(user_id, elo_overall, elo_preflop, elo_flop, elo_turn, elo_river, "
            "total_decisions, n_preflop, n_flop, n_turn, n_river) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ), (
            int(snapshot['user_id']),
            float(overall.get('elo') or 1500),
            float(pre.get('elo')) if pre else None,
            float(flp.get('elo')) if flp else None,
            float(trn.get('elo')) if trn else None,
            float(rvr.get('elo')) if rvr else None,
            int(snapshot.get('total_decisions') or 0),
            int(pre.get('n_decisions') or 0),
            int(flp.get('n_decisions') or 0),
            int(trn.get('n_decisions') or 0),
            int(rvr.get('n_decisions') or 0),
        ))
        conn.commit()
        return 1
    finally:
        conn.close()


def get_latest_elo(user_id: int) -> Optional[dict]:
    """Retorna o snapshot mais recente do user, ou None se nunca calculado."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT user_id, elo_overall, elo_preflop, elo_flop, elo_turn, elo_river, "
            "total_decisions, n_preflop, n_flop, n_turn, n_river, calculated_at "
            "FROM player_elo_history WHERE user_id = ? "
            "ORDER BY calculated_at DESC, id DESC LIMIT 1"
        ), (user_id,))
        return dict(row) if row else None
    finally:
        conn.close()


def get_elo_history(user_id: int, limit: int = 100) -> list[dict]:
    """Retorna histórico de snapshots (mais novos primeiro)."""
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT id, elo_overall, elo_preflop, elo_flop, elo_turn, elo_river, "
            "total_decisions, calculated_at "
            "FROM player_elo_history WHERE user_id = ? "
            "ORDER BY calculated_at DESC, id DESC LIMIT ?"
        ), (user_id, int(limit)))
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_last_activity_at(user_id: int) -> Optional[str]:
    """Último imported_at de torneio do user (base do decay por inatividade do ELO)."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT MAX(imported_at) AS last FROM tournaments WHERE user_id = ?"
        ), (user_id,))
        return (dict(row).get('last') if row else None)
    finally:
        conn.close()


# ── Notificações in-app (genérico — type + payload JSON, render no frontend) ──
def create_notification(user_id: int, ntype: str, payload: Optional[dict] = None,
                        link: Optional[str] = None) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "INSERT INTO notifications (user_id, type, payload, link) VALUES (?,?,?,?)"
        ), (user_id, ntype, json.dumps(payload or {}), link))
        conn.commit()
        return getattr(cur, 'lastrowid', 0) or 0
    finally:
        conn.close()


def get_notifications(user_id: int, limit: int = 30) -> list[dict]:
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT id, type, payload, link, created_at, read_at FROM notifications "
            "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?"
        ), (user_id, int(limit)))
        out = []
        for r in rows:
            d = dict(r)
            try:
                d['payload'] = json.loads(d.get('payload') or '{}')
            except Exception:
                d['payload'] = {}
            d['read'] = d.get('read_at') is not None
            out.append(d)
        return out
    finally:
        conn.close()


def get_unread_notification_count(user_id: int) -> int:
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND read_at IS NULL"
        ), (user_id,))
        return int(dict(row).get('n', 0)) if row else 0
    finally:
        conn.close()


def mark_notification_read(user_id: int, notif_id: int) -> None:
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "UPDATE notifications SET read_at = ? "
            "WHERE id = ? AND user_id = ? AND read_at IS NULL"
        ), (now, notif_id, user_id))
        conn.commit()
    finally:
        conn.close()


def mark_all_notifications_read(user_id: int) -> None:
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL"
        ), (now, user_id))
        conn.commit()
    finally:
        conn.close()


def dismiss_notification(user_id: int, notif_id: int) -> bool:
    """Remove (dispensa) uma notificação ao ser clicada — não fica acumulando na lista."""
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "DELETE FROM notifications WHERE id = ? AND user_id = ?"
        ), (notif_id, user_id))
        conn.commit()
        return (cur.rowcount or 0) > 0
    finally:
        conn.close()


def dismiss_all_notifications(user_id: int) -> int:
    """Limpa todas as notificações do usuário. Retorna quantas foram removidas."""
    conn = get_conn()
    try:
        cur = conn.execute(_adapt("DELETE FROM notifications WHERE user_id = ?"), (user_id,))
        conn.commit()
        return cur.rowcount or 0
    finally:
        conn.close()


def get_leaderboard_metrics(period_days: int = 90,
                            user_ids: Optional[list[int]] = None) -> list[dict]:
    """Agrega, por usuário, as métricas que alimentam o ranking (#15, fundação):
    mãos, torneios, drills, decisões com gto_label, aderência total e aderência
    início×recente (metades cronológicas) — tudo no período. Funções puras de
    pontuação/ranqueamento ficam em leaklab/leaderboard.py.

    `user_ids` opcional restringe o cálculo a um conjunto de usuários (usado pela
    visão do coach, que ranqueia só os próprios alunos)."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=period_days)).strftime("%Y-%m-%d %H:%M:%S")
    _ALIGNED = ("gto_correct", "gto_mixed")

    conn = get_conn()
    try:
        sql = ("SELECT DISTINCT u.id AS id, u.username AS username, "
               "       u.leaderboard_opt_in AS opt_in, u.leaderboard_handle AS handle "
               "FROM users u JOIN tournaments t ON t.user_id = u.id "
               "WHERE t.imported_at >= ?")
        params: list = [cutoff]
        if user_ids:
            ph = ",".join(["?"] * len(user_ids))
            sql += f" AND u.id IN ({ph})"
            params.extend(user_ids)
        users = _fetchall(conn, _adapt(sql), tuple(params))

        out: list[dict] = []
        for u in users:
            uid = u["id"]
            tt = _fetchone(conn, _adapt(
                "SELECT COALESCE(SUM(hands_count),0) AS hands, COUNT(*) AS tournaments "
                "FROM tournaments WHERE user_id = ? AND imported_at >= ?"
            ), (uid, cutoff))
            drills_row = _fetchone(conn, _adapt(
                "SELECT COUNT(*) AS n FROM drill_sessions WHERE user_id = ? AND drilled_at >= ?"
            ), (uid, cutoff))
            drows = _fetchall(conn, _adapt(
                "SELECT d.street AS street, d.gto_label AS gto_label, d.label AS label, "
                "d.created_at AS created_at, d.id AS id FROM decisions d "
                "JOIN tournaments t ON t.id = d.tournament_id "
                "WHERE t.user_id = ? AND t.imported_at >= ? AND d.gto_label IS NOT NULL "
                "ORDER BY t.imported_at, d.id"
            ), (uid, cutoff))
            labels = [r["gto_label"] for r in drows]

            n = len(labels)
            aligned_pct = (sum(1 for l in labels if l in _ALIGNED) / n) if n else 0.0
            half = n // 2
            early = labels[:half] or labels
            recent = labels[half:] or labels
            aligned_early = (sum(1 for l in early if l in _ALIGNED) / len(early)) if early else 0.0
            aligned_recent = (sum(1 for l in recent if l in _ALIGNED) / len(recent)) if recent else 0.0

            # ELO do jogador (dimensão A do ranking) a partir das mesmas decisões
            from leaklab.elo_engine import compute_player_elo_from_decisions, INITIAL_ELO
            player_elo = compute_player_elo_from_decisions(uid, [dict(r) for r in drows]).overall.elo if n else INITIAL_ELO

            handle = (u["handle"] or "").strip() or None
            out.append({
                "user_id":        uid,
                "username":       u["username"],
                "display_name":   u["username"],   # nome real; o endpoint público troca por handle quando opt-in
                "opt_in":         bool(u["opt_in"]),
                "handle":         handle,
                "hands":          int(tt["hands"] or 0),
                "tournaments":    int(tt["tournaments"] or 0),
                "drills":         int(drills_row["n"] or 0),
                "gto_decisions":  n,
                "player_elo":     round(player_elo, 1),
                "aligned_pct":    round(aligned_pct, 4),
                "aligned_early":  round(aligned_early, 4),
                "aligned_recent": round(aligned_recent, 4),
            })
        return out
    finally:
        conn.close()


def get_leaderboard_prefs(user_id: int) -> dict:
    """Preferências de privacidade do ranking (#15 opt-in). Default: fora do ranking
    (opt_in=False). `handle` None → exibe o username quando opta por participar."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT leaderboard_opt_in AS opt_in, leaderboard_handle AS handle "
            "FROM users WHERE id = ?"
        ), (user_id,))
        if not row:
            return {"opt_in": False, "handle": None}
        return {"opt_in": bool(row["opt_in"]), "handle": (row["handle"] or "").strip() or None}
    finally:
        conn.close()


def set_leaderboard_prefs(user_id: int, opt_in: bool, handle: Optional[str] = None) -> dict:
    """Grava opt-in/handle do ranking. `handle` é sanitizado (trim, máx 24 chars);
    vazio vira NULL (cai pro username quando opta por participar). Retorna as prefs
    efetivas. Não altera nada além da vitrine pública — o coach segue vendo os números.

    O handle é **único, case-insensitive** entre os usuários: se já estiver em uso por
    outro aluno, levanta `ValueError("handle_taken")` (o endpoint mapeia para 409)."""
    h = (handle or "").strip()
    h = h[:24] if h else None
    conn = get_conn()
    try:
        if h is not None:
            taken = _fetchone(conn, _adapt(
                "SELECT id FROM users WHERE LOWER(leaderboard_handle) = LOWER(?) AND id != ?"
            ), (h, user_id))
            if taken:
                raise ValueError("handle_taken")
        conn.execute(_adapt(
            "UPDATE users SET leaderboard_opt_in = ?, leaderboard_handle = ? WHERE id = ?"
        ), (bool(opt_in), h, user_id))
        conn.commit()
    finally:
        conn.close()
    return {"opt_in": bool(opt_in), "handle": h}


# ── Snapshots do leaderboard (#15 — histórico de posição + delta) ─────────────
# Hoje gravados SOB DEMANDA (guard ~1/dia no GET). Falta um cron real (scheduler/
# hosting) para gravar de forma confiável independente de acesso — ver backlog #15.

def save_leaderboard_snapshot(period_days: int, ranked: list[dict],
                              snapshot_at: Optional[str] = None) -> int:
    """Grava um snapshot do ranking: uma linha por jogador elegível (rank, score,
    dimensões). `ranked` = saída de `rank_leaderboard` (cada item já tem rank).
    `snapshot_at` opcional (default = agora) permite backfill/testes determinísticos.
    Retorna quantas linhas gravou."""
    import json as _json
    rows = [p for p in ranked if p.get("rank") is not None]
    conn = get_conn()
    try:
        for p in rows:
            dims = _json.dumps(p.get("dimensions") or {})
            if snapshot_at is None:
                conn.execute(_adapt(
                    "INSERT INTO leaderboard_snapshots (user_id, period_days, rank, score, dimensions_json) "
                    "VALUES (?, ?, ?, ?, ?)"
                ), (p["user_id"], period_days, int(p["rank"]), float(p.get("score") or 0.0), dims))
            else:
                conn.execute(_adapt(
                    "INSERT INTO leaderboard_snapshots (user_id, period_days, rank, score, dimensions_json, snapshot_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)"
                ), (p["user_id"], period_days, int(p["rank"]), float(p.get("score") or 0.0), dims, snapshot_at))
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def get_last_snapshot_at(period_days: int = 90):
    """Timestamp do snapshot mais recente desse período (ou None)."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT MAX(snapshot_at) AS last FROM leaderboard_snapshots WHERE period_days = ?"
        ), (period_days,))
        return row["last"] if row and row["last"] else None
    finally:
        conn.close()


def should_take_snapshot(period_days: int = 90, min_hours: float = 20.0) -> bool:
    """True se ainda não há snapshot hoje (último mais antigo que `min_hours`).
    Guard do modelo sob-demanda — evita gravar a cada acesso."""
    last = get_last_snapshot_at(period_days)
    if last is None:
        return True
    from datetime import datetime, timedelta
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "").replace("T", " ").split(".")[0])
        return (datetime.utcnow() - last_dt) >= timedelta(hours=min_hours)
    except Exception:
        return True


def take_leaderboard_snapshot(period_days: int = 90) -> int:
    """Recomputa o ranking e grava um snapshot. Pensado para um cron diário —
    hoje também usado sob demanda. Retorna o nº de linhas gravadas."""
    from leaklab.leaderboard import rank_leaderboard
    result = rank_leaderboard(get_leaderboard_metrics(period_days=period_days))
    return save_leaderboard_snapshot(period_days, result["ranked"])


def maybe_take_daily_snapshot(period_days: int = 90) -> bool:
    """Substituto local do cron: grava um snapshot só se passou ~1 dia desde o
    último. Idempotente em chamadas frequentes. Retorna True se gravou."""
    if not should_take_snapshot(period_days):
        return False
    take_leaderboard_snapshot(period_days)
    return True


def get_rank_delta(user_id: int, period_days: int = 90):
    """Variação de posição do usuário entre os 2 snapshots mais recentes.
    Retorna {current, previous, delta} (delta > 0 = subiu de posição) ou None
    quando há menos de 2 snapshots."""
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT rank, snapshot_at FROM leaderboard_snapshots "
            "WHERE user_id = ? AND period_days = ? ORDER BY snapshot_at DESC, id DESC LIMIT 2"
        ), (user_id, period_days))
        if len(rows) < 2:
            return None
        current, previous = int(rows[0]["rank"]), int(rows[1]["rank"])
        return {"current": current, "previous": previous, "delta": previous - current}
    finally:
        conn.close()


def get_hall_of_fame(period_days: int = 90, limit: int = 12) -> list[dict]:
    """Campeões mensais (#15 hall of fame): o **#1 do snapshot mais recente de cada
    mês**. Respeita privacidade — só expõe a identidade de quem está com opt-in
    (via handle/username); campeão sem opt-in aparece como anônimo. Mês mais recente
    primeiro. Vazio até a série de snapshots cobrir ≥1 mês."""
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT s.user_id AS user_id, s.score AS score, s.snapshot_at AS snapshot_at, "
            "u.username AS username, u.leaderboard_opt_in AS opt_in, "
            "u.leaderboard_handle AS handle "
            "FROM leaderboard_snapshots s JOIN users u ON u.id = s.user_id "
            "WHERE s.period_days = ? AND s.rank = 1 "
            "ORDER BY s.snapshot_at DESC"
        ), (period_days,))
    finally:
        conn.close()

    out: list[dict] = []
    seen: set = set()
    for r in rows:
        month = str(r["snapshot_at"])[:7]   # YYYY-MM
        if month in seen:
            continue                        # já temos o campeão (mais recente) desse mês
        seen.add(month)
        opted = bool(r["opt_in"])
        handle = (r["handle"] or "").strip() or None
        out.append({
            "month":     month,
            "champion":  (handle or r["username"]) if opted else None,
            "anonymous": not opted,
            "score":     round(float(r["score"] or 0.0), 1),
        })
        if len(out) >= limit:
            break
    return out


def get_coach_students_leaderboard(coach_id: int, period_days: int = 90) -> dict:
    """Ranking dos PRÓPRIOS alunos do coach (#15 coach view). Diferente do ranking
    público: ranqueia só os alunos entre si, com **nomes reais** e SEM filtro de
    opt-in (o coach sempre vê os números do aluno). Alunos sem atividade no período
    entram como inelegíveis (0 mãos). Read-only — não compete entre coaches."""
    from leaklab.leaderboard import rank_leaderboard
    from leaklab.elo_engine import INITIAL_ELO

    students = get_students(coach_id)
    ids = [s["id"] for s in students]
    if not ids:
        return {"ranked": [], "ineligible": []}

    metrics = get_leaderboard_metrics(period_days=period_days, user_ids=ids)
    present = {m["user_id"] for m in metrics}
    # alunos sem torneios no período → linha zerada (inelegíveis), para o coach ver todos
    for s in students:
        if s["id"] not in present:
            metrics.append({
                "user_id": s["id"], "username": s["username"], "display_name": s["username"],
                "opt_in": False, "handle": None,
                "hands": 0, "tournaments": 0, "drills": 0, "gto_decisions": 0,
                "player_elo": INITIAL_ELO, "aligned_pct": 0.0,
                "aligned_early": 0.0, "aligned_recent": 0.0,
            })
    return rank_leaderboard(metrics)


def get_decisions_for_elo_by_stake(user_id: int, last_n_tournaments: Optional[int] = None) -> list[dict]:
    """Como get_decisions_for_elo, mas inclui `buy_in` do torneio em cada decisão
    (para segmentar o ELO por faixa de stake — Sprint 2 #19)."""
    conn = get_conn()
    try:
        if last_n_tournaments:
            t_rows = _fetchall(conn, _adapt(
                "SELECT id FROM tournaments WHERE user_id = ? "
                "ORDER BY imported_at DESC, id DESC LIMIT ?"
            ), (user_id, int(last_n_tournaments)))
            tids = [r['id'] for r in t_rows]
            if not tids:
                return []
            ph = ",".join(["?"] * len(tids))
            rows = _fetchall(conn, _adapt(
                f"SELECT d.id, d.street, d.gto_label, d.label, d.created_at, t.buy_in "
                f"FROM decisions d INNER JOIN tournaments t ON t.id = d.tournament_id "
                f"WHERE d.tournament_id IN ({ph}) ORDER BY d.created_at ASC, d.id ASC"
            ), tuple(tids))
        else:
            rows = _fetchall(conn, _adapt(
                "SELECT d.id, d.street, d.gto_label, d.label, d.created_at, t.buy_in "
                "FROM decisions d INNER JOIN tournaments t ON t.id = d.tournament_id "
                "WHERE t.user_id = ? ORDER BY d.created_at ASC, d.id ASC"
            ), (user_id,))
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_decisions_for_elo(user_id: int, last_n_tournaments: Optional[int] = None) -> list[dict]:
    """
    Lista decisões do user ordenadas por created_at (asc) pra recalcular ELO
    sequencialmente.

    last_n_tournaments: se informado, limita aos últimos N torneios (por
    imported_at) — usado pra ELO de 'forma recente'. None = histórico todo.
    """
    conn = get_conn()
    try:
        if last_n_tournaments:
            # IDs dos últimos N torneios do user (mais recentes por imported_at)
            t_rows = _fetchall(conn, _adapt(
                "SELECT id FROM tournaments WHERE user_id = ? "
                "ORDER BY imported_at DESC, id DESC LIMIT ?"
            ), (user_id, int(last_n_tournaments)))
            tids = [r['id'] for r in t_rows]
            if not tids:
                return []
            placeholders = ",".join(["?"] * len(tids))
            rows = _fetchall(conn, _adapt(
                f"SELECT d.id, d.street, d.gto_label, d.label, d.created_at "
                f"FROM decisions d WHERE d.tournament_id IN ({placeholders}) "
                f"ORDER BY d.created_at ASC, d.id ASC"
            ), tuple(tids))
        else:
            rows = _fetchall(conn, _adapt(
                "SELECT d.id, d.street, d.gto_label, d.label, d.created_at "
                "FROM decisions d "
                "INNER JOIN tournaments t ON t.id = d.tournament_id "
                "WHERE t.user_id = ? "
                "ORDER BY d.created_at ASC, d.id ASC"
            ), (user_id,))
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_decisions_for_elo_curve(user_id: int, last_n_tournaments: Optional[int] = None) -> list[dict]:
    """
    Decisões pra curva de ELO torneio-a-torneio: inclui tournament_id, ordenadas
    por imported_at do torneio (cronológico) + ordem da decisão.

    last_n_tournaments: limita aos últimos N torneios (por imported_at).
    """
    conn = get_conn()
    try:
        if last_n_tournaments:
            t_rows = _fetchall(conn, _adapt(
                "SELECT id FROM tournaments WHERE user_id = ? "
                "ORDER BY imported_at DESC, id DESC LIMIT ?"
            ), (user_id, int(last_n_tournaments)))
            tids = [r['id'] for r in t_rows]
            if not tids:
                return []
            placeholders = ",".join(["?"] * len(tids))
            rows = _fetchall(conn, _adapt(
                f"SELECT d.id, d.tournament_id, d.street, d.gto_label, d.label "
                f"FROM decisions d "
                f"INNER JOIN tournaments t ON t.id = d.tournament_id "
                f"WHERE d.tournament_id IN ({placeholders}) "
                f"ORDER BY t.imported_at ASC, t.id ASC, d.id ASC"
            ), tuple(tids))
        else:
            rows = _fetchall(conn, _adapt(
                "SELECT d.id, d.tournament_id, d.street, d.gto_label, d.label "
                "FROM decisions d "
                "INNER JOIN tournaments t ON t.id = d.tournament_id "
                "WHERE t.user_id = ? "
                "ORDER BY t.imported_at ASC, t.id ASC, d.id ASC"
            ), (user_id,))
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_peak_elo(user_id: int) -> Optional[float]:
    """Maior elo_overall já registrado pro user (pico histórico)."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT MAX(elo_overall) AS peak FROM player_elo_history WHERE user_id = ?"
        ), (user_id,))
        return float(row['peak']) if row and row['peak'] is not None else None
    finally:
        conn.close()


# ── gw_raw_cache (multiway / squeeze responses from /gw-spot) ────────────────

def get_gw_raw_cache(cache_key: str) -> Optional[dict]:
    """Busca response cacheada do /gw-spot. Retorna dict (payload deserializado)
    com metadata, ou None se cache miss."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT cache_key, gametype, depth_used, preflop_actions, hero_position, "
            "payload_json, created_at FROM gw_raw_cache WHERE cache_key = ?"
        ), (cache_key,))
        if not row:
            return None
        try:
            payload = json.loads(row['payload_json'])
        except Exception:
            return None
        return {
            'cache_key':       row['cache_key'],
            'gametype':        row['gametype'],
            'depth_used':      row['depth_used'],
            'preflop_actions': row['preflop_actions'],
            'hero_position':   row['hero_position'],
            'payload':         payload,
            'created_at':      row['created_at'],
        }
    finally:
        conn.close()


def upsert_gw_raw_cache(
    cache_key: str,
    gametype: str,
    depth_used: float,
    preflop_actions: str,
    hero_position: Optional[str],
    payload: dict,
) -> None:
    """Insere ou atualiza entrada de cache do /gw-spot."""
    conn = get_conn()
    try:
        payload_json = json.dumps(payload, sort_keys=True)
        # UPSERT: SQLite usa INSERT OR REPLACE; Postgres usa ON CONFLICT
        if USE_POSTGRES:
            conn.execute(_adapt(
                "INSERT INTO gw_raw_cache "
                "(cache_key, gametype, depth_used, preflop_actions, hero_position, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (cache_key) DO UPDATE SET "
                "gametype=EXCLUDED.gametype, depth_used=EXCLUDED.depth_used, "
                "preflop_actions=EXCLUDED.preflop_actions, hero_position=EXCLUDED.hero_position, "
                "payload_json=EXCLUDED.payload_json, created_at=NOW()"
            ), (cache_key, gametype, float(depth_used), preflop_actions, hero_position, payload_json))
        else:
            conn.execute(_adapt(
                "INSERT OR REPLACE INTO gw_raw_cache "
                "(cache_key, gametype, depth_used, preflop_actions, hero_position, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ), (cache_key, gametype, float(depth_used), preflop_actions, hero_position, payload_json))
        conn.commit()
    finally:
        conn.close()


def get_gto_stats() -> dict:
    """Retorna estatísticas da base gto_nodes."""
    conn = get_conn()
    try:
        total_row = _fetchone(conn, "SELECT COUNT(*) AS n FROM gto_nodes")
        total = total_row['n'] if total_row else 0
        by_street = {}
        for row in _fetchall(conn, "SELECT street, COUNT(*) AS n FROM gto_nodes GROUP BY street"):
            by_street[row['street']] = row['n']
        by_position = {}
        for row in _fetchall(conn, "SELECT position, COUNT(*) AS n FROM gto_nodes GROUP BY position"):
            by_position[row['position']] = row['n']
        return {'total': total, 'by_street': by_street, 'by_position': by_position}
    finally:
        conn.close()


def get_decisions_for_spot(user_id: int, street: str | None = None,
                           position: str | None = None, days: int = 90,
                           limit: int = 8) -> list[dict]:
    """Mãos reais por trás de um leak: decisões com erro de um spot específico.

    Usado pelo gerador de plano de estudos agêntico para ancorar cada módulo em
    mãos concretas do jogador (em vez de conselho genérico). Retorna apenas
    decisões com desvio GTO ou EV perdido, da que mais sangra para a que menos.
    """
    tf, tp = _build_tournament_filter(user_id, days)
    conds  = [tf]
    params = list(tp)
    if street:
        conds.append("d.street = ?");   params.append(street)
    if position:
        conds.append("d.position = ?"); params.append(position)
    conds.append("(d.gto_label IN ('gto_critical','gto_minor_deviation') "
                 "OR COALESCE(d.ev_loss_bb, 0) > 0.05)")
    where = ' AND '.join(conds)
    params.append(limit)
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(f"""
            SELECT d.street, d.position, d.hero_cards, d.board, d.action_taken,
                   COALESCE(d.gto_action, d.best_action) AS ideal_action,
                   d.gto_label, d.ev_loss_bb, d.m_ratio, d.icm_pressure, d.stack_bb
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {where}
            ORDER BY COALESCE(d.ev_loss_bb, 0) DESC
            LIMIT ?
        """), params)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_decisions_for_hand(tournament_id: int, hand_id: str) -> list[dict]:
    """Todas as decisões de uma mesma mão, em ordem de street. Contexto para o
    deep-dive agêntico de uma decisão (entender a mão inteira, não só um street)."""
    conn = get_conn()
    try:
        rows = conn.execute(
            _adapt("SELECT * FROM decisions WHERE tournament_id = ? AND hand_id = ? ORDER BY id"),
            (tournament_id, hand_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_gto_quality_breakdown(user_id: int, since_days: int = 90, last_n: int | None = None) -> dict:
    """Distribuição de gto_label para o usuário nos últimos since_days dias (ou last_n torneios)."""
    tf, tp = _build_tournament_filter(user_id, since_days, last_n)
    conn = get_conn()
    try:
        label_rows = _fetchall(conn, _adapt(f"""
            SELECT d.gto_label, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.gto_label IS NOT NULL
            GROUP BY d.gto_label
        """), tp)

        total_row = _fetchone(conn, _adapt(f"""
            SELECT COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
        """), tp)

        counts = {r['gto_label']: r['n'] for r in label_rows}
        total_gto = sum(counts.values())
        total_dec = total_row['n'] if total_row else 0

        def pct(k: str) -> float:
            return round(counts.get(k, 0) * 100.0 / total_gto, 1) if total_gto else 0.0

        aligned = counts.get('gto_correct', 0) + counts.get('gto_mixed', 0)
        return {
            'total_with_gto': total_gto,
            'coverage_pct': round(total_gto * 100.0 / total_dec, 1) if total_dec else 0.0,
            'gto_correct_pct':  pct('gto_correct'),
            'gto_mixed_pct':    pct('gto_mixed'),
            'gto_minor_pct':    pct('gto_minor_deviation'),
            'gto_critical_pct': pct('gto_critical'),
            'aligned_pct': round(aligned * 100.0 / total_gto, 1) if total_gto else 0.0,
        }
    finally:
        conn.close()


def get_gto_alignment_by_street(user_id: int, since_days: int = 90, last_n: int | None = None) -> dict:
    """GTO alignment breakdown by street for dashboard card."""
    tf, tp = _build_tournament_filter(user_id, since_days, last_n)
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(f"""
            SELECT
                d.street,
                d.gto_label,
                COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
            GROUP BY d.street, d.gto_label
        """), tp)

        total_row = _fetchone(conn, _adapt(f"""
            SELECT COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
        """), tp)

        total_dec = total_row['n'] if total_row else 0

        # Build per-street counts
        from collections import defaultdict
        street_counts: dict = defaultdict(lambda: defaultdict(int))
        for r in rows:
            street_counts[r['street']][r['gto_label'] or ''] += r['n']

        STREETS = ['preflop', 'flop', 'turn', 'river']
        by_street = []
        for s in STREETS:
            counts = street_counts.get(s, {})
            total_with_gto = sum(v for k, v in counts.items() if k and k != '')
            total_street   = sum(counts.values())
            if total_street == 0:
                continue
            correct = counts.get('gto_correct', 0)
            mixed   = counts.get('gto_mixed', 0)
            minor   = counts.get('gto_minor_deviation', 0)
            critical = counts.get('gto_critical', 0)
            aligned  = correct + mixed
            by_street.append({
                'street':        s,
                'total':         total_street,
                'with_gto':      total_with_gto,
                'coverage_pct':  round(total_with_gto * 100.0 / total_street, 1) if total_street else 0.0,
                'aligned_pct':   round(aligned * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'correct_pct':   round(correct  * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'mixed_pct':     round(mixed    * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'minor_pct':     round(minor    * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'critical_pct':  round(critical * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
            })

        # Overall totals across all streets with gto_label
        all_gto = sum(s['with_gto'] for s in by_street)
        all_aligned = sum(
            street_counts[s].get('gto_correct', 0) + street_counts[s].get('gto_mixed', 0)
            for s in STREETS
        )
        return {
            'total_decisions': total_dec,
            'total_with_gto':  all_gto,
            'overall_coverage_pct': round(all_gto * 100.0 / total_dec, 1) if total_dec else 0.0,
            'overall_aligned_pct':  round(all_aligned * 100.0 / all_gto, 1) if all_gto else 0.0,
            'by_street': by_street,
        }
    finally:
        conn.close()


def get_gto_alignment_by_position(user_id: int, since_days: int = 90, last_n: int | None = None) -> dict:
    """GTO alignment breakdown by position for dashboard card."""
    from collections import defaultdict
    tf, tp = _build_tournament_filter(user_id, since_days, last_n)
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(f"""
            SELECT
                d.position,
                d.gto_label,
                COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.position IS NOT NULL
            GROUP BY d.position, d.gto_label
        """), tp)

        total_row = _fetchone(conn, _adapt(f"""
            SELECT COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.position IS NOT NULL
        """), tp)

        total_dec = total_row['n'] if total_row else 0

        pos_counts: dict = defaultdict(lambda: defaultdict(int))
        for r in rows:
            pos_counts[r['position']][r['gto_label'] or ''] += r['n']

        POS_ORDER = ['BTN', 'CO', 'HJ', 'MP', 'UTG+2', 'UTG+1', 'UTG', 'SB', 'BB']
        found = set(pos_counts.keys())
        ordered = [p for p in POS_ORDER if p in found] + [p for p in found if p not in POS_ORDER]

        by_position = []
        for pos in ordered:
            counts = pos_counts[pos]
            total_with_gto = sum(v for k, v in counts.items() if k and k != '')
            total_pos       = sum(counts.values())
            if total_pos == 0:
                continue
            correct  = counts.get('gto_correct', 0)
            mixed    = counts.get('gto_mixed', 0)
            minor    = counts.get('gto_minor_deviation', 0)
            critical = counts.get('gto_critical', 0)
            aligned  = correct + mixed
            by_position.append({
                'position':     pos,
                'total':        total_pos,
                'with_gto':     total_with_gto,
                'coverage_pct': round(total_with_gto * 100.0 / total_pos, 1) if total_pos else 0.0,
                'aligned_pct':  round(aligned  * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'correct_pct':  round(correct  * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'mixed_pct':    round(mixed     * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'minor_pct':    round(minor     * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
                'critical_pct': round(critical  * 100.0 / total_with_gto, 1) if total_with_gto else 0.0,
            })

        all_gto     = sum(p['with_gto'] for p in by_position)
        all_aligned = sum(
            pos_counts[p].get('gto_correct', 0) + pos_counts[p].get('gto_mixed', 0)
            for p in found
        )
        return {
            'total_decisions':      total_dec,
            'total_with_gto':       all_gto,
            'overall_coverage_pct': round(all_gto * 100.0 / total_dec, 1) if total_dec else 0.0,
            'overall_aligned_pct':  round(all_aligned * 100.0 / all_gto, 1) if all_gto else 0.0,
            'by_position':          by_position,
        }
    finally:
        conn.close()


def get_gto_alignment_matrix(user_id: int, since_days: int = 90, last_n: int | None = None) -> dict:
    """GTO alignment matrix: posição × street. Cada célula tem aligned_pct + n.

    Posições agrupadas em buckets canônicos (EP/MP/CO/BTN/SB/BB) pra evitar
    explosão de células com pouco volume. Cliente decide se mostra célula
    com baixo n (sample insuficiente) ou atenua.
    """
    from collections import defaultdict
    tf, tp = _build_tournament_filter(user_id, since_days, last_n)
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(f"""
            SELECT
                d.position,
                d.street,
                d.gto_label,
                COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE {tf}
              AND d.position IS NOT NULL
              AND d.street IS NOT NULL
            GROUP BY d.position, d.street, d.gto_label
        """), tp)

        # Bucket de posição canônico (mantém heatmap legível com 6 linhas)
        def pos_bucket(p: str) -> str:
            u = (p or '').upper()
            if u in ('UTG', 'UTG+1', 'UTG+2', 'UTG1', 'UTG2', 'LJ'): return 'EP'
            if u in ('HJ', 'MP', 'MP1', 'MP2'):                       return 'MP'
            if u in ('CO', 'BTN', 'SB', 'BB'):                        return u
            return 'OTHER'

        STREETS = ['preflop', 'flop', 'turn', 'river']
        POS_ORDER = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB']

        # cell_counts[pos][street][gto_label] = n
        cell_counts: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        for r in rows:
            pb = pos_bucket(r['position'])
            if pb == 'OTHER':
                continue
            cell_counts[pb][r['street']][r['gto_label'] or ''] += r['n']

        cells = []
        for pos in POS_ORDER:
            for street in STREETS:
                counts = cell_counts.get(pos, {}).get(street, {})
                total_street = sum(counts.values())
                with_gto = sum(v for k, v in counts.items() if k and k != '')
                if total_street == 0:
                    cells.append({
                        'position':     pos,
                        'street':       street,
                        'n':            0,
                        'with_gto':     0,
                        'aligned_pct':  None,
                        'critical_pct': None,
                    })
                    continue
                aligned  = counts.get('gto_correct', 0) + counts.get('gto_mixed', 0)
                critical = counts.get('gto_critical', 0)
                cells.append({
                    'position':     pos,
                    'street':       street,
                    'n':            total_street,
                    'with_gto':     with_gto,
                    'aligned_pct':  round(aligned  * 100.0 / with_gto, 1) if with_gto else None,
                    'critical_pct': round(critical * 100.0 / with_gto, 1) if with_gto else None,
                })

        return {
            'positions': POS_ORDER,
            'streets':   STREETS,
            'cells':     cells,
        }
    finally:
        conn.close()


def get_results_vs_gto(user_id: int, since_days: int = 90, last_n: int | None = None) -> dict:
    """Insight #5 results×GTO — 'ganhei mas joguei errado'. Decisões que foram
    ERRO de GTO (gto_critical) mas a mão foi GANHA (hero coletou o pote): o
    resultado mascara o erro de processo. Coaching: parar de validar processo
    ruim pelo resultado. Inclui headline + spots recorrentes para drill-down.
    Só conta decisões com gto_label (o resto é NULL honesto, fora do cálculo)."""
    tf, tp = _build_tournament_filter(user_id, since_days, last_n)
    conn = get_conn()
    try:
        def _count(extra: str) -> int:
            row = _fetchone(conn, _adapt(
                "SELECT COUNT(*) AS n FROM decisions d "
                "JOIN tournaments t ON t.id = d.tournament_id "
                f"WHERE {tf} {extra}"), tp)
            return row['n'] if row else 0

        gto   = "AND d.gto_label IS NOT NULL AND d.gto_label != ''"
        crit  = "AND d.gto_label = 'gto_critical'"
        won   = "AND d.hero_won_hand = 1"

        total_critical  = _count(crit)
        won_critical    = _count(crit + " " + won)
        won_evaluated   = _count(gto + " " + won)
        total_evaluated = _count(gto)
        # cobertura de resultado: quantas decisões têm o sinal won/lost capturado
        with_result     = _count("AND d.hero_won_hand IS NOT NULL")
        total_dec       = _count("")

        rows = _fetchall(conn, _adapt(
            "SELECT d.position, d.street, d.action_taken, COUNT(*) AS n "
            "FROM decisions d JOIN tournaments t ON t.id = d.tournament_id "
            f"WHERE {tf} {crit} {won} "
            "GROUP BY d.position, d.street, d.action_taken "
            "ORDER BY n DESC LIMIT 6"), tp)
        top_spots = [{
            'position': r['position'] or '?',
            'street':   r['street'],
            'action':   r['action_taken'],
            'n':        r['n'],
        } for r in rows]

        return {
            'won_critical':            won_critical,
            'total_critical':          total_critical,
            # % dos seus erros claros de GTO que ficaram "escondidos" atrás de vitórias
            'pct_critical_hidden':     round(won_critical * 100.0 / total_critical, 1) if total_critical else 0.0,
            'won_evaluated':           won_evaluated,
            # % das decisões avaliadas em mãos GANHAS que foram erro claro
            'pct_won_were_critical':   round(won_critical * 100.0 / won_evaluated, 1) if won_evaluated else 0.0,
            'total_evaluated':         total_evaluated,
            'result_coverage_pct':     round(with_result * 100.0 / total_dec, 1) if total_dec else 0.0,
            'top_spots':               top_spots,
        }
    finally:
        conn.close()


def get_missing_gto_spots(limit: int = 100) -> list[dict]:
    """Retorna spots únicos de decisions que não têm nó GTO — para o bot priorizar."""
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT d.street, d.position, d.board, d.hero_cards, d.stack_bb,
                   COUNT(*) AS frequency
            FROM decisions d
            WHERE d.street IS NOT NULL
              AND d.position IS NOT NULL
              AND d.hero_cards IS NOT NULL
              AND d.stack_bb IS NOT NULL
            GROUP BY d.street, d.position, d.board, d.hero_cards, d.stack_bb
            ORDER BY frequency DESC
            LIMIT ?
        """), (limit,))
        from leaklab.gto_utils import compute_spot_hash
        result = []
        seen_hashes: set[str] = set()
        for row in rows:
            try:
                board = json.loads(row['board']) if row['board'] else []
                hand  = row['hero_cards'].split() if row['hero_cards'] else []
                bb    = float(row['stack_bb']) if row['stack_bb'] else 30.0
                h = compute_spot_hash(
                    street=row['street'],
                    position=row['position'],
                    board=board,
                    hero_hand=hand,
                    hero_stack_bb=bb,
                )
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                # check if already populated
                exists = _fetchone(conn, "SELECT 1 FROM gto_nodes WHERE spot_hash = ?", (h,))
                if not exists:
                    result.append({
                        'spot_hash':    h,
                        'street':       row['street'],
                        'position':     row['position'],
                        'board':        board,
                        'hero_hand':    hand,
                        'stack_bb':     bb,
                        'frequency':    row['frequency'],
                    })
            except Exception:
                continue
        return result
    finally:
        conn.close()


# ── GTO Preflop Ranges ────────────────────────────────────────────────────────

def upsert_preflop_ranges(rows: list[dict]) -> int:
    """
    Insere ranges preflop verificadas por solver.
    Exige exploitability_pct — rejeita rows sem garantia de qualidade.
    """
    if not rows:
        return 0
    conn = get_conn()
    try:
        count = 0
        for r in rows:
            exploitability = r.get('exploitability_pct')
            if exploitability is None:
                continue  # nunca armazena sem garantia
            if float(exploitability) > GTO_EXPLOITABILITY_THRESHOLD:
                continue  # solve não convergiu o suficiente

            conn.execute(_adapt("""
                INSERT INTO gto_preflop_ranges
                    (position, vs_position, action_seq, hand_type, action,
                     frequency, ev_bb, exploitability_pct, stack_bucket, source, solver_config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(position, vs_position, action_seq, hand_type, action, stack_bucket)
                DO UPDATE SET
                    frequency=excluded.frequency,
                    ev_bb=excluded.ev_bb,
                    exploitability_pct=excluded.exploitability_pct,
                    source=excluded.source,
                    solver_config=excluded.solver_config
            """), (
                r['position'].upper(),
                (r.get('vs_position') or '').upper(),
                r['action_seq'],
                r['hand_type'],
                r['action'],
                float(r['frequency']),
                float(r['ev_bb']) if r.get('ev_bb') is not None else None,
                float(exploitability),
                r.get('stack_bucket', '35-60bb'),
                r.get('source', 'solver'),
                r.get('solver_config'),
            ))
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def get_preflop_gto(
    position: str,
    hand_type: str,
    action_seq: str = 'rfi',
    vs_position: str = '',
    stack_bucket: str = '35-60bb',
) -> list[dict]:
    """
    Retorna estratégia GTO preflop verificada por solver.
    Só retorna rows com exploitability_pct confirmada abaixo do threshold.
    """
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT action, frequency, ev_bb, exploitability_pct, source
            FROM gto_preflop_ranges
            WHERE position         = ?
              AND vs_position      = ?
              AND action_seq       = ?
              AND hand_type        = ?
              AND stack_bucket     = ?
              AND exploitability_pct IS NOT NULL
              AND exploitability_pct <= ?
            ORDER BY frequency DESC
        """), (
            position.upper(),
            vs_position.upper(),
            action_seq,
            hand_type,
            stack_bucket,
            GTO_EXPLOITABILITY_THRESHOLD,
        ))
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_preflop_stats() -> dict:
    """Estatísticas da base preflop — só dados verificados."""
    conn = get_conn()
    try:
        total = (_fetchone(conn, _adapt("""
            SELECT COUNT(*) AS n FROM gto_preflop_ranges
            WHERE exploitability_pct IS NOT NULL AND exploitability_pct <= ?
        """), (GTO_EXPLOITABILITY_THRESHOLD,)) or {}).get('n', 0)
        by_pos = {}
        for r in _fetchall(conn, _adapt("""
            SELECT position, COUNT(*) AS n FROM gto_preflop_ranges
            WHERE exploitability_pct IS NOT NULL AND exploitability_pct <= ?
            GROUP BY position
        """), (GTO_EXPLOITABILITY_THRESHOLD,)):
            by_pos[r['position']] = r['n']
        return {
            'total': total,
            'by_position': by_pos,
            'exploitability_threshold_pct': GTO_EXPLOITABILITY_THRESHOLD,
        }
    finally:
        conn.close()


# ── GTO Solver Queue ──────────────────────────────────────────────────────────

def _notify_solver_enqueue() -> bool:
    """Fase 2 (plano solver): acorda o worker na hora (em vez do tick de 60s)."""
    try:
        from leaklab.solver_signals import notify_solver_queue
        notify_solver_queue()
    except Exception:
        pass
    return True


def upsert_tree_strategy(tree_hash: str, board: list, actions: list, hand_table: list) -> bool:
    """Fase 3 (plano solver): grava a tabela POR MÃO de um solve (freq+EV por ação
    por combo), keyed por tree_hash. `board` = board DO SOLVE (referência p/ mapear
    mãos de spots isomorfos via iso_suit_map)."""
    if not (tree_hash and actions and hand_table):
        return False
    conn = get_conn()
    try:
        conn.execute(_adapt("""
            INSERT OR REPLACE INTO gto_tree_strategies (tree_hash, board, actions, hand_table)
            VALUES (?, ?, ?, ?)
        """), (tree_hash, json.dumps(list(board or [])),
               json.dumps(list(actions)), json.dumps(hand_table)))
        conn.commit()
        return True
    finally:
        conn.close()


def get_tree_strategy(tree_hash: str) -> Optional[dict]:
    """Fase 3: lê a tabela por mão da árvore. {board, actions, hand_table} ou None."""
    if not tree_hash:
        return None
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt(
            "SELECT board, actions, hand_table FROM gto_tree_strategies WHERE tree_hash = ?"
        ), (tree_hash,))
        if not row:
            return None
        try:
            return {
                'board':      json.loads(row['board']),
                'actions':    json.loads(row['actions']),
                'hand_table': json.loads(row['hand_table']),
            }
        except Exception:
            return None
    finally:
        conn.close()


def get_ev_summary(user_id: int) -> dict:
    """UX-1 (plano pós-solver): resumo de EV para o hero do DashboardV2.

    EV/100 = bb perdidos por 100 decisões ANALISADAS (com ev_loss_bb — solver
    hand-aware postflop + overlay preflop). Tendência: últimos 5 torneios vs os
    5 anteriores. top_leaks: padrões (street + jogou + melhor) rankeados por
    CUSTO em bb, não por contagem — o diferencial da plataforma."""
    conn = get_conn()
    try:
        tids = [r['id'] for r in _fetchall(conn, _adapt(
            "SELECT id FROM tournaments WHERE user_id = ? ORDER BY id DESC"), (user_id,))]
        if not tids:
            return {'has_data': False}

        def _ev_per_100(id_list):
            if not id_list:
                return None, 0
            ph = ','.join('?' * len(id_list))
            row = _fetchone(conn, _adapt(f"""
                SELECT COUNT(ev_loss_bb) AS with_ev, COALESCE(SUM(ev_loss_bb),0) AS loss
                FROM decisions WHERE tournament_id IN ({ph})"""), tuple(id_list))
            n = row['with_ev'] or 0
            if n < 10:
                return None, n   # amostra pequena demais pra taxa honesta
            return round(float(row['loss']) / n * 100.0, 1), n

        ev100_all,  n_all  = _ev_per_100(tids)
        ev100_cur,  _      = _ev_per_100(tids[:5])
        ev100_prev, _      = _ev_per_100(tids[5:10])

        ph_all = ','.join('?' * len(tids))
        srow = _fetchone(conn, _adapt(f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN label = 'standard' THEN 1 ELSE 0 END) AS std
            FROM decisions WHERE tournament_id IN ({ph_all})"""), tuple(tids))
        standard_pct = (round(srow['std'] / srow['total'] * 100.0, 1)
                        if srow and srow['total'] else None)

        leaks = _fetchall(conn, _adapt(f"""
            SELECT street, action_taken, best_action,
                   COUNT(*) AS cnt, SUM(ev_loss_bb) AS loss_bb
            FROM decisions
            WHERE tournament_id IN ({ph_all})
              AND ev_loss_bb IS NOT NULL AND ev_loss_bb > 0.05
              AND best_action IS NOT NULL AND best_action != ''
            GROUP BY street, action_taken, best_action
            ORDER BY loss_bb DESC LIMIT 5"""), tuple(tids))
        total_loss = sum(float(l['loss_bb'] or 0) for l in leaks) or None
        lrow = _fetchone(conn, _adapt(f"""
            SELECT COALESCE(SUM(ev_loss_bb),0) AS s FROM decisions
            WHERE tournament_id IN ({ph_all}) AND ev_loss_bb > 0.05"""), tuple(tids))
        loss_all = float(lrow['s'] or 0) if lrow else 0.0
        top_leaks = [{
            'street':       l['street'],
            'action_taken': l['action_taken'],
            'best_action':  l['best_action'],
            'count':        l['cnt'],
            'loss_bb':      round(float(l['loss_bb'] or 0), 1),
            'share_pct':    (round(float(l['loss_bb'] or 0) / loss_all * 100.0)
                             if loss_all > 0 else 0),
        } for l in leaks]

        # Série por torneio (últimos 12, ordem cronológica) — sparkline de tendência
        last12 = tids[:12]
        ph12 = ','.join('?' * len(last12))
        srows = _fetchall(conn, _adapt(f"""
            SELECT d.tournament_id AS tid, t.tournament_name AS name,
                   COUNT(d.ev_loss_bb) AS n, COALESCE(SUM(d.ev_loss_bb),0) AS loss
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.tournament_id IN ({ph12})
            GROUP BY d.tournament_id, t.tournament_name
            ORDER BY d.tournament_id ASC"""), tuple(last12))
        series = [{
            'tournament_id': r['tid'],
            'name':          (r['name'] or '')[:24],
            'ev_per_100':    (round(float(r['loss']) / r['n'] * 100.0, 1) if r['n'] >= 5 else None),
        } for r in srows]

        # Sangria por street (bb perdidos) — card "onde você sangra" do V2
        st_rows = _fetchall(conn, _adapt(f"""
            SELECT street, COUNT(*) AS cnt, COALESCE(SUM(ev_loss_bb),0) AS loss
            FROM decisions
            WHERE tournament_id IN ({ph_all}) AND ev_loss_bb > 0.05
            GROUP BY street"""), tuple(tids))
        _order = {'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}
        by_street = sorted([{
            'street':  r['street'],
            'count':   r['cnt'],
            'loss_bb': round(float(r['loss']), 1),
        } for r in st_rows], key=lambda x: _order.get(x['street'], 9))

        # Cobertura GTO por street group (% decisões com gto_label) — anéis do V2
        cov = _fetchall(conn, _adapt(f"""
            SELECT CASE WHEN street = 'preflop' THEN 'pre' ELSE 'post' END AS grp,
                   COUNT(*) AS tot,
                   SUM(CASE WHEN gto_label IS NOT NULL AND gto_label != '' THEN 1 ELSE 0 END) AS covd
            FROM decisions WHERE tournament_id IN ({ph_all})
            GROUP BY CASE WHEN street = 'preflop' THEN 'pre' ELSE 'post' END"""), tuple(tids))
        coverage = {}
        for r in cov:
            coverage[r['grp']] = round(r['covd'] / r['tot'] * 100.0, 1) if r['tot'] else None

        return {
            'has_data':          True,
            'decisions_with_ev': n_all,
            'ev_per_100':        ev100_all,
            'ev_per_100_recent': ev100_cur,
            'ev_per_100_prev':   ev100_prev,
            'standard_pct':      standard_pct,
            'total_loss_bb':     round(loss_all, 1),
            'top_leaks':         top_leaks,
            'series':            series,
            'coverage':          {'preflop_pct': coverage.get('pre'),
                                  'postflop_pct': coverage.get('post')},
            'by_street':         by_street,
        }
    finally:
        conn.close()


def enqueue_solver_spot(spot_hash: str, spot_json: str, priority: int = 5,
                        tree_hash: str = None) -> bool:
    """
    Adiciona spot à fila do solver. Retorna True se inserido ou reenfileirado.
    Spots com status done/failed/requeued são resetados para pending (permite
    reprocessamento após fixes de hash ou mudança de parâmetros).
    Spots pending/running não são alterados.

    Fase 1 (plano solver): tree_hash (identidade da árvore, sem hero_hand + board
    canônico) é computado do spot_json quando não fornecido — permite ao worker
    REUSAR nós de árvores já solvadas em vez de re-solvar (dedup).
    """
    if tree_hash is None:
        try:
            from leaklab.gto_utils import compute_tree_hash
            tree_hash = compute_tree_hash(json.loads(spot_json))
        except Exception:
            tree_hash = None
    conn = get_conn()
    try:
        existing = _fetchone(conn, _adapt("SELECT id, status FROM gto_solver_queue WHERE spot_hash = ?"), (spot_hash,))
        if existing:
            if existing['status'] in ('done', 'failed', 'requeued'):
                conn.execute(_adapt("""
                    UPDATE gto_solver_queue
                    SET status='pending', spot_json=?, priority=?, tree_hash=?
                    WHERE spot_hash=?
                """), (spot_json, priority, tree_hash, spot_hash))
                conn.commit()
                return _notify_solver_enqueue()
            return False  # pending ou running — não reprocessar
        conn.execute(_adapt("""
            INSERT INTO gto_solver_queue (spot_hash, spot_json, status, priority, tree_hash)
            VALUES (?, ?, 'pending', ?, ?)
        """), (spot_hash, spot_json, priority, tree_hash))
        conn.commit()
        return _notify_solver_enqueue()
    finally:
        conn.close()


def get_next_solver_job() -> Optional[dict]:
    """Retorna o próximo spot pendente e marca como running atomicamente."""
    conn = get_conn()
    try:
        row = _fetchone(conn, _adapt("""
            SELECT id, spot_hash, spot_json, tree_hash
            FROM gto_solver_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, requested_at ASC
            LIMIT 1
        """))
        if row:
            conn.execute(_adapt(
                "UPDATE gto_solver_queue SET status='running' WHERE spot_hash=?"
            ), (row['spot_hash'],))
            conn.commit()
        return row
    finally:
        conn.close()


def mark_solver_job_done(spot_hash: str, status: str = 'done') -> None:
    conn = get_conn()
    try:
        conn.execute(_adapt("""
            UPDATE gto_solver_queue
            SET status = ?, solved_at = datetime('now')
            WHERE spot_hash = ?
        """), (status, spot_hash))
        conn.commit()
    finally:
        conn.close()


# ── GTO Hand Requests ─────────────────────────────────────────────────────────

def request_gto_for_hand(tournament_id: int, hand_id: str, user_id: int) -> dict:
    """Enfileira análise GTO para uma mão. Retorna {'status': ..., 'id': ...}."""
    conn = get_conn()
    try:
        existing = _fetchone(conn, _adapt(
            "SELECT id, status, decisions_done FROM gto_hand_requests WHERE hand_id = ? AND requested_by = ?"
        ), (hand_id, user_id))
        if existing:
            # Se já foi processado mas não achou dados GTO (decisions_done=0 ou null),
            # apaga e re-enfileira para que o worker tente novamente com o código atual
            if existing['status'] in ('done', 'solver_queued') and not existing.get('decisions_done'):
                conn.execute(_adapt("DELETE FROM gto_hand_requests WHERE id = ?"), (existing['id'],))
                conn.commit()
            else:
                return {'inserted': False, 'id': existing['id'], 'status': existing['status']}
        conn.execute(_adapt("""
            INSERT INTO gto_hand_requests (tournament_id, hand_id, requested_by, status)
            VALUES (?, ?, ?, 'pending')
        """), (tournament_id, hand_id, user_id))
        conn.commit()
        row = _fetchone(conn, _adapt(
            "SELECT id FROM gto_hand_requests WHERE hand_id = ? AND requested_by = ?"
        ), (hand_id, user_id))
        return {'inserted': True, 'id': row['id'] if row else None, 'status': 'pending'}
    finally:
        conn.close()


def bulk_request_gto_for_hands(tournament_id: int, hand_ids: list, user_id: int) -> int:
    """
    Enfileira análise GTO para múltiplas mãos de uma vez.
    INSERT OR IGNORE — seguro de chamar múltiplas vezes (reimport não duplica).
    Retorna o número de novas entradas inseridas.
    """
    if not hand_ids:
        return 0
    conn = get_conn()
    try:
        count = 0
        for hand_id in hand_ids:
            cur = conn.execute(_adapt("""
                INSERT OR IGNORE INTO gto_hand_requests
                    (tournament_id, hand_id, requested_by, status, created_at)
                VALUES (?, ?, ?, 'pending', datetime('now'))
            """), (tournament_id, str(hand_id), user_id))
            if cur.rowcount:
                count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def get_gto_hand_request_status(hand_id: str, user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        return _fetchone(conn, _adapt("""
            SELECT id, status, decisions_found, decisions_done, error_msg, created_at, processed_at
            FROM gto_hand_requests WHERE hand_id = ? AND requested_by = ?
        """), (hand_id, user_id))
    finally:
        conn.close()


def get_pending_gto_hand_requests(limit: int = 5) -> list:
    conn = get_conn()
    try:
        return _fetchall(conn, _adapt("""
            SELECT id, tournament_id, hand_id, requested_by
            FROM gto_hand_requests
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
        """), (limit,))
    finally:
        conn.close()


def update_gto_hand_request(request_id: int, status: str,
                             decisions_found: int = None, decisions_done: int = None,
                             error_msg: str = None) -> None:
    conn = get_conn()
    try:
        conn.execute(_adapt("""
            UPDATE gto_hand_requests
            SET status = ?,
                decisions_found = COALESCE(?, decisions_found),
                decisions_done  = COALESCE(?, decisions_done),
                error_msg       = COALESCE(?, error_msg),
                processed_at    = CASE WHEN ? IN ('done', 'error') THEN datetime('now') ELSE processed_at END
            WHERE id = ?
        """), (status, decisions_found, decisions_done, error_msg, status, request_id))
        conn.commit()
    finally:
        conn.close()


def get_user_pending_gto_count(user_id: int) -> int:
    """Retorna quantos spots GTO ainda estão pendentes para o usuário.

    Conta duas fontes:
    - gto_hand_requests com status='pending' para o usuário
    - decisions com gto_label='wizard_pending' nos torneios do usuário
    """
    conn = get_conn()
    try:
        req_row = _fetchone(conn, _adapt("""
            SELECT COUNT(*) AS n FROM gto_hand_requests
            WHERE requested_by = ? AND status = 'pending'
        """), (user_id,))
        wizard_row = _fetchone(conn, _adapt("""
            SELECT COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ? AND d.gto_label = 'wizard_pending'
        """), (user_id,))
        return (req_row['n'] if req_row else 0) + (wizard_row['n'] if wizard_row else 0)
    finally:
        conn.close()


def get_gto_hand_request_queue(limit: int = 50) -> list:
    """Lista fila completa (admin view)."""
    conn = get_conn()
    try:
        return _fetchall(conn, _adapt("""
            SELECT r.id, r.tournament_id, r.hand_id, r.status,
                   r.decisions_found, r.decisions_done, r.error_msg,
                   r.created_at, r.processed_at, u.username
            FROM gto_hand_requests r
            JOIN users u ON u.id = r.requested_by
            ORDER BY r.created_at DESC
            LIMIT ?
        """), (limit,))
    finally:
        conn.close()


_LABEL_SEVERITY = {'standard': 0, 'marginal': 1, 'small_mistake': 2, 'clear_mistake': 3}


def _is_pf_zone(stack_bb: float | None, street: str | None) -> bool:
    """Push/Fold zone: stack curto (<=12bb) em preflop — decisão deve ser jam/fold."""
    try:
        return bool(street == 'preflop' and stack_bb is not None and float(stack_bb) <= 12.0)
    except (TypeError, ValueError):
        return False


def _reconcile_label(label: str, gto_label: str,
                     stack_bb: float | None = None,
                     street: str | None = None,
                     action_taken: str | None = None) -> str:
    """Reconcilia label heurístico com veredicto GTO. GTO é autoritativo para direção.

    Em push/fold zone (stack ≤ 12bb preflop), se hero não jam/fold com gto_mixed:
    demote para small_mistake — não é decisão "standard" limpar/callar em short stack.
    """
    is_pf = _is_pf_zone(stack_bb, street)
    act = (action_taken or '').lower().strip()
    pf_non_decisive = is_pf and act not in ('jam', 'shove', 'allin', 'all-in', 'fold')

    if gto_label in ('gto_correct', 'gto_mixed'):
        # PF zone com call/limp/check vs gto_mixed → não é standard
        if pf_non_decisive and gto_label == 'gto_mixed':
            return label if _LABEL_SEVERITY.get(label, 0) >= 2 else 'small_mistake'
        return 'standard'
    if gto_label == 'gto_minor_deviation':
        return label if _LABEL_SEVERITY.get(label, 0) >= 1 else 'marginal'
    if gto_label == 'gto_critical':
        return label if _LABEL_SEVERITY.get(label, 0) >= 2 else 'small_mistake'
    return label


def update_decision_gto(decision_id: int, gto_label: str, gto_action: str,
                        label: str | None = None, score: float | None = None) -> None:
    """Atualiza gto_label/gto_action. Quando label não é fornecido, reconcilia o label
    existente com o novo gto_label para manter consistência."""
    conn = get_conn()
    try:
        if label is not None and score is not None:
            conn.execute(_adapt("""
                UPDATE decisions
                SET gto_label = ?, gto_action = ?, label = ?, score = ?
                WHERE id = ?
            """), (gto_label, gto_action, label, round(score, 4), decision_id))
        else:
            # Reconcilia o label existente com o novo gto_label
            row = _fetchone(conn, _adapt(
                "SELECT label, stack_bb, street, action_taken FROM decisions WHERE id = ?"
            ), (decision_id,))
            reconciled = _reconcile_label(
                row['label'] if row else 'standard', gto_label,
                stack_bb=row['stack_bb'] if row else None,
                street=row['street'] if row else None,
                action_taken=row['action_taken'] if row else None,
            )
            conn.execute(_adapt("""
                UPDATE decisions SET gto_label = ?, gto_action = ?, label = ? WHERE id = ?
            """), (gto_label, gto_action, reconciled, decision_id))
        conn.commit()
    finally:
        conn.close()


def resync_gto_labels_for_node(spot_hash: str) -> int:
    """
    Após um nó ser inserido/atualizado em gto_nodes, reclassifica todas as decisions
    cujo spot_hash (calculado ao vivo) bate com este nó.

    Retorna o número de decisions atualizadas.
    Chamado automaticamente por insert_gto_nodes após cada REPLACE bem-sucedido.
    """
    conn = get_conn()
    try:
        node_row = _fetchone(conn, _adapt(
            "SELECT street, position, board, gto_action, gto_freq, strategy_json "
            "FROM gto_nodes WHERE spot_hash = ?"
        ), (spot_hash,))
        if not node_row:
            return 0

        try:
            board_list = json.loads(node_row['board'] or '[]')
        except Exception:
            return 0

        strategy: dict = {}
        if node_row['strategy_json']:
            try:
                raw = json.loads(node_row['strategy_json'])
                # format: {action: {frequency: float, ...}} or {action: float}
                for k, v in raw.items():
                    strategy[k] = v['frequency'] if isinstance(v, dict) else float(v)
            except Exception:
                pass
        if not strategy and node_row['gto_action']:
            strategy[node_row['gto_action']] = float(node_row['gto_freq'] or 1.0)
        if not strategy:
            return 0

        top_action = max(strategy, key=lambda k: strategy[k])

        from leaklab.gto_utils import compute_spot_hash as _csh, stack_bucket as _sb
        street   = node_row['street']
        position = node_row['position']

        # Find candidate decisions that match street + position + rough board overlap.
        # We recompute their hash and compare to spot_hash.
        # Note: no gto_label IS NOT NULL filter — this node may be arriving for the first
        # time for decisions that had no GTO coverage at upload.
        candidates = _fetchall(conn, _adapt("""
            SELECT id, tournament_id, board, hero_cards, stack_bb, facing_bet, action_taken, label
            FROM decisions
            WHERE street = ? AND position = ?
        """), (street, position))

        updated = 0
        affected_tournaments: set = set()
        for d in candidates:
            try:
                d_board = json.loads(d['board'] or '[]') if d['board'] else []
                d_hand  = json.loads(d['hero_cards'] or '[]') if d['hero_cards'] else []
                d_stack = float(d['stack_bb'] or 20.0)
                d_face  = float(d['facing_bet'] or 0.0)
                d_hash  = _csh(street, position, d_board, d_hand, d_stack, d_face)
                # Also check generic hash (no hero_hand)
                d_hash_g = _csh(street, position, d_board, [], d_stack, d_face)
                if d_hash != spot_hash and d_hash_g != spot_hash:
                    continue

                acted = (d['action_taken'] or '').lower().rstrip('s')
                acted = {'raise': 'bet', 'all-in': 'allin', 'jam': 'allin'}.get(acted, acted)
                freq  = strategy.get(acted, 0.0)

                if freq >= 0.60:
                    new_gto_label = 'gto_correct'
                elif freq >= 0.30:
                    new_gto_label = 'gto_mixed'
                elif freq >= 0.10:
                    new_gto_label = 'gto_minor_deviation'
                else:
                    new_gto_label = 'gto_critical'

                reconciled = _reconcile_label(
                    d.get('label', 'standard'), new_gto_label,
                    stack_bb=d.get('stack_bb'),
                    street=street,
                    action_taken=d.get('action_taken'),
                )
                conn.execute(_adapt(
                    "UPDATE decisions SET gto_label=?, gto_action=?, label=? WHERE id=?"
                ), (new_gto_label, top_action, reconciled, d['id']))
                updated += 1
                if d.get('tournament_id'):
                    affected_tournaments.add(d['tournament_id'])
            except Exception:
                continue

        if updated:
            conn.commit()
            # Recalculate standard_pct for all affected tournaments so dashboard KPIs
            # reflect the updated labels immediately — not just on next upload.
            for tid in affected_tournaments:
                try:
                    pct_row = _fetchone(conn, _adapt(
                        "SELECT COUNT(CASE WHEN label='standard' THEN 1 END)*100.0/COUNT(*) AS s, "
                        "AVG(score) AS a FROM decisions WHERE tournament_id=?"
                    ), (tid,))
                    if pct_row:
                        conn.execute(_adapt(
                            "UPDATE tournaments SET standard_pct=?, avg_score=? WHERE id=?"
                        ), (round(pct_row['s'] or 0, 2), round(pct_row['a'] or 0, 4), tid))
                except Exception:
                    continue
            conn.commit()
        return updated
    finally:
        conn.close()


def reconcile_tournament_labels(tournament_id: int) -> int:
    """
    Reconcilia label vs gto_label para todas as decisões de um torneio,
    e recalcula standard_pct do torneio.
    Chamado como background thread após upload e após sync de gto_labels.
    Retorna o número de decisões atualizadas.
    """
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT id, label, gto_label, stack_bb, street, action_taken
            FROM decisions
            WHERE tournament_id = ?
              AND gto_label IS NOT NULL AND gto_label != ''
              AND label IS NOT NULL AND label != ''
        """), (tournament_id,))

        changes = []
        for r in rows:
            new = _reconcile_label(
                r['label'], r['gto_label'],
                stack_bb=r['stack_bb'], street=r['street'], action_taken=r['action_taken'],
            )
            if new != r['label']:
                changes.append((new, r['id']))

        for new_label, dec_id in changes:
            conn.execute(_adapt(
                "UPDATE decisions SET label=? WHERE id=?"
            ), (new_label, dec_id))

        # Recalcula standard_pct
        pct_row = _fetchone(conn, _adapt(
            "SELECT COUNT(CASE WHEN label='standard' THEN 1 END)*100.0/COUNT(*) AS s, "
            "AVG(score) AS a FROM decisions WHERE tournament_id=?"
        ), (tournament_id,))
        if pct_row:
            conn.execute(_adapt(
                "UPDATE tournaments SET standard_pct=?, avg_score=? WHERE id=?"
            ), (round(pct_row['s'] or 0, 2), round(pct_row['a'] or 0, 4), tournament_id))

        # Stamp the tournament as reconciled — sempre, mesmo sem mudanças,
        # para que o dashboard saiba que a análise GTO ja foi aplicada.
        try:
            conn.execute(_adapt(
                "UPDATE tournaments SET labels_reconciled_at = CURRENT_TIMESTAMP WHERE id = ?"
            ), (tournament_id,))
        except Exception:
            pass

        if changes or pct_row:
            conn.commit()
        else:
            conn.commit()
        log.info(
            "reconcile_tournament_labels: tournament_id=%s changes=%d",
            tournament_id, len(changes),
        )
        return len(changes)
    except Exception as e:
        log.exception(
            "reconcile_tournament_labels FAILED tournament_id=%s err=%s",
            tournament_id, e,
        )
        return 0
    finally:
        conn.close()


# ── HUD Fase 1: perfis de comportamento de oponente ──────────────────────────────

def upsert_opponent_profile(tournament_id: int, player_name: str, profile: dict) -> None:
    """Salva/atualiza o perfil de um jogador num torneio (idempotente por
    tournament_id+player_name). `profile` é o dict do opponent_stats.finalize."""
    import json as _json
    conn = get_conn()
    try:
        conn.execute(_adapt("""
            INSERT INTO opponent_profiles
                (tournament_id, player_name, hands_seen, archetype, confidence, stats_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tournament_id, player_name) DO UPDATE SET
                hands_seen = excluded.hands_seen,
                archetype  = excluded.archetype,
                confidence = excluded.confidence,
                stats_json = excluded.stats_json
        """), (tournament_id, player_name,
               int(profile.get('hands', 0)),
               profile.get('archetype', 'unknown'),
               profile.get('confidence', 'insufficient'),
               _json.dumps(profile, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def get_opponent_profiles(tournament_id: int, min_hands: int = 0) -> list:
    """Perfis de oponentes de um torneio, ordenados por amostra (mãos vistas)."""
    import json as _json
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT player_name, hands_seen, archetype, confidence, stats_json "
            "FROM opponent_profiles WHERE tournament_id = ? AND hands_seen >= ? "
            "ORDER BY hands_seen DESC"
        ), (tournament_id, min_hands))
        return [{
            'player':     r['player_name'],
            'hands':      r['hands_seen'],
            'archetype':  r['archetype'],
            'confidence': r['confidence'],
            'stats':      _json.loads(r['stats_json'] or '{}'),
        } for r in rows]
    finally:
        conn.close()
