"""
sync_gto_labels_from_ranges.py — Preenche gto_label/gto_action para decisões
preflop sem veredicto de solver, usando a análise de ranges estáticos.

O solver (gto_nodes) tem prioridade absoluta; este script só atualiza
decisões que ainda não têm gto_label, preenchendo o gap com o range estático.

Uso:
    cd backend
    python scripts/sync_gto_labels_from_ranges.py          # dry-run (todas as decisões)
    python scripts/sync_gto_labels_from_ranges.py --save   # persiste no banco
    python scripts/sync_gto_labels_from_ranges.py --save --tid 145  # só um torneio

API pública:
    from scripts.sync_gto_labels_from_ranges import sync_tournament
    sync_tournament(tournament_id)  # chamado automaticamente após upload
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database.schema import get_conn
from database.repositories import reconcile_tournament_labels
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type


def parse_cards(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if " " in raw:
        return raw.split()
    return [raw[i:i+2] for i in range(0, len(raw), 2)] if len(raw) % 2 == 0 else []


def quality_to_label(quality: str) -> str:
    if quality in ("correct",):
        return "gto_correct"
    if quality in ("acceptable",):
        return "gto_mixed"
    if quality in ("gto_minor_deviation", "minor_mistake"):
        return "gto_minor_deviation"
    return "gto_critical"


def _build_vs3bet_context(rows: list[dict], conn) -> set[int]:
    """Identifica decisions que sao vs_3bet por contexto: hero ja deu raise
    antes na mesma hand_id, mesma street=preflop, e agora enfrenta facing_bet>0.

    O campo decisions.is_3bet vindo do pipeline so e True quando hero da 3-bet
    (action=raise), nao quando hero FOLDA/CALLA ao 3-bet. Por isso recomputamos.

    Retorna o set de decision ids que devem ser tratados como is_3bet_pot=True.
    """
    hand_ids = {r["hand_id"] for r in rows if r.get("hand_id") and r.get("street") == "preflop"}
    if not hand_ids:
        return set()
    # Para cada hand, busca todas as decisions preflop com seus ids/actions
    placeholders = ",".join("?" * len(hand_ids))
    raised_by_hand: dict[str, list[int]] = {}
    for hid, did, act in conn.execute(
        f"SELECT hand_id, id, action_taken FROM decisions "
        f"WHERE hand_id IN ({placeholders}) AND street='preflop' ORDER BY id ASC",
        list(hand_ids),
    ).fetchall():
        if (act or "").lower() in ("raise", "jam", "shove", "allin"):
            raised_by_hand.setdefault(hid, []).append(did)

    is_vs3bet: set[int] = set()
    for r in rows:
        if r.get("street") != "preflop":
            continue
        try:
            facing = float(r.get("facing_bet") or 0)
        except Exception:
            facing = 0.0
        if facing <= 0:
            continue
        prior_raises = raised_by_hand.get(r["hand_id"], [])
        if any(prev_id < r["id"] for prev_id in prior_raises):
            is_vs3bet.add(r["id"])
    return is_vs3bet


def _process_rows(rows: list[dict], conn, dry_run: bool = True, verbose: bool = True) -> int:
    """Process a list of decision rows, filling gto_label where missing. Returns count updated."""
    updates: list[tuple] = []
    skipped = 0
    vs3bet_ids = _build_vs3bet_context(rows, conn)

    for r in rows:
        cards = parse_cards(r["hero_cards"])
        if len(cards) < 2:
            skipped += 1
            continue

        try:
            hand_type = hand_to_type(cards)
        except Exception:
            skipped += 1
            continue

        stack_bb  = float(r["stack_bb"] or 20)
        facing_bb = float(r["facing_bet"] or 0)
        pos       = r["position"] or ""
        vs_pos    = r["vs_position"] or ""
        # is_3bet_pot semantico: hero ja deu raise antes nesta hand
        # (corrige bug do pipeline que so marca True quando hero da 3-bet)
        is_3bet   = bool(r["is_3bet"]) or (r["id"] in vs3bet_ids)
        action    = (r["action_taken"] or "").lower()

        # BB free play: no facing bet, BB checks — always correct
        if pos.upper() == "BB" and facing_bb == 0 and action == "check":
            updates.append(("gto_correct", "check", r["id"]))
            continue

        try:
            result = analyze_preflop(
                position=pos,
                hero_hand_type=hand_type,
                stack_bb=stack_bb,
                action_taken=action,
                facing_size=facing_bb,
                vs_position=vs_pos,
                is_3bet_pot=is_3bet,
            )
        except Exception:
            skipped += 1
            continue

        if not result.get("available"):
            skipped += 1
            continue

        quality    = result.get("action_quality", "")
        rec_acts   = result.get("recommended_actions") or []
        new_label  = quality_to_label(quality)
        new_action = rec_acts[0] if rec_acts else (r["best_action"] or "")

        updates.append((new_label, new_action, r["id"]))
        if verbose and new_label != "gto_correct":
            print(f"  id={r['id']:>7}  {pos:<6} {stack_bb:>6.1f}bb  "
                  f"hand={hand_type:<4}  played={action:<6}  "
                  f"quality={quality:<24}  label={new_label}")

    if verbose:
        print(f"\nCom range disponivel: {len(updates)}  |  Sem range (skipped): {skipped}")

    if not updates or dry_run:
        return 0

    for new_label, new_action, dec_id in updates:
        conn.execute(
            "UPDATE decisions SET gto_label=?, gto_action=? WHERE id=?",
            (new_label, new_action, dec_id)
        )
    conn.commit()
    return len(updates)


def sync_tournament(tournament_id: int) -> int:
    """
    Preenche gto_label/gto_action para decisões preflop sem veredicto no torneio indicado.
    Chamado automaticamente após cada upload como background thread.
    Retorna o número de decisões atualizadas.
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, hand_id, street, position, stack_bb, facing_bet, is_3bet,
                   action_taken, best_action, hero_cards, vs_position
            FROM decisions
            WHERE tournament_id = ?
              AND street = 'preflop'
              AND (gto_label IS NULL OR gto_label = '')
              AND hero_cards IS NOT NULL AND hero_cards != ''
        """, (tournament_id,)).fetchall()
        rows = [dict(r) for r in rows]

        if not rows:
            return 0

        n = _process_rows(rows, conn, dry_run=False, verbose=False)
        if n:
            reconcile_tournament_labels(tournament_id)
        return n
    except Exception:
        return 0
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--tid", type=int, default=None, help="Processar apenas este tournament_id")
    args = parser.parse_args()

    conn = get_conn()

    where = "WHERE street = 'preflop' AND (gto_label IS NULL OR gto_label = '') AND hero_cards IS NOT NULL AND hero_cards != ''"
    params: list = []
    if args.tid:
        where += " AND tournament_id = ?"
        params.append(args.tid)

    rows = conn.execute(
        f"SELECT id, hand_id, street, position, stack_bb, facing_bet, is_3bet, "
        f"action_taken, best_action, hero_cards, vs_position FROM decisions {where}",
        params
    ).fetchall()
    rows = [dict(r) for r in rows]
    print(f"Preflop sem gto_label: {len(rows)}")

    n = _process_rows(rows, conn, dry_run=not args.save, verbose=True)

    if not args.save:
        print("\n[DRY RUN] Use --save para persistir.")
        conn.close()
        return

    conn.close()
    if n:
        print(f"\n{n} decisoes preflop atualizadas com veredicto de range estatico.")
        # Reconciliar labels para torneios afetados
        conn2 = get_conn()
        tids = set(r['tournament_id'] for r in conn2.execute(
            "SELECT DISTINCT tournament_id FROM decisions WHERE street='preflop' AND gto_label IS NOT NULL"
        ).fetchall())
        conn2.close()
        for tid in tids:
            r2 = reconcile_tournament_labels(tid)
            if r2:
                print(f"  Torneio {tid}: {r2} labels reconciliados.")
        if tids:
            print(f"standard_pct recalculado para {len(tids)} torneios.")
    else:
        print("\nNenhuma atualizacao necessaria.")


if __name__ == "__main__":
    main()
