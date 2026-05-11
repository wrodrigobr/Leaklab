"""
benchmark_gto.py — Compara resultados do nosso solver CFR com o GTO Wizard.

Uso:
    python scripts/benchmark_gto.py [caminho_har]

Padrão: backend/docs/app.gtowizard.com.har

Fluxo:
  1. Lê o HAR e extrai todos os spots do GTO Wizard (spot-solution com status 200)
  2. Mapeia cada spot para o formato do nosso solver_cli Rust
  3. Roda o solver localmente (sem escrever no DB)
  4. Exibe tabela comparativa: ação | GTO Wizard freq | Nosso freq | delta

Não faz nenhuma chamada à API do GTO Wizard — só usa as respostas já capturadas no HAR.
Não escreve nada no banco de dados.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional

# ── Caminhos ──────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
HAR_DEFAULT = BACKEND_DIR / "docs" / "app.gtowizard.com.har"
SOLVER_BIN  = BACKEND_DIR / "gto_bot" / "solver_cli" / "target" / "release" / (
    "solver_cli.exe" if os.name == "nt" else "solver_cli"
)

# Ranges padrão (mesmos usados em gto_solver.py)
_RANGES: dict[str, str] = {
    "BTN": "22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,54s,A2o+,K8o+,Q9o+,J9o+,T9o",
    "CO":  "22+,A2s+,K6s+,Q8s+,J8s+,T8s+,98s,87s,76s,A4o+,K9o+,Q9o+,J9o+",
    "HJ":  "44+,A2s+,K9s+,Q9s+,J9s+,T9s,A9o+,KTo+,QTo+,JTo",
    "UTG": "55+,A9s+,KTs+,QTs+,JTs,AJo+,KQo",
    "SB":  "22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,A2o+,K7o+,Q9o+",
    "BB":  "22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K4o+,Q7o+,J8o+,T8o+",
}
_WIDE = "22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K8o+,Q9o+,J9o+"


# ── Parser HAR ─────────────────────────────────────────────────────────────────

def parse_har(har_path: Path) -> list[dict]:
    """
    Retorna lista de spots extraídos do HAR.
    Cada spot:
      {
        url, params,
        gtowizard_actions: [{action_type, betsize, allin, freq}],
        players_info: [...],
      }
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    spots = []
    for entry in har["log"]["entries"]:
        url    = entry["request"]["url"]
        status = entry["response"]["status"]
        if "spot-solution" not in url or status != 200:
            continue

        parsed  = urllib.parse.urlparse(url)
        params  = dict(urllib.parse.parse_qsl(parsed.query))
        content = entry["response"]["content"].get("text", "")
        if not content:
            continue
        body = json.loads(content)

        actions = []
        for sol in body.get("action_solutions", []):
            a = sol["action"]
            actions.append({
                "type":     a["type"],
                "code":     a["code"],
                "betsize":  float(a.get("betsize") or 0),
                "allin":    a.get("allin", False),
                "freq":     sol["total_frequency"],
            })

        # players_info é lista de {player: {...}} ou direto do game.players
        raw_pi = body.get("players_info") or []
        players = [p.get("player", p) for p in raw_pi] if raw_pi else body.get("game", {}).get("players", [])

        spots.append({
            "url":                url,
            "params":             params,
            "gtowizard_actions":  actions,
            "players_info":       players,
        })

    return spots


# ── Extração de contexto do spot ───────────────────────────────────────────────

