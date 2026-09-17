# -*- coding: utf-8 -*-
"""O historico das maos praticadas no modo Pratica, e o relatorio sobre ele.

── O pedido (16/09) ──────────────────────────────────────────────────────────────────────────

O dono, depois de treinar: "seria interessante armazenar este treino, para ficar no historico das
ultimas maos treinadas, e ter a possibilidade de gerar um relatorio como o do gto wizard".

── Por que o VEREDITO nao vem do cliente ─────────────────────────────────────────────────────

A regua dos quatro niveis nasceu no front, e ficou la enquanto o Pratica so PINTAVA o veredito.
Gravar mudou isso: aceitar o nivel que o navegador manda faria o relatorio adulteravel, e calcular
de novo aqui criaria a segunda implementacao da mesma regra -- a regra 5 da casa, e o defeito que
este modo pagou em outra dimensao (o motor chamando `major_leak` o que o Pratica chamava de
"aceitavel", em 36,5% das combinacoes).

Entao a regua mora em `pratica_preflop.nivel_do_veredito`, o `corrigir` a aplica, e aqui so se
grava o que ele devolveu. Quem quiser mudar a regua muda um lugar, e a mesa, o placar e o
relatorio mudam juntos.

── O que NAO se grava, e por que ────────────────────────────────────────────────────────────

Mao sem veredito (`nivel` nulo) entra no historico com a coluna vazia, e nao com um chute. O
relatorio conta essas maos numa linha propria em vez de espalha-las nos quatro niveis: contar como
erro seria inventar acusacao, como acerto seria o oposto, e as duas coisas mentem no numero que o
jogador usa para medir a propria evolucao.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from database.schema import USE_POSTGRES, get_conn

log = logging.getLogger(__name__)

_CRIADA = False

#: Teto de maos devolvidas de uma vez. O historico e para OLHAR, e uma pagina grande e mais
#: latencia do Neon para uma tabela que ninguem le inteira.
LIMITE_MAXIMO = 200

#: Quantas maos o relatorio resume por padrao. O GTO Wizard resume a sessao; aqui a "sessao" nao
#: existe como entidade (o jogador abre e fecha mesas a vontade), entao o corte e por ultimas N.
ULTIMAS_PADRAO = 200


def _stmts(postgres: bool) -> List[str]:
    """DDL nas duas gramaticas, testavel sem servidor (padrao de `recepcao_de_upload`).

    `id SERIAL` de proposito: tabela sem id autoincrement teria de entrar na allowlist
    `_NO_ID_TABLES` do adaptador, e esquecer disso ja custou um INSERT que falhava SO no Postgres.

    Sem UNIQUE: praticar a MESMA mao duas vezes e o que o jogador faz de proposito quando quer
    fixar um spot, e o historico tem de mostrar as duas tentativas em ordem. A idempotencia aqui
    seria perda de dado, e nao protecao.
    """
    if postgres:
        return ["""
            CREATE TABLE IF NOT EXISTS pratica_maos (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER NOT NULL,
                mao           TEXT NOT NULL,
                posicao       TEXT,
                vs_posicao    TEXT,
                stack_bb      REAL,
                cenario       TEXT,
                resumo        TEXT,
                acao          TEXT NOT NULL,
                acao_gto      TEXT,
                freq_da_acao  REAL,
                freq_melhor   REAL,
                nivel         TEXT,
                ev_loss_bb    REAL,
                criado_em     TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
                """CREATE INDEX IF NOT EXISTS ix_pratica_maos_do_jogador
                   ON pratica_maos (user_id, id DESC)"""]
    return ["""
        CREATE TABLE IF NOT EXISTS pratica_maos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            mao           TEXT NOT NULL,
            posicao       TEXT,
            vs_posicao    TEXT,
            stack_bb      REAL,
            cenario       TEXT,
            resumo        TEXT,
            acao          TEXT NOT NULL,
            acao_gto      TEXT,
            freq_da_acao  REAL,
            freq_melhor   REAL,
            nivel         TEXT,
            ev_loss_bb    REAL,
            criado_em     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
            """CREATE INDEX IF NOT EXISTS ix_pratica_maos_do_jogador
               ON pratica_maos (user_id, id DESC)"""]


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


def _num(v):
    """Numero ou `None`. `bool` fica de fora de proposito: `True` vira 1.0 em REAL e viraria um
    custo de 1bb no relatorio."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _freqs(grade: dict, acao: str):
    """`(frequencia da acao dele, frequencia da melhor)`, no vocabulario do no.

    O `hand_freq` vem com o codigo do solver (`F`, `R2.5`, `RAI`) e a acao com o nome; a
    normalizacao e a MESMA de `pratica_preflop`, importada e nao recopiada.
    """
    from leaklab.pratica_preflop import _normaliza_acao
    freq = {k: v for k, v in (grade.get('hand_freq') or {}).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if not freq:
        return None, None
    minha = 0.0
    for k, v in freq.items():
        if _normaliza_acao(k) == _normaliza_acao(acao):
            minha = v
            break
    return round(float(minha), 4), round(float(max(freq.values())), 4)


def gravar(user_id: int, spot: dict, acao: str, grade: dict) -> Optional[int]:
    """Grava UMA mao praticada e devolve o id. `None` se nao deu para gravar.

    Nunca levanta: o jogador esta no meio de um treino de quatro mesas, e perder a resposta dele
    porque o historico falhou seria trocar um recurso novo pelo que ja funcionava.
    """
    from leaklab.pratica_preflop import resumo_do_spot
    s = spot or {}
    g = grade or {}
    try:
        _tabela()
        minha, melhor = _freqs(g, acao or '')
        try:
            resumo = resumo_do_spot(s)
        except Exception:
            log.exception('historico de pratica: resumo do spot')
            resumo = None
        conn = get_conn()
        try:
            from database.repositories import _adapt
            cur = conn.execute(_adapt(
                "INSERT INTO pratica_maos (user_id, mao, posicao, vs_posicao, stack_bb, cenario, "
                "resumo, acao, acao_gto, freq_da_acao, freq_melhor, nivel, ev_loss_bb) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"),
                (int(user_id), str(s.get('hand') or ''), s.get('position'), s.get('vs_position'),
                 _num(s.get('stack_bb')), s.get('scenario'), resumo, str(acao or ''),
                 g.get('best_action'), minha, melhor, g.get('nivel'), _num(g.get('ev_loss_bb'))))
            conn.commit()
            try:
                return int(cur.lastrowid)
            except (AttributeError, TypeError):
                return None
        finally:
            conn.close()
    except Exception:
        # LOGA e devolve None. `except: pass` aqui esconderia defeito de schema por semanas, e a
        # casa tem a cicatriz: um `except` mudo engoliu um `NameError` que so apareceu em producao.
        log.exception('historico de pratica: falha ao gravar (user=%s)', user_id)
        return None


def ultimas(user_id: int, limite: int = 50, desde_id: Optional[int] = None) -> List[dict]:
    """As maos mais recentes primeiro.

    Pagina por `desde_id` (keyset) e nao por OFFSET: com o jogador praticando enquanto olha o
    historico, OFFSET pula ou repete linha a cada pagina, porque a base se move embaixo dele.
    """
    _tabela()
    from database.repositories import _adapt
    lim = max(1, min(int(limite or 50), LIMITE_MAXIMO))
    conn = get_conn()
    try:
        if desde_id:
            sql = ("SELECT * FROM pratica_maos WHERE user_id = ? AND id < ? "
                   "ORDER BY id DESC LIMIT ?")
            args = (int(user_id), int(desde_id), lim)
        else:
            sql = "SELECT * FROM pratica_maos WHERE user_id = ? ORDER BY id DESC LIMIT ?"
            args = (int(user_id), lim)
        rows = conn.execute(_adapt(sql), args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def relatorio(user_id: int, ultimas_n: int = ULTIMAS_PADRAO) -> dict:
    """O resumo do treino: quantas maos, o placar por nivel, o custo somado, e os cortes por
    posicao e por cenario.

    ── Por que a conta e feita em PYTHON e nao em SQL ────────────────────────────────────────

    O corte e "as ultimas N maos", e em SQL isso vira subquery com LIMIT dentro de agregacao --
    que a casa ja escreveu errado uma vez no Postgres (o `%` em SQL com parametro). Sao no maximo
    200 linhas: a conta em memoria e mais barata que o risco de dialeto.

    As maos SEM veredito aparecem em `sem_avaliacao`, fora dos quatro niveis. Espalha-las seria
    inventar acusacao ou inventar acerto, e as duas mentem no numero que o jogador usa para medir
    a propria evolucao.
    """
    _tabela()
    n = max(1, min(int(ultimas_n or ULTIMAS_PADRAO), LIMITE_MAXIMO))
    maos = ultimas(user_id, limite=n)

    por_nivel = {'correta': 0, 'imprecisao': 0, 'errada': 0, 'grave': 0}
    sem_avaliacao = 0
    custo = 0.0
    por_posicao: dict = {}
    por_cenario: dict = {}

    for m in maos:
        nivel = m.get('nivel')
        alvo = por_nivel if nivel in por_nivel else None
        if alvo is None:
            sem_avaliacao += 1
        else:
            por_nivel[nivel] += 1
        ev = _num(m.get('ev_loss_bb')) or 0.0
        custo += abs(ev)

        for chave, mapa in (('posicao', por_posicao), ('cenario', por_cenario)):
            k = m.get(chave) or '?'
            d = mapa.setdefault(k, {'maos': 0, 'corretas': 0, 'bb': 0.0})
            d['maos'] += 1
            if nivel == 'correta':
                d['corretas'] += 1
            d['bb'] = round(d['bb'] + abs(ev), 3)

    julgadas = sum(por_nivel.values())
    return {
        'maos': len(maos),
        'julgadas': julgadas,
        'sem_avaliacao': sem_avaliacao,
        'por_nivel': por_nivel,
        # o acerto e sobre as JULGADAS: dividir pelo total faria a taxa cair quando o solver
        # nao respondeu, o que nao e culpa nem merito do jogador
        'acerto': round(100.0 * por_nivel['correta'] / julgadas, 1) if julgadas else None,
        'bb_perdidos': round(custo, 2),
        'bb_por_mao': round(custo / julgadas, 3) if julgadas else None,
        'por_posicao': por_posicao,
        'por_cenario': por_cenario,
    }


def apagar_do_jogador(user_id: int) -> int:
    """Apaga o historico DELE. Existe para a exclusao de usuario nao deixar orfao: a tabela
    `uploads_recebidos` ficou fora daquela lista e o achado e recente."""
    _tabela()
    from database.repositories import _adapt
    conn = get_conn()
    try:
        cur = conn.execute(_adapt("DELETE FROM pratica_maos WHERE user_id = ?"), (int(user_id),))
        conn.commit()
        return int(cur.rowcount or 0)
    finally:
        conn.close()
