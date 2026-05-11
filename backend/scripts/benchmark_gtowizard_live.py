"""
benchmark_gtowizard_live.py — Busca spots do nosso DB e compara com GTO Wizard ao vivo.

Uso:
    python scripts/benchmark_gtowizard_live.py [opcoes]

Opcoes:
    --user-id ID       Filtra por user_id (default: todos)
    --limit N          Max spots a testar (default: 10)
    --street flop      Filtra por street: flop, turn, river (default: flop)
    --mistakes-only    So testa decisoes com label != standard
    --db PATH          Caminho do banco SQLite (default: backend/data/leaklab.db)
    --har PATH         HAR para extrair refresh token (default: backend/docs/app.gtowizard.com.har)

O script:
  1. Le o refresh token do HAR (ou de GW_REFRESH_TOKEN no ambiente)
  2. Busca decisoes postflop no nosso DB
  3. Reconstroi o contexto preflop para o formato do GTO Wizard
  4. Consulta spot-solution em api.gtowizard.com
  5. Compara nossa best_action com a acao primaria do GTO Wizard
  6. Exibe tabela de benchmark com match/divergencia

Nao escreve nada no banco de dados.
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# ── Caminhos ──────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
HAR_DEFAULT = BACKEND_DIR / "docs" / "app.gtowizard.com.har"
DB_DEFAULT  = BACKEND_DIR / "data" / "leaklab.db"

# Client ID capturado do HAR (identifica a sessao do browser)
GW_CLIENT_ID = os.environ.get("GW_CLIENT_ID", "790ab864-ed0c-4545-9e5a-97efe89672cd")
GW_API_BASE  = "https://api.gtowizard.com"

# Ordem das posicoes em 8-max (indice 0=UTG ... 7=BB)
POSITIONS_8MAX = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POS_IDX = {p: i for i, p in enumerate(POSITIONS_8MAX)}


# ── Auth Manager ──────────────────────────────────────────────────────────────

class GWAuth:
    """Gerencia o token de acesso ao GTO Wizard, auto-refreshing quando necessario."""

    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    @classmethod
    def from_har(cls, har_path: Path) -> "GWAuth":
        with open(har_path, encoding="utf-8") as f:
            har = json.load(f)
        for entry in har["log"]["entries"]:
            if "token/refresh" in entry["request"]["url"] and entry["request"]["method"] == "POST":
                body = entry["request"].get("postData", {}).get("text", "")
                if body:
                    data = json.loads(body)
                    if "refresh" in data:
                        print(f"[auth] Refresh token extraido do HAR.")
                        return cls(data["refresh"])
        raise ValueError("Refresh token nao encontrado no HAR.")

    @classmethod
    def from_access_token(cls, token: str) -> "GWAuth":
        """Usa um access token direto (sem refresh). Expira em ~15min — rerun quando necessario."""
        import base64
        inst = cls(refresh_token="")
        inst._access_token = token
        parts = token.split(".")
        pad   = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            claims = json.loads(base64.b64decode(pad))
            inst._expires_at = float(claims.get("exp", time.time() + 900))
            remaining = int(inst._expires_at - time.time())
            print(f"[auth] Access token direto — expira em {remaining}s.")
            if remaining < 30:
                print("[auth] AVISO: token expirado ou prestes a expirar!")
        except Exception:
            inst._expires_at = time.time() + 900
        return inst

    @classmethod
    def from_env_or_har(cls, har_path: Path) -> "GWAuth":
        # 1. Access token direto (mais simples, capturado do DevTools)
        access = os.environ.get("GW_ACCESS_TOKEN", "")
        if access:
            print("[auth] Usando GW_ACCESS_TOKEN do ambiente.")
            return cls.from_access_token(access)
        # 2. Refresh token
        token = os.environ.get("GW_REFRESH_TOKEN", "")
        if token:
            print("[auth] Usando GW_REFRESH_TOKEN do ambiente.")
            return cls(token)
        # 3. Extrai refresh token do HAR
        return cls.from_har(har_path)

    def access_token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 30:
            return self._access_token
        if not self.refresh_token:
            raise RuntimeError(
                "Token expirado. Capture um novo access token do DevTools do browser e "
                "defina GW_ACCESS_TOKEN=eyJ... antes de rodar o script."
            )
        self._refresh()
        return self._access_token  # type: ignore

    def _refresh(self) -> None:
        url     = f"{GW_API_BASE}/v1/token/refresh/"
        payload = json.dumps({"refresh": self.refresh_token}).encode()
        req     = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "Origin": "https://app.gtowizard.com"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            raise RuntimeError(f"Falha ao renovar token GTO Wizard: {e}") from e

        self._access_token = data["access"]
        # JWT exp claim
        import base64
        parts  = self._access_token.split(".")
        pad    = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.b64decode(pad))
        self._expires_at = float(claims.get("exp", time.time() + 900))
        print(f"[auth] Token renovado, expira em {int(self._expires_at - time.time())}s.")


# ── GTO Wizard API Client ──────────────────────────────────────────────────────

class GWClient:
    def __init__(self, auth: GWAuth):
        self.auth = auth

    def _headers(self) -> dict:
        return {
            "Authorization":  f"Bearer {self.auth.access_token()}",
            "Accept":         "application/json",
            "Origin":         "https://app.gtowizard.com",
            "Referer":        "https://app.gtowizard.com/",
            "gwclientid":     GW_CLIENT_ID,
            "User-Agent":     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def _get(self, path: str, params: dict, retry: bool = True) -> Optional[dict]:
        qs  = urllib.parse.urlencode(params)
        url = f"{GW_API_BASE}{path}?{qs}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 401 and retry:
                self.auth._refresh()
                return self._get(path, params, retry=False)
            body = e.read().decode(errors="replace")[:200]
            print(f"  [!] HTTP {e.code} para {path}: {body}")
            return None
        except Exception as e:
            print(f"  [!] Erro em {path}: {e}")
            return None

    def spot_solution(self, params: dict) -> Optional[dict]:
        return self._get("/v4/solutions/spot-solution/", params)

    def board_usage(self) -> Optional[dict]:
        return self._get("/v4/solutions/board-usage/", {})


# ── Banco de dados ─────────────────────────────────────────────────────────────

def fetch_decisions(
    db_path: Path,
    user_id: Optional[int] = None,
    street: str = "flop",
    mistakes_only: bool = False,
    limit: int = 10,
) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    wheres = [
        "d.street = ?",
        "d.board IS NOT NULL AND d.board != ''",
        "d.stack_bb IS NOT NULL AND d.stack_bb > 3",
        "d.pot_size IS NOT NULL AND d.pot_size > 0.5",
        "d.position IS NOT NULL",
    ]
    args: list = [street]

    if user_id:
        wheres.append("t.user_id = ?")
        args.append(user_id)
    if mistakes_only:
        wheres.append("d.label IN ('clear_mistake','small_mistake','marginal')")

    where_sql = " AND ".join(wheres)
    args.append(limit)

    rows = conn.execute(f"""
        SELECT d.id, d.street, d.position, d.board,
               d.action_taken, d.best_action, d.label, d.score,
               d.stack_bb, d.pot_size, d.facing_bet, d.is_3bet,
               d.num_players, d.hand_id, t.user_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {where_sql}
        ORDER BY d.id DESC
        LIMIT ?
    """, args).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ── Reconstrucao do contexto preflop ──────────────────────────────────────────

def _round_half(x: float) -> float:
    """Arredonda para o 0.5 mais proximo."""
    return round(x * 2) / 2


def build_gw_params(dec: dict) -> Optional[dict]:
    """
    Converte uma decisao do nosso DB para os parametros do GTO Wizard.

    Logica:
    - depth = stack_bb + pot_bb/2  (aprox para pote HU)
    - stacks = [depth] * 8  (todos iguais — simplificacao)
    - preflop_actions: reconstruido a partir de posicao, is_3bet, pot_bb
    - board: apenas as 3 cartas do flop para consulta inicial do flop
    """
    try:
        board = json.loads(dec["board"]) if isinstance(dec["board"], str) else dec["board"]
    except Exception:
        return None

    if not board or len(board) < 3:
        return None

    position  = (dec.get("position") or "BTN").upper()
    pot_bb    = float(dec["pot_size"])
    stack_bb  = float(dec["stack_bb"])
    is_3bet   = bool(dec.get("is_3bet"))
    street    = dec.get("street", "flop").lower()

    # Depth estimado: stack actual + o que hero contribuiu preflop
    depth = round(stack_bb + pot_bb / 2, 3)

    # Tamanhos padrao para reconstrucao
    if is_3bet:
        # 3-bet pot: 3-bet size ≈ pot/2
        threebet_size = _round_half(max(6.0, pot_bb / 2))
        open_size     = _round_half(max(2.0, threebet_size / 3))
    else:
        # SRP: open size ≈ pot/2.2 (inclui dead money dos blinds)
        open_size = _round_half(max(2.0, pot_bb / 2.2))

    # Posicao do hero na tabela
    pos_idx = POS_IDX.get(position, POS_IDX.get("BTN", 5))

    # Constroi a sequencia de acoes preflop
    actions: list[str] = []
    if is_3bet:
        # Abre em alguma posicao, BB (ou outro) 3-bets, hero calls
        if position == "BB":
            # BB 3-bettou e o IP chamou
            # Assume IP = BTN abriu
            for i in range(8):
                if i < 5:    actions.append("F")   # UTG..CO folds
                elif i == 5: actions.append(f"R{open_size}")  # BTN opens
                elif i == 6: actions.append("F")   # SB folds
                else:        actions.append(f"R{threebet_size}")  # BB 3-bets
            actions.append("C")  # BTN calls
        else:
            # Hero abriu e foi 3-bettado (por BB)
            for i in range(8):
                if i < pos_idx:  actions.append("F")
                elif i == pos_idx: actions.append(f"R{open_size}")
                elif i < 7:      actions.append("F")
                else:            actions.append(f"R{threebet_size}")  # BB 3-bets
            actions.append("C")  # hero calls
    else:
        # SRP: hero abriu ou chamou uma abertura
        if position in ("BB", "SB"):
            # BB/SB chamou uma abertura (assume BTN abriu)
            for i in range(8):
                if i < 5:    actions.append("F")
                elif i == 5: actions.append(f"R{open_size}")  # BTN opens
                elif i == 6: actions.append("F")  # SB folds (se hero = BB)
                else:        actions.append("C")  # BB calls
        else:
            # Hero abriu, BB chamou
            for i in range(8):
                if i < pos_idx:    actions.append("F")
                elif i == pos_idx: actions.append(f"R{open_size}")
                elif i < 7:        actions.append("F")
                else:              actions.append("C")  # BB calls

    preflop_str = "-".join(actions)

    # Board: so o flop para consulta inicial
    flop_cards = board[:3]
    board_str  = "".join(flop_cards)

    # Acoes de cada street (vazias para consulta do inicio da street)
    flop_actions  = ""
    turn_actions  = ""
    river_actions = ""

    stacks_str = "-".join([str(depth)] * 8)

    return {
        "gametype":        "MTTGeneral_8m",
        "depth":           depth,
        "stacks":          stacks_str,
        "preflop_actions": preflop_str,
        "flop_actions":    flop_actions,
        "turn_actions":    turn_actions,
        "river_actions":   river_actions,
        "board":           board_str,
        # meta para display
        "_board_list":     board,
        "_position":       position,
        "_is_3bet":        is_3bet,
        "_open_size":      open_size,
    }


# ── Normalizacao de acoes ──────────────────────────────────────────────────────

def _norm(a: str) -> str:
    a = (a or "").lower().strip()
    if a in ("check", "x"):         return "check"
    if a in ("fold", "f"):          return "fold"
    if a in ("call", "c"):          return "call"
    if a in ("bet", "raise", "jam", "allin", "all-in"): return "aggressive"
    if a.startswith("bet_"):        return "aggressive"
    if a.startswith("raise_"):      return "aggressive"
    return a


def gw_primary(action_solutions: list[dict]) -> tuple[str, float]:
    """Retorna (tipo, frequencia) da acao primaria do GTO Wizard."""
    best = max(action_solutions, key=lambda x: x["total_frequency"])
    t = best["action"]["type"].lower()
    if t in ("check", "x"):   t = "check"
    elif t in ("call", "c"):  t = "call"
    elif t in ("fold", "f"):  t = "fold"
    else:                     t = "aggressive"
    return t, best["total_frequency"]


# ── Exibicao ──────────────────────────────────────────────────────────────────

RESET = "\033[0m"
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"

def _color(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"{code}{text}{RESET}"
    return text


def _bar(freq: float, width: int = 18) -> str:
    f = round(freq * width)
    return "#" * f + "." * (width - f)


def print_spot(dec: dict, params: dict, gw_result: Optional[dict]) -> None:
    board   = dec.get("board", "[]")
    b_list  = json.loads(board) if isinstance(board, str) else board
    b_str   = " ".join(b_list[:3])
    pos     = dec["position"]
    street  = dec["street"].upper()
    stack   = dec["stack_bb"]
    pot     = dec["pot_size"]
    acted   = dec["action_taken"]
    best    = dec["best_action"]
    label   = dec["label"]
    is_3bet = bool(dec.get("is_3bet"))
    hand_id = dec.get("hand_id", "?")

    spr     = round(stack / pot, 2) if pot else 0
    pot_type= "3BET" if is_3bet else "SRP"

    print()
    print("=" * 72)
    print(f"  {_color(street, BOLD)}  Board: {_color(b_str, CYAN)}  |  {pos} ({pot_type})")
    print(f"  Pot: {pot:.1f} BB  Stack: {stack:.1f} BB  SPR: {spr}  Hand: {hand_id}")
    print(f"  Preflop seq: {params['preflop_actions']}")
    print("-" * 72)

    our_acted = _norm(acted)
    our_best  = _norm(best)

    print(f"  Nossa analise: jogou={_color(acted, YELLOW)}  recomendacao={_color(best, CYAN)}  "
          f"label={label}")

    if gw_result is None:
        print("  [GTO Wizard: sem resposta]")
        print()
        return

    solutions = gw_result.get("action_solutions", [])
    if not solutions:
        print("  [GTO Wizard: resposta vazia]")
        print()
        return

    gw_prim_type, gw_prim_freq = gw_primary(solutions)

    print()
    print(f"  {'ACAO GW':<16} {'Freq':>7}   Barra")
    print("  " + "-" * 40)
    for sol in sorted(solutions, key=lambda x: -x["total_frequency"]):
        t    = sol["action"]["type"]
        bs   = sol["action"].get("betsize", 0)
        freq = sol["total_frequency"]
        label_gw = t
        if bs and float(bs) > 0:
            label_gw += f" {float(bs):.1f}BB"
        if sol["action"].get("allin"):
            label_gw += " (AI)"
        print(f"  {label_gw:<16} {freq*100:>6.1f}%   {_bar(freq)}")

    print()

    # Comparacao: nossa best_action vs GTO Wizard primary
    our_match = _norm(best) == gw_prim_type
    gw_agrees = _norm(acted) == gw_prim_type

    verdict_best = (
        _color("[MATCH]",   GREEN)  if our_match  else
        _color("[DIVERGE]", RED)
    )
    verdict_play = (
        _color("[GW OK]",   GREEN)  if gw_agrees  else
        _color("[GW ERRO]", YELLOW)
    )

    print(f"  Nossa recomendacao: {_color(best, CYAN):<10}  vs GTO primary: "
          f"{_color(gw_prim_type, CYAN)} ({gw_prim_freq*100:.0f}%)  {verdict_best}")
    print(f"  Acao jogada:        {_color(acted, YELLOW):<10}  {verdict_play}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark LeakLab vs GTO Wizard (live)")
    parser.add_argument("--user-id",      type=int,   default=None)
    parser.add_argument("--limit",        type=int,   default=10)
    parser.add_argument("--street",       default="flop", choices=["flop","turn","river"])
    parser.add_argument("--mistakes-only",action="store_true")
    parser.add_argument("--db",           default=str(DB_DEFAULT))
    parser.add_argument("--har",          default=str(HAR_DEFAULT))
    args = parser.parse_args()

    db_path  = Path(args.db)
    har_path = Path(args.har)

    if not db_path.is_file():
        print(f"DB nao encontrado: {db_path}")
        sys.exit(1)

    # Auth
    auth   = GWAuth.from_env_or_har(har_path)
    client = GWClient(auth)

    # Verifica quota antes de comecar
    usage = client.board_usage()
    if usage:
        print(f"[quota] Gametype: {usage.get('gametype')}  "
              f"Reset: {usage.get('reset_date','?')[:10]}")

    # Busca decisoes
    decisions = fetch_decisions(
        db_path,
        user_id      = args.user_id,
        street       = args.street,
        mistakes_only= args.mistakes_only,
        limit        = args.limit,
    )

    print(f"\n{len(decisions)} decisao(oes) encontrada(s) para benchmark.\n")

    # Estatisticas
    total   = 0
    matches = 0
    gw_ok   = 0

    for dec in decisions:
        params = build_gw_params(dec)
        if not params:
            print(f"  [!] Nao foi possivel construir params para hand {dec.get('hand_id')}")
            continue

        print(f"Consultando GTO Wizard: {' '.join(json.loads(dec['board']) if isinstance(dec['board'],str) else dec['board'])[:8]}... ", end="", flush=True)

        gw_result = client.spot_solution(params)
        print("OK" if gw_result else "FALHOU")

        print_spot(dec, params, gw_result)

        if gw_result and gw_result.get("action_solutions"):
            total += 1
            gw_prim_type, _ = gw_primary(gw_result["action_solutions"])
            if _norm(dec["best_action"]) == gw_prim_type:
                matches += 1
            if _norm(dec["action_taken"]) == gw_prim_type:
                gw_ok += 1

        # Respeita rate limit
        time.sleep(0.8)

    # Resumo
    if total > 0:
        print("=" * 72)
        print(f"  RESUMO: {total} spots consultados")
        print(f"  Nossa recomendacao == GTO Wizard: {matches}/{total} ({matches/total*100:.0f}%)")
        print(f"  Acao jogada       == GTO Wizard: {gw_ok}/{total} ({gw_ok/total*100:.0f}%)")
        print()


if __name__ == "__main__":
    main()
