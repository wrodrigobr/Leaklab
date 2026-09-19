# -*- coding: utf-8 -*-
"""AY-29b: re-solve do acervo ANTIGO com o assento efetivo, em lotes, so com o solver ocioso.

── O pedido (19/09) ──────────────────────────────────────────────────────────────────────────

O dono, depois de aprovar o conserto para frente: "pode criar uma rotina de resolve de spots
antigos incluindo 300 spots sempre que o solver estiver ocioso".

── O que fica errado nas maos antigas, e o que NAO fica ────────────────────────────────────

O conserto do AY-29 vale para spot NOVO. O que ja esta gravado segue sendo servido pelo no antigo,
via o degrau legado da cascata do `lookup_gto`. Medido no solver de producao, 10 spots: a
recomendacao desloca ~10 pontos percentuais (maximo 21,7) e em 1 de 10 a ACAO troca. Mas o
VEREDITO muda em 2 de 1.431 decisoes, em direcoes opostas. **O rotulo esta certo e a porcentagem
ao lado dele nao** -- e a porcentagem e o que o jogador le.

── Por que reparsear a mao, em vez de montar o payload da linha ───────────────────────────────

`potType`, `preflopOpener` e `preflop3bettor` NAO existem em `decisions`: moram no contexto do
spot, que so o pipeline tem. Montar da linha (como faz o
`scripts/reenfileirar_postflop_sem_cobertura.py`, onde e aceitavel porque la a decisao nao tem
cobertura NENHUMA) cairia no ramo legado do `resolve_solver_ranges`: o range capturado de 168
chars vira o generico de 71, e o no novo sairia PIOR que o antigo. Tres medicoes minhas falharam
o controle antes de eu entender isto.

Entao o lote reparseia o `raw_text` do torneio e usa `_enfileirar_spot_da_decisao`, o MESMO
caminho do upload -- que ja traduz o assento e ja carrega o contexto.

── Por que PORAO (prioridade 0) e nao um "modo ocioso" proprio ────────────────────────────────

A fila ja ordena por `priority DESC`. O lote de import usa 1 e a doutrina esta escrita la:
"qualquer spot organico fura o lote inteiro; o lote so consome capacidade ociosa". Este reparo usa
0, abaixo ate daquele. Somado ao gatilho (so enfileira quando a fila esta VAZIA), o pior caso para
um jogador e esperar UM solve terminar, nunca o lote.

── Desligado por padrao ──────────────────────────────────────────────────────────────────────

`REPARO_ASSENTO_ENABLED=1` liga. Vale a mesma razao do win-back: trabalho de fundo que consome
recurso compartilhado nao comeca sozinho num deploy. Ligar e uma env no host mais restart do
container, sem deploy.
"""
from __future__ import annotations

import logging
import os
from typing import List

from database.schema import USE_POSTGRES, get_conn

log = logging.getLogger(__name__)

#: Quantos spots por lote. O numero e do dono.
TETO_POR_LOTE = 300

#: Abaixo do lote de import (1), que ja e o porao. Ver `gto_solver._priority`.
PRIORIDADE_DO_PORAO = 0

#: Quantos torneios olhar por lote. Cada um rende poucas dezenas de spots com assento trocado;
#: cinco cobrem o teto com folga e mantem o SELECT barato.
TORNEIOS_POR_LOTE = 5

#: Quanto esperar depois de um lote que NAO achou nada.
#:
#: O consumidor chama isto a cada 60s com a fila vazia. A consulta de pendentes varre as decisoes
#: pos-flop (o assento sai de um CASE, que nenhum indice cobre) -- 27 mil linhas so em dev. Uma
#: varredura por minuto, para sempre depois que o backlog acabar, mantem o compute do Neon
#: ACORDADO, e ele e cobrado por isso (capado em 0,25-1 CU). O reparo existe para consumir sobra,
#: nao para criar despesa por outro caminho: seria trocar o box pago do burst por conta de banco.
INTERVALO_SEM_TRABALHO_S = 6 * 3600

#: Relogio monotonico da proxima varredura permitida. Por PROCESSO, de proposito: o consumidor e
#: um so (`run_solver_consumer.py`), e persistir isso em banco seria mais uma escrita por tick
#: para economizar uma leitura por tick.
_proxima_varredura = 0.0

