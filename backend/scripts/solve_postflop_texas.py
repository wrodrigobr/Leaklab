"""Popula os spots POSTFLOP pendentes (sem cobertura GTO) com o solver Texas REATIVADO,
após os fixes P0 de correção (jogador OOP/IP, facing em bb, ranges reais). Varre as
decisões dos torneios, monta os params do spot e chama lookup_gto(block_remote=True) —
que resolve via Texas no depth REAL e grava o nó (source='solver_cli').

Cobre só o que a integração faz CERTO hoje:
  - hero OOP (player 0) — heroes IP ficam pro patch do main.rs (flag TEXAS_HERO_IP);
  - HU (nActiveOpponents==1) — multiway o solver não faz (segue no heurístico);
  - stack ≤60bb (cap do solver) e facing convertível (passamos bb_chips).
O próprio lookup_gto aplica esse gate; aqui só filtramos HU pra não nem tentar multiway.

Uso:
    python -m scripts.solve_postflop_texas                 # dry-run (conta elegíveis)
    python -m scripts.solve_postflop_texas --tournament 999999
    python -m scripts.solve_postflop_texas --apply --limit 200
    python -m scripts.solve_postflop_texas --apply --resync
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
# Carrega backend/.env (GTO_SOLVER_URL/KEY) — scripts não herdam.
_envp = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_envp):
    for _l in open(_envp, encoding='utf-8'):
        _l = _l.strip()
        if _l and not _l.startswith('#') and '=' in _l:
            _k, _v = _l.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())
os.environ.setdefault('SOLVER_TIER', 'production')   # cap 60bb, iters altas

from database.schema import get_conn
from database.repositories import get_gto_node
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import compute_spot_hash
from leaklab.gto_solver import lookup_gto

_POSTFLOP = ('flop', 'turn', 'river')


def _spots(raw):
    """Spots postflop HU elegíveis (street, position, board, hero_hand, stack, facing
    chips, vs_position, bb_chips). Filtra HU; o resto do gate é do lookup_gto."""
    out = []
    for hand in parse_hand_history(raw):
        bb = float(hand.bb or 0) or 1.0
        try:
            dis = build_decision_inputs_for_hand(hand)
        except Exception:
            continue
        for di in dis:
            st = (di.get('street') or '').lower()
            if st not in _POSTFLOP:
                continue
            sp = di.get('spot', {})
            board = sp.get('board') or []
            pos = sp.get('position', '')
            hero = di.get('hero_cards', [])
            if not board or not pos or not hero:
                continue
            if int(sp.get('nActiveOpponents') or 1) != 1:   # só HU
                continue
            stack = float(sp.get('effectiveStackBb') or 20.0)
            if stack > 60.0:                                 # cap do solver
                continue
            out.append({
                'street': st, 'position': pos, 'board': board, 'hero': hero,
                'stack': stack, 'facing': float(sp.get('facingSize') or 0.0),
                'vs': sp.get('villainPosition', ''), 'bb_chips': bb,
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tournament')
    ap.add_argument('--limit', type=int, default=10_000)
    ap.add_argument('--resync', action='store_true')
    ap.add_argument('--apply', action='store_true', help='(no-op: lookup_gto já grava; presente p/ simetria)')
    args = ap.parse_args()

    conn = get_conn()
    q = "SELECT tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL"
    params = []
    if args.tournament:
        q += " AND tournament_id = ?"; params.append(args.tournament)
    rows = conn.execute(q, params).fetchall()

    seen = set()
    solved = skipped = cached = errs = 0
    for r in rows:
        for s in _spots(r['raw_text']):
            if solved + skipped + cached >= args.limit:
                break
            h = compute_spot_hash(s['street'], s['position'], s['board'], s['hero'],
                                  s['stack'], s['facing'])
            if h in seen:
                continue
            seen.add(h)
            if get_gto_node(h):                # já coberto (GW ou Texas)
                cached += 1; continue
            t0 = time.time()
            try:
                res = lookup_gto(
                    street=s['street'], position=s['position'], board=s['board'],
                    hero_hand=s['hero'], hero_stack_bb=s['stack'], vs_position=s['vs'],
                    facing_size_bb=s['facing'], pot_bb=0.0, num_players=2,
                    bb_chips=s['bb_chips'], block_remote=True,
                )
            except Exception as e:
                errs += 1
                print(f"  ERRO {s['street']} {s['position']} {''.join(s['board'])}: {e}", flush=True)
                continue
            if res.get('found') and res.get('source') == 'remote_solver':
                solved += 1
                dist = {x['action']: round(x['frequency'], 2) for x in (res.get('strategy') or [])}
                print(f"  [{time.time()-t0:.0f}s] solved: {s['street']} {s['position']} "
                      f"{''.join(s['board'])} {s['stack']:.0f}bb fac={s['facing']:.0f} → {dist}", flush=True)
            else:
                skipped += 1   # IP / facing não-convertível / vilão unknown → heurístico

    print(f"\nRESUMO: solved={solved} | já cobertos={cached} | pulados(heurístico)={skipped} | erros={errs}")
    if args.resync and solved:
        print("\nRodando resync_postflop_gto --apply…")
        os.system(f'"{sys.executable}" scripts/resync_postflop_gto.py --apply')


if __name__ == '__main__':
    main()
