"""
extract_reglife_ranges.py — Extrai ranges RFI do PDF RegLife via análise de pixels.

Lê os 42 PNG em docs/range_pages/rfi_{stack}_{pos}.png e produz
backend/docs/leaklab_gto_ranges_reglife.json com hands por posição/stack.

Uso:
    cd backend
    python scripts/extract_reglife_ranges.py
    python scripts/extract_reglife_ranges.py --probe rfi_20bb_BTN   # debug de uma imagem
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from collections import Counter

import numpy as np
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
PAGES_DIR   = BACKEND_DIR.parent / "docs" / "range_pages"
OUT_PATH    = BACKEND_DIR / "docs" / "leaklab_gto_ranges_reglife.json"

RANKS    = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
STACKS   = [14, 17, 20, 30, 50, 100]
POSITIONS = ['UTG', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB']

# ── Grid bounds (2384×1684 px at 4x DPI)
# x bounds confirmados via probe: grade 13×13 vai de x≈283 a x≈1340
# y bounds variam por imagem (top-half vs bottom-half pages) — detectados automaticamente
GRID_X0_FIXED = 283
GRID_X1_FIXED = 1340

# ── Color classification thresholds
def _classify_rgb(r: int, g: int, b: int) -> str | None:
    """Classify pixel as raise/fold/shove/call or None (text/border/unknown)."""
    # Ignore dark pixels (text, borders)
    if r < 50 and g < 50 and b < 50:
        return None
    # Ignore light pixels (white background, labels)
    if r > 200 and g > 200 and b > 200:
        return None
    # Ignore mixed gray/neutral pixels
    if abs(int(r) - int(g)) < 30 and abs(int(g) - int(b)) < 30 and r < 200:
        return None

    # Red = raise (open 2bb)
    if r > 160 and g < 130 and b < 130 and r > g + 80:
        # Distinguish shove (darker red) from raise (bright red)
        if r > 200:
            return "raise"
        else:
            return "shove"

    # Blue/teal = fold
    if b > 100 and r < 120 and b > r + 40 and b > g - 20:
        return "fold"

    # Green = call/limp
    if g > 120 and r < 130 and b < 120 and g > r + 20:
        return "call"

    return None


def _detect_y_bounds(arr: np.ndarray, x_frac: float = 0.15) -> tuple[int, int]:
    """Detecta y0,y1 da grade varrendo uma coluna à esquerda (15% da largura)."""
    h, w = arr.shape[:2]
    x = int(w * x_frac)
    x = max(0, min(x, w - 1))
    grid_ys = []
    for y in range(0, h, 3):
        r, g, b = int(arr[y, x, 0]), int(arr[y, x, 1]), int(arr[y, x, 2])
        c = _classify_rgb(r, g, b)
        if c in ("raise", "fold", "shove", "call"):
            grid_ys.append(y)
    if not grid_ys:
        return 0, h
    return max(0, min(grid_ys) - 5), min(h, max(grid_ys) + 10)


def extract_grid(img_path: Path, probe: bool = False) -> dict[str, str]:
    """
    Extrai classificação de cada célula da grade 13×13.
    Retorna dict: hand_name -> action ('raise','fold','shove','call','mixed')
    """
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    # x bounds fixos (confirmados via probe para todas as imagens 2384px)
    x0 = GRID_X0_FIXED
    x1 = GRID_X1_FIXED
    # y bounds detectados automaticamente (variam conforme top/bottom half page)
    y0, y1 = _detect_y_bounds(arr)

    cw = (x1 - x0) / 13   # largura de cada célula
    ch = (y1 - y0) / 13   # altura de cada célula

    result: dict[str, str] = {}

    for row in range(13):
        for col in range(13):
            # Coordenadas do centro da célula
            cx = x0 + cw * col + cw / 2
            cy = y0 + ch * row + ch / 2

            # Amostrar 5×5 pontos dentro da célula (evitando bordas: 25% a 75% da célula)
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
                action = "unknown"
            else:
                action = counts.most_common(1)[0][0]

            # Nome da mão
            if row == col:
                hand = f"{RANKS[row]}{RANKS[row]}"
            elif row < col:
                hand = f"{RANKS[row]}{RANKS[col]}s"
            else:
                hand = f"{RANKS[col]}{RANKS[row]}o"

            result[hand] = action

            if probe:
                sym = {'raise': 'R', 'fold': 'F', 'shove': 'S', 'call': 'C',
                       'unknown': '?', 'mixed': 'M'}.get(action, '?')
                print(f"  [{row:2d},{col:2d}] {hand:<5}: {action:<8} "
                      f"(center {int(cx)},{int(cy)}) counts={dict(counts)}")

    return result


def hands_for_action(grid: dict[str, str], action: str) -> list[str]:
    return [h for h, a in grid.items() if a == action]


def grid_to_hand_str(raise_hands: list[str]) -> str:
    """Converte lista de mãos para string compacta tipo '44+,A4s+,...'."""
    if not raise_hands:
        return ""

    pairs = sorted([h for h in raise_hands if len(h) == 2],
                   key=lambda h: RANKS.index(h[0]))
    suited = sorted([h for h in raise_hands if h.endswith('s')],
                    key=lambda h: (RANKS.index(h[0]), RANKS.index(h[1])))
    offsuit = sorted([h for h in raise_hands if h.endswith('o')],
                     key=lambda h: (RANKS.index(h[0]), RANKS.index(h[1])))

    parts: list[str] = []

    # Compress pairs: AA,KK,QQ,JJ,TT → TT+
    def _compress_pairs(ps: list[str]) -> list[str]:
        if not ps:
            return []
        # Find consecutive groups
        idx = [RANKS.index(p[0]) for p in ps]
        groups: list[list[int]] = []
        cur = [idx[0]]
        for i in idx[1:]:
            if i == cur[-1] + 1:
                cur.append(i)
            else:
                groups.append(cur)
                cur = [i]
        groups.append(cur)
        result = []
        for grp in groups:
            if len(grp) == 1:
                result.append(f"{RANKS[grp[0]]}{RANKS[grp[0]]}")
            else:
                lo = RANKS[grp[-1]]
                result.append(f"{lo}{lo}+")
        return result

    parts.extend(_compress_pairs(pairs))

    # Compress suited: AKs,AQs,AJs,ATs → ATs+
    def _compress_suited(hs: list[str]) -> list[str]:
        from itertools import groupby
        result = []
        by_top: dict[str, list[str]] = {}
        for h in hs:
            by_top.setdefault(h[0], []).append(h)
        for top, grp in sorted(by_top.items(), key=lambda x: RANKS.index(x[0])):
            kickers = sorted([h[1] for h in grp], key=lambda k: RANKS.index(k))
            # Find consecutive kicker runs
            idx = [RANKS.index(k) for k in kickers]
            groups: list[list[int]] = []
            cur = [idx[0]]
            for i in idx[1:]:
                if i == cur[-1] + 1:
                    cur.append(i)
                else:
                    groups.append(cur)
                    cur = [i]
            groups.append(cur)
            for grp2 in groups:
                if len(grp2) == 1:
                    result.append(f"{top}{RANKS[grp2[0]]}s")
                else:
                    lo = RANKS[grp2[-1]]
                    if grp2[-1] == RANKS.index(top) + 1:
                        # consecutive down to just below top → use "top-1s" not "+"
                        result.append(f"{top}{lo}s+")
                    else:
                        result.append(f"{top}{lo}s+")
        return result

    parts.extend(_compress_suited(suited))

    # Compress offsuit similarly
    def _compress_offsuit(hs: list[str]) -> list[str]:
        result = []
        by_top: dict[str, list[str]] = {}
        for h in hs:
            by_top.setdefault(h[0], []).append(h)
        for top, grp in sorted(by_top.items(), key=lambda x: RANKS.index(x[0])):
            kickers = sorted([h[1] for h in grp], key=lambda k: RANKS.index(k))
            idx = [RANKS.index(k) for k in kickers]
            groups: list[list[int]] = []
            cur = [idx[0]]
            for i in idx[1:]:
                if i == cur[-1] + 1:
                    cur.append(i)
                else:
                    groups.append(cur)
                    cur = [i]
            groups.append(cur)
            for grp2 in groups:
                if len(grp2) == 1:
                    result.append(f"{top}{RANKS[grp2[0]]}o")
                else:
                    lo = RANKS[grp2[-1]]
                    result.append(f"{top}{lo}o+")
        return result

    parts.extend(_compress_offsuit(offsuit))

    return ",".join(parts)


def process_all() -> dict:
    """Processa todas as 42 imagens e retorna estrutura do JSON."""
    ranges: dict = {}

    for stack in STACKS:
        stack_key = f"{stack}bb"
        ranges[stack_key] = {"RFI": {}}
        print(f"\n=== {stack_key} ===")

        for pos in POSITIONS:
            fname = DOCS_fname(stack, pos)
            img_path = PAGES_DIR / fname
            if not img_path.exists():
                print(f"  {pos}: ARQUIVO NAO ENCONTRADO: {fname}")
                continue

            grid = extract_grid(img_path)
            raise_hands = hands_for_action(grid, "raise")
            shove_hands = hands_for_action(grid, "shove")
            limp_hands  = hands_for_action(grid, "call")   # verde = limp
            all_open    = raise_hands + shove_hands
            total_cells = 169
            pct      = len(all_open) / total_cells
            pct_limp = len(limp_hands) / total_cells

            hand_str      = grid_to_hand_str(all_open)
            limp_hand_str = grid_to_hand_str(limp_hands) if limp_hands else ""

            # Ações para raise/shove range
            acoes = []
            if shove_hands:
                acoes.append("ALLIN")
            if raise_hands:
                acoes.append("RFI")

            entry: dict = {
                "pct":    round(pct, 3),
                "hands":  hand_str,
                "acoes":  acoes if acoes else ["FOLD"],
            }

            # SB tem limp range separada
            if pos == "SB" and limp_hands:
                entry["limp_pct"]   = round(pct_limp, 3)
                entry["limp_hands"] = limp_hand_str
                entry["acoes_limp"] = ["CALL"]

            entry["_debug"] = {
                "raise_count": len(raise_hands),
                "shove_count": len(shove_hands),
                "limp_count":  len(limp_hands),
                "fold_count":  len(hands_for_action(grid, "fold")),
                "unknown":     len(hands_for_action(grid, "unknown")),
            }

            ranges[stack_key]["RFI"][pos] = entry

            limp_note = f" | limp {pct_limp:.1%} ({len(limp_hands)} maos)" if limp_hands else ""
            print(f"  {pos:<5}: raise {pct:.1%} ({len(all_open)} maos){limp_note} -> {hand_str[:50]}...")

    ranges["BB"] = {"pct": 0.0, "hands": "N/A - BB nao tem RFI", "acoes": []}
    return ranges


def DOCS_fname(stack: int, pos: str) -> str:
    return f"rfi_{stack}bb_{pos}.png"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", help="Debug de uma imagem específica (ex: rfi_20bb_BTN)")
    parser.add_argument("--out",   default=str(OUT_PATH))
    args = parser.parse_args()

    if args.probe:
        fname = args.probe if args.probe.endswith(".png") else f"{args.probe}.png"
        img_path = PAGES_DIR / fname
        if not img_path.exists():
            print(f"Arquivo não encontrado: {img_path}")
            sys.exit(1)
        print(f"Probing {img_path.name} ...")
        grid = extract_grid(img_path, probe=True)
        raise_h = hands_for_action(grid, "raise")
        shove_h = hands_for_action(grid, "shove")
        fold_h  = hands_for_action(grid, "fold")
        unk_h   = hands_for_action(grid, "unknown")
        print(f"\nRaise ({len(raise_h)}): {', '.join(raise_h[:30])}")
        print(f"Shove ({len(shove_h)}): {', '.join(shove_h[:30])}")
        print(f"Fold  ({len(fold_h)}): {len(fold_h)} mãos")
        print(f"Unknown ({len(unk_h)}): {', '.join(unk_h[:20])}")
        all_open = raise_h + shove_h
        print(f"\nHand string: {grid_to_hand_str(all_open)}")
        return

    data = process_all()

    out = Path(args.out)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "_metadata": {
                "fonte": "RegLife - PDF Ranges RFI e vs RFI",
                "metodo": "Pixel analysis das imagens PNG do PDF",
                "num_players": 8,
                "formato": "MTT 8-max com ante",
                "stacks_cobertos": STACKS,
                "posicoes": POSITIONS,
            },
            "ranges": data,
        }, f, ensure_ascii=False, indent=2)

    print(f"\nSalvo em: {out}")


if __name__ == "__main__":
    main()
