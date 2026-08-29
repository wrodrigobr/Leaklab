# -*- coding: utf-8 -*-
"""Ritual da sessão: o check-in antes de jogar e o debriefing depois — o laço que fecha.

── Por que existe (30/08) ───────────────────────────────────────────────────────────────────

Último item do benchmark. O concorrente pergunta e devolve zero: as respostas do check-in dele
não alimentam nada. Nós temos os insumos parados (leaks medidos, plano de estudo, EV por mão)
e faltava só a costura. E o funil mostra onde ela ataca: 86% de quem importa treina, mas só
50% voltam — o debriefing dá motivo de retorno a cada sessão jogada.

── As três decisões de desenho ──────────────────────────────────────────────────────────────

**1. O foco é a correção acionável, não o nome de um stat.** Sai do leak mais caro medido
(`get_leak_summary`): "flop quando o certo era fold", não "fold to c-bet 38%".

**2. A linha de base é SELADA no check-in.** O debriefing compara a sessão contra o histórico
DO MOMENTO DA PROMESSA — mesmo princípio do gabarito vetado do desafio: comparar contra uma
régua que se move depois é como o card que contradiz o teaching.

**3. Sem amostra não há promessa quebrada.** Foco só é sugerido com amostra mínima; debriefing
sem decisão da família na sessão diz "não apareceu spot do seu foco", nunca 0% nem 100%.

A banca ("cobre o stake?") é auto-resposta gravada: o produto NÃO conhece a banca do jogador —
perguntar é honesto, fingir que calcula não seria.
"""
from __future__ import annotations

from typing import Optional

from database.repositories import _adapt, _fetchall, _fetchone, get_leak_summary
from database.schema import get_conn

#: amostra mínima do leak para virar foco sugerido — abaixo disso a "correção" é ruído
FOCO_MIN_AMOSTRA = 5
#: rótulos que contam como erro (a mesma régua do get_leak_summary)
_ERROS = ('small_mistake', 'clear_mistake')


def _tabela(conn) -> None:
    """Bloco isolado (ver reference_pg_migration_abort_proof)."""
    try:
        conn.execute(_adapt("""
            CREATE TABLE IF NOT EXISTS session_checkins (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bankroll_ok   INTEGER,
                foco_spot     TEXT,
                base_n        INTEGER,
                base_erros    INTEGER,
                debrief_tid   INTEGER,
                debriefed_at  TIMESTAMP
            )""" if _sqlite(conn) else """
            CREATE TABLE IF NOT EXISTS session_checkins (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bankroll_ok   INTEGER,
                foco_spot     TEXT,
                base_n        INTEGER,
                base_erros    INTEGER,
                debrief_tid   INTEGER,
                debriefed_at  TIMESTAMP
            )"""))
        conn.commit()
    except Exception:                                          # noqa: BLE001
        conn.rollback()


def _sqlite(conn) -> bool:
    return 'sqlite' in type(conn).__module__.lower() or hasattr(conn, 'row_factory')


def _spot_stats(conn, user_id: int, spot: str, tournament_id: Optional[int] = None) -> dict:
    """n e erros da família `street/best_action` — no torneio dado, ou no histórico inteiro."""
    try:
        street, best = spot.split('/', 1)
    except ValueError:
        return {'n': 0, 'erros': 0}
    sql = ("SELECT COUNT(*) AS n, "
           "SUM(CASE WHEN d.label IN (?, ?) THEN 1 ELSE 0 END) AS erros "
           "FROM decisions d JOIN tournaments t ON t.id = d.tournament_id "
           "WHERE t.user_id = ? AND d.street = ? AND d.best_action = ?")
    params: list = [_ERROS[0], _ERROS[1], user_id, street, best]
    if tournament_id is not None:
        sql += " AND d.tournament_id = ?"
        params.append(tournament_id)
    r = _fetchone(conn, _adapt(sql), tuple(params))
    d = dict(r) if r else {}
    return {'n': int(d.get('n') or 0), 'erros': int(d.get('erros') or 0)}


def sugerir_foco(user_id: int) -> Optional[dict]:
    """O leak mais caro COM amostra vira o foco. `None` = sem leak medido suficiente
    (jogador novo ou sólido): o front oferece sessão livre, sem inventar correção."""
    for leak in get_leak_summary(user_id, days=90):
        if int(leak.get('n') or 0) >= FOCO_MIN_AMOSTRA:
            return {'spot': leak['spot'], 'n': int(leak['n']),
                    'avg_score': float(leak.get('avg_score') or 0)}
    return None


