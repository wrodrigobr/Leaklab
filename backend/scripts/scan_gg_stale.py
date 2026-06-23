"""
scan_gg_stale.py — varre torneios GGPoker e detecta os ESTALE: compara o level_bb (BB do nível)
ARMAZENADO nas decisões vs o RE-PARSEADO com o parser atual (corrigido). Divergência = blinds/stack
salvos errados pelo parser antigo (ex.: GG Level12(400/800(120)) salvo como level_bb=1.0 em vez de 800).

READ-ONLY — não escreve nada. Lista quais GG precisam deletar+re-subir e quais já estão corretos.

Uso (no container): docker compose exec -T web python scripts/scan_gg_stale.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn                 # noqa: E402
from database.repositories import _adapt              # noqa: E402
from leaklab.parser import parse_hand_history          # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand  # noqa: E402


def _is_gg(raw: str) -> bool:
    # mesmo critério do _detect_site: GG tem 'Poker Hand #', PokerStars tem 'PokerStars Hand #'
    return bool(raw) and 'Poker Hand #' in raw and 'PokerStars Hand #' not in raw


conn = get_conn()
try:
    # NB: nada de PRAGMA aqui — é SQLite-only e no Postgres aborta a transação (InFailedSqlTransaction)
    # poisonando todas as queries seguintes. Scan é read-only, não precisa de busy_timeout.
    tourneys = list(conn.execute(
        "SELECT id, tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"))

    stale, clean, skipped = [], [], []
    for t in tourneys:
        t = dict(t)
        raw = t.get('raw_text')
        if not _is_gg(raw):
            continue
        try:
            hands = parse_hand_history(raw)
        except Exception as e:
            skipped.append((t['tournament_id'], f'parse: {e}'))
            continue

        # level_bb RE-PARSEADO por mão (parser atual)
        reparsed = {}
        for h in hands:
            try:
                for di in build_decision_inputs_for_hand(h):
                    lb = di.get('context', {}).get('levelBb')
                    if lb:
                        reparsed[h.hand_id] = float(lb)
                        break
            except Exception:
                continue

        # level_bb ARMAZENADO por mão
        stored = {}
        for r in conn.execute(_adapt(
                "SELECT hand_id, level_bb FROM decisions WHERE tournament_id = ? AND level_bb IS NOT NULL"),
                (t['id'],)):
            r = dict(r)
            stored.setdefault(r['hand_id'], float(r['level_bb']))

        mismatches, example = 0, None
        for hid, lb_new in reparsed.items():
            lb_old = stored.get(hid)
            if lb_old is not None and abs(lb_old - lb_new) > 0.01:
                mismatches += 1
                if example is None:
                    example = (hid, lb_old, lb_new)

        if not reparsed or not stored:
            skipped.append((t['tournament_id'], 'sem level_bb p/ comparar'))
        elif mismatches:
            stale.append((t['tournament_id'], mismatches, len(reparsed), example))
        else:
            clean.append(t['tournament_id'])

    total = len(stale) + len(clean)
    print(f"=== GG escaneados: {total} | ESTALE: {len(stale)} | OK: {len(clean)} | pulados: {len(skipped)} ===\n")

    if stale:
        print("ESTALE (level_bb armazenado != re-parseado -> deletar + re-subir):")
        for tid, mm, tot, ex in stale:
            ex_s = f"ex mao {ex[0]}: armazenado={ex[1]} -> correto={ex[2]}" if ex else ""
            print(f"  torneio {tid}: {mm}/{tot} maos divergem   {ex_s}")
        print()

    if clean:
        print(f"OK (ja corretos, re-import seria no-op): {', '.join(str(c) for c in clean)}\n")

    if skipped:
        print("PULADOS (sem dado p/ comparar ou parse falhou):")
        for tid, why in skipped:
            print(f"  torneio {tid}: {why}")

    if not stale:
        print("Nenhum GG estale. Base GG consistente.")
finally:
    conn.close()
