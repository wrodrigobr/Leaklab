"""Captura GTO Wizard (GW) pros spots POSTFLOP pendentes — substituindo o que antes
eram nós do solver Texas (solver_cli), agora ignorados. Varre as decisões postflop
dos torneios, monta os params do spot e consulta o GW; o nó capturado (source=
'gto_wizard') passa a ser servido pelo engine. Depois roda o resync pra refletir nas
decisões salvas.

PRÉ-REQUISITO: o servidor GW (GTO_SOLVER_URL) precisa estar com o Chrome LOGADO no
GTO Wizard. Se vier `auth_unavailable` (503), logue o Chrome na VM (VNC) e rode de novo.
Carrega o backend/.env automaticamente (GTO_SOLVER_URL + GTO_SOLVER_API_KEY).

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
from leaklab.gto_utils import compute_spot_hash
from leaklab.gto_wizard_client import query_spot


def _preflight():
    """Confirma que o GW está alcançável E logado (não auth_unavailable)."""
    import requests
    url = os.environ.get('GTO_SOLVER_URL', '').rstrip('/')
    key = os.environ.get('GTO_SOLVER_API_KEY', '')
    if not url:
        return False, "GTO_SOLVER_URL vazio (configure o backend/.env)"
    try:
        r = requests.post(f"{url}/gto-wizard",
                          json={'street': 'flop', 'position': 'BTN', 'board': ['As', 'Kd', '2c'],
                                'hero_stack_bb': 40, 'facing_size_bb': 0, 'pot_bb': 5, 'num_players': 2},
                          headers={'x-api-key': key}, timeout=20)
        if r.status_code == 503 or 'auth_unavailable' in r.text:
            return False, "GW retornou auth_unavailable — Chrome da VM NÃO está logado no GTO Wizard (logue via VNC e tente de novo)"
        if r.status_code == 401:
            return False, "401 unauthorized — GTO_SOLVER_API_KEY inválida"
        return True, f"GW OK (HTTP {r.status_code})"
    except Exception as e:
        return False, f"GW inalcançável: {e}"


def _spots_for_tournament(raw):
    """Gera params de spot postflop (street, position, board, hand, stack, facing_bb, pot_bb, n)."""
    out = []
    for hand in parse_hand_history(raw):
        bb = hand.bb or 1.0
        for di in build_decision_inputs_for_hand(hand):
            if di['street'] in ('preflop',):
                continue
            sp = di.get('spot', {})
            board = sp.get('board') or []
            pos = sp.get('position', '')
            if not board or not pos:
                continue
            out.append({
                'street':        di['street'],
                'position':      pos,
                'board':         board,
                'hero_hand':     di.get('hero_cards', []),
                'hero_stack_bb': float(sp.get('effectiveStackBb') or 20.0),
                'facing_bb':     round(float(sp.get('facingSize') or 0.0) / bb, 2),
                'pot_bb':        float(sp.get('potBb') or 0.0),
                'num_players':   int(sp.get('nActiveOpponents') or 1) + 1,
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
    print(f"Preflight GW: {'✅' if ok else '❌'} {msg}")
    if not ok:
        print("\nAbortado — sem GW logado não dá pra capturar. (Os spots pendentes seguem no heurístico, "
              "que é honesto.) Logue o Chrome no GTO Wizard na VM e rode de novo.")
        sys.exit(1)

    conn = get_conn()
    q = "SELECT id, tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL"
    params = []
    if args.tournament:
        q += " AND tournament_id = ?"; params.append(args.tournament)
    rows = conn.execute(q, params).fetchall()

    seen_hashes = set()
    captured = skipped = not_found = errs = 0
    for r in rows:
        for s in _spots_for_tournament(r['raw_text']):
            if captured + not_found + skipped >= args.limit:
                break
            h = compute_spot_hash(s['street'], s['position'], s['board'], s['hero_hand'],
                                  s['hero_stack_bb'], s['facing_bb'])
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            existing = get_gto_node(h)
            if existing and existing.get('source') == 'gto_wizard':
                skipped += 1; continue   # já tem GW
            try:
                gw = query_spot(street=s['street'], position=s['position'], board=s['board'],
                                hero_stack_bb=s['hero_stack_bb'], facing_size_bb=s['facing_bb'],
                                pot_bb=s['pot_bb'], num_players=s['num_players'])
            except Exception as e:
                errs += 1; continue
            if not gw or not gw.get('found') or not gw.get('strategy'):
                not_found += 1; continue
            best = max(gw['strategy'], key=lambda x: x['frequency'])
            node = {
                'street': s['street'], 'position': s['position'], 'board': s['board'],
                'hero_hand': s['hero_hand'], 'hero_stack_bb': s['hero_stack_bb'],
                'facing_size_bb': s['facing_bb'], 'gto_action': best['action'],
                'gto_freq': best['frequency'], 'exploitability_pct': None, 'source': 'gto_wizard',
                'strategy_json': json.dumps(
                    {x['action']: {'frequency': x['frequency'], 'betsize_bb': x.get('betsize_bb')}
                     for x in gw['strategy']}, sort_keys=True),
            }
            if args.apply:
                insert_gto_nodes([node])
            captured += 1
            print(f"  {'capturado' if args.apply else 'capturaria'}: {s['street']} {s['position']} "
                  f"{s['board']} {s['hero_stack_bb']:.0f}bb → {best['action']}")

    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN'}: capturados={captured} | já tinha GW={skipped} "
          f"| GW sem solução={not_found} | erros={errs}")
    if args.apply and args.resync and captured:
        print("\nRodando resync_postflop_gto --apply…")
        os.system(f'"{sys.executable}" scripts/resync_postflop_gto.py --apply')


if __name__ == '__main__':
    main()
