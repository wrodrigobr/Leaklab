"""
fetch_gw_rfi.py — Coleta ranges RFI do GTO Wizard via Playwright + Edge logado.

Pré-requisitos:
  - Edge instalado e logado em https://app.gtowizard.com
  - Edge FECHADO antes de rodar (Playwright precisa do user-data-dir exclusivo)
  - playwright instalado: pip install playwright && playwright install msedge

Uso:
  python scripts/fetch_gw_rfi.py --test          # 1 spot só (UTG 20bb) para validar
  python scripts/fetch_gw_rfi.py                  # coleta completa (56 spots)
  python scripts/fetch_gw_rfi.py --headless       # sem abrir janela

Output:
  docs/gw_rfi_raw_{timestamp}.json   — JSONs brutos do GW (backup)
  docs/leaklab_gto_ranges_gw_v3.json — JSON estruturado pro engine
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR    = BACKEND_DIR / "docs"

# Default: perfil principal do Edge no Windows
DEFAULT_EDGE_USERDATA = Path.home() / "AppData/Local/Microsoft/Edge/User Data"

STACKS    = [10, 14, 17, 20, 30, 50, 75, 100]
POSITIONS = ['UTG', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB']  # BB não tem RFI

# Ordem canônica das 169 mãos no array `strategy` do GW (assumida — validar com teste)
# Linha por linha do grid 13×13, da esquerda pra direita.
# Diagonal = pares; acima = suited; abaixo = offsuit.
RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

def hand_name(row: int, col: int) -> str:
    if row == col:
        return f"{RANKS[row]}{RANKS[row]}"
    elif row < col:
        return f"{RANKS[row]}{RANKS[col]}s"
    else:
        return f"{RANKS[col]}{RANKS[row]}o"


def preflop_sequence(position: str) -> str:
    """UTG → '', MP → 'F', LJ → 'F-F', etc."""
    idx = POSITIONS.index(position)
    return '-'.join(['F'] * idx)


def build_url(depth: float, preflop_actions: str) -> str:
    stacks_str = '-'.join([f'{depth}'] * 9)
    return (
        f'https://api.gtowizard.com/v4/solutions/spot-solution/'
        f'?gametype=MTTGeneralV2'
        f'&depth={depth}'
        f'&stacks={stacks_str}'
        f'&preflop_actions={preflop_actions}'
        f'&flop_actions=&turn_actions=&river_actions=&board='
    )


def fetch_in_browser(page, url: str) -> dict:
    """Executa fetch() no contexto do browser — auth é assinada automaticamente."""
    js = f"""
        async () => {{
            const r = await fetch({json.dumps(url)}, {{
                headers: {{ "accept": "application/json" }}
            }});
            const status = r.status;
            const text = await r.text();
            return {{ status, body: text }};
        }}
    """
    result = page.evaluate(js)
    if result['status'] != 200:
        raise RuntimeError(f"HTTP {result['status']}: {result['body'][:200]}")
    return json.loads(result['body'])


def parse_rfi_spot(raw: dict) -> dict:
    """Extrai RFI summary do response cru.

    Retorna:
        {
          "total_actions": [{action: "FOLD"/"RAISE"/"ALLIN", betsize, freq, hands_with_freq}],
          "raise_hands": "AA,KK,...",  # mãos com freq > 0 em RAISE sized
          "allin_hands": "...",         # mãos em allin
          "raise_pct": 0.155,
          "allin_pct": 0.020,
          "open_pct":  0.175,           # raise_pct + allin_pct
        }
    """
    sols = raw.get('action_solutions', [])
    if not sols:
        return {}

    result = {
        "actions_summary": [],
        "raise_hands": "",
        "allin_hands": "",
        "raise_pct": 0.0,
        "allin_pct": 0.0,
        "open_pct":  0.0,
    }

    def strategy_to_hands(strategy: list) -> list[str]:
        """Mapeia array de 169 floats para lista de mãos com freq > 0."""
        if not strategy or len(strategy) != 169:
            return []
        hands = []
        i = 0
        for row in range(13):
            for col in range(13):
                if strategy[i] > 0.001:
                    hands.append(hand_name(row, col))
                i += 1
        return hands

    raise_combined: list[str] = []
    for sol in sols:
        act = sol.get('action', {})
        atype = act.get('type', '')
        allin = act.get('allin', False)
        freq  = sol.get('total_frequency', 0)
        hands = strategy_to_hands(sol.get('strategy', []))

        summary = {
            "type":     atype,
            "code":     act.get('code'),
            "betsize":  act.get('betsize'),
            "allin":    allin,
            "frequency": round(freq, 4),
            "hand_count": len(hands),
        }
        result["actions_summary"].append(summary)

        if atype == 'RAISE':
            if allin:
                result["allin_hands"] = ",".join(hands)
                result["allin_pct"] = round(freq, 4)
            else:
                # primeira RAISE sized vira o "raise hands" principal
                if not result["raise_hands"]:
                    result["raise_hands"] = ",".join(hands)
                    result["raise_pct"] = round(freq, 4)
                raise_combined.extend(hands)

    result["open_pct"] = round(result["raise_pct"] + result["allin_pct"], 4)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Apenas 1 spot teste (UTG 20bb)")
    ap.add_argument("--headless", action="store_true", help="Sem janela visível")
    ap.add_argument("--user-data-dir", default=str(DEFAULT_EDGE_USERDATA),
                    help="Caminho do user-data-dir do Edge (será clonado para temp)")
    ap.add_argument("--no-clone", action="store_true",
                    help="Usar user-data-dir direto (Edge precisa estar fechado)")
    ap.add_argument("--profile-dir", default=None,
                    help="Profile dedicado (criado uma vez). Default: ~/.gw_edge_profile")
    ap.add_argument("--login", action="store_true",
                    help="Abre janela para login manual no profile dedicado. Use ANTES de coletar.")
    ap.add_argument("--cdp-url", default=None,
                    help="Conecta em Edge JÁ rodando via CDP (ex: http://localhost:9222). "
                         "Bypassa detecção de automação. Você precisa abrir Edge com "
                         "--remote-debugging-port=9222 antes.")
    ap.add_argument("--throttle-ms", type=int, default=300,
                    help="Pausa entre requests (default 300ms)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: playwright não instalado. Rode: pip install playwright && playwright install msedge")
        sys.exit(1)

    src_userdata = Path(args.user_data_dir)

    # Profile dedicado: nunca conflita com Edge principal. Login manual 1 vez.
    profile_dir = Path(args.profile_dir) if args.profile_dir else (Path.home() / ".gw_edge_profile")

    if args.login:
        profile_dir.mkdir(parents=True, exist_ok=True)
        print(f"Abrindo Edge com profile dedicado em {profile_dir}")
        print("\n>>> 1. FAÇA LOGIN no app.gtowizard.com nesta janela")
        print(">>> 2. Confirme que carrega ranges (preflop → MTT)")
        print(">>> 3. FECHE a janela quando estiver logado\n")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel='msedge', headless=False,
                )
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto('https://app.gtowizard.com/')
                # Espera o user fechar a janela
                page.wait_for_event('close', timeout=0)
                ctx.close()
            print("\n✓ Profile salvo. Agora rode sem --login para coletar.")
        except Exception as e:
            print(f"ERRO no login: {e}")
        return

    # Modo coleta — usa profile dedicado se existir, senão clone do Default
    if profile_dir.exists() and (profile_dir / "Default").exists():
        effective_userdata = str(profile_dir)
        print(f"Usando profile dedicado: {profile_dir}")
    elif args.no_clone:
        if not src_userdata.exists():
            print(f"ERRO: user-data-dir não encontrado: {src_userdata}")
            sys.exit(1)
        effective_userdata = str(src_userdata)
    else:
        if not src_userdata.exists():
            print(f"ERRO: user-data-dir não encontrado: {src_userdata}")
            sys.exit(1)
        import shutil, tempfile
        tmp_userdata = Path(tempfile.mkdtemp(prefix="gw_edge_clone_"))
        src_default  = src_userdata / "Default"
        if not src_default.exists():
            print(f"ERRO: profile Default não encontrado em {src_userdata}")
            sys.exit(1)
        print(f"Clonando profile Default para {tmp_userdata} (pode levar 10-30s)...")
        # Copia recursiva ignorando subpastas pesadas/desnecessárias
        IGNORE = shutil.ignore_patterns(
            'Cache', 'Code Cache', 'GPUCache', 'Service Worker',
            'Storage', 'blob_storage', 'GrShaderCache', 'ShaderCache',
            'Crashpad', '*.log', 'AutofillStrikeDatabase',
        )
        try:
            shutil.copytree(src_default, tmp_userdata / "Default", ignore=IGNORE,
                            dirs_exist_ok=True)
        except (PermissionError, OSError) as e:
            print(f"AVISO: alguns arquivos não copiaram ({e}) — auth pode estar incompleta")
        # Local State é necessário em alguns casos
        ls = src_userdata / "Local State"
        if ls.exists():
            try:
                shutil.copy2(ls, tmp_userdata / "Local State")
            except Exception:
                pass
        effective_userdata = str(tmp_userdata)
        print(f"Clone OK ({sum(f.stat().st_size for f in tmp_userdata.rglob('*') if f.is_file()) // 1024 // 1024} MB)")

    specs = []
    if args.test:
        specs = [(20, 'UTG')]
    else:
        for stack in STACKS:
            for pos in POSITIONS:
                specs.append((stack, pos))

    print(f"Coletando {len(specs)} spots (RFI). Throttle {args.throttle_ms}ms.")
    print(f"User-data-dir: {args.user_data_dir}")
    print("⚠ FECHE O EDGE antes de rodar (Playwright precisa lock exclusivo).\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_results: dict = {}
    parsed_results: dict = {"_metadata": {
        "source": "gtowizard_api_v4_spot-solution",
        "gametype": "MTTGeneralV2",
        "fetched_at": datetime.now().isoformat(),
        "spots_count": len(specs),
    }, "ranges": {}}

    with sync_playwright() as p:
        # Modo CDP: conecta em Edge já rodando (preserva sessão real, bypass detection)
        if args.cdp_url:
            try:
                print(f"Conectando via CDP em {args.cdp_url} ...")
                browser = p.chromium.connect_over_cdp(args.cdp_url, timeout=10000)
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            except Exception as e:
                print(f"ERRO ao conectar CDP: {e}")
                print("Confira que o Edge foi aberto com --remote-debugging-port=9222")
                sys.exit(1)
            # Reusa página aberta no GW, ou abre nova
            page = next((p for p in ctx.pages if 'gtowizard' in p.url), None)
            if not page:
                page = ctx.new_page()
                page.goto('https://app.gtowizard.com/', wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
            else:
                print(f"Reusando página GW já aberta: {page.url}")
        else:
            try:
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=effective_userdata,
                    channel='msedge',
                    headless=args.headless,
                    args=['--disable-blink-features=AutomationControlled'],
                )
            except Exception as e:
                print(f"ERRO ao abrir Edge: {e}")
                print("Se o erro for sobre lock, feche todas as janelas do Edge e tente de novo.")
                sys.exit(1)

            page = ctx.new_page()
            print("Carregando app.gtowizard.com ...")
            page.goto('https://app.gtowizard.com/', wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)  # deixa o JS inicializar (gera gwclientid se não houver)

        for i, (stack, pos) in enumerate(specs, 1):
            seq = preflop_sequence(pos)
            url = build_url(stack, seq)
            try:
                raw = fetch_in_browser(page, url)
            except Exception as e:
                print(f"  [{i}/{len(specs)}] {stack}bb {pos}: FALHOU — {e}")
                continue

            key_stack = f"{stack}bb"
            raw_results.setdefault(key_stack, {}).setdefault("RFI", {})[pos] = raw

            summary = parse_rfi_spot(raw)
            parsed_results["ranges"].setdefault(key_stack, {}).setdefault("RFI", {})[pos] = summary

            open_pct = summary.get("open_pct", 0)
            actions = ", ".join(f"{a['type']}{'(AI)' if a['allin'] else ''}={a['frequency']:.1%}"
                                for a in summary.get("actions_summary", []))
            print(f"  [{i:3d}/{len(specs)}] {stack:3d}bb {pos:3s}: open={open_pct:.1%} | {actions}")

            time.sleep(args.throttle_ms / 1000)

        ctx.close()

    # Salvar outputs
    raw_path    = DOCS_DIR / f"gw_rfi_raw_{timestamp}.json"
    parsed_path = DOCS_DIR / "leaklab_gto_ranges_gw_v3.json"

    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
    with open(parsed_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Raw saved: {raw_path}")
    print(f"✓ Parsed saved: {parsed_path}")
    print(f"\nValidação rápida — sanity check do JSON parsed:")
    for stack_k, stack_data in parsed_results["ranges"].items():
        for pos, summary in stack_data.get("RFI", {}).items():
            n_actions = len(summary.get("actions_summary", []))
            print(f"  {stack_k} {pos}: {n_actions} ações, open_pct={summary.get('open_pct'):.1%}")


if __name__ == "__main__":
    main()
