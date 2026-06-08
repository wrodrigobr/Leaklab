"""Captura GTO Wizard (GW) pros spots POSTFLOP pendentes — substituindo o que antes
eram nós do solver Texas (solver_cli), agora ignorados. Varre as decisões postflop
dos torneios, ENCODA a linha de ações (preflop + flop/turn) no formato GW e consulta
via `POST /gw-spot` (o endpoint que DIRIGE a página real do Chrome logado — não usa o
refresh de auth, que fica desligado no servidor). O nó capturado (source='gto_wizard')
passa a ser servido pelo engine. Depois roda o resync pra refletir nas decisões salvas.

POR QUE /gw-spot E NÃO /gto-wizard: o `/gto-wizard` replica headers de auth capturados
(via refresh loop, DESLIGADO no servidor → sempre 503 auth_unavailable). O `/gw-spot`
navega a página no Chrome logado a cada request, então funciona com `gto_wizard:
degraded` no /health (estado NORMAL desse servidor).

PRÉ-REQUISITO: Chrome da VM logado no GTO Wizard com CDP na porta 9222 (já é o setup
padrão). Carrega o backend/.env automaticamente (GTO_SOLVER_URL + GTO_SOLVER_API_KEY).

Uso:
    python -m scripts.capture_postflop_gw                 # dry-run (todos os torneios)
    python -m scripts.capture_postflop_gw --tournament 999999
    python -m scripts.capture_postflop_gw --apply --limit 200
    python -m scripts.capture_postflop_gw --apply --resync
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Carrega backend/.env (GTO_SOLVER_URL / GTO_SOLVER_API_KEY) — scripts não herdam.
_envp = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_envp):
    for _l in open(_envp, encoding='utf-8'):
        _l = _l.strip()
        if _l and not _l.startswith('#') and '=' in _l:
            _k, _v = _l.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from database.schema import get_conn
from database.repositories import get_gto_node, insert_gto_nodes
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import compute_spot_hash, hand_to_type
from leaklab.gw_action_encoder import (
    encode_preflop_actions, encode_street_actions, num_seated_players, gw_gametype_for,
    gw_board_order,
)
from leaklab.hand_state_builder import _effective_stack
from leaklab.gto_wizard_client import query_spot_raw

# Mesmo conjunto que extract_decision_points usa — garante alinhamento di↔índice.
_DECISION_ACTIONS = {'folds', 'checks', 'calls', 'bets', 'raises', 'all-in'}


def _preflight():
    """Confirma que o /gw-spot responde de fato (independe do auth_ok/refresh loop).
    Probe = RFI 9-max 20bb (preflop puro, sem board) — resolve sempre que o GW está
    acessível e logado. found=True → GW operacional."""
    url = os.environ.get('GTO_SOLVER_URL', '').rstrip('/')
    if not url:
        return False, "GTO_SOLVER_URL vazio (configure o backend/.env)"
    # A página Chrome do servidor é serial e ocasionalmente trava numa navegação
    # anterior — a 1ª query depois disso falha e a seguinte recupera. Tenta algumas
    # vezes antes de abortar.
    last_err = None
    for attempt in range(4):
        try:
            probe = query_spot_raw(preflop_actions="", num_players=9, depth_bb=20,
                                   board="", include_strategy=True, use_cache=False, timeout=40)
        except Exception as e:
            last_err = f"/gw-spot inalcançável: {e}"; continue
        if probe and probe.get('found'):
            return True, f"/gw-spot OK (RFI probe → {len(probe.get('strategy') or [])} ações, tent.{attempt+1})"
        last_err = "probe RFI sem solução (página presa?)"
    return False, (f"{last_err} — após 4 tentativas. Chrome da VM provavelmente não está "
                   "logado no GTO Wizard (CDP 9222), ou o servidor está sobrecarregado.")


def _spots_for_tournament(raw):
    """Gera spots postflop com a linha de ações ENCODED pro /gw-spot + os params de
    hash IDÊNTICOS ao engine (_postflop_gto_lookup), pra o nó ser encontrável."""
    out = []
    for hand in parse_hand_history(raw):
        hero = hand.hero
        if not hero:
            continue
        n_seat   = num_seated_players(hand)
        gametype = gw_gametype_for(n_seat)
        if not gametype:
            continue
        depth = round(_effective_stack(hand, hero, []), 2)  # stack inicial em bb = depth GW
        dec_idxs = [i for i, a in enumerate(hand.actions)
                    if a.player == hero and a.action in _DECISION_ACTIONS]
        try:
            dis = build_decision_inputs_for_hand(hand)
        except Exception:
            continue
        if len(dis) != len(dec_idxs):
            continue  # desalinhamento di↔índice — pula a mão (raro)

        for di, idx in zip(dis, dec_idxs):
            street = (di.get('street') or '').lower()
            if street not in ('flop', 'turn', 'river'):
                continue
            sp        = di.get('spot', {})
            board     = sp.get('board') or []
            pos       = sp.get('position', '')
            hero_hand = di.get('hero_cards', [])
            if not board or not pos or not hero_hand:
                continue
            # Params de hash — EXATAMENTE como o engine (sem dividir facing por bb).
            stack_bb  = float(sp.get('effectiveStackBb') or 20.0)
            facing_bb = float(sp.get('facingSize') or 0.0)
            # Linha de ações encoded (até a decisão do hero no índice idx).
            out.append({
                'street':     street,
                'position':   pos,
                'board':      board,
                'hero_hand':  hero_hand,
                'hand_type':  hand_to_type(hero_hand),
                'stack_bb':   stack_bb,
                'facing_bb':  facing_bb,
                'n_opp':      int(sp.get('nActiveOpponents') or 1),
                'gametype':   gametype,
                'n_seat':     n_seat,
                'depth':      depth,
                'pf':         encode_preflop_actions(hand, idx),
                'fl':         encode_street_actions(hand, 'flop',  idx),
                'tn':         encode_street_actions(hand, 'turn',  idx),
                'rv':         encode_street_actions(hand, 'river', idx),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tournament')
    ap.add_argument('--limit', type=int, default=10_000)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--resync', action='store_true', help='roda resync_postflop_gto --apply no fim')
    args = ap.parse_args()

    ok, msg = _preflight()
    print(f"Preflight GW: {'OK' if ok else 'FALHOU'} — {msg}")
    if not ok:
        print("\nAbortado — sem GW operacional não dá pra capturar. (Os spots pendentes seguem no "
              "heurístico, que é honesto.)")
        sys.exit(1)

    conn = get_conn()
    q = "SELECT id, tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL"
    params = []
    if args.tournament:
        q += " AND tournament_id = ?"; params.append(args.tournament)
    rows = conn.execute(q, params).fetchall()

    seen_hashes = set()
    captured = skipped = not_found = errs = multiway = 0
    for r in rows:
        for s in _spots_for_tournament(r['raw_text']):
            if captured + not_found + skipped >= args.limit:
                break
            # Pula spots MULTIWAY (3+ jogadores no flop): o GW só tem solução postflop
            # HU — consultar multiway só gera subprocess_timeout (~35s desperdiçados).
            # Esses spots seguem no heurístico (honesto).
            if s['n_opp'] > 1:
                multiway += 1
                continue
            h = compute_spot_hash(s['street'], s['position'], s['board'], s['hero_hand'],
                                  s['stack_bb'], s['facing_bb'])
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            existing = get_gto_node(h)
            if existing and existing.get('source') == 'gto_wizard':
                skipped += 1; continue   # já tem GW
            gw = None
            for _try in range(2):   # retry: 1ª query após página presa falha, 2ª recupera
                try:
                    gw = query_spot_raw(
                        preflop_actions=s['pf'], num_players=s['n_seat'], depth_bb=s['depth'],
                        flop_actions=s['fl'], turn_actions=s['tn'], river_actions=s['rv'],
                        board=gw_board_order(s['board']), gametype=s['gametype'],
                        include_strategy=True, fetch_timeout=15,
                    )
                except Exception:
                    gw = None
                if gw and gw.get('found'):
                    break
            if not gw or not gw.get('found'):
                not_found += 1; continue

            # Estratégia da MÃO ESPECÍFICA do hero (hand_freqs[hand_type]); fallback p/
            # a agregada do spot. betsize_bb vem da agregada (por nome de ação).
            agg_bet = {x['action']: x.get('betsize_bb') for x in (gw.get('strategy') or [])}
            hf      = (gw.get('hand_freqs') or {}).get(s['hand_type'])
            if hf:
                strat = dict(hf)                                   # {action: frequency}
            else:
                strat = {x['action']: x['frequency'] for x in (gw.get('strategy') or [])}
            strat = {a: f for a, f in strat.items() if f and f > 0.0}
            if not strat:
                not_found += 1; continue
            best_action = max(strat, key=strat.get)
            node = {
                'street': s['street'], 'position': s['position'], 'board': s['board'],
                'hero_hand': s['hero_hand'], 'hero_stack_bb': s['stack_bb'],
                'facing_size_bb': s['facing_bb'], 'gto_action': best_action,
                'gto_freq': round(float(strat[best_action]), 4), 'exploitability_pct': None,
                'source': 'gto_wizard',
                'strategy_json': json.dumps(
                    {a: {'frequency': round(float(f), 4), 'betsize_bb': agg_bet.get(a)}
                     for a, f in strat.items()}, sort_keys=True),
            }
            if args.apply:
                insert_gto_nodes([node])
            captured += 1
            print(f"  {'capturado' if args.apply else 'capturaria'}: {s['street']} {s['position']} "
                  f"{''.join(s['board'])} {s['stack_bb']:.0f}bb {s['hand_type']} → {best_action} "
                  f"({strat[best_action]*100:.0f}%)")

    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN'}: capturados={captured} | já tinha GW={skipped} "
          f"| GW sem solução={not_found} | multiway pulados={multiway} (heurístico) | erros={errs}")
    if args.apply and args.resync and captured:
        print("\nRodando resync_postflop_gto --apply…")
        os.system(f'"{sys.executable}" scripts/resync_postflop_gto.py --apply')


if __name__ == '__main__':
    main()
