"""
add_pushfold_ranges.py — Adiciona ranges de push/fold ao JSON para stacks curtos.

Fonte: GTO push/fold sem ICM, MTT full ring (fornecido manualmente).
Cobre: 10bb, 12bb (→ bucket 10bb), 15bb (→ bucket 14bb), 20bb (→ bucket 20bb).

Para cada stack/posição armazena:
  push_fold[pos] = {
    "shove_hands": "AA,KK,...",   # range de shove/push
    "shove_pct":   0.xxx,          # combo_pct
    "_source":     "pushfold_gto"
  }

Em vs_RFI, a reshove range é inferida como ≈ 65% das mãos do shove
(heurística conservadora para resposta a raise vs shove puro).
"""
from __future__ import annotations
import json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
JSON_PATH = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"

# ── Dados push/fold fornecidos (GTO sem ICM, MTT full ring) ───────────────────
# Mapeamento de posição push/fold → chave do JSON
POS_MAP = {"UTG": "UTG", "MP": "UTG1", "CO": "CO", "BTN": "BTN", "SB": "SB"}

PUSH_FOLD: dict[str, dict[str, str]] = {
    "10bb": {
        "UTG": "22+, A2s+, A8o+, KTs+, KJo+, QTs+, JTs",
        "MP":  "22+, A2s+, A5o+, K9s+, KTo+, QTs+, JTs, T9s",
        "CO":  "22+, A2s+, A2o+, K8s+, K9o+, Q9s+, QTo+, J9s+, T9s, 98s",
        "BTN": "22+, A2s+, A2o+, K2s+, K7o+, Q8s+, Q9o+, J8s+, J9o+, T8s+, T9o, 98s, 87s",
        "SB":  "22+, A2s+, A2o+, K2s+, K7o+, Q2s+, Q7o+, J4s+, J8o+, T6s+, T8o+, 97s+, 65s+",
    },
    "12bb": {  # → bucket 10bb (stack_buckets 10bb: max=12)
        "UTG": "33+, A2s+, A9o+, KTs+, KQo, QJs",
        "MP":  "22+, A2s+, A7o+, K9s+, KJo+, QTs+, JTs, T9s",
        "CO":  "22+, A2s+, A5o+, K8s+, KTo+, Q9s+, J9s+, T9s, 98s",
        "BTN": "22+, A2s+, A2o+, K2s+, K6o+, Q7s+, Q9o+, J7s+, J9o+, T8s+, T9o, 98s, 87s",
        "SB":  "22+, A2s+, A2o+, K2s+, K7o+, Q2s+, Q6o+, J4s+, J7o+, T6s+, T8o+, 97s+, 65s+",
    },
    "15bb": {  # → bucket 14bb (stack_buckets 14bb: min=13 max=16)
        "UTG": "44+, A2s+, ATo+, KJs+, KQo, QJs",
        "MP":  "33+, A2s+, A8o+, KTs+, KJo+, QTs+, JTs, T9s",
        "CO":  "22+, A2s+, A5o+, K9s+, KTo+, Q9s+, J9s+, T9s, 98s",
        "BTN": "22+, A2s+, A2o+, K2s+, K5o+, Q6s+, Q8o+, J7s+, J9o+, T8s+, T9o, 98s, 87s",
        "SB":  "22+, A2s+, A2o+, K2s+, K6o+, Q2s+, Q5o+, J3s+, J7o+, T6s+, T8o+, 97s+, 65s+",
    },
    "20bb_pf": {  # → bucket 20bb (push/fold simplificado — 20bb já tem RegLife completo)
        "UTG": "55+, AJs+, AQo+, KQs",
        "MP":  "44+, A2s+, ATo+, KJs+, KQo, QJs",
        "CO":  "33+, A2s+, A8o+, KTs+, KJo+, QTs+, JTs",
        "BTN": "22+, A2s+, A5o+, K9s+, KTo+, Q9s+, J9s+, T9s, 98s",
        "SB":  "22+, A2s+, A2o+, K2s+, K7o+, Q6s+, Q9o+, J7s+, J9o+, T8s+, 98s, 87s",
    },
}

# Stack push/fold → bucket JSON onde inserir
BUCKET_TARGETS = {
    "10bb":    "10bb",
    "12bb":    "10bb",   # mesma faixa (0-12bb)
    "15bb":    "14bb",   # faixa 13-16bb
    "20bb_pf": "20bb",
}


def combo_pct(range_str: str) -> float:
    """Estima combo_pct de uma range string (approx via contagem de grupos)."""
    from leaklab.gto_utils import expand_range_notation
    hands: set[str] = set()
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        for h in expand_range_notation(part):
            h = h.strip()
            if not h:
                continue
            if len(h) == 2:
                hands.add(h + "s"); hands.add(h + "o")
            else:
                hands.add(h)
    # Conta combos aproximados
    combos = 0
    for h in hands:
        if len(h) < 2:
            continue
        r1, r2 = h[0], h[1] if len(h) == 2 else h[1]
        if len(h) == 2:  # par: ex 'AA' → 6 combos
            combos += 6
        elif h.endswith("s"):
            combos += 4
        elif h.endswith("o"):
            combos += 12
    return round(combos / 1326, 4)


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    ranges = data["ranges"]
    inserted = []

    for pf_stack, bucket in BUCKET_TARGETS.items():
        if bucket not in ranges:
            print(f"  [SKIP] bucket {bucket} nao encontrado")
            continue

        pf_data = PUSH_FOLD[pf_stack]
        bucket_pf = ranges[bucket].setdefault("push_fold", {})

        for pf_pos, range_str in pf_data.items():
            json_pos = POS_MAP.get(pf_pos, pf_pos)
            pct = combo_pct(range_str)
            entry = {
                "shove_hands": range_str,
                "shove_pct":   pct,
                "_source":     f"pushfold_gto_{pf_stack}",
            }
            # Guarda por stack dentro da posição para referência cruzada
            if json_pos not in bucket_pf:
                bucket_pf[json_pos] = {}
            bucket_pf[json_pos][pf_stack] = entry
            inserted.append(f"{bucket}/{json_pos}/{pf_stack}")
            print(f"  {bucket:<6} {json_pos:<6} {pf_stack:<8}  pct={pct:.3f}  {range_str[:50]}")

    data["_metadata"]["versao"] = "2.4.0"
    data["_metadata"]["ultima_atualizacao"] = "2026-05-19"
    data["_metadata"]["nota_pushfold"] = (
        "push_fold[pos][stack] = ranges de shove GTO sem ICM para 10/12/15/20bb. "
        "Usados como fallback em analyze_preflop para stacks curtos sem dados RegLife."
    )

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nTotal inserido: {len(inserted)} entradas — JSON v2.4.0")


if __name__ == "__main__":
    main()
