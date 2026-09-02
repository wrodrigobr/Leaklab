# -*- coding: utf-8 -*-
"""Fila de análise GTO por plano: o upload SEMPRE entra; a análise espera a vez.

── Por que existe (02/09, decisão do dono) ─────────────────────────────────────────────────

Primeiro desenho era barrar o upload do free enquanto houvesse análise em andamento — e barrar
upload ataca a ativação, que é o gargalo medido do funil (28% importam). O dono corrigiu o
desenho: *"permitir ele fazer o upload dos 30 de uma vez, porém com 3 análises simultâneas...
quando cai um dos 3, entra o próximo. A fila é inteligência nossa."*

Então: o jogador free sobe quantos torneios quiser (teto mensal continua valendo); o motor
local analisa tudo na hora (cartas, posições, vereditos de carta). O que espera a vez é a
CAMADA GTO (solver): no free, 3 torneios por vez; Pro não espera.

── Como funciona ───────────────────────────────────────────────────────────────────────────

- No upload, `deve_esperar(user_id)` conta os torneios do usuário com análise EM ANDAMENTO:
  spots na fila ativa do solver (mesmo sinal do selo "Analisando") OU gto_hand_requests
  não-terminal — o segundo sinal cobre a janela entre promover e os spots entrarem na fila,
  sem ele o promotor via vaga falsa e soltava mais de 3.
- Cheio → o torneio entra em `gto_analysis_waitlist` em vez de disparar a análise GTO.
- `promover_aguardando()` roda a cada tick do consumer (barato com a lista vazia): para cada
  usuário na espera, promove os mais antigos até encher as vagas do plano. Promover = criar os
  gto_hand_requests a partir das DECISÕES gravadas (o worker de mãos monta e enfileira os
  spots dele — mesmo caminho do botão do replay).
- Stale de 24h nos dois sinais: solver caído não prende ninguém para sempre.

O limite mora em PLAN_LIMITS['<plano>']['simultaneous_analyses'] (None = sem espera).
"""
from __future__ import annotations

import logging
from typing import List

from database.schema import USE_POSTGRES, get_conn

log = logging.getLogger(__name__)

_CRIADA = False


def _stmts(postgres: bool) -> List[str]:
    """DDL nas duas gramáticas, testável sem servidor (padrão de mao_compartilhada).
    `id` SERIAL de propósito: tabela sem id autoincrement exige entrar na allowlist
    `_NO_ID_TABLES` do adaptador PG — com id, o INSERT adaptado funciona sem exceção."""
    if postgres:
        return ["""
            CREATE TABLE IF NOT EXISTS gto_analysis_waitlist (
                id            SERIAL PRIMARY KEY,
                tournament_id INTEGER NOT NULL UNIQUE,
                user_id       INTEGER NOT NULL,
                created_at    TIMESTAMP NOT NULL DEFAULT NOW()
            )"""]
    return ["""
        CREATE TABLE IF NOT EXISTS gto_analysis_waitlist (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL UNIQUE,
            user_id       INTEGER NOT NULL,
            created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""]


def _tabela() -> None:
    global _CRIADA
    if _CRIADA:
        return
    conn = get_conn()
    try:
        for sql in _stmts(USE_POSTGRES):
            conn.execute(sql)
        conn.commit()
        _CRIADA = True
    finally:
        conn.close()


def _limite_do_plano(user_id: int):
    from database.repositories import get_quota_status
    return get_quota_status(user_id)['limits'].get('simultaneous_analyses')


def _cutoff_stale() -> str:
    from datetime import datetime, timedelta
    from database.repositories import _GTO_STALE_HOURS
    return (datetime.utcnow() - timedelta(hours=_GTO_STALE_HOURS)).strftime('%Y-%m-%d %H:%M:%S')


def em_analise(user_id: int) -> List[int]:
    """Ids (db) dos torneios do usuário com análise GTO em andamento — os DOIS sinais
    (spot na fila ativa OU request de mão não-terminal), ambos com stale de 24h."""
    from database.repositories import _adapt, _fetchall
    cutoff = _cutoff_stale()
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT DISTINCT t.id FROM tournaments t
            JOIN gto_tournament_queue m ON m.tournament_id = t.id
            JOIN gto_solver_queue q ON q.spot_hash = m.spot_hash
            WHERE t.user_id = ? AND q.status IN ('pending', 'running') AND q.requested_at > ?
            UNION
            SELECT DISTINCT t.id FROM tournaments t
            JOIN gto_hand_requests ghr ON ghr.tournament_id = t.id
            WHERE t.user_id = ?
              AND ghr.status IN ('pending', 'solver_queued', 'processing', 'queued', 'running')
              AND ghr.created_at > ?
        """), (user_id, cutoff, user_id, cutoff))
        return [r['id'] for r in rows]
    finally:
        conn.close()


