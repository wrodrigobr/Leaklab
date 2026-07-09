from __future__ import annotations
import re
from typing import List, Optional
from .models import ParsedHand, ParsedAction

# ── Timestamp da mão (todas as salas): "2025/12/11 14:27:59 ET" / "... -05" / sem TZ ──
_HAND_TS_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")


def extract_session_times(raw_text: str):
    """(started_at, ended_at) = timestamp da 1ª e da última mão do torneio, no formato
    'YYYY-MM-DD HH:MM:SS' (hora LOCAL da sala; o sufixo de fuso é descartado). Serve de base
    para concorrência (janelas de torneio que se sobrepõem), fadiga (ordem na sessão) e horário.
    Retorna (None, None) se não houver timestamp. Formato ISO-like ordena cronologicamente."""
    if not raw_text:
        return None, None
    ts = [f"{m[0]}-{m[1]}-{m[2]} {m[3]}:{m[4]}:{m[5]}" for m in _HAND_TS_RE.findall(raw_text)]
    if not ts:
        return None, None
    return min(ts), max(ts)


# ── PokerStars patterns ───────────────────────────────────────────────────────
PS_SPLIT_RE  = re.compile(r"(?=PokerStars Hand #)")
PS_ID_RE     = re.compile(r"PokerStars Hand #(\d+)")

# ── GGPoker patterns ──────────────────────────────────────────────────────────
# Hand IDs: #SG... (Spin & Gold), #RC... (regular), #HD... (Hold'em), etc.
GG_SPLIT_RE  = re.compile(r"(?=Poker Hand #)")
GG_ID_RE     = re.compile(r"Poker Hand #(\w+)")

# ── ACR / WPN patterns (Americas Cardroom / Winning Poker Network) ─────────────
# Dialeto PokerStars-like na estrutura MAS com diferenças que quebram o parser PS:
#   header "Game Hand #<id> - Tournament #<tid> - Holdem (No Limit) - Level N (sb.00/bb.00) - ... UTC"
#   assentos "Seat N: nome (29150.00)"  → SEM "in chips", stack decimal
#   AÇÕES SEM DOIS-PONTOS: "nome raises X to Y", "nome calls X", "nome folds", "... and is all-in"
#   antes "nome posts ante 150.00" (sem "the"/sem ":"), linhas "Main pot X" extras (ignoradas)
# Header/button/hero/blinds(decimais)/board/showdown reusam os regexes compartilhados. Ver
# specs/acr-parser.md. Vários arquivos do MESMO Tournament # = mesmo torneio (merge no import).
ACR_SPLIT_RE  = re.compile(r"(?=Game Hand #)")
ACR_ID_RE     = re.compile(r"Game Hand #(\d+)")
ACR_SEAT_RE   = re.compile(r"^Seat (\d+): (.+?) \(([\d.,]+)\)$")
ACR_ANTE_RE   = re.compile(r"^(?P<player>.+?) posts (?:the )?ante (?P<amount>[\d.,]+)", re.IGNORECASE)
# "raises X to Y" (Y=total), "calls X", "bets X", "folds"/"checks", "... and is all-in".
ACR_ACTION_RE = re.compile(
    r"^(?P<player>.+?) (?P<action>folds|checks|calls|bets|raises)"
    r"(?:\s+(?P<amount>[\d.,]+))?(?:\s+to\s+(?P<toamt>[\d.,]+))?"
    r"(?P<allin>\s+and is all-in)?\s*$",
    re.IGNORECASE,
)

