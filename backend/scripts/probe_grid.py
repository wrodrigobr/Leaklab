"""probe_grid.py — Detecta bounds do grid nas imagens RegLife."""
from __future__ import annotations
from pathlib import Path
from PIL import Image
import numpy as np

DOCS = Path(__file__).resolve().parent.parent.parent / "docs" / "range_pages"


def is_grid_color(r, g, b):
    if r > 160 and g < 130 and b < 130 and r > g + 80:
        return True
    if b > 100 and r < 120 and b > r + 40:
        return True
    return False


def detect_grid_bounds(img_path: Path, verbose: bool = False) -> tuple[int,int,int,int]:
    """
    Detecta bounds da grade 13×13.
    Retorna (gx0, gx1, gy0, gy1).
    """
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    # 1) Encontra gy bounds varrendo colunas do lado esquerdo (< 20% da imagem)
    x_probes = [int(w * f) for f in [0.10, 0.15, 0.20]]
    grid_rows = set()
    for x in x_probes:
        for y in range(0, h, 3):
            r, g, b = arr[y, x]
            if is_grid_color(r, g, b):
                grid_rows.add(y)

    if not grid_rows:
        gy0, gy1 = 0, h
    else:
        gy0 = max(0, min(grid_rows) - 5)
        gy1 = min(h, max(grid_rows) + 10)

    # 2) Encontra gx1 (borda direita da grade) usando densidade de colunas verticais
    # Uma coluna pertence à grade se tem >= 8 pixels de grid-color na faixa gy0..gy1
    # O painel de stats tem colunas com densidade baixa/esparsa
    gx0 = w
    gx1_best = 0
    last_dense_x = 0
    for x in range(0, int(w * 0.75), 3):
        count = 0
        for y in range(gy0, gy1, 5):
            r, g, b = arr[y, x]
            if is_grid_color(r, g, b):
                count += 1
        if count >= 6:
            gx1_best = x
            if x < gx0:
                gx0 = x

    # gx0 = leftmost x with grid color; gx1 = rightmost DENSE column (to the left of stats panel)
    # Extra: do a refined scan near gx1_best to confirm it's the last grid column
    # Find the LAST column before a gap (stats panel starts with a blank column)
    last_dense = 0
    for x in range(0, int(w * 0.72), 2):
        count = 0
        for y in range(gy0, gy1, 8):
            r, g, b = arr[y, x]
            if is_grid_color(r, g, b):
                count += 1
        if count >= 4:
            last_dense = x

    gx0 = max(0, gx0 - 5)
    gx1 = last_dense + 5

    if verbose:
        cw = (gx1 - gx0) / 13
        ch = (gy1 - gy0) / 13
        print(f"  {img_path.name}: {w}x{h}px -> grid x={gx0}..{gx1}, y={gy0}..{gy1} "
              f"cell={cw:.0f}x{ch:.0f}px")

    return gx0, gx1, gy0, gy1


if __name__ == "__main__":
    for img in sorted(DOCS.glob("rfi_14bb_*.png")):
        detect_grid_bounds(img, verbose=True)
    print()
    for img in sorted(DOCS.glob("rfi_20bb_*.png")):
        detect_grid_bounds(img, verbose=True)
