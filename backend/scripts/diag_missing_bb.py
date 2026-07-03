"""Diagnóstico: acha mãos cujo parser NÃO extraiu o big blind (hand.bb None/0). Isso faz o
`potBb` (pipeline) cair no fallback pot/1 = pote em FICHAS → nós GTO degenerados (bug do pot).
Dump do header + linhas de blind pra revelar o formato que o SB_RE não casa.

Uso:
    python -m scripts.diag_missing_bb            # conta + 5 amostras
    python -m scripts.diag_missing_bb --all      # lista todos os (tid, hand_id)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn
from leaklab.parser import parse_hand_history

_show_all = '--all' in sys.argv


def _header_snip(raw, hand_id):
    """Primeiras linhas úteis do bloco da mão (header + blinds/level)."""
    i = raw.find(str(hand_id))
    if i < 0:
        return '(bloco não localizado)'
    start = max(raw.rfind('\n\n', 0, i), 0)
    lines = raw[start:i + 400].splitlines()
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        low = ln.lower()
        if ('level' in low or 'blind' in low or 'hold' in low or 'tournament' in low
                or 'posts' in low or ln.startswith('Poker') or ln.startswith('Game')):
            out.append(ln)
        if len(out) >= 6:
            break
    return ' | '.join(out) if out else lines[:2]


def main():
    conn = get_conn()
    rows = conn.execute("SELECT tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL").fetchall()
    total = bad = 0
    shown = 0
    bad_tids = {}
    for r in rows:
        d = dict(r)
        try:
            hands = parse_hand_history(d['raw_text'])
        except Exception:
            continue
        for h in hands:
            total += 1
            if not h.bb or h.bb <= 0:
                bad += 1
                bad_tids[d['tournament_id']] = bad_tids.get(d['tournament_id'], 0) + 1
                if _show_all:
                    print(f"{d['tournament_id']} {h.hand_id}  sb={h.sb} bb={h.bb}")
                elif shown < 5:
                    print(f"\n--- tid={d['tournament_id']} hand={h.hand_id} sb={h.sb} bb={h.bb}")
                    print(f"    {_header_snip(d['raw_text'], h.hand_id)}")
                    shown += 1
    print(f"\n=== total hands: {total} | sem bb (bb None/0): {bad} ===")
    if bad_tids:
        print("torneios afetados (tid: qtd):")
        for tid, n in sorted(bad_tids.items(), key=lambda x: -x[1])[:20]:
            print(f"  {tid}: {n}")


if __name__ == '__main__':
    main()
