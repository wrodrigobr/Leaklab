"""
extract_vsrfi_ranges.py — Extrai ranges vs_RFI do PDF RegLife via analise de pixels.

Le os 163+ PNG vsrfi_[stack]_[defender]_vs_[opener].png em docs/range_pages/ e
adiciona os dados de vs_RFI ao leaklab_gto_ranges.json existente.

Estrutura adicionada:
    ranges.[stack].vs_RFI.[opener].[defender] = {
        "fold_pct":  0.91,
        "call_pct":  0.00,
        "raise_pct": 0.00,   # 3bet para tamanho especifico
        "allin_pct": 0.085,  # 3bet all-in
        "fold_hands": "...",
        "call_hands": "...",
        "raise_hands": "...",
        "allin_hands": "..."
    }

Uso:
    cd backend
    python scripts/extract_vsrfi_ranges.py
    python scripts/extract_vsrfi_ranges.py --probe vsrfi_20bb_HJ_vs_LJ   # debug
    python scripts/extract_vsrfi_ranges.py --dry-run                      # apenas conta
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from collections import Counter

import numpy as np
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
PAGES_DIR   = BACKEND_DIR.parent / "docs" / "range_pages"
RANGES_FILE = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"

RANKS     = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
STACKS    = [14, 17, 20, 30, 50, 100]
POSITIONS = ['UTG', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

GRID_X0_FIXED = 283
GRID_X1_FIXED = 1340
TOTAL_COMBOS  = 1326
TOTAL_CELLS   = 169


# ── Color classification (same as RFI extractor)
def _classify_rgb(r: int, g: int, b: int) -> str | None:
    if r < 50 and g < 50 and b < 50:
        return None
    if r > 200 and g > 200 and b > 200:
        return None
    if abs(int(r) - int(g)) < 30 and abs(int(g) - int(b)) < 30 and r < 200:
        return None

    # Red = 3bet-raise or all-in
    if r > 160 and g < 130 and b < 130 and r > g + 80:
        if r > 200:
            return "raise"   # 3bet to specific size (brighter red)
        else:
            return "allin"   # 3bet all-in (darker red)

    # Blue/teal = fold
    if b > 100 and r < 120 and b > r + 40 and b > g - 20:
        return "fold"

    # Green = call
    if g > 120 and r < 130 and b < 120 and g > r + 20:
        return "call"

    return None


def _detect_y_bounds(arr: np.ndarray, x_frac: float = 0.15) -> tuple[int, int]:
    h, w = arr.shape[:2]
    x = max(0, min(int(w * x_frac), w - 1))
    grid_ys = []
    for y in range(0, h, 3):
        r, g, b = int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2])
        if _classify_rgb(r, g, b) in ("raise", "fold", "allin", "call"):
            grid_ys.append(y)
    if not grid_ys:
        return 0, h
    return max(0, min(grid_ys) - 5), min(h, max(grid_ys) + 10)


def extract_grid(img_path: Path, probe: bool = False) -> dict[str, str]:
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    x0, x1 = GRID_X0_FIXED, GRID_X1_FIXED
    y0, y1  = _detect_y_bounds(arr)

    cw = (x1 - x0) / 13
    ch = (y1 - y0) / 13

    result: dict[str, str] = {}
    for row in range(13):
        for col in range(13):
            counts: Counter = Counter()
            for dy in np.linspace(0.25, 0.75, 5):
                for dx in np.linspace(0.25, 0.75, 5):
                    px = int(x0 + cw * col + cw * dx)
                    py = int(y0 + ch * row + ch * dy)
                    px = max(0, min(px, w - 1))
                    py = max(0, min(py, h - 1))
                    r, g, b = arr[py, px]
                    kind = _classify_rgb(r, g, b)
                    if kind:
                        counts[kind] += 1

            if not counts:
                action = "fold"  # unknown cells default to fold in vs_RFI context
            else:
                action = counts.most_common(1)[0][0]

            if row == col:
                hand = f"{RANKS[row]}{RANKS[row]}"
            elif row < col:
                hand = f"{RANKS[row]}{RANKS[col]}s"
            else:
                hand = f"{RANKS[col]}{RANKS[row]}o"

            result[hand] = action

            if probe:
                cx = x0 + cw * col + cw / 2
                cy = y0 + ch * row + ch / 2
                sym = {'raise': 'R', 'fold': 'F', 'allin': 'A', 'call': 'C'}.get(action, '?')
                print(f"  [{row:2d},{col:2d}] {hand:<5}: {action:<8} "
                      f"(center {int(cx)},{int(cy)}) counts={dict(counts)}")

    return result


def hands_for_action(grid: dict[str, str], action: str) -> list[str]:
    return [h for h, a in grid.items() if a == action]


def grid_to_hand_str(hands: list[str]) -> str:
    if not hands:
        return ""
    pairs   = sorted([h for h in hands if len(h) == 2],    key=lambda h: RANKS.index(h[0]))
    suited  = sorted([h for h in hands if h.endswith('s')], key=lambda h: (RANKS.index(h[0]), RANKS.index(h[1])))
    offsuit = sorted([h for h in hands if h.endswith('o')], key=lambda h: (RANKS.index(h[0]), RANKS.index(h[1])))
    parts: list[str] = []

    def _compress(hs: list[str], suffix: str = "") -> list[str]:
        if not hs: return []
        by_top: dict[str, list[str]] = {}
        for h in hs:
            top = h[0]
            kicker = "" if len(h) == 2 else h[1]
            by_top.setdefault(top, []).append(kicker or top)
        result = []
        for top, kickers in sorted(by_top.items(), key=lambda x: RANKS.index(x[0])):
            idx = sorted([RANKS.index(k) for k in kickers])
            groups: list[list[int]] = []
            cur = [idx[0]]
            for i in idx[1:]:
                if i == cur[-1] + 1:
                    cur.append(i)
                else:
                    groups.append(cur); cur = [i]
            groups.append(cur)
            for grp in groups:
                lo = RANKS[grp[-1]]
                if suffix == "":  # pairs
                    result.append(f"{lo}{lo}+") if len(grp) > 1 else result.append(f"{top}{top}")
                elif len(grp) == 1:
                    result.append(f"{top}{lo}{suffix}")
                else:
                    result.append(f"{top}{lo}{suffix}+")
        return result

    parts.extend(_compress([h for h in pairs], ""))
    parts.extend(_compress(suited, "s"))
    parts.extend(_compress(offsuit, "o"))
    return ",".join(parts)


def _combo_count(hands: list[str]) -> int:
    pairs   = sum(1 for h in hands if len(h) == 2)
    suited  = sum(1 for h in hands if h.endswith('s'))
    offsuit = sum(1 for h in hands if h.endswith('o'))
    return pairs * 6 + suited * 4 + offsuit * 12


def parse_vsrfi_filename(name: str) -> tuple[str, str, str] | None:
    """vsrfi_20bb_HJ_vs_LJ -> ('20bb', 'HJ', 'LJ') = (stack, defender, opener)"""
    m = re.match(r'vsrfi_(\d+bb)_([A-Z]+)_vs_([A-Z]+)', name)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def process_all(pages_dir: Path) -> dict:
    """Processa todos os arquivos vsrfi_*.png e retorna dict aninhado."""
    result: dict = {}

    files = sorted(pages_dir.glob("vsrfi_*.png"))
    print(f"Encontrados {len(files)} arquivos vsrfi_*.png\n")

    for img_path in files:
        parsed = parse_vsrfi_filename(img_path.stem)
        if not parsed:
            print(f"  IGNORADO (nome invalido): {img_path.name}")
            continue

        stack, defender, opener = parsed

        grid       = extract_grid(img_path)
        fold_h     = hands_for_action(grid, "fold")
        call_h     = hands_for_action(grid, "call")
        raise_h    = hands_for_action(grid, "raise")
        allin_h    = hands_for_action(grid, "allin")

        fold_pct   = round(_combo_count(fold_h)  / TOTAL_COMBOS, 4)
        call_pct   = round(_combo_count(call_h)  / TOTAL_COMBOS, 4)
        raise_pct  = round(_combo_count(raise_h) / TOTAL_COMBOS, 4)
        allin_pct  = round(_combo_count(allin_h) / TOTAL_COMBOS, 4)
        aggr_pct   = round(call_pct + raise_pct + allin_pct, 4)

        entry = {
            "fold_pct":    fold_pct,
            "call_pct":    call_pct,
            "raise_pct":   raise_pct,
            "allin_pct":   allin_pct,
            "aggr_pct":    aggr_pct,   # total nao-fold
            "fold_hands":  grid_to_hand_str(fold_h),
            "call_hands":  grid_to_hand_str(call_h),
            "raise_hands": grid_to_hand_str(raise_h),
            "allin_hands": grid_to_hand_str(allin_h),
        }

        result.setdefault(stack, {}).setdefault(opener, {})[defender] = entry

        print(f"  {stack} {defender:3s} vs {opener:3s}: "
              f"fold={fold_pct:.1%} call={call_pct:.1%} "
              f"raise={raise_pct:.1%} allin={allin_pct:.1%} "
              f"[aggr={aggr_pct:.1%}]")

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe",    help="Debug de uma imagem (ex: vsrfi_20bb_HJ_vs_LJ)")
    parser.add_argument("--dry-run",  action="store_true", help="Apenas exibe, nao salva")
    parser.add_argument("--stack",    help="Filtrar apenas este stack (ex: 20bb)")
    args = parser.parse_args()

    if args.probe:
        fname = args.probe if args.probe.endswith(".png") else f"{args.probe}.png"
        img_path = PAGES_DIR / fname
        if not img_path.exists():
            print(f"Arquivo nao encontrado: {img_path}"); sys.exit(1)
        print(f"Probing {img_path.name} ...")
        grid   = extract_grid(img_path, probe=True)
        fold_h = hands_for_action(grid, "fold")
        call_h = hands_for_action(grid, "call")
        raise_h= hands_for_action(grid, "raise")
        allin_h= hands_for_action(grid, "allin")
        print(f"\nFold  ({len(fold_h)}): {grid_to_hand_str(fold_h)[:60]}")
        print(f"Call  ({len(call_h)}): {grid_to_hand_str(call_h)[:60]}")
        print(f"Raise ({len(raise_h)}): {grid_to_hand_str(raise_h)[:60]}")
        print(f"Allin ({len(allin_h)}): {grid_to_hand_str(allin_h)[:60]}")
        return

    vsrfi_data = process_all(PAGES_DIR)

    if args.dry_run:
        stacks_found = sorted(vsrfi_data.keys())
        total = sum(
            len(defenders)
            for stack_data in vsrfi_data.values()
            for defenders in stack_data.values()
        )
        print(f"\n[dry-run] {total} spots em {stacks_found}. Nao salvando.")
        return

    # Merge into existing ranges JSON
    if not RANGES_FILE.exists():
        print(f"ERRO: {RANGES_FILE} nao encontrado. Rode add_combo_pct.py primeiro.")
        sys.exit(1)

    with open(RANGES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    for stack, openers in vsrfi_data.items():
        bucket = data.get("ranges", {}).get(stack)
        if bucket is None:
            print(f"  AVISO: stack {stack} nao encontrado no JSON existente")
            continue
        bucket["vs_RFI"] = openers

    data["_metadata"]["versao"]              = "2.2.0"
    data["_metadata"]["ultima_atualizacao"]  = "2026-05-19"
    data["_metadata"]["nota_vsrfi"]          = (
        "vs_RFI[opener][defender]: fold/call/raise(3bet-size)/allin(3bet-push). "
        "Todos os pct sao combo_pct (/ 1326)."
    )

    with open(RANGES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total = sum(
        len(defenders)
        for stack_data in vsrfi_data.values()
        for defenders in stack_data.values()
    )
    print(f"\n{total} spots vs_RFI adicionados ao {RANGES_FILE.name} (v2.2.0)")


if __name__ == "__main__":
    main()
