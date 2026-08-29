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
from database.schema import USE_POSTGRES, get_conn

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


def _stmts(postgres: bool) -> tuple:
    """Os statements por backend, como FUNÇÃO para o teste poder afirmar sobre os dois lados
    sem precisar de um Postgres de verdade (30/08: a heurística hasattr(conn,'row_factory')
    detectava PG como SQLite — o wrapper tem a propriedade — e o AUTOINCREMENT quebrava o
    CREATE calado; o Sentry acusou UndefinedTable em prod)."""
    pk = 'SERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    return (
        """CREATE TABLE IF NOT EXISTS shared_hands (
                token          TEXT PRIMARY KEY,
                user_id        INTEGER NOT NULL,
                tournament_id  INTEGER NOT NULL,
                hand_id        TEXT NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at     TIMESTAMP,
                views          INTEGER DEFAULT 0
            )""",
        "ALTER TABLE shared_hands ADD COLUMN step_idx INTEGER",
        "ALTER TABLE shared_hands ADD COLUMN pergunta TEXT",
        "ALTER TABLE shared_hands ADD COLUMN anonimo INTEGER DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS shared_hand_votes (
                token   TEXT NOT NULL,
                action  TEXT NOT NULL,
                n       INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (token, action)
            )""",
        """CREATE TABLE IF NOT EXISTS shared_hand_comments (
                id         %s,
                token      TEXT NOT NULL,
                user_id    INTEGER NOT NULL,
                texto      TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP
            )""" % pk,
    )


def _tabela(conn) -> None:
    """CADA statement em bloco isolado: em PG um erro aborta a transação e o seguinte
    falharia calado sem o rollback (ver reference_pg_migration_abort_proof)."""
    for st in _stmts(USE_POSTGRES):
        try:
            conn.execute(_adapt(st))
            conn.commit()
        except Exception:                                      # noqa: BLE001
            conn.rollback()


def criar(user_id: int, tournament_id: int, hand_id: str,
          step_idx: Optional[int] = None, pergunta: Optional[str] = None,
          anonimo: bool = False) -> Optional[str]:
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
                    'UPDATE shared_hands SET step_idx = ?, pergunta = ?, anonimo = ? '
                    'WHERE token = ?'),
                    (step_idx, (pergunta or '')[:280] or None, 1 if anonimo else 0, token))
                conn.commit()
            return token
        # 16 bytes = 128 bits. Aleatório, não derivado: ver o docblock.
        token = secrets.token_urlsafe(16)
        conn.execute(_adapt(
            'INSERT INTO shared_hands (token, user_id, tournament_id, hand_id, step_idx, pergunta, anonimo) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)'),
            (token, user_id, tournament_id, hand_id, step_idx, (pergunta or '')[:280] or None,
             1 if anonimo else 0))
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


def _username(user_id) -> Optional[str]:
    conn = get_conn()
    try:
        r = conn.execute(_adapt('SELECT username FROM users WHERE id = ?'),
                         (user_id,)).fetchone()
        return dict(r)['username'] if r else None
    finally:
        conn.close()


def ler(token: str) -> Optional[dict]:
    """O payload PÚBLICO da mão, ou `None` se o link não existe ou foi revogado."""
    conn = get_conn()
    try:
        _tabela(conn)
        row = conn.execute(_adapt(
            'SELECT tournament_id, hand_id, step_idx, pergunta, anonimo, user_id FROM shared_hands '
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
            # 30/08, decisao do dono: quem ESCOLHEU compartilhar com nome aparece; anonimo
            # e opcao no popover. Nick de POKER segue invisivel em qualquer modo.
            'autor': (None if r.get('anonimo') else _username(r.get('user_id'))),
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


# ── O feed da comunidade (30/08): as mãos compartilhadas, num lugar só ───────────────────────

#: ordenações do feed — cada uma um SQL DECLARADO (nada de concatenar entrada do usuário)
_ORDENACOES = {
    'recentes':    'sh.created_at DESC',
    'comentadas':  'comentarios DESC, sh.created_at DESC',
    'votadas':     'votos DESC, sh.created_at DESC',
    'sem_resposta': 'sh.created_at DESC',
}


def listar_feed(ordenar: str = 'recentes', posicao: Optional[str] = None,
                limit: int = 30, offset: int = 0) -> list[dict]:
    """Os links vivos, com autor (username GrindLab), pergunta, prévia da mão e placar.

    A distinção de anonimato que este feed fixa: a regra de 28/08 protege NICK DE POKER
    (pessoas que não consentiram); o username GrindLab de quem ESCOLHEU compartilhar é
    identidade de plataforma — os comentários já assinam assim. A prévia sai da MESMA
    whitelist do payload público, e o veredito fica de fora do card: quem clica vota antes
    de ver (o mecanismo que faz o link valer).
    """
    ordenar = ordenar if ordenar in _ORDENACOES else 'recentes'
    limit = max(1, min(int(limit or 30), 60))
    conn = get_conn()
    try:
        _tabela(conn)
        where = 'sh.revoked_at IS NULL'
        if ordenar == 'sem_resposta':
            # a aba do benchmark que faz sentido aqui: pergunta feita, ninguém respondeu ainda
            where += (" AND sh.pergunta IS NOT NULL AND NOT EXISTS ("
                      "SELECT 1 FROM shared_hand_comments c WHERE c.token = sh.token "
                      "AND c.deleted_at IS NULL)")
        rows = conn.execute(_adapt(
            'SELECT sh.token, sh.pergunta, sh.step_idx, sh.created_at, sh.views, sh.anonimo AS _anon, '
            '       sh.tournament_id AS _tid, sh.hand_id AS _hid, u.username AS autor, '
            '       (SELECT COALESCE(SUM(n), 0) FROM shared_hand_votes v '
            '        WHERE v.token = sh.token) AS votos, '
            '       (SELECT COUNT(*) FROM shared_hand_comments c '
            '        WHERE c.token = sh.token AND c.deleted_at IS NULL) AS comentarios '
            'FROM shared_hands sh JOIN users u ON u.id = sh.user_id '
            'WHERE ' + where + ' ORDER BY ' + _ORDENACOES[ordenar] +
            ' LIMIT ? OFFSET ?'), (limit, max(0, int(offset or 0)))).fetchall()
        feed = []
        for r in rows:
            d = dict(r)
            if d.pop('_anon', 0):
                d['autor'] = None                      # anonimo por escolha do dono do link
            decisoes = conn.execute(_adapt(
                'SELECT * FROM decisions WHERE tournament_id = ? AND hand_id = ? ORDER BY id'),
                (d.pop('_tid'), d.pop('_hid'))).fetchall()
            if not decisoes:
                continue
            idx = d.get('step_idx')
            alvo = dict(decisoes[idx]) if isinstance(idx, int) and 0 <= idx < len(decisoes)                 else dict(decisoes[0])
            # prévia SEM veredito: cartas/posição/street saem; label/best_action ficam — o
            # card não pode entregar a resposta que a página pede para votar.
            previa = {k: _limpa(v) for k, v in alvo.items()
                      if k in CAMPOS_PUBLICOS and k not in (
                          'label', 'gto_label', 'best_action', 'gto_strategy',
                          'recommended', 'ev_loss_bb', 'verdict_source', 'verdict_has_cost')}
            if posicao and str(previa.get('position') or '').upper() != posicao.upper():
                continue
            d['previa'] = previa
            d['n_passos'] = len(decisoes)
            feed.append(d)
        return feed
    finally:
        conn.close()
