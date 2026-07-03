from __future__ import annotations
from .models import HandState, SpotClassification, RangeEvaluation


def evaluate_preflop_range(state: HandState, spot: SpotClassification) -> RangeEvaluation:
    cards = state.hero_cards or ""
    zone = _classify_range_zone(cards)
    facing_size = float(getattr(state, 'facing_size', 0) or 0)
    stack_bb    = float(getattr(state, 'effective_stack_bb', 0) or getattr(spot, 'effective_stack_bb', 0) or 0)
    # Pote 3-bet/squeeze enfrentado a frio (≥2 raises de villains e hero não foi agressor):
    # a lógica padrão "borderline → call (set-mine)" é p/ enfrentar UM 3-bet HU, não p/
    # cold-call de squeeze OOP. Aqui só premiums (core) seguem; borderline folda.
    md = getattr(state, 'metadata', {}) or {}
    faces_3bet = (int(md.get('preflop_raises_faced', 0) or 0) >= 2
                  and not bool(md.get('hero_was_aggressor', False)))
    recommended = _recommended_action(cards, state.position, facing_size, stack_bb=stack_bb,
                                      faces_3bet=faces_3bet)
    alternatives = []
    if zone == "borderline_range":
        base_alts = ["call", "fold"] if recommended == "call" else ["raise", "fold"]
        # BB pode check grátis — fold não é alternativa válida sem aposta
        alternatives = [a for a in base_alts if not (a == "fold" and facing_size == 0 and state.position == "BB")]
    elif zone == "core_range":
        alternatives = [recommended]
    return RangeEvaluation(
        recommended_primary_action=recommended,
        alternative_actions=list(dict.fromkeys(alternatives)),
        range_zone=zone,
        confidence=0.72,
        mix_weight=0.25 if zone == "borderline_range" else 0.05,
    )


def _classify_range_zone(cards: str) -> str:
    if len(cards) < 4:
        return "outside_range"
    r1, s1, r2, s2 = cards[0], cards[1], cards[2], cards[3]
    pair = r1 == r2
    suited = s1 == s2
    broadway = r1 in "TJQKA" and r2 in "TJQKA"
    if pair and r1 in "89TJQKA":
        return "core_range"
    if pair and r1 in "4567":
        return "borderline_range"
    if broadway and suited:
        return "core_range"
    if broadway or suited:
        return "borderline_range"
    return "outside_range"


def _is_squeeze_premium(cards: str) -> bool:
    """Mãos que seguem (4-bet/call) vs um squeeze a frio: QQ+ e AK. Tudo abaixo
    (JJ/TT/AQs/ATs/KQs/pares médios) folda a frio sem cobertura GTO — 4-bet light
    de squeeze é exatamente o erro que marcava o fold do hero como erro grave."""
    if len(cards) < 4:
        return False
    r1, r2 = cards[0], cards[2]
    if r1 == r2 and r1 in "QKA":          # QQ, KK, AA
        return True
    return {r1, r2} == {"A", "K"}          # AKs / AKo


def _recommended_action(cards: str, position: str, facing_size: float = 0.0,
                         stack_bb: float = 0.0, faces_3bet: bool = False) -> str:
    """Recomenda ação preflop usando classificação por zona + posição + facing_size + stack.

    Regras críticas:
    - Push/Fold zone (stack ≤ 12bb preflop): apenas JAM ou FOLD. Nada de call/limp.
    - Facing >= 3bb (vs 3-bet): borderline = call (set-mine); core IP = raise; core OOP = call.
    - RFI: core = raise; borderline = raise (não-blind) ou call (blind); fora = fold.
    """
    zone = _classify_range_zone(cards)
    is_pair = len(cards) >= 4 and cards[0] == cards[2]
    r1      = cards[0] if len(cards) >= 1 else ""

    # Push/Fold zone: stack curto → decisão binária jam ou fold
    # Threshold 14bb cobre 10-14bb range padrão MTT (push/fold standard)
    if stack_bb > 0 and stack_bb <= 14.0:
        # BB num pote limpado (facing 0) vê o flop DE GRAÇA, mesmo curto: NUNCA folda uma opção
        # livre. Core isola com jam (fold equity + valor); o resto vê o flop (check).
        if position == "BB" and facing_size == 0:
            return "jam" if zone == "core_range" else "check"
        if zone == "core_range":
            return "jam"
        if zone == "borderline_range":
            # Borderline em PF: jam de posições mid-late (LJ+), fold de early.
            # SB/BTN/CO jamming wide range; UTG/UTG+1 mais tight.
            if position in {"BTN", "SB", "CO", "HJ", "LJ", "MP", "MP1", "MP2"}:
                return "jam"
            return "fold"
        # outside_range em PF zone → fold
        return "fold"

    # Facing > 2bb (vs raise, iso-over-limp, ou 3-bet): tighter logic
    # — set-mine / call em vez de 4-bet. Threshold 2bb cobre iso 2.5x sobre limpers
    # (era 3bb antes, mas iso típicos são 2-2.5x e estavam fora do critério).
    if facing_size >= 2.0:
        if zone == "core_range":
            # Squeeze/3-bet a FRIO (cold, hero não foi agressor): 'core_range' agrega
            # 88–AA + todo broadway suited, mas vs um squeeze só PREMIUM (QQ+/AK) segue
            # — 4-betar ATs/KQs/99 light a frio é o erro que marcávamos o fold do hero
            # como clear_mistake (ATs vs squeeze do review #27). Não-premium folda.
            if faces_3bet and not _is_squeeze_premium(cards):
                return "fold"
            # Pares 88-AA + broadway suited → call ou 4-bet conforme posição
            # Em IP, premium pode 4-bet; OOP prefere call
            return "raise" if position not in {"BB", "SB", "UTG", "UTG+1", "UTG1"} else "call"
        if zone == "borderline_range":
            # Borderline facing 3-bet HU: call (set-mine, implied odds). MAS num
            # pote 3-bet/squeeze enfrentado a frio (cold), borderline não tem preço
            # — folda (evita "call 45s vs squeeze").
            return "fold" if faces_3bet else "call"
        return "fold"

    # Sem facing ou facing pequeno (steal/limp): lógica RFI/vs_limp.
    if zone == "core_range":
        # Mão forte ISO-raiseia por valor — inclusive na BB sobre um limp. AKs/pares grandes
        # na BB NÃO dão só check/call num limp; iso-raise é a jogada padrão (era o bug: BB core
        # recomendava "call", marcando o iso de AKs como erro).
        return "raise"
    if zone == "borderline_range":
        # BB vê o flop de graça num pote limpado (check, não "call" — não há aposta a pagar);
        # SB completa (call); demais posições abrem (RFI = raise). Um iso light da BB fica como
        # ALTERNATIVA aceitável (zona borderline), não erro.
        if position == "BB":
            return "check"
        return "call" if position == "SB" else "raise"
    # Mão fraca: BB pode check grátis; demais posições estão escolhendo não abrir — fold é correto.
    if facing_size == 0 and position == "BB":
        return "check"
    return "fold"