def abrir_checkin(user_id: int, bankroll_ok: Optional[bool], foco_spot: Optional[str]) -> dict:
    """Abre o check-in do dia, SELANDO a linha de base do foco. Um novo check-in substitui o
    anterior não-debriefado — a promessa vale para a próxima sessão, não acumula dívida."""
    conn = get_conn()
    try:
        _tabela(conn)
        base = _spot_stats(conn, user_id, foco_spot) if foco_spot else {'n': 0, 'erros': 0}
        conn.execute(_adapt(
            'DELETE FROM session_checkins WHERE user_id = ? AND debriefed_at IS NULL'),
            (user_id,))
        conn.execute(_adapt(
            'INSERT INTO session_checkins (user_id, bankroll_ok, foco_spot, base_n, base_erros) '
            'VALUES (?, ?, ?, ?, ?)'),
            (user_id, None if bankroll_ok is None else (1 if bankroll_ok else 0),
             foco_spot, base['n'], base['erros']))
        conn.commit()
        row = _fetchone(conn, _adapt(
            'SELECT id, foco_spot, base_n, base_erros FROM session_checkins '
            'WHERE user_id = ? AND debriefed_at IS NULL'), (user_id,))
        return dict(row)
    finally:
        conn.close()


def checkin_aberto(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        _tabela(conn)
        row = _fetchone(conn, _adapt(
            'SELECT id, created_at, bankroll_ok, foco_spot, base_n, base_erros '
            'FROM session_checkins WHERE user_id = ? AND debriefed_at IS NULL'), (user_id,))
        return dict(row) if row else None
    finally:
        conn.close()


def debrief(user_id: int, tournament_db_id: int) -> Optional[dict]:
    """O balanço da sessão contra a promessa. `None` se o torneio não é do usuário.

    A execução do foco compara a taxa DA SESSÃO com a linha de base SELADA no check-in.
    Sem check-in aberto, ainda devolve o balanço (mão gatilho + mãos caras) — o debriefing
    serve mesmo a quem não prometeu nada; só a parte da promessa fica de fora.
    """
    conn = get_conn()
    try:
        _tabela(conn)
        dono = _fetchone(conn, _adapt(
            'SELECT 1 AS x FROM tournaments WHERE id = ? AND user_id = ?'),
            (tournament_db_id, user_id))
        if not dono:
            return None

        out: dict = {'tournament_id': tournament_db_id}

        ck = _fetchone(conn, _adapt(
            'SELECT id, foco_spot, base_n, base_erros FROM session_checkins '
            'WHERE user_id = ? AND debriefed_at IS NULL'), (user_id,))
        if ck:
            c = dict(ck)
            spot = c.get('foco_spot')
            if spot:
                sessao = _spot_stats(conn, user_id, spot, tournament_id=tournament_db_id)
                base_n, base_err = int(c['base_n'] or 0), int(c['base_erros'] or 0)
                out['foco'] = {
                    'spot': spot,
                    'sessao': sessao,
                    # a régua da promessa, congelada no check-in
                    'base': {'n': base_n, 'erros': base_err,
                             'taxa': round(base_err / base_n, 4) if base_n else None},
                    # sem spot da família na sessão, não há promessa cumprida NEM quebrada
                    'taxa_sessao': (round(sessao['erros'] / sessao['n'], 4)
                                    if sessao['n'] else None),
                }
            out['checkin_id'] = c['id']

        # A mão gatilho e as mais caras: o custo em bb quando é confiável; senão o score.
        caras = _fetchall(conn, _adapt(
            "SELECT d.hand_id, d.street, d.action_taken, d.best_action, d.hero_cards, "
            "       d.label, d.score, d.ev_loss_bb "
            "FROM decisions d WHERE d.tournament_id = ? AND d.label IN (?, ?) "
            "ORDER BY COALESCE(d.ev_loss_bb, 0) DESC, d.score DESC LIMIT 3"),
            (tournament_db_id, _ERROS[0], _ERROS[1]))
        out['maos_caras'] = [dict(r) for r in caras]
        out['mao_gatilho'] = out['maos_caras'][0] if out['maos_caras'] else None
        return out
    finally:
        conn.close()


def fechar_checkin(user_id: int, checkin_id: int, tournament_db_id: int) -> bool:
    """Marca o check-in como debriefado (ato explícito do jogador, não efeito de leitura)."""
    conn = get_conn()
    try:
        _tabela(conn)
        cur = conn.execute(_adapt(
            'UPDATE session_checkins SET debriefed_at = CURRENT_TIMESTAMP, debrief_tid = ? '
            'WHERE id = ? AND user_id = ? AND debriefed_at IS NULL'),
            (tournament_db_id, checkin_id, user_id))
        conn.commit()
        return bool(getattr(cur, 'rowcount', 0))
    finally:
        conn.close()
