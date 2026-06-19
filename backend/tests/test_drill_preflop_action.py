"""Regressão: abrir preflop é RAISE (não "bet") no grading do drill.

Enfrentando só as blinds (facing=0), abrir o pote é um RAISE (raisa por cima do BB).
A conversão raise→bet só vale POSTFLOP (sem blinds em frente). Bug histórico: o open
preflop virava "bet" → marcava o "raise" do usuário como errado.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.app as app

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


_base = dict(position='CO', board=None, stack_bb=40, hero_cards='AhKh', pot_size=1.5,
             gto_action='raise', best_action='raise', gto_label='gto_correct')

check(app._resolve_best_action_from_node(dict(_base, street='preflop', facing_bet=0)) == 'raise',
      "preflop open (facing=0) deve ser RAISE")
check(app._resolve_best_action_from_node(
          dict(_base, street='flop', facing_bet=0, board='["Th","4c","2s"]')) == 'bet',
      "postflop sem aposta (facing=0) deve ser BET")
check(app._resolve_best_action_from_node(dict(_base, street='preflop', facing_bet=3)) == 'raise',
      "preflop vs RFI (facing>0) deve ser RAISE")

print(f"\nTotal: {passed + failed} Passed: {passed} Failed: {failed}")
sys.exit(1 if failed else 0)
