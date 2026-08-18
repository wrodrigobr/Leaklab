"""mao_completa.py — drill de MÃO INTEIRA heads-up (Fase 3 do catálogo).

Replay de mão REAL do acervo compartilhado, decisão por street. Medido em prod (17/08):
673 mãos 100% HU no postflop; **167 jogáveis** na régua estrita (hand-aware em toda street);
224 a UMA street de virarem jogáveis via fila de solve.

## Regras que não são opcionais

- **HU pela coluna do consumidor** (`n_active_opponents == 1`), nunca por `num_players`:
  a primeira medição usou num_players==2 e achou 56 mãos onde havia 673 — número em
  contradição é critério errado, não acervo menor.
- **Anonimização por construção** (decidido 02/08): o payload nasce DO ZERO — posição, stack
  em bb, board, linha de ação. NUNCA por reuso do payload do replayer, que carrega
  tournament_id, nome do torneio, data e nicks. `decision_ref` (id opaco de decisions) pode
  viajar; test_mao_completa varre o JSON servido e FALHA se achar identificador.
- **Uma porta por veredito**: cada street é jogável sse `_resolve_best_action_from_node`
  (a porta do Ghost/replay) devolve source='gto_hand'; a correção é `grade_drill_action`
  (fonte única, pura). O resolver entra por INJEÇÃO (o chamador em api/app.py passa as
  funções) para este módulo não importar a camada de cima.
- Sem SRS aqui: SRS é do Ghost do dono da mão. O progresso registra em
  training_skill_progress, categoria 'fh:full_hand'.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Callable, Optional

from database.schema import get_conn
from database.repositories import _adapt

_POSTFLOP = ('flop', 'turn', 'river')

# Campos que PODEM aparecer no payload servido. Whitelist, não blacklist: campo novo no
# banco não vaza por esquecimento. O teste de anonimização confere contra esta lista.
CAMPOS_PERMITIDOS_PASSO = {
    'ref', 'street', 'position', 'vs_position', 'stack_bb', 'facing_bb', 'pot_bb',
    'board', 'board_cards', 'options', 'narracao',
}

_SQL_CANDIDATAS = """
    SELECT d.tournament_id, d.hand_id,
           COUNT(*) AS n_decisoes,
           SUM(CASE WHEN LOWER(d.street) != 'preflop' THEN 1 ELSE 0 END) AS n_postflop
      FROM decisions d
     GROUP BY d.tournament_id, d.hand_id
    HAVING SUM(CASE WHEN LOWER(d.street) != 'preflop'
                     AND COALESCE(d.n_active_opponents, 99) != 1 THEN 1 ELSE 0 END) = 0
       AND SUM(CASE WHEN LOWER(d.street) != 'preflop' THEN 1 ELSE 0 END) >= 1
       AND COUNT(*) >= 2
