"""Debug: find pages containing the 7 missing vs_RFI tables."""
from __future__ import annotations
import re, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PDF_PATH    = BACKEND_DIR.parent / "docs" / "PDF - Ranges RFI e vs RFI.pdf"

MISSING = {
    "vsrfi_100bb_BB_vs_MP",
    "vsrfi_14bb_BB_vs_CO",
    "vsrfi_14bb_BB_vs_UTG",
    "vsrfi_17bb_BB_vs_LJ",
    "vsrfi_20bb_BB_vs_CO",
    "vsrfi_30bb_LJ_vs_MP",
    "vsrfi_50bb_MP_vs_UTG",
}

STACKS = {"14": "14bb", "17": "17bb", "20": "20bb", "30": "30bb", "50": "50bb", "100": "100bb"}


def title_to_filename(title: str):
    t = title.strip().replace("  ", " ")
    m_stack = re.search(r'(\d+)\s*bbs?', t, re.IGNORECASE)
    if not m_stack:
        return None
    stack = STACKS.get(m_stack.group(1))
    if not stack:
        return None
    m_vs = re.search(r'([A-Z0-9]+)\s+vs\s+([A-Z0-9]+)', t, re.IGNORECASE)
    if m_vs:
        return f"vsrfi_{stack}_{m_vs.group(1).upper()}_vs_{m_vs.group(2).upper()}"
    m_rfi = re.search(r'RFI\s+([A-Z0-9]+)', t, re.IGNORECASE)
    if m_rfi:
        return f"rfi_{stack}_{m_rfi.group(1).upper()}"
    return None


def main():
    import fitz
    doc = fitz.open(str(PDF_PATH))

    # Scan ALL pages for text containing any of the missing patterns
    print("Scanning all pages for missing titles...\n")
    for i in range(len(doc)):
        page   = doc[i]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not re.search(r'\d+\s*bbs?', text, re.IGNORECASE):
                        continue
                    fname = title_to_filename(text)
                    if fname and fname in MISSING:
                        y    = span.get("origin", (0,0))[1]
                        size = span.get("size", 0)
                        print(f"  FOUND p{i+1:03d} y={y:.0f} size={size:.1f}: '{text}' -> {fname}")

    # Also print ALL text > 14pt with bbs on pages near known problem areas
    problem_pages = [13, 14, 17, 24, 27, 28, 29, 71, 90, 112]
    print("\n=== Problem page details ===")
    for p in problem_pages:
        if p > len(doc): continue
        page   = doc[p - 1]
        half_y = page.rect.height / 2
        blocks = page.get_text("dict")["blocks"]
        print(f"\n-- Page {p} (h={page.rect.height:.0f}) --")
        for b in blocks:
            if b.get("type") != 0: continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0)
                    text = span.get("text", "").strip()
                    if size > 10 and text:
                        y = span.get("origin", (0,0))[1]
                        half = "T" if y < half_y else "B"
                        print(f"  [{half}] y={y:.0f} sz={size:.1f}: '{text}'")

    doc.close()


if __name__ == "__main__":
    main()
