"""
Compara os spots do DB com o GTO Wizard via API direta.

Uso:
    1. Abra o GTO Wizard no browser
    2. F12 → Network → filtre "api.gtowizard"
    3. Clique em qualquer request → copie:
       - Authorization: Bearer eyJ...  (apenas o token, sem "Bearer ")
       - Google-Anal-Id: 7z6v...       (valor completo)
    4. Execute:
       python compare_spots.py --token "eyJ..." --anal-id "7z6v..."
    5. Aguarde (0.5s por spot)
    6. Resultados salvos em comparison_results_raw.json
    7. python analyze_results.py --input comparison_results_raw.json
"""
from __future__ import annotations
import os, sys, json, time, argparse, base64

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    import requests
except ImportError:
    print("ERROR: pip install requests")
    sys.exit(1)

SCRIPTS_DIR = os.path.dirname(__file__)
BASE_URL = "https://api.gtowizard.com"

# Re-usa a lógica de construção de spots do generate_console_script
from generate_console_script import build_spot_url_params, GAMETYPE


def _token_exp(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get("exp", 0))
    except Exception:
        return None


def check_token(token: str):
    exp = _token_exp(token)
    if exp is None:
        print("WARN: não foi possível decodificar o token.")
        return
    remaining = exp - int(time.time())
    if remaining <= 0:
        print(f"ERROR: token EXPIRADO há {-remaining}s. Copie um token novo do Network tab.")
        sys.exit(1)
    if remaining < 120:
        print(f"WARN: token expira em {remaining}s. Execute rapidamente.")
    else:
        print(f"Token válido por {remaining}s ({remaining//60}min {remaining%60}s).")


def parse_strategy(data: dict) -> tuple[dict, str | None]:
    actions: dict[str, float] = {}
    top_action = None
    top_freq = -1.0
    for item in data.get("action_solutions", []):
        atype = (item.get("action", {}).get("type") or "").lower()
        freq = float(item.get("total_frequency") or 0)
        name = {
            "check": "check", "call": "call", "fold": "fold",
            "bet": "bet", "raise": "bet", "all_in": "allin", "allin": "allin",
        }.get(atype, atype)
        actions[name] = actions.get(name, 0.0) + freq
        if freq > top_freq:
            top_freq = freq
            top_action = name
    return actions, top_action


def run_comparison(spots: list[dict], headers: dict, delay: float) -> list[dict]:
    session = requests.Session()
    session.headers.update(headers)
    results = []

    for i, spot in enumerate(spots):
        p = build_spot_url_params(spot)
        if not p:
            continue

        meta = p["meta"]
        print(f"[{i+1}/{len(spots)}] {meta['position']} | {p['board']} | {p['depth']}bb | "
              f"preflop: {p['preflop_actions']}", end="  ", flush=True)

        result: dict = {
            **meta,
            "board": p["board"],
            "stack": p["depth"],
            "preflop_actions": p["preflop_actions"],
            "flop_actions": p["flop_actions"],
            "gto_found": False,
            "gto_strategy": {},
            "gto_top_action": None,
            "error": None,
        }

        params = {
            "gametype": p["gametype"],
            "depth": p["depth"],
            "stacks": p["stacks"],
            "preflop_actions": p["preflop_actions"],
            "flop_actions": p["flop_actions"],
            "turn_actions": "",
            "river_actions": "",
            "board": p["board"],
        }

        try:
            r = session.get(f"{BASE_URL}/v4/solutions/spot-solution/",
                            params=params, timeout=15)
            if r.status_code == 401:
                print("EXPIRED 401 - token expirado. Reinicie com novo token.")
                result["error"] = "token_expired_401"
                results.append(result)
                break
            elif r.status_code == 403:
                print("403 - plano nao inclui este spot")
                result["error"] = "forbidden_403"
            elif r.status_code == 404:
                print("404 - spot nao encontrado")
                result["error"] = "not_found_404"
            elif not r.ok:
                print(f"ERR {r.status_code}")
                result["error"] = f"http_{r.status_code}"
            else:
                data = r.json()
                actions, top_action = parse_strategy(data)
                result["gto_found"] = True
                result["gto_strategy"] = actions
                result["gto_top_action"] = top_action

                our_action = (meta.get("our_best_action") or "").lower()
                gto_key = {"raise": "bet", "all-in": "allin", "jam": "allin"}.get(our_action, our_action)
                freq = actions.get(gto_key, 0.0)
                result["our_action_gto_freq"] = freq
                result["verdict"] = (
                    "agreement" if freq >= 0.40 else
                    "mixed"     if freq >= 0.15 else
                    "divergence"
                )

                strat = " | ".join(
                    f"{k} {v*100:.0f}%"
                    for k, v in sorted(actions.items(), key=lambda x: -x[1])[:3]
                )
                verdict_str = result["verdict"].upper().ljust(12)
                print(f"OK {verdict_str} our={our_action}({freq*100:.0f}%)  GTO: {strat}")
        except Exception as e:
            print(f"ERROR: {e}")
            result["error"] = str(e)

        results.append(result)
        if i < len(spots) - 1:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token",   required=True, help="Bearer token (sem 'Bearer ')")
    parser.add_argument("--anal-id", required=True, dest="anal_id",
                        help="Google-Anal-Id header completo")
    parser.add_argument("--spots",   default=os.path.join(SCRIPTS_DIR, "unique_spots.jsonl"))
    parser.add_argument("--limit",   type=int, default=30)
    parser.add_argument("--street",  default="flop")
    parser.add_argument("--delay",   type=float, default=0.5,
                        help="Delay entre requests em segundos (default 0.5)")
    parser.add_argument("--output",  default=os.path.join(SCRIPTS_DIR, "comparison_results_raw.json"))
    args = parser.parse_args()

    token = args.token.strip().removeprefix("Bearer ").strip()
    check_token(token)

    headers = {
        "Authorization":  f"Bearer {token}",
        "Accept":          "application/json, text/plain, */*",
        "GWCLIENTID":      "790ab864-ed0c-4545-9e5a-97efe89672cd",
        "Google-Anal-Id":  args.anal_id.strip(),
        "Origin":          "https://app.gtowizard.com",
        "Referer":         "https://app.gtowizard.com/",
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
    }

    if not os.path.exists(args.spots):
        print(f"ERROR: {args.spots} not found. Run spot_extractor.py first.")
        sys.exit(1)

    spots = []
    with open(args.spots, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if args.street and s.get("street") != args.street:
                continue
            spots.append(s)
            if args.limit and len(spots) >= args.limit:
                break

    valid = [s for s in spots if build_spot_url_params(s) is not None]
    print(f"\nSpots: {len(valid)} válidos de {len(spots)} carregados")
    print(f"Tempo estimado: ~{len(valid) * args.delay:.0f}s\n")

    results = run_comparison(valid, headers, args.delay)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    found = [r for r in results if r.get("gto_found")]
    verdicts: dict[str, int] = {}
    for r in results:
        k = r.get("verdict") or r.get("error") or "skip"
        verdicts[k] = verdicts.get(k, 0) + 1

    print(f"\n{'='*60}")
    print(f"RESULTADO: {len(found)}/{len(results)} spots encontrados")
    for v, n in sorted(verdicts.items(), key=lambda x: -x[1]):
        pct = n / len(results) * 100
        print(f"  {v:<20} {n:>3}  ({pct:.0f}%)")
    print(f"{'='*60}")
    print(f"Salvo em: {args.output}")
    print(f"Próximo passo: python analyze_results.py --input {args.output}")


if __name__ == "__main__":
    main()
