"""Cria torneio sintético com mãos de SQUEEZE (hero BTN squeeza vs UTG open +
UTG+1 call @14bb) para a varredura do card. Valida posições/cobertura e insere
para o user 13. Uso: python -m scripts._make_squeeze_synth [--insert]"""
import sys, re
sys.path.insert(0, '.')
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type

TID = 'SQZSWEEP1'
HANDS = [
    ('SQZ001', 'As Ks'),  # AKs -> shove correto
    ('SQZ002', 'Ac Ad'),  # AA  -> shove major_leak (GTO faz raise, nao jam)
    ('SQZ003', 'Kc Jd'),  # KJo -> shove major_leak (fold 100%)
]

def make_hand(hid, hero_cards):
    seats = "\n".join(f"Seat {i}: P{i} (2000 in chips)" for i in range(1, 9))
    return f"""Poker Hand #{hid}: Tournament #{TID}, Synthetic Squeeze Hold'em No Limit - Level1(50/100) - 2026/06/03 12:00:00
Table 'SQZ' 9-max Seat #9 is the button
{seats}
Seat 9: Hero (1400 in chips)
P1: posts small blind 50
P2: posts big blind 100
*** HOLE CARDS ***
Dealt to Hero [{hero_cards}]
P3: raises 120 to 220
P4: calls 220
P5: folds
P6: folds
P7: folds
P8: folds
Hero: raises 1180 to 1400 and is all-in
P1: folds
P2: folds
P3: folds
P4: folds
Uncalled bet (1180) returned to Hero
Hero collected 690 from pot
*** SUMMARY ***
Total pot 690 | Rake 0
Board []
Seat 9: Hero (button) collected (690)
"""

raw_full = "\n\n".join(make_hand(hid, hc) for hid, hc in HANDS)

# ── valida parse + posições + cobertura ──
hands = parse_hand_history(raw_full)
print(f"parseou {len(hands)} maos")
for h in hands:
    for di in build_decision_inputs_for_hand(h):
        if (di.get('street') or '').lower() != 'preflop':
            continue
        sp = di.get('spot', {}); act = (di.get('player_action') or '').lower()
        if act not in ('raise', 'shove', 'jam', 'allin'):
            continue
        ht = hand_to_type(di.get('hero_cards') or [])
        r = analyze_preflop(position=sp.get('position', ''), hero_hand_type=ht,
                            stack_bb=float(sp.get('effectiveStackBb') or 0), action_taken=act,
                            facing_size=float(sp.get('facingSize') or 0),
                            vs_position=sp.get('villainPosition') or '', is_3bet_pot=True,
                            n_players=sp.get('nPlayers'),
                            facing_raises=int(sp.get('preflopRaisesFaced') or 0),
                            hero_was_aggressor=bool(sp.get('heroWasAggressor')),
                            facing_limp=False, caller_position=sp.get('callerPosition', ''))
        print(f"  hand={h.hand_id} {ht} pos={sp.get('position')} opener={sp.get('villainPosition')} "
              f"caller={sp.get('callerPosition')} stk={round(float(sp.get('effectiveStackBb') or 0),1)} "
              f"act={act} -> scen={r.get('scenario')} avail={r.get('available')} q={r.get('action_quality')}")

if '--insert' in sys.argv:
    from database.repositories import save_tournament
    metrics = {'label_pct': {}, 'hands_count': len(hands), 'decisions_count': 0,
               'avg_score': 0, 'standard_pct': 0, 'marginal_pct': 0, 'small_pct': 0, 'clear_pct': 0}
    tdb = save_tournament(user_id=13, tournament_id=TID, hero='Hero', metrics=metrics,
                          site='ggpoker', raw_text=raw_full, tournament_name='Synthetic Squeeze')
    print(f"INSERIDO tournament_id={TID} db_id={tdb} (user 13)")
    print("hand_ids:", [hid for hid, _ in HANDS])
