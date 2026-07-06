"""
analyze_relookup_coverage.py — ANÁLISE (read-only) do ganho de um re-lookup postflop HU.

Responde: "quantas decisões postflop HU hoje UNCOVERED já teriam um nó no banco (gto_nodes)
se re-consultássemos agora?" — o ganho de cobertura de graça, sem solvar nada. Em prod o
banco de nós é bem maior que em dev, então o número aqui é o real do ambiente onde roda.

NÃO escreve nada. Só compute_spot_hash + get_gto_node (o MESMO hash do engine/lookup_gto).
Multiway fica de fora (teto HU-only do solver). Preflop fica de fora (ranges estáticas).

Uso:
    python scripts/analyze_relookup_coverage.py                 # todos os torneios
    python scripts/analyze_relookup_coverage.py --tid 426       # um torneio
    python scripts/analyze_relookup_coverage.py --user-id 13    # de um usuário
    python scripts/analyze_relookup_coverage.py --limit 200     # cap de torneios
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_hand_history                       # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand         # noqa: E402
from leaklab.gto_utils import compute_spot_hash                     # noqa: E402
from database.repositories import get_conn, get_gto_node, _adapt    # noqa: E402

_POST = ('flop', 'turn', 'river')


def _has_node(street, pos, board, hero_hand, stack, facing) -> bool:
    """Read-only: nó com strategy_json existe pro spot? (variantes exact/genérico/sem-facing)."""
    if not board or not pos:
        return False
    for _hh, _f in ((hero_hand, facing), ([], facing), ([], 0.0)):
        try:
            n = get_gto_node(compute_spot_hash(street.lower(), pos.upper(), board, _hh, stack, _f, ''))
        except Exception:
            n = None
        if n and n.get('strategy_json'):
            return True
    return False


def _tournaments(conn, tid, user_id, limit):
    q = "SELECT id, tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL"
    params = []
    if tid:
        q += " AND id = ?"; params.append(tid)
    elif user_id:
        q += " AND user_id = ?"; params.append(user_id)
    q += " ORDER BY id DESC"
    if limit:
        q += " LIMIT ?"; params.append(limit)
    return [dict(r) for r in conn.execute(_adapt(q), tuple(params)).fetchall()]


def analyze(args):
    conn = get_conn()
    try:
        tours = _tournaments(conn, args.tid, args.user_id, args.limit)
        print(f"Analisando {len(tours)} torneio(s)...\n")
        g_hu = g_hu_node = g_cov = g_multi = 0
        movers = []
        for t in tours:
            # cobertura postflop HU atual (do banco)
            row = conn.execute(_adapt(
                "SELECT "
                " SUM(CASE WHEN (n_active_opponents IS NULL OR n_active_opponents<2) THEN 1 ELSE 0 END) hu,"
                " SUM(CASE WHEN (n_active_opponents IS NULL OR n_active_opponents<2) AND gto_label IS NOT NULL AND gto_label!='' THEN 1 ELSE 0 END) hu_cov,"
                " SUM(CASE WHEN n_active_opponents>=2 THEN 1 ELSE 0 END) multi "
                "FROM decisions WHERE tournament_id=? AND lower(street) IN ('flop','turn','river')"),
                (t['id'],)).fetchone()
            d = dict(row)
            hu_cov = int(d.get('hu_cov') or 0); multi = int(d.get('multi') or 0)
            # nós existentes por spot (rebuild p/ board/stack/facing)
            try:
                hands = parse_hand_history(t['raw_text'])
            except Exception:
                continue
            hu_node = 0
            for h in hands:
                for di in build_decision_inputs_for_hand(h):
                    sp = di.get('spot', {})
                    if di['street'] in _POST and (sp.get('nActiveOpponents') is None or sp.get('nActiveOpponents') < 2):
                        if _has_node(di['street'], sp.get('position', ''), sp.get('board', []),
                                     di.get('hero_cards', []), float(sp.get('effectiveStackBb') or 20),
                                     float(sp.get('facingToBb') or 0)):
                            hu_node += 1
            recoverable = max(0, hu_node - hu_cov)   # tem nó mas ainda não rotulado
            g_hu += int(d.get('hu') or 0); g_hu_node += hu_node; g_cov += hu_cov; g_multi += multi
            if recoverable:
                movers.append((t['tournament_id'], recoverable))

        print("=" * 64)
        print(f"Decisões postflop HU (total):            {g_hu}")
        print(f"  já cobertas (gto_label):               {g_cov}")
        print(f"  com nó BRUTO, ainda uncovered:         {g_hu_node - g_cov if g_hu_node > g_cov else 0}")
        print(f"Decisões postflop MULTIWAY (teto, ficam): {g_multi}")
        print()
        print("ATENÇÃO: 'com nó bruto' é TETO OTIMISTA (só existência de nó). O grader real")
        print("(evaluate_decision) rejeita nós por hero-IP / cap 60bb / hand-aware / qualidade,")
        print("então o ganho GRADEÁVEL é MENOR (frequentemente 0). Número autoritativo:")
        print("  python scripts/resync_postflop_gto.py --street postflop --fill-only   (olhe 'appeared')")
        if movers:
            movers.sort(key=lambda x: -x[1])
            print("\nTorneios que mais ganhariam (tournament_id: +decisões):")
            for tid_, n in movers[:15]:
                print(f"  {tid_}: +{n}")
        print("=" * 64)
        print("Read-only: nada foi alterado. Ganho REAL = o do ambiente onde rodou (prod > dev).")
    finally:
        conn.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tid', type=int, default=None, help='um torneio (id do banco)')
    ap.add_argument('--user-id', type=int, default=None, help='torneios de um usuário')
    ap.add_argument('--limit', type=int, default=0, help='cap de torneios (0 = todos)')
    analyze(ap.parse_args())
