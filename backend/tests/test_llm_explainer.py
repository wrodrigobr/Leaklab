"""
Testes do llm_explainer.
Testa templates locais, parsing de resposta e fallback — sem chamar a API real.
"""
import sys, os, json, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaphunter.llm_explainer import (
    explain_decisions, _template_standard, _template_error,
    _parse_llm_response, _key, _cache
)


def _decision(label='standard', action='fold', best='fold',
              street='preflop', score=0.05, math_pen=0.0, hand_id='123'):
    return {
        'handId':     hand_id,
        'street':     street,
        'actionTaken': action,
        'bestAction':  best,
        'hero_cards':  'AsKh',
        'evaluation': {
            'label':        label,
            'mistakeScore': score,
            'scoreBreakdown': {
                'baseActionGap': 0.0 if label == 'standard' else 0.18,
                'mathPenalty':   math_pen,
                'rangePenalty':  0.0,
                'contextPenalty':0.01,
                'toleranceCredit':0.0,
            }
        },
        'math': {'potOddsEquity': None, 'estimatedHandEquity': 0.49},
        'context': {
            'icmPressure': 'low',
            'tournamentStage': 'early',
            'mRatio': 12.0,
            'heroStackBb': 30.0,
        }
    }


# ── Templates locais ──────────────────────────────────────────────────────────

def test_template_standard_returns_string():
    d   = _decision(label='standard', action='fold', street='preflop')
    txt = _template_standard(d)
    assert isinstance(txt, str) and len(txt) > 10
    assert 'pré-flop' in txt
    print(f"OK  test_template_standard_returns_string | '{txt[:60]}...'")


def test_template_error_contains_actions():
    d   = _decision(label='small_mistake', action='fold', best='raise',
                    street='preflop', score=0.256)
    txt = _template_error(d)
    assert 'fold' in txt
    assert 'raise' in txt
    assert '0.256' in txt
    print(f"OK  test_template_error_contains_actions | '{txt[:70]}...'")


def test_template_street_translation():
    for street, pt in [('preflop','pré-flop'), ('flop','flop'),
                       ('turn','turn'), ('river','river')]:
        d   = _decision(street=street)
        txt = _template_standard(d)
        assert pt in txt, f"'{pt}' não encontrado em '{txt}'"
    print("OK  test_template_street_translation")


# ── Parse de resposta LLM ─────────────────────────────────────────────────────

def test_parse_valid_json_array():
    raw = '["Explicação 1.", "Explicação 2.", "Explicação 3."]'
    result = _parse_llm_response(raw, 3)
    assert result == ["Explicação 1.", "Explicação 2.", "Explicação 3."]
    print("OK  test_parse_valid_json_array")


def test_parse_json_with_markdown_fences():
    raw = '```json\n["Texto A.", "Texto B."]\n```'
    result = _parse_llm_response(raw, 2)
    assert len(result) == 2
    assert result[0] == "Texto A."
    print("OK  test_parse_json_with_markdown_fences")


def test_parse_pads_short_response():
    """Se LLM retornar menos itens que o esperado, preenche com fallback."""
    raw = '["Só uma explicação."]'
    result = _parse_llm_response(raw, 3)
    assert len(result) == 3
    assert result[0] == "Só uma explicação."
    assert result[1] == 'Decisão analisada pelo engine.'
    print("OK  test_parse_pads_short_response")


def test_parse_truncates_extra_items():
    raw = '["A.", "B.", "C.", "D."]'
    result = _parse_llm_response(raw, 2)
    assert len(result) == 2
    print("OK  test_parse_truncates_extra_items")


def test_parse_fallback_on_invalid_json():
    raw = 'Não consegui gerar o JSON.\nExplicação 1.\nExplicação 2.'
    result = _parse_llm_response(raw, 2)
    assert len(result) == 2
    assert isinstance(result[0], str)
    print("OK  test_parse_fallback_on_invalid_json")


# ── explain_decisions — sem LLM ───────────────────────────────────────────────

def test_explain_standard_uses_template_not_llm():
    """Decisões standard/marginal não devem chamar o LLM."""
    decisions = [
        _decision(label='standard', hand_id='001'),
        _decision(label='marginal', action='call', best='raise',
                  score=0.15, hand_id='002'),
    ]
    # explain_decisions não deve falhar mesmo sem API key
    result = explain_decisions(decisions)
    assert len(result) == 2
    for k, v in result.items():
        assert isinstance(v, str) and len(v) > 5
    print(f"OK  test_explain_standard_uses_template_not_llm | {len(result)} explicações")


def test_explain_error_uses_fallback_when_no_api():
    """Com erro no LLM, deve usar template de fallback sem quebrar."""
    decisions = [
        _decision(label='small_mistake', action='fold', best='raise',
                  score=0.256, hand_id='err01'),
        _decision(label='clear_mistake', action='call', best='fold',
                  score=0.599, hand_id='err02'),
    ]
    # Sem API key, vai cair no fallback — não deve levantar exceção
    result = explain_decisions(decisions)
    assert len(result) == 2
    for k, v in result.items():
        assert isinstance(v, str) and len(v) > 5
    print(f"OK  test_explain_error_uses_fallback_when_no_api | {len(result)} explicações")


