"""
test_preflop_gw.py — Testa 10 spots preflop via lookup_gto → gto_wizard_client → servidor remoto.

Usa a mesma rota que o engine usa em produção:
  lookup_gto → gto_wizard_client.query_spot → POST /gto-wizard (servidor Google Cloud)
  O servidor tem o CDP/Chrome com auth do GTO Wizard.

Uso:
    cd backend
    python scripts/test_preflop_gw.py
    python scripts/test_preflop_gw.py --limit 10 --save   # salva gto_label/gto_action no DB
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from leaklab.gto_solver import lookup_gto
from leaklab.gto_wizard_client import get_status
from database.schema import get_conn

# ── Verifica status do servidor ────────────────────────────────────────────────

def check_server():
    status = get_status()
    solver_url = os.environ.get("GTO_SOLVER_URL", "n/a")
    enabled    = os.environ.get("GTO_WIZARD_ENABLED", "false")
    print(f"Servidor  : {solver_url}")
    print(f"GW enabled: {enabled}")
    print(f"GW status : {status}")
    if not status.get("auth_ok"):
        print("\nAVISO: GTO Wizard sem auth no servidor. Verifique o Chrome/CDP no servidor remoto.")
    return status


# ── Busca decisões preflop ─────────────────────────────────────────────────────

def fetch_decisions(limit: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT d.id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.gto_label, d.hero_cards,
               d.pot_size, d.level_bb
        FROM decisions d
        WHERE d.street = 'preflop'
          AND d.label IN ('small_mistake','clear_mistake')
          AND d.position IS NOT NULL AND d.position != ''
          AND d.hero_cards IS NOT NULL AND d.hero_cards != ''
        ORDER BY d.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Parsing hero_cards ─────────────────────────────────────────────────────────

def parse_hero(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    if " " in raw:
        return raw.split()
    if len(raw) % 2 == 0:
        return [raw[i:i+2] for i in range(0, len(raw), 2)]
    return []


# ── Classificação ──────────────────────────────────────────────────────────────

def _norm(a: str) -> str:
    a = (a or "").lower().strip()
    return {"jam": "allin", "shove": "allin", "all-in": "allin", "all_in": "allin",
            "raise": "raise", "3bet": "raise"}.get(a, a)


def classify(action_taken: str, strategy: list[dict]) -> tuple[str, str]:
    """Retorna (gto_label, gto_action) a partir da estratégia GTO Wizard."""
    if not strategy:
        return None, None
    top = max(strategy, key=lambda s: s["frequency"])
    gto_action = top["action"]
    played     = _norm(action_taken)
    # Busca frequência da ação jogada
    freq = 0.0
    for s in strategy:
        if _norm(s["action"]) == played:
            freq = s["frequency"]
            break
    if freq >= 0.60:
        lbl = "gto_correct"
    elif freq >= 0.30:
        lbl = "gto_mixed"
    elif freq >= 0.10:
        lbl = "gto_minor_deviation"
    else:
        lbl = "gto_critical"
    return lbl, gto_action


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--save",  action="store_true", help="Grava gto_label/gto_action no DB")
    args = parser.parse_args()

    print("=" * 70)
    status = check_server()
    print("=" * 70)
    print()

    decisions = fetch_decisions(args.limit)
    print(f"Decisoes preflop carregadas: {len(decisions)}\n")

    if not decisions:
        print("Nenhuma decisao encontrada.")
        return

    print(f"{'ID':>7}  {'POS':<6} {'STK':>6} {'FACED':>6} {'PLAYED':<8} "
          f"{'BEST':8} {'GW_TOP':<8} {'GW_FREQ':>8} {'SOURCE':<16} {'LABEL'}")
    print("-" * 105)

    total = gw_ok = matched = 0
    updates: list[tuple] = []  # (gto_label, gto_action, id)

    for d in decisions:
        pos    = (d["position"] or "").upper()
        stack  = float(d["stack_bb"] or 20)
        facing = float(d["facing_bet"] or 0)
        pot    = float(d["pot_size"] or max(facing * 2 + 2, 2))
        played = _norm(d["action_taken"] or "")
        best   = _norm(d["best_action"] or "")
        hero   = parse_hero(d["hero_cards"])

        total += 1

        # Chama lookup_gto → gto_wizard_client → servidor Google Cloud
        result = lookup_gto(
            street         = "preflop",
            position       = pos,
            board          = [],      # preflop: sem board
            hero_hand      = hero,
            hero_stack_bb  = stack,
            action_seq     = "rfi" if facing == 0 else "vs_rfi",
            facing_size_bb = facing,
            pot_bb         = pot,
        )

        source   = result.get("source", "miss")
        strategy = result.get("strategy", [])
        gto_label = gto_action = gw_top = None
        gw_freq = 0.0

        if result.get("found") and strategy:
            gw_ok += 1
            gto_label, gto_action = classify(played, strategy)
            # Ação top do GTO Wizard
            top = max(strategy, key=lambda s: s["frequency"])
            gw_top  = _norm(top["action"])
            gw_freq = top["frequency"]
            if gw_top == best:
                matched += 1

        match_str = ""
        if gw_top:
            match_str = "OK" if gw_top == best else f"! diverge ({gw_top})"

        freq_str   = f"{gw_freq:.0%}" if gw_freq else "n/a"
        label_str  = gto_label or ("sem_resultado" if result.get("found") else source)
        gw_top_str = gw_top or "n/a"

        print(f"{d['id']:>7}  {pos:<6} {stack:>6.1f} {facing:>6.1f} {played:<8} "
              f"{best:<8} {gw_top_str:<8} {freq_str:>8} {source:<16} {label_str}  {match_str}")

        # Exibe estratégia completa
        if strategy:
            strat_str = "  GW: " + " | ".join(
                f"{_norm(s['action'])} {s['frequency']:.0%}"
                for s in sorted(strategy, key=lambda s: -s["frequency"])
            )
            print(strat_str)

        if args.save and gto_label and gto_action:
            updates.append((gto_label, gto_action, d["id"]))

    # Grava no DB
    if updates:
        conn = get_conn()
        for gto_label, gto_action, did in updates:
            conn.execute(
                "UPDATE decisions SET gto_label=?, gto_action=? WHERE id=?",
                (gto_label, gto_action, did)
            )
        conn.commit()
        conn.close()
        print(f"\n{len(updates)} decisoes atualizadas no DB.")

    print()
    print("=" * 70)
    print(f"Total          : {total}")
    print(f"GTO Wizard OK  : {gw_ok}")
    if gw_ok:
        pct = matched / gw_ok * 100
        print(f"Match GW/leaklab: {matched}/{gw_ok} ({pct:.0f}%)")
    diverge = gw_ok - matched
    if diverge:
        print(f"Divergencias   : {diverge}  <- candidatos a revisar em leaklab_gto_ranges.json")
    print()


if __name__ == "__main__":
    main()