# ── CoinPoker patterns ────────────────────────────────────────────────────────
# Dialeto PokerStars-like: ações COM dois-pontos ("player: raises 300 to 400"), assentos
# "Seat N: hash (10,000 in chips)", antes/blinds/streets/showdown padrão. Diferenças que
# quebram o parser PS:
#   header 2 linhas: "CoinPoker Hand #<id>: NLH (50/100/15) <data> -05"  (sb/bb/ANTE com BARRAS,
#     não o ante aninhado do GG "(sb/bb(ante))" → o SB_RE não casa → bb=None → bug das fichas)
#   torneio na 2a linha: "Tournament '₮1.10 ... PKO [Turbo]' '72561' 7-max Seat #3 is the button"
#     (id entre aspas, não "Tournament #<id>"); buy-in em ₮ (token), não $; showdown "*** SHOWDOWN ***"
# Nomes anonimizados (hash), Hero é "Hero". Button/hero/board/showdown reusam os regexes shared.
COIN_SPLIT_RE  = re.compile(r"(?=CoinPoker Hand #)")
COIN_ID_RE     = re.compile(r"CoinPoker Hand #(\d+)")
# blinds do header "(50/100/15)" = sb/bb/ante (o gate do bb). Aceita milhar (vírgula/espaço).
COIN_BLINDS_RE = re.compile(r"\((\d[\d, ]*(?:\.\d+)?)/(\d[\d, ]*(?:\.\d+)?)/(\d[\d, ]*(?:\.\d+)?)\)")
# id do torneio entre aspas: "Tournament '<nome>' '<id>' <max>-max"
COIN_TOURN_RE  = re.compile(r"Tournament\s+'[^']*'\s+'(\w+)'")


# ── PartyGaming dialect (888poker / PartyPoker) ───────────────────────────────
# Os dois sites compartilham um formato quase idêntico (herança Pacific/PartyGaming),
# bem diferente do PokerStars/GGPoker. Header e cada linha de ação mudam.
#   888:   ***** 888poker Hand History for Game 655462938 *****
#   Party: ***** Hand History for Game 13165152578 *****
PG_SPLIT_RE   = re.compile(r"(?=\*\*\*\*\* (?:888poker )?Hand History for Game)")
PG_ID_RE      = re.compile(r"Hand History for Game (\d+)")
PG_TOURN_RE   = re.compile(r"Tournament #(\d+)|Trny:\s*(\d+)", re.IGNORECASE)
PG_BUTTON_RE  = re.compile(r"Seat (\d+) is the button")
PG_SEAT_RE    = re.compile(r"^Seat (\d+): (.+?) \(")
PG_DEALT_RE   = re.compile(r"Dealt to (\S+) \[\s*([^\]]+?)\s*\]")
# Blinds: tenta na ordem — antes-blinds (MTT party), blinds parentizado (STT party),
# e o par "$sb/$bb" (cash/tourney 888 e cash party). Números podem ter "," ou " " (milhar).
PG_BLINDS_AB_RE  = re.compile(r"Blinds-Antes\(([\d ,]+)/([\d ,]+)")
PG_BLINDS_P_RE   = re.compile(r"Blinds\(([\d ,]+)/([\d ,]+)\)")
PG_BLINDS_DOLLAR_RE = re.compile(r"\$([\d.,]+)/\$([\d.,]+)")
# Ações (sem ":" — diferença central vs PokerStars). Valor opcional em [ ... ].
PG_ACTION_RE  = re.compile(
    r"^(?P<player>\S+) (?P<action>folds|checks|calls|bets|raises|shows)"
    r"(?: \[\s*(?P<amount>[^\]]+?)\s*\])?",
    re.IGNORECASE,
)
# All-in tem sintaxe própria: "Player is all-In  [425]"
PG_ALLIN_RE   = re.compile(r"^(?P<player>\S+) is all-In\s*\[\s*(?P<amount>[^\]]+?)\s*\]", re.IGNORECASE)

# ── Shared patterns ───────────────────────────────────────────────────────────
TOURN_RE        = re.compile(r"Tournament #(\d+)")
BUTTON_RE       = re.compile(r"Seat #(\d+) is the button")
HERO_DEALT_RE   = re.compile(r"Dealt to ([^\[\n]+) \[([^\]]+)\]")
BOARD_RE        = re.compile(r"\[([^\]]+)\]")
# Blinds no header: "(10/20)" (PokerStars) e "(400/800(120))" (GGPoker, com ante aninhado antes
# do ")"). O 3º grupo opcional captura o ante. Sem o ante opcional, o GG não casava → bb=None e o
# display tratava 400/800 como 4bb/8bb (caía num default bb=100).
# Aceita separador de milhar (vírgula/espaço): GG em níveis altos escreve "Level14(1,500/3,000(350))"
# — sem isto o \d+ parava no "1,500" → bb=None → potBb/stack_bb em FICHAS → nós GTO degenerados.
# Converter os grupos SEMPRE via _pg_num (tira vírgula/espaço) antes do float.
SB_RE           = re.compile(r"\((\d[\d, ]*(?:\.\d+)?)/(\d[\d, ]*(?:\.\d+)?)(?:\((\d[\d, ]*(?:\.\d+)?)\))?\)")
ACTION_LINE_RE  = re.compile(
    r"^(?P<player>[^:]+): (?P<action>folds|checks|calls|bets|raises|all-in|shows|mucks)"
    r"(?: .*?(?P<amount>\d[\d,]*(?:\.\d+)?))?",   # aceita separador de milhar do GG (1,109)
    re.IGNORECASE,
)

