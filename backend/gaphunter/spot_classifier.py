from __future__ import annotations
from .models import HandState, SpotClassification


def classify_spot(state: HandState) -> SpotClassification:
    spot_type = "unknown"
    tags = []
    if state.street == "preflop":
        if state.player_action == "raise":
            spot_type = "preflop_open_or_iso"
        elif state.player_action == "call":
            spot_type = "preflop_flat"
        elif state.player_action == "fold":
            spot_type = "preflop_fold"
        elif state.player_action == "jam":
            spot_type = "preflop_jam"
    else:
        if state.player_action == "bet":
            spot_type = f"{state.street}_bet"
        elif state.player_action == "raise":
            spot_type = f"{state.street}_raise"
        elif state.player_action == "call":
            spot_type = f"{state.street}_call"
        elif state.player_action == "fold":
            spot_type = f"{state.street}_fold"
        elif state.player_action == "check":
            spot_type = f"{state.street}_check"

    if state.is_multiway:
        tags.append("multiway")
    if not state.is_in_position:
        tags.append("oop")
    return SpotClassification(
        spot_type=spot_type,
        street=state.street,
        position=state.position,
        villain_position=state.villain_position,
        tags=tags,
    )
