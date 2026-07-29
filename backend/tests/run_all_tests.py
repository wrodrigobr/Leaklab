#!/usr/bin/env python3
"""
PokerLeakLab — Master Test Runner
Executa todos os testes e exige zero regressões.

Uso:
    python3 tests/run_all_tests.py              # todos
    python3 tests/run_all_tests.py --fast       # sem testes com fixture real
    python3 tests/run_all_tests.py --suite api  # só um grupo
"""
import sys, os, subprocess, time, argparse
sys.path.insert(0, os.path.dirname(__file__))

SUITES = {
    'engine':    ['test_decision_engine.py', 'test_evaluators.py', 'test_pipeline.py',
                  'test_draw_detector.py', 'test_postflop_evaluator.py', 'test_mtt_context.py',
                  'test_preflop_gto_quality.py', 'test_recent_regressions.py', 'test_icm.py',
                  'test_elo_engine.py', 'test_leaderboard.py', 'test_invariants.py',
                  'test_leak_trainer.py', 'test_strategy_provider.py', 'test_progression.py',
                  'test_drill_fronteira.py',
                  'test_memorizacao_range.py',
                  'test_proximo_passo.py',
                  'test_cobranca_email.py',
                  'test_pg_migration_isolation.py',
                  'test_interpretation_sign.py',
                  'test_validation.py',
                  'test_equity_range_aware.py', 'test_preflop_open_size.py',
                  'test_bet_intent.py', 'test_opponent_stats.py', 'test_sizing_advisor.py',
                  'test_hu_position.py', 'test_parser_bounty.py',
                  'test_stack_buckets.py'],
    'database':  ['test_database.py', 'test_coach_system.py', 'test_notifications.py',
                  'test_solve_quota.py', 'test_coach_adherence_multiway.py', 'test_coach_invites.py',
                  'test_coach_trial.py', 'test_coach_referral.py', 'test_coach_replay.py',
                  'test_admin_finance.py', 'test_verdict_invariant.py',
                  'test_training_gamification.py',
                  'test_pending_gto_count.py', 'test_confidence_drift.py',
                  'test_no_id_tables.py', 'test_hand_request_cadence.py',
                  'test_is_production.py',
                  'test_clear_bogus_icm_tax.py', 'test_diag_validacao.py',
                  'test_evolution_report.py', 'test_bool_int_convention.py',
                  'test_evolution_cadence.py', 'test_row_access.py'],
    'llm':       ['test_llm_explainer.py', 'test_study_plan.py', 'test_study_patterns.py'],
    'api':       ['test_api_endpoints.py', 'test_subscription.py', 'test_partygaming_financials.py',
                  'test_stripe_hardening.py', 'test_worker_entrypoints.py'],
    'regression':['test_tournament.py', 'test_multi_decision.py', 'test_partygaming_parser.py',
                  'test_acr_parser.py', 'test_coinpoker_parser.py',
                  'test_raise_total_separator.py'],
    'ghost':     ['test_ghost_table_invariants.py', 'test_table_state.py', 'test_drill_preflop_action.py'],
    'academy':   ['test_academy_variety.py'],
    'challenge': ['test_daily_challenge_difficulty.py', 'test_challenge_adversarial.py'],
    'gto':       ['test_tree_hash.py',
                  'test_board_slice_hash.py',
                  'test_hand_view.py',
                  'test_gto_comparison.py',
                  'test_gto_utils_comprehensive.py',
                  'test_gto_enrichment.py',
                  'test_api_gto_endpoints.py',
                  'test_card_invariants.py',
                  'test_card_verdict.py',
                  'test_multiway_divergence.py',
                  'test_multiway_advisor.py',
                  'test_multiway_safety.py',
                  'test_pko_har_parser.py',
                  'test_pko_engine.py',
                  'test_ev_loss.py',
                  'test_ev_leaks.py',
                  'test_replay_reconciliation_golden.py',
                  'test_replay_nao_grava.py'],
    'revalidation': ['test_revalidation_oracle.py',
                     'test_revalidation_differ.py',
                     'test_revalidation_orchestrator.py',
                     'test_revalidation_api.py',
                     'test_revalidation_llm_judge.py',
                     'test_revalidation_fixtures.py',
                     'test_revalidation_drift.py',
                     'test_revalidation_pattern_scan.py'],
}

BASE = os.path.dirname(__file__)

def run_suite(name: str, files: list, fast: bool = False) -> tuple[int,int,list]:
    passed = failed = 0
    failures = []
    for fname in files:
        fpath = os.path.join(BASE, fname)
        if not os.path.exists(fpath):
            print(f"  ⚠️  {fname} — arquivo não encontrado, pulando")
            continue
        r = subprocess.run(
            [sys.executable, fpath],
            capture_output=True, text=True, encoding='utf-8',
            cwd=os.path.join(BASE, '..')
        )
        lines = (r.stdout + r.stderr).strip().split('\n')
        summary = [l for l in lines if 'Total:' in l and 'Passed:' in l]
        fails   = [l for l in lines if l.startswith('FAIL')]
        if summary:
            s = summary[-1]
            p = int(s.split('Passed:')[1].split('|')[0].strip())
            f = int(s.split('Failed:')[1].strip())
            passed += p; failed += f
            mark = '✅' if f == 0 else f'❌ {f}×'
            print(f"  {mark:<8} {fname:<42} {p+f:>3} testes")
            for fail in fails:
                failures.append(f"[{fname}] {fail}")
                print(f"           ↳ {fail}")
        else:
            err = '\n'.join(l for l in lines if 'Error' in l or 'error' in l)[:120]
            print(f"  ⚠️  {fname:<42} IMPORT/RUNTIME ERROR: {err}")
            failures.append(f"[{fname}] IMPORT/RUNTIME ERROR: {err}")
    return passed, failed, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true', help='Pular testes com fixture real')
    parser.add_argument('--suite', default=None, help='Executar só uma suite: engine|database|llm|api|regression')
    args = parser.parse_args()

    suites = {args.suite: SUITES[args.suite]} if args.suite and args.suite in SUITES else SUITES

    print("=" * 60)
    print("PokerLeakLab — Test Runner")
    print("=" * 60)

    t0 = time.time()
    total_p = total_f = 0
    all_failures = []

    for suite_name, files in suites.items():
        print(f"\n── {suite_name.upper()} ──")
        p, f, fails = run_suite(suite_name, files, fast=args.fast)
        total_p += p; total_f += f
        all_failures.extend(fails)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_p+total_f} testes | ✅ {total_p} ok | ❌ {total_f} falhas | {elapsed:.1f}s")
    print('='*60)

    if all_failures:
        print("\n🔴 FALHAS — regressão detectada:")
        for f in all_failures:
            print(f"  • {f}")
        sys.exit(1)
    else:
        print("\n🟢 Todos os testes passaram — zero regressões")
        sys.exit(0)


if __name__ == '__main__':
    main()