def test_cache_populated_after_template():
    """Após explain_decisions, decisões standard ficam disponíveis."""
    d = _decision(label='standard', hand_id='cache_test_01')
    result = explain_decisions([d])
    assert len(result) == 1
    print("OK  test_cache_populated_after_template")


def test_key_deterministic():
    """A mesma decisão sempre gera a mesma chave."""
    d = _decision(hand_id='555', street='flop', action='call')
    assert _key(d) == _key(d)
    print("OK  test_key_deterministic")


def test_key_different_for_different_decisions():
    d1 = _decision(hand_id='A', street='flop',   action='call')
    d2 = _decision(hand_id='A', street='turn',   action='call')
    d3 = _decision(hand_id='B', street='flop',   action='call')
    assert _key(d1) != _key(d2)
    assert _key(d1) != _key(d3)
    print("OK  test_key_different_for_different_decisions")


def test_mixed_batch_returns_all():
    """Batch com erros e standards retorna explicação para todos."""
    decisions = [
        _decision(label='standard',     hand_id='m1'),
        _decision(label='small_mistake', action='fold', best='raise',
                  score=0.256, hand_id='m2'),
        _decision(label='clear_mistake', action='call', best='fold',
                  score=0.599, hand_id='m3'),
        _decision(label='marginal',     action='call', best='raise',
                  score=0.15,  hand_id='m4'),
    ]
    result = explain_decisions(decisions)
    assert len(result) == 4
    print(f"OK  test_mixed_batch_returns_all | {len(result)} explicações")
# ── Tournament summary ────────────────────────────────────────────────────────

def _make_results(n=20):
    """Gera lista de resultados simulados para testar o summary."""
    import random; random.seed(42)
    labels = ['standard','standard','standard','marginal','small_mistake','clear_mistake']
    icms   = ['low','medium','high']
    results = []
    for i in range(n):
        label = random.choice(labels)
        score = {'standard':.05,'marginal':.15,'small_mistake':.28,'clear_mistake':.50}[label]
        results.append({
            'evaluation': {'label': label, 'mistakeScore': score},
            'street': random.choice(['preflop','flop','turn','river']),
            'actionTaken': random.choice(['fold','call','raise','bet','check']),
            'bestAction':  random.choice(['fold','call','raise']),
            'context': {
                'icmPressure': random.choice(icms),
                'mRatio': random.uniform(2, 18),
            }
        })
    return results


def test_summary_fallback_returns_string():
    from gaphunter.llm_explainer import generate_tournament_summary
    results = _make_results(20)
    s = generate_tournament_summary(results, 15, 'TestPlayer')
    assert isinstance(s, str) and len(s) > 50
    print(f"OK  test_summary_fallback_returns_string | {len(s.split())} palavras")


def test_summary_contains_player_name():
    from gaphunter.llm_explainer import generate_tournament_summary
    results = _make_results(20)
    s = generate_tournament_summary(results, 15, 'Villanacci')
    assert 'Villanacci' in s
    print("OK  test_summary_contains_player_name")


def test_summary_context_builds_correctly():
    from gaphunter.llm_explainer import _build_tournament_context
    results = _make_results(40)
    ctx = _build_tournament_context(results, 30)
    assert 'total_hands' in ctx
    assert 'avg_score' in ctx
    assert 'standard_pct' in ctx
    assert 'icm_breakdown' in ctx
    assert 'top_leaks' in ctx
    assert ctx['total_decisions'] == 40
    assert 0 < ctx['standard_pct'] < 100
    print(f"OK  test_summary_context_builds_correctly | score={ctx['avg_score']:.3f} std={ctx['standard_pct']:.0f}%")


def test_summary_cache_works():
    from gaphunter.llm_explainer import generate_tournament_summary, _cache
    results = _make_results(20)
    s1 = generate_tournament_summary(results, 15, 'CacheTest')
    s2 = generate_tournament_summary(results, 15, 'CacheTest')
    assert s1 == s2  # segunda chamada deve vir do cache
    print("OK  test_summary_cache_works")


def test_summary_icm_comment_when_high_pressure():
    from gaphunter.llm_explainer import _build_tournament_context, _template_tournament_summary
    # Criar resultados com performance muito pior no ICM high
    results = []
    for _ in range(10):
        results.append({'evaluation':{'label':'standard','mistakeScore':.04},'street':'preflop','actionTaken':'fold','bestAction':'fold','context':{'icmPressure':'low','mRatio':15.0}})
    for _ in range(10):
        results.append({'evaluation':{'label':'clear_mistake','mistakeScore':.55},'street':'turn','actionTaken':'call','bestAction':'fold','context':{'icmPressure':'high','mRatio':4.0}})
    ctx = _build_tournament_context(results, 20)
    s   = _template_tournament_summary(ctx, 'Hero')
    # Score ICM high deve ser muito maior que avg — comentário deve aparecer
    assert ctx['icm_breakdown']['high']['avg'] > ctx['avg_score'] * 1.3
    assert 'ICM' in s or 'stack' in s.lower()
    print(f"OK  test_summary_icm_comment_when_high_pressure | icm_high_avg={ctx['icm_breakdown']['high']['avg']:.3f}")

if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
