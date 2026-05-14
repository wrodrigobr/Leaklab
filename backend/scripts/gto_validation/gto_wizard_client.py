"""
GTO Wizard API client.

Auth: Bearer token via /v1/token/refresh/ using a long-lived refresh JWT.
Main endpoint: GET /v4/solutions/spot-solution/

Set GTOWIZARD_REFRESH_TOKEN env var before running.
"""
from __future__ import annotations
import os, time, json, logging, requests
from typing import Optional

log = logging.getLogger(__name__)

BASE = "https://api.gtowizard.com"
CLIENT_ID = "790ab864-ed0c-4545-9e5a-97efe89672cd"  # gwclientid from HAR

# gametype codes for MTT — 8-max is the standard
GAMETYPE_MTT_8M = "MTTGeneral_8m"
GAMETYPE_MTT_9M = "MTTGeneral_9m"


class GtoWizardClient:
    """
    Thin wrapper around the GTO Wizard REST API.

    Usage:
        client = GtoWizardClient()   # reads GTOWIZARD_REFRESH_TOKEN from env
        result = client.get_spot_solution(
            gametype=GAMETYPE_MTT_8M,
            depth=25.0,
            preflop_actions="R2-F-F-F-F-C",  # BTN open, BB call
            board="Ks Qd 2c",
            flop_actions="",                  # start of flop, OOP to act
        )
        print(result.summary())
    """

    def __init__(self, refresh_token: Optional[str] = None):
        self._refresh = refresh_token or os.environ.get("GTOWIZARD_REFRESH_TOKEN", "")
        if not self._refresh:
            raise ValueError(
                "Set GTOWIZARD_REFRESH_TOKEN env var or pass refresh_token=..."
            )
        self._access: Optional[str] = None
        self._access_exp: float = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://app.gtowizard.com",
            "Referer": "https://app.gtowizard.com/",
            "gwclientid": CLIENT_ID,
        })

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _ensure_token(self):
        """Refresh access token if missing or within 60s of expiry."""
        if self._access and time.time() < self._access_exp - 60:
            return
        log.debug("Refreshing GTO Wizard access token")
        r = self._session.post(
            f"{BASE}/v1/token/refresh/",
            json={"refresh": self._refresh},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        self._access = data["access"]
        # Decode exp from JWT payload (no signature verification needed here)
        import base64
        payload_b64 = self._access.split(".")[1]
        payload_b64 += "==" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        self._access_exp = float(payload.get("exp", time.time() + 3600))
        self._session.headers["Authorization"] = f"Bearer {self._access}"
        log.debug("Access token refreshed, expires %s", time.ctime(self._access_exp))

    # ── Spot encoding helpers ─────────────────────────────────────────────────

    @staticmethod
    def encode_board(board: str | list[str]) -> str:
        """
        Normalize board cards to GTO Wizard format: 'Ks Qd 2c' or ['Ks','Qd','2c'] → 'KsQd2c'
        Rank: 2-9, T, J, Q, K, A  /  Suit: s, h, d, c (lowercase)
        """
        if isinstance(board, list):
            cards = board
        else:
            cards = board.replace(",", " ").split()
        def _norm(c: str) -> str:
            c = c.strip()
            rank = c[0].upper()
            suit = c[1].lower()
            return rank + suit
        return "".join(_norm(c) for c in cards if c)

    @staticmethod
    def encode_stacks(depth: float, n_players: int = 8) -> str:
        """All players same starting stack (simplified for MTT spots)."""
        return "-".join([str(round(depth, 3))] * n_players)

    # ── Main API calls ────────────────────────────────────────────────────────

    def get_next_actions(
        self,
        depth: float,
        preflop_actions: str,
        board: str | list[str],
        flop_actions: str = "",
        turn_actions: str = "",
        river_actions: str = "",
        gametype: str = GAMETYPE_MTT_8M,
    ) -> dict:
        """
        GET /v4/game-points/next-actions/
        Returns available actions and game state at the given spot.
        Use this to validate that a spot exists before fetching the solution.
        """
        self._ensure_token()
        params = {
            "gametype": gametype,
            "depth": round(depth, 3),
            "stacks": self.encode_stacks(depth),
            "preflop_actions": preflop_actions,
            "flop_actions": flop_actions,
            "turn_actions": turn_actions,
            "river_actions": river_actions,
            "board": self.encode_board(board),
        }
        r = self._session.get(f"{BASE}/v4/game-points/next-actions/", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_spot_solution(
        self,
        depth: float,
        preflop_actions: str,
        board: str | list[str],
        flop_actions: str = "",
        turn_actions: str = "",
        river_actions: str = "",
        gametype: str = GAMETYPE_MTT_8M,
    ) -> "SpotSolution":
        """
        GET /v4/solutions/spot-solution/
        Returns GTO strategy (frequencies per action) for the given spot.

        Args:
            depth: effective stack in BBs (e.g. 25.0)
            preflop_actions: action sequence, e.g. "R2-F-F-F-F-C" (BTN open, BB call)
            board: flop cards, e.g. "Ks Qd 2c" or ['Ks','Qd','2c']
            flop_actions: actions taken on the flop so far, e.g. "X-B9.5"
            turn_actions / river_actions: same for later streets
            gametype: MTT variant (default 8-max)

        Returns:
            SpotSolution with .actions dict {fold/call/check/raise/bet: frequency}
        """
        self._ensure_token()
        params = {
            "gametype": gametype,
            "depth": round(depth, 3),
            "stacks": self.encode_stacks(depth),
            "preflop_actions": preflop_actions,
            "flop_actions": flop_actions,
            "turn_actions": turn_actions,
            "river_actions": river_actions,
            "board": self.encode_board(board),
        }
        r = self._session.get(f"{BASE}/v4/solutions/spot-solution/", params=params, timeout=30)
        if r.status_code == 404:
            return SpotSolution(found=False, raw={}, params=params)
        r.raise_for_status()
        return SpotSolution(found=True, raw=r.json(), params=params)


class SpotSolution:
    """Parsed result from /v4/solutions/spot-solution/."""

    def __init__(self, found: bool, raw: dict, params: dict):
        self.found = found
        self.raw = raw
        self.params = params
        self.actions: dict[str, float] = {}  # {action_name: total_frequency}
        self.top_action: Optional[str] = None
        if found and raw:
            self._parse(raw)

    def _parse(self, data: dict):
        action_solutions = data.get("action_solutions", [])
        best_freq = -1.0
        for item in action_solutions:
            action = item.get("action", {})
            freq = float(item.get("total_frequency", 0.0))
            # Normalize action type to our internal names
            raw_type = action.get("type", "").upper()
            name = {
                "CHECK": "check",
                "CALL": "call",
                "FOLD": "fold",
                "BET": "bet",
                "RAISE": "raise",
                "ALL_IN": "allin",
                "ALLIN": "allin",
            }.get(raw_type, raw_type.lower())
            # Aggregate by action family (multiple bet sizes collapse into "bet")
            self.actions[name] = self.actions.get(name, 0.0) + freq
            if freq > best_freq:
                best_freq = freq
                self.top_action = name

    @property
    def fold(self) -> float:
        return self.actions.get("fold", 0.0)

    @property
    def call(self) -> float:
        return self.actions.get("call", 0.0)

    @property
    def check(self) -> float:
        return self.actions.get("check", 0.0)

    @property
    def bet(self) -> float:
        return self.actions.get("bet", 0.0) + self.actions.get("raise", 0.0)

    @property
    def allin(self) -> float:
        return self.actions.get("allin", 0.0)

    def summary(self) -> str:
        if not self.found:
            return "[not found]"
        parts = []
        for name, freq in sorted(self.actions.items(), key=lambda x: -x[1]):
            parts.append(f"{name} {freq*100:.1f}%")
        return " | ".join(parts) if parts else "[empty]"

    def __repr__(self):
        return f"SpotSolution(found={self.found}, {self.summary()})"
