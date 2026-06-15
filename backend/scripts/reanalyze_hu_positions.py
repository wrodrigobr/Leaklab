"""Re-analisa as decisões HEADS-UP (num_players=2) após o fix de posição (botão=SB).

As decisões HU foram gravadas com SB/BB trocados → posição/best/label/gto errados.
Aqui re-parseia os torneios afetados, reconstrói os spots pelo pipeline ATUAL (já com o
fix) e regrava label/best_action/gto_label/gto_action das decisões HU. Match por
(hand_id, street, action_taken). Read-only sem --apply.

Uso:
    python scripts/reanalyze_hu_positions.py            # dry-run
    python scripts/reanalyze_hu_positions.py --apply
"""
import sys, os, argparse
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
for _l in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in _l and not _l.strip().startswith('#'):
        _k, _v = _l.split('=', 1); os.environ.setdefault(_k.strip(), _v.strip())

from database.schema import get_conn
from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def _norm(s):
    return (s or '').strip().lower() or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    conn = get_conn()
    try:
        conn.execute('PRAGMA busy_timeout=8000')
    except Exception:
        pass

    rows = conn.execute(
        "SELECT id, tournament_id, hand_id, street, action_taken, position, label, best_action, gto_label "
        "FROM decisions WHERE num_players = 2").fetchall()
    by_tid = defaultdict(list)
    for r in rows:
        by_tid[r['tournament_id']].append(dict(r))
    print(f"Decisões HU: {len(rows)} em {len(by_tid)} torneio(s)")

    changed = 0
    kinds = Counter()
    ex = []
    for tid, decs in by_tid.items():
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not raw or not raw['raw_text']:
            continue
        try:
            hands = {str(h.hand_id): h for h in parse_pokerstars_file_from_text(raw['raw_text'])}
        except Exception:
            continue
        # índice de di por (hand_id, street, action)
        for d in decs:
            h = hands.get(str(d['hand_id']))
            if not h:
                continue
            match = None
            for di in build_decision_inputs_for_hand(h):
                if di['street'] == d['street'] and _norm(di.get('player_action')) == _norm(d['action_taken']):
                    match = di
                    break
            if not match:
                continue
            try:
                ev = evaluate_decision(match)
            except Exception:
                continue
            g = ev.get('gto') or {}
            new = {
                'pos':   match['spot'].get('position'),
                'label': (ev.get('evaluation') or {}).get('label') or d['label'],
                'best':  ev.get('bestAction') or d['best_action'],
                'gl':    _norm(g.get('gto_label')),
                'ga':    _norm(g.get('gto_action')),
            }
            diff = (new['label'] != d['label'] or new['best'] != d['best_action']
                    or new['gl'] != _norm(d['gto_label']) or new['pos'] != d['position'])
            if not diff:
                continue
            changed += 1
            if new['pos'] != d['position']:
                kinds['pos_fix'] += 1
            if new['gl'] and not _norm(d['gto_label']):
                kinds['gto_appeared'] += 1
            if new['label'] != d['label']:
                kinds['label_changed'] += 1
            if len(ex) < 14:
                ex.append(f"  #{d['id']} {d['hand_id']} {d['street']}/{d['action_taken']} | "
                          f"pos {d['position']}->{new['pos']} | label {d['label']}->{new['label']} | "
                          f"best {d['best_action']}->{new['best']} | gto {_norm(d['gto_label'])}->{new['gl']}")
            if args.apply:
                # posição NÃO é coluna gravável aqui? é: decisions.position existe.
                conn.execute(
                    "UPDATE decisions SET position=?, label=?, best_action=?, gto_label=?, gto_action=? WHERE id=?",
                    (new['pos'], new['label'], new['best'], new['gl'], new['ga'], d['id']))

    if args.apply:
        conn.commit()
    conn.close()
    print(f"\nMudam: {changed} | {dict(kinds)}")
    if ex:
        print("Exemplos:\n" + "\n".join(ex))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == '__main__':
    main()
