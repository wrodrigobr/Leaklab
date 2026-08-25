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
    'engine':    ['test_decision_engine.py', 'test_procedencia_do_veredito.py', 'test_evaluators.py', 'test_pipeline.py',
                  'test_draw_detector.py', 'test_postflop_evaluator.py', 'test_mtt_context.py',
                  'test_preflop_gto_quality.py', 'test_recent_regressions.py', 'test_icm.py',
                  'test_elo_engine.py', 'test_leaderboard.py', 'test_invariants.py',
                  'test_invariantes_acervo.py',
                  'test_mesma_jogada_outra_palavra.py',
                  'test_leak_trainer.py', 'test_strategy_provider.py', 'test_sanidade_do_gabarito.py', 'test_progression.py',
                  'test_nota_da_mao_postflop.py',
                  'test_condicoes_da_pergunta.py',
                  'test_drill_fronteira.py',
                  'test_memorizacao_range.py',
                  'test_proximo_passo.py',
                  'test_cobranca_email.py',
                  'test_meta_semanal.py',
                  'test_replay_acr_summary.py',
                  'test_reveals_do_summary.py',
                  'test_assento_sitting_out.py',
                  'test_assento_pko.py',
                  'test_replay_mao_pko.py',
                  'test_iniciativa_postflop.py',
                  'test_roster_e_formato.py',
                  'test_mesa_final.py',
                  'test_posicoes.py',
                  'test_familia_spot.py',
                  'test_perguntas_de_range.py',
                  'test_call_ja_allin.py',
                  'test_shove_equivale_call.py',
                  'test_acusacao_carrega_recomendacao.py',
                  'test_quatro_guardas_do_relatorio.py',
                  'test_facing_to_call.py',
                  'test_replay_pareamento.py',
                  'test_stack_efetivo.py',
                  'test_pote_e_equity_river.py',
                  'test_sem_gabarito_nao_e_erro.py',
                  'test_sem_gabarito_e_sem_gabarito_nenhum.py',
                  'test_sem_definicao_duplicada.py',
                  'test_pote_limpado_tem_preco.py',
                  'test_ev_cabe_no_jogo.py',
                  'test_progressao.py',
                  'test_pg_migration_isolation.py',
                  'test_interpretation_sign.py',
                  'test_texto_bate_com_veredito.py',
                  'test_validation.py',
                  'test_equity_range_aware.py', 'test_equity_do_river.py', 'test_preflop_open_size.py',
                  'test_bet_intent.py', 'test_opponent_stats.py', 'test_sizing_advisor.py',
                  'test_hu_position.py', 'test_posicao_botao_morto.py', 'test_parser_bounty.py',
                  'test_stack_buckets.py'],
    'database':  ['test_database.py', 'test_score_alinhado_no_insert.py', 'test_coach_system.py', 'test_notifications.py',
                  'test_solve_quota.py', 'test_coach_adherence_multiway.py', 'test_coach_invites.py',
                  'test_coach_trial.py', 'test_coach_referral.py', 'test_coach_replay.py',
                  'test_anotacao_sobrevive_reprocesso.py',
                  'test_admin_finance.py', 'test_verdict_invariant.py',
                  'test_training_gamification.py', 'test_conquistas_sem_prova.py',
                  'test_pool_de_conexoes.py',
                  'test_pending_gto_count.py', 'test_confidence_drift.py',
                  'test_no_id_tables.py', 'test_hand_request_cadence.py',
                  'test_chaves_de_decisao_gravadas.py',
                  'test_migracao_de_boot.py',
                  'test_reconcile_x_motor.py',
                  'test_sync_usa_o_provider.py',
                  'test_sync_x_motor_mesmos_args.py',
                  'test_is_production.py',
                  'test_clear_bogus_icm_tax.py', 'test_diag_validacao.py',
                  'test_evolution_report.py', 'test_bool_int_convention.py',
                  'test_evolution_cadence.py', 'test_row_access.py', 'test_sql_sem_porcentagem.py',
                  'test_portas_do_ev.py', 'test_facing_allin_row.py',
                  'test_ultima_atividade.py', 'test_prova_sem_n_mais_1.py'],
    'llm':       ['test_llm_explainer.py', 'test_gate_de_linguagem_gto.py', 'test_study_plan.py', 'test_study_patterns.py',
                  'test_revisor_pt.py', 'test_vocabulario_da_copy.py',
                  'test_i18n_copy_do_frontend.py'],
    'api':       ['test_api_endpoints.py', 'test_subscription.py', 'test_partygaming_financials.py',
                  'test_stripe_hardening.py', 'test_worker_entrypoints.py',
                  'test_decisao_exemplo.py', 'test_dashboard_demo.py',
                  'test_email_confirmacao.py', 'test_enqueue_pot_unit.py',
                  'test_villain_reveals_hud.py', 'test_equity_real_vs_mostrada.py',
                  'test_no_da_linha_pot_type.py', 'test_leaktrainer_3bet_pot.py',
                  'test_catalogo_de_treinos.py', 'test_mao_da_arvore.py',
                  'test_range_classes.py', 'test_mao_completa.py',
                  'test_funil_ativacao.py', 'test_dns_email_health.py',
                  'test_programa_fundadores.py', 'test_telegram_bot.py'],
    'regression':['test_tournament.py', 'test_multi_decision.py', 'test_partygaming_parser.py',
                  'test_acr_parser.py', 'test_coinpoker_parser.py',
                  'test_coinpoker_allin.py',
                  'test_raise_total_separator.py'],
    'ghost':     ['test_ghost_table_invariants.py', 'test_table_state.py', 'test_drill_preflop_action.py',
                  'test_drill_sem_veredito.py', 'test_trainer_pool.py',
                  'test_board_da_street_no_pool.py',
                  'test_dinheiro_coerente.py',
                  'test_trainer_catalog.py', 'test_grind_mode.py',
                  'test_categorias_cbet.py'],
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
                  'test_gap_preflop_nomeado.py',
                  'test_hu_preflop.py',
                  'test_coletor_gw.py',
                  'test_ring_gw.py',
                  'test_equity_vs_range_3bet.py',
                  'test_villain_jam_range.py',
                  'test_forca_da_mao_string_ou_lista.py',
                  'test_todo_caminho_mesmos_args.py', 'test_pko_carta_consistente.py',
                  'test_pote_do_guarda_de_jam.py',
                  'test_matriz_sem_carta.py', 'test_matriz_usa_stack_efetivo.py',
                  'test_carta_do_no_certo.py',
                  'test_no_iniciativa_aware.py',
                  'test_frequencia_nao_se_inventa.py',
                  'test_motivo_sem_gabarito_tem_frase.py',
                  'test_posicao_por_jogadores_atras.py',
                  'test_adjacencia_raise_jam.py',
                  'test_range_pct_unidade.py',
                  'test_sizing_nao_contradiz_veredito.py',
                  'test_fallback_call_vs_shove.py',
                  'test_limp_fora_dos_blinds.py',
                  'test_balde_da_carta_profundidade.py',
                  'test_plano_ring.py',
                  'test_facing_limp_persistido.py',
                  'test_bb_check_nao_e_free_play.py',
                  'test_multiway_divergence.py',
                  'test_multiway_advisor.py',
                  'test_multiway_safety.py',
                  'test_pko_har_parser.py',
                  'test_pko_engine.py',
                  'test_ev_loss.py',
                  'test_ev_leaks.py',
                  'test_replay_reconciliation_golden.py',
                  'test_replay_nao_grava.py',
                  'test_resync_pareamento.py'],
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
        # Os arquivos imprimem em DUAS convencoes ('FAIL ...' e 'FALHOU ...'). So a primeira era
        # capturada: em 15/08 a suite terminou "4 falhas" e VERDE, porque as 4 eram FALHOU e a
        # lista (que decide o exit code) ficou vazia. Falha contada sem nome capturado nao pode
        # virar verde — dai o fallback sintetico abaixo.
        fails   = [l for l in lines if l.startswith('FAIL') or l.startswith('FALHOU')]
        if summary:
            s = summary[-1]
            p = int(s.split('Passed:')[1].split('|')[0].strip())
            f = int(s.split('Failed:')[1].strip())
            passed += p; failed += f
            mark = '✅' if f == 0 else f'❌ {f}×'
            print(f"  {mark:<8} {fname:<42} {p+f:>3} testes")
            if f > 0 and not fails:
                fails = [f"{f} falha(s) sem linha FAIL/FALHOU capturada — ver saida do arquivo"]
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
