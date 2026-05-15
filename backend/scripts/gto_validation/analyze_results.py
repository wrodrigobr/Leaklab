"""
Analisa os resultados brutos do console script do GTO Wizard.

Uso:
    python analyze_results.py --input comparison_results_raw.json
"""
from __future__ import annotations
import os, sys, json, argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = os.path.dirname(__file__)


def analyze(results: list[dict]):
    total = len(results)
    found = [r for r in results if r.get("gto_found")]
    not_found = [r for r in results if not r.get("gto_found") and not r.get("error")]
    errors = [r for r in results if r.get("error")]

    print(f"\n{'='*65}")
    print(f"GTO WIZARD — ANÁLISE DE RESULTADOS")
    print(f"{'='*65}")
    print(f"Total de spots:        {total}")
    print(f"Encontrados no GTO:    {len(found)}")
    print(f"Não encontrados (404): {len(not_found)}")
    print(f"Erros:                 {len(errors)}")

    if not found:
        print("\nNenhum spot encontrado. Verifique o plano do GTO Wizard.")
        if not_found:
            print("\nSpots não encontrados (404) — podem exigir upgrade de plano:")
            for r in not_found[:5]:
                print(f"  {r.get('position','')} | {r.get('board','')} | {r.get('stack','')}bb | {r.get('scenario','')}")
        return

    # Verdicts
    verdicts = {}
    for r in found:
        v = r.get("verdict", "unknown")
        verdicts[v] = verdicts.get(v, 0) + 1

    print(f"\nVereditos (de {len(found)} spots com solução GTO):")
    for v, count in sorted(verdicts.items(), key=lambda x: -x[1]):
        pct = count / len(found) * 100
        bar = "#" * int(pct / 4)
        print(f"  {v:<20} {count:>3} ({pct:5.1f}%)  {bar}")

    # Agreement rate
    agreed = verdicts.get("agreement", 0)
    mixed  = verdicts.get("mixed", 0)
    diverg = verdicts.get("divergence", 0)
    print(f"\nAcordo geral: {(agreed+mixed)/len(found)*100:.0f}% (agreement + mixed)")

    # Helper: format full GTO strategy with dominant action marked
    def _gto_dist(gto_strat: dict, our_action: str) -> str:
        """Exibe distribuição completa do GTO. Ação dominante marcada com ^."""
        if not gto_strat:
            return "(sem dados)"
        top_freq = max(gto_strat.values())
        parts = []
        for k, v in sorted(gto_strat.items(), key=lambda x: -x[1]):
            marker = "^" if v == top_freq else " "
            ours   = "<nós" if k == our_action else ""
            parts.append(f"{k}{marker}{v*100:.0f}%{ours}")
        return "  ".join(parts)

    # Detailed divergences
    divergences = [r for r in found if r.get("verdict") == "divergence"]
    if divergences:
        print(f"\n{'-'*65}")
        print(f"DIVERGÊNCIAS ({len(divergences)} spots — nós recomendamos ação que GTO usa < 15%):")
        print(f"  Nota: o GTO Wizard usa estratégias mistas (% = frequência).")
        print(f"  Nosso solver é binário — recomenda apenas uma ação.")
        print(f"{'-'*65}")
        for r in sorted(divergences, key=lambda x: x.get("our_action_gto_freq", 1)):
            pos     = r.get("position", "?")
            board   = r.get("board", "")[:10]
            stack   = r.get("stack", 0)
            our     = r.get("our_best_action", "?")
            label   = r.get("our_label", "")
            gto_strat = r.get("gto_strategy", {})
            dist_str  = _gto_dist(gto_strat, our)
            print(f"  {pos:<6} {board:<10} {stack:>5.0f}bb  nós={our:<6}  GTO: {dist_str}  [{label}]")

    # Mixed spots
    mixed_spots = [r for r in found if r.get("verdict") == "mixed"]
    if mixed_spots:
        print(f"\n{'-'*65}")
        print(f"MIXED ({len(mixed_spots)} spots — GTO usa nossa ação 15-40%, estratégia mista):")
        for r in mixed_spots:
            pos     = r.get("position", "?")
            board   = r.get("board", "")[:10]
            stack   = r.get("stack", 0)
            our     = r.get("our_best_action", "?")
            gto_strat = r.get("gto_strategy", {})
            dist_str  = _gto_dist(gto_strat, our)
            print(f"  {pos:<6} {board:<10} {stack:>5.0f}bb  nós={our:<6}  GTO: {dist_str}")

    # Agreements
    agreements = [r for r in found if r.get("verdict") == "agreement"]
    if agreements:
        print(f"\n{'-'*65}")
        print(f"AGREEMENT ({len(agreements)} spots — GTO usa nossa ação >= 40%): validados")
        for r in agreements[:10]:
            pos     = r.get("position", "?")
            board   = r.get("board", "")[:10]
            stack   = r.get("stack", 0)
            our     = r.get("our_best_action", "?")
            gto_strat = r.get("gto_strategy", {})
            dist_str  = _gto_dist(gto_strat, our)
            print(f"  {pos:<6} {board:<10} {stack:>5.0f}bb  nós={our:<6}  GTO: {dist_str}")

    # Error breakdown
    if errors:
        print(f"\n{'-'*65}")
        print(f"ERROS ({len(errors)} spots — não comparados):")
        err_types: dict[str, int] = {}
        for r in errors:
            e = r.get("error", "?")
            err_types[e] = err_types.get(e, 0) + 1
        for etype, count in sorted(err_types.items(), key=lambda x: -x[1]):
            note = {
                "http_422": "sequência de ações inválida (facing_bet — tamanho não existe na árvore GTO)",
                "forbidden_403": "plano ou combinação posição/stack não disponível",
                "http_401": "sessão expirou (renovar browser)",
            }.get(etype, "")
            print(f"  {etype:<18} {count}×  — {note}")

    print(f"\n{'='*65}")
    print(f"CONCLUSÃO:")
    total_found = len(found)
    pct_ok = (agreed + mixed) / total_found * 100 if total_found else 0
    if pct_ok >= 80:
        print(f"  SOLVER VALIDADO — {pct_ok:.0f}% de concordância com GTO Wizard")
    elif pct_ok >= 60:
        print(f"  SOLVER PARCIALMENTE VALIDADO — {pct_ok:.0f}% concordância, revisar divergências")
    else:
        print(f"  ATENÇÃO — {pct_ok:.0f}% concordância, investigar sistematicamente")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON de resultados do console script")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: {args.input} não encontrado")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        results = json.load(f)

    analyze(results)


if __name__ == "__main__":
    main()
