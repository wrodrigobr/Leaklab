"""
Fix mojibake (double-encoded UTF-8) in i18n locale JSON files.
The files were saved by a tool that mis-interpreted UTF-8 bytes as Windows-1252
and re-encoded them, producing garbled text like "decisÃ£o" instead of "decisão".
"""
import json
import glob
import os


def fix_mojibake(text: str) -> str:
    """Reverse double-encoding: chars encoded as Windows-1252 then as UTF-8."""
    result_bytes = b""
    for c in text:
        try:
            result_bytes += c.encode("windows-1252")
        except UnicodeEncodeError:
            result_bytes += c.encode("utf-8")
    return result_bytes.decode("utf-8")


def is_mojibake(text: str) -> bool:
    """Detect double-encoding: Windows-1252 byte re-encoded as UTF-8."""
    for i in range(len(text) - 1):
        c1, c2 = ord(text[i]), ord(text[i + 1])
        # Latin-1 Supplement pairs: Ã/Â followed by continuation-range char
        if c1 in (0x00C2, 0x00C3) and 0x0080 <= c2 <= 0x00BF:
            return True
        # E2-based: â followed by Windows-1252 special chars (€, curly quotes, dashes, arrows…)
        if c1 == 0x00E2 and c2 in (0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021,
                                    0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0x017D, 0x2018,
                                    0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC,
                                    0x2122, 0x0161, 0x203A, 0x0153, 0x017E, 0x0178, 0x0086,
                                    0x00A6, 0x2192):
            return True
    return False


base = os.path.join(os.path.dirname(__file__), "..", "..","frontend", "src", "i18n", "locales")
base = os.path.abspath(base)
files = glob.glob(os.path.join(base, "**", "*.json"), recursive=True)

fixed_count = 0
for path in sorted(files):
    with open(path, "rb") as f:
        raw = f.read()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    if had_bom:
        raw = raw[3:]
    text = raw.decode("utf-8")
    if not is_mojibake(text):
        continue
    fixed = fix_mojibake(text)
    # Validate it's still valid JSON
    try:
        json.loads(fixed)
    except json.JSONDecodeError as e:
        print(f"SKIP (JSON error after fix): {os.path.relpath(path, base)} — {e}")
        continue
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fixed)
    rel = os.path.relpath(path, base)
    print(f"FIXED: {rel}")
    fixed_count += 1

print(f"\nTotal fixed: {fixed_count} files")
