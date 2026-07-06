"""Solve + attach dos spots POSTFLOP HU sem GTO — cap de 60bb (Opção B), por decisão.

Para cada decisão postflop heads-up sem gto_label (o mapa de postflop_hu_gto_gaps):
  1. reconstrói o spot pelo PARSER ATUAL (match por hand_id+street+AÇÃO — uma street pode
     ter +1 decisão do hero);
  2. SOLVA hand-aware no VM (lookup_gto require_hand_aware), que JÁ capa o stack efetivo a
     60bb (_solver_params_for_stack) — não estoura a RAM por profundidade; ranges largas
     ainda podem falhar (6GB) e o spot é pulado honestamente;
  3. re-avalia com evaluate_decision (autoritativo) e, se o gto_label passou a existir,
     ATUALIZA SÓ aquela decisão (label/best_action/gto_label/gto_action). Não toca outras.

Resumível: pula quem já tem gto_label. Commit por decisão. Read-only sem --apply.

Uso:
    python scripts/solve_attach_postflop_hu_gaps.py             # dry-run (solva + mostra)
    python scripts/solve_attach_postflop_hu_gaps.py --apply
    python scripts/solve_attach_postflop_hu_gaps.py --no-solve  # só re-attach (sem solver)
"""
import os, sys, argparse
from pathlib import Path
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env é conveniência de DEV; em prod (container) não existe — as envs já vêm do compose.
# Ler só se existir, senão o script quebra em prod (FileNotFoundError no /app/.env).
_envp = Path(os.path.join(os.path.dirname(__file__), '..', '.env'))
if _envp.exists():
    for _l in _envp.read_text().splitlines():
        if '=' in _l and not _l.strip().startswith('#'):
            _k, _v = _l.split('=', 1); os.environ.setdefault(_k.strip(), _v.strip())
os.environ['TEXAS_HERO_IP'] = '1'
os.environ['TEXAS_HERO_IP_FACING'] = '1'

import sqlite3
from database.schema import get_conn
from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.gto_solver import lookup_gto

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')


def _na(a):
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    return 'allin' if s in ('shove', 'jam', 'allin') else s


def _norm(s):
    return (s or '').strip().lower() or None


def _gaps():
    c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True, timeout=30); c.row_factory = sqlite3.Row
    HU = "(COALESCE(n_active_opponents, num_players-1) = 1)"
    rows = c.execute(f"""SELECT id,tournament_id,hand_id,street,action_taken,stack_bb,label,best_action
        FROM decisions WHERE lower(street) IN ('flop','turn','river') AND {HU}
        AND (gto_label IS NULL OR gto_label='') ORDER BY tournament_id,street""").fetchall()
    out = [dict(r) for r in rows]
    c.close()
    return out


def _di_for(hands, hand_id, street, action):
    h = hands.get(str(hand_id))
    if not h:
        return None
    for di in build_decision_inputs_for_hand(h):
        if di['street'] == street and _na(di.get('player_action')) == _na(action):
            return di
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--no-solve', action='store_true', help='pula o solve; só re-attach do que já existe')
    args = ap.parse_args()

    gaps = _gaps()
    by_tid = defaultdict(list)
    for g in gaps:
        by_tid[g['tournament_id']].append(g)

    ro = sqlite3.connect(f'file:{DB}?mode=ro', uri=True, timeout=30); ro.row_factory = sqlite3.Row
    wconn = get_conn() if args.apply else None
    stats = Counter()
    print(f"{len(gaps)} spots postflop HU sem GTO. solve={'OFF' if args.no_solve else 'ON (cap 60bb)'} "
          f"apply={'SIM' if args.apply else 'dry-run'}\n")

    for tid, gs in by_tid.items():
        raw = ro.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        hands = {str(h.hand_id): h for h in parse_pokerstars_file_from_text(raw['raw_text'])} if raw and raw['raw_text'] else {}
        for g in gs:
            di = _di_for(hands, g['hand_id'], g['street'], g['action_taken'])
            tag = f"#{g['id']} t{tid} {g['street']}/{g['action_taken']} stk={g['stack_bb']}"
            if not di:
                print(f"  {tag}: SEM-DI (parser não casou)"); stats['no_di'] += 1
                continue
            sp = di['spot']
            # 1. solve (capado a 60bb internamente)
            if not args.no_solve:
                try:
                    r = lookup_gto(
                        street=g['street'], position=(sp.get('position') or '').upper(),
                        board=sp.get('board') or [], hero_hand=di.get('hero_cards') or [],
                        hero_stack_bb=float(sp.get('effectiveStackBb') or 0),
                        vs_position=(sp.get('villainPosition') or '').upper(),
                        pot_bb=float(sp.get('potBb') or 0), facing_size_bb=float(sp.get('facingToBb') or 0),
                        bb_chips=1.0, allow_remote_solve=True, block_remote=True, require_hand_aware=True,
                        pot_type=sp.get('potType', ''), opener=sp.get('preflopOpener', ''),
                        threebettor=sp.get('preflop3bettor', ''))
                    src = r.get('source')
                except Exception as e:
                    print(f"  {tag}: SOLVE-ERRO {e!s:.70}"); stats['solve_err'] += 1
                    continue
            # 2. re-avalia (autoritativo) e attach
            ev = evaluate_decision(di)
            gd = ev.get('gto') or {}
            gl = _norm(gd.get('gto_label'))
            if not gl:
                why = 'ungradeable' if (ev.get('gto') or {}).get('ungradeable_action') else 'sem-cobertura'
                print(f"  {tag}: NÃO ATRIBUIU ({why})"); stats[why] += 1
                continue
            new = {'label': (ev.get('evaluation') or {}).get('label') or None,
                   'best': ev.get('bestAction') or None, 'gto_label': gl,
                   'gto_action': _norm(gd.get('gto_action'))}
            print(f"  {tag}: GTO! {new['gto_label']}/{new['gto_action']} "
                  f"(label {g['label']}->{new['label']}, best {g['best_action']}->{new['best']})")
            stats['attached'] += 1
            if args.apply:
                wconn.execute('UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=? WHERE id=?',
                              (new['label'], new['best'], new['gto_label'], new['gto_action'], g['id']))
                wconn.commit()

    ro.close()
    if wconn:
        wconn.close()
    print(f"\nResumo: {dict(stats)}")
    if not args.apply:
        print("DRY-RUN — rode com --apply para gravar.")


if __name__ == '__main__':
    main()
