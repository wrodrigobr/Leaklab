"""
parse_external_ranges.py — Converte os TS modules de charts externos
(Greenline + Pekarstas) em JSON normalizado para uso pelo synthesizer.

Output: backend/docs/external_ranges/normalized.json
Estrutura:
  {
    "greenline": { "UTG-vs-3bet-BB": {"AA": "raise", ...}, ... },
    "pekarstas": { ... }
  }
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
EXT_DIR     = BACKEND_DIR / "docs" / "external_ranges"
OUT_FILE    = EXT_DIR / "normalized.json"


def parse_ts_charts(ts_path: Path) -> dict[str, dict[str, str | list[str]]]:
    """
    Parse um arquivo TS no formato:
      'KEY': { 'HAND': 'action', 'HAND': ['action', 'action'], ... },
    Retorna dict[key] -> dict[hand] -> str | list[str]
    """
    text = ts_path.read_text(encoding="utf-8")
    result: dict[str, dict] = {}

    # Captura cada bloco "'KEY': { ... }," incluindo o conteudo entre chaves
    # Usa busca por balanceamento manual (regex nao lida bem com chaves aninhadas)
    pos = 0
    key_re = re.compile(r"^\s*'([A-Z][A-Za-z0-9\-_]+)'\s*:\s*\{", re.MULTILINE)
    for m in key_re.finditer(text):
        key = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start:i - 1]

        # Agora extrair pares 'HAND': 'action' OU 'HAND': ['a', 'b']
        hand_map: dict[str, str | list[str]] = {}
        # caso lista
        for hm in re.finditer(r"'([A-Za-z0-9]+)'\s*:\s*\[\s*([^\]]+?)\s*\]", body):
            hand = hm.group(1)
            actions = [a.strip().strip("'").strip('"') for a in hm.group(2).split(",") if a.strip()]
            hand_map[hand] = actions
        # caso string
        for hm in re.finditer(r"'([A-Za-z0-9]+)'\s*:\s*'([A-Za-z]+)'", body):
            hand = hm.group(1)
            if hand not in hand_map:  # nao sobrescrever listas
                hand_map[hand] = hm.group(2)

        result[key] = hand_map

    return result


def main() -> None:
    sources = {
        "greenline": EXT_DIR / "greenline_ranges.ts",
        "pekarstas": EXT_DIR / "pekarstas_ranges.ts",
    }
    out: dict[str, dict] = {}
    for name, path in sources.items():
        if not path.exists():
            print(f"WARN: {path} nao encontrado", file=sys.stderr)
            continue
        parsed = parse_ts_charts(path)
        print(f"{name}: {len(parsed)} charts | "
              f"vs_3bet: {sum(1 for k in parsed if 'vs-3bet' in k)} | "
              f"vs_4bet: {sum(1 for k in parsed if 'vs-4bet' in k)}")
        out[name] = parsed

    OUT_FILE.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nEscrito: {OUT_FILE} ({OUT_FILE.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
