"""
fetch_gw_passive.py — Captura passivamente responses do GTO Wizard via CDP.

Conecta no Edge rodando (--remote-debugging-port=9222), instala listener em
todas responses /spot-solution/, salva incrementalmente conforme você navega
no app. Funciona com QUALQUER navegação manual no tree (RFI, vs_RFI, 3bet, etc).

Uso:
    python scripts/fetch_gw_passive.py
    # ... navega no app GW, cada nova posição/stack/action dispara captura
    # Ctrl+C quando terminar

Output:
    docs/gw_capture_{timestamp}.json — todos responses capturados
    docs/gw_capture_summary.csv      — resumo (stack, preflop_actions, action_count)
"""
from __future__ import annotations
import argparse
import csv
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR    = BACKEND_DIR / "docs"


def parse_spot_url(url: str) -> dict:
    """Extrai params de uma URL /spot-solution/."""
    qs = parse_qs(urlparse(url).query)
    return {k: v[0] if v else '' for k, v in qs.items()}


def position_from_actions(preflop_actions: str) -> str:
    """Mapeia preflop_actions vazio→UTG, F→MP, F-F→LJ, etc."""
    POSITIONS = ['UTG', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
    if not preflop_actions:
        return POSITIONS[0]
    parts = preflop_actions.split('-')
    # Se todos folds antes desta posição, é RFI nessa posição
    if all(p == 'F' for p in parts):
        idx = len(parts)
        if idx < len(POSITIONS):
            return POSITIONS[idx]
    # Caso contrário, retorna a sequência como context
    return f"action:{preflop_actions}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp-url", default="http://localhost:9222")
    ap.add_argument("--output-prefix", default="gw_capture",
                    help="Prefixo dos arquivos output em docs/")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: pip install playwright")
        sys.exit(1)

    captured: list[dict] = []
    seen_keys: set = set()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = DOCS_DIR / f"{args.output_prefix}_{timestamp}.json"
    csv_path = DOCS_DIR / f"{args.output_prefix}_{timestamp}.csv"

    def save_all():
        if not captured:
            print("Nada capturado.")
            return
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['stack', 'preflop_actions', 'position_hint', 'action_count', 'gametype'])
            for c in captured:
                p = c['params']
                w.writerow([
                    p.get('depth', ''),
                    p.get('preflop_actions', ''),
                    position_from_actions(p.get('preflop_actions', '')),
                    len(c.get('actions_summary', [])),
                    p.get('gametype', ''),
                ])
        print(f"\n✓ {len(captured)} responses salvos:")
        print(f"  Raw:     {raw_path}")
        print(f"  Summary: {csv_path}")

    def on_sigint(sig, frame):
        print("\n\nCtrl+C recebido, salvando...")
        save_all()
        sys.exit(0)
    signal.signal(signal.SIGINT, on_sigint)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_url, timeout=10000)
        ctx = browser.contexts[0]
        page = next((pg for pg in ctx.pages if 'gtowizard' in pg.url), None)
        if not page:
            print("ERRO: nenhuma aba gtowizard aberta no Edge.")
            sys.exit(1)
        print(f"✓ Conectado em: {page.url}\n")
        print("Modo captura passiva ATIVO. Navegue no app GW:")
        print("  - Cada novo spot (posição/stack/action) será capturado automaticamente")
        print("  - Duplicatas (mesma URL) são ignoradas")
        print("  - Ctrl+C para salvar e sair\n")

        def on_response(r):
            try:
                if '/spot-solution/' not in r.url or r.status != 200:
                    return
                # Dedup por URL completa
                if r.url in seen_keys:
                    return
                seen_keys.add(r.url)

                body = r.json()
                params = parse_spot_url(r.url)
                actions_summary = []
                for sol in body.get('action_solutions', []):
                    act = sol.get('action', {})
                    actions_summary.append({
                        'type':     act.get('type'),
                        'code':     act.get('code'),
                        'betsize':  act.get('betsize'),
                        'allin':    act.get('allin'),
                        'frequency': sol.get('total_frequency'),
                        'next_position': act.get('next_position'),
                    })

                # Strategy completo (169 floats por ação) — preserva pra análise
                strategies_by_action = {}
                for sol in body.get('action_solutions', []):
                    code = sol.get('action', {}).get('code')
                    strat = sol.get('strategy', [])
                    if code and strat:
                        strategies_by_action[code] = strat

                entry = {
                    'url': r.url,
                    'params': params,
                    'actions_summary': actions_summary,
                    'strategies': strategies_by_action,
                }
                captured.append(entry)

                # Print resumo imediato
                stack = params.get('depth', '?')
                pa = params.get('preflop_actions', '') or '(none)'
                pos = position_from_actions(params.get('preflop_actions', ''))
                actions = ', '.join(f"{a['type']}{'(AI)' if a['allin'] else ''}={a['frequency']:.1%}"
                                    for a in actions_summary if a['frequency'] is not None)
                print(f"  [{len(captured):3d}] {stack}bb pos={pos} actions=[{pa}] → {actions}")
            except Exception as e:
                print(f"  ERRO ao processar response: {e}")

        page.on('response', on_response)

        # Loop infinito (até Ctrl+C)
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            pass

    save_all()


if __name__ == "__main__":
    main()