# "<player>: posts the ante 40" / "posts ante 40" (PS/GG). Antes não são ações (não entram
# em ACTION_LINE_RE) e vão direto pro pote como dead money — capturados à parte por assento.
ANTE_LINE_RE    = re.compile(
    r"^(?P<player>[^:]+): posts (?:the )?ante (?P<amount>\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
# PokerStars PKO: "Seat 3: phpro (1500 in chips) bounty $0.25"
SEAT_BOUNTY_PS_RE = re.compile(
    r"^Seat \d+: (.+?) \([0-9.,]+ in chips\) bounty \$([0-9.]+)", re.IGNORECASE
)
# GGPoker PKO: "Seat 3: phpro (1500 in chips, bounty $0.25)"
SEAT_BOUNTY_GG_RE = re.compile(
    r"^Seat \d+: (.+?) \([0-9.,]+ in chips, bounty \$([0-9.]+)\)", re.IGNORECASE
)
# PokerStars PKO (formato real PS): "Seat 3: phpro (1500 in chips, $0.25 bounty)"
# quantia ANTES da palavra "bounty", dentro dos parênteses (aceita $1 ou $0.50).
SEAT_BOUNTY_PS2_RE = re.compile(
    r"^Seat \d+: (.+?) \([0-9.,]+ in chips, \$([0-9.]+) bounty\)", re.IGNORECASE
)
# Assento que NÃO participa desta mão: jogador movido de outra mesa que só vai
# jogar depois do botão passar por ele —
#   "Seat 1: rafaela919 (1500 in chips) out of hand (moved from another table into small blind)"
# Ele ocupa o assento mas NÃO recebe cartas, NÃO posta blind/ante e NÃO age. Contá-lo
# como jogador inflava num_players (HU virava "multiway") e deslocava as posições. É
# excluído de players/seats no parser e da contagem de assentos do cálculo de posição.
SEAT_OUT_OF_HAND_RE = re.compile(r"\bout of hand\b", re.IGNORECASE)
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


# Suporte a 888poker/PartyPoker (dialeto PartyGaming) — DESATIVADO por ora.
# Foco atual: PokerStars/GGPoker. O parser PartyGaming permanece todo no código
# (funções _parse_partygaming_*, regexes, extração financeira) e seus testes
# continuam validando-o; basta voltar esta flag para True para reativar a
# detecção/roteamento. Ver CHANGELOG "desabilita detecção 888/PartyPoker".
PARTYGAMING_ENABLED = False


def _detect_site(text: str) -> str:
    """Detecta o site a partir do conteúdo do hand history."""
    if "PokerStars Hand #" in text:
        return "pokerstars"
    if "CoinPoker Hand #" in text:       # ANTES do GG: "CoinPoker Hand #" contém "Poker Hand #"
        return "coinpoker"
    if "Poker Hand #" in text:
        return "ggpoker"
    if "Game Hand #" in text:            # ACR/WPN: "Game Hand #... - Tournament #..."
        return "acr"
    if PARTYGAMING_ENABLED:
        # 888 antes de PartyPoker: o header do 888 também contém "Hand History for Game".
        if "888poker" in text:
            return "888poker"
        if "Hand History for Game" in text:
            return "partypoker"
    return "unknown"


def _split_hands(text: str, site: str) -> List[str]:
    """Divide o texto em chunks de mão individuais."""
    if site == "coinpoker":
        prefix = "CoinPoker Hand #"
        chunks = [c.strip() for c in COIN_SPLIT_RE.split(text) if c.strip().startswith(prefix)]
    elif site == "ggpoker":
        prefix = "Poker Hand #"
        chunks = [c.strip() for c in GG_SPLIT_RE.split(text) if c.strip().startswith(prefix)]
    elif site == "acr":
        prefix = "Game Hand #"
        chunks = [c.strip() for c in ACR_SPLIT_RE.split(text) if c.strip().startswith(prefix)]
    else:
        prefix = "PokerStars Hand #"
        chunks = [c.strip() for c in PS_SPLIT_RE.split(text) if c.strip().startswith(prefix)]
    return chunks


def parse_pokerstars_file(path: str) -> List[ParsedHand]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return parse_hand_history(content)


def parse_hand_history(text: str) -> List[ParsedHand]:
    """Parseia hand history de qualquer site suportado (PokerStars, GGPoker, 888poker, PartyPoker)."""
    site = _detect_site(text)
    if site in ("888poker", "partypoker"):
        return _parse_partygaming_hands(text, site)
    id_re = (COIN_ID_RE if site == "coinpoker" else ACR_ID_RE if site == "acr"
             else GG_ID_RE if site == "ggpoker" else PS_ID_RE)
    chunks = _split_hands(text, site)
    return [parse_hand(chunk, id_re, site) for chunk in chunks]


def parse_hand(raw_text: str, id_re: re.Pattern | None = None, site: str = "pokerstars") -> ParsedHand:
    if id_re is None:
        id_re = PS_ID_RE
    is_acr = (site == "acr")

    is_coin = (site == "coinpoker")

    hand_id  = _search(id_re, raw_text)
    tourn_id = _search(COIN_TOURN_RE if is_coin else TOURN_RE, raw_text)
    button   = _search(BUTTON_RE, raw_text, cast=int)

    hero_name  = None
    hero_cards = None
    m = HERO_DEALT_RE.search(raw_text)
    if m:
        hero_name  = m.group(1).strip()
        hero_cards = m.group(2).replace(" ", "")

    sb = bb = None
    # CoinPoker: blinds "(50/100/15)" = sb/bb/ante com BARRAS (o SB_RE espera ante aninhado
    # "(sb/bb(ante))" → não casaria → bb=None → potBb/stack em FICHAS → nós GTO degenerados).
    m2 = COIN_BLINDS_RE.search(raw_text) if is_coin else SB_RE.search(raw_text)
    if m2:
        sb = _pg_num(m2.group(1))   # _pg_num tira vírgula/espaço de milhar (GG: "1,500" → 1500.0)
        bb = _pg_num(m2.group(2))

    players: List[str] = []
    seats: List[dict] = []
    actions: List[ParsedAction] = []
    bounties: dict = {}
    antes: dict = {}
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
        if is_acr:
            # Assento ACR: "Seat N: nome (29150.00)" — sem "in chips", stack decimal, fim na paren.
            # (as linhas de summary "Seat N: nome (button) folded..." não terminam em número → não casam)
            msa = ACR_SEAT_RE.match(line)
            if msa:
                name = msa.group(2).strip()
                players.append(name)
                try:
                    seats.append({'seat': int(msa.group(1)), 'name': name,
                                  'stack': float(msa.group(3).replace(",", ""))})
                except Exception:
                    pass
                continue
        if line.startswith("Seat ") and ":" in line and "(" in line and "in chips" in line:
            # Assento "out of hand" (movido de outra mesa, joga só após o botão):
            # não é jogador desta mão — fora de players/seats/bounties.
            if SEAT_OUT_OF_HAND_RE.search(line):
                continue
            name = line.split(":", 1)[1].split("(", 1)[0].strip()
            players.append(name)
            # seat# + stack inicial — base da mesa fiel (Ghost Table visual)
            try:
                _seat_num  = int(line.split(":", 1)[0].split()[1])
                _stack_str = line.split("(", 1)[1].split("in chips", 1)[0].strip().replace(",", "")
                seats.append({'seat': _seat_num, 'name': name, 'stack': float(_stack_str)})
            except Exception:
                pass
            mb = (SEAT_BOUNTY_PS_RE.match(line) or SEAT_BOUNTY_GG_RE.match(line)
                  or SEAT_BOUNTY_PS2_RE.match(line))
            if mb:
                bounties[mb.group(1).strip()] = float(mb.group(2))
        mw = BOUNTY_WIN_RE.match(line)
        if mw:
            # Track latest bounty value per player (bounty grows as they knock out others)
            winner = mw.group(1).strip()
            amount = float(mw.group(2))
            bounties[winner] = bounties.get(winner, 0.0) + amount
        mant = (ACR_ANTE_RE if is_acr else ANTE_LINE_RE).match(line)
        if mant:
            _an = mant.group("player").strip()
            try:
                antes[_an] = antes.get(_an, 0.0) + float(mant.group("amount").replace(",", ""))
            except Exception:
                pass
            continue   # ante não é ação; não cai no ACTION_LINE_RE
        if is_acr:
            # Ação ACR SEM dois-pontos: "nome raises X to Y" (Y=total), "nome calls X", "nome folds".
            maa = ACR_ACTION_RE.match(line)
            if maa:
                action_str = maa.group("action").lower()
                amt = maa.group("toamt") or maa.group("amount")   # raise → total 'to'; call/bet → valor
                if action_str in ("bets", "raises") and maa.group("allin"):
                    action_str = "all-in"
                actions.append(ParsedAction(
                    player=maa.group("player").strip(), street=street, action=action_str,
                    amount=float(amt.replace(",", "")) if amt else None, raw=line))
            continue   # ACR não usa o ACTION_LINE_RE (PS/GG, com dois-pontos)
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
                amount=float(amount.replace(',', '')) if amount else None,  # GG: 1,109 -> 1109
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
        seats=seats,
        actions=actions,
        raw_text=raw_text,
        bounties=bounties,
        antes=antes,
        is_pko=is_pko,
        showdown_result=_extract_showdown_result(raw_text, hero_name),
    )


