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

# Gametype MTT do GTO Wizard — 9-max (MTTGeneral)
GW_GAMETYPE = "MTTGeneral"
GW_NUM_PLAYERS = 9

# Snapshots de stack disponíveis no GTO Wizard MTT
GW_STACK_SNAPS = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]

# Preflop action sequences para MTTGeneral 9-max (8 acoes: posicoes antes do blinds)
# Arvore usa 8 acoes preflop: UTG/UTG+1/LJ/HJ/CO/BTN/SB/BB
# Raise size padrao: 2.3bb (tamanho do tree — confirmado via API)
# Stacks: string vazia (arvore usa depth= como referencia)
PREFLOP_BY_POS = {
    "UTG":   "R2.3-F-F-F-F-F-F-C",   # UTG abre, 5 fold, SB fold, BB call
    "UTG+1": "F-R2.3-F-F-F-F-F-C",   # UTG+1 abre
    "UTG+2": "F-F-R2.3-F-F-F-F-C",   # alias LJ
    "LJ":    "F-F-R2.3-F-F-F-F-C",   # LJ abre (3a posicao)
    "HJ":    "F-F-F-R2.3-F-F-F-C",   # HJ abre
    "CO":    "F-F-F-F-R2.3-F-F-C",   # CO abre
    "BTN":   "F-F-F-F-F-R2.3-F-C",   # BTN abre — CONFIRMADO via API
    "SB":    "F-F-F-F-F-F-R2.3-C",   # SB abre vs BB
    "BB":    "F-F-F-F-F-R2.3-F-C",   # BTN abre, SB fold, BB call (OOP hero)
    "MP":    "F-F-R2.3-F-F-F-F-C",   # alias LJ
    "EP":    "R2.3-F-F-F-F-F-F-C",   # alias UTG
}


# ── Auth Manager ──────────────────────────────────────────────────────────────

