"""
gto_preflop_seeder.py — Seed da base GTO preflop com ranges públicas GTO.

Ranges baseadas em solvers padrão (PioSOLVER/GTO+) para 6-max NL Hold'em.
Cobre RFI por posição, 3-bet ranges e respostas a 3-bet.

Uso:
    python -m leaklab.gto_preflop_seeder          # insere no banco ativo
    python -m leaklab.gto_preflop_seeder --dry-run # imprime sem inserir
"""
from __future__ import annotations
import sys
from leaklab.gto_utils import expand_range_notation

# ── Formato de entrada das ranges ─────────────────────────────────────────────
# Cada entrada é uma tupla:
#   (position, vs_position, action_seq, stack_bucket, [ (notation, action, frequency, ev_bb) ])
#
# notation: notação padrão poker ("AKs", "TT+", "ATo+", etc.)
# action:   "raise" | "call" | "fold"
# frequency: 0.0–1.0 (1.0 = sempre, 0.5 = mixed 50%)
# ev_bb:    EV em BBs (None = não disponível)

# ── RFI ranges 6-max NL, 40–80bb effective (bucket 35-60bb) ─────────────────
# Fonte: consenso entre GTO Wizard e PioSOLVER 6-max solution trees
# Convenção: mãos não listadas têm frequency=0 (fold)

RFI_UTG = [
    # Value raises sempre
    ("AA",    "raise", 1.0,  4.8),
    ("KK",    "raise", 1.0,  3.9),
    ("QQ",    "raise", 1.0,  2.9),
    ("JJ",    "raise", 1.0,  1.8),
    ("TT",    "raise", 1.0,  1.1),
    ("AKs",   "raise", 1.0,  1.9),
    ("AQs",   "raise", 1.0,  1.3),
    ("AJs",   "raise", 1.0,  0.9),
    ("ATs",   "raise", 1.0,  0.7),
    ("KQs",   "raise", 1.0,  0.8),
    ("AKo",   "raise", 1.0,  1.4),
    ("AQo",   "raise", 1.0,  0.8),
    # Mixed raises
    ("99",    "raise", 0.85, 0.6),
    ("99",    "fold",  0.15, None),
    ("88",    "raise", 0.45, 0.3),
    ("88",    "fold",  0.55, None),
    ("KJs",   "raise", 0.80, 0.5),
    ("KJs",   "fold",  0.20, None),
    ("QJs",   "raise", 0.55, 0.3),
    ("QJs",   "fold",  0.45, None),
    ("JTs",   "raise", 0.40, 0.2),
    ("JTs",   "fold",  0.60, None),
    ("AJo",   "raise", 0.60, 0.4),
    ("AJo",   "fold",  0.40, None),
]

RFI_HJ = [
    ("AA",    "raise", 1.0,  4.6),
    ("KK",    "raise", 1.0,  3.7),
    ("QQ",    "raise", 1.0,  2.7),
    ("JJ",    "raise", 1.0,  1.6),
    ("TT",    "raise", 1.0,  1.0),
    ("99",    "raise", 1.0,  0.6),
    ("AKs",   "raise", 1.0,  1.8),
    ("AQs",   "raise", 1.0,  1.2),
    ("AJs",   "raise", 1.0,  0.8),
    ("ATs",   "raise", 1.0,  0.6),
    ("A9s",   "raise", 0.80, 0.4),
    ("A9s",   "fold",  0.20, None),
    ("KQs",   "raise", 1.0,  0.8),
    ("KJs",   "raise", 1.0,  0.5),
    ("KTs",   "raise", 0.85, 0.4),
    ("KTs",   "fold",  0.15, None),
    ("QJs",   "raise", 1.0,  0.5),
    ("QTs",   "raise", 0.75, 0.3),
    ("QTs",   "fold",  0.25, None),
    ("JTs",   "raise", 0.70, 0.3),
    ("JTs",   "fold",  0.30, None),
    ("AKo",   "raise", 1.0,  1.3),
    ("AQo",   "raise", 1.0,  0.7),
    ("AJo",   "raise", 1.0,  0.4),
    ("ATo",   "raise", 0.65, 0.2),
    ("ATo",   "fold",  0.35, None),
    ("KQo",   "raise", 0.80, 0.3),
    ("KQo",   "fold",  0.20, None),
    ("88",    "raise", 0.75, 0.4),
    ("88",    "fold",  0.25, None),
    ("77",    "raise", 0.40, 0.2),
    ("77",    "fold",  0.60, None),
]

