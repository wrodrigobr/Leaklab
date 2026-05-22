"""
synthesize_missing_vs3bet.py — Gera entries de vs_3bet e vs_4bet faltantes
no leaklab_gto_ranges.json a partir de normalized.json (Greenline+Pekarstas).

NAO altera o JSON principal. Output em leaklab_gto_ranges_gaps.json para
inspecao manual antes de mesclar.

Uso:
    python scripts/synthesize_missing_vs3bet.py
    python scripts/synthesize_missing_vs3bet.py --verbose
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from collections import Counter, defaultdict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR    = BACKEND_DIR / "docs"
EXT_DIR     = DOCS_DIR / "external_ranges"
NORMALIZED  = EXT_DIR / "normalized.json"
RANGES      = DOCS_DIR / "leaklab_gto_ranges.json"
OUT_FILE    = DOCS_DIR / "leaklab_gto_ranges_gaps.json"


# ── Mapping 6-max -> 8-max ───────────────────────────────────────────────────
# 6-max possui: UTG, MP, CO, BTN, SB, BB
# 8-max possui: UTG, UTG+1, MP, MP1, LJ, HJ, CO, BTN, SB, BB
# Para cada posicao 8-max alvo, qual key 6-max usar como base e modo:
POS_MAPPING_8TO6 = {
    "UTG":   ("UTG", "identity"),
    "UTG+1": ("UTG", "identity"),
    "MP":    ("MP",  "identity"),   # MP_6max ~= MP_8max (middle)
    "MP1":   ("MP",  "identity"),
    "LJ":    ("UTG", "identity"),   # LJ_8max e quase tao tight quanto UTG_6max
    "HJ":    ("MP",  "identity"),   # HJ_8max ~= MP_6max (entre MP e CO)
    "CO":    ("CO",  "identity"),
    "BTN":   ("BTN", "identity"),
    "SB":    ("SB",  "identity"),
    "BB":    ("BB",  "identity"),
}


# Posicoes "opener" (RFI) para vs_3bet: nao faz sentido para BB
VS_3BET_OPENER_POSITIONS = ["UTG", "MP", "LJ", "HJ", "CO", "BTN", "SB"]

# Posicoes "3-bettor" para vs_4bet (alguem que ja deu 3-bet, agora enfrenta 4-bet)
VS_4BET_3BETTOR_POSITIONS = ["UTG", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB"]


# ── Categorias de acao no formato externo ────────────────────────────────────
# Acoes externas: 'fold' / 'call' / 'raise' / 'allin' / ['raise','fold'] etc.
# Categorias internas para nossa estrutura:
#   raise/allin -> 4bet
#   call        -> call
#   fold        -> fold
def _resolve_action(value) -> str:
    """Converte valor externo em categoria interna: '4bet' | 'call' | 'fold' | 'mixed'.
    Para mixed (lista), pega a acao mais agressiva da lista.
    """
    if isinstance(value, list):
        # Lista de acoes mistas — prioriza a mais agressiva (raise/allin > call > fold)
        rank = {"allin": 3, "raise": 2, "call": 1, "fold": 0}
        best = max(value, key=lambda a: rank.get(a, 0))
        return _resolve_action(best)
    if value in ("raise", "allin"):
        return "4bet"
    if value == "call":
        return "call"
    return "fold"


def _hands_to_string(hands: list[str]) -> str:
    """Converte lista de hands em string compactada por familia (ex: AA,KK,QQ -> JJ+)."""
    if not hands:
        return ""
    return ",".join(sorted(hands))


def _aggregate_keys(normalized: dict, keys: list[str]) -> dict[str, str]:
    """Agrega multiplas chaves (de diferentes providers + diferentes villains) em
    um mapa hand -> action_consensus.

    Regra de consenso por hand:
      - se ao menos uma fonte diz '4bet' AND mais de metade concorda -> 4bet
      - se ao menos uma fonte diz 'call' AND mais de metade concorda -> call
      - caso contrario, o vote majoritario
    """
    hand_votes: dict[str, Counter] = defaultdict(Counter)
    for prov in ("greenline", "pekarstas"):
        ranges = normalized.get(prov, {})
        for key in keys:
            chart = ranges.get(key, {})
            for hand, val in chart.items():
                act = _resolve_action(val)
                hand_votes[hand][act] += 1

    consensus: dict[str, str] = {}
    for hand, votes in hand_votes.items():
        consensus[hand] = votes.most_common(1)[0][0]
    return consensus


def _compress_for_stack(consensus: dict[str, str], target_stack: int) -> dict[str, str]:
    """Aplica compressao de stack para downscale 100bb -> stacks menores.
    Regras heuristicas baseadas em principios de solver:

    - 100bb / 75bb: identity (range basicamente igual)
    - 50bb: shrink call range — remove hands mais marginais (A5s-A8s, T9s, etc.)
    - 30bb: shrink call range para premium apenas; 4-bet vira jam (mantemos como '4bet')

    Retorna novo dict (consensus permanece imutavel).
    """
    if target_stack >= 75:
        return dict(consensus)

    # Hands que viram fold em stacks mais curtos (perdem implied odds)
    MARGINAL_AT_50BB = {
        "A2s","A3s","A4s","A5s","A6s","A7s","A8s",
        "76s","87s","98s","T9s","J9s",
        "K9s","Q9s",
    }
    MARGINAL_AT_30BB = MARGINAL_AT_50BB | {
        "ATs","AJs","KJs","QJs","JTs",  # remover broadway suited marginais
        "ATo","KQo","AJo","QJo","JTo",
        "88","99","TT",  # pares medios viram fold (sem implied) ou jam (so vs late pos)
    }

    drop = MARGINAL_AT_50BB if target_stack >= 40 else MARGINAL_AT_30BB
    out: dict[str, str] = {}
    for hand, act in consensus.items():
        if hand in drop and act == "call":
            out[hand] = "fold"
        else:
            out[hand] = act
    return out


def _consensus_to_entry(consensus: dict[str, str], source: str, stack: int) -> dict:
    """Converte consensus hand->action no shape do leaklab_gto_ranges.json."""
    by_action: dict[str, list[str]] = defaultdict(list)
    for hand, act in consensus.items():
        by_action[act].append(hand)
    total = len(consensus)
    continua = sum(1 for a in consensus.values() if a in ("4bet", "call"))
    return {
        "pct_continua": round(continua / total, 3) if total else 0.0,
        "hands_4bet":   ",".join(sorted(by_action.get("4bet", []))),
        "hands_call":   ",".join(sorted(by_action.get("call", []))),
        "hands_fold":   "resto",
        "_source":      source,
        "_synth_stack": stack,
    }


# ── Stacks a popular ──────────────────────────────────────────────────────────
TARGET_STACKS_VS_3BET = [100, 75, 50, 30]
TARGET_STACKS_VS_4BET = [100, 75, 50]


def synthesize(normalized: dict, existing: dict, verbose: bool = False) -> dict:
    """Gera somente as entries que NAO existem ainda no JSON principal."""
    ranges = existing.get("ranges", {})
    out_buckets: dict[str, dict] = {}

    # ── vs_3bet ──────────────────────────────────────────────────────────────
    for stack in TARGET_STACKS_VS_3BET:
        bucket_key = f"{stack}bb"
        existing_v3 = ranges.get(bucket_key, {}).get("vs_3bet", {})
        existing_keys = {k for k in existing_v3.keys() if not k.startswith("_")}

        # Para cada posicao opener 8-max
        for pos8 in VS_3BET_OPENER_POSITIONS:
            target_key = f"{pos8}_RFI_vs_3bet"
            if target_key in existing_keys:
                continue  # ja existe — nao tocar

            pos6, mode = POS_MAPPING_8TO6.get(pos8, (None, None))
            if pos6 is None or pos6 == "BB":
                continue

            # Coletar todas as keys externas do tipo POS6-vs-3bet-<villain>
            ext_keys = []
            for prov in ("greenline", "pekarstas"):
                for k in normalized.get(prov, {}).keys():
                    if k.startswith(f"{pos6}-vs-3bet-"):
                        ext_keys.append(k)
            if not ext_keys:
                if verbose:
                    print(f"  [skip] {stack}bb {target_key}: sem dados externos para {pos6}")
                continue

            consensus = _aggregate_keys(normalized, list(set(ext_keys)))
            adjusted  = _compress_for_stack(consensus, stack)
            src = f"greenline+pekarstas {pos6}_6max (agg N={len(set(ext_keys))})"
            if stack < 75:
                src += f" + stack_compression({stack}bb)"

            out_buckets.setdefault(bucket_key, {}).setdefault("vs_3bet", {})[target_key] = \
                _consensus_to_entry(adjusted, src, stack)
            if verbose:
                print(f"  [add] {stack}bb {target_key}: {len(adjusted)} hands, "
                      f"continua={sum(1 for a in adjusted.values() if a in ('4bet','call'))}")

    # ── vs_4bet ──────────────────────────────────────────────────────────────
    # Estrutura: key = '<POS_3bettor>_3bet_vs_4bet' (nova convencao, alinhada com vs_3bet)
    for stack in TARGET_STACKS_VS_4BET:
        bucket_key = f"{stack}bb"
        existing_v4 = ranges.get(bucket_key, {}).get("vs_4bet", {})
        existing_keys = {k for k in existing_v4.keys() if not k.startswith("_")}

        for pos8 in VS_4BET_3BETTOR_POSITIONS:
            target_key = f"{pos8}_3bet_vs_4bet"
            if target_key in existing_keys:
                continue

            pos6, mode = POS_MAPPING_8TO6.get(pos8, (None, None))
            if pos6 is None:
                continue

            ext_keys = []
            for prov in ("greenline", "pekarstas"):
                for k in normalized.get(prov, {}).keys():
                    if k.startswith(f"{pos6}-vs-4bet-"):
                        ext_keys.append(k)
            if not ext_keys:
                if verbose:
                    print(f"  [skip] {stack}bb {target_key}: sem dados externos para {pos6}")
                continue

            consensus = _aggregate_keys(normalized, list(set(ext_keys)))
            adjusted  = _compress_for_stack(consensus, stack)
            src = f"greenline+pekarstas {pos6}_6max (agg N={len(set(ext_keys))})"
            if stack < 75:
                src += f" + stack_compression({stack}bb)"

            out_buckets.setdefault(bucket_key, {}).setdefault("vs_4bet", {})[target_key] = \
                _consensus_to_entry(adjusted, src, stack)
            if verbose:
                print(f"  [add] {stack}bb {target_key}: {len(adjusted)} hands")

    return {
        "_metadata": {
            "generated_by": "synthesize_missing_vs3bet.py",
            "source_providers": ["greenline", "pekarstas"],
            "mapping_6max_to_8max": POS_MAPPING_8TO6,
            "note": (
                "Apenas entries que NAO existem em leaklab_gto_ranges.json. "
                "vs_3bet usa shape compativel com analyze_preflop. "
                "vs_4bet introduz nova convencao '<POS>_3bet_vs_4bet' — exige fix no engine antes de uso."
            ),
        },
        "ranges": out_buckets,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if not NORMALIZED.exists():
        print(f"ERRO: {NORMALIZED} nao encontrado. Rode parse_external_ranges.py primeiro.", file=sys.stderr)
        sys.exit(1)

    normalized = json.loads(NORMALIZED.read_text(encoding="utf-8"))
    existing   = json.loads(RANGES.read_text(encoding="utf-8"))

    gaps = synthesize(normalized, existing, verbose=args.verbose)

    OUT_FILE.write_text(json.dumps(gaps, indent=2, ensure_ascii=False), encoding="utf-8")

    total_v3 = sum(len(b.get("vs_3bet", {})) for b in gaps["ranges"].values())
    total_v4 = sum(len(b.get("vs_4bet", {})) for b in gaps["ranges"].values())
    print(f"\nEntries geradas: vs_3bet={total_v3}, vs_4bet={total_v4}")
    print(f"Escrito: {OUT_FILE}")


if __name__ == "__main__":
    main()