# Linha de summary do showdown (PokerStars/GGPoker):
#   "Seat 4: Hero showed [6c Ad] and lost with Ace high"
#   "Seat 3: b75bd8ef (button) showed [8c 8h] and won (780) with three of a kind"
_SD_SUMMARY_RE = re.compile(
    r"^Seat\s+\d+:\s+(?P<player>.+?)\s+(?:\([^)]*\)\s+)?showed\s+\[", re.IGNORECASE
)


def _extract_showdown_result(raw_text: str, hero: str | None) -> Optional[str]:
    """Resultado do hero NO SHOWDOWN: 'won' | 'lost' | None (não chegou/não revelou).

    Lê a seção SUMMARY: a linha do hero com 'showed [...]' + 'and won'/'and lost'.
    None quando o hero não revelou (foldou antes / ganhou sem showdown) — assim o
    denominador do W$SD conta só showdowns de verdade."""
    if not hero:
        return None
    for line in raw_text.splitlines():
        m = _SD_SUMMARY_RE.match(line.strip())
        if m and m.group("player").strip() == hero:
            low = line.lower()
            if "and won" in low or "won (" in low:
                return "won"
            if "and lost" in low or " lost " in low:
                return "lost"
    return None


# ── PartyGaming dialect parser (888poker / PartyPoker) ────────────────────────

