"""Tipos de dados do bot."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GtoNode:
    street:        str            # "preflop" | "flop" | "turn" | "river"
    position:      str            # "BTN" | "CO" | "MP" | "UTG" | "SB" | "BB"
    board:         list[str]      # [] no preflop, ex: ["Ah","Kd","2c"] no flop
    hero_hand:     list[str]      # ex: ["As","Ks"]
    hero_stack_bb: float          # stack do hero em big blinds
    gto_action:    str            # "fold" | "call" | "raise" | "jam"
    gto_freq:      float          # frequência GTO (0.0–1.0)
    ev_diff:       Optional[float] = None   # EV diff vs 2ª melhor ação
    source:        str            = 'gto_wizard'

    def to_dict(self) -> dict:
        return {
            'street':        self.street,
            'position':      self.position,
            'board':         self.board,
            'hero_hand':     self.hero_hand,
            'hero_stack_bb': self.hero_stack_bb,
            'gto_action':    self.gto_action,
            'gto_freq':      self.gto_freq,
            'ev_diff':       self.ev_diff,
            'source':        self.source,
        }
