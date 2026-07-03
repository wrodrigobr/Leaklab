"""Fix CIRÚRGICO de uma mão: deleta os nós postflop DEGENERADOS dela (bug do pot em fichas →
all-in fake) e re-solva com o pot CORRETO (potBb/facingToBb em BB). Só toca os spot_hash
dessa mão; nunca purga em massa. Reusa a lógica de solve do cleanup_postflop_pot_bug.

Uso:
    python -m scripts.fix_hand_spots --tid 3910307458 --num 317          # dry-run
    python -m scripts.fix_hand_spots --tid 3910307458 --num 317 --apply  # deleta+resolve (exige GTO_SOLVER_URL)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import compute_spot_hash
from leaklab.gto_solver import (_call_remote_solver, _remote_url, _remote_key,
                                _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE, _solver_params_for_stack)
from database.repositories import insert_gto_nodes, get_gto_node, GTO_EXPLOITABILITY_THRESHOLD

_POSTFLOP = ('flop', 'turn', 'river')


def _arg(f):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv and sys.argv.index(f) + 1 < len(sys.argv) else None


def main():
    tid, num, hand_id = _arg('--tid'), _arg('--num'), _arg('--hand')
    apply = '--apply' in sys.argv
    if not tid:
        print(__doc__); return

    conn = get_conn()
    trow = conn.execute("SELECT id, raw_text FROM tournaments WHERE tournament_id = ?", (tid,)).fetchone()
    if not trow:
        print(f"torneio {tid} não encontrado"); return
    t = dict(trow)

    if not hand_id and num:
        rows = conn.execute("SELECT hand_id FROM decisions WHERE tournament_id = ? "
                            "GROUP BY hand_id ORDER BY LENGTH(hand_id), hand_id", (t['id'],)).fetchall()
        hids = [dict(r)['hand_id'] for r in rows]
        idx = int(num) - 1
        if not (0 <= idx < len(hids)):
            print(f"--num {num} fora do intervalo"); return
        hand_id = hids[idx]
        print(f"mao #{num} -> hand_id={hand_id}")

    hands = parse_hand_history(t['raw_text'])
    target = next((h for h in hands if str(getattr(h, 'hand_id', '')) == str(hand_id)), None)
    if not target:
        print(f"hand_id {hand_id} não encontrado"); return

    if apply and not (_remote_url() and _remote_key()):
        print("⛔ GTO_SOLVER_URL/API_KEY ausentes — solve é remoto. Abortado."); return

    dis = build_decision_inputs_for_hand(target)
    post = [d for d in dis if (d.get('street') or '').lower() in _POSTFLOP]
    print(f"{len(post)} decisão(ões) postflop\n")

    solved = failed = 0
    for d in post:
        sp = d.get('spot', {}) or {}
        st = (d.get('street') or '').lower()
        pos = (sp.get('position') or '').upper()
        vs_pos = (sp.get('villainPosition') or '').upper()
        board = sp.get('board', [])
        hero = d.get('hero_cards', [])
        stack = float(sp.get('effectiveStackBb') or 20.0)
        pot_bb = float(sp.get('potBb') or 0.0)          # CORRETO (BB)
        facing = float(sp.get('facingToBb') or 0.0)     # CORRETO (BB)
        if not pos or not board or not hero:
            continue
        shash = compute_spot_hash(st, pos, board, hero, stack, facing)
        old = get_gto_node(shash)
        oldinfo = ''
        if old:
            od = dict(old)
            oldinfo = f"(existente: exploit={od.get('exploitability_pct')} action={od.get('gto_action')})"
        print(f"--- {st} {pos} {board} stack={stack:.1f} facing={facing:.2f} pot={pot_bb:.2f} hash={shash[:10]} {oldinfo}")

        if not apply:
            print("    [dry-run] deletaria e re-solvaria com pot correto\n")
            continue

        # 1) deleta o nó degenerado (só este hash)
        conn.execute("DELETE FROM gto_nodes WHERE spot_hash = ?", (shash,))
        conn.commit()
        # 2) re-solva com pot CORRETO
        _p = _solver_params_for_stack(stack)
        payload = {
            'street': st, 'board': board, 'position': pos, 'hero_hand': hero,
            'hero_stack_bb': stack, 'facing_size_bb': facing,
            'oop_range': _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
            'ip_range': _DEFAULT_RANGES.get(pos, _DEFAULT_RANGE_WIDE),
            'pot_bb': pot_bb,
            'effective_stack_bb': _p['effective_stack_bb'],
            'max_iterations': _p['max_iterations'],
            'target_exploitability_pct': _p['target_exploitability_pct'],
            '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero,
                      'hero_stack_bb': stack, 'facing_size_bb': facing, 'street': st, 'board': board},
        }
        try:
            res = _call_remote_solver(payload, timeout=90)
        except Exception as e:
            print(f"    solve ERRO: {e}"); failed += 1; continue
        if not res:
            print("    solve vazio"); failed += 1; continue
        exploit = res.get('exploitability') or res.get('exploitability_pct')
        if exploit is None or float(exploit) > GTO_EXPLOITABILITY_THRESHOLD:
            print(f"    rejeitado: exploit={exploit}"); failed += 1; continue
        node = {
            'spot_hash': shash, 'street': st, 'position': pos, 'board': board,
            'hero_hand': hero, 'hero_stack_bb': stack, 'facing_size_bb': facing,
            'gto_action': res['primary_action'], 'gto_freq': res['primary_freq'],
            'ev_diff': res.get('ev'), 'exploitability_pct': float(exploit),
            'iterations': res.get('iterations'), 'strategy_detail': res.get('strategy_detail'),
            'source': 'solver_cli',
        }
        if insert_gto_nodes([node]):
            print(f"    OK re-solvado: exploit={exploit} action={res['primary_action']} freq={res.get('primary_freq')}")
            solved += 1
        else:
            print("    insert rejeitado"); failed += 1
        print()

    if apply:
        print(f"FIM: {solved} re-solvados, {failed} falhos. Rode resync_postflop_gto --apply pra colar o label.")


if __name__ == '__main__':
    main()
