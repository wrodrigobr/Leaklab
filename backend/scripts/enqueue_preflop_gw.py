"""
enqueue_preflop_gw.py — Valida spots preflop contra o GTO Wizard ao vivo.

Reutiliza GWAuth/GWClient de benchmark_gtowizard_live.py (mesmo token, mesma API).
Para preflop, a query usa preflop_actions até o ponto de decisão do hero (board vazio).

Uso:
    cd backend
    $env:GW_ACCESS_TOKEN = 'eyJ...'   # copiar do DevTools -> Network -> Authorization
    python scripts/enqueue_preflop_gw.py --limit 10
    python scripts/enqueue_preflop_gw.py --limit 10 --dry-run   # só exibe, nao grava

Resultado:
    - Exibe tabela comparando best_action (leaklab) vs GTO Wizard
    - Atualiza gto_action/gto_label nas decisions (a menos que --dry-run)
    - Grava nós em gto_nodes quando o GTO Wizard retornar estratégia válida
"""
from __future__ import annotations
import json, os, sys, time
import argparse
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Reutiliza GWAuth/GWClient do benchmark_gtowizard_live
_live = BACKEND_DIR / "scripts" / "benchmark_gtowizard_live.py"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("live", _live)
_mod  = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
GWAuth   = _mod.GWAuth
GWClient = _mod.GWClient

# ── Constantes ─────────────────────────────────────────────────────────────────
HAR_DEFAULT = BACKEND_DIR / "docs" / "app.gtowizard.com.har"
DB_DEFAULT  = BACKEND_DIR / "data" / "leaklab.db"
GW_GAMETYPE = "MTTGeneral"
GW_STACKS   = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]

# Posições em ordem de ação (9-max, 8 posições de decisão)
POSITIONS_ORDER = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
# Aliases para normalização
POS_ALIAS = {"UTG+2": "LJ", "UTG1": "UTG+1", "MP": "LJ", "EP": "UTG", "MP1": "HJ", "MP2": "CO"}

# Raise size padrão na árvore MTTGeneral (confirmado via API)
GW_OPEN_SIZE = 2.3


def _norm_pos(pos: str) -> str:
    pos = (pos or "").upper().strip()
    return POS_ALIAS.get(pos, pos)


def _nearest_snap(stack: float) -> float:
    return min(GW_STACKS, key=lambda s: abs(s - stack))


# ── Constrói action string até o ponto de decisão ─────────────────────────────

def _preflop_decision_point(
    position: str,
    facing_bet: float,
    is_3bet: bool,
) -> str | None:
    """
    Retorna a string de ações preflop até (não incluindo) a ação do hero.
    Ex: BTN RFI -> "F-F-F-F-F"  (UTG/UTG+1/LJ/HJ/CO foldaram)
        BB vs BTN raise -> "F-F-F-F-F-R2.3-F"  (todos fold até BTN, BTN abre, SB fold)
    """
    pos = _norm_pos(position)
    if pos not in POSITIONS_ORDER:
        return None

    hero_idx = POSITIONS_ORDER.index(pos)

    if is_3bet:
        # 3-bet pot: muito complexo reconstruir sem info do villão — pular
        return None

    if facing_bet == 0 and pos == "BB":
        # BB free play (limp pot): assume SB completou
        # F-F-F-F-F-C-F  (todos fold até SB, SB limp, BB decide)
        actions = ["F"] * (hero_idx - 1) + ["C"]
        return "-".join(actions)

    if facing_bet == 0:
        # RFI: todos antes do hero foldaram
        actions = ["F"] * hero_idx
        return "-".join(actions) if actions else ""

    # facing_bet > 0: hero está enfrentando uma abertura
    # Assume que o raise veio do BTN (cenário mais comum para blinds)
    # ou do jogador imediatamente anterior (para posições IP)
    if pos == "BB":
        # Assume BTN abriu, SB foldou
        btn_idx = POSITIONS_ORDER.index("BTN")
        sb_idx  = POSITIONS_ORDER.index("SB")
        actions = []
        for i in range(hero_idx):
            if i < btn_idx:
                actions.append("F")
            elif i == btn_idx:
                actions.append(f"R{GW_OPEN_SIZE}")
            elif i == sb_idx:
                actions.append("F")
        return "-".join(actions)

    if pos == "SB":
        # Assume BTN abriu
        btn_idx = POSITIONS_ORDER.index("BTN")
        actions = []
        for i in range(hero_idx):
            if i < btn_idx:
                actions.append("F")
            elif i == btn_idx:
                actions.append(f"R{GW_OPEN_SIZE}")
        return "-".join(actions)

    # Posição IP enfrentando raise: assume UTG abriu, todos entre foldaram
    actions = []
    for i in range(hero_idx):
        actions.append("F" if i != 0 else f"R{GW_OPEN_SIZE}")
    return "-".join(actions)


