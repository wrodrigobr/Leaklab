# -*- coding: utf-8 -*-
"""Compartilhar uma mão: um link público que mostra a mão e o veredito, sem expor ninguém.

── Por que existe (29/08) ──────────────────────────────────────────────────────────────────

Do benchmark. O dono: *"aquela parte de compartilhar mãos achei legal"*. É a única coisa do
produto que sai dele -- alguém posta o link num grupo e quem clica vê o que o GrindLab disse.

── As três decisões que definem o desenho ──────────────────────────────────────────────────

**1. Compartilhar é ATO, não derivação.** O `grind_mode` já tem `token_da_mao`, um hash da mão com
o segredo. Reusá-lo aqui seria tentador e errado: token derivado significa que TODA mão já tem
link, sem ninguém ter decidido nada, sem registro de quem quis e sem como revogar. Aqui o token é
aleatório e nasce de um pedido explícito do dono da mão.

**2. Lista BRANCA de campos.** Copiada da disciplina de `mao_completa`: campo novo em `decisions`
não vaza por esquecimento. Blacklist protege contra o que se lembrou; whitelist protege contra o
que ainda não existe.

**3. Nick de vilão nunca sai.** Em 28/08 uma captura para a landing saiu com os 43 screen names
reais de um torneio -- pessoas que não concordaram em aparecer. Ali era uma imagem, e deu para
refazer. Aqui é um link que qualquer um abre, e o dano seria contínuo.

── O que o link mostra, e o que não mostra ─────────────────────────────────────────────────

Mostra: cartas, board, posições, stacks em bb, ações, e o veredito com sua procedência. É o que
faz o link valer a pena postar.

Não mostra: nick de ninguém (nem do dono), nome do torneio, data, id de torneio ou de mão. Quem
abre vê a MÃO, não a pessoa.
"""
from __future__ import annotations

import json
import secrets
from typing import Optional

from database.repositories import _adapt
from database.schema import get_conn

#: Campos que podem sair no payload público. WHITELIST -- ver o docblock.
CAMPOS_PUBLICOS = {
    'street', 'position', 'vs_position', 'stack_bb', 'pot_bb', 'facing_bb',
    'board', 'hero_cards', 'action_taken', 'best_action',
    'label', 'gto_label', 'ev_loss_bb', 'verdict_source', 'verdict_has_cost',
    'gto_strategy', 'recommended',
}

#: Campos que NUNCA saem, listados por nome para o teste poder afirmar sobre eles. Não é a
#: proteção (a whitelist é); é a declaração do que se está protegendo.
CAMPOS_PROIBIDOS = {
    'hero', 'villain', 'player_name', 'username', 'email', 'tournament_id', 'hand_id',
    'user_id', 'played_at', 'imported_at', 'tournament_name', 'raw_text', 'id',
}


