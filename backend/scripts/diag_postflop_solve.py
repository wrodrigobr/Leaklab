"""
diag_postflop_solve.py — rastreia POR QUE hand_strategy vem None num solve postflop.
Solva 1 spot (BB AhKs no 852 vs BTN) e inspeciona cada elo da cadeia:
  solver devolve hand_table? → foi persistido em gto_tree_strategies? → hand_view_for_spot acha a mão?

Uso (no server da API, dentro do container):
    docker compose exec -T web python scripts/diag_postflop_solve.py
"""
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.gto_solver import lookup_gto, hand_view_for_spot
from leaklab.gto_utils import compute_spot_hash
from database.schema import get_conn


def _parse(s, n):
    return [s[i:i + 2] for i in range(0, min(len(s), n * 2), 2)]


STREET, POS, VS = 'flop', 'BB', 'BTN'
# argv: board (ex.: Ad6c3s) + mão (ex.: 9h9d). Default = pocket pair que deu None.
BOARD = _parse(sys.argv[1], 3) if len(sys.argv) > 1 else ['Ad', '6c', '3s']
HERO  = _parse(sys.argv[2], 2) if len(sys.argv) > 2 else ['9h', '9d']
STACK, CBET, POT = 40.0, 1.65, 5.0


def main():
    print(f"GTO_SOLVER_URL: {os.environ.get('GTO_SOLVER_URL') or '(vazio)'}")
    res = lookup_gto(
        street=STREET, position=POS, board=BOARD, hero_hand=HERO,
        hero_stack_bb=STACK, vs_position=VS,
        facing_size_bb=CBET, pot_bb=POT, bb_chips=1.0,
        allow_remote_solve=True, block_remote=True, require_hand_aware=True,
    )
    print("\n[1] RESULTADO do lookup_gto:")
    print("  keys:", sorted(res.keys()))
    for k in ('found', 'source', 'exploitability_pct', 'queued'):
        print(f"  {k}: {res.get(k)}")
    sh = res.get('spot_hash')
    print(f"  spot_hash: {sh}")
    agg = res.get('strategy') or []
    print("  strategy (AGREGADO):", [(s.get('action'), round((s.get('frequency') or 0) * 100)) for s in agg])
    print("  hand_strategy:", res.get('hand_strategy'))

    conn = get_conn()
    print("\n[2] NÓ em gto_nodes (por spot_hash):")
    row = conn.execute("SELECT tree_hash, gto_action, gto_freq, exploitability_pct, "
                       "(strategy_json IS NOT NULL) AS has_strat FROM gto_nodes WHERE spot_hash=?",
                       (sh,)).fetchone()
    if not row:
        print("  (nenhum nó — o solve não foi armazenado por spot_hash)")
    else:
        d = dict(row)
        print("  tree_hash:", d.get('tree_hash'))
        print("  gto_action:", d.get('gto_action'), "| gto_freq:", d.get('gto_freq'),
              "| has_strategy_json:", d.get('has_strat'), "| expl:", d.get('exploitability_pct'))
        th = d.get('tree_hash')
        print("\n[3] ÁRVORE em gto_tree_strategies (por tree_hash):")
        if not th:
            print("  (nó SEM tree_hash → solver não devolveu hand_table OU não foi repassado/persistido)")
        else:
            tr = conn.execute("SELECT board, (hand_table IS NOT NULL) AS has_ht, actions "
                              "FROM gto_tree_strategies WHERE tree_hash=?", (th,)).fetchone()
            if not tr:
                print("  (tree_hash existe no nó, mas NÃO há linha em gto_tree_strategies → persist falhou)")
            else:
                td = dict(tr)
                print("  board armazenado:", td.get('board'), "| has_hand_table:", td.get('has_ht'),
                      "| actions:", td.get('actions'))
                print("\n[4] hand_view_for_spot direto (tree_hash, board do spot, mão):")
                hv = hand_view_for_spot(th, BOARD, HERO)
                if hv is None:
                    print("  None → investigando o mapeamento:")
                    from leaklab.gto_utils import iso_suit_map, map_cards_suits, normalize_cards
                    from database.repositories import get_tree_strategy
                    ts = get_tree_strategy(th)
                    smap = iso_suit_map(BOARD, ts['board']) if ts else None
                    print(f"    smap (naipes board {BOARD} → {ts['board'] if ts else '?'}): {smap}")
                    if ts and smap is not None:
                        mapped = map_cards_suits(normalize_cards(HERO), smap)
                        print(f"    mão {HERO} → mapeada {mapped} | cartas DISTINTAS: {len(set(mapped))}"
                              + ("  ← COLISÃO! (pair virou inválido)" if len(set(mapped)) < 2 else ""))
                        ranks = {c[0] for c in HERO}
                        combos = [h.get('hand') for h in (ts.get('hand_table') or [])
                                  if h.get('hand') and len(h['hand']) >= 4
                                  and h['hand'][0] in ranks and h['hand'][2] in ranks]
                        print(f"    combos no hand_table c/ ranks {ranks}: {combos[:12] or 'NENHUM (fora do range)'}")
                else:
                    print("  OK:", {k: hv.get(k) for k in ('best_action', 'best_ev_bb', 'weight')})
                    print("  actions:", hv.get('actions'))
    conn.close()
    print("\nDIAGNÓSTICO: o primeiro elo que vier vazio/None é onde a cadeia quebra.")


if __name__ == '__main__':
    main()
