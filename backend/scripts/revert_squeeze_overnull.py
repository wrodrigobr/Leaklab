"""Reverte o over-NULL do fix_preflop_3bet_misclass (2026-06-15).

Contexto: aquele script foi escrito quando o engine NÃO tinha o branch `faces_squeeze`
e spots de squeeze/3-bet-cold caíam em vs_rfi (range errado). Desde então o engine
ganhou o cenário `faces_squeeze` com ranges REAIS do GW — 38 dos 42 spots squeeze-cold
SÃO cobertos corretamente (correct/gto_minor_deviation). Aplicar o fix NULLou esses 38
indevidamente (perdeu cobertura legítima; drift subiu 4→43).

Este script re-avalia cada spot squeeze-cold (`preflopRaisesFaced>=2 AND not heroWasAggressor`)
com `evaluate_decision` (autoritativo) e regrava label/best/gto_label/gto_action do engine.
Onde o engine cobre → restaura o veredito; onde não cobre (4 spots) → fica NULL honesto.

Uso:
    python scripts/revert_squeeze_overnull.py            # dry-run
    python scripts/revert_squeeze_overnull.py --apply
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
for _l in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in _l and not _l.strip().startswith('#'):
        _k, _v = _l.split('=', 1); os.environ.setdefault(_k.strip(), _v.strip())

from database.schema import get_conn
from leaklab.parser import parse_hand_history
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
    trows = conn.execute('SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id').fetchall()
    seen = set()
    restored = nullkept = changed = 0
    ex = []
    for tr in trows:
        raw = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tr['id'],)).fetchone()
        if not raw or not raw[0]:
            continue
        try:
            hands = parse_hand_history(raw[0])
        except Exception:
            continue
        for h in hands:
            try:
                dis = build_decision_inputs_for_hand(h)
            except Exception:
                continue
            for di in dis:
                if di.get('street') != 'preflop':
                    continue
                sp = di.get('spot', {})
                if not (int(sp.get('preflopRaisesFaced') or 0) >= 2 and not sp.get('heroWasAggressor')):
                    continue
                hand_id = di.get('hand_id', '')
                act = (di.get('player_action') or '').lower()
                key = (hand_id, act)
                if not hand_id or key in seen:
                    continue
                seen.add(key)
                row = conn.execute(
                    "SELECT id, label, best_action, gto_label, gto_action FROM decisions "
                    "WHERE hand_id=? AND street='preflop' AND action_taken=? LIMIT 1", (hand_id, act)).fetchone()
                if not row:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                g = r.get('gto') or {}
                new = {
                    'label': (r.get('evaluation') or {}).get('label') or row['label'],
                    'best':  r.get('bestAction') or row['best_action'],
                    'gl':    _norm(g.get('gto_label')),
                    'ga':    _norm(g.get('gto_action')),
                }
                if new['gl']:
                    restored += 1
                else:
                    nullkept += 1
                diff = (new['label'] != row['label'] or new['best'] != row['best_action']
                        or new['gl'] != _norm(row['gto_label']) or new['ga'] != _norm(row['gto_action']))
                if diff:
                    changed += 1
                    if len(ex) < 12:
                        ex.append(f"  #{row['id']} {hand_id} {di.get('position')} {act} | "
                                  f"gto {_norm(row['gto_label'])}/{_norm(row['gto_action'])} -> {new['gl']}/{new['ga']} "
                                  f"| label {row['label']}->{new['label']}")
                    if args.apply:
                        conn.execute('UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=? WHERE id=?',
                                     (new['label'], new['best'], new['gl'], new['ga'], row['id']))
    if args.apply:
        conn.commit()
    conn.close()
    print(f"squeeze-cold avaliados | engine COBRE (restaura gto): {restored} | engine sem cobertura (NULL honesto): {nullkept}")
    print(f"linhas que mudam: {changed}")
    if ex:
        print('exemplos:\n' + '\n'.join(ex))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == '__main__':
    main()
