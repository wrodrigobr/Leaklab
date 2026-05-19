"""
render_reglife_pages.py — Renderiza todas as 216 tabelas do PDF RegLife como PNG.

Para cada pagina do PDF extrai todos os titulos via texto (pode ser 1, 2 ou 3 tabelas),
renderiza cada fatia vertical com clip proporcional e salva com o nome correto:
  rfi_[stack]_[pos].png
  vsrfi_[stack]_[pos]_vs_[pos].png

Uso:
    cd backend
    python scripts/render_reglife_pages.py
    python scripts/render_reglife_pages.py --dpi 300 --dry-run
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PDF_PATH    = BACKEND_DIR.parent / "docs" / "PDF - Ranges RFI e vs RFI.pdf"
OUT_DIR     = BACKEND_DIR.parent / "docs" / "range_pages"

STACKS = {"14": "14bb", "17": "17bb", "20": "20bb", "30": "30bb", "50": "50bb", "100": "100bb"}

# Margem acima do titulo para incluir algum espaco antes da tabela
TITLE_MARGIN_ABOVE = 20

# Correcoes de titulos com erro tipografico no PDF original.
# Chave: (pagina_1based, fname_errado) -> fname_correto
PAGE_TITLE_OVERRIDES: dict[tuple[int, str], str] = {
    # p071: titulo diz "50 bbs - LJ vs MP RFI" mas esta na secao 30bb
    (71, "vsrfi_50bb_LJ_vs_MP"): "vsrfi_30bb_LJ_vs_MP",
}


def title_to_filename(title: str) -> str | None:
    """
    Converte titulo do PDF em nome de arquivo.
    Ex: '14 bbs - RFI UTG'         -> 'rfi_14bb_UTG'
        '14 bbs - MP vs UTG RFI'   -> 'vsrfi_14bb_MP_vs_UTG'
        '17 bbs -  RFI UTG (15,8%)' -> 'rfi_17bb_UTG'
    """
    t = title.strip().replace("  ", " ")

    m_stack = re.search(r'(\d+)\s*bbs?', t, re.IGNORECASE)
    if not m_stack:
        return None
    stack_n = m_stack.group(1)
    stack   = STACKS.get(stack_n)
    if not stack:
        return None

    # vs_RFI: "X vs Y RFI" ou "X vs Y"
    m_vs = re.search(r'([A-Z0-9]+)\s+vs\s+([A-Z0-9]+)', t, re.IGNORECASE)
    if m_vs:
        defender = m_vs.group(1).upper()
        opener   = m_vs.group(2).upper()
        return f"vsrfi_{stack}_{defender}_vs_{opener}"

    # RFI: "RFI POS" ou "RFI_POS" — pode ter percentual depois
    m_rfi = re.search(r'RFI\s+([A-Z0-9]+)', t, re.IGNORECASE)
    if m_rfi:
        pos = m_rfi.group(1).upper()
        return f"rfi_{stack}_{pos}"

    return None


def extract_all_titles(page, page_1based: int = 0) -> list[tuple[float, str]]:
    """
    Extrai TODOS os titulos de uma pagina, ordenados por Y crescente (top -> bottom).
    Retorna lista de (y_origin, filename_sem_ext).
    """
    blocks = page.get_text("dict")["blocks"]
    found: list[tuple[float, str]] = []

    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                text = span.get("text", "").strip()
                # Titulos sao 22-28pt; algumas paginas tem titulos menores (min 13pt).
                # Subtitulos sao 14pt mas nao conteem numeros de stack validos (14/17/20/30/50/100).
                # Threshold > 12 e seguro pois a validacao de stack filtra subtitulos.
                if size > 12 and re.search(r'\d+\s*bbs?', text, re.IGNORECASE):
                    fname = title_to_filename(text)
                    if fname:
                        fname = PAGE_TITLE_OVERRIDES.get((page_1based, fname), fname)
                        y = span.get("origin", (0, 0))[1]
                        found.append((y, fname))

    # Dedup por fname (manter menor y em caso de duplicata)
    seen: dict[str, float] = {}
    for y, fname in found:
        if fname not in seen or y < seen[fname]:
            seen[fname] = y

    result = sorted(seen.items(), key=lambda kv: kv[1])
    return [(y, fname) for fname, y in result]


def render_slice(page, y_start: float, y_end: float, dpi: int, out_path: Path) -> None:
    """Renderiza uma fatia vertical da pagina entre y_start e y_end."""
    import fitz
    rect = page.rect
    clip = fitz.Rect(0, y_start, rect.width, y_end)
    mat  = fitz.Matrix(dpi / 72, dpi / 72)
    pix  = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    pix.save(str(out_path))


def main() -> None:
    import fitz

    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi",     type=int,  default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--page",    type=int,  default=0, help="Renderiza so esta pagina (debug)")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescreve arquivos existentes")
    args = parser.parse_args()

    if not PDF_PATH.exists():
        print(f"PDF nao encontrado: {PDF_PATH}")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(PDF_PATH))
    print(f"PDF: {len(doc)} paginas | DPI: {args.dpi} | Saida: {OUT_DIR}\n")

    saved   = 0
    skipped = 0
    unknown = 0

    pages = [args.page - 1] if args.page > 0 else range(len(doc))

    for i in pages:
        page    = doc[i]
        page_h  = page.rect.height
        titles  = extract_all_titles(page, page_1based=i + 1)

        if not titles:
            unknown += 1
            continue

        for idx, (y_title, fname) in enumerate(titles):
            # Clip: do inicio (ou meio com pagina anterior) ate o inicio da proxima tabela
            y_start = max(0.0, y_title - TITLE_MARGIN_ABOVE)
            if idx == 0 and y_title > 50:
                y_start = 0.0  # inclui topo da pagina para primeira tabela

            if idx + 1 < len(titles):
                next_y  = titles[idx + 1][0]
                y_end   = next_y - TITLE_MARGIN_ABOVE
            else:
                y_end = page_h

            out_path = OUT_DIR / f"{fname}.png"

            if out_path.exists() and not args.overwrite and not args.dry_run:
                skipped += 1
                continue

            slot = f"#{idx+1}/{len(titles)}"
            print(f"  p{i+1:03d} {slot} -> {fname}.png")

            if not args.dry_run:
                render_slice(page, y_start, y_end, args.dpi, out_path)
                saved += 1

    doc.close()
    print(f"\nSalvas: {saved} | Puladas (existentes): {skipped} | Paginas sem titulo: {unknown}")


if __name__ == "__main__":
    main()
