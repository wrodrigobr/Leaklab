# -*- coding: utf-8 -*-
"""Receber o arquivo é uma coisa; processá-lo é outra. Esta é a primeira (14/09).

── Por que existe ────────────────────────────────────────────────────────────────────────────

O dono pediu essa separação duas vezes ("receber o arquivo, garantir que está íntegro e só
depois começar a processar... se der problema no processamento o usuário não precisaria
reenviar, já teríamos o arquivo"). Um fundador tentou subir e viu `NetworkError` duas vezes,
enquanto 22 torneios dele **tinham sido gravados**. A tela disse que falhou o que deu certo.

── A medição que decidiu o desenho ───────────────────────────────────────────────────────────

O arquivo real, 3,1 MB e 18 torneios, pela rota pública, em conta vazia:

    homologação (Postgres no mesmo host) .....  36,1 s  →  1,9 s por torneio
    PRODUÇÃO    (Neon remoto) ................ 117,4 s  →  6,2 s por torneio   (fator 3,3x)

Passou por 2,6 segundos dos 120 s do gunicorn. E o custo é dominado por ida e volta de rede:
**311 viagens ao banco** por torneio de 123 decisões, a **8,10 ms** cada — perto de 40% do
tempo. Agrupar as maiores (as 123 do `executemany` e as 29 de `opponent_profiles`) economiza
~1,2 s por torneio, o que levaria 117 s para ~96 s: **não compra segurança**, porque o tempo
depende de latência de rede e de contenção de CPU, e nenhum orçamento dentro de uma requisição
HTTP dá garantia sobre isso.

Por isso o conserto não é otimizar: é sair da requisição.

── O contrato ────────────────────────────────────────────────────────────────────────────────

`receber()` é barato de propósito: confere que o texto PARECE hand history (uma regex, não o
parse, que custa 9 s nos 3,1 MB), grava os bytes e devolve o recibo. Quem divide e processa é o
worker, pelo mesmo `_analyze_orquestrado` de hoje.

A idempotência é por `sha256` do conteúdo mais `user_id`: rearrastar o mesmo arquivo devolve **o
mesmo recibo** em vez de criar trabalho novo. Só isso já teria evitado a confusão de hoje.

Os bytes são TRANSITÓRIOS e o recibo é permanente: `conteudo` é zerado ao concluir, senão a gente
duplicaria no banco tudo o que já vive em `tournaments.raw_text`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import List, Optional

from database.schema import USE_POSTGRES, get_conn, interval_minutos_sql, now_sql

log = logging.getLogger(__name__)

_CRIADA = False

# Estados. `processando` é reivindicado por UM worker; `devolver_travados` desfaz reivindicação
# órfã (worker morto), que é o mesmo remédio do reset de `running` na fila do solver.
RECEBIDO = 'recebido'
PROCESSANDO = 'processando'
CONCLUIDO = 'concluido'
ERRO = 'erro'
# O teto mensal do jogador acabou no meio do arquivo. NAO e erro e NAO e conclusao: o que sobrou
# fica guardado e entra quando a cota virar (ou quando ele fizer upgrade).
AGUARDANDO_COTA = 'aguardando_cota'

TENTATIVAS_MAX = 3
TRAVADO_APOS_MIN = 15

# Teto de arquivos em espera por jogador. Aceitar e guardar e o que da valor, mas sem teto um
# Free empilharia arquivo sem limite e nos pagariamos o armazenamento por ele. Mesmo espirito do
# `max_pending_solves` dos planos.
ESPERA_MAX_POR_USUARIO = 5

# Teto de BYTES em aberto por jogador (auditoria SEG-2 e SEG-3, 15/09). O teto acima conta so
# `aguardando_cota`, e quem poe nesse estado e o worker, DEPOIS do POST: em rajada (que e como o
# front manda uma fila) 20 arquivos entraram com teto 5, e um free empilhou 45 MB de lixo com
# uma linha de cabecalho em 10 POSTs, tudo em `recebido`. A grandeza que custa e byte, nao
# arquivo, entao o teto e em bytes e conta TODO recibo cujo conteudo ainda esta guardado
# (`recebido`, `processando`, `aguardando_cota`); `concluido` e `erro` zeram os bytes.
# 40 MB e 13 vezes o maior arquivo real medido (3,1 MB, 18 torneios): folga para o mes inteiro
# de um fundador, e o lote drena enquanto ele envia.
BYTES_EM_ABERTO_MAX_POR_USUARIO = 40 * 1024 * 1024
STATUS_EM_ABERTO = (RECEBIDO, PROCESSANDO, AGUARDANDO_COTA)

# A peneira BARATA da recepção: o arquivo parece hand history? Uma regex sobre o texto, não o
# parse. Os cinco dialetos do acervo, pelos cabeçalhos que o parser já reconhece.
_PARECE_HH = re.compile(
    r'(PokerStars\s+(Zoom\s+)?Hand\s+#'          # PokerStars, GGPoker, ACR compartilham o molde
    r'|Game\s+Hand\s+#'                          # ACR/WPN
    r'|Hand\s+#\d+\s+-\s+'                       # CoinPoker
    r'|\*\*\*\*\*\s*Hand\s+History'              # PartyPoker antigo
    r'|Tourney\s+Texas\s+Holdem\s+Game\s+Table'  # PartyPoker novo
    r'|\#Game\s+No\s*:'                          # 888poker
    r')', re.IGNORECASE)


def _stmts(postgres: bool) -> List[str]:
    """DDL nas duas gramáticas, testável sem servidor (padrão de `fila_de_analise`).

    `id SERIAL` de propósito: tabela sem id autoincrement teria de entrar na allowlist
    `_NO_ID_TABLES` do adaptador, e esquecer disso já custou um INSERT que falhava SÓ no
    Postgres, com a transação abortada escondendo o culpado.

    `UNIQUE(user_id, sha256)` é a idempotência, e ela mora no BANCO em vez de num `if`: duas
    requisições simultâneas do mesmo arquivo (duplo clique) não podem criar dois trabalhos.
    """
    if postgres:
        return ["""
            CREATE TABLE IF NOT EXISTS uploads_recebidos (
                id                   SERIAL PRIMARY KEY,
                user_id              INTEGER NOT NULL,
                filename             TEXT,
                sha256               TEXT NOT NULL,
                bytes_total          INTEGER NOT NULL DEFAULT 0,
                conteudo             TEXT,
                status               TEXT NOT NULL DEFAULT 'recebido',
                tentativas           INTEGER NOT NULL DEFAULT 0,
                torneios_no_arquivo  INTEGER,
                torneios_gravados    INTEGER NOT NULL DEFAULT 0,
                torneios_ja_estavam  INTEGER NOT NULL DEFAULT 0,
                torneios_com_erro    INTEGER NOT NULL DEFAULT 0,
                detalhe              TEXT,
                erro                 TEXT,
                recebido_em          TIMESTAMP NOT NULL DEFAULT NOW(),
                iniciado_em          TIMESTAMP,
                concluido_em         TIMESTAMP,
                UNIQUE (user_id, sha256)
            )""",
                """CREATE INDEX IF NOT EXISTS ix_uploads_recebidos_fila
                   ON uploads_recebidos (status, recebido_em)"""]
    return ["""
        CREATE TABLE IF NOT EXISTS uploads_recebidos (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id              INTEGER NOT NULL,
            filename             TEXT,
            sha256               TEXT NOT NULL,
            bytes_total          INTEGER NOT NULL DEFAULT 0,
            conteudo             TEXT,
            status               TEXT NOT NULL DEFAULT 'recebido',
            tentativas           INTEGER NOT NULL DEFAULT 0,
            torneios_no_arquivo  INTEGER,
            torneios_gravados    INTEGER NOT NULL DEFAULT 0,
            torneios_ja_estavam  INTEGER NOT NULL DEFAULT 0,
            torneios_com_erro    INTEGER NOT NULL DEFAULT 0,
            detalhe              TEXT,
            erro                 TEXT,
            recebido_em          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            iniciado_em          TIMESTAMP,
            concluido_em         TIMESTAMP,
            UNIQUE (user_id, sha256)
        )""",
            """CREATE INDEX IF NOT EXISTS ix_uploads_recebidos_fila
               ON uploads_recebidos (status, recebido_em)"""]


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


def parece_hand_history(conteudo: str) -> bool:
    """A peneira da recepção: isto parece hand history de alguma das salas?

    Barata de propósito. O parse completo custa 9 s nos 3,1 MB do arquivo medido, e pagar isso
    na requisição era metade do problema que esta frente existe para resolver. Arquivo com molde
    de sala mas conteúdo quebrado é recusado DEPOIS, pelo worker, no recibo -- e aí o usuário não
    precisa reenviar, porque o arquivo já está guardado.
    """
    return bool(_PARECE_HH.search(conteudo or ''))


def _linha(conn, recibo_id: int) -> Optional[dict]:
    from database.repositories import _adapt
    r = conn.execute(_adapt(
        "SELECT id, user_id, filename, sha256, bytes_total, status, tentativas, "
        "torneios_no_arquivo, torneios_gravados, torneios_ja_estavam, torneios_com_erro, "
        "detalhe, erro, recebido_em, iniciado_em, concluido_em "
        "FROM uploads_recebidos WHERE id=?"), (recibo_id,)).fetchone()
    return dict(r) if r else None


def receber(user_id: int, conteudo: str, filename: str | None = None) -> dict:
    """Grava o arquivo e devolve o recibo. NÃO processa nada.

    Devolve `{'recibo': id, 'status': ..., 'repetido': bool, ...}`. `repetido=True` quando o
    mesmo usuário já mandou o mesmo conteúdo: devolve o recibo que já existe, em vez de criar
    trabalho novo.
    """
    _tabela()
    from database.repositories import _adapt
    sha = hashlib.sha256((conteudo or '').encode('utf-8', 'replace')).hexdigest()
    n_bytes = len((conteudo or '').encode('utf-8', 'replace'))
    conn = get_conn()
    try:
        ja = conn.execute(_adapt(
            "SELECT id FROM uploads_recebidos WHERE user_id=? AND sha256=?"),
            (user_id, sha)).fetchone()
        if ja:
            r = _linha(conn, dict(ja)['id'])
            r['repetido'] = True
            return r
        conn.execute(_adapt(
            "INSERT INTO uploads_recebidos (user_id, filename, sha256, bytes_total, conteudo, "
            "status) VALUES (?,?,?,?,?,?)"),
            (user_id, filename, sha, n_bytes, conteudo, RECEBIDO))
        conn.commit()
        novo = conn.execute(_adapt(
            "SELECT id FROM uploads_recebidos WHERE user_id=? AND sha256=?"),
            (user_id, sha)).fetchone()
        r = _linha(conn, dict(novo)['id'])
        r['repetido'] = False
        return r
    finally:
        conn.close()


def recibo(user_id: int, recibo_id: int) -> Optional[dict]:
    """O recibo, conferindo o dono. O `user_id` não é zelo: sem ele o id na URL vira
    enumeração do upload de qualquer jogador."""
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        r = conn.execute(_adapt(
            "SELECT id FROM uploads_recebidos WHERE id=? AND user_id=?"),
            (recibo_id, user_id)).fetchone()
        if not r:
            return None
        d = _linha(conn, recibo_id)
        if d and d.get('detalhe'):
            try:
                d['detalhe'] = json.loads(d['detalhe'])
            except Exception:
                pass
        return d
    finally:
        conn.close()


def pendentes_do_usuario(user_id: int) -> List[dict]:
    """Recibos que ainda não terminaram. O front usa para reabrir a lista depois de um F5."""
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        rs = conn.execute(_adapt(
            "SELECT id FROM uploads_recebidos WHERE user_id=? AND status IN (?,?) "
            "ORDER BY recebido_em"), (user_id, RECEBIDO, PROCESSANDO)).fetchall()
        return [_linha(conn, dict(r)['id']) for r in rs]
    finally:
        conn.close()


def devolver_travados(minutos: int = TRAVADO_APOS_MIN) -> int:
    """`processando` órfão volta para a fila, contando a tentativa.

    Mesmo remédio do reset de `running` na fila do solver: worker morto não pode prender o
    arquivo de alguém para sempre. Acima de `TENTATIVAS_MAX` o recibo vira `erro` com motivo, em
    vez de girar eternamente -- fila que retenta sem teto esconde defeito em vez de mostrá-lo.
    """
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        cur = conn.execute(_adapt(
            "UPDATE uploads_recebidos SET status=?, iniciado_em=NULL "
            "WHERE status=? AND tentativas < ? AND iniciado_em < %s"
            % interval_minutos_sql(minutos)), (RECEBIDO, PROCESSANDO, TENTATIVAS_MAX))
        n = int(getattr(cur, 'rowcount', 0) or 0)
        conn.execute(_adapt(
            "UPDATE uploads_recebidos SET status=?, erro=? "
            "WHERE status=? AND tentativas >= ?"),
            (ERRO, 'o processamento falhou %d vezes' % TENTATIVAS_MAX,
             PROCESSANDO, TENTATIVAS_MAX))
        conn.commit()
        return n
    finally:
        conn.close()


def reivindicar() -> Optional[dict]:
    """Pega UM recibo para processar, marcando-o. None quando não há nada.

    A reivindicação é condicional (`WHERE id=? AND status='recebido'`) e conferida por
    `rowcount`: dois workers que leiam a mesma linha não podem processá-la os dois. `rowcount`
    existe nas duas gramáticas (conferido no wrapper), então isto não é padrão só-Postgres.
    """
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        cand = conn.execute(_adapt(
            "SELECT id FROM uploads_recebidos WHERE status=? "
            "ORDER BY recebido_em, id LIMIT 1"), (RECEBIDO,)).fetchone()
        if not cand:
            return None
        rid = dict(cand)['id']
        cur = conn.execute(_adapt(
            "UPDATE uploads_recebidos SET status=?, iniciado_em=%s, tentativas=tentativas+1 "
            "WHERE id=? AND status=?" % now_sql()), (PROCESSANDO, rid, RECEBIDO))
        if not int(getattr(cur, 'rowcount', 0) or 0):
            conn.rollback()
            return None                      # outro worker levou
        conn.commit()
        d = _linha(conn, rid)
        raw = conn.execute(_adapt(
            "SELECT conteudo FROM uploads_recebidos WHERE id=?"), (rid,)).fetchone()
        d['conteudo'] = dict(raw)['conteudo'] if raw else None
        return d
    finally:
        conn.close()


def tocar(recibo_id: int, gravados: int | None = None) -> None:
    """Batimento de coração: renova a reivindicação e, de passagem, o progresso.

    Sem isto, `devolver_travados` devolveria à fila um arquivo que AINDA está sendo processado
    (um arquivo de 100 torneios passa de 15 minutos com folga), e dois passes rodariam sobre o
    mesmo conteúdo ao mesmo tempo. O dano seria limitado, porque o segundo veria tudo como
    duplicado, mas é o tipo de corrida que só aparece com o usuário grande -- justamente quem
    não pode ser o cobaia.

    Quem está vivo mantém a própria vez; só quem morreu a perde. Chamado por torneio, o que
    também alimenta o "11 de 18" da tela sem uma segunda consulta.
    """
    from database.repositories import _adapt
    conn = get_conn()
    try:
        if gravados is None:
            conn.execute(_adapt(
                "UPDATE uploads_recebidos SET iniciado_em=%s WHERE id=?" % now_sql()),
                (recibo_id,))
        else:
            conn.execute(_adapt(
                "UPDATE uploads_recebidos SET iniciado_em=%s, torneios_gravados=? "
                "WHERE id=?" % now_sql()), (int(gravados), recibo_id))
        conn.commit()
    finally:
        conn.close()


def em_espera_por_cota(user_id: int) -> int:
    """Quantos arquivos deste jogador estão parados esperando a cota virar."""
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        return int(dict(conn.execute(_adapt(
            "SELECT COUNT(*) AS n FROM uploads_recebidos WHERE user_id=? AND status=?"),
            (user_id, AGUARDANDO_COTA)).fetchone())['n'])
    finally:
        conn.close()


def bytes_em_aberto(user_id: int) -> int:
    """Soma de `bytes_total` dos recibos deste jogador cujo conteudo ainda esta guardado."""
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        marcas = ','.join('?' * len(STATUS_EM_ABERTO))
        r = conn.execute(_adapt(
            "SELECT COALESCE(SUM(bytes_total), 0) AS b FROM uploads_recebidos "
            "WHERE user_id=? AND status IN (%s)" % marcas),
            (user_id,) + tuple(STATUS_EM_ABERTO)).fetchone()
        return int(dict(r)['b'] or 0)
    finally:
        conn.close()


def pausar_por_cota(recibo_id: int, conteudo_restante: str, gravados: int, ja_estavam: int,
                    com_erro: int, detalhe=None) -> None:
    """O teto mensal acabou no meio do arquivo: guarda o que FALTA e para.

    ── Por que reescrever o conteúdo ─────────────────────────────────────────────────────────

    O recibo passa a guardar **só os torneios que ainda não entraram**. Três ganhos, e o
    primeiro é o que importa: retomar não reprocessa o que já está lá (e reprocessar 30 torneios
    para chegar no 31º gastaria a janela inteira do worker). Depois: o armazenamento encolhe a
    cada retomada. E o "torneios_no_arquivo" continua sendo o do arquivo ORIGINAL, porque é isso
    que a tela precisa dizer ("30 de 200").

    ── Por que não é `erro` nem `concluido` ──────────────────────────────────────────────────

    Medido antes desta mudança, com teto de 3 e arquivo de 5: o recibo dizia `concluido` com
    "2 com erro" e os bytes eram APAGADOS. Ou seja, o jogador lia que algo quebrou (não quebrou,
    ele bateu o teto) e perdia os dois torneios, tendo que lembrar de reenviar o arquivo no mês
    seguinte -- exatamente o que separar receber de processar existia para acabar.
    """
    from database.repositories import _adapt
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "UPDATE uploads_recebidos SET status=?, conteudo=?, torneios_gravados=?, "
            "torneios_ja_estavam=?, torneios_com_erro=?, detalhe=?, erro=NULL, "
            "iniciado_em=NULL, tentativas=0 WHERE id=?"),
            (AGUARDANDO_COTA, conteudo_restante, int(gravados), int(ja_estavam),
             int(com_erro),
             json.dumps(detalhe, ensure_ascii=False) if detalhe is not None else None,
             recibo_id))
        conn.commit()
    finally:
        conn.close()


def reivindicar_com_cota_liberada():
    """Um recibo parado por cota cujo jogador VOLTOU a ter cota. None quando não há.

    A cota vira sozinha no primeiro dia do mês (`_maybe_reset_quota`, preguiçoso na leitura), e
    também vira quando o jogador faz upgrade -- e este caminho pega os dois sem saber a
    diferença, porque ele pergunta "tem cota agora?" em vez de olhar o calendário.

    A pergunta é feita pela MESMA função que a rota usa (`get_quota_status`), senão teríamos
    duas noções de "tem cota" e a que mora aqui seria a que ninguém conferiria.
    """
    _tabela()
    from database.repositories import _adapt, get_quota_status
    conn = get_conn()
    try:
        cands = [dict(x) for x in conn.execute(_adapt(
            "SELECT id, user_id FROM uploads_recebidos WHERE status=? "
            "ORDER BY recebido_em, id"), (AGUARDANDO_COTA,)).fetchall()]
    finally:
        conn.close()
    for cand in cands:
        try:
            st = get_quota_status(cand['user_id'])
            limite = st['limits'].get('tournaments')
            if limite is not None and st['tournaments_used'] >= limite:
                continue                     # ainda sem vaga
        except Exception:
            log.exception("cota do usuario %s", cand['user_id'])
            continue
        conn = get_conn()
        try:
            cur = conn.execute(_adapt(
                "UPDATE uploads_recebidos SET status=?, iniciado_em=%s, "
                "tentativas=tentativas+1 WHERE id=? AND status=?" % now_sql()),
                (PROCESSANDO, cand['id'], AGUARDANDO_COTA))
            if not int(getattr(cur, 'rowcount', 0) or 0):
                conn.rollback()
                continue
            conn.commit()
            d = _linha(conn, cand['id'])
            raw = conn.execute(_adapt(
                "SELECT conteudo FROM uploads_recebidos WHERE id=?"), (cand['id'],)).fetchone()
            d['conteudo'] = dict(raw)['conteudo'] if raw else None
            return d
        finally:
            conn.close()
    return None


def registrar_divisao(recibo_id: int, torneios_no_arquivo: int) -> None:
    """Quantos torneios o arquivo tem. Gravado ANTES de processar, para a tela poder dizer
    "11 de 18" em vez de só "processando".

    Grava **só na primeira vez** (`IS NULL`), e isso não é detalhe: quando um recibo pausado por
    cota é retomado, o worker divide apenas o que FALTA. Sobrescrever aqui faria o total encolher
    a cada retomada, e a tela passaria de "30 de 200" para "30 de 170" -- número que mente sobre
    o arquivo que o jogador mandou.
    """
    from database.repositories import _adapt
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "UPDATE uploads_recebidos SET torneios_no_arquivo=? "
            "WHERE id=? AND torneios_no_arquivo IS NULL"),
            (int(torneios_no_arquivo), recibo_id))
        conn.commit()
    finally:
        conn.close()


def concluir(recibo_id: int, gravados: int, ja_estavam: int, com_erro: int,
             detalhe=None, erro: str | None = None) -> None:
    """Fecha o recibo e APAGA os bytes.

    Zerar `conteudo` não é economia de disco por capricho: sem isso o banco guardaria duas
    vezes o mesmo texto, porque cada torneio processado já grava o seu em `tournaments.raw_text`.
    """
    from database.repositories import _adapt
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "UPDATE uploads_recebidos SET status=?, conteudo=NULL, torneios_gravados=?, "
            "torneios_ja_estavam=?, torneios_com_erro=?, detalhe=?, erro=?, "
            "concluido_em=%s WHERE id=?" % now_sql()),
            (ERRO if erro else CONCLUIDO, int(gravados), int(ja_estavam), int(com_erro),
             json.dumps(detalhe, ensure_ascii=False) if detalhe is not None else None,
             erro, recibo_id))
        conn.commit()
    finally:
        conn.close()