RFI_CO = [
    ("AA",    "raise", 1.0,  4.4),
    ("KK",    "raise", 1.0,  3.5),
    ("QQ",    "raise", 1.0,  2.5),
    ("JJ",    "raise", 1.0,  1.5),
    ("TT",    "raise", 1.0,  0.9),
    ("99",    "raise", 1.0,  0.6),
    ("88",    "raise", 1.0,  0.4),
    ("77",    "raise", 0.85, 0.3),
    ("77",    "fold",  0.15, None),
    ("66",    "raise", 0.55, 0.2),
    ("66",    "fold",  0.45, None),
    ("55",    "raise", 0.30, 0.1),
    ("55",    "fold",  0.70, None),
    ("AKs",   "raise", 1.0,  1.7),
    ("AQs",   "raise", 1.0,  1.1),
    ("AJs",   "raise", 1.0,  0.7),
    ("ATs",   "raise", 1.0,  0.5),
    ("A9s",   "raise", 1.0,  0.4),
    ("A8s",   "raise", 0.90, 0.3),
    ("A8s",   "fold",  0.10, None),
    ("A7s",   "raise", 0.75, 0.2),
    ("A7s",   "fold",  0.25, None),
    ("KQs",   "raise", 1.0,  0.7),
    ("KJs",   "raise", 1.0,  0.5),
    ("KTs",   "raise", 1.0,  0.4),
    ("K9s",   "raise", 0.70, 0.2),
    ("K9s",   "fold",  0.30, None),
    ("QJs",   "raise", 1.0,  0.4),
    ("QTs",   "raise", 1.0,  0.3),
    ("Q9s",   "raise", 0.65, 0.2),
    ("Q9s",   "fold",  0.35, None),
    ("JTs",   "raise", 1.0,  0.3),
    ("J9s",   "raise", 0.75, 0.2),
    ("J9s",   "fold",  0.25, None),
    ("T9s",   "raise", 0.60, 0.2),
    ("T9s",   "fold",  0.40, None),
    ("98s",   "raise", 0.45, 0.1),
    ("98s",   "fold",  0.55, None),
    ("AKo",   "raise", 1.0,  1.2),
    ("AQo",   "raise", 1.0,  0.6),
    ("AJo",   "raise", 1.0,  0.4),
    ("ATo",   "raise", 1.0,  0.2),
    ("A9o",   "raise", 0.55, 0.1),
    ("A9o",   "fold",  0.45, None),
    ("KQo",   "raise", 1.0,  0.3),
    ("KJo",   "raise", 0.85, 0.2),
    ("KJo",   "fold",  0.15, None),
    ("KTo",   "raise", 0.55, 0.1),
    ("KTo",   "fold",  0.45, None),
    ("QJo",   "raise", 0.65, 0.1),
    ("QJo",   "fold",  0.35, None),
    ("JTo",   "raise", 0.45, 0.1),
    ("JTo",   "fold",  0.55, None),
]

