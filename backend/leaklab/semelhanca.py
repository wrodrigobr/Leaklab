# -*- coding: utf-8 -*-
"""Veredito POR SEMELHANCA: o que uma arvore ja resolvida de board PARECIDO diria sobre a
decisao, enquanto o solver nao resolve o spot exato (AY-28 passo 2, 08/09/2026).

-- Como funciona ------------------------------------------------------------------------------

1. A decisao ganha uma `assinatura` (leaklab.assinatura_do_spot): rua, posicao, faixa de
   stack, faixa de aposta, textura do board e relacao da mao com ele. A parte SEM a mao e a
   assinatura de board.
2. Vizinhos = arvores resolvidas (gto_tree_strategies) cujo spot tem a mesma assinatura de
   board. Chegamos a elas pelas decisoes que ja tem no: `decisions.spot_assinatura` -> no ->
   `tree_hash`.
3. Em cada arvore vizinha, olhamos as maos que tem a MESMA relacao com aquele board (top pair
   com flush draw, por exemplo) e tiramos a media ponderada (pelo peso da mao no range) das
   frequencias por FAMILIA de acao (check, bet, call, raise, fold, allin). O tamanho da aposta
   nao entra: a arvore vizinha pode ter outro sizing.
4. A media simples entre as arvores vizinhas e a estrategia por semelhanca. Dela saem a acao
   recomendada, a frequencia da jogada e o rotulo (mesma regua de card_verdict.label_for_freq).

-- O que se grava e por que ------------------------------------------------------------------

`vereditos_por_semelhanca` guarda o veredito provisorio de cada decisao SEM no no momento do
upload. Quando o exato chega (gancho de reconciliacao apos a fila drenar), a linha ganha a
comparacao: acao igual, erro/nao-erro igual, rotulo igual. E dessa comparacao que sai a curva do
admin e o criterio de saida do passo 3 (>= 85% de acordo erro/nao-erro com >= 3 vizinhos por duas
semanas). NADA daqui chega ao jogador neste passo.

Medido em prod em 08/09 (leave-one-out, 896 decisoes): acao igual 75%, erro/nao-erro 79%,
rotulo 60%. Quem confia num numero destes sem a curva viva esta apostando; por isso a tabela.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Optional

from leaklab.assinatura_do_spot import relacao_da_mao
from leaklab.card_verdict import label_for_freq, norm_action

log = logging.getLogger(__name__)

#: acima disto a arvore nao e mais consultada: 8 vizinhos ja estabilizam a media (medicao 08/09)
MAX_VIZINHOS = 8
#: abaixo disto a jogada conta como ERRO (mesma fronteira de label_for_freq: < 0.30 = desvio)
FREQ_DE_ERRO = 0.30


def familia(acao) -> str:
    """'bet_75pct' -> 'bet', 'raise_2.5bb' -> 'raise', 'jam'/'shove'/'all-in' -> 'allin'.
    A arvore vizinha pode ter outro sizing, entao a comparacao e por familia."""
    a = norm_action(acao)
    for f in ('raise', 'bet', 'call', 'check', 'fold', 'allin'):
        if a.startswith(f):
            return f
    return a


def assinatura_de_board(assinatura_completa: Optional[str]) -> Optional[str]:
    """'flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado|top_pair-...' -> os 5 primeiros campos."""
    if not assinatura_completa:
        return None
    partes = assinatura_completa.split('|')
    return '|'.join(partes[:5]) if len(partes) >= 5 else None


def relacao_da_assinatura(assinatura_completa: Optional[str]) -> Optional[str]:
    partes = (assinatura_completa or '').split('|')
    return partes[5] if len(partes) >= 6 else None


def estrategia_por_relacao(arvore: dict) -> dict:
    """{relacao: {familia: freq}} de UMA arvore: media ponderada pelo peso das maos com a mesma
    relacao com o board da arvore. Calculado uma vez por arvore e guardado em gto_tree_relacoes."""
    board = arvore['board']
    acoes = [familia(a) for a in arvore['actions']]
    acc: dict = defaultdict(lambda: defaultdict(float))
    peso: dict = defaultdict(float)
    for h in arvore['hand_table'] or []:
        rel = relacao_da_mao(board, h.get('hand'))
        if not rel:
            continue
        w = float(h.get('weight') or 0)
        freqs = h.get('freqs') or []
        if w <= 0 or len(freqs) != len(acoes):
            continue
        peso[rel] += w
        for fam, f in zip(acoes, freqs):
            acc[rel][fam] += w * float(f)
    return {rel: {fam: round(v / peso[rel], 4) for fam, v in fams.items()}
            for rel, fams in acc.items() if peso[rel] > 0}


def combinar(estrategias: list) -> Optional[dict]:
    """Media simples das estrategias (uma por arvore vizinha) por familia de acao."""
    if not estrategias:
        return None
    acc: dict = defaultdict(float)
    for e in estrategias:
        for fam, f in e.items():
            acc[fam] += float(f)
    n = len(estrategias)
    return {fam: round(v / n, 4) for fam, v in acc.items()}


def veredito(estrategia: Optional[dict], acao_jogada) -> Optional[dict]:
    """{acao, freq_jogada, rotulo} a partir da estrategia combinada; None sem estrategia."""
    if not estrategia:
        return None
    acao = max(estrategia, key=estrategia.get)
    jogada = familia(acao_jogada)
    freq = float(estrategia.get(jogada, 0.0))
    return {'acao': acao, 'freq_jogada': round(freq, 4), 'rotulo': label_for_freq(freq)}


# -- Banco ------------------------------------------------------------------------------------

def _json(v):
    return json.loads(v) if isinstance(v, str) else v


def _relacoes_da_arvore(conn, tree_hash: str) -> Optional[dict]:
    """Le (ou calcula e guarda) a estrategia por relacao da arvore. None se a arvore nao existe."""
    from database.repositories import _adapt, _fetchone
    row = _fetchone(conn, _adapt("SELECT relacoes_json FROM gto_tree_relacoes WHERE tree_hash = ?"), (tree_hash,))
    if row and row['relacoes_json']:
        try:
            return _json(row['relacoes_json'])
        except ValueError:
            pass
    t = _fetchone(conn, _adapt("SELECT board, actions, hand_table FROM gto_tree_strategies WHERE tree_hash = ?"), (tree_hash,))
    if not t:
        return None
    try:
        arvore = {'board': _json(t['board']), 'actions': _json(t['actions']), 'hand_table': _json(t['hand_table'])}
    except ValueError:
        return None
    rel = estrategia_por_relacao(arvore)
    # INSERT OR IGNORE, e sem DELETE antes (08/09, erro em producao): dois uploads simultaneos
    # leem o cache vazio para a MESMA arvore e os dois tentam gravar — o segundo estourava
    # `UniqueViolation` em `gto_tree_relacoes_pkey` e derrubava os provisorios do torneio
    # inteiro. Ganhar ou perder a corrida nao muda nada aqui: `estrategia_por_relacao` e funcao
    # pura da arvore, entao as duas gravariam o MESMO conteudo. O DELETE saiu junto porque so
    # servia para reescrever o identico; se um dia a formula mudar, a invalidacao tem de ser
    # explicita (versao na linha), nao um delete que abre janela de corrida.
    #
    # Continua SEM try/except: erro de cache aqui e bug e tem de aparecer no log. Na
    # homologacao foi assim que apareceu a tabela de chave natural fora de `_NO_ID_TABLES`.
    conn.execute(_adapt("INSERT OR IGNORE INTO gto_tree_relacoes (tree_hash, relacoes_json, n_relacoes) VALUES (?, ?, ?)"),
                 (tree_hash, json.dumps(rel), len(rel)))
    return rel


def arvores_vizinhas(conn, ass_board: str, excluir_tree_hash: Optional[str] = None) -> list:
    """tree_hash das arvores resolvidas cujo spot tem esta assinatura de board (mais recentes
    primeiro), no maximo MAX_VIZINHOS. Chega pelas decisoes que ja tem no."""
    from database.repositories import _adapt, _fetchall
    rows = _fetchall(conn, _adapt("""
        SELECT n.tree_hash, MAX(n.created_at) AS em
        FROM decisions d
        JOIN gto_nodes n ON n.spot_hash = d.spot_hash
        JOIN gto_tree_strategies s ON s.tree_hash = n.tree_hash
        WHERE d.spot_assinatura LIKE ? AND n.tree_hash IS NOT NULL
        GROUP BY n.tree_hash ORDER BY em DESC
    """), (ass_board + '|%',)) or []
    out = []
    for r in rows:
        th = r['tree_hash']
        if th and th != excluir_tree_hash and th not in out:
            out.append(th)
        if len(out) >= MAX_VIZINHOS:
            break
    return out


def estrategia_por_semelhanca(conn, assinatura_completa: str, excluir_tree_hash: Optional[str] = None,
                              memo: Optional[dict] = None) -> tuple:
    """(estrategia combinada ou None, n vizinhos usados) para uma assinatura completa.
    `memo`: cache por chamada (um torneio) de vizinhos por assinatura de board e de relacoes por
    arvore, para nao repetir a mesma consulta a cada decisao do mesmo board."""
    ass_board = assinatura_de_board(assinatura_completa)
    rel = relacao_da_assinatura(assinatura_completa)
    if not ass_board or not rel:
        return None, 0
    memo = memo if memo is not None else {}
    viz_key = ('viz', ass_board, excluir_tree_hash)
    if viz_key not in memo:
        memo[viz_key] = arvores_vizinhas(conn, ass_board, excluir_tree_hash)
    usadas = []
    for th in memo[viz_key]:
        if ('arv', th) not in memo:
            memo[('arv', th)] = _relacoes_da_arvore(conn, th)
        relacoes = memo[('arv', th)]
        if relacoes and rel in relacoes:
            usadas.append(relacoes[rel])
    return combinar(usadas), len(usadas)


def gravar_provisorios(tournament_id: int) -> int:
    """Para cada decisao pos-flop do torneio SEM no exato e com assinatura, grava o veredito
    provisorio por semelhanca (se houver vizinho). Idempotente: refaz as linhas do torneio que
    ainda nao foram comparadas. Devolve quantas linhas gravou."""
    from database.schema import get_conn
    from database.repositories import _adapt, _fetchall
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT d.id, d.spot_assinatura, d.action_taken
            FROM decisions d
            LEFT JOIN gto_nodes n ON n.spot_hash = d.spot_hash
            WHERE d.tournament_id = ? AND d.street <> 'preflop' AND d.spot_assinatura IS NOT NULL
              AND n.spot_hash IS NULL
        """), (tournament_id,)) or []
        gravadas = 0
        memo: dict = {}
        for r in rows:
            estrategia, n = estrategia_por_semelhanca(conn, r['spot_assinatura'], memo=memo)
            v = veredito(estrategia, r['action_taken'])
            if not v:
                continue
            conn.execute(_adapt("DELETE FROM vereditos_por_semelhanca WHERE decision_id = ? AND comparado_em IS NULL"), (r['id'],))
            conn.execute(_adapt("""
                INSERT INTO vereditos_por_semelhanca
                    (decision_id, tournament_id, assinatura, vizinhos, acao, freq_jogada, rotulo, estrategia_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """), (r['id'], tournament_id, r['spot_assinatura'], n, v['acao'], v['freq_jogada'], v['rotulo'], json.dumps(estrategia)))
            gravadas += 1
        conn.commit()
        return gravadas
    finally:
        conn.close()


