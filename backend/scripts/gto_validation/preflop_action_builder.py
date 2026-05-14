"""
Constrói a string preflop_actions no formato do GTO Wizard a partir dos dados do nosso DB.

Formato GTO Wizard:
  R{bb}  = raise para X big blinds
  C      = call
  F      = fold
  X      = check
  B{bb}  = bet (postflop)
  Ações separadas por '-', em ordem de ação na mesa.

Para spots de flop, a sequência preflop é necessária para contextualizar o spot.
O GTO Wizard precisa saber que chegamos ao flop com esse histórico.

Mapeamentos de posição (8-max MTT):
  UTG, UTG+1 (ou LJ), HJ, CO, BTN, SB, BB

Cenários mais comuns extraídos do nosso DB:
  1. BTN abriu, BB chamou  → R2-F-F-F-F-C  (dependendo do n° de jogadores restantes)
  2. CO abriu, BB chamou   → F-F-R2-F-F-C
  3. SB abriu, BB chamou   → F-F-F-F-F-R2-C
  4. BB vs limper único    → F-F-F-F-F-C-X  (com check da BB)
"""
from __future__ import annotations

# Ordem de ação preflop 8-max (sem postagem de blinds):
# UTG, UTG+1/LJ, HJ, CO, BTN, SB, BB
POSITIONS_8MAX = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POSITION_INDEX_8MAX = {p: i for i, p in enumerate(POSITIONS_8MAX)}

# Open raise size padrão em MTT (2bb ou 2.5bb dependendo do stack)
DEFAULT_OPEN_SIZE = 2.0
DEFAULT_3BET_SIZE = 6.5


def build_preflop_actions_simple(
    hero_position: str,
    villain_position: str,
    pot_type: str = "single_raised",
    hero_open_size: float = DEFAULT_OPEN_SIZE,
    hero_3bet_size: float = DEFAULT_3BET_SIZE,
    n_players: int = 8,
) -> str:
    """
    Gera preflop_actions para os cenários mais comuns:
    - single_raised: hero abre, villain chama (HU no flop)
    - three_bet: villain abre, hero 3-bets, villain chama
    - limp: villain limpa, hero na BB checa

    Retorna string no formato GTO Wizard (ex: 'R2-F-F-F-F-C').
    """
    positions = POSITIONS_8MAX[:n_players] if n_players <= 8 else POSITIONS_8MAX

    hero_idx = POSITION_INDEX_8MAX.get(hero_position, -1)
    villain_idx = POSITION_INDEX_8MAX.get(villain_position, -1)

    if hero_idx == -1 or villain_idx == -1:
        return ""

    if pot_type == "single_raised":
        # IP abre, OOP chama (assumindo hero é o opener, villain na BB)
        actions = []
        opener_idx = min(hero_idx, villain_idx)
        caller_idx = max(hero_idx, villain_idx)
        for i, pos in enumerate(positions):
            if i < opener_idx:
                actions.append("F")
            elif i == opener_idx:
                actions.append(f"R{hero_open_size}")
            elif i < caller_idx:
                actions.append("F")
            elif i == caller_idx:
                actions.append("C")
            # BB fecha a ação se não houver mais jogadores
        return "-".join(actions)

    elif pot_type == "three_bet":
        # villain abre UTG/CO/BTN, hero 3-bets, villain chama
        actions = []
        for i, pos in enumerate(positions):
            if i < villain_idx:
                actions.append("F")
            elif i == villain_idx:
                actions.append(f"R{hero_open_size}")
            elif i < hero_idx:
                actions.append("F")
            elif i == hero_idx:
                actions.append(f"R{hero_3bet_size}")
            else:
                # Demais folds, opener chama
                pass
        actions.append("C")  # villain chama o 3-bet
        return "-".join(actions)

    elif pot_type == "limp":
        # villain limpa, hero na BB checa
        actions = []
        for i, pos in enumerate(positions):
            if i < villain_idx:
                actions.append("F")
            elif i == villain_idx:
                actions.append("C")  # limp = call do BB
            elif i < len(positions) - 1:
                actions.append("F")
            else:
                actions.append("X")  # BB checa
        return "-".join(actions)

    return ""


# Cenários pré-configurados mais comuns no nosso DB
COMMON_SCENARIOS = {
    "BTN_vs_BB_open": {
        "gametype": "MTTGeneral_8m",
        "preflop_actions": "F-F-F-F-R2-F-C",  # todos folds até BTN abre, SB fold, BB call
        "description": "BTN open 2bb, BB call (HU flop)",
        "hero_position_postflop": "IP",
    },
    "CO_vs_BB_open": {
        "gametype": "MTTGeneral_8m",
        "preflop_actions": "F-F-F-R2-F-F-C",  # UTG/LJ/HJ fold, CO open, BTN/SB fold, BB call
        "description": "CO open 2bb, BB call (HU flop)",
        "hero_position_postflop": "IP",
    },
    "SB_vs_BB_open": {
        "gametype": "MTTGeneral_8m",
        "preflop_actions": "F-F-F-F-F-R2-C",  # todos fold até SB, BB call
        "description": "SB open 2bb, BB call (HU flop)",
        "hero_position_postflop": "IP",
    },
    "BTN_vs_BB_3bet": {
        "gametype": "MTTGeneral_8m",
        "preflop_actions": "F-F-F-F-R2-F-R6.5-C",  # BTN open, BB 3-bet, BTN call
        "description": "BTN open 2bb, BB 3-bet 6.5bb, BTN call (3-bet pot HU)",
        "hero_position_postflop": "OOP",
    },
    "BB_vs_BTN_limp": {
        "gametype": "MTTGeneral_8m",
        "preflop_actions": "F-F-F-F-C-F-X",  # BTN limp, SB fold, BB check
        "description": "BTN limp, BB check (limped pot HU)",
        "hero_position_postflop": "OOP",
    },
}


def get_scenario(position: str, villain_position: str, facing_bb: float) -> dict:
    """
    Tenta mapear um spot do nosso DB para um cenário pré-configurado.
    Retorna o cenário ou um fallback genérico.
    """
    # Identify common patterns
    pair = (position, villain_position)

    if pair == ("BTN", "BB") and facing_bb > 0:
        return COMMON_SCENARIOS["BTN_vs_BB_open"]
    if pair == ("BB", "BTN") and facing_bb > 0:
        return COMMON_SCENARIOS["BTN_vs_BB_open"]  # mesmo spot, perspectiva invertida
    if pair == ("CO", "BB") and facing_bb > 0:
        return COMMON_SCENARIOS["CO_vs_BB_open"]
    if pair == ("BB", "CO") and facing_bb > 0:
        return COMMON_SCENARIOS["CO_vs_BB_open"]
    if pair in [("SB", "BB"), ("BB", "SB")] and facing_bb > 0:
        return COMMON_SCENARIOS["SB_vs_BB_open"]
    if pair == ("BB", "BTN") and facing_bb == 0:
        return COMMON_SCENARIOS["BB_vs_BTN_limp"]

    return {}