RFI_BTN = [
    ("AA",    "raise", 1.0,  4.2),
    ("KK",    "raise", 1.0,  3.3),
    ("QQ",    "raise", 1.0,  2.3),
    ("JJ",    "raise", 1.0,  1.4),
    ("TT",    "raise", 1.0,  0.8),
    ("99",    "raise", 1.0,  0.5),
    ("88",    "raise", 1.0,  0.4),
    ("77",    "raise", 1.0,  0.3),
    ("66",    "raise", 1.0,  0.2),
    ("55",    "raise", 1.0,  0.2),
    ("44",    "raise", 0.85, 0.1),
    ("44",    "fold",  0.15, None),
    ("33",    "raise", 0.65, 0.1),
    ("33",    "fold",  0.35, None),
    ("22",    "raise", 0.45, 0.1),
    ("22",    "fold",  0.55, None),
    ("AKs",   "raise", 1.0,  1.6),
    ("AQs",   "raise", 1.0,  1.0),
    ("AJs",   "raise", 1.0,  0.7),
    ("ATs",   "raise", 1.0,  0.5),
    ("A9s",   "raise", 1.0,  0.4),
    ("A8s",   "raise", 1.0,  0.3),
    ("A7s",   "raise", 1.0,  0.3),
    ("A6s",   "raise", 1.0,  0.3),
    ("A5s",   "raise", 1.0,  0.3),
    ("A4s",   "raise", 1.0,  0.2),
    ("A3s",   "raise", 1.0,  0.2),
    ("A2s",   "raise", 1.0,  0.2),
    ("KQs",   "raise", 1.0,  0.6),
    ("KJs",   "raise", 1.0,  0.5),
    ("KTs",   "raise", 1.0,  0.4),
    ("K9s",   "raise", 1.0,  0.3),
    ("K8s",   "raise", 0.80, 0.2),
    ("K8s",   "fold",  0.20, None),
    ("K7s",   "raise", 0.70, 0.1),
    ("K7s",   "fold",  0.30, None),
    ("K6s",   "raise", 0.55, 0.1),
    ("K6s",   "fold",  0.45, None),
    ("K5s",   "raise", 0.45, 0.1),
    ("K5s",   "fold",  0.55, None),
    ("QJs",   "raise", 1.0,  0.4),
    ("QTs",   "raise", 1.0,  0.3),
    ("Q9s",   "raise", 1.0,  0.2),
    ("Q8s",   "raise", 0.80, 0.2),
    ("Q8s",   "fold",  0.20, None),
    ("Q7s",   "raise", 0.55, 0.1),
    ("Q7s",   "fold",  0.45, None),
    ("JTs",   "raise", 1.0,  0.3),
    ("J9s",   "raise", 1.0,  0.2),
    ("J8s",   "raise", 0.85, 0.2),
    ("J8s",   "fold",  0.15, None),
    ("J7s",   "raise", 0.60, 0.1),
    ("J7s",   "fold",  0.40, None),
    ("T9s",   "raise", 1.0,  0.2),
    ("T8s",   "raise", 1.0,  0.2),
    ("T7s",   "raise", 0.70, 0.1),
    ("T7s",   "fold",  0.30, None),
    ("98s",   "raise", 1.0,  0.2),
    ("97s",   "raise", 0.85, 0.1),
    ("97s",   "fold",  0.15, None),
    ("87s",   "raise", 0.85, 0.1),
    ("87s",   "fold",  0.15, None),
    ("76s",   "raise", 0.80, 0.1),
    ("76s",   "fold",  0.20, None),
    ("65s",   "raise", 0.70, 0.1),
    ("65s",   "fold",  0.30, None),
    ("54s",   "raise", 0.55, 0.1),
    ("54s",   "fold",  0.45, None),
    ("AKo",   "raise", 1.0,  1.1),
    ("AQo",   "raise", 1.0,  0.6),
    ("AJo",   "raise", 1.0,  0.3),
    ("ATo",   "raise", 1.0,  0.2),
    ("A9o",   "raise", 1.0,  0.1),
    ("A8o",   "raise", 0.85, 0.1),
    ("A8o",   "fold",  0.15, None),
    ("A7o",   "raise", 0.70, 0.1),
    ("A7o",   "fold",  0.30, None),
    ("A6o",   "raise", 0.55, None),
    ("A6o",   "fold",  0.45, None),
    ("A5o",   "raise", 0.45, None),
    ("A5o",   "fold",  0.55, None),
    ("KQo",   "raise", 1.0,  0.3),
    ("KJo",   "raise", 1.0,  0.2),
    ("KTo",   "raise", 1.0,  0.1),
    ("K9o",   "raise", 0.80, 0.1),
    ("K9o",   "fold",  0.20, None),
    ("QJo",   "raise", 1.0,  0.1),
    ("QTo",   "raise", 0.85, 0.1),
    ("QTo",   "fold",  0.15, None),
    ("Q9o",   "raise", 0.65, None),
    ("Q9o",   "fold",  0.35, None),
    ("JTo",   "raise", 0.85, 0.1),
    ("JTo",   "fold",  0.15, None),
    ("J9o",   "raise", 0.60, None),
    ("J9o",   "fold",  0.40, None),
    ("T9o",   "raise", 0.55, None),
    ("T9o",   "fold",  0.45, None),
    ("98o",   "raise", 0.40, None),
    ("98o",   "fold",  0.60, None),
]

