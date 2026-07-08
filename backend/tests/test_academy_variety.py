"""
test_academy_variety.py — Testa a taxa de variedade e a correção semântica dos geradores da Academia.

Cobertura:
  1. Variedade: >= 70% de questões únicas em 50 chamadas por gerador.
  2. Validade de street: odds_vs_equity nunca usa preflop ou river (regra 2/4 não se aplica).

Roda sem banco de dados (mock de _fetch_math_decision).
"""
import sys, os, re, random, unittest, unittest.mock
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

    def setUp(self):
        # Seed fixa → variedade determinística. Sem isto, o estado global do RNG
        # deixado por testes anteriores na suite completa fazia o gerador mais
        # apertado (3bet_pot, ~80% típico) oscilar abaixo do mínimo de 70% (flaky).
        random.seed(20260530)

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

    def test_bubble_defense_structure(self):
        """bubble_defense: espaço pequeno (resposta fixa) → teste estrutural, não de
        variedade. A cobertura do dispatcher fica no test_tournament_variety."""
        q = acad._bubble_defense_question()
        self.assertEqual(q['type'], 'bubble_defense')
        self.assertEqual(len(q['options']), 3)
        self.assertEqual(q['correct_index'], 0)
        self.assertIn('MENOS', q['options'][q['correct_index']])   # over-defense = defender menos
        self.assertTrue(q['explanation'] and q['mental_tip'])
        print("  ✔ bubble_defense structure")

    def test_multiway_drill_structure(self):
        """Treino da aula de Multiway: 3 tipos, estrutura válida, resposta certa alinhada
        aos conceitos (blefe→desistir, sizing→menor, meio→apertado)."""
        seen = set()
        for _ in range(30):
            q = acad.generate_multiway_question(user_id=1)
            self.assertIn(q['type'], ('mw_bluff', 'mw_sizing', 'mw_middle'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'mw_bluff', 'mw_sizing', 'mw_middle'})  # os 3 aparecem
        # variedade: o pool parametrizado gera muitos enunciados distintos (dedup no
        # front garante unicidade em sessão; aqui só conferimos que há margem)
        fps = {_fingerprint(acad.generate_multiway_question(1)) for _ in range(120)}
        self.assertGreaterEqual(len(fps), 12, f"pool multiway pequeno: {len(fps)} enunciados")
        # respostas certas por conceito
        import leaklab.academy as A
        self.assertIn('Desistir', A._mw_bluff_question()['options'][A._mw_bluff_question()['correct_index']])
        self.assertEqual(A._mw_sizing_question()['options'][A._mw_sizing_question()['correct_index']], 'Menor')
        self.assertEqual(A._mw_middle_question()['options'][A._mw_middle_question()['correct_index']], 'Jogar apertado')
        print("  ✔ multiway drill structure")

    def test_icm_drill_structure(self):
        """Treino da aula de ICM: reusa icm_spot + bubble_defense (foco em ICM)."""
        seen = set()
        for _ in range(40):
            q = acad.generate_icm_question(user_id=1)
            self.assertIn(q['type'], ('icm_spot', 'bubble_defense'))
            self.assertGreaterEqual(len(q['options']), 2)
            self.assertTrue(0 <= q['correct_index'] < len(q['options']))
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'icm_spot', 'bubble_defense'})  # os dois aparecem
        print("  ✔ icm drill structure")

    def test_postflop_drill_structure(self):
        """Treino da aula de Postflop: cbet_dry, cbet_wet, barrel."""
        seen = set()
        for _ in range(40):
            q = acad.generate_postflop_question(user_id=1)
            self.assertIn(q['type'], ('cbet_dry', 'cbet_wet', 'barrel'))
            self.assertEqual(len(q['options']), 3)
            self.assertTrue(0 <= q['correct_index'] < 3)
            self.assertTrue(q['question'] and q['explanation'] and q['mental_tip'])
            seen.add(q['type'])
        self.assertEqual(seen, {'cbet_dry', 'cbet_wet', 'barrel'})
        import leaklab.academy as A
        self.assertIn('C-bet pequeno', A._cbet_dry_question()['options'][A._cbet_dry_question()['correct_index']])
        print("  ✔ postflop drill structure")

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


    # ── Street validity tests ──────────────────────────────────────────────────

    def test_odds_vs_equity_rejects_preflop(self):
        """Rule of 2/4 never appears with preflop context."""
        ctx = {'street': 'preflop', 'label': 'standard',
               'action_taken': 'call', 'best_action': 'call', 'position': 'IP'}
        for _ in range(30):
            q = acad._odds_vs_equity_question(10.0, 5.0, ctx)
            m = re.search(r'No \*\*(\w+)\*\*', q['question'])
            street = m.group(1) if m else 'unknown'
            self.assertIn(street, ('flop', 'turn'),
                          f"preflop leaked: {q['question'][:80]}")

    def test_odds_vs_equity_rejects_river(self):
        """Rule of 2/4 never appears with river context (no cards to come)."""
        ctx = {'street': 'river', 'label': 'standard',
               'action_taken': 'call', 'best_action': 'call', 'position': 'IP'}
        for _ in range(30):
            q = acad._odds_vs_equity_question(10.0, 5.0, ctx)
            m = re.search(r'No \*\*(\w+)\*\*', q['question'])
            street = m.group(1) if m else 'unknown'
            self.assertIn(street, ('flop', 'turn'),
                          f"river leaked: {q['question'][:80]}")

    def test_generate_math_intermediate_preflop_history_safe(self):
        """generate_math[intermediate] with preflop history never produces invalid street."""
        bad_ctx = {'street': 'preflop', 'label': 'standard',
                   'action_taken': 'call', 'best_action': 'call', 'position': 'IP'}
        with unittest.mock.patch.object(acad, '_fetch_math_decision', return_value=bad_ctx):
            for _ in range(50):
                q = acad.generate_math_question(user_id=1, level='intermediate')
                if q['type'] == 'odds_vs_equity':
                    m = re.search(r'No \*\*(\w+)\*\*', q['question'])
                    street = m.group(1) if m else 'unknown'
                    self.assertIn(street, ('flop', 'turn'),
                                  f"preflop leaked via dispatcher: {q['question'][:80]}")


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
