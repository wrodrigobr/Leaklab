from __future__ import annotations
import sys
from .parser import parse_pokerstars_file
from .pipeline import build_decision_inputs_for_hand
from .decision_engine_v11 import evaluate_decision
from .mtt_context import build_mtt_context
from .session_metrics import build_session_metrics
from .leak_correlator import correlate_leaks
from .report_generator import generate_report


def run_validation(file_path: str, output_html: str | None = None) -> dict:
    print('\n=== GapHunter Validation v1.1 ===')
    print(f'Arquivo: {file_path}\n')

    hands = parse_pokerstars_file(file_path)
    results, errors, hand_results = [], [], {}

    # Detectar hero e tournament_id da primeira mão
    hero = hands[0].hero if hands else 'Hero'
    tournament_id = hands[0].tournament_id if hands else ''

    for hand in hands:
        try:
            mtt    = build_mtt_context(hand)
            inputs = build_decision_inputs_for_hand(hand)
            hand_decisions = []
            for di in inputs:
                r = evaluate_decision(di)
                r['street']       = di['street']
                r['context']      = di['context']
                r['math']         = di['math']
                r['spot']         = di['spot']
                r['hero_cards']   = hand.hero_cards
                r['hand_id_full'] = hand.hand_id
                results.append(r)
                hand_decisions.append(r)
            if hand_decisions:
                hand_results[hand.hand_id] = {
                    'decisions': hand_decisions,
                    'cards': hand.hero_cards,
                    'mtt': {
                        'mRatio':   mtt.m_ratio,
                        'icm':      mtt.icm_pressure,
                        'stage':    mtt.tournament_stage,
                        'players':  mtt.active_players,
                        'stackBb':  mtt.hero_stack_bb,
                    },
                }
        except Exception as e:
            errors.append((hand.hand_id, str(e)))

    metrics = build_session_metrics(results)
    leaks   = correlate_leaks(results)

    _print_summary(metrics, leaks, results, len(hands), errors)

    if output_html:
        path = generate_report(results, hand_results, output_html,
                               hero=hero, tournament_id=tournament_id)
        print(f'\n✅ Relatório salvo em: {path}')

    return {
        'total_hands':     len(hands),
        'total_decisions': metrics['total_decisions'],
        'metrics':         metrics,
        'leaks':           leaks,
        'errors':          errors,
        'results':         results,
    }


def _print_summary(metrics, leaks, results, total_hands, errors):
    print('=== RESULTADOS ===')
    print(f'Mãos no arquivo:     {total_hands}')
    print(f'Decisões analisadas: {metrics["total_decisions"]}')
    print(f'Erros de parse:      {len(errors)}')

    print('\nDistribuição de labels:')
    for label in ['standard', 'marginal', 'small_mistake', 'clear_mistake']:
        count = metrics['label_distribution'].get(label, 0)
        pct   = metrics['label_pct'].get(label, 0.0)
        print(f'  {label:<15} {count:>4}  ({pct:.1f}%)')

    print(f'\nScore médio: {metrics["avg_mistake_score"]:.4f}')

    print('\nPor street:')
    for street in ['preflop', 'flop', 'turn', 'river']:
        dist = metrics['by_street'].get(street, {})
        if dist:
            total_s  = sum(dist.values())
            erros_s  = sum(v for k, v in dist.items() if k != 'standard')
            print(f'  {street:<8} {total_s:>4} decisões | {erros_s} com erro ({erros_s/total_s*100:.0f}%)')

    print('\n=== TOP 10 ERROS ===')
    worst = sorted(results, key=lambda x: x['evaluation']['mistakeScore'], reverse=True)[:10]
    for r in worst:
        ctx = r.get('context', {})
        print(f'  #{str(r["handId"])[-7:]} | {r["street"]:<8} | '
              f'{r["evaluation"]["label"]:<15} | '
              f'score={r["evaluation"]["mistakeScore"]:.3f} | '
              f'tomou={r["actionTaken"]} esperado={r["bestAction"]} | '
              f'M={ctx.get("mRatio","?")} icm={ctx.get("icmPressure","?")}')

    print('\n=== LEAKS (street × ação, top 8) ===')
    sa = sorted(leaks['by_street_action'].items(),
                key=lambda x: x[1]['avg_weight'], reverse=True)
    for key, v in sa[:8]:
        if v['count'] >= 2:
            print(f'  {key:<25} avg={v["avg_weight"]:.3f}  n={v["count"]}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python -m gaphunter.run_tournament_validation <arquivo.txt> [relatorio.html]')
        raise SystemExit(1)
    html_out = sys.argv[2] if len(sys.argv) > 2 else None
    run_validation(sys.argv[1], html_out)