#: ── A REGRA DA CARONA (pedido do dono, 19/09) ─────────────────────────────────────────────
#:
#: "eu havia esquecido do neon... nao podemos deixa-lo ligado, vai gerar um custo alto."
#:
#: O intervalo acima resolve a varredura ociosa, e so metade do problema. Enquanto o reparo
#: RODA, ele mantem o Neon acordado igual: 300 solves gravando nos, depois mais 300, ate os ~5
#: mil acabarem. Seriam horas de compute que nao existiriam sem o reparo -- e o Neon e cobrado
#: por compute, capado em 0,25-1 CU, com escala a zero quando ninguem usa.
#:
#: Entao o reparo PEGA CARONA: so enfileira lote quando houve trabalho ORGANICO recente, ou seja
#: quando o banco ja estaria acordado de qualquer forma. Sem jogador por perto, ele dorme.
#:
#: A ancora e a atividade ORGANICA, nunca a do proprio reparo. Ancorar na atividade da fila em
#: geral faria o lote se auto-sustentar: ele enfileira, a fila fica movimentada, ele acha que ha
#: movimento e enfileira de novo, para sempre.
JANELA_DE_CARONA_S = 15 * 60

_ultima_atividade_organica = 0.0


def marcar_atividade_organica() -> None:
    """Chamado pelo consumidor quando ha spot de JOGADOR na fila. E o que abre a janela da carona."""
    global _ultima_atividade_organica
    import time as _t
    _ultima_atividade_organica = _t.monotonic()


def pode_pegar_carona() -> bool:
    """True quando o banco ja estaria acordado por causa de trabalho de alguem."""
    import time as _t
    return (_t.monotonic() - _ultima_atividade_organica) <= JANELA_DE_CARONA_S

_CRIADA = False