RFI_SB = [
    ("AA",    "raise", 1.0,  3.9),
    ("KK",    "raise", 1.0,  3.1),
    ("QQ",    "raise", 1.0,  2.1),
    ("JJ",    "raise", 1.0,  1.2),
    ("TT",    "raise", 1.0,  0.7),
    ("99",    "raise", 1.0,  0.4),
    ("88",    "raise", 1.0,  0.3),
    ("77",    "raise", 1.0,  0.2),
    ("66",    "raise", 1.0,  0.2),
    ("55",    "raise", 0.90, 0.1),
    ("55",    "fold",  0.10, None),
    ("44",    "raise", 0.75, 0.1),
    ("44",    "fold",  0.25, None),
    ("33",    "raise", 0.60, None),
    ("33",    "fold",  0.40, None),
    ("22",    "raise", 0.50, None),
    ("22",    "fold",  0.50, None),
    ("AKs",   "raise", 1.0,  1.5),
    ("AQs",   "raise", 1.0,  0.9),
    ("AJs",   "raise", 1.0,  0.6),
    ("ATs",   "raise", 1.0,  0.4),
    ("A9s",   "raise", 1.0,  0.3),
    ("A8s",   "raise", 1.0,  0.3),
    ("A7s",   "raise", 1.0,  0.2),
    ("A6s",   "raise", 1.0,  0.2),
    ("A5s",   "raise", 1.0,  0.2),
    ("A4s",   "raise", 1.0,  0.2),
    ("A3s",   "raise", 0.85, 0.1),
    ("A3s",   "fold",  0.15, None),
    ("A2s",   "raise", 0.75, 0.1),
    ("A2s",   "fold",  0.25, None),
    ("KQs",   "raise", 1.0,  0.6),
    ("KJs",   "raise", 1.0,  0.4),
    ("KTs",   "raise", 1.0,  0.3),
    ("K9s",   "raise", 1.0,  0.2),
    ("K8s",   "raise", 0.90, 0.1),
    ("K8s",   "fold",  0.10, None),
    ("K7s",   "raise", 0.80, 0.1),
    ("K7s",   "fold",  0.20, None),
    ("K6s",   "raise", 0.65, 0.1),
    ("K6s",   "fold",  0.35, None),
    ("K5s",   "raise", 0.55, None),
    ("K5s",   "fold",  0.45, None),
    ("K4s",   "raise", 0.40, None),
    ("K4s",   "fold",  0.60, None),
    ("QJs",   "raise", 1.0,  0.3),
    ("QTs",   "raise", 1.0,  0.2),
    ("Q9s",   "raise", 0.90, 0.2),
    ("Q9s",   "fold",  0.10, None),
    ("Q8s",   "raise", 0.75, 0.1),
    ("Q8s",   "fold",  0.25, None),
    ("Q7s",   "raise", 0.55, 0.1),
    ("Q7s",   "fold",  0.45, None),
    ("JTs",   "raise", 1.0,  0.2),
    ("J9s",   "raise", 1.0,  0.2),
    ("J8s",   "raise", 0.80, 0.1),
    ("J8s",   "fold",  0.20, None),
    ("J7s",   "raise", 0.60, None),
    ("J7s",   "fold",  0.40, None),
    ("T9s",   "raise", 1.0,  0.2),
    ("T8s",   "raise", 0.90, 0.1),
    ("T8s",   "fold",  0.10, None),
    ("T7s",   "raise", 0.70, 0.1),
    ("T7s",   "fold",  0.30, None),
    ("98s",   "raise", 0.85, 0.1),
    ("98s",   "fold",  0.15, None),
    ("97s",   "raise", 0.70, 0.1),
    ("97s",   "fold",  0.30, None),
    ("87s",   "raise", 0.65, 0.1),
    ("87s",   "fold",  0.35, None),
    ("76s",   "raise", 0.60, None),
    ("76s",   "fold",  0.40, None),
    ("65s",   "raise", 0.50, None),
    ("65s",   "fold",  0.50, None),
    ("AKo",   "raise", 1.0,  1.0),
    ("AQo",   "raise", 1.0,  0.5),
    ("AJo",   "raise", 1.0,  0.3),
    ("ATo",   "raise", 1.0,  0.2),
    ("A9o",   "raise", 1.0,  0.1),
    ("A8o",   "raise", 0.90, 0.1),
    ("A8o",   "fold",  0.10, None),
    ("A7o",   "raise", 0.75, None),
    ("A7o",   "fold",  0.25, None),
    ("A6o",   "raise", 0.60, None),
    ("A6o",   "fold",  0.40, None),
    ("A5o",   "raise", 0.50, None),
    ("A5o",   "fold",  0.50, None),
    ("A4o",   "raise", 0.40, None),
    ("A4o",   "fold",  0.60, None),
    ("KQo",   "raise", 1.0,  0.3),
    ("KJo",   "raise", 1.0,  0.2),
    ("KTo",   "raise", 0.90, 0.1),
    ("KTo",   "fold",  0.10, None),
    ("K9o",   "raise", 0.75, 0.1),
    ("K9o",   "fold",  0.25, None),
    ("K8o",   "raise", 0.55, None),
    ("K8o",   "fold",  0.45, None),
    ("QJo",   "raise", 1.0,  0.1),
    ("QTo",   "raise", 0.85, 0.1),
    ("QTo",   "fold",  0.15, None),
    ("Q9o",   "raise", 0.65, None),
    ("Q9o",   "fold",  0.35, None),
    ("JTo",   "raise", 0.80, None),
    ("JTo",   "fold",  0.20, None),
    ("J9o",   "raise", 0.60, None),
    ("J9o",   "fold",  0.40, None),
    ("T9o",   "raise", 0.50, None),
    ("T9o",   "fold",  0.50, None),
    ("98o",   "raise", 0.35, None),
    ("98o",   "fold",  0.65, None),
]

