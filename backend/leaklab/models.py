from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ParsedAction:
    player: str
    street: str
    action: str
    amount: Optional[float] = None
    raw: str = ""


@dataclass
class ParsedHand:
    hand_id: str
    tournament_id: Optional[str] = None
    hero: Optional[str] = None
    button_seat: Optional[int] = None
    sb: Optional[float] = None
    bb: Optional[float] = None
    hero_cards: Optional[str] = None
    board: List[str] = field(default_factory=list)
    players: List[str] = field(default_factory=list)
    actions: List[ParsedAction] = field(default_factory=list)
    raw_text: str = ""
    bounties: Dict[str, float] = field(default_factory=dict)   # player -> bounty value
    is_pko:   bool = False                                     # PKO/Bounty tournament flag


@dataclass
class HandState:
    hand_id: str
    street: str
    hero: str
    hero_cards: Optional[str]
    board: List[str]
    player_action: str
    pot_size: float
    facing_size: float
    effective_stack_bb: float
    position: str
    villain_position: Optional[str]
    is_in_position: bool
    is_multiway: bool
    actions: List[ParsedAction]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpotClassification:
    spot_type: str
    street: str
    position: str
    villain_position: Optional[str]
    tags: List[str] = field(default_factory=list)


@dataclass
class MathSnapshot:
    pot_odds_equity: Optional[float]
    estimated_hand_equity: Optional[float]
    implied_odds_factor: Optional[float]
    reverse_implied_odds_factor: Optional[float]
    pressure_score: Optional[float]


@dataclass
class RangeEvaluation:
    recommended_primary_action: str
    alternative_actions: List[str]
    range_zone: str
    confidence: float = 0.7
    mix_weight: Optional[float] = None


@dataclass
class DecisionInput:
    hand_id: str
    street: str
    player_action: str
    spot: Dict[str, Any]
    hand_profile: Dict[str, Any]
    math: Dict[str, Any]
    range_evaluation: Dict[str, Any]
    context: Dict[str, Any]
