"""test_leak_trainer.py — Leak Trainer (spots GTO canônicos adaptativos).

Valida geração (spots cobertos), grading (formato DrillSubmitResult, fold-100%=correto,
ações dominadas=erro) e a régua adaptativa. Tudo via analyze_preflop (dado pré-capturado).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import leaklab.leak_trainer as lt

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {msg}")


def _rfi_spot(hand, pos='UTG', stack=50):
    return {'scenario': 'rfi', 'position': pos, 'vs_position': '', 'stack_bb': stack,
            'facing_size': 0.0, 'is_3bet_pot': False, 'hero_was_aggressor': False,
            'facing_raises': 0, 'hand': hand}


# ── Geração: spots cobertos (available + cenário bate) ───────────────────────────
random.seed(7)
for cat in lt._fundamentals():
    spot = lt.generate_canonical_spot(cat)
    check(spot is not None, f"fundamentals {cat['key']} gera spot coberto")
    if spot:
        check(spot['spot']['scenario'] == 'rfi', f"{cat['key']} cenário rfi")
        check(spot['street'] == 'preflop' and spot['hero_cards'], f"{cat['key']} tem cartas")

vs3 = lt.generate_canonical_spot({'key': 'vs_3bet:CO:BTN:50', 'scenario': 'vs_3bet',
                                  'position': 'CO', 'vs_position': 'BTN', 'stack_bucket': 50,
                                  'label': 'x'})
check(vs3 is not None and vs3['spot']['scenario'] == 'vs_3bet',
      "vs_3bet gera spot (hero_was_aggressor resolve o cenário certo)")

# ── Grading: verdades GTO robustas (AA sempre abre, 32o sempre folda UTG) ─────────
g = lt.grade_canonical_spot(_rfi_spot('AA'), 'raise')
check(g['is_correct'] and g['gto_tier'] == 'correct' and g['gto_freq'] > 0.9,
      "AA RFI raise = correto (freq alta)")
check(lt.grade_canonical_spot(_rfi_spot('AA'), 'fold')['gto_tier'] == 'error',
      "AA RFI fold = erro")

gf = lt.grade_canonical_spot(_rfi_spot('32o'), 'fold')
check(gf['is_correct'] and gf['gto_tier'] == 'correct' and gf['gto_freq'] > 0.9,
      "32o RFI fold = correto (fold ~100%)")
check(not lt.grade_canonical_spot(_rfi_spot('32o'), 'raise')['is_correct'],
      "32o RFI raise = errado")

# ── Contrato: chaves que o CoachCard lê ──────────────────────────────────────────
need = {'is_correct', 'best_action', 'new_action', 'gto_freq', 'mixed',
        'gto_tier', 'gto_strategy', 'validation_source'}
check(need.issubset(set(g.keys())), "grade tem todas as chaves do contrato CoachCard")
check(isinstance(g['gto_strategy'], list) and all('action' in s and 'frequency' in s for s in g['gto_strategy']),
      "gto_strategy é lista de {action,frequency}")

# ── Normalização de ação (preflop: bet→raise, shove→jam) ─────────────────────────
check(lt._norm_action('bet') == 'raise' and lt._norm_action('shove') == 'jam' and
      lt._norm_action('3bet') == 'raise', "normalização de ação preflop")

# ── Adaptatividade: erros sobem o peso da categoria ─────────────────────────────
check(lt._adapt_factor({'misses': 3, 'hits': 0}) > lt._adapt_factor({'misses': 0, 'hits': 2}),
      "erros aumentam o fator adaptativo vs acertos")
check(lt._adapt_factor({'misses': 0, 'hits': 100}) >= 0.1,
      "fator adaptativo nunca abaixo do piso 0.1")

# next_spot devolve um spot da fundamentals (sem session_state)
ns = lt.next_spot(lt._fundamentals(), {}, rng=random.Random(3))
check(ns is not None and ns['street'] == 'preflop', "next_spot devolve spot dos fundamentos")

print(f"\nTotal: {passed + failed} Passed: {passed} Failed: {failed}")
sys.exit(1 if failed else 0)