def extract_spot_context(spot: dict) -> dict:
    """
    A partir dos params do URL e players_info, extrai:
      - board, street, oop_position, ip_position
      - effective_stack_bb, pot_bb
    """
    p = spot["params"]
    board_str = p.get("board", "")
    # Normaliza board: "Ad6h5d" → ["Ad","6h","5d"]
    board = [board_str[i:i+2] for i in range(0, len(board_str), 2)] if board_str else []

    # Street baseada em quais _actions estão preenchidos
    flop_acts  = p.get("flop_actions", "")
    turn_acts  = p.get("turn_actions", "")
    river_acts = p.get("river_actions", "")
    if river_acts:
        street = "river"
    elif turn_acts:
        street = "turn"
    elif flop_acts:
        street = "flop"
    else:
        street = "flop"  # board presente + flop_actions vazio = início do flop

    # Posições OOP / IP a partir dos players
    oop_pos = ip_pos = "BB"
    for pl in spot["players_info"]:
        rpp = pl.get("relative_postflop_position")
        pos = pl.get("position", "?")
        if rpp == "OOP":
            oop_pos = pos
        elif rpp == "IP":
            ip_pos = pos

    # Stacks efetivos
    depth = float(p.get("depth", "20"))
    stacks_raw = p.get("stacks", "")
    stacks = [float(s) for s in stacks_raw.split("-") if s]

    # Current stacks dos jogadores ativos (não foldados)
    active_stacks = []
    for pl in spot["players_info"]:
        # players_info pode ter camada extra {player: {...}}
        pl = pl.get("player", pl)
        if not pl.get("is_folded", True):
            cs = pl.get("current_stack")
            if cs is not None:
                active_stacks.append(float(cs))

    if active_stacks:
        effective_stack_bb = min(active_stacks)
    else:
        effective_stack_bb = depth * 0.65  # estimativa

    # Pot = 2 × (profundidade inicial − stack atual efetivo)
    pot_bb = round(2 * (depth - effective_stack_bb), 2)

    return {
        "board":               board,
        "street":              street,
        "oop_position":        oop_pos,
        "ip_position":         ip_pos,
        "effective_stack_bb":  effective_stack_bb,
        "pot_bb":              pot_bb,
        "depth_bb":            depth,
        "gametype":            p.get("gametype", "?"),
        "preflop_actions":     p.get("preflop_actions", ""),
    }


# ── Execução do nosso solver ───────────────────────────────────────────────────

def run_our_solver(
    ctx: dict,
    iterations: int = 200,
    target_exploit: float = 5.0,
    timeout: int = 180,
) -> Optional[dict]:
    if not SOLVER_BIN.is_file():
        print(f"  [!] solver_cli não encontrado em {SOLVER_BIN}")
        return None

    oop_range = _RANGES.get(ctx["oop_position"], _WIDE)
    ip_range  = _RANGES.get(ctx["ip_position"],  _WIDE)

    payload = {
        "street":                    ctx["street"],
        "board":                     ctx["board"],
        "oop_range":                 oop_range,
        "ip_range":                  ip_range,
        "pot_bb":                    ctx["pot_bb"],
        "effective_stack_bb":        min(ctx["effective_stack_bb"], 30.0),
        "max_iterations":            iterations,
        "target_exploitability_pct": target_exploit,
    }

    _BREAKAWAY = 0x01000000 if os.name == "nt" else 0
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            tmp = f.name
        try:
            with open(tmp, encoding="utf-8") as stdin_f:
                proc = subprocess.run(
                    [str(SOLVER_BIN)],
                    stdin=stdin_f,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=timeout,
                    creationflags=_BREAKAWAY,
                )
        finally:
            os.unlink(tmp)

        if proc.returncode != 0:
            print(f"  [!] solver_cli erro (exit {proc.returncode}): {proc.stderr[:300]}")
            return None

        return json.loads(proc.stdout)

    except subprocess.TimeoutExpired:
        print(f"  [!] solver_cli timeout ({timeout}s)")
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [!] solver_cli falhou: {e}")
        return None


# ── Normalização de nomes de ação ──────────────────────────────────────────────

def _normalize_action(a: str) -> str:
    a = a.upper()
    if a in ("X", "CHECK"):  return "CHECK"
    if a in ("F", "FOLD"):   return "FOLD"
    if a in ("C", "CALL"):   return "CALL"
    if a.startswith("B"):    return "BET"
    if a.startswith("R"):    return "RAISE/BET"
    if a in ("JAM", "ALLIN", "ALL-IN"): return "ALL-IN"
    return a


def _match_our_action(gto_type: str, our_strategy: dict) -> Optional[float]:
    """Tenta mapear uma ação do GTO Wizard para a nossa, retorna frequência."""
    norm = _normalize_action(gto_type)
    # tenta match direto
    for k, v in our_strategy.items():
        kn = _normalize_action(k)
        if kn == norm:
            return v
        # BET e RAISE/BET são equivalentes no nosso solver
        if norm in ("BET", "RAISE/BET") and kn in ("BET", "RAISE/BET", "BET_50PCT", "BET_75PCT"):
            return v
    return None


# ── Exibição ───────────────────────────────────────────────────────────────────

def _bar(freq: float, width: int = 20) -> str:
    filled = round(freq * width)
    return "#" * filled + "." * (width - filled)


