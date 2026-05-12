"""
precompute_common_spots.py — Gera e enfileira os spots postflop mais frequentes em MTT 8-max.

Uso:
    python scripts/precompute_common_spots.py [--dry-run] [--streets flop turn] [--limit 500]

Flags:
    --dry-run       Lista os spots que seriam gerados sem enfileirar
    --streets       Quais streets gerar: flop, turn, river (padrão: flop turn)
    --limit N       Máximo de spots a enfileirar (padrão: 500)

O script gera combinações de:
  - Posições HU postflop (IP vs OOP): BTN/BB, CO/BB, SB/BB, HJ/BB, BTN/SB
  - Stack depths em MTT: 12, 15, 20, 25, 30, 40, 50bb
  - Texturas de board (flop): rainbow high, rainbow low, two-tone, monotone, paired, coordenado
  - Turn: adiciona um runout neutro ao flop base

Os spots são armazenados com hero_hand=[] (spot genérico de posição+board+stack).
lookup_gto() usa esses spots como fallback quando não encontra o hash exato com hero_hand.

Após rodar, use run_gto_worker.py para drenar a fila:
    python scripts/run_gto_worker.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from itertools import product
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from leaklab.gto_utils import compute_spot_hash
from database.repositories import get_gto_node, enqueue_solver_spot

# ── Ranges padrão por posição ──────────────────────────────────────────────────

_RANGES = {
    "BTN": "22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,54s,A2o+,K8o+,Q9o+,J9o+,T9o",
    "CO":  "22+,A2s+,K6s+,Q8s+,J8s+,T8s+,98s,87s,76s,A4o+,K9o+,Q9o+,J9o+",
    "HJ":  "44+,A2s+,K9s+,Q9s+,J9s+,T9s,A9o+,KTo+,QTo+,JTo",
    "UTG": "55+,A9s+,KTs+,QTs+,JTs,AJo+,KQo",
    "SB":  "22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,A2o+,K7o+,Q9o+",
    "BB":  "22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K4o+,Q7o+,J8o+,T8o+",
}
_RANGE_WIDE = _RANGES["BB"]

# ── Configurações por stack ────────────────────────────────────────────────────
# Dois perfis: 'remote' (Google Cloud 4 vCPU) e 'local' (Rust binário 1-core).
# O script detecta automaticamente qual usar via GTO_SOLVER_URL.

_STACK_PARAMS_REMOTE = [
    (15,   {"max_iterations": 500, "target_exploitability_pct": 2.0, "effective_stack_bb": 13}),
    (20,   {"max_iterations": 700, "target_exploitability_pct": 2.0, "effective_stack_bb": 18}),
    (30,   {"max_iterations": 700, "target_exploitability_pct": 2.0, "effective_stack_bb": 28}),
    (50,   {"max_iterations": 600, "target_exploitability_pct": 2.5, "effective_stack_bb": 45}),
    (9999, {"max_iterations": 400, "target_exploitability_pct": 3.0, "effective_stack_bb": 55}),
]

# Solver local: cap em 20bb para não travar, poucas iterações
_STACK_PARAMS_LOCAL = [
    (20,   {"max_iterations": 200, "target_exploitability_pct": 5.0, "effective_stack_bb": 18}),
    (9999, {"max_iterations": 150, "target_exploitability_pct": 5.0, "effective_stack_bb": 20}),
]


def _solver_params(stack_bb: float) -> dict:
    has_remote = bool(os.environ.get("GTO_SOLVER_URL"))
    table = _STACK_PARAMS_REMOTE if has_remote else _STACK_PARAMS_LOCAL
    for cap, p in table:
        if stack_bb <= cap:
            return p
    return table[-1][1]


# ── Definição dos spots a gerar ────────────────────────────────────────────────

# (ip_position, oop_position, label, pot_formula)
# pot_formula é uma função stack_bb → pot_bb estimado para cada cenário
_MATCHUPS = [
    # HU RFI (open + call): raise 2.5bb, call → pot ≈ 5.5bb
    ("BTN", "BB",  "btn_vs_bb_rfi",   lambda s: min(5.5, s * 0.35)),
    ("CO",  "BB",  "co_vs_bb_rfi",    lambda s: min(5.5, s * 0.35)),
    ("HJ",  "BB",  "hj_vs_bb_rfi",    lambda s: min(5.5, s * 0.35)),
    ("SB",  "BB",  "sb_vs_bb_rfi",    lambda s: min(5.0, s * 0.30)),
    # 3-bet pots: raiser 3x, 3bet 9x, call → pot ≈ 18-20bb relative
    ("BTN", "BB",  "btn_vs_bb_3bet",  lambda s: min(18.0, s * 0.70)),
    ("CO",  "BB",  "co_vs_bb_3bet",   lambda s: min(16.0, s * 0.65)),
    ("SB",  "BB",  "sb_vs_bb_3bet",   lambda s: min(14.0, s * 0.60)),
]

# Stack depths mais comuns em MTT (bb)
_STACKS = [12, 15, 20, 25, 30, 40, 50]

# Boards de flop por textura
_FLOP_BOARDS: list[tuple[str, list[str]]] = [
    # Rainbow high card
    ("rainbow_high_AK7",    ["Ah", "Kd", "7c"]),
    ("rainbow_high_AQ9",    ["Ah", "Qd", "9c"]),
    ("rainbow_high_KQ8",    ["Kh", "Qd", "8c"]),
    ("rainbow_high_AT5",    ["Ah", "Td", "5c"]),
    # Rainbow medium
    ("rainbow_mid_JT5",     ["Jh", "Td", "5c"]),
    ("rainbow_mid_987",     ["9h", "8d", "7c"]),
    ("rainbow_mid_J84",     ["Jh", "8d", "4c"]),
    ("rainbow_mid_T73",     ["Th", "7d", "3c"]),
    # Rainbow low
    ("rainbow_low_762",     ["7h", "6d", "2c"]),
    ("rainbow_low_542",     ["5h", "4d", "2c"]),
    # Two-tone high
    ("two_tone_AK7",        ["Ah", "Kh", "7d"]),
    ("two_tone_JT5",        ["Jh", "Th", "5d"]),
    ("two_tone_987",        ["9h", "8h", "7d"]),
    ("two_tone_AT5",        ["Ah", "Th", "5d"]),
    # Monotone
    ("monotone_AK7",        ["Ah", "Kh", "7h"]),
    ("monotone_987",        ["9h", "8h", "7h"]),
    ("monotone_JT5",        ["Jh", "Th", "5h"]),
    # Paired board
    ("paired_AA7",          ["Ah", "Ad", "7c"]),
    ("paired_KK9",          ["Kh", "Kd", "9c"]),
    ("paired_TT5",          ["Th", "Td", "5c"]),
    ("paired_774",          ["7h", "7d", "4c"]),
    # Coordinated / straight-draw heavy
    ("coord_JT9",           ["Jh", "Td", "9c"]),
    ("coord_987",           ["9h", "8d", "7c"]),  # duplicado intencional — alta frequência
    ("coord_QJT",           ["Qh", "Jd", "Tc"]),
]

# Turn runouts neutros (adicionados ao board de flop para gerar turn)
_TURN_CARDS = ["2s", "7s", "Kc", "Ac"]


def _generate_spots(streets: list[str]) -> list[dict]:
    """
    Retorna lista de spots a pré-computar.
    Cada spot é o payload exato para a fila (spot_json).
    """
    spots = []

    for street in streets:
        if street == "flop":
            boards_to_use = [(label, board) for label, board in _FLOP_BOARDS]
        elif street in ("turn", "river"):
            # Turn/river: pega subset dos flops e adiciona runout
            subset_flops = [b for b in _FLOP_BOARDS if "rainbow" in b[0] or "paired" in b[0]]
            boards_to_use = []
            for flop_label, flop_board in subset_flops:
                for turn_card in _TURN_CARDS[:2]:  # 2 runouts por flop = volume controlado
                    if turn_card not in flop_board:
                        boards_to_use.append((
                            f"{flop_label}_{turn_card.lower()}",
                            flop_board + [turn_card],
                        ))
        else:
            continue

        for (ip_pos, oop_pos, matchup_label, pot_fn), stack_bb in product(_MATCHUPS, _STACKS):
            for board_label, board in boards_to_use:
                pot_bb  = round(pot_fn(stack_bb), 1)
                params  = _solver_params(stack_bb)
                spot_hash = compute_spot_hash(street, ip_pos, board, [], stack_bb, 0.0)

                spots.append({
                    "spot_hash":   spot_hash,
                    "label":       f"{matchup_label}_{board_label}_{stack_bb}bb_{street}",
                    "street":      street,
                    "board":       board,
                    "position":    ip_pos,
                    "hero_hand":   [],
                    "hero_stack_bb":             float(stack_bb),
                    "facing_size_bb":            0.0,
                    "oop_range":                 _RANGES.get(oop_pos, _RANGE_WIDE),
                    "ip_range":                  _RANGES.get(ip_pos,  _RANGE_WIDE),
                    "pot_bb":                    pot_bb,
                    "effective_stack_bb":        float(params["effective_stack_bb"]),
                    "max_iterations":            params["max_iterations"],
                    "target_exploitability_pct": params["target_exploitability_pct"],
                    "_meta": {
                        "position":      ip_pos,
                        "vs_position":   oop_pos,
                        "matchup":       matchup_label,
                        "board_texture": board_label,
                        "hero_stack_bb": float(stack_bb),
                        "facing_size_bb": 0.0,
                        "street":        street,
                        "board":         board,
                        "hero_hand":     [],
                    },
                })

    return spots


# ── Prioridade por street + stack ──────────────────────────────────────────────

def _priority(street: str, stack_bb: float) -> int:
    base = {"flop": 6, "turn": 5, "river": 4}.get(street, 5)
    # Stacks curtos (<= 25bb) têm prioridade maior — mais frequentes em MTT
    return base + (1 if stack_bb <= 25 else 0)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pré-computa spots GTO comuns em MTT")
    parser.add_argument("--dry-run",  action="store_true",  help="Lista spots sem enfileirar")
    parser.add_argument("--streets",  nargs="+", default=["flop", "turn"],
                        choices=["flop", "turn", "river"])
    parser.add_argument("--limit",    type=int, default=500, help="Máximo de spots a enfileirar")
    args = parser.parse_args()

    solver_mode = "remote (Google Cloud)" if os.environ.get("GTO_SOLVER_URL") else "local (Rust binario)"
    print(f"Modo solver: {solver_mode}")

    spots = _generate_spots(args.streets)

    # Deduplica por spot_hash
    seen: set[str] = set()
    unique: list[dict] = []
    for s in spots:
        if s["spot_hash"] not in seen:
            seen.add(s["spot_hash"])
            unique.append(s)

    total_unique = len(unique)

    print(f"\nLeakLab — Pré-computacao de Spots GTO")
    print(f"Streets: {args.streets}")
    print(f"Spots unicos gerados: {total_unique}")

    if args.dry_run:
        print(f"\n[DRY RUN] Primeiros 20 spots:")
        for s in unique[:20]:
            print(f"  {s['label'][:60]:<60} hash={s['spot_hash']}")
        print(f"\n... e mais {max(0, total_unique - 20)} spots")
        return

    # Verifica quais já estão resolvidos
    already_done  = sum(1 for s in unique if get_gto_node(s["spot_hash"]))
    to_enqueue    = [s for s in unique if not get_gto_node(s["spot_hash"])]
    to_enqueue    = to_enqueue[:args.limit]

    print(f"Ja resolvidos no banco:  {already_done}")
    print(f"A enfileirar (limite={args.limit}): {len(to_enqueue)}")

    if not to_enqueue:
        print("Nada a fazer — todos os spots ja estao resolvidos.")
        return

    print("\nEnfileirando...")
    t0       = time.time()
    enqueued = skipped = 0
    for s in to_enqueue:
        payload_fields = {k: v for k, v in s.items() if k not in ("spot_hash", "label")}
        payload_json   = json.dumps(payload_fields, sort_keys=True)
        prio           = _priority(s["street"], s["hero_stack_bb"])
        if enqueue_solver_spot(s["spot_hash"], payload_json, priority=prio):
            enqueued += 1
        else:
            skipped += 1

    elapsed = time.time() - t0
    print(f"Enfileirados: {enqueued}  |  Ja na fila (skipped): {skipped}  |  Tempo: {elapsed:.1f}s")
    print(f"\nPara processar, rode:")
    print(f"  python scripts/run_gto_worker.py --poll 10")


if __name__ == "__main__":
    main()