def comparar_com_exato(tournament_id: int) -> int:
    """Depois que o exato chegou (decisions.gto_* preenchido pelo resync), compara cada veredito
    provisorio ainda aberto do torneio com ele. Devolve quantas linhas foram comparadas.

    erro = frequencia da jogada abaixo de FREQ_DE_ERRO, nos dois lados; acao = familia da acao
    recomendada; rotulo = label_for_freq dos dois lados. Nunca reabre linha ja comparada."""
    from database.schema import get_conn
    from database.repositories import _adapt, _fetchall
    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT v.id, v.acao, v.freq_jogada, v.rotulo, d.gto_action, d.gto_played_freq, d.gto_label
            FROM vereditos_por_semelhanca v
            JOIN decisions d ON d.id = v.decision_id
            WHERE v.tournament_id = ? AND v.comparado_em IS NULL
              AND d.gto_action IS NOT NULL AND d.gto_played_freq IS NOT NULL
        """), (tournament_id,)) or []
        n = 0
        for r in rows:
            exato_freq = float(r['gto_played_freq'])
            exato_rotulo = r['gto_label'] or label_for_freq(exato_freq)
            acao_igual = familia(r['gto_action']) == familia(r['acao'])
            erro_igual = (exato_freq < FREQ_DE_ERRO) == (float(r['freq_jogada']) < FREQ_DE_ERRO)
            rotulo_igual = exato_rotulo == r['rotulo']
            conn.execute(_adapt("""
                UPDATE vereditos_por_semelhanca
                   SET exato_acao = ?, exato_freq_jogada = ?, exato_rotulo = ?,
                       acao_igual = ?, erro_igual = ?, rotulo_igual = ?, comparado_em = CURRENT_TIMESTAMP
                 WHERE id = ?
            """), (r['gto_action'], exato_freq, exato_rotulo, bool(acao_igual), bool(erro_igual), bool(rotulo_igual), r['id']))
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()
