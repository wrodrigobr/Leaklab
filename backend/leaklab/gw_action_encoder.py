"""
gw_action_encoder.py — Converte ParsedHand → notação GW preflop_actions.

Formato GW (visto via HAR):
  Cada elemento da string corresponde a UMA ação tomada em ordem
  cronológica (NÃO uma entry por posição). Separador "-".

Tokens:
  F        fold
  C        call
  X        check (BB free play)
  R{x.y}   raise para x.y bb (último raise da posição, se houver múltiplos)
  RAI      all-in (preferido por GW em vez de R{stack})

Exemplos reais (mão #100000002, 8-max, hero=BB):
  ""                                  → UTG abre (spot inicial)
  "R2.1"                              → UTG abriu 2.1bb; UTG+1 to act
  "R2.1-F"                            → UTG+1 foldou; LJ to act
  ...
  "R2.1-F-F-C-F-C-R11.55"             → SB squeezou; BB to act (multiway 4-way)

Posts de SB/BB/ante NÃO entram na string (são implícitos pelo
depth/stacks). Hero NÃO entra (string é o estado ANTES da decisão).

Limitações conhecidas (não cobertas neste módulo):
  1. Sizing ante-adjusted: GW codifica raises em bb-incluindo-ante (ex
     "raises 2 to 2" → R2.1 quando há ante de 0.13×8). Aqui emitimos
     o valor cru convertido pra bb (R2.0). Pode haver mismatch no
     lookup → GW retorna 404; consumidor deve snap pro sizing válido.
  2. Bug parser PokerStars: "raises 0 to 0" em formatos com ante
     aparece com amount=0 (squeeze real perdido). Encoder propaga o
     valor cru — fix deve ser no parser, não aqui.
"""
from __future__ import annotations

import re
from typing import List, Optional

from .models import ParsedHand, ParsedAction

# "raises X to Y" (PokerStars) → captura o TOTAL Y. GG ("raises to Y") idem.
_RAISE_TO_TOTAL = re.compile(r"\bto\s+([\d.]+)", re.IGNORECASE)

# Ordem canônica do board que o GW exige na URL da API: flop por rank DESCENDENTE,
# desempate de naipe s>h>d>c; turn/river anexados na ordem de distribuição (sem
# re-ordenar). O matcher do servidor (is_target) casa o `board=` EXATO, então enviar
# fora dessa ordem → GW nunca responde → subprocess_timeout.
_RANK_ORDER = {r: i for i, r in enumerate("AKQJT98765432")}
_SUIT_ORDER = {"s": 0, "h": 1, "d": 2, "c": 3}


def gw_board_order(board: list[str]) -> list[str]:
    """Reordena o board pra ordem canônica do GW (flop rank-desc + suit s,h,d,c;
    turn/river preservados). Não muda o hash do engine (que faz sorted())."""
    cards = [str(c).strip() for c in (board or []) if len(str(c).strip()) >= 2]
    flop = sorted(cards[:3],
                  key=lambda c: (_RANK_ORDER.get(c[0].upper(), 99), _SUIT_ORDER.get(c[1].lower(), 9)))
    return flop + cards[3:]