def _pg_num(s: str | None) -> float | None:
    """Converte um valor PartyGaming em float. Trata '$', ' USD', vírgula e espaço
    como separador de milhar: '$1,594' → 1594.0, '1 200' → 1200.0, '$0.10 USD' → 0.10."""
    if not s:
        return None
    cleaned = s.replace("$", "").replace("USD", "").replace(",", "").replace(" ", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _pg_cards(s: str) -> List[str]:
    """Normaliza cartas entre colchetes: '8c, Qs' ou '3h Js' → ['8c', '5s']."""
    return [c for c in s.replace(",", " ").split() if c]


def _parse_partygaming_hands(text: str, site: str) -> List[ParsedHand]:
    chunks = [c.strip() for c in PG_SPLIT_RE.split(text)
              if "Hand History for Game" in c]
    return [_parse_partygaming_hand(c, site) for c in chunks]


def _parse_partygaming_hand(raw_text: str, site: str) -> ParsedHand:
    hand_id = _search(PG_ID_RE, raw_text)

    tourn_id = None
    mt = PG_TOURN_RE.search(raw_text)
    if mt:
        tourn_id = mt.group(1) or mt.group(2)

    button = _search(PG_BUTTON_RE, raw_text, cast=int)

    hero_name = hero_cards = None
    md = PG_DEALT_RE.search(raw_text)
    if md:
        hero_name = md.group(1).strip()
        hero_cards = "".join(_pg_cards(md.group(2)))

    sb = bb = None
    mb = (PG_BLINDS_AB_RE.search(raw_text)
          or PG_BLINDS_P_RE.search(raw_text)
          or PG_BLINDS_DOLLAR_RE.search(raw_text))
    if mb:
        sb = _pg_num(mb.group(1))
        bb = _pg_num(mb.group(2))

    players: List[str] = []
    actions: List[ParsedAction] = []
    street = "preflop"
    board: List[str] = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Streets — board só traz a(s) carta(s) nova(s), então acumulamos.
        low = line.lower()
        if low.startswith("** dealing flop **"):
            street = "flop"
            board = _extract_board(line)
            continue
        if low.startswith("** dealing turn **"):
            street = "turn"
            board = board + _extract_board(line)
            continue
        if low.startswith("** dealing river **"):
            street = "river"
            board = board + _extract_board(line)
            continue

        ms = PG_SEAT_RE.match(line)
        if ms:
            players.append(ms.group(2).strip())
            continue

        # All-in tem sintaxe própria; tentar antes das ações normais.
        mai = PG_ALLIN_RE.match(line)
        if mai:
            actions.append(ParsedAction(
                player=mai.group("player").strip(),
                street=street,
                action="all-in",
                amount=_pg_num(mai.group("amount")),
                raw=line,
            ))
            continue

        ma = PG_ACTION_RE.match(line)
        if ma:
            action_str = ma.group("action").lower()
            # "raises [X] and is all-in" → all-in (variante defensiva)
            if action_str in ("bets", "raises") and "all-in" in low:
                action_str = "all-in"
            actions.append(ParsedAction(
                player=ma.group("player").strip(),
                street=street,
                action=action_str,
                amount=_pg_num(ma.group("amount")),
                raw=line,
            ))

    # PKO: o formato PartyGaming das amostras não traz bounty por assento;
    # detecta só por palavra-chave no header (knockout/bounty/PKO).
    is_pko = bool(PKO_KEYWORD_RE.search(raw_text[:300]))

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
        bounties={},
        is_pko=is_pko,
    )