# ── 3-bet ranges (vs RFI) ──────────────────────────────────────────────────────
# vs_position = posição do raiser; position = quem faz o 3-bet

THREEBET_BTN_VS_CO = [
    ("AA",  "raise", 1.0,  3.5),
    ("KK",  "raise", 1.0,  2.8),
    ("QQ",  "raise", 1.0,  1.8),
    ("JJ",  "raise", 0.70, 1.0), ("JJ",  "call", 0.30, 0.6),
    ("TT",  "call",  0.75, 0.5), ("TT",  "raise", 0.25, 0.7),
    ("AKs", "raise", 1.0,  1.8),
    ("AQs", "raise", 0.65, 1.0), ("AQs", "call", 0.35, 0.7),
    ("AJs", "call",  0.80, 0.5), ("AJs", "raise", 0.20, 0.7),
    ("ATs", "call",  0.85, 0.4), ("ATs", "raise", 0.15, 0.5),
    ("A5s", "raise", 0.60, 0.3), ("A5s", "fold",  0.40, None),
    ("A4s", "raise", 0.65, 0.3), ("A4s", "fold",  0.35, None),
    ("KQs", "call",  0.70, 0.4), ("KQs", "raise", 0.30, 0.6),
    ("AKo", "raise", 1.0,  1.3),
    ("AQo", "call",  0.80, 0.4), ("AQo", "raise", 0.20, 0.6),
]