class GWAuth:
    """Gerencia o token de acesso ao GTO Wizard, auto-refreshing quando necessario."""

    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    @classmethod
    def anal_id_from_har(cls, har_path: Path) -> str:
        """Extrai o google-anal-id mais recente do HAR (browser remove Authorization por seguranca)."""
        try:
            with open(har_path, encoding="utf-8") as f:
                har = json.load(f)
        except Exception:
            return ""
        best_anal = ""
        best_time = 0.0
        import datetime
        for entry in har["log"]["entries"]:
            if "api.gtowizard.com" not in entry["request"]["url"]:
                continue
            hdrs = {h["name"].lower(): h["value"] for h in entry["request"].get("headers", [])}
            anal = hdrs.get("google-anal-id", "")
            if not anal:
                continue
            try:
                t = datetime.datetime.fromisoformat(
                    entry["startedDateTime"].replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                t = 0.0
            if t > best_time:
                best_time = t
                best_anal = anal
        return best_anal

    @classmethod
    def from_har(cls, har_path: Path) -> "tuple[GWAuth, str]":
        """Tenta extrair access token do HAR. Browser geralmente remove Authorization — use env var."""
        with open(har_path, encoding="utf-8") as f:
            har = json.load(f)
        entries = har["log"]["entries"]

        # Tenta achar access token (raro — browser normalmente retira)
        best_access = ""
        best_time   = 0.0
        import datetime
        for entry in entries:
            if "api.gtowizard.com" not in entry["request"]["url"]:
                continue
            hdrs = {h["name"].lower(): h["value"] for h in entry["request"].get("headers", [])}
            auth = hdrs.get("authorization", "")
            if not auth.startswith("Bearer "):
                continue
            try:
                t = datetime.datetime.fromisoformat(
                    entry["startedDateTime"].replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                t = 0.0
            if t > best_time:
                best_time   = t
                best_access = auth.removeprefix("Bearer ").strip()

        anal = cls.anal_id_from_har(har_path)
        if best_access:
            print(f"[auth] Access token extraido do HAR.")
            return cls.from_access_token(best_access), anal

        raise ValueError(
            "O browser remove o header Authorization ao exportar HAR.\n"
            "Use: $env:GW_ACCESS_TOKEN = 'eyJ...'  (copie do DevTools > Network > Headers)\n"
            "O google-anal-id sera lido do HAR automaticamente."
        )

    @classmethod
    def from_access_token(cls, token: str) -> "GWAuth":
        """Usa um access token direto (sem refresh). Expira em ~15min — rerun quando necessario."""
        import base64
        inst = cls(refresh_token="")
        inst._access_token = token
        parts = token.split(".")
        try:
            pad    = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.b64decode(pad))
            inst._expires_at = float(claims.get("exp", time.time() + 900))
            remaining = int(inst._expires_at - time.time())
            print(f"[auth] Access token direto — expira em {remaining}s.")
            if remaining < 30:
                print("[auth] AVISO: token expirado ou prestes a expirar!")
        except Exception:
            inst._expires_at = time.time() + 900
            print("[auth] Nao foi possivel decodificar o JWT — usando TTL de 15min.")
        return inst

    @classmethod
    def from_env_or_har(cls, har_path: Path) -> "tuple[GWAuth, str]":
        """Retorna (auth, anal_id).
        - Bearer token: GW_ACCESS_TOKEN env var (obrigatorio)
        - google-anal-id: GW_ANAL_ID env var OU extraido do HAR automaticamente
        """
        # 1. Access token (obrigatorio — browser retira do HAR)
        access = os.environ.get("GW_ACCESS_TOKEN", "").strip()
        if not access:
            print(
                "ERRO: GW_ACCESS_TOKEN nao definido.\n"
                "Copie o Bearer token do DevTools (Network > qualquer request api.gtowizard.com > Headers > Authorization):\n"
                "  $env:GW_ACCESS_TOKEN = 'eyJ...'"
            )
            sys.exit(1)
        print("[auth] Usando GW_ACCESS_TOKEN do ambiente.")
        auth = cls.from_access_token(access)

        # 2. google-anal-id: env var tem prioridade, senao tenta HAR
        anal = os.environ.get("GW_ANAL_ID", "").strip()
        if anal:
            print("[auth] google-anal-id do ambiente.")
        elif har_path.is_file():
            anal = cls.anal_id_from_har(har_path)
            if anal:
                print(f"[auth] google-anal-id extraido do HAR ({har_path.name}).")
            else:
                print("[auth] AVISO: google-anal-id nao encontrado no HAR — navegue ate Solutions antes de salvar o HAR.")
        else:
            print("[auth] AVISO: google-anal-id ausente — requests de Solutions podem falhar.")

        return auth, anal

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
        import requests as _req
        url = f"{GW_API_BASE}/v1/token/refresh/"
        try:
            r = _req.post(url, json={"refresh": self.refresh_token},
                          headers={"Origin": "https://app.gtowizard.com"}, timeout=15)
            r.raise_for_status()
            data = r.json()
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
    def __init__(self, auth: GWAuth, anal_id: str = ""):
        self.auth    = auth
        self.anal_id = anal_id or os.environ.get("GW_ANAL_ID", "")

    def _headers(self) -> dict:
        h = {
            "authorization":      f"Bearer {self.auth.access_token()}",
            "accept":             "application/json, text/plain, */*",
            "origin":             "https://app.gtowizard.com",
            "referer":            "https://app.gtowizard.com/",
            "gwclientid":         GW_CLIENT_ID,
            "user-agent":         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "sec-ch-ua":          '"Chromium";v="147", "Not/A)Brand";v="24"',
            "sec-ch-ua-mobile":   "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        if self.anal_id:
            h["google-anal-id"] = self.anal_id
        return h

    def _get(self, path: str, params: dict) -> Optional[dict]:
        try:
            import requests as _req
        except ImportError:
            print("  [!] pip install requests")
            return None
        url = f"{GW_API_BASE}{path}"
        try:
            r = _req.get(url, params=params, headers=self._headers(), timeout=20)
            if r.status_code == 204 or not r.content:
                print(f"  [!] HTTP {r.status_code} body vazio para {path}")
                return None
            if not r.ok:
                print(f"  [!] HTTP {r.status_code} para {path}: {r.text[:200]}")
                return None
            return r.json()
        except RuntimeError as e:
            print(f"  [!] Auth error: {e}")
            return None
        except Exception as e:
            print(f"  [!] Erro em {path}: {e}")
            return None

    def spot_solution(self, params: dict) -> Optional[dict]:
        api_params = {k: v for k, v in params.items() if not k.startswith("_")}
        return self._get("/v4/solutions/spot-solution/", api_params)

    def board_usage(self) -> Optional[dict]:
        return self._get("/v4/solutions/board-usage/", {})


# ── Banco de dados ─────────────────────────────────────────────────────────────

def fetch_decisions(
    db_path: Path,
    user_id: Optional[int] = None,
    street: str = "flop",
    mistakes_only: bool = False,
    limit: int = 10,
    min_stack: float = 20.0,
) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    wheres = [
        "d.street = ?",
        "d.board IS NOT NULL AND d.board != ''",
        f"d.stack_bb IS NOT NULL AND d.stack_bb >= {min_stack}",  # min stack p/ ter solucao de flop no GTO Wizard
        "d.pot_size IS NOT NULL AND d.pot_size > 0.5",
        "d.position IS NOT NULL",
        "d.is_3bet = 0",  # SRP apenas (mais facil de reconstruir preflop_actions)
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


def build_gw_params(dec: dict) -> Optional[dict]:
    """
    Converte uma decisao do nosso DB para os parametros do GTO Wizard.

    Usa os mesmos snapshots de stack e sequencias preflop do generate_console_script.py
    para maximizar compatibilidade com a arvore de solucoes do GTO Wizard.
    """
    try:
        board = json.loads(dec["board"]) if isinstance(dec["board"], str) else dec["board"]
    except Exception:
        return None

    if not board or len(board) < 3:
        return None

    position = (dec.get("position") or "BTN").upper()
    stack_bb = float(dec["stack_bb"])

    # Snap para o snapshot mais proximo disponivel no GTO Wizard
    snap = min(GW_STACK_SNAPS, key=lambda s: abs(s - stack_bb))
    stack_frac = snap + 0.125   # fracional = estado MTT com antes
    stacks_str = ""             # arvore MTTGeneral usa depth= como referencia

    # Sequencia preflop (SRP assumido — nao temos info de vilao no DB)
    preflop_str = PREFLOP_BY_POS.get(position)
    if not preflop_str:
        return None  # posicao desconhecida

    # Board: apenas as 3 cartas do flop, rank uppercase + suit lowercase
    flop = []
    for c in board[:3]:
        c = c.strip()
        if len(c) >= 2:
            flop.append(c[0].upper() + c[1].lower())
    if len(flop) < 3:
        return None
    board_str = "".join(flop)

    return {
        "gametype":        GW_GAMETYPE,
        "depth":           stack_frac,
        "stacks":          stacks_str,
        "preflop_actions": preflop_str,
        "flop_actions":    "",
        "turn_actions":    "",
        "river_actions":   "",
        "board":           board_str,
        # campos privados para display (filtrados antes de enviar para API)
        "_board_list":     board,
        "_position":       position,
        "_snap_bb":        snap,
        "_stack_bb":       stack_bb,
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

    snap    = params.get("_snap_bb", stack)
    spr     = round(stack / pot, 2) if pot else 0
    pot_type= "3BET" if is_3bet else "SRP"

    print()
    print("=" * 72)
    print(f"  {_color(street, BOLD)}  Board: {_color(b_str, CYAN)}  |  {pos} ({pot_type})")
    print(f"  Pot: {pot:.1f} BB  Stack: {stack:.1f} BB (snap: {snap}bb)  SPR: {spr}  Hand: {hand_id}")
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
    parser.add_argument("--min-stack",    type=float, default=20.0,
                        help="Stack minimo em BB (default 20, GTO Wizard sem flop solutions < 20bb)")
    parser.add_argument("--db",           default=str(DB_DEFAULT))
    parser.add_argument("--har",          default=str(HAR_DEFAULT))
    args = parser.parse_args()

    db_path  = Path(args.db)
    har_path = Path(args.har)

    if not db_path.is_file():
        print(f"DB nao encontrado: {db_path}")
        sys.exit(1)

    # Auth
    auth, anal_id = GWAuth.from_env_or_har(har_path)
    if not anal_id:
        print("[auth] AVISO: google-anal-id nao encontrado — requests de Solutions podem falhar.")
    client = GWClient(auth, anal_id)

    # Verifica quota antes de comecar (opcional — falha silenciosamente)
    try:
        usage = client.board_usage()
        if usage:
            print(f"[quota] Gametype: {usage.get('gametype')}  "
                  f"Reset: {usage.get('reset_date','?')[:10]}")
    except Exception:
        pass  # board_usage nao e essencial para o benchmark

    # Busca decisoes
    decisions = fetch_decisions(
        db_path,
        user_id      = args.user_id,
        street       = args.street,
        mistakes_only= args.mistakes_only,
        limit        = args.limit,
        min_stack    = args.min_stack,
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
        if gw_result and gw_result.get("action_solutions"):
            print(f"OK ({len(gw_result['action_solutions'])} acoes)")
        elif gw_result is not None:
            print("OK (sem action_solutions)")
        else:
            print("FALHOU")

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
