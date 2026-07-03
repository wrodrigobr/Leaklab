"""Diagnóstico cirúrgico de UMA mão: mostra o que o solver retorna DE VERDADE para os spots
postflop dela, e o que o engine deriva. Read-only (o lookup_gto pode solvar 1 spot inline, mas
com a blindagem do insert não degrada nada).

Uso:
    python -m scripts.diag_hand_spot --tid 3910307458 --num 317        # pela posição na lista
    python -m scripts.diag_hand_spot --tid 3910307458 --hand <hand_id> # pelo hand_id direto
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import compute_spot_hash
from leaklab.gto_solver import lookup_gto, _effective_pot_type
from leaklab.decision_engine_v11 import _enrich_gto
from database.repositories import get_gto_node

_POSTFLOP = ('flop', 'turn', 'river')


def _arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else None


def main():
    tid = _arg('--tid')
    hand_id = _arg('--hand')
    num = _arg('--num')
    if not tid:
        print(__doc__); return

    conn = get_conn()
    trow = conn.execute("SELECT id, raw_text FROM tournaments WHERE tournament_id = ?", (tid,)).fetchone()
    if not trow:
        print(f"torneio {tid} não encontrado"); return
    t = dict(trow)

    # --num: mapeia a posição da lista (ordem do frontend: LENGTH(hand_id), hand_id, id) → hand_id
    if not hand_id and num:
        rows = conn.execute(
            "SELECT hand_id FROM decisions WHERE tournament_id = ? "
            "GROUP BY hand_id ORDER BY LENGTH(hand_id), hand_id", (t['id'],)).fetchall()
        hids = [dict(r)['hand_id'] for r in rows]
        idx = int(num) - 1
        if 0 <= idx < len(hids):
            hand_id = hids[idx]
            print(f"mao #{num} -> hand_id={hand_id}")
        else:
            print(f"--num {num} fora do intervalo (1..{len(hids)})"); return

    hands = parse_hand_history(t['raw_text'])
    target = next((h for h in hands if str(getattr(h, 'hand_id', '')) == str(hand_id)), None)
    if not target:
        print(f"hand_id {hand_id} não encontrado no raw"); return

    dis = build_decision_inputs_for_hand(target)
    post = [d for d in dis if d.get('street') in _POSTFLOP]
    print(f"\n=== hand {hand_id} | {len(post)} decisão(ões) postflop ===\n")

    for d in post:
        spot = d.get('spot', {}) or {}
        street = d.get('street')
        pos = spot.get('position', '')
        board = spot.get('board', [])
        hero = d.get('hero_cards', [])
        stack = float(spot.get('effectiveStackBb') or 0)
        facing = float(spot.get('facingToBb') or 0)
        pt = _effective_pot_type(spot.get('potType', ''), spot.get('preflopOpener', ''),
                                 spot.get('preflop3bettor', ''), stack)
        action = d.get('player_action', '')
        print(f"--- {street} | pos={pos} board={board} hero={hero} stack={stack:.1f}bb "
              f"facing={facing:.2f}bb pot_type={pt!r} ação={action}")

        h = compute_spot_hash(street, pos, board, hero, stack, facing, pt)
        node = get_gto_node(h)
        print(f"    spot_hash={h[:12]} | nó no banco: {'SIM' if node else 'NÃO'}")
        if node:
            nd = dict(node)
            print(f"      source={nd.get('source')} exploit={nd.get('exploitability_pct')} "
                  f"gto_action={nd.get('gto_action')} strategy={'sim' if nd.get('strategy_json') else 'NÃO'}")

        # o que o ENGINE deriva (o que a decisão realmente enxerga)
        try:
            eng = _enrich_gto(d)
            print(f"    engine _enrich_gto: available={eng.get('available')} "
                  f"gto_label={eng.get('gto_label')} gto_action={eng.get('gto_action')} "
                  f"source={eng.get('source')} reason={eng.get('reason')}")
        except Exception as e:
            print(f"    engine _enrich_gto ERRO: {e}")

        # o SOLVER cru (block_remote=True força o solve remoto e devolve a estratégia)
        try:
            lg = lookup_gto(street, pos, board, hero, stack,
                            facing_size_bb=facing, pot_bb=float(spot.get('potSize') or 0),
                            vs_position=spot.get('villainPosition', ''), pot_type=pt,
                            opener=spot.get('preflopOpener', ''), threebettor=spot.get('preflop3bettor', ''),
                            block_remote=True)
            print(f"    lookup_gto(remote): found={lg.get('found')} source={lg.get('source')} "
                  f"exploit={lg.get('exploitability_pct')} queued={lg.get('queued')}")
            print(f"      strategy={json.dumps(lg.get('strategy'), ensure_ascii=False)[:400]}")
        except Exception as e:
            print(f"    lookup_gto ERRO: {e}")
        print()


if __name__ == '__main__':
    main()