def _tabela(conn) -> None:
    """Cria as tabelas na primeira chamada. CADA statement em bloco isolado: em PG um `CREATE`
    que falha aborta a transação e todo statement seguinte falha calado
    (ver `reference_pg_migration_abort_proof`)."""
    stmts = (
        """CREATE TABLE IF NOT EXISTS shared_hands (
                token          TEXT PRIMARY KEY,
                user_id        INTEGER NOT NULL,
                tournament_id  INTEGER NOT NULL,
                hand_id        TEXT NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at     TIMESTAMP,
                views          INTEGER DEFAULT 0
            )""",
        # A pergunta do dono: o link quase sempre existe POR CAUSA de uma decisão. O dono marca
        # o passo e escreve a dúvida; o visitante vota nela antes de ver o veredito.
        "ALTER TABLE shared_hands ADD COLUMN step_idx INTEGER",
        "ALTER TABLE shared_hands ADD COLUMN pergunta TEXT",
        # Voto AGREGADO por token+ação: nenhum visitante identificável é gravado.
        """CREATE TABLE IF NOT EXISTS shared_hand_votes (
                token   TEXT NOT NULL,
                action  TEXT NOT NULL,
                n       INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (token, action)
            )""",
        # Comentário exige CONTA (anônimo vota, não escreve): spam e autoria ficam tratáveis.
        """CREATE TABLE IF NOT EXISTS shared_hand_comments (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token      TEXT NOT NULL,
                user_id    INTEGER NOT NULL,
                texto      TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP
            )""",
    )
    for st in stmts:
        try:
            conn.execute(_adapt(st.replace('AUTOINCREMENT', 'AUTOINCREMENT')
                                if _sqlite(conn) else
                                st.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')))
            conn.commit()
        except Exception:                                      # noqa: BLE001
            conn.rollback()


def _sqlite(conn) -> bool:
    return 'sqlite' in type(conn).__module__.lower() or hasattr(conn, 'row_factory')


def criar(user_id: int, tournament_id: int, hand_id: str,
          step_idx: Optional[int] = None, pergunta: Optional[str] = None) -> Optional[str]:
    """Cria (ou devolve) o link da mão. `None` se a mão não é do usuário.

    A conferência de dono não é formalidade: sem ela qualquer um compartilharia a mão de qualquer
    um, e o link é público.
    """
    conn = get_conn()
    try:
        _tabela(conn)
        dono = conn.execute(_adapt(
            'SELECT 1 FROM tournaments WHERE id = ? AND user_id = ?'),
            (tournament_id, user_id)).fetchone()
        if not dono:
            return None
        ja = conn.execute(_adapt(
            'SELECT token FROM shared_hands WHERE user_id = ? AND tournament_id = ? '
            'AND hand_id = ? AND revoked_at IS NULL'),
            (user_id, tournament_id, hand_id)).fetchone()
        if ja:
            token = dict(ja)['token']
            if step_idx is not None or pergunta:
                # Compartilhar de novo com pergunta nova ATUALIZA o link existente: o link é da
                # mão, a pergunta é o estado atual da dúvida do dono.
                conn.execute(_adapt(
                    'UPDATE shared_hands SET step_idx = ?, pergunta = ? WHERE token = ?'),
                    (step_idx, (pergunta or '')[:280] or None, token))
                conn.commit()
            return token
        # 16 bytes = 128 bits. Aleatório, não derivado: ver o docblock.
        token = secrets.token_urlsafe(16)
        conn.execute(_adapt(
            'INSERT INTO shared_hands (token, user_id, tournament_id, hand_id, step_idx, pergunta) '
            'VALUES (?, ?, ?, ?, ?, ?)'),
            (token, user_id, tournament_id, hand_id, step_idx, (pergunta or '')[:280] or None))
        conn.commit()
        return token
    finally:
        conn.close()


def revogar(user_id: int, token: str) -> bool:
    """Desliga o link. Só o dono. Quem compartilhou tem de poder voltar atrás."""
    conn = get_conn()
    try:
        _tabela(conn)
        cur = conn.execute(_adapt(
            'UPDATE shared_hands SET revoked_at = CURRENT_TIMESTAMP '
            'WHERE token = ? AND user_id = ? AND revoked_at IS NULL'), (token, user_id))
        conn.commit()
        return bool(getattr(cur, 'rowcount', 0))
    finally:
        conn.close()


def _limpa(valor):
    """Normaliza o que sai. `board` vem string JSON em algumas linhas e lista em outras."""
    if isinstance(valor, str) and valor.startswith('['):
        try:
            return json.loads(valor)
        except Exception:                                      # noqa: BLE001
            return valor
    return valor


def ler(token: str) -> Optional[dict]:
    """O payload PÚBLICO da mão, ou `None` se o link não existe ou foi revogado."""
    conn = get_conn()
    try:
        _tabela(conn)
        row = conn.execute(_adapt(
            'SELECT tournament_id, hand_id, step_idx, pergunta FROM shared_hands '
            'WHERE token = ? AND revoked_at IS NULL'), (token,)).fetchone()
        if not row:
            return None
        r = dict(row)
        decisoes = conn.execute(_adapt(
            'SELECT * FROM decisions WHERE tournament_id = ? AND hand_id = ? ORDER BY id'),
            (r['tournament_id'], r['hand_id'])).fetchall()
        if not decisoes:
            return None
        votos = {dict(v)['action']: dict(v)['n'] for v in conn.execute(_adapt(
            'SELECT action, n FROM shared_hand_votes WHERE token = ?'), (token,)).fetchall()}
        # Autor pelo USERNAME (decisão de 29/08): quem escreve assina; o dono da MÃO segue
        # anônimo no payload — quem comenta não descobre de quem é a mão.
        comentarios = [dict(c) for c in conn.execute(_adapt(
            'SELECT c.id, c.texto, c.created_at, u.username AS autor '
            'FROM shared_hand_comments c JOIN users u ON u.id = c.user_id '
            'WHERE c.token = ? AND c.deleted_at IS NULL ORDER BY c.id'), (token,)).fetchall()]
        conn.execute(_adapt(
            'UPDATE shared_hands SET views = COALESCE(views, 0) + 1 WHERE token = ?'), (token,))
        conn.commit()
    finally:
        conn.close()

    passos = []
    for d in decisoes:
        linha = dict(d)
        # WHITELIST: só o que está declarado sai. Campo novo no banco não vaza por esquecimento.
        passos.append({k: _limpa(v) for k, v in linha.items() if k in CAMPOS_PUBLICOS})
    return {'passos': passos, 'n': len(passos),
            'pergunta': r.get('pergunta'), 'passo_marcado': r.get('step_idx'),
            'votos': votos, 'comentarios': comentarios}


# ── Voto e comentário (29/08): o que faz o link não ser copy-paste ───────────────────────────

#: Ações votáveis — o menu do treino. Whitelist: voto fora disso é descartado, não gravado.
ACOES_VOTAVEIS = {'fold', 'call', 'raise', 'allin', 'check', 'bet'}


def votar(token: str, acao: str) -> Optional[dict]:
    """Registra um voto AGREGADO na decisão marcada e devolve o placar. Anônimo vota: o
    agregado por token+ação não identifica ninguém. `None` se o link não existe/revogado ou a
    ação não é votável."""
    acao = (acao or '').strip().lower()
    if acao not in ACOES_VOTAVEIS:
        return None
    conn = get_conn()
    try:
        _tabela(conn)
        vivo = conn.execute(_adapt(
            'SELECT 1 FROM shared_hands WHERE token = ? AND revoked_at IS NULL'),
            (token,)).fetchone()
        if not vivo:
            return None
        cur = conn.execute(_adapt(
            'UPDATE shared_hand_votes SET n = n + 1 WHERE token = ? AND action = ?'),
            (token, acao))
        if not getattr(cur, 'rowcount', 0):
            conn.execute(_adapt(
                'INSERT INTO shared_hand_votes (token, action, n) VALUES (?, ?, 1)'),
                (token, acao))
        conn.commit()
        return {dict(v)['action']: dict(v)['n'] for v in conn.execute(_adapt(
            'SELECT action, n FROM shared_hand_votes WHERE token = ?'), (token,)).fetchall()}
    finally:
        conn.close()


def comentar(token: str, user_id: int, texto: str) -> Optional[int]:
    """Comentário exige conta (anônimo vota, não escreve). Devolve o id, ou `None` se o link
    não existe/revogado ou o texto é vazio. Teto de 1000 chars: comentário, não artigo."""
    texto = (texto or '').strip()[:1000]
    if not texto:
        return None
    conn = get_conn()
    try:
        _tabela(conn)
        vivo = conn.execute(_adapt(
            'SELECT 1 FROM shared_hands WHERE token = ? AND revoked_at IS NULL'),
            (token,)).fetchone()
        if not vivo:
            return None
        conn.execute(_adapt(
            'INSERT INTO shared_hand_comments (token, user_id, texto) VALUES (?, ?, ?)'),
            (token, user_id, texto))
        conn.commit()
        row = conn.execute(_adapt(
            'SELECT MAX(id) AS i FROM shared_hand_comments WHERE token = ? AND user_id = ?'),
            (token, user_id)).fetchone()
        return dict(row)['i'] if row else None
    finally:
        conn.close()


def apagar_comentario(comment_id: int, user_id: int) -> bool:
    """Soft-delete. Quem pode: o AUTOR do comentário ou o DONO da mão (moderação mínima)."""
    conn = get_conn()
    try:
        _tabela(conn)
        cur = conn.execute(_adapt(
            'UPDATE shared_hand_comments SET deleted_at = CURRENT_TIMESTAMP '
            'WHERE id = ? AND deleted_at IS NULL AND ('
            '  user_id = ? OR token IN (SELECT token FROM shared_hands WHERE user_id = ?)'
            ')'), (comment_id, user_id, user_id))
        conn.commit()
        return bool(getattr(cur, 'rowcount', 0))
    finally:
        conn.close()
