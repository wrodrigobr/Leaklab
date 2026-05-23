"""
Testa leaklab.revalidation.llm_judge -- mocka requests.post para evitar API real.

Cobre:
  - payload tem modelo + max_tokens + descrição do spot
  - parse de resposta válida (JSON estrito)
  - parse tolerante a texto extra
  - cache hit pula a chamada
  - budget=0 não chama
  - judge_findings só processa categorias disputadas
"""
import sys, os, json, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest.mock as mock

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ['ANTHROPIC_API_KEY'] = 'test-key-xxx'  # judge_spot verifica isso


def _reset_db_with_cache_table():
    try:
        os.unlink(_TMPDB.name)
    except FileNotFoundError:
        pass
    from database.schema import init_db
    init_db()


def _finding(**over):
    base = {
        'tournament_db_id': 1, 'hand_id': 'H1', 'decision_index': 0,
        'street': 'flop', 'position': 'BTN',
        'action_taken': 'check', 'engine_best': 'check',
        'oracle_action': 'bet', 'gto_action': 'bet',
        'category': 'major_mismatch', 'severity_score': 0.85,
        'opp_cost_bb': 0.40, 'oracle_source': 'postflop_strategy',
        'oracle_confidence': 'high', 'reasons': [],
    }
    base.update(over)
    return base


def _fake_response(text: str):
    """Simula requests.Response -- retorna .json() e .raise_for_status()."""
    m = mock.MagicMock()
    m.raise_for_status = lambda: None
    m.json = lambda: {'content': [{'type': 'text', 'text': text}]}
    return m


# -- Testes ------------------------------------------------------------------

def test_payload_has_model_and_spot_context():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    captured = {}
    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['payload'] = json
        return _fake_response('{"verdict":"oracle_correct","reasoning":"GTO solver wins."}')

    with mock.patch('requests.post', side_effect=fake_post):
        res = llm_judge.judge_spot(_finding())

    assert captured['url'].endswith('/v1/messages')
    p = captured['payload']
    assert p['model'] == 'claude-haiku-4-5-20251001'
    assert p['max_tokens'] >= 100
    msg = p['messages'][0]['content']
    assert 'engine recomenda' in msg
    assert 'oracle recomenda' in msg
    assert 'street=flop' in msg
    assert res['verdict'] == 'oracle_correct'
    assert res['cached'] is False
    print(f"OK  test_payload_has_model_and_spot_context (verdict={res['verdict']})")


def test_response_parse_strict_json():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    with mock.patch('requests.post', return_value=_fake_response(
        '{"verdict":"engine_correct","reasoning":"3-bet vs aberto OOP é correto."}'
    )):
        res = llm_judge.judge_spot(_finding())
    assert res['verdict'] == 'engine_correct'
    assert 'OOP' in res['reasoning']
    print("OK  test_response_parse_strict_json")


def test_response_parse_tolerates_wrapping_text():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    with mock.patch('requests.post', return_value=_fake_response(
        'analyzing...\n{"verdict":"both_acceptable","reasoning":"linha de borda"}\nfim'
    )):
        res = llm_judge.judge_spot(_finding())
    assert res['verdict'] == 'both_acceptable'
    print("OK  test_response_parse_tolerates_wrapping_text")


def test_invalid_verdict_falls_back_to_neither():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    with mock.patch('requests.post', return_value=_fake_response(
        '{"verdict":"WAT","reasoning":"x"}'
    )):
        res = llm_judge.judge_spot(_finding())
    assert res['verdict'] == 'neither'
    print("OK  test_invalid_verdict_falls_back_to_neither")


def test_cache_hit_skips_api_call():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    call_count = {'n': 0}
    def fake_post(url, json=None, headers=None, timeout=None):
        call_count['n'] += 1
        return _fake_response('{"verdict":"oracle_correct","reasoning":"first call"}')

    with mock.patch('requests.post', side_effect=fake_post):
        r1 = llm_judge.judge_spot(_finding())
        r2 = llm_judge.judge_spot(_finding())  # mesmo finding -> cache hit
    assert r1['cached'] is False
    assert r2['cached'] is True
    assert call_count['n'] == 1, f"esperava 1 chamada, recebi {call_count['n']}"
    print("OK  test_cache_hit_skips_api_call")


def test_judge_findings_budget_zero_no_calls():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    findings = [_finding(), _finding(category='no_oracle_data')]
    with mock.patch('requests.post') as p:
        n = llm_judge.judge_findings(findings, budget=0)
    assert n == 0
    assert p.call_count == 0
    print("OK  test_judge_findings_budget_zero_no_calls")


def test_judge_findings_only_processes_disputed():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    # Cada finding disputado tem combinação ÚNICA de spot para evitar cache hit cross-finding.
    findings = [
        _finding(category='aligned',         engine_best='bet', oracle_action='bet',  street='flop'),
        _finding(category='acceptable_alt',  engine_best='call', oracle_action='raise', street='turn'),
        _finding(category='major_mismatch',  engine_best='fold', oracle_action='raise', street='flop'),
        _finding(category='no_oracle_data',  engine_best='call', oracle_action=None,   street='river'),
    ]
    call_count = {'n': 0}
    def fake_post(url, json=None, headers=None, timeout=None):
        call_count['n'] += 1
        return _fake_response('{"verdict":"oracle_correct","reasoning":"ok"}')

    with mock.patch('requests.post', side_effect=fake_post):
        n = llm_judge.judge_findings(findings, budget=10)
    assert n == 2, f"esperava 2 chamadas, recebi {n}"
    # findings aligned/acceptable_alt NÃO recebem llm_verdict
    assert 'llm_verdict' not in findings[0]
    assert 'llm_verdict' not in findings[1]
    assert findings[2]['llm_verdict'] == 'oracle_correct'
    assert findings[3]['llm_verdict'] == 'oracle_correct'
    print(f"OK  test_judge_findings_only_processes_disputed (n_calls={n})")


def test_judge_findings_respects_budget_cap():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge

    # Spots distintos (street ou position diferentes) -> cada um é uma chamada nova.
    streets = ['flop', 'turn', 'river', 'flop', 'turn', 'river', 'flop', 'turn', 'river', 'flop']
    positions = ['BTN', 'CO', 'HJ', 'SB', 'BB', 'UTG', 'UTG1', 'LJ', 'MP', 'BTN']
    findings = [_finding(street=streets[i], position=positions[i],
                          severity_score=0.99 - i*0.01) for i in range(10)]
    with mock.patch('requests.post', return_value=_fake_response(
        '{"verdict":"oracle_correct","reasoning":"ok"}'
    )) as p:
        n = llm_judge.judge_findings(findings, budget=3)
    assert n == 3
    assert p.call_count == 3
    print(f"OK  test_judge_findings_respects_budget_cap (n={n})")


def test_judge_spot_raises_when_no_api_key_and_no_cache():
    _reset_db_with_cache_table()
    from leaklab.revalidation import llm_judge
    os.environ.pop('ANTHROPIC_API_KEY', None)
    try:
        # finding novo -- não tem cache -- vai tentar chamar e falhar
        threw = False
        try:
            llm_judge.judge_spot(_finding(hand_id='H_NEW'))
        except RuntimeError as e:
            threw = 'ANTHROPIC_API_KEY' in str(e)
        assert threw, "esperava RuntimeError sobre ANTHROPIC_API_KEY"
        print("OK  test_judge_spot_raises_when_no_api_key_and_no_cache")
    finally:
        os.environ['ANTHROPIC_API_KEY'] = 'test-key-xxx'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)