THREEBET_BB_VS_BTN = [
    ("AA",  "raise", 1.0,  3.2),
    ("KK",  "raise", 1.0,  2.6),
    ("QQ",  "raise", 1.0,  1.6),
    ("JJ",  "raise", 0.80, 0.8), ("JJ",  "call", 0.20, 0.5),
    ("TT",  "call",  0.65, 0.4), ("TT",  "raise", 0.35, 0.6),
    ("99",  "call",  0.70, 0.3), ("99",  "raise", 0.15, 0.4), ("99", "fold", 0.15, None),
    ("AKs", "raise", 1.0,  1.7),
    ("AQs", "raise", 0.80, 0.8), ("AQs", "call", 0.20, 0.5),
    ("AJs", "call",  0.60, 0.4), ("AJs", "raise", 0.40, 0.6),
    ("ATs", "call",  0.70, 0.3), ("ATs", "raise", 0.30, 0.4),
    ("A5s", "raise", 0.75, 0.3), ("A5s", "fold",  0.25, None),
    ("A4s", "raise", 0.80, 0.3), ("A4s", "fold",  0.20, None),
    ("A3s", "raise", 0.55, 0.2), ("A3s", "fold",  0.45, None),
    ("KQs", "call",  0.60, 0.3), ("KQs", "raise", 0.40, 0.5),
    ("KJs", "call",  0.75, 0.2), ("KJs", "raise", 0.25, 0.3),
    ("AKo", "raise", 1.0,  1.2),
    ("AQo", "raise", 0.70, 0.5), ("AQo", "call", 0.30, 0.3),
    ("AJo", "call",  0.70, 0.2), ("AJo", "raise", 0.30, 0.3),
]

# ── Tabela principal: (position, vs_position, action_seq, stack_bucket, data) ─

SEEDER_ENTRIES = [
    ("UTG", "",    "rfi",  "35-60bb", RFI_UTG),
    ("HJ",  "",    "rfi",  "35-60bb", RFI_HJ),
    ("CO",  "",    "rfi",  "35-60bb", RFI_CO),
    ("BTN", "",    "rfi",  "35-60bb", RFI_BTN),
    ("SB",  "",    "rfi",  "35-60bb", RFI_SB),
    ("BTN", "CO",  "3bet", "35-60bb", THREEBET_BTN_VS_CO),
    ("BB",  "BTN", "3bet", "35-60bb", THREEBET_BB_VS_BTN),
]


# ── Seed function ──────────────────────────────────────────────────────────────

def build_rows() -> list[dict]:
    """Expande todas as entradas em rows prontas para inserção."""
    rows = []
    for position, vs_position, action_seq, stack_bucket, data in SEEDER_ENTRIES:
        for hand_type, action, frequency, ev_bb in data:
            rows.append({
                "position":    position,
                "vs_position": vs_position,
                "action_seq":  action_seq,
                "hand_type":   hand_type,
                "action":      action,
                "frequency":   frequency,
                "ev_bb":       ev_bb,
                "stack_bucket": stack_bucket,
                "source":      "gto_charts_v1",
            })
    return rows


def seed(dry_run: bool = False) -> int:
    """Insere as ranges pré-computadas no banco. Retorna o número de rows inseridas."""
    rows = build_rows()

    if dry_run:
        for r in rows:
            print(f"{r['position']:4s} {r['vs_position'] or 'RFI':4s} "
                  f"{r['action_seq']:6s} {r['hand_type']:4s} "
                  f"{r['action']:6s} {r['frequency']:.2f}")
        print(f"\nTotal: {len(rows)} rows")
        return len(rows)

    from database.repositories import upsert_preflop_ranges
    inserted = upsert_preflop_ranges(rows)
    print(f"Seed GTO preflop: {inserted} rows inseridas/atualizadas.")
    return inserted


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    seed(dry_run=dry)
