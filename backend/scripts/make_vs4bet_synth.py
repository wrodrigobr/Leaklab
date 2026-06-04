"""Cria torneio sintético com mãos de vs_4bet (hero CO 3beta, UTG 4beta, hero
responde @50bb) para a varredura do card. Valida e insere para o user 13.
Uso: python -m scripts.make_vs4bet_synth [--insert]"""
import sys
sys.path.insert(0, '.')
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type

TID = 'VS4BSWEEP1'
HANDS = [
    ('V4B001', 'Ac Ad'),  # AA 5bet-jam -> major_leak (GTO CALA AA vs 4bet deep)
    ('V4B002', 'Ah Kd'),  # AKo 5bet-jam -> correct
    ('V4B003', 'As Ks'),  # AKs 5bet-jam -> acceptable (jam é minoria 13%)
]

def make_hand(hid, hero_cards):
    seats = "\n".join(f"Seat {i}: P{i} (5000 in chips)" for i in range(1, 8))
    return f"""Poker Hand #{hid}: Tournament #{TID}, Synthetic vs4bet Hold'em No Limit - Level1(50/100) - 2026/06/04 12:00:00
Table 'V4B' 9-max Seat #9 is the button
{seats}
Seat 8: Hero (5000 in chips)
Seat 9: P9 (5000 in chips)
P1: posts small blind 50
P2: posts big blind 100
*** HOLE CARDS ***
Dealt to Hero [{hero_cards}]
P3: raises 120 to 220
P4: folds
P5: folds
P6: folds
P7: folds
Hero: raises 380 to 600
P9: folds
P1: folds
P2: folds
P3: raises 700 to 1300
Hero: raises 3700 to 5000 and is all-in
P3: folds
Uncalled bet (3700) returned to Hero
Hero collected 2700 from pot
*** SUMMARY ***
Total pot 2700 | Rake 0
Board []
Seat 8: Hero collected (2700)
"""

raw_full = "\n\n".join(make_hand(hid, hc) for hid, hc in HANDS)

hands = parse_hand_history(raw_full)
print(f"parseou {len(hands)} maos")
for h in hands:
    for di in build_decision_inputs_for_hand(h):
        if (di.get('street') or '').lower() != 'preflop':
            continue
        sp = di.get('spot', {}); act = (di.get('player_action') or '').lower()
        if act not in ('raise', 'shove', 'jam', 'allin'):
            continue
        # só a decisão vs_4bet (hero agressor enfrentando 2+ raises)
        if not (sp.get('heroWasAggressor') and int(sp.get('preflopRaisesFaced') or 0) >= 2):
            continue
        ht = hand_to_type(di.get('hero_cards') or [])
        r = analyze_preflop(position=sp.get('position', ''), hero_hand_type=ht,
                            stack_bb=float(sp.get('effectiveStackBb') or 0), action_taken=act,
                            facing_size=float(sp.get('facingSize') or 0),
                            vs_position=sp.get('villainPosition') or '', is_3bet_pot=False,
                            n_players=sp.get('nPlayers'),
                            facing_raises=int(sp.get('preflopRaisesFaced') or 0),
                            hero_was_aggressor=True, facing_limp=False)
        print(f"  hand={h.hand_id} {ht} pos={sp.get('position')} 4bettor={sp.get('villainPosition')} "
              f"raises={sp.get('preflopRaisesFaced')} stk={round(float(sp.get('effectiveStackBb') or 0),1)} "
              f"act={act} -> scen={r.get('scenario')} avail={r.get('available')} q={r.get('action_quality')}")

if '--insert' in sys.argv:
    from database.repositories import save_tournament
    metrics = {'label_pct': {}, 'hands_count': len(hands), 'decisions_count': 0,
               'avg_score': 0, 'standard_pct': 0, 'marginal_pct': 0, 'small_pct': 0, 'clear_pct': 0}
    tdb = save_tournament(user_id=13, tournament_id=TID, hero='Hero', metrics=metrics,
                          site='ggpoker', raw_text=raw_full, tournament_name='Synthetic vs4bet')
    print(f"INSERIDO tournament_id={TID} db_id={tdb} (user 13)")
    print("hand_ids:", [hid for hid, _ in HANDS])