# ── Normalização de ações ─────────────────────────────────────────────────────

def _norm_action(a: str) -> str:
    a = (a or "").lower().strip()
    if a in ("jam", "shove", "allin", "all-in", "all_in"):
        return "allin"
    if a in ("raise", "3bet"):
        return "raise"
    return a


def _classify_gw(action_taken: str, strategy: dict) -> tuple[str, str]:
    """Retorna (gto_label, gto_action) a partir da estratégia GTO Wizard."""
    if not strategy:
        return None, None

    top_action = max(strategy, key=lambda k: strategy[k])
    acted = _norm_action(action_taken)
    # Mapeamento para chaves da estratégia GTO Wizard
    acted_gw = {"raise": "raise", "allin": "allin", "fold": "fold",
                "call": "call", "check": "check"}.get(acted, acted)

    freq = strategy.get(acted_gw, 0.0)

    if freq >= 0.60:
        lbl = "gto_correct"
    elif freq >= 0.30:
        lbl = "gto_mixed"
    elif freq >= 0.10:
        lbl = "gto_minor_deviation"
    else:
        lbl = "gto_critical"

    return lbl, top_action


# ── Busca decisões preflop pendentes ─────────────────────────────────────────

def fetch_preflop_decisions(db_path: Path, limit: int, user_id: int | None) -> list[dict]:
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    where = [
        "d.street = 'preflop'",
        "d.label IN ('small_mistake','clear_mistake')",
        "d.position IS NOT NULL AND d.position != ''",
        "d.hero_cards IS NOT NULL AND d.hero_cards != ''",
    ]
    if user_id:
        where.append(f"t.user_id = {user_id}")
    q = f"""
        SELECT d.id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.gto_label, d.gto_action,
               d.hero_cards, d.pot_size, t.user_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {" AND ".join(where)}
        ORDER BY d.id DESC
        LIMIT {limit}
    """
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",   type=int,  default=10)
    parser.add_argument("--user-id", type=int,  default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db",      default=str(DB_DEFAULT))
    parser.add_argument("--har",     default=str(HAR_DEFAULT))
    args = parser.parse_args()

    # Auth
    auth, anal_id = GWAuth.from_env_or_har(Path(args.har))
    client = GWClient(auth, anal_id)

    # Decisões
    decisions = fetch_preflop_decisions(Path(args.db), args.limit, args.user_id)
    print(f"\n{len(decisions)} spots preflop carregados para validacao GTO Wizard\n")

    if not decisions:
        print("Nenhum spot encontrado. Verifique o banco e os filtros.")
        return

    import sqlite3
    db = sqlite3.connect(str(args.db))
    db.row_factory = sqlite3.Row

    # Cabeçalho
    print(f"{'ID':>7}  {'POS':<6} {'STK':>6} {'FACED':>6} {'PLAYED':<8} "
          f"{'BEST':8} {'GW_TOP':<8} {'GW_FREQ':>8} {'LABEL':<22} {'MATCH'}")
    print("-" * 100)

    total = matched = updated = api_ok = 0

    for d in decisions:
        pos    = _norm_pos(d["position"])
        stack  = float(d["stack_bb"] or 20)
        facing = float(d["facing_bet"] or 0)
        is3bet = bool(d["is_3bet"])
        played = _norm_action(d["action_taken"] or "")
        best   = _norm_action(d["best_action"] or "")

        total += 1

        # Constrói action string até o ponto de decisão
        decision_point = _preflop_decision_point(pos, facing, is3bet)
        if decision_point is None:
            print(f"{d['id']:>7}  {pos:<6} {stack:>6.1f} {facing:>6.1f} {played:<8} "
                  f"{best:<8} {'SKIP':<8} {'':>8} {'3bet/desconhecido':<22}")
            continue

        snap = _nearest_snap(stack) + 0.125

        # Query GTO Wizard: preflop sem board
        params = {
            "gametype":        GW_GAMETYPE,
            "depth":           snap,
            "stacks":          "",
            "preflop_actions": decision_point,
            "flop_actions":    "",
            "turn_actions":    "",
            "river_actions":   "",
            "board":           "",
        }

        gw_result = client.spot_solution(params)
        time.sleep(0.6)  # respeita rate limit

        strategy   = {}
        gw_top     = None
        gw_freq    = 0.0
        gto_label  = None
        gto_action = None

        if gw_result and gw_result.get("action_solutions"):
            api_ok += 1
            for sol in gw_result["action_solutions"]:
                t    = (sol.get("action", {}).get("type") or "").lower()
                freq = float(sol.get("total_frequency", 0))
                name = {"check": "check", "call": "call", "fold": "fold",
                        "bet": "raise", "raise": "raise", "all_in": "allin"}.get(t, t)
                strategy[name] = strategy.get(name, 0.0) + freq

            if strategy:
                gw_top  = max(strategy, key=lambda k: strategy[k])
                gw_freq = strategy[gw_top]
                gto_label, gto_action = _classify_gw(played, strategy)

        # Verifica match: nosso best_action vs GTO Wizard top
        match_sym = ""
        if gw_top:
            norm_best = _norm_action(best)
            norm_gw   = _norm_action(gw_top)
            if norm_best == norm_gw:
                matched += 1
                match_sym = "OK"
            else:
                match_sym = f"!diverge ({gw_top})"

        freq_str = f"{gw_freq:.0%}" if gw_freq else "n/a"
        lbl_str  = gto_label or ("sem resposta" if gw_result is not None else "API falhou")
        print(f"{d['id']:>7}  {pos:<6} {stack:>6.1f} {facing:>6.1f} {played:<8} "
              f"{best:<8} {(gw_top or 'n/a'):<8} {freq_str:>8} {lbl_str:<22} {match_sym}")

        # Exibe estratégia completa do GTO Wizard
        if strategy:
            strat_str = "  GW: " + " | ".join(
                f"{k} {v:.0%}"
                for k, v in sorted(strategy.items(), key=lambda x: -x[1])
            )
            print(strat_str)

        # Grava no DB
        if not args.dry_run and gto_label and gto_action:
            db.execute(
                "UPDATE decisions SET gto_action=?, gto_label=? WHERE id=?",
                (gto_action, gto_label, d["id"])
            )
            updated += 1

    if not args.dry_run:
        db.commit()
    db.close()

    print()
    print("=" * 70)
    print(f"Total spots       : {total}")
    print(f"GTO Wizard ok     : {api_ok}")
    print(f"Match leaklab/GW  : {matched}/{api_ok if api_ok else total}  "
          f"({matched/api_ok*100:.0f}%" if api_ok else "")
    print(f"DB atualizados    : {updated}  (dry_run={args.dry_run})")
    if api_ok < total:
        print(f"\nAVISO: {total - api_ok} spots sem resposta GW.")
        print("Verifique se GW_ACCESS_TOKEN ainda é válido (expira em ~15min).")
    print()


if __name__ == "__main__":
    main()