def print_comparison(spot: dict, ctx: dict, our_result: Optional[dict]) -> None:
    gw_actions = spot["gtowizard_actions"]

    print()
    print("=" * 70)
    board_str = " ".join(ctx["board"])
    print(f"  SPOT: {ctx['gametype']}  |  Board: {board_str}  |  Street: {ctx['street'].upper()}")
    print(f"  {ctx['oop_position']} (OOP) vs {ctx['ip_position']} (IP)")
    print(f"  Depth: {ctx['depth_bb']:.1f} BB  |  Eff.stack: {ctx['effective_stack_bb']:.2f} BB  |  Pot: {ctx['pot_bb']:.2f} BB")
    print(f"  Preflop: {ctx['preflop_actions']}")
    print("-" * 70)

    gw_primary = max(gw_actions, key=lambda x: x["freq"])

    our_strategy: dict = {}
    our_primary = None
    our_exploit = None
    if our_result:
        sd = our_result.get("strategy_detail") or {}
        st = our_result.get("strategy") or {}
        if isinstance(sd, dict) and sd:
            our_strategy = {k: v["frequency"] for k, v in sd.items()}
        elif isinstance(st, dict):
            our_strategy = st
        our_primary = our_result.get("primary_action")
        our_exploit = our_result.get("exploitability") or our_result.get("exploitability_pct")

    print(f"  {'ACAO':<18} {'GTOWizard':>10}  {'Nosso':>8}  {'delta':>7}  Barra GW")
    print("-" * 70)

    gw_matched: set = set()
    for act in sorted(gw_actions, key=lambda x: -x["freq"]):
        gw_freq  = act["freq"]
        our_freq = _match_our_action(act["type"], our_strategy)
        delta_str = ""
        if our_freq is not None:
            delta = our_freq - gw_freq
            sign  = "+" if delta >= 0 else ""
            delta_str = f"{sign}{delta*100:.1f}%"
            for k in our_strategy:
                if _normalize_action(k) == _normalize_action(act["type"]):
                    gw_matched.add(k)

        our_str = f"{our_freq*100:.1f}%" if our_freq is not None else "  ---"
        label   = act["type"]
        if act["betsize"] > 0:
            label += f" {act['betsize']:.1f}BB"
        if act["allin"]:
            label += " (AI)"

        print(f"  {label:<18} {gw_freq*100:>9.1f}%  {our_str:>8}  {delta_str:>7}  {_bar(gw_freq)}")

    extra = {k: v for k, v in our_strategy.items() if k not in gw_matched and v > 0.005}
    if extra:
        print("  --- acoes extras do nosso solver ---")
        for k, v in sorted(extra.items(), key=lambda x: -x[1]):
            print(f"  {k:<18} {'---':>10}  {v*100:>7.1f}%  {'':>7}  {_bar(v)}")

    print("-" * 70)
    gw_prim_label = gw_primary["type"]
    if gw_primary["betsize"] > 0:
        gw_prim_label += f" {gw_primary['betsize']:.1f}BB"

    if our_primary:
        match = _normalize_action(our_primary) == _normalize_action(gw_prim_label.split()[0])
        verdict = "[MATCH]" if match else "[DIVERGE]"
    else:
        verdict = "[sem resultado]"

    print(f"  GTOWizard primary : {gw_prim_label} ({gw_primary['freq']*100:.1f}%)")
    if our_primary:
        our_prim_freq = our_strategy.get(our_primary, 0)
        print(f"  Nosso primary     : {our_primary} ({our_prim_freq*100:.1f}%)  {verdict}")
    if our_exploit is not None:
        qual = "OK" if our_exploit <= 5.0 else "ALTA"
        print(f"  Nossa exploitab.  : {our_exploit:.2f}%  [{qual}]")
    if not our_result:
        print("  [solver nao rodou -- verifique se solver_cli compilado]")
    print()


def main() -> None:
    har_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HAR_DEFAULT
    if not har_path.is_file():
        print(f"HAR não encontrado: {har_path}")
        sys.exit(1)

    print(f"\nLeakLab GTO Benchmark — HAR: {har_path.name}")
    print(f"Solver: {SOLVER_BIN}")
    print(f"Solver disponível: {SOLVER_BIN.is_file()}")

    spots = parse_har(har_path)
    if not spots:
        print("Nenhum spot-solution encontrado no HAR.")
        sys.exit(0)

    print(f"\n{len(spots)} spot(s) encontrado(s) no HAR.\n")

    for i, spot in enumerate(spots, 1):
        ctx = extract_spot_context(spot)
        print(f"[{i}/{len(spots)}] Rodando solver para {' '.join(ctx['board'])}...", flush=True)
        our = run_our_solver(ctx, iterations=300, target_exploit=5.0, timeout=240)
        print_comparison(spot, ctx, our)

    print("Benchmark concluído.")


if __name__ == "__main__":
    main()
