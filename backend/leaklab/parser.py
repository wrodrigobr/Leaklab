from __future__ import annotations
import re
from typing import List
from .models import ParsedHand, ParsedAction

# ── PokerStars patterns ───────────────────────────────────────────────────────
PS_SPLIT_RE  = re.compile(r"(?=PokerStars Hand #)")
PS_ID_RE     = re.compile(r"PokerStars Hand #(\d+)")

# ── GGPoker patterns ──────────────────────────────────────────────────────────
# Hand IDs: #SG... (Spin & Gold), #RC... (regular), #HD... (Hold'em), etc.
GG_SPLIT_RE  = re.compile(r"(?=Poker Hand #)")
GG_ID_RE     = re.compile(r"Poker Hand #(\w+)")

# ── Shared patterns ───────────────────────────────────────────────────────────
TOURN_RE        = re.compile(r"Tournament #(\d+)")
BUTTON_RE       = re.compile(r"Seat #(\d+) is the button")
HERO_DEALT_RE   = re.compile(r"Dealt to ([^\[\n]+) \[([^\]]+)\]")
BOARD_RE        = re.compile(r"\[([^\]]+)\]")
SB_RE           = re.compile(r"\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)")
ACTION_LINE_RE  = re.compile(
    r"^(?P<player>[^:]+): (?P<action>folds|checks|calls|bets|raises|all-in|shows|mucks)"
    r"(?: .*?(?P<amount>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)
# PokerStars PKO: "Seat 3: phpro (1500 in chips) bounty $0.25"
SEAT_BOUNTY_PS_RE = re.compile(
    r"^Seat \d+: (.+?) \(\d+ in chips\) bounty \$([0-9.]+)", re.IGNORECASE
)
# GGPoker PKO: "Seat 3: phpro (1500 in chips, bounty $0.25)"
SEAT_BOUNTY_GG_RE = re.compile(
    r"^Seat \d+: (.+?) \(\d+ in chips, bounty \$([0-9.]+)\)", re.IGNORECASE
)
# PokerStars bounty collection: "phpro wins $0.25 bounty for eliminating villain"
BOUNTY_WIN_RE = re.compile(
    r"^(.+?) wins \$([0-9.]+) bounty for eliminating (.+)", re.IGNORECASE
)
# Deteccao PKO via header (caso bounties no seat nao estejam visiveis):
# 3-tier buyin "$0.45+$0.45+$0.10" (buyin + bounty + rake)
PKO_3TIER_RE = re.compile(r"\$[0-9.]+\+\$[0-9.]+\+\$[0-9.]+")
PKO_KEYWORD_RE = re.compile(
    r"\b(progressive|knockout|bounty\b|\bKO|PKO)\b", re.IGNORECASE
)


def _detect_site(text: str) -> str:
    """Detecta o site a partir do conteúdo do hand history."""
    if "PokerStars Hand #" in text:
        return "pokerstars"
    if "Poker Hand #" in text:
        return "ggpoker"
    return "unknown"


def _split_hands(text: str, site: str) -> List[str]:
    """Divide o texto em chunks de mão individuais."""
    if site == "ggpoker":
        prefix = "Poker Hand #"
        chunks = [c.strip() for c in GG_SPLIT_RE.split(text) if c.strip().startswith(prefix)]
    else:
        prefix = "PokerStars Hand #"
        chunks = [c.strip() for c in PS_SPLIT_RE.split(text) if c.strip().startswith(prefix)]
    return chunks


def parse_pokerstars_file(path: str) -> List[ParsedHand]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return parse_hand_history(content)


def parse_hand_history(text: str) -> List[ParsedHand]:
    """Parseia hand history de qualquer site suportado (PokerStars ou GGPoker)."""
    site = _detect_site(text)
    id_re = GG_ID_RE if site == "ggpoker" else PS_ID_RE
    chunks = _split_hands(text, site)
    return [parse_hand(chunk, id_re) for chunk in chunks]


def parse_hand(raw_text: str, id_re: re.Pattern | None = None) -> ParsedHand:
    if id_re is None:
        id_re = PS_ID_RE

    hand_id  = _search(id_re, raw_text)
    tourn_id = _search(TOURN_RE, raw_text)
    button   = _search(BUTTON_RE, raw_text, cast=int)

    hero_name  = None
    hero_cards = None
    m = HERO_DEALT_RE.search(raw_text)
    if m:
        hero_name  = m.group(1).strip()
        hero_cards = m.group(2).replace(" ", "")

    sb = bb = None
    m2 = SB_RE.search(raw_text)
    if m2:
        sb = float(m2.group(1))
        bb = float(m2.group(2))

    players: List[str] = []
    actions: List[ParsedAction] = []
    bounties: dict = {}
    street = "preflop"
    board  = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("*** FLOP ***"):
            street = "flop"
            board  = _extract_board(line)
            continue
        if line.startswith("*** TURN ***"):
            street = "turn"
            board  = _extract_board(line)
            continue
        if line.startswith("*** RIVER ***"):
            street = "river"
            board  = _extract_board(line)
            continue
        if line.startswith("Seat ") and ":" in line and "(" in line and "in chips" in line:
            name = line.split(":", 1)[1].split("(", 1)[0].strip()
            players.append(name)
            mb = SEAT_BOUNTY_PS_RE.match(line) or SEAT_BOUNTY_GG_RE.match(line)
            if mb:
                bounties[mb.group(1).strip()] = float(mb.group(2))
        mw = BOUNTY_WIN_RE.match(line)
        if mw:
            # Track latest bounty value per player (bounty grows as they knock out others)
            winner = mw.group(1).strip()
            amount = float(mw.group(2))
            bounties[winner] = bounties.get(winner, 0.0) + amount
        ma = ACTION_LINE_RE.match(line)
        if ma:
            amount = ma.group("amount")
            action_str = ma.group("action").lower()
            # "bets X and is all-in" / "raises X and is all-in" → all-in
            if action_str in ('bets', 'raises') and 'and is all-in' in line.lower():
                action_str = 'all-in'
            actions.append(ParsedAction(
                player=ma.group("player").strip(),
                street=street,
                action=action_str,
                amount=float(amount) if amount else None,
                raw=line,
            ))

    # Deteccao PKO: bounty visivel em seat OU header com 3-tier buyin OU palavra-chave
    is_pko = bool(bounties)
    if not is_pko:
        header = raw_text[:300]
        # PokerStars: $0.45+$0.45+$0.10 (buyin + bounty + rake)
        if PKO_3TIER_RE.search(header):
            is_pko = True
        elif PKO_KEYWORD_RE.search(header):
            is_pko = True

    return ParsedHand(
        hand_id=hand_id or "unknown",
        tournament_id=tourn_id,
        hero=hero_name,
        button_seat=button,
        sb=sb,
        bb=bb,
        hero_cards=hero_cards,
        board=board,
        players=players,
        actions=actions,
        raw_text=raw_text,
        bounties=bounties,
        is_pko=is_pko,
    )


def _extract_board(line: str) -> List[str]:
    """Extrai o board completo de uma linha de street.

    Formato (PokerStars e GGPoker são idênticos):
      FLOP:  *** FLOP ***   [Ah Kd 3c]
      TURN:  *** TURN ***   [Ah Kd 3c] [7s]
      RIVER: *** RIVER ***  [Ah Kd 3c 7s] [9h]
    """
    matches = BOARD_RE.findall(line)
    if not matches:
        return []
    cards = []
    for group in matches:
        cards.extend(group.split())
    return cards


def _search(regex, text, cast=str):
    m = regex.search(text)
    if not m:
        return None
    return cast(m.group(1))


def parse_pokerstars_file_from_text(text: str) -> List[ParsedHand]:
    """Aceita string diretamente — detecta site automaticamente."""
    return parse_hand_history(text)