def parse_acr_results(content: str) -> Optional[dict]:
    """Parseia o arquivo de RESULTADOS do ACR/WPN (Tournament Summary '.ots', JSON): resultado +
    premiação por jogador (o HH ACR é só chips, sem prize). Devolve
    {tournament_id, prize_pool, player_count, currency, finishes:[{player, place, prize}]} ou None
    se não for um arquivo de resultados WPN válido. Complementa a premiação do torneio no import."""
    import json
    try:
        data = json.loads(content)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    tn = str(data.get('tournament_number') or '')
    finishes_raw = data.get('tournament_finishes_and_winnings')
    if not tn or not isinstance(finishes_raw, list):
        return None
    m = re.search(r'(\d+)', tn)                 # "T#35409697" → "35409697"
    if not m:
        return None
    finishes = []
    for f in finishes_raw:
        if not isinstance(f, dict) or not f.get('player_name'):
            continue
        try:
            place = int(f['finish_position']) if f.get('finish_position') is not None else None
        except Exception:
            place = None
        prize = 0.0
        for k in ('prize', 'ticket_value'):     # ticket conta como prêmio recebido
            try:
                prize += float(f.get(k) or 0)
            except Exception:
                pass
        finishes.append({'player': str(f['player_name']).strip(), 'place': place,
                         'prize': round(prize, 2)})
    return {
        'tournament_id': m.group(1),
        'prize_pool':    data.get('prize_pool'),
        'player_count':  data.get('player_count'),
        'currency':      data.get('currency'),
        'finishes':      finishes,
    }


_PS_SUMMARY_HEADER_RE = re.compile(r'PokerStars\s+Tournament\s+#(\d+)', re.IGNORECASE)
_PS_PLAYERS_RE        = re.compile(r'^\s*(\d+)\s+players\b', re.IGNORECASE | re.MULTILINE)
_PS_POOL_RE           = re.compile(r'Total\s+Prize\s+Pool:\s*\$?([\d.,]+)', re.IGNORECASE)
_PS_BUYIN_RE          = re.compile(r'Buy-In:\s*([^\n]+)', re.IGNORECASE)
_PS_STARTED_RE        = re.compile(r'Tournament\s+started\s+(\d{4})/(\d{2})/(\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})', re.IGNORECASE)
_PS_FINISHED_RE       = re.compile(r'You\s+finished\s+in\s+(\d+)\s*(?:st|nd|rd|th)\s+place', re.IGNORECASE)
# linha de colocação: "  37: phpro (Brazil), " ou "  1: Winner (X), $30.00"
_PS_PLACE_RE          = re.compile(r'^\s*(\d+):\s*(.+?)\s*\(([^)]*)\)\s*,?\s*(.*)$')
_MONEY_RE             = re.compile(r'\$([\d.,]+)')