def _stmts(postgres: bool) -> List[str]:
    """DDL nas duas gramaticas. A tabela e o PROGRESSO do reparo: sem ela, cada rodada
    reparsearia os mesmos torneios para descobrir que nao ha o que fazer."""
    if postgres:
        return ["""
            CREATE TABLE IF NOT EXISTS reparo_assento_torneios (
                tournament_id INTEGER PRIMARY KEY,
                spots         INTEGER NOT NULL DEFAULT 0,
                feito_em      TIMESTAMP NOT NULL DEFAULT NOW()
            )"""]
    return ["""
        CREATE TABLE IF NOT EXISTS reparo_assento_torneios (
            tournament_id INTEGER PRIMARY KEY,
            spots         INTEGER NOT NULL DEFAULT 0,
            feito_em      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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


def ligado() -> bool:
    return os.environ.get('REPARO_ASSENTO_ENABLED', '0').lower() in ('1', 'true', 'yes')


def torneios_pendentes(limite: int = TORNEIOS_POR_LOTE) -> List[int]:
    """Torneios com decisao pos-flop cujo assento MUDA na traducao e que ainda nao foram feitos.

    O filtro do assento sai do `sql_assento_chart()`, que monta o CASE a partir do mesmo
    `_mapa_da_mesa` do motor -- nao ha segunda tabela de assento aqui.
    """
    _tabela()
    from database.repositories import _adapt, sql_assento_chart
    conn = get_conn()
    try:
        sql = ("""
            SELECT DISTINCT d.tournament_id AS tid
              FROM decisions d
              JOIN tournaments t ON t.id = d.tournament_id
             WHERE d.street IN ('flop','turn','river')
               AND d.position IS NOT NULL
               AND d.num_players IS NOT NULL
               AND t.raw_text IS NOT NULL
               AND %s <> d.position
               AND NOT EXISTS (SELECT 1 FROM reparo_assento_torneios r
                                WHERE r.tournament_id = d.tournament_id)
             ORDER BY d.tournament_id
             LIMIT ?""" % sql_assento_chart())
        return [int(dict(r)['tid']) for r in conn.execute(_adapt(sql), (int(limite),)).fetchall()]
    finally:
        conn.close()


def _marca_feito(tournament_id: int, spots: int) -> None:
    from database.repositories import _adapt
    conn = get_conn()
    try:
        # Sem ON CONFLICT: o torneio so entra aqui uma vez, e um erro de duplicata e informacao
        # (alguem chamou duas vezes em paralelo), nao ruido a engolir.
        try:
            conn.execute(_adapt(
                "INSERT INTO reparo_assento_torneios (tournament_id, spots) VALUES (?, ?)"),
                (int(tournament_id), int(spots)))
            conn.commit()
        except Exception:
            conn.rollback()
            log.warning("reparo de assento: torneio %s ja estava marcado", tournament_id)
    finally:
        conn.close()


def enfileirar_lote(limite: int = TETO_POR_LOTE) -> dict:
    """Reparseia os proximos torneios pendentes e enfileira ate `limite` spots no PORAO.

    Devolve {'torneios': n, 'spots': n, 'pendentes_depois': n}. Nunca levanta: isto roda dentro
    do loop do consumidor, e derrubar o consumidor para reparar acervo antigo seria trocar o
    que funciona pelo que e opcional.
    """
    from database.repositories import get_decisions
    from leaklab.parser import parse_hand_history
    from leaklab.pipeline import build_decision_inputs_for_hand
    from leaklab.pareamento_decisoes import BaldeDeDecisoes
    from leaklab.preflop_gto_ranges import _mapa_da_mesa

    global _proxima_varredura
    import time as _time

    resumo = {'torneios': 0, 'spots': 0, 'pendentes_depois': 0, 'dormindo': False,
              'sem_carona': False}
    if not pode_pegar_carona():
        # Ninguem por perto: acordar o Neon so para reparar acervo antigo e criar despesa por
        # outro caminho. O reparo espera a proxima vez que o banco estiver acordado por si.
        resumo['sem_carona'] = True
        return resumo
    if _time.monotonic() < _proxima_varredura:
        # Ja se sabe que nao ha o que fazer, e a varredura custa compute do Neon. Volta sem
        # tocar no banco.
        resumo['dormindo'] = True
        return resumo
    try:
        from api.app import _enfileirar_spot_da_decisao
    except Exception:
        log.exception("reparo de assento: nao consegui importar o enfileirador")
        return resumo

    def _norm(a):
        if not a:
            return ''
        a = a.rstrip('s') if a.endswith('s') else a
        return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a

    try:
        pendentes = torneios_pendentes()
    except Exception:
        log.exception("reparo de assento: falha ao listar torneios pendentes")
        return resumo
    if not pendentes:
        # Nada a reparar. Dorme: sem isto, a varredura acima roda a cada 60s para sempre.
        _proxima_varredura = _time.monotonic() + INTERVALO_SEM_TRABALHO_S
        log.info("reparo de assento: nada pendente, proxima varredura em %.0fh",
                 INTERVALO_SEM_TRABALHO_S / 3600.0)
        return resumo

    conn = get_conn()
    try:
        from database.repositories import _adapt
        # A lista vem de `torneios_pendentes()`, que devolve inteiros — daí o IN interpolado com
        # `int()` por item. Interpolar uma lista VAZIA produziria `IN ()`, que é erro de sintaxe
        # nos dois bancos; o `return` acima é o que impede, e não um `or` no fim da expressão
        # (que a precedência de operador tornaria inofensivo, como estava).
        sql = ("SELECT id, raw_text FROM tournaments WHERE id IN (%s)"
               % ','.join(str(int(i)) for i in pendentes))
        brutos = {int(dict(r)['id']): dict(r)['raw_text']
                  for r in conn.execute(_adapt(sql), ()).fetchall()}
    except Exception:
        log.exception("reparo de assento: falha ao ler os torneios pendentes")
        return resumo
    finally:
        conn.close()

    for tid, raw in brutos.items():
        if resumo['spots'] >= limite:
            break
        do_torneio = 0
        try:
            linhas = get_decisions(tid)
            balde = BaldeDeDecisoes(linhas, lambda d: (_norm(d.get('street', '')),
                                                       _norm(d.get('action_taken', ''))))
            for hand in parse_hand_history(raw or ''):
                for di in build_decision_inputs_for_hand(hand):
                    if resumo['spots'] >= limite:
                        break
                    if di.get('street') not in ('flop', 'turn', 'river'):
                        continue
                    linha = balde.proxima((_norm(di['street']),
                                           _norm(di.get('player_action', '') or '')))
                    if not linha:
                        continue
                    n = int(linha.get('num_players') or 0)
                    if not (2 <= n <= 10):
                        continue
                    cru = (linha.get('position') or '').upper()
                    if _mapa_da_mesa(n).get(cru, cru) == cru:
                        continue            # o assento nao muda: nada a reparar aqui
                    if _enfileirar_spot_da_decisao(di, float(linha.get('facing_bet') or 0), tid,
                                                   prioridade=PRIORIDADE_DO_PORAO):
                        do_torneio += 1
                        resumo['spots'] += 1
        except Exception:
            log.exception("reparo de assento: falha no torneio %s", tid)
            continue
        _marca_feito(tid, do_torneio)
        resumo['torneios'] += 1

    try:
        resumo['pendentes_depois'] = len(torneios_pendentes(limite=1000))
    except Exception:
        resumo['pendentes_depois'] = -1
    if resumo['spots']:
        log.info("reparo de assento: %s spots de %s torneios enfileirados no porao "
                 "(torneios pendentes: %s)",
                 resumo['spots'], resumo['torneios'], resumo['pendentes_depois'])
    return resumo