"""


def chave_opaca(tournament_id: int, hand_id: str) -> str:
    """Chave de dedup da SESSÃO. Hash, não `tid:hid`: o dedup viaja pelo cliente, e a chave
    crua seria exatamente o identificador que a anonimização proíbe de sair."""
    return hashlib.sha256(f'{tournament_id}:{hand_id}'.encode()).hexdigest()[:16]


def maos_candidatas() -> list:
    """(tournament_id, hand_id) das mãos 100% HU no postflop com ≥2 decisões. A régua
    hand-aware é cara (lookup por street) e fica para a hora de SERVIR, mão a mão."""
    with get_conn() as conn:
        rows = conn.execute(_adapt(_SQL_CANDIDATAS)).fetchall()
    return [(r['tournament_id'], r['hand_id']) for r in rows]


def _linhas_da_mao(tournament_id: int, hand_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(_adapt(
            "SELECT * FROM decisions WHERE tournament_id = ? AND hand_id = ? ORDER BY id"),
            (tournament_id, hand_id)).fetchall()
    return [dict(r) for r in rows]


def street_gradeavel_gto(d: dict, resolver: Callable) -> bool:
    """A street postflop será corrigida por GTO hand-aware — replicando TODOS os gates do
    corretor, não só o do resolver: `grade_drill_action` cai em 'heuristic' quando o gravado
    não tem `gto_action`/`gto_label`, mesmo com nó vivo. O probe em prod pegou exatamente
    isso (mãos servidas com veredito heuristic no turn) — seletor com um gate a menos que o
    consumidor é a cicatriz mais repetida do projeto."""
    if not d.get('gto_action') or (d.get('gto_label') or '') in ('', 'wizard_pending'):
        return False
    try:
        return resolver(d, return_strategy=True)[2] == 'gto_hand'
    except Exception:
        return False


def mao_jogavel(resolver: Callable, rng: Optional[random.Random] = None,
                evitar: Optional[set] = None, teto_tentativas: int = 20):
    """Sorteia uma mão candidata cujas streets postflop são TODAS gradeáveis por GTO
    hand-aware (`street_gradeavel_gto`). Devolve (linhas, chave) ou (None, None). O preflop
    não precisa de nó (a porta preflop do trainer cobre sempre)."""
    rng = rng or random
    evitar = evitar or set()
    todas = [c for c in maos_candidatas() if chave_opaca(*c) not in evitar]
    rng.shuffle(todas)
    for chave in todas[:teto_tentativas]:
        linhas = _linhas_da_mao(*chave)
        pf = [d for d in linhas if (d.get('street') or '').lower() in _POSTFLOP]
        if not pf:
            continue
        if all(street_gradeavel_gto(d, resolver) for d in pf):
            return linhas, chave
    return None, None


def _menu_da_linha(d: dict) -> list:
    """Menu pelo FACING da linha — a mesma forma que os guardas RC-5/6 exigem do nó:
    enfrentando aposta → fold/call/raise(/allin); sem aposta postflop → check/bet."""
    facing = float(d.get('facing_bet') or 0)
    street = (d.get('street') or '').lower()
    if street == 'preflop':
        return ['fold', 'call', 'raise', 'allin'] if facing > 0 else ['fold', 'call', 'raise']
    return ['fold', 'call', 'raise'] if facing > 0 else ['check', 'bet']


def montar_passos(linhas: list) -> list:
    """Passos do drill a partir das LINHAS do banco — payload construído do zero.

    PENDENTE (próximo passo da F3): enriquecer com a linha do VILÃO re-parseando
    `tournaments.raw_text` pela MESMA porta do /replay (`parse_pokerstars_file_from_text` +
    `build_decision_inputs_for_hand`) — assentos verdadeiros e narração real, com nomes
    trocados por rótulo de posição ANTES de qualquer campo entrar aqui.
    """
    from leaklab.leak_trainer import _cards_to_objs
    from leaklab.gto_utils import board_for_street

    passos = []
    for d in linhas:
        street = (d.get('street') or '').lower()
        try:
            board = d.get('board') or []
            board = json.loads(board) if isinstance(board, str) else list(board)
        except Exception:
            board = []
        board = board_for_street(board, street)
        passos.append({
            'ref': d['id'],
            'street': street,
            'position': d.get('position') or '',
            'stack_bb': float(d.get('stack_bb') or 0) or None,
            'facing_bb': float(d.get('facing_bet') or 0),
            'board': board,
            'board_cards': _cards_to_objs(board),
            'options': _menu_da_linha(d),
        })
    return passos


def _mao_parseada(tournament_id: int, hand_id: str):
    """(hand parseada, bb) da mão, re-parseando `tournaments.raw_text` pela MESMA porta do
    /replay. None quando o torneio não guarda o texto (importações antigas)."""
    from leaklab.parser import parse_pokerstars_file_from_text
    with get_conn() as conn:
        t = conn.execute(_adapt(
            "SELECT raw_text FROM tournaments WHERE id = ?"), (tournament_id,)).fetchone()
    raw = (t or {}) and t['raw_text']
    if not raw:
        return None
    try:
        hands = parse_pokerstars_file_from_text(raw)
    except Exception:
        return None
    return next((h for h in hands if str(h.hand_id) == str(hand_id)), None)


def narracao_da_mao(hand) -> dict:
    """Linha da mão por street, ANONIMIZADA na construção: hero → 'hero', todos os outros →
    'vilao' (drill é HU no postflop; no preflop os demais são fold/call de passagem). Valores
    em BB. Nunca inclui nome, seat ou id — é a única forma de o dado não vazar por esquecimento.
    """
    bb = float(hand.bb or 1) or 1
    linha: dict = {}
    for a in (hand.actions or []):
        st = (a.street or '').lower()
        quem = 'hero' if a.player == hand.hero else 'vilao'
        item = {'quem': quem, 'acao': (a.action or '').lower()}
        if a.amount is not None:
            item['valor_bb'] = round(float(a.amount) / bb, 2)
        linha.setdefault(st, []).append(item)
    return linha


def montar_mao(linhas: list, tournament_id: int, hand_id: str) -> Optional[dict]:
    """Payload completo do drill: passos + narração + cartas do herói. Construído do zero;
    o teste de anonimização varre este dict inteiro."""
    from leaklab.leak_trainer import _cards_to_objs
    passos = montar_passos(linhas)
    if len(passos) < 2:
        return None
    hand = _mao_parseada(tournament_id, hand_id)
    # Pote no ponto de cada decisão pela porta que ACERTA (`_pote_no_meio`, 99,6% vs SUMMARY;
    # `decisions.pot_size` soma cru do parser e acerta 1,2%). Pareamento por ÍNDICE com
    # guarda: os HandState são exatamente os pontos de decisão do herói, na ordem em que o
    # pipeline gravou as linhas — se as contagens divergem, nenhum pote é servido (pote
    # errado ensina pot odds errada; ausência é honesta).
    if hand:
        try:
            from leaklab.hand_state_builder import extract_decision_points
            from leaklab.street_math_engine import _pote_no_meio
            states = extract_decision_points(hand)
            bb = float(hand.bb or 0) or 0
            if bb > 0 and len(states) == len(passos):
                for passo, st in zip(passos, states):
                    if (st.street or '').lower() == passo['street']:
                        passo['pot_bb'] = round(_pote_no_meio(st) / bb, 2)
        except Exception:
            pass
    hc = (hand.hero_cards if hand else None) or (linhas[0].get('hero_cards') or '')
    hc = hc.replace(' ', '')
    mao = [hc[i:i + 2] for i in range(0, len(hc), 2)] if hc else []
    if len(mao) != 2:
        return None
    return {
        'kind': 'full_hand',
        'hero_hand': mao,
        'hero_cards': _cards_to_objs(mao),
        'narracao': narracao_da_mao(hand) if hand else {},
        'passos': passos,
        'total_passos': len(passos),
    }


def corrigir_passo(ref: int, action: str, grader: Callable, resolver_row=None) -> Optional[dict]:
    """Corrige UM passo pelo `grade_drill_action` injetado. Recarrega a linha do banco pela
    ref — a verdade nunca vem do que voltou do cliente."""
    with get_conn() as conn:
        row = conn.execute(_adapt("SELECT * FROM decisions WHERE id = ?"), (ref,)).fetchone()
    if not row:
        return None
    return grader(dict(row), action)