def deve_esperar(user_id: int) -> bool:
    """True se o plano limita análises simultâneas e as vagas estão cheias."""
    limite = _limite_do_plano(user_id)
    if limite is None:
        return False
    return len(em_analise(user_id)) >= limite


def entrar_na_espera(tournament_db_id: int, user_id: int) -> None:
    from database.repositories import _adapt
    _tabela()
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "INSERT OR IGNORE INTO gto_analysis_waitlist (tournament_id, user_id) VALUES (?, ?)"),
            (tournament_db_id, user_id))
        conn.commit()
        log.info("fila de analise: torneio %s do user %s aguardando vaga", tournament_db_id, user_id)
    finally:
        conn.close()


def em_espera_ids(user_id: int) -> List[int]:
    """Ids (db) dos torneios do usuário aguardando vaga — para o selo "Na fila" da lista."""
    from database.repositories import _adapt, _fetchall
    _tabela()
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt(
            "SELECT tournament_id FROM gto_analysis_waitlist WHERE user_id = ? ORDER BY id"),
            (user_id,))
        return [r['tournament_id'] for r in rows]
    finally:
        conn.close()


def promover_aguardando() -> int:
    """Preenche vagas: para cada usuário na espera, promove os torneios mais antigos até o
    limite do plano. Promover = criar gto_hand_requests das mãos postflop gravadas (o worker
    de mãos monta e enfileira os spots — mesmo caminho do botão do replay). Retorna promovidos."""
    from database.repositories import _adapt, _fetchall, bulk_request_gto_for_hands
    _tabela()
    conn = get_conn()
    try:
        users = _fetchall(conn, "SELECT DISTINCT user_id FROM gto_analysis_waitlist")
    finally:
        conn.close()
    promovidos = 0
    for u in users:
        uid = u['user_id']
        limite = _limite_do_plano(uid)
        vagas = None if limite is None else limite - len(em_analise(uid))
        if vagas is not None and vagas <= 0:
            continue
        fila = em_espera_ids(uid)
        for tid in (fila if vagas is None else fila[:vagas]):
            conn = get_conn()
            try:
                hands = _fetchall(conn, _adapt(
                    "SELECT DISTINCT hand_id FROM decisions WHERE tournament_id = ? "
                    "AND lower(street) IN ('flop','turn','river') AND hand_id IS NOT NULL"), (tid,))
                # Sai da espera ANTES de pedir: se não há mão postflop, promover é só sair.
                conn.execute(_adapt("DELETE FROM gto_analysis_waitlist WHERE tournament_id = ?"), (tid,))
                conn.commit()
            finally:
                conn.close()
            hand_ids = [h['hand_id'] for h in hands]
            if hand_ids:
                bulk_request_gto_for_hands(tid, hand_ids, uid)
            promovidos += 1
            log.info("fila de analise: torneio %s do user %s PROMOVIDO (%d maos)",
                     tid, uid, len(hand_ids))
    return promovidos
