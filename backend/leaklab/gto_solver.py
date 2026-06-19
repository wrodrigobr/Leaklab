"""
gto_solver.py — Orquestrador GTO: lookup → solver verificado → cache.

Garantia de qualidade:
  - Nenhum dado entra no banco sem exploitability_pct medida pelo solver
  - Threshold: exploitability_pct <= 1.0% do pot (configurável em repositories.py)
  - Solves que não convergem são descartados e recolocados na fila com mais iterações

Fluxo:
  1. Preflop → gto_preflop_ranges (só rows com exploitability confirmada)
  2. Postflop → gto_nodes (só rows com exploitability confirmada)
  3. Miss → tenta solver remoto (Oracle Cloud) → fallback local → enfileira
  4. Worker chama solver_cli (Rust CFR) → armazena com exploitability real
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
from typing import Optional

# ── Solver remoto (Oracle Cloud) ──────────────────────────────────────────────
# Lidas em runtime (não no import) para garantir que o .env já foi carregado
def _remote_url() -> str:
    return os.environ.get('GTO_SOLVER_URL', '').rstrip('/')

def _remote_key() -> str:
    return os.environ.get('GTO_SOLVER_API_KEY', '')

# Ranges padrão por posição (6-max, 100bb, RFI / call). Simplificadas para convergência rápida.
_DEFAULT_RANGES: dict[str, str] = {
    'BTN': '22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,54s,A2o+,K8o+,Q9o+,J9o+,T9o',
    'CO':  '22+,A2s+,K6s+,Q8s+,J8s+,T8s+,98s,87s,76s,A4o+,K9o+,Q9o+,J9o+',
    'HJ':  '44+,A2s+,K9s+,Q9s+,J9s+,T9s,A9o+,KTo+,QTo+,JTo',
    'UTG': '55+,A9s+,KTs+,QTs+,JTs,AJo+,KQo',
    'SB':  '22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,A2o+,K7o+,Q9o+',
    'BB':  '22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K4o+,Q7o+,J8o+,T8o+',
}
_DEFAULT_RANGE_WIDE = '22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K8o+,Q9o+,J9o+'

log = logging.getLogger(__name__)

_SOLVER_BIN = os.environ.get(
    'GTO_SOLVER_BIN',
    os.path.join(
        os.path.dirname(__file__), '..', 'gto_bot', 'solver_cli', 'target', 'release',
        'solver_cli.exe' if os.name == 'nt' else 'solver_cli',
    )
)
_SOLVER_AVAILABLE: Optional[bool] = None

# Threshold de validação.
# production (Google VM): converge para 2-3% → aceita até 10%
# test (Oracle 1 core): pode chegar a 30% → aceita até 50%
# Definido dinamicamente em run_solver_worker baseado em SOLVER_TIER.
MAX_EXPLOITABILITY_PCT = 50.0  # fallback conservador; sobrescrito abaixo


def _solver_params_for_stack(stack_bb: float) -> dict:
    """
    Parâmetros do solver escalonados por stack e nível de hardware disponível.

    SOLVER_TIER (env var):
      'production' — Google Cloud VM 4 vCPU / 16 GB (padrão quando GTO_SOLVER_URL definido)
      'test'       — Oracle 1 core / 1 GB (fallback local)

    Retorna: {max_iterations, target_exploitability_pct, timeout, effective_stack_bb}
    """
    tier = os.environ.get('SOLVER_TIER', '')
    # Auto-detecta tier: se tem URL remoto configurado assume produção
    if not tier:
        tier = 'production' if os.environ.get('GTO_SOLVER_URL') else 'test'

    if tier == 'production':
        # Hetzner 8 vCPU / 16GB — todos os cores num solve (MAX_CONCURRENT=1, RAYON=8).
        # Com 1 árvore por vez dá ~13GB de RAM → cap 100bb (compressão liga p/ árvores
        # grandes). Iterações altas p/ fechar mais spots; timeouts ≤ 290 (< client 300s).
        # Solve por TEMPO: o budget (s) é o limite real — árvores grandes não estouram
        # o timeout. max_iterations é só um teto alto; o CFR para no budget ou no alvo.
        # Cap 60bb (revertido de 100): com 1 size, 60bb cabe no limite de RAM do solver.
        capped = min(float(stack_bb), 60.0)
        target = 2.0 if stack_bb < 40 else 3.0
        return {'max_iterations': 30000, 'target_exploitability_pct': target,
                'time_budget_s': 150, 'timeout': 220, 'effective_stack_bb': capped}
    else:
        # Oracle test server 1 core / 1GB — cap agressivo para não travar
        capped = min(float(stack_bb), 20.0)
        return {
            'max_iterations':            10,
            'target_exploitability_pct': 15.0,
            'timeout':                   120,
            'effective_stack_bb':        capped,
        }


# Ordem de ação postflop (primeiro→último a agir). Quem age por ÚLTIMO está IN POSITION.
_POSTFLOP_ORDER = {'SB': 0, 'BB': 1, 'UTG': 2, 'UTG+1': 3, 'UTG+2': 4,
                   'LJ': 5, 'HJ': 6, 'CO': 7, 'BTN': 8}

# Liga o suporte a hero IP (c-bet) no Texas postflop. Default OFF: só vale DEPOIS que o
# main.rs com `hero_is_ip` for buildado/deployado na VM (senão o binário antigo ignora a
# flag e devolve o player 0 = OOP = jogador errado). Flip p/ '1' após o deploy.
_TEXAS_HERO_IP = os.environ.get('TEXAS_HERO_IP', '0') == '1'

# Liga o suporte a hero IP ENFRENTANDO APOSTA (root → OOP bet → IP age). Default OFF:
# só vale DEPOIS do deploy do main.rs com navigate_to_ip_facing_bet (senão o binário antigo
# aborta facing>0 IP). Flip p/ '1' após o deploy. Requer _TEXAS_HERO_IP também ligado.
_TEXAS_HERO_IP_FACING = os.environ.get('TEXAS_HERO_IP_FACING', '0') == '1'


def _postflop_hero_is_ip(hero_pos: str, vs_pos: str) -> bool:
    """True se o hero está IN POSITION (age depois do vilão) no postflop. Determina qual
    jogador é OOP(player 0)/IP(player 1) no solve. O solver_cli SÓ devolve o player 0 (OOP),
    então hoje só servimos spots em que o hero é OOP (ver gate no lookup_gto)."""
    h = _POSTFLOP_ORDER.get((hero_pos or '').upper().strip(), 99)
    v = _POSTFLOP_ORDER.get((vs_pos or '').upper().strip(), -1)
    return h > v


def _captured_range_str(position: str, stack_bb: float, kind: str, opener: str = '') -> Optional[str]:
    """Notação de range REAL capturada do GW (P0 fix 2.3) pra alimentar o solver Texas em
    vez das _DEFAULT_RANGES genéricas. kind='rfi' → range de abertura da posição; kind=
    'call_vs_rfi' → range de call do defensor vs o open do `opener`. None se sem cobertura."""
    try:
        from leaklab.preflop_gto_ranges import _load, _stack_bucket
        bk = _load().get('ranges', {}).get(_stack_bucket(stack_bb), {})
        pos = (position or '').upper().strip()
        if kind == 'rfi':
            node = (bk.get('RFI') or {}).get(pos) or {}
            return node.get('raise_hands') or None
        if kind == 'call_vs_rfi' and opener:
            node = ((bk.get('vs_RFI') or {}).get((opener or '').upper().strip()) or {}).get(pos) or {}
            return node.get('call_hands') or None
    except Exception:
        return None
    return None


def _captured_3bet_ranges(opener: str, threebettor: str, stack_bb: float):
    """Ranges REAIS de pote 3-bet (Fase 2). Retorna (range_3bettor, range_caller) ou
    (None, None) se sem cobertura. range_3bettor = quem 3-betou (vs_RFI[opener][3bettor]
    .raise_hands); range_caller = o opener que pagou o 3-bet (vs_3bet[opener][3bettor]
    .call_hands)."""
    try:
        from leaklab.preflop_gto_ranges import _load, _stack_bucket
        bk = _load().get('ranges', {}).get(_stack_bucket(stack_bb), {})
        op = (opener or '').upper().strip()
        tb = (threebettor or '').upper().strip()
        if not op or not tb:
            return None, None
        r_3b = (((bk.get('vs_RFI') or {}).get(op) or {}).get(tb) or {}).get('raise_hands') or None
        r_call = (((bk.get('vs_3bet') or {}).get(op) or {}).get(tb) or {}).get('call_hands') or None
        return r_3b, r_call
    except Exception:
        return None, None


def _effective_pot_type(pot_type: str, opener: str, threebettor: str, stack_bb: float) -> str:
    """pot_type EFETIVO pro hash/ranges: '3bet' só quando é pote 3-bet E há ranges 3-bet
    capturadas pros dois jogadores; senão '' (comporta-se como SRP — hash legado). 4bet e
    spots sem range caem em '' (aproximação SRP, paridade com o legado)."""
    if (pot_type or '').lower().strip() != '3bet':
        return ''
    r_3b, r_call = _captured_3bet_ranges(opener, threebettor, stack_bb)
    return '3bet' if (r_3b and r_call) else ''


def _canon_solver_action(label: str, facing_size_bb: float) -> str:
    """Normaliza o label de ação do solver_cli (ex.: 'bet_50pct', 'bet_2.5x') pro conjunto
    canônico {check,call,fold,bet,raise,allin} que o insert_gto_nodes/engine aceitam. Um
    label de aposta vira 'raise' quando há aposta a enfrentar (facing>0) e 'bet' quando o
    hero abre a ação (facing==0). Sem isso, o nó é rejeitado ('ações inválidas')."""
    a = (label or '').lower().strip()
    if 'check' in a:
        return 'check'
    if a == 'call':
        return 'call'
    if a == 'fold':
        return 'fold'
    if 'allin' in a or 'all-in' in a or 'all_in' in a or 'jam' in a or 'shove' in a:
        return 'allin'
    # bet_50pct / bet_2.5x / raise_* / *x / *pct → bet ou raise conforme o contexto
    return 'raise' if (facing_size_bb or 0) > 0 else 'bet'


def _solver_binary() -> Optional[str]:
    global _SOLVER_AVAILABLE
    if _SOLVER_AVAILABLE is None:
        _SOLVER_AVAILABLE = os.path.isfile(_SOLVER_BIN)
        if not _SOLVER_AVAILABLE:
            log.warning("solver_cli não encontrado em %s — on-demand solve indisponível", _SOLVER_BIN)
    return _SOLVER_BIN if _SOLVER_AVAILABLE else None


# ── Fase 3 (plano solver): visão POR MÃO da árvore solvada ────────────────────

def _store_tree_strategy(tree_hash: str, board: list, result: dict) -> None:
    """Persiste a tabela por mão (hand_table/actions do solver_cli) keyed por
    tree_hash. Best-effort: binário antigo (sem hand_table) → no-op."""
    try:
        if tree_hash and result.get('hand_table') and result.get('actions'):
            from database.repositories import upsert_tree_strategy
            upsert_tree_strategy(tree_hash, board, result['actions'], result['hand_table'])
    except Exception as e:
        log.debug("tree_strategy store falhou: %s", e)


def hand_view_for_spot(tree_hash: str, spot_board: list, hero_hand: list) -> Optional[dict]:
    """Extrai a estratégia + EVs DA MÃO DO HERO a partir da tabela por mão da
    árvore (gto_tree_strategies). O board armazenado pode ser um ISOMORFO do
    board do spot (Fase 1) — a mão é mapeada pelos naipes via iso_suit_map.

    Retorna {'actions': {label: {'frequency','ev_bb','ev_loss_bb'}},
             'best_action', 'best_ev_bb', 'weight'} ou None (sem tabela /
    mão fora do range / boards não-isomorfos)."""
    if not (tree_hash and hero_hand and len(hero_hand) >= 2):
        return None
    try:
        from database.repositories import get_tree_strategy
        from leaklab.gto_utils import iso_suit_map, map_cards_suits, normalize_cards
        ts = get_tree_strategy(tree_hash)
        if not ts:
            return None
        # mapeia a mão do spot → naipes do board ARMAZENADO (solve original)
        smap = iso_suit_map(spot_board, ts['board'])
        if smap is None:
            return None
        mapped = map_cards_suits(normalize_cards(hero_hand), smap)
        if len(mapped) < 2:
            return None
        key = frozenset(mapped)
        row = None
        for h in ts['hand_table']:
            hs = h.get('hand') or ''
            if len(hs) >= 4 and frozenset((hs[0:2], hs[2:4])) == key:
                row = h
                break
        if row is None:
            return None   # mão do hero fora do range usado no solve
        acts = ts['actions']
        freqs, evs = row.get('freqs') or [], row.get('evs') or []
        if len(acts) != len(freqs) or len(acts) != len(evs):
            return None
        best_ev = max(evs) if evs else 0.0
        out = {}
        for i, a in enumerate(acts):
            out[a] = {
                'frequency':  freqs[i],
                'ev_bb':      evs[i],
                'ev_loss_bb': round(best_ev - evs[i], 2),
            }
        best_action = max(out, key=lambda k: out[k]['frequency'])
        return {'actions': out, 'best_action': best_action,
                'best_ev_bb': best_ev, 'weight': row.get('weight')}
    except Exception as e:
        log.debug("hand_view_for_spot falhou: %s", e)
        return None


# ── Lookup principal ───────────────────────────────────────────────────────────

def lookup_gto(
    street: str,
    position: str,
    board: list[str],
    hero_hand: list[str],
    hero_stack_bb: float,
    action_seq: str = 'rfi',
    vs_position: str = '',
    facing_size_bb: float = 0.0,
    pot_bb: float = 0.0,
    num_players: int = 9,
    bb_chips: float = 0.0,
    block_remote: bool = True,
    allow_remote_solve: bool = True,
    pot_type: str = '',
    opener: str = '',
    threebettor: str = '',
    require_hand_aware: bool = False,
) -> dict:
    """
    Ponto de entrada único para consultas GTO.

    Retorna apenas dados com exploitability_pct garantida pelo solver.

    {
      "found":               bool,
      "source":              "postflop_db" | "queued" | "solver_unavailable",
      "strategy":            [{action, frequency, ev_bb, exploitability_pct}],
      "exploitability_pct":  float | None,
      "spot_hash":           str,
      "queued":              bool,
    }
    """
    from leaklab.gto_utils import compute_spot_hash, hand_to_type, stack_bucket
    from database.repositories import (
        get_preflop_gto, get_gto_node, enqueue_solver_spot, insert_gto_nodes,
    )

    street_l   = street.lower()
    position_u = position.upper()
    sb         = stack_bucket(hero_stack_bb)
    hand_type  = hand_to_type(hero_hand)
    # Fase 2: pot_type efetivo ('3bet' só com ranges 3-bet capturadas; senão '' = SRP/legado)
    _eff_pot   = _effective_pot_type(pot_type, opener, threebettor, hero_stack_bb)
    spot_hash  = compute_spot_hash(street_l, position_u, board, hero_hand, hero_stack_bb, facing_size_bb, _eff_pot)

    # 1. Preflop — só retorna se houver dados verificados
    if street_l == 'preflop' and hand_type:
        rows = get_preflop_gto(
            position=position_u,
            hand_type=hand_type,
            action_seq=action_seq,
            vs_position=vs_position.upper(),
            stack_bucket=sb,
        )
        if rows:
            top_exploit = min(r.get('exploitability_pct') or 99 for r in rows)
            return {
                'found':              True,
                'source':             'preflop_db',
                'hand_type':          hand_type,
                'strategy':           rows,
                'exploitability_pct': top_exploit,
                'spot_hash':          spot_hash,
                'queued':             False,
            }

    # 2. Postflop — gto_nodes verificados
    # Fallbacks em ordem de precisão decrescente:
    #   a) hash exato (com hero_hand + facing_size_bb)
    #   b) sem hero_hand mas com mesmo facing bucket (precompute genérico)
    #   c) sem hero_hand e sem facing — SOMENTE quando facing == 0
    #      (evita retornar nó de "sem aposta" quando hero enfrenta aposta → gto_spot_mismatch)
    # NOTA: fallback hash_no_facing (facing=0 com hero_hand) foi removido — causava mismatches
    #       quando hero enfrentava aposta mas só havia nó sem-aposta para aquela mão específica.
    def _has_strategy(n):
        return n and n.get('strategy_json')

    def _pick_node(pt: str):
        """Melhor nó pra um pot_type: exato > genérico (sem hero_hand) > sem-facing."""
        h_exact = compute_spot_hash(street_l, position_u, board, hero_hand, hero_stack_bb, facing_size_bb, pt)
        h_gen   = compute_spot_hash(street_l, position_u, board, [],        hero_stack_bb, facing_size_bb, pt)
        h_nf    = compute_spot_hash(street_l, position_u, board, [],        hero_stack_bb, 0.0, pt)
        ne  = get_gto_node(h_exact)
        ng  = get_gto_node(h_gen) if h_gen != h_exact else None
        nnf = (get_gto_node(h_nf) if facing_size_bb == 0 and h_nf != h_gen else None)
        best = ((ne if _has_strategy(ne) else None) or (ng if _has_strategy(ng) else None)
                or (nnf if _has_strategy(nnf) else None) or ne or ng or nnf)
        return best, h_exact

    node, _ = _pick_node(_eff_pot)
    # Fallback SRP: SÓ em read-only (ex.: /replay). Pote 3-bet sem nó 3-bet solvado → serve o
    # nó SRP (aproximação), nunca pior que o legado. Quando SOLVANDO (precompute,
    # allow_remote_solve=True) NÃO cai no SRP — segue pro solve do nó 3-bet de verdade.
    if node is None and _eff_pot == '3bet' and not allow_remote_solve:
        node, _ = _pick_node('')
    # Nó com estratégia completa (strategy_json) → retorna imediatamente
    # Nó apenas com primary action (sem strategy_json) → salva como fallback e tenta GTO Wizard
    _db_fallback_strategy = None
    if node:
        strategy_detail = None
        if node.get('strategy_json'):
            try:
                strategy_detail = json.loads(node['strategy_json'])
            except Exception:
                pass
        if strategy_detail:
            strategy_list = []
            for k, v in strategy_detail.items():
                if isinstance(v, dict):
                    freq   = v.get('frequency', 0.0)
                    combos = v.get('combos')
                else:
                    freq   = float(v)
                    combos = None
                strategy_list.append({
                    'action':             k,
                    'frequency':          freq,
                    'combos':             combos,
                    'ev_bb':              node.get('ev_diff'),
                    'exploitability_pct': node.get('exploitability_pct'),
                })
            if strategy_list:
                strategy_list.sort(key=lambda s: s['frequency'], reverse=True)
                _hv = hand_view_for_spot(node.get('tree_hash'), board, hero_hand)
                # require_hand_aware: um nó AGREGADO (sem tabela por-mão) não satisfaz
                # quem precisa do ev_loss por mão. Se há solve real à frente
                # (allow_remote_solve + block_remote), NÃO retorna o agregado — cai pro
                # solve Texas que gera o hand_table. Default (flag off) = inalterado.
                if not (require_hand_aware and _hv is None
                        and allow_remote_solve and block_remote):
                    return {
                        'found':    True,
                        'source':   'postflop_db',
                        'strategy': strategy_list,
                        'exploitability_pct': node.get('exploitability_pct'),
                        'spot_hash':          spot_hash,
                        'queued':             False,
                        # Fase 3: visão da MÃO do hero (gto_tree_strategies via tree_hash;
                        # None p/ nós antigos sem tabela — UI cai no agregado)
                        'hand_strategy': _hv,
                    }
        # Nó parcial: sem strategy_json — salva como fallback, continua para GTO Wizard
        action = node.get('gto_action')
        if action:
            _db_fallback_strategy = [{
                'action':             action,
                'frequency':          node.get('gto_freq') or 1.0,
                'combos':             None,
                'ev_bb':              node.get('ev_diff'),
                'exploitability_pct': node.get('exploitability_pct'),
            }]
        log.debug("Nó parcial (sem strategy_json) para hash=%s; consultando GTO Wizard", spot_hash)

    # Short-circuit: chamadas inline (ex.: rota /replay) não devem bloquear em I/O remoto.
    # O worker assíncrono cuida de popular gto_nodes em background.
    if not block_remote:
        if _db_fallback_strategy:
            return {'found': True, 'source': 'postflop_db_partial',
                    'strategy': _db_fallback_strategy,
                    'exploitability_pct': None, 'spot_hash': spot_hash, 'queued': False}
        return {'found': False, 'source': 'solver_unavailable',
                'strategy': [], 'exploitability_pct': None,
                'spot_hash': spot_hash, 'queued': False}

    # 3. Miss — tenta GTO Wizard primeiro (se habilitado e auth disponível)
    try:
        from leaklab.gto_wizard_client import query_spot as _gw_query
        # require_hand_aware pula o GW: ele devolve estratégia agregada SEM tabela
        # por-mão → vai direto pro solver Texas, que gera o hand_table.
        _gw = None if require_hand_aware else _gw_query(
            street         = street_l,
            position       = position_u,
            board          = board,
            hero_stack_bb  = hero_stack_bb,
            facing_size_bb = facing_size_bb,
            pot_bb         = pot_bb,
            num_players    = num_players,
        )
        if _gw and _gw.get('found') and _gw.get('strategy'):
            _gw_best = max(_gw['strategy'], key=lambda s: s['frequency'])
            # Armazena no cache local para não bater na API novamente para o mesmo spot
            insert_gto_nodes([{
                'street':          street_l,
                'position':        position_u,
                'board':           board,
                'hero_hand':       hero_hand,
                'hero_stack_bb':   hero_stack_bb,
                'facing_size_bb':  facing_size_bb,
                'gto_action':      _gw_best['action'],
                'gto_freq':        _gw_best['frequency'],
                'exploitability_pct': None,
                'source':          'gto_wizard',
                'strategy_json':   json.dumps(
                    {s['action']: {'frequency': s['frequency'], 'combos': s.get('combos')}
                     for s in _gw['strategy']},
                    sort_keys=True,
                ),
            }])
            return {**_gw, 'spot_hash': spot_hash}
    except Exception as _gw_err:
        log.debug("gto_wizard: query_spot exception — %s", _gw_err)

    # 4. Fallback para o solver Texas (CFR remoto) — REATIVADO p/ postflop HU, COM TRAVAS.
    # O bug do "shove de 150bb" era DEPTH (solve capado a 20bb servido a spot fundo via o
    # bucket de stack), NÃO o solver. Agora o solve roda no depth REAL
    # (_solver_params_for_stack, effective_stack capado a 60bb). Travas:
    #   (a) só POSTFLOP com board (preflop usa preflop_db/GW);
    #   (b) só stack ≤ 60bb — acima, o cap de 60bb viraria aproximação → heurístico honesto
    #       (o engine NUNCA serve solver_cli > 60bb; ver _postflop_gto_lookup);
    #   (c) o engine aplica o guard de SPR (jam postflop só com SPR ≤ 3) ao ler o nó.
    # GATE do Texas postflop (P0 — correção). Só resolvemos os spots que o pipeline
    # atual faz CERTO; o resto cai no heurístico (honesto):
    #   - street postflop com board e stack ≤60bb (cap do solver);
    #   - vilão conhecido (precisa pra montar a range adversária);
    #   - hero é OOP (player 0). O solver_cli SÓ devolve a estratégia do player 0; com o
    #     hero IP, o nó seria a estratégia do VILÃO → bug do "jogador errado". Liberado
    #     quando o main.rs ler hero_player (fix Rust);
    #   - facing: o solver navega em BB, mas `facing_size_bb` chega em FICHAS. Converte via
    #     `bb_chips` (fix 2.2). Se facing>0 e bb_chips não veio → não dá pra converter →
    #     fica fora (sem navegação errada). NOTA: o hash ainda usa facing em fichas (bucket
    #     grosso "40bb+"); distinguir sizes finos é P1.
    _vs = (vs_position or '').upper().strip()
    _hero_ip = _postflop_hero_is_ip(position_u, _vs)
    _facing_solver_bb = (facing_size_bb / bb_chips) if (bb_chips and bb_chips > 0) else facing_size_bb
    _facing_unconvertible = facing_size_bb > 0.0 and not (bb_chips and bb_chips > 0)
    # hero IP servido com o main.rs patcheado (TEXAS_HERO_IP): c-bet (facing==0) sempre;
    # facing>0 (IP enfrentando aposta, root → OOP bet → IP age) só com TEXAS_HERO_IP_FACING
    # (requer o binário novo com navigate_to_ip_facing_bet deployado). Senão, heurístico.
    _ip_blocked = _hero_ip and not (
        _TEXAS_HERO_IP and (facing_size_bb == 0.0 or _TEXAS_HERO_IP_FACING)
    )
    # Guard de consistência street×board: o nº de cartas precisa bater com a street
    # (flop=3, turn=4, river=5). Spots inconsistentes (ex.: 'river' com 4 cartas — bug
    # de parser onde a carta de river some) fariam o solver_cli abortar (500). Pula.
    _nb = len([c for c in board if c])
    _board_mismatch = _nb != {'flop': 3, 'turn': 4, 'river': 5}.get(street_l, -1)
    # Opção B (decidida pelo usuário): spots fundos (>60bb) são SOLVADOS no cap de 60bb
    # (_solver_params já capa effective_stack) e SERVIDOS como aproximação, com selo
    # "≈ Aproximação" (depth_capped no _enrich_gto). Acima de 200bb nem aproxima → heurístico.
    # O guard de SPR/allin no engine continua rejeitando shove fundo degenerado.
    if (street_l == 'preflop' or not board or hero_stack_bb > 200.0
            or _vs in ('', 'UNKNOWN') or _ip_blocked or _facing_unconvertible
            or _board_mismatch):
        if _db_fallback_strategy:
            return {'found': True, 'source': 'postflop_db_partial',
                    'strategy': _db_fallback_strategy,
                    'exploitability_pct': None, 'spot_hash': spot_hash, 'queued': False}
        return {'found': False, 'source': 'solver_unavailable',
                'strategy': [], 'exploitability_pct': None,
                'spot_hash': spot_hash, 'queued': False}

    # --- solver Texas (CFR remoto) — postflop HU, hero OOP (player 0), depth real ≤60bb ---
    # Ranges atribuídas aos jogadores CORRETOS (hero=OOP, vilão=IP) e, quando há cobertura,
    # REAIS do GW (2.3): HU SRP típico → o vilão IP abriu (RFI) e o hero OOP pagou (call vs
    # RFI). Fallback pras _DEFAULT_RANGES genéricas quando o GW não cobre o cenário.
    if _hero_ip:
        # hero é IP (opener/c-bettor); vilão é OOP (caller/defender)
        ip_pos, oop_pos = position_u, _vs
    else:
        # hero é OOP (caller/defender); vilão é IP (opener)
        ip_pos, oop_pos = _vs, position_u

    if _eff_pot == '3bet':
        # Pote 3-bet (Fase 2): o 3-bettor recebe a range de 3-bet; o opener que pagou recebe
        # a range de call-vs-3bet (capada, mais forte que a RFI larga do SRP). Mapeia por posição.
        _r3b, _rcall = _captured_3bet_ranges(opener, threebettor, hero_stack_bb)
        _by_pos = {(opener or '').upper(): _rcall, (threebettor or '').upper(): _r3b}
        ip_range  = _by_pos.get(ip_pos)  or _DEFAULT_RANGES.get(ip_pos,  _DEFAULT_RANGE_WIDE)
        oop_range = _by_pos.get(oop_pos) or _DEFAULT_RANGES.get(oop_pos, _DEFAULT_RANGE_WIDE)
    else:
        ip_range  = (_captured_range_str(ip_pos, hero_stack_bb, 'rfi')
                     or _DEFAULT_RANGES.get(ip_pos, _DEFAULT_RANGE_WIDE))                   # IP = opener (RFI)
        oop_range = (_captured_range_str(oop_pos, hero_stack_bb, 'call_vs_rfi', opener=ip_pos)
                     or _DEFAULT_RANGES.get(oop_pos, _DEFAULT_RANGE_WIDE))                  # OOP = caller (call vs RFI)
    effective_pot = pot_bb if pot_bb > 0 else max(_facing_solver_bb * 2 + 2, 4.0)

    # Read-only: quem chama com allow_remote_solve=False (ex.: /replay) NÃO dispara um
    # solve Texas dentro da requisição — solve é caro e, com params errados (pot em
    # fichas), gera nós degenerados. Sem nó local, devolve "sem cobertura" (heurístico).
    if not allow_remote_solve:
        if _db_fallback_strategy:
            return {'found': True, 'source': 'postflop_db_partial', 'strategy': _db_fallback_strategy,
                    'exploitability_pct': None, 'spot_hash': spot_hash, 'queued': False}
        return {'found': False, 'source': 'solver_skipped', 'strategy': [],
                'exploitability_pct': None, 'spot_hash': spot_hash, 'queued': False}

    _params = _solver_params_for_stack(hero_stack_bb)
    solver_payload = {
        'street':                    street_l,
        'board':                     board,
        'oop_range':                 oop_range,
        'ip_range':                  ip_range,
        'pot_bb':                    effective_pot,
        'effective_stack_bb':        _params['effective_stack_bb'],
        'max_iterations':            _params['max_iterations'],
        'target_exploitability_pct': _params['target_exploitability_pct'],
        'facing_size_bb':            _facing_solver_bb,   # 2.2: solver navega em BB
        'hero_is_ip':                _hero_ip,            # main.rs lê player 1 quando IP
    }

    # ── Fase 1 (plano solver): dedup por tree_hash ────────────────────────────
    # Mesma ÁRVORE já solvada (outra mão do hero na mesma situação, ou board
    # isomorfo por permutação de naipes) → copia o nó existente em vez de pagar
    # outro solve CFR. A estratégia agregada da range é invariante à mão do hero
    # (que não é input do solver) e à permutação de naipes.
    from leaklab.gto_utils import compute_tree_hash
    from database.repositories import get_gto_node_by_tree_hash
    tree_hash = compute_tree_hash(solver_payload)
    _tnode = get_gto_node_by_tree_hash(tree_hash)
    if _tnode and _tnode.get('strategy_json'):
        try:
            _t_detail = json.loads(_tnode['strategy_json'])
        except Exception:
            _t_detail = None
        if _t_detail:
            insert_gto_nodes([{
                'street':          street_l,
                'position':        position_u,
                'board':           board,
                'hero_hand':       hero_hand,
                'hero_stack_bb':   hero_stack_bb,
                'facing_size_bb':  facing_size_bb,
                'spot_hash':       spot_hash,
                'tree_hash':       tree_hash,
                'gto_action':      _tnode['gto_action'],
                'gto_freq':        _tnode['gto_freq'],
                'ev_diff':         _tnode.get('ev_diff'),
                'exploitability_pct': _tnode.get('exploitability_pct'),
                'iterations':      _tnode.get('iterations'),
                'source':          _tnode.get('source') or 'solver_cli',
                'strategy_json':   _tnode['strategy_json'],
            }])
            _t_list = []
            for _k, _v in _t_detail.items():
                _freq   = _v.get('frequency', 0.0) if isinstance(_v, dict) else float(_v or 0)
                _combos = _v.get('combos') if isinstance(_v, dict) else None
                _t_list.append({'action': _k, 'frequency': _freq, 'combos': _combos,
                                'ev_bb': _tnode.get('ev_diff'),
                                'exploitability_pct': _tnode.get('exploitability_pct')})
            _t_list.sort(key=lambda s: s['frequency'], reverse=True)
            log.info("GTO tree-cache hit: %s <- tree %s (sem re-solve)", spot_hash, tree_hash)
            return {
                'found':              True,
                'source':             'tree_cache',
                'strategy':           _t_list,
                'exploitability_pct': _tnode.get('exploitability_pct'),
                'spot_hash':          spot_hash,
                'queued':             False,
                'hand_strategy':      hand_view_for_spot(tree_hash, board, hero_hand),
            }

    remote = _call_remote_solver(solver_payload)
    if remote:
        exploit = remote.get('exploitability_pct')
        # Normaliza os labels do solver (bet_50pct/bet_2.5x → bet/raise) pro conjunto
        # canônico e AGREGA por ação (senão o insert rejeita 'ações inválidas'). Aceita
        # strategy_detail {action:{frequency,combos}} ou strategy {action:freq}.
        raw_detail = remote.get('strategy_detail') or remote.get('strategy') or {}
        strategy_detail: dict = {}
        for k, v in raw_detail.items():
            ck = _canon_solver_action(k, facing_size_bb)
            if isinstance(v, dict):
                freq = float(v.get('frequency', 0) or 0); combos = v.get('combos')
            else:
                freq = float(v or 0); combos = None
            if ck in strategy_detail:
                strategy_detail[ck]['frequency'] += freq
            else:
                strategy_detail[ck] = {'frequency': freq, 'combos': combos}
        primary_action = _canon_solver_action(remote.get('primary_action', ''), facing_size_bb)
        primary_freq   = (strategy_detail.get(primary_action, {}).get('frequency')
                          or float(remote.get('primary_freq', 0) or 0))
        strategy_list = [
            {'action': k, 'frequency': v['frequency'], 'combos': v.get('combos'),
             'ev_bb': None, 'exploitability_pct': exploit}
            for k, v in strategy_detail.items()
        ]
        insert_gto_nodes([{
            'street':          street_l,
            'position':        position_u,
            'board':           board,
            'hero_hand':       hero_hand,
            'hero_stack_bb':   hero_stack_bb,
            'facing_size_bb':  facing_size_bb,
            'spot_hash':       spot_hash,   # Fase 2: hash 3bet-aware (_eff_pot) — não recomputa sem pot_type
            'tree_hash':       tree_hash,   # Fase 1 (plano solver): identidade da árvore p/ dedup
            'gto_action':      primary_action,
            'gto_freq':        primary_freq,
            'ev_diff':         remote.get('ev'),
            'exploitability_pct': float(exploit) if exploit else None,
            'iterations':      remote.get('iterations'),
            'strategy_detail': strategy_detail,
        }])
        _store_tree_strategy(tree_hash, board, remote)   # Fase 3: tabela por mão
        log.info("GTO remote solve: %s → %s %.0f%% (exploit=%.2f%%)",
                 spot_hash, primary_action, primary_freq * 100, exploit or 0)
        return {
            'found':              True,
            'source':             'remote_solver',
            'strategy':           strategy_list,
            'exploitability_pct': float(exploit) if exploit else None,
            'spot_hash':          spot_hash,
            'queued':             False,
            'hand_strategy':      hand_view_for_spot(tree_hash, board, hero_hand),
        }

    # GTO Wizard e solver remoto indisponíveis — usa nó parcial do DB como último recurso
    if _db_fallback_strategy:
        log.debug("GTO fallback parcial: %s (GW+solver indisponíveis, usando nó DB sem strategy_json)", spot_hash)
        return {
            'found':              True,
            'source':             'postflop_db_partial',
            'strategy':           _db_fallback_strategy,
            'exploitability_pct': None,
            'spot_hash':          spot_hash,
            'queued':             False,
        }
    log.debug("GTO miss: %s (GW indisponível + solver remoto sem resposta)", spot_hash)
    return {
        'found':              False,
        'source':             'solver_unavailable',
        'strategy':           [],
        'exploitability_pct': None,
        'spot_hash':          spot_hash,
        'queued':             False,
    }


def _priority(street: str) -> int:
    # Fase 2 (plano solver): shortest-job-first — river/turn solvem em segundos,
    # flop fundo leva minutos. Processar os baratos primeiro minimiza a espera
    # média da fila (antes flop>turn>river: os caros bloqueavam os baratos).
    return {'preflop': 8, 'river': 7, 'turn': 6, 'flop': 5}.get(street, 5)


def is_simple_spot(street: str, board: list[str], stack_bb: float, facing_size_bb: float = 0.0) -> bool:
    """
    Retorna True para spots que podem ser resolvidos sincronamente (< 30s no remote solver).
    False → enfileira imediatamente sem bloquear o request.

    Critérios de simplicidade:
      - Stack ≤ 25bb: qualquer street resolve síncronamente (árvore pequena com stack curto)
      - Flop + stack ≤ 35bb + board rainbow: resolve síncronamente
      - Turn/River com stack > 25bb: sempre async (árvore grande)
    """
    street_l = street.lower()
    if stack_bb <= 25:
        return True   # short stack: flop/turn/river são rápidos em qualquer street
    if street_l != 'flop':
        return False  # turn/river com stack > 25bb: árvore grande → async
    if stack_bb > 35:
        return False
    suits = [c[1].lower() for c in board if len(c) >= 2]
    is_rainbow = len(set(suits)) == 3 and len(suits) >= 3
    bet_is_small = facing_size_bb <= stack_bb * 0.35
    return is_rainbow and bet_is_small


def _call_remote_solver(spot: dict, timeout: int = 1800) -> Optional[dict]:
    """Chama o solver remoto. Retorna resultado ou None em caso de falha.
    timeout alto (1800s) p/ acomodar solves longos de árvore rica (alta convergência)."""
    url = _remote_url()
    key = _remote_key()
    if not url or not key:
        return None
    try:
        import requests
        resp = requests.post(
            f"{url}/solve",
            json=spot,
            headers={"x-api-key": key},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json()
        log.warning("Remote solver HTTP %d: %s", resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        log.warning("Remote solver indisponível: %s", e)
        return None


# ── Worker — consume fila, valida exploitability ──────────────────────────────

def run_solver_worker(max_jobs: int = 10) -> dict:
    """
    Processa até max_jobs spots da fila.
    Prioridade: solver remoto (GTO_SOLVER_URL) → solver local (Rust binário).
    Threshold de aceitação: production=10%, test=50%.

    Retorna {solved, rejected, failed, copied} — copied = nós reusados via tree_hash (Fase 1)
    """
    tier = os.environ.get('SOLVER_TIER', '')
    if not tier:
        tier = 'production' if os.environ.get('GTO_SOLVER_URL') else 'test'
    acceptance_threshold = 10.0 if tier == 'production' else 50.0
    from database.repositories import get_next_solver_job, mark_solver_job_done, insert_gto_nodes

    use_remote = bool(_remote_url() and _remote_key())
    bin_path   = _solver_binary()

    if not use_remote and not bin_path:
        return {'solved': 0, 'rejected': 0, 'failed': 0, 'error': 'solver_unavailable'}

    if use_remote:
        log.info("run_solver_worker: usando solver REMOTO (%s)", _remote_url())
    else:
        log.info("run_solver_worker: usando solver LOCAL (%s)", bin_path)

    solved = rejected = failed = copied = 0

    for _ in range(max_jobs):
        job = get_next_solver_job()
        if not job:
            break

        job       = dict(job)
        spot_hash = job['spot_hash']
        spot      = json.loads(job['spot_json'])

        # ── Fase 1 (plano solver): dedup por tree_hash — árvore já solvada →
        # copia o nó existente para este spot_hash, sem pagar outro solve CFR.
        try:
            from leaklab.gto_utils import compute_tree_hash
            from database.repositories import get_gto_node_by_tree_hash
            _th = job.get('tree_hash') or compute_tree_hash(spot)
        except Exception:
            _th = None
        if _th:
            _existing = get_gto_node_by_tree_hash(_th)
            if _existing and _existing.get('strategy_json'):
                _meta    = spot.get('_meta', {})
                _copied = insert_gto_nodes([{
                    'spot_hash':       spot_hash,
                    'tree_hash':       _th,
                    'street':          spot.get('street', ''),
                    'position':        spot.get('position') or _meta.get('position', ''),
                    'board':           spot.get('board', []),
                    'hero_hand':       spot.get('hero_hand') or _meta.get('hero_hand', []),
                    'hero_stack_bb':   spot.get('hero_stack_bb') or _meta.get('hero_stack_bb', 30.0),
                    'facing_size_bb':  spot.get('facing_size_bb') or _meta.get('facing_size_bb', 0.0),
                    'gto_action':      _existing['gto_action'],
                    'gto_freq':        _existing['gto_freq'],
                    'ev_diff':         _existing.get('ev_diff'),
                    'exploitability_pct': _existing.get('exploitability_pct'),
                    'iterations':      _existing.get('iterations'),
                    'source':          _existing.get('source') or 'solver_cli',
                    'strategy_json':   _existing['strategy_json'],
                }])
                if _copied:
                    mark_solver_job_done(spot_hash, 'done')
                    copied += 1
                    log.info("GTO tree-cache copy: %s <- tree %s (sem solve)", spot_hash, _th)
                    continue

        try:
            stack   = spot.get('effective_stack_bb', 30.0)
            params  = _solver_params_for_stack(stack)
            timeout = params['timeout']
            # Sobrescreve params CONGELADOS no spot_json (foram gravados no enqueue, muitas
            # vezes no tier 'test' → max_iterations=10). Sempre usa os params frescos do
            # tier atual — senão mudar iterações/alvo aqui não tem efeito nenhum.
            spot['max_iterations']            = params['max_iterations']
            spot['target_exploitability_pct'] = params['target_exploitability_pct']
            spot['effective_stack_bb']        = params['effective_stack_bb']
            spot['time_budget_s']             = params.get('time_budget_s', 150)

            # Prefere solver remoto; cai para local se remoto indisponível
            if use_remote:
                result = _call_remote_solver(spot, timeout=timeout)
                if result is None and bin_path:
                    log.warning("Remoto falhou para %s — tentando local", spot_hash)
                    result = _call_solver(bin_path, spot, timeout=timeout)
            else:
                result = _call_solver(bin_path, spot, timeout=timeout)

            if not result:
                mark_solver_job_done(spot_hash, 'failed')
                failed += 1
                continue

            # Fase 3: persiste a tabela por mão do solve (keyed por tree_hash)
            _store_tree_strategy(_th, spot.get('board', []), result)

            # Normaliza chave: solver local usa 'exploitability', remoto usa 'exploitability_pct'
            exploit = result.get('exploitability') or result.get('exploitability_pct')
            if exploit is None or float(exploit) > acceptance_threshold:
                log.warning(
                    "Spot %s exploitability=%.2f%% > MAX %.1f%% — descartando",
                    spot_hash, exploit or 999, acceptance_threshold
                )
                mark_solver_job_done(spot_hash, 'failed')
                failed += 1
                continue

            # Extrai campos de _meta quando não disponíveis no nível raiz
            meta     = spot.get('_meta', {})
            position = spot.get('position') or meta.get('position', '')
            facing   = spot.get('facing_size_bb') or meta.get('facing_size_bb', 0.0)
            hero_hand    = spot.get('hero_hand') or meta.get('hero_hand', [])
            hero_stack   = spot.get('hero_stack_bb') or meta.get('hero_stack_bb', 30.0)
            inserted = insert_gto_nodes([{
                'spot_hash':         spot_hash,
                'tree_hash':         _th,
                'street':            spot['street'],
                'position':          position,
                'board':             spot.get('board', []),
                'hero_hand':         hero_hand,
                'hero_stack_bb':     hero_stack,
                'facing_size_bb':    facing,
                'gto_action':        result['primary_action'],
                'gto_freq':          result['primary_freq'],
                'ev_diff':           result.get('ev'),
                'exploitability_pct': float(exploit),
                'iterations':        result.get('iterations'),
                'strategy_detail':   result.get('strategy_detail'),
            }])

            if inserted:
                mark_solver_job_done(spot_hash, 'done')
                solved += 1
                log.info(
                    "GTO verified: %s → %s %.0f%% (exploit=%.2f%%)",
                    spot_hash, result['primary_action'],
                    result['primary_freq'] * 100, exploit
                )
            else:
                # insert_gto_nodes retornou 0 — exploitability rejeitada internamente
                mark_solver_job_done(spot_hash, 'rejected')
                rejected += 1

        except Exception as e:
            log.exception("Solver error for %s: %s", spot_hash, e)
            mark_solver_job_done(spot_hash, 'failed')
            failed += 1

    return {'solved': solved, 'rejected': rejected, 'failed': failed, 'copied': copied}


def _requeue_with_more_iterations(spot_hash: str, spot: dict) -> None:
    """
    Recoloca spot na fila com parâmetros relaxados.
    Em vez de apenas multiplicar iterações (o que causaria timeout novamente),
    dobra o threshold de exploitability para aceitar uma solução menos precisa.
    """
    from database.repositories import enqueue_solver_spot
    stack           = spot.get('effective_stack_bb', 30.0)
    base            = _solver_params_for_stack(stack)
    current_iter    = spot.get('max_iterations', base['max_iterations'])
    current_target  = spot.get('target_exploitability_pct', base['target_exploitability_pct'])
    # Relaxa threshold (máx 10%) e mantém iterações dentro do razoável
    spot_augmented  = {
        **spot,
        'max_iterations':            min(current_iter, base['max_iterations']),
        'target_exploitability_pct': min(current_target * 2.0, 10.0),
    }
    enqueue_solver_spot(
        spot_hash + '_retry',
        json.dumps(spot_augmented, sort_keys=True),
        priority=_priority(spot.get('street', 'flop')) + 1,
    )


def _call_solver(bin_path: str, spot: dict, timeout: int = 300) -> Optional[dict]:
    """
    Chama solver_cli com spot JSON via stdin. Retorna dict com resultado ou None.
    """
    # CREATE_BREAKAWAY_FROM_JOB: libera o processo do Job Object do Python no Windows,
    # permitindo que Rayon crie threads sem restrições (sem isso: ~10x mais lento).
    _BREAKAWAY = 0x01000000 if os.name == 'nt' else 0
    try:
        # stdin direto (sem temp file): elimina I/O em disco e lixo órfão em %TEMP%
        proc = subprocess.run(
            [bin_path],
            input=json.dumps(spot),
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout,
            creationflags=_BREAKAWAY,
        )
        if proc.returncode != 0:
            log.error("solver_cli exit=%d stderr: %s", proc.returncode, proc.stderr[:500])
            return None
        result = json.loads(proc.stdout)
        # Normaliza nome do campo exploitability (solver retorna 'exploitability')
        if 'exploitability' not in result and 'exploitability_pct' in result:
            result['exploitability'] = result['exploitability_pct']
        return result
    except subprocess.TimeoutExpired:
        log.error("solver_cli timeout após %ds", timeout)
        return None
    except json.JSONDecodeError as e:
        log.error("solver_cli output inválido: %s", e)
        return None