def _money(s):
    try:
        return float(str(s).replace(',', ''))
    except Exception:
        return None


def parse_pokerstars_summary(content: str) -> Optional[dict]:
    """Parseia o arquivo Tournament Summary (texto) do PokerStars. O HH traz o resultado do hero,
    mas NÃO traz o tamanho do field (nº de jogadores) nem o prize pool — que só existem aqui.
    Devolve {site, tournament_id, player_count, prize_pool, buy_in, rake, started_at, hero_place,
    finishes:[{player, place, prize}]} ou None se não for um summary do PokerStars.

    Distingue de hand history (que também tem 'Tournament #'): o summary tem a contagem de
    jogadores e o prize pool e NÃO tem marcadores de mão ('*** HOLE CARDS ***')."""
    if not content or '*** ' in content:
        return None
    mh = _PS_SUMMARY_HEADER_RE.search(content)
    mp = _PS_PLAYERS_RE.search(content)
    if not mh or not mp:
        return None

    tid = mh.group(1)
    player_count = int(mp.group(1))

    mpool = _PS_POOL_RE.search(content)
    prize_pool = _money(mpool.group(1)) if mpool else None

    # Buy-In: "$0.98/$0.12 USD" → total = 1.10, rake = última parcela. PKO tem 3 parcelas
    # ($prize/$bounty/$rake) — total é a soma de todas.
    buy_in = rake = None
    mb = _PS_BUYIN_RE.search(content)
    if mb:
        parts = [_money(x) for x in _MONEY_RE.findall(mb.group(1))]
        parts = [x for x in parts if x is not None]
        if parts:
            buy_in = round(sum(parts), 2)
            rake = parts[-1]

    started_at = None
    ms = _PS_STARTED_RE.search(content)
    if ms:
        started_at = f"{ms.group(1)}-{ms.group(2)}-{ms.group(3)} " \
                     f"{int(ms.group(4)):02d}:{ms.group(5)}:{ms.group(6)}"

    hero_place = None
    mf = _PS_FINISHED_RE.search(content)
    if mf:
        hero_place = int(mf.group(1))

    finishes = []
    for line in content.splitlines():
        m = _PS_PLACE_RE.match(line)
        if not m:
            continue
        place = int(m.group(1))
        player = m.group(2).strip()
        # nome pode vir com sufixo de re-entrada "[2]" — não faz parte do nick
        player = re.sub(r'\s*\[\d+\]\s*$', '', player).strip()
        tail = m.group(4) or ''
        mm = _MONEY_RE.search(tail)
        prize = _money(mm.group(1)) if mm else 0.0
        finishes.append({'player': player, 'place': place, 'prize': prize})

    return {
        'site':         'pokerstars',
        'tournament_id': tid,
        'player_count':  player_count,
        'prize_pool':    prize_pool,
        'buy_in':        buy_in,
        'rake':          rake,
        'started_at':    started_at,
        'hero_place':    hero_place,
        'finishes':      finishes,
    }


def _extract_board(line: str) -> List[str]:
    """Extrai o board completo de uma linha de street.

    Formato (PokerStars e GGPoker são idênticos):
      FLOP:  *** FLOP ***   [Ah Kd 3c]
      TURN:  *** TURN ***   [Ah Kd 3c] [7s]
      RIVER: *** RIVER ***  [Ah Kd 3c 7s] [9h]
    PartyGaming (888/PartyPoker) usa cartas separadas por vírgula:
      ** Dealing Flop ** [ As, 5c, 9c ]
    """
    matches = BOARD_RE.findall(line)
    if not matches:
        return []
    cards = []
    for group in matches:
        cards.extend(group.replace(",", " ").split())
    return cards


def _search(regex, text, cast=str):
    m = regex.search(text)
    if not m:
        return None
    return cast(m.group(1))


def parse_pokerstars_file_from_text(text: str) -> List[ParsedHand]:
    """Aceita string diretamente — detecta site automaticamente."""
    return parse_hand_history(text)
