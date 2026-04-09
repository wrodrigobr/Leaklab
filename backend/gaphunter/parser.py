from __future__ import annotations
import re
from typing import List
from .models import ParsedHand, ParsedAction

HAND_SPLIT_RE = re.compile(r"(?=PokerStars Hand #)")
HAND_ID_RE = re.compile(r"PokerStars Hand #(\d+)")
TOURN_RE = re.compile(r"Tournament #(\d+)")
BUTTON_RE = re.compile(r"Seat #(\d+) is the button")
HERO_DEALT_RE = re.compile(r"Dealt to ([^\[]+) \[([^\]]+)\]")
BOARD_RE = re.compile(r"\[([^\]]+)\]")
SB_RE = re.compile(r"\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)")
ACTION_LINE_RE = re.compile(
    r"^(?P<player>[^:]+): (?P<action>folds|checks|calls|bets|raises|all-in|shows|mucks)(?: .*?(?P<amount>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)
SEAT_RE = re.compile(r"^Seat \d+: ([^(]+) \(")


def parse_pokerstars_file(path: str) -> List[ParsedHand]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    chunks = [c.strip() for c in HAND_SPLIT_RE.split(content) if c.strip().startswith("PokerStars Hand #")]
    return [parse_hand(chunk) for chunk in chunks]


def parse_hand(raw_text: str) -> ParsedHand:
    hand_id = _search(HAND_ID_RE, raw_text)
    tourn_id = _search(TOURN_RE, raw_text)
    button = _search(BUTTON_RE, raw_text, cast=int)
    hero_name = None
    hero_cards = None
    m = HERO_DEALT_RE.search(raw_text)
    if m:
        hero_name = m.group(1).strip()
        hero_cards = m.group(2).replace(" ", "")
    sb = bb = None
    m2 = SB_RE.search(raw_text)
    if m2:
        sb = float(m2.group(1))
        bb = float(m2.group(2))

    players = []
    actions: List[ParsedAction] = []
    street = "preflop"
    board = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("*** FLOP ***"):
            street = "flop"
            board = _extract_board(line)
            continue
        if line.startswith("*** TURN ***"):
            street = "turn"
            board = _extract_board(line)
            continue
        if line.startswith("*** RIVER ***"):
            street = "river"
            board = _extract_board(line)
            continue
        if line.startswith("Seat ") and ":" in line and "(" in line and "in chips" in line:
            name = line.split(":", 1)[1].split("(", 1)[0].strip()
            players.append(name)
        ma = ACTION_LINE_RE.match(line)
        if ma:
            amount = ma.group("amount")
            actions.append(ParsedAction(
                player=ma.group("player").strip(),
                street=street,
                action=ma.group("action").lower(),
                amount=float(amount) if amount else None,
                raw=line,
            ))

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
    )


def _extract_board(line: str):
    """Extrai o board acumulado de uma linha de street.
    TURN/RIVER têm 2 grupos: [board acumulado] [carta nova]
    Sempre usamos o primeiro grupo (board completo até aqui).
    """
    matches = BOARD_RE.findall(line)
    if not matches:
        return []
    # matches[0] = board acumulado (flop ou turn+flop)
    # matches[-1] = só a carta nova (em TURN/RIVER)
    cards = matches[0].split()
    return cards


def _search(regex, text, cast=str):
    m = regex.search(text)
    if not m:
        return None
    return cast(m.group(1))


def parse_pokerstars_file_from_text(text: str):
    """
    Versão da função de parse que aceita string diretamente.
    Usada pela API para evitar I/O de arquivo.
    """
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                     encoding='utf-8', delete=False) as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    try:
        return parse_pokerstars_file(tmp_path)
    finally:
        os.unlink(tmp_path)
