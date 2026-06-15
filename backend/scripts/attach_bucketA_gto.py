"""Anexa o gto_label às decisões do bucket A já solvadas hand-aware — CIRÚRGICO.

Espelha a lógica do resync_postflop_gto (evaluate_decision → mesmos 4 campos:
label/best_action/gto_label/gto_action) MAS atualiza SOMENTE as decisões-alvo, por
`id`. Não toca em nenhuma outra decisão (o resync geral varreria drift pré-existente
de outros torneios, fora do escopo desta tarefa). Rode depois de solve_bucketA_handaware.

Uso:
    python scripts/attach_bucketA_gto.py --dry-run
    python scripts/attach_bucketA_gto.py --apply
"""
import os, sys, argparse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for line in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
os.environ['TEXAS_HERO_IP'] = '1'
os.environ['TEXAS_HERO_IP_FACING'] = '1'

from database.schema import get_conn
from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

# decisão-alvo: id + chaves de matching (mesmas do solve). `action` é OBRIGATÓRIO —
# uma street pode ter +1 decisão do hero (ver solve_bucketA_handaware).
TARGETS = [
    {'decision_id': 33286, 'tid': 149, 'hand_id': '260605886991', 'street': 'river', 'pos': 'CO',  'vs': 'UTG', 'action': 'bet'},
    {'decision_id': 35868, 'tid': 388, 'hand_id': '100000022',    'street': 'turn',  'pos': 'BB',  'vs': 'HJ',  'action': 'shove'},
    {'decision_id': 33118, 'tid': 148, 'hand_id': '258867235685', 'street': 'flop',  'pos': 'BTN', 'vs': 'BB',  'action': 'bet'},
    {'decision_id': 33153, 'tid': 148, 'hand_id': '258867373219', 'street': 'flop',  'pos': 'HJ',  'vs': 'BB',  'action': 'bet'},
    {'decision_id': 33087, 'tid': 147, 'hand_id': '258867150524', 'street': 'flop',  'pos': 'SB',  'vs': 'BB',  'action': 'bet'},
]


def _norm(s):
    return (s or '').strip().lower() or None


def _norm_act(a):
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    return 'allin' if s in ('shove', 'jam', 'allin') else s


def _fresh_for(conn, tgt):
    raw = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tgt['tid'],)).fetchone()
    if not raw or not raw['raw_text']:
        return None
    for h in parse_pokerstars_file_from_text(raw['raw_text']):
        if str(h.hand_id) != str(tgt['hand_id']):
            continue
        for di in build_decision_inputs_for_hand(h):
            sp = di['spot']
            if di['street'] != tgt['street']:
                continue
            if (sp.get('position') or '').upper() != tgt['pos'].upper():
                continue
            if (sp.get('villainPosition') or '').upper() != tgt['vs'].upper():
                continue
            if _norm_act(di.get('player_action')) != _norm_act(tgt['action']):
                continue
            r = evaluate_decision(di)
            g = r.get('gto') or {}
            return {
                'label':      (r.get('evaluation') or {}).get('label') or None,
                'best':       r.get('bestAction') or None,
                'gto_label':  _norm(g.get('gto_label')),
                'gto_action': _norm(g.get('gto_action')),
            }
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    conn = get_conn()
    n_upd = 0
    for tgt in TARGETS:
        row = conn.execute(
            'SELECT id, label, best_action, gto_label, gto_action FROM decisions WHERE id=?',
            (tgt['decision_id'],)).fetchone()
        if not row:
            print(f"#{tgt['decision_id']}  NÃO existe no banco")
            continue
        s = dict(row)
        f = _fresh_for(conn, tgt)
        if not f:
            print(f"#{tgt['decision_id']}  não reconstruído no parse")
            continue
        before = f"label={s['label']} best={s['best_action']} gto={_norm(s['gto_label'])}/{_norm(s['gto_action'])}"
        after  = f"label={f['label']} best={f['best']} gto={f['gto_label']}/{f['gto_action']}"
        changed = (f['label'] != s['label'] or f['best'] != s['best_action']
                   or f['gto_label'] != _norm(s['gto_label']) or f['gto_action'] != _norm(s['gto_action']))
        flag = 'APPEARED' if (f['gto_label'] and not _norm(s['gto_label'])) else ('CHANGED' if changed else 'no-op')
        print(f"#{tgt['decision_id']} [{flag}]\n    antes: {before}\n    agora: {after}")
        if args.apply and changed:
            conn.execute(
                'UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=? WHERE id=?',
                (f['label'], f['best'], f['gto_label'], f['gto_action'], s['id']))
            n_upd += 1
    if args.apply:
        conn.commit()
        print(f"\nAPLICADO — {n_upd} decisão(ões) atualizada(s).")
    else:
        print("\nDRY-RUN (use --apply)")
    conn.close()


if __name__ == '__main__':
    main()
