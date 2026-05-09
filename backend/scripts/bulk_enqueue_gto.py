"""
bulk_enqueue_gto.py — Enfileira spots GTO para todas as decisões postflop carregadas.

Lógica:
  - Agrupa decisões por (street, board_key, position_bucket) → reduz duplicatas
  - Atribui oop_range / ip_range com base na posição do herói
  - Enfileira diretamente no formato que solver_cli aceita
  - Não enfileira spots já resolvidos no gto_nodes
"""
from __future__ import annotations
import json
import sys
import os
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
from leaklab.gto_solver import _solver_binary, MAX_EXPLOITABILITY_PCT

# ── Ranges padrão por posição ─────────────────────────────────────────────────
# Ranges intencionalmente compactas (~10-18%) para caber na RAM do solver.
# Representa "range de abertura padrão MTT" — boa cobertura dos spots reais.
#
# Regra de memória: OOP_combos × IP_combos deve ficar abaixo de ~15.000.
# Com 1 bet size por street isso mantém uso < 3 GB (16-bit comprimido).

# ── Ranges ultra-compactas (~60-100 combos) ───────────────────────────────────
# Regra: OOP_combos × IP_combos < 10.000 para solver concluir em <90s.
# Cobertura: mãos premium e semi-premium — representam ~70% dos confrontos reais.

RANGES: dict[str, str] = {
    # IP opening ranges (~60-80 combos)
    'BTN':   'QQ+,AKs,AQs,AJs,KQs,JTs,T9s,AKo,AQo',      # ~75 combos
    'CO':    'QQ+,AKs,AQs,AJs,KQs,AKo,AQo',                # ~65 combos
    'HJ':    'QQ+,AKs,AQs,KQs,AKo,AQo',                    # ~60 combos
    'UTG+2': 'KK+,AKs,AQs,AKo,QQ,JJ',                      # ~55 combos
    'UTG+1': 'KK+,AKs,AQs,AKo,QQ',                         # ~50 combos
    'UTG':   'KK+,AKs,AQs,AKo,QQ',                         # ~50 combos
    # OOP calling ranges (~70-90 combos)
    'SB':    'QQ+,AKs,AQs,AJs,KQs,JTs,AKo,AQo,AJo',       # ~80 combos
    'BB':    'JJ+,AKs,AQs,AJs,ATs,KQs,JTs,AKo,AQo,AJo',   # ~90 combos
}

# Posições IP vs OOP — em MTT 6-max/9-max:
#   IP  → BTN, CO, HJ, UTG+2, UTG+1, UTG
#   OOP → SB, BB
OOP_POSITIONS = {'SB', 'BB'}
IP_POSITIONS  = {'BTN', 'CO', 'HJ', 'UTG+2', 'UTG+1', 'UTG'}

# Villain padrão para cada cenário
VILLAIN_WHEN_HERO_OOP = RANGES['BTN']  # villain mais comum vs blinds
VILLAIN_WHEN_HERO_IP  = RANGES['BB']   # villain mais comum vs raisers

STREET_BOARD_LEN = {'flop': 3, 'turn': 4, 'river': 5}


def board_key(board_json: str, street: str) -> str:
    """Retorna somente as cartas relevantes para a street (ordena para dedup)."""
    try:
        cards = json.loads(board_json)
    except Exception:
        return board_json
    n = STREET_BOARD_LEN.get(street, 3)
    relevant = sorted(cards[:n])  # ordena para dedup (AhKd2c == 2cAhKd)
    return ','.join(relevant)


def spot_hash_for_solver(street: str, board_json: str, position: str) -> str:
    key = f"{street}|{board_key(board_json, street)}|{position}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def build_solver_spot(street: str, board_json: str, position: str, stack_bb: float, pot_bb: float) -> dict | None:
    try:
        cards = json.loads(board_json)
    except Exception:
        return None

    n = STREET_BOARD_LEN.get(street, 3)
    board = cards[:n]
    if len(board) < 3:
        return None

    hero_range   = RANGES.get(position, RANGES['BB'])
    is_oop       = position in OOP_POSITIONS

    if is_oop:
        oop_range = hero_range
        ip_range  = VILLAIN_WHEN_HERO_OOP
    else:
        ip_range  = hero_range
        oop_range = VILLAIN_WHEN_HERO_IP

    return {
        'street':                   street,
        'board':                    board,
        'oop_range':                oop_range,
        'ip_range':                 ip_range,
        'pot_bb':                   float(pot_bb) if pot_bb else 10.0,
        'effective_stack_bb':       float(stack_bb) if stack_bb else 30.0,
        'max_iterations':           1000,
        'target_exploitability_pct': MAX_EXPLOITABILITY_PCT,
    }


def main() -> None:
    conn = schema.get_conn()

    rows = conn.execute("""
        SELECT street, board, position, stack_bb, pot_size
        FROM decisions
        WHERE street IN ('flop','turn','river')
          AND board IS NOT NULL
          AND position IS NOT NULL
    """).fetchall()

    print(f"Decisões postflop brutas: {len(rows)}")

    # Agrupa por spot único
    seen: dict[str, dict] = {}
    for row in rows:
        d = dict(row)
        pos = d['position']
        if pos not in (OOP_POSITIONS | IP_POSITIONS):
            continue  # posição desconhecida, pula
        sh = spot_hash_for_solver(d['street'], d['board'], pos)
        if sh not in seen:
            seen[sh] = d

    print(f"Spots únicos (street+board+position): {len(seen)}")

    # Verifica quais já estão resolvidos em gto_nodes
    resolved = set()
    try:
        for sh in seen:
            row = conn.execute(
                "SELECT spot_hash FROM gto_nodes WHERE spot_hash=? AND exploitability_pct IS NOT NULL AND exploitability_pct<=?",
                (sh, MAX_EXPLOITABILITY_PCT)
            ).fetchone()
            if row:
                resolved.add(sh)
    except Exception as e:
        print(f"Aviso ao checar gto_nodes: {e}")

    print(f"Já resolvidos em gto_nodes: {len(resolved)}")

    # Verifica quais já estão na fila
    queued_already = set()
    try:
        existing = conn.execute("SELECT spot_hash FROM gto_solver_queue").fetchall()
        queued_already = {dict(r)['spot_hash'] for r in existing}
    except Exception as e:
        print(f"Aviso ao checar fila: {e}")

    print(f"Já na fila: {len(queued_already)}")

    # Enfileira os faltantes
    enqueued = 0
    skipped  = 0
    for sh, d in seen.items():
        if sh in resolved or sh in queued_already:
            skipped += 1
            continue

        spot = build_solver_spot(d['street'], d['board'], d['position'], d['stack_bb'], d['pot_size'])
        if spot is None:
            skipped += 1
            continue

        priority = {'flop': 6, 'turn': 5, 'river': 4}.get(d['street'], 5)
        spot_json = json.dumps(spot, sort_keys=True)

        try:
            conn.execute(
                """INSERT OR IGNORE INTO gto_solver_queue
                   (spot_hash, spot_json, priority, status)
                   VALUES (?, ?, ?, 'pending')""",
                (sh, spot_json, priority)
            )
            enqueued += 1
        except Exception as e:
            print(f"  Erro ao enfileirar {sh}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print(f"\nResultado:")
    print(f"  Enfileirados: {enqueued}")
    print(f"  Já resolvidos/na fila/sem dados: {skipped}")
    print(f"\nAgora rode: POST /admin/gto/run-solver")


if __name__ == '__main__':
    main()