# Posições GW por mesa size (espelha _TABLE_CONFIG no solver_api/server.py)
_GW_POSITIONS: dict[int, list[str]] = {
    2: ["BTN", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["CO", "BTN", "SB", "BB"],
    5: ["HJ", "CO", "BTN", "SB", "BB"],
    6: ["LJ", "HJ", "CO", "BTN", "SB", "BB"],
    7: ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"],
    8: ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"],
    9: ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"],
}


def num_seated_players(hand: ParsedHand) -> int:
    """Conta jogadores efetivamente sentados na mão (linhas 'Seat N:' no
    header, antes de '*** HOLE CARDS ***'). Ignora summary final."""
    n = 0
    for line in hand.raw_text.splitlines():
        if line.startswith("*** HOLE CARDS ***"):
            break
        if line.startswith("Seat ") and ": " in line and "(" in line and "chips" in line:
            n += 1
    if n == 0 and hand.players:
        n = len(hand.players)
    return n


def gw_gametype_for(n_players: int) -> Optional[str]:
    mapping = {
        2: "MTTHUGeneral",
        3: "MTTGeneral_3m",
        4: "MTTGeneral_4m",
        5: "MTTGeneral_5m",
        6: "MTT6mSimple",
        7: "MTTGeneral_7m",
        8: "MTTGeneral_8m",
        9: "MTTGeneralV2",
    }
    return mapping.get(n_players)


def _encode_amount_bb(amount: Optional[float], bb: float) -> str:
    """Formata raise amount em bb com 1 casa decimal (formato GW)."""
    if amount is None or bb <= 0:
        return "0"
    bb_val = amount / bb
    # Formato GW: 1 casa decimal (ex 2.1, 11.55 com 2 quando precisa)
    # GW usa precisão variável (R2.1, R11.55). Mantemos até 2 casas, removendo
    # trailing zero apenas em .X0 → .X.
    s = f"{bb_val:.2f}"
    if s.endswith("0"):
        s = s[:-1]
    if s.endswith("."):
        s = s + "0"  # garante pelo menos 1 casa decimal
    return s


def _action_token(action: ParsedAction, bb: float, hero_stack_before: float) -> Optional[str]:
    """Converte uma ParsedAction preflop em token GW. None pra posts/skip."""
    a = (action.action or "").lower()
    if a in ("posts", "post"):
        return None
    if a in ("folds", "fold"):
        return "F"
    if a in ("checks", "check"):
        return "X"
    if a in ("calls", "call"):
        return "C"
    if a in ("raises", "raise", "bets", "bet"):
        # PokerStars loga 'raises X to Y' onde amount=X (INCREMENTO). O GW raciocina
        # sobre o 'raise to' TOTAL (Y). Lê o 'to Y' do raw quando presente; senão
        # usa amount (bets postflop e GG 'raises to Y' já são totais).
        amt = action.amount
        if a in ("raises", "raise"):
            m = _RAISE_TO_TOTAL.search(action.raw or "")
            if m:
                try:
                    amt = float(m.group(1))
                except ValueError:
                    pass
        return f"R{_encode_amount_bb(amt, bb)}"
    if a in ("all-in", "allin", "shove"):
        # GW codifica all-in como RAI (independente do tamanho)
        return "RAI"
    return None


def encode_preflop_actions(hand: ParsedHand, stop_index: int) -> str:
    """
    Constrói preflop_actions GW pra mão `hand`, considerando o estado ANTES
    da action `hand.actions[stop_index]` (a ação do hero que vai decidir).

    Inclui só ações preflop (street='preflop'), pula posts, e converte cada
    ação numa token (F/C/X/R{x.y}/RAI). Retorna string vazia se hero é
    primeiro a agir (sem ações antes).

    Raises ValueError se stop_index inválido.
    """
    if stop_index < 0 or stop_index > len(hand.actions):
        raise ValueError(f"stop_index {stop_index} fora de range (0..{len(hand.actions)})")

    bb = hand.bb or 1.0
    tokens: List[str] = []

    for i, act in enumerate(hand.actions):
        if i >= stop_index:
            break
        if act.street != "preflop":
            continue
        tok = _action_token(act, bb, hero_stack_before=0.0)
        if tok is None:
            continue
        tokens.append(tok)

    return "-".join(tokens)


def encode_street_actions(hand: ParsedHand, street: str, stop_index: int) -> str:
    """
    Constrói a string de ações GW de UMA street (flop/turn/river) pra mão `hand`,
    considerando o estado ANTES da action `hand.actions[stop_index]` (a decisão do
    hero que vai ser consultada). Mesma tokenização do preflop (X/C/F/R{x.y}/RAI),
    só muda o filtro de street. Retorna '' se ninguém agiu nessa street ainda.

    Usada pra montar flop_actions/turn_actions no fetch postflop via /gw-spot.
    """
    if stop_index < 0 or stop_index > len(hand.actions):
        raise ValueError(f"stop_index {stop_index} fora de range (0..{len(hand.actions)})")

    bb = hand.bb or 1.0
    tokens: List[str] = []
    for i, act in enumerate(hand.actions):
        if i >= stop_index:
            break
        if act.street != street:
            continue
        tok = _action_token(act, bb, hero_stack_before=0.0)
        if tok is None:
            continue
        tokens.append(tok)
    return "-".join(tokens)


def find_hero_preflop_decisions(hand: ParsedHand) -> List[int]:
    """Retorna lista de indices em hand.actions onde o hero toma decisão preflop."""
    if not hand.hero:
        return []
    out = []
    for i, a in enumerate(hand.actions):
        if a.street == "preflop" and a.player == hand.hero:
            out.append(i)
    return out


def classify_multiway(preflop_actions: str) -> dict:
    """
    Classifica spot preflop baseado nos tokens já emitidos.

    Retorna {scenario, n_raises, n_calls, n_folds, has_callers_before_raise,
             is_multiway_with_callers}.

    Cenários esperáveis:
      rfi             — hero é primeiro a agir (string vazia)
      vs_rfi          — 1 raise antes do hero, sem callers
      vs_3bet         — 2 raises, sem callers
      vs_4bet         — 3 raises, sem callers
      squeeze         — 1 raise + 1+ calls, hero ainda não agiu
      vs_squeeze      — 1 raise + 1+ calls + 1 raise (squeeze), hero ainda não agiu
      multiway        — qualquer outro multiway com callers
    """
    if not preflop_actions:
        return {"scenario": "rfi", "n_raises": 0, "n_calls": 0, "n_folds": 0,
                "has_callers_before_raise": False, "is_multiway_with_callers": False}

    tokens = preflop_actions.split("-")
    n_raises = sum(1 for t in tokens if t.startswith("R") and t != "RAI")
    n_allin  = sum(1 for t in tokens if t == "RAI")
    n_calls  = sum(1 for t in tokens if t == "C")
    n_folds  = sum(1 for t in tokens if t == "F")

    # Posição relativa do primeiro raise vs primeiro call
    first_raise_idx = next((i for i, t in enumerate(tokens) if t.startswith("R")), -1)
    first_call_idx  = next((i for i, t in enumerate(tokens) if t == "C"),         -1)

    is_multi = n_calls > 0

    if n_raises == 0 and n_allin == 0 and n_calls == 0:
        scenario = "rfi"  # só folds antes do hero
    elif n_raises + n_allin == 1 and n_calls == 0:
        scenario = "vs_rfi"
    elif n_raises + n_allin == 2 and n_calls == 0:
        scenario = "vs_3bet"
    elif n_raises + n_allin == 3 and n_calls == 0:
        scenario = "vs_4bet"
    elif n_raises + n_allin == 1 and n_calls >= 1:
        scenario = "squeeze"
    elif n_raises + n_allin == 2 and n_calls >= 1:
        scenario = "vs_squeeze"
    elif n_raises + n_allin >= 4:
        scenario = "5bet_or_higher"
    else:
        scenario = "multiway"

    return {
        "scenario":                  scenario,
        "n_raises":                  n_raises + n_allin,
        "n_calls":                   n_calls,
        "n_folds":                   n_folds,
        "has_callers_before_raise":  first_call_idx >= 0 and first_call_idx < first_raise_idx if first_raise_idx >= 0 else False,
        "is_multiway_with_callers":  is_multi and (n_raises + n_allin) >= 1,
    }
