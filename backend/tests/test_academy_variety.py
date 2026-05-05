"""
test_academy_variety.py — Testa a taxa de variedade dos geradores da Academia.

Objetivo: detectar quando um gerador repete questões com frequência excessiva.
Critério de aprovação: >= 70% de questões únicas em 50 chamadas.

Roda sem banco de dados (mock de _fetch_math_decision → None, que ativa fallback sintético).
"""
import sys, os, unittest, unittest.mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.academy as acad

# ── Helper ─────────────────────────────────────────────────────────────────────

def _fingerprint(q: dict) -> str:
    """Identifica uma questão pelo texto e resposta correta."""
    return f"{q['question'][:120]}|{q['correct_index']}"


def _diversity(generator_fn, n: int = 50) -> tuple[int, int, float]:
    """Retorna (únicos, total, taxa)."""
    seen = set()
    for _ in range(n):
        q = generator_fn()
        seen.add(_fingerprint(q))
    rate = len(seen) / n
    return len(seen), n, rate


MIN_DIVERSITY = 0.70   # mínimo 70% únicos em 50 chamadas


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestAcademyVariety(unittest.TestCase):

    def _assert_diverse(self, name: str, fn, n: int = 50):
        unique, total, rate = _diversity(fn, n)
        self.assertGreaterEqual(
            rate, MIN_DIVERSITY,
            f"{name}: apenas {unique}/{total} únicos ({rate:.0%}) — abaixo do mínimo {MIN_DIVERSITY:.0%}"
        )
        print(f"  ✔ {name}: {unique}/{total} únicos ({rate:.0%})")

    # ── Geradores diretos (sem banco) ──────────────────────────────────────────

    def test_outs_count_variety(self):
        self._assert_diverse("outs_count", acad._outs_count_question)

    def test_equity_estimate_variety(self):
        self._assert_diverse("equity_estimate", acad._equity_estimate_question)

    def test_spr_commitment_variety(self):
        self._assert_diverse("spr_commitment", acad._spr_commitment_question)

    def test_icm_spot_variety(self):
        self._assert_diverse("icm_spot", acad._icm_spot_question)

    def test_3bet_pot_variety(self):
        self._assert_diverse("3bet_pot", acad._3bet_pot_question)

    # ── Geradores via dispatcher (mock: sem banco) ─────────────────────────────

    def test_math_beginner_variety(self):
        """generate_math_question(beginner) — mock sem histórico do usuário."""
        with unittest.mock.patch.object(acad, '_fetch_math_decision', return_value=None):
            fn = lambda: acad.generate_math_question(user_id=1, level='beginner')
            self._assert_diverse("generate_math_question[beginner]", fn)

    def test_math_intermediate_variety(self):
        """generate_math_question(intermediate) — mock sem histórico."""
        with unittest.mock.patch.object(acad, '_fetch_math_decision', return_value=None):
            fn = lambda: acad.generate_math_question(user_id=1, level='intermediate')
            self._assert_diverse("generate_math_question[intermediate]", fn)

    def test_tournament_variety(self):
        """generate_tournament_question — só usa geradores internos, sem banco."""
        fn = lambda: acad.generate_tournament_question(user_id=1)
        self._assert_diverse("generate_tournament_question", fn)

    # ── Teste de repetição com histórico PEQUENO (simula usuário com poucas mãos) ──

    def test_math_beginner_small_history(self):
        """
        Simula usuário com apenas 3 decisões distintas no banco.
        Mesmo com pool pequena, a variedade deve ser >= 70%.
        """
        small_pool = [
            {'pot_size': 10.0, 'facing_bet': 5.0,  'stack_bb': 25, 'm_ratio': 8,
             'label': 'standard', 'action_taken': 'call', 'best_action': 'call',
             'street': 'flop', 'position': 'IP', 'score': 0.8},
            {'pot_size': 20.0, 'facing_bet': 10.0, 'stack_bb': 40, 'm_ratio': 12,
             'label': 'small_mistake', 'action_taken': 'call', 'best_action': 'fold',
             'street': 'turn', 'position': 'OOP', 'score': 0.3},
            {'pot_size': 8.0,  'facing_bet': 8.0,  'stack_bb': 15, 'm_ratio': 4,
             'label': 'clear_mistake', 'action_taken': 'fold', 'best_action': 'call',
             'street': 'river', 'position': 'IP', 'score': 0.1},
        ]

        import itertools
        pool_cycle = itertools.cycle(small_pool)

        with unittest.mock.patch.object(acad, '_fetch_math_decision',
                                        side_effect=lambda uid: next(pool_cycle)):
            fn = lambda: acad.generate_math_question(user_id=1, level='beginner')
            self._assert_diverse("generate_math_question[beginner, small history=3]", fn)


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_tests():
    loader  = unittest.TestLoader()
    suite   = loader.loadTestsFromTestCase(TestAcademyVariety)
    runner  = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
    result  = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    failed = len(result.failures) + len(result.errors)

    print(f"\n{'='*60}")
    if result.failures or result.errors:
        for label, tb in result.failures + result.errors:
            print(f"FAIL  {label.id().split('.')[-1]}")
            # Print the assertion message only
            lines = tb.strip().split('\n')
            for l in lines[-3:]:
                print(f"      {l}")
        print()
    print(f"Total: {result.testsRun} | Passed: {passed} | Failed: {failed}")


if __name__ == '__main__':
    print("Academia LeakLab — Teste de Variedade de Exercícios")
    print("="*60)
    run_tests()
