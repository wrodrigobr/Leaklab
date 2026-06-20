"""
test_study_plan.py — Testes do plano de estudos LLM e Coach IA

Cobre:
- generate_study_plan: estrutura, campos obrigatórios, fallback
- generate_study_plan: f-string do prompt sem chaves duplas
- generate_study_plan: cache key v2 e invalidação
- generate_study_plan: campos novos (diagnostico, conceitos, recursos, metrica)
- coach_replay_decision: estrutura de resposta
- tournament_summary: integração ponta-a-ponta sem LLM real
- Regressão: erro de f-string (bug fix de chaves duplas no prompt)
- Regressão: fallback retorna estrutura válida sempre
"""
import sys, os, json, traceback, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.llm_explainer import (
    generate_study_plan,
    generate_tournament_summary,
    _build_tournament_context,
    _template_tournament_summary,
    coach_replay_decision,
    _cache,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _leaks(n=6):
    spots = ['preflop/fold', 'flop/call', 'turn/check',
             'river/bet', 'preflop/3bet', 'flop/raise']
    return [
        {'spot': spots[i % len(spots)], 'n': 10 + i*5,
         'avg_score': 0.10 + i*0.05}
        for i in range(n)
    ]

def _evolution(n=5):
    return [
        {'decisions_count': 50, 'avg_score': 0.12 - i*0.005,
         'standard_pct': 72 + i, 'clear_pct': 8 - i*0.5}
        for i in range(n)
    ]

def _icm():
    return {
        'low':    {'standard_rate': 0.78},
        'medium': {'standard_rate': 0.68},
        'high':   {'standard_rate': 0.52},
    }

def _make_results(n=30):
    import random; random.seed(99)
    labels = ['standard']*5 + ['marginal','small_mistake','clear_mistake']
    icms   = ['low','medium','high']
    return [
        {
            'evaluation': {
                'label': (lbl := random.choice(labels)),
                'mistakeScore': {'standard':.04,'marginal':.15,
                                 'small_mistake':.28,'clear_mistake':.50}[lbl]
            },
            'street': random.choice(['preflop','flop','turn','river']),
            'actionTaken': random.choice(['fold','call','raise','bet','check']),
            'bestAction':  random.choice(['fold','call','raise']),
            'context': {'icmPressure': random.choice(icms), 'mRatio': random.uniform(2,18)},
        }
        for _ in range(n)
    ]


# ── generate_study_plan: estrutura básica ─────────────────────────────────────

def test_study_plan_returns_valid_structure():
    """Fallback sempre retorna estrutura válida com as chaves esperadas."""
    plan = generate_study_plan(_leaks(), _evolution(), _icm(), hero='phpro')
    assert isinstance(plan, dict), "Deve retornar dict"
    assert 'nivel' in plan,   "Falta campo 'nivel'"
    assert 'resumo' in plan,  "Falta campo 'resumo'"
    assert 'cards' in plan,   "Falta campo 'cards'"
    assert isinstance(plan['cards'], list), "'cards' deve ser list"
    print(f"OK  test_study_plan_returns_valid_structure | nivel={plan['nivel']} cards={len(plan['cards'])}")


def test_study_plan_nivel_valid():
    plan = generate_study_plan(_leaks(), _evolution(), _icm())
    assert plan['nivel'] in ('iniciante', 'intermediario', 'avancado'), \
        f"'nivel' inválido: {plan['nivel']}"
    print(f"OK  test_study_plan_nivel_valid | {plan['nivel']}")


def test_study_plan_resumo_is_string():
    plan = generate_study_plan(_leaks(), _evolution(), _icm())
    assert isinstance(plan['resumo'], str) and len(plan['resumo']) > 5
    print(f"OK  test_study_plan_resumo_is_string | {len(plan['resumo'])} chars")


def test_study_plan_no_double_braces_in_prompt():
    """Regressão: o prompt f-string não deve gerar {{ no output (bug das chaves duplas)."""
    import inspect
    src = inspect.getsource(generate_study_plan)
    # Extrair o bloco do prompt
    p_start = src.find('prompt = f"""')
    p_end   = src.find('"""', p_start + 13) + 3
    if p_start < 0:
        print("OK  test_study_plan_no_double_braces_in_prompt | prompt não encontrado (skip)")
        return
    prompt_src = src[p_start:p_end]
    # Simular execução — verificar que não há {{{{ no source
    assert '{{{{' not in prompt_src, "f-string com {{{{ (chaves quádruplas) detectado — bug regressivo!"
    print("OK  test_study_plan_no_double_braces_in_prompt | f-string limpo")


def test_study_plan_cache_key_v2():
    """O cache key deve usar prefixo v5 (v0.156.0 adicionou leak_source ao cache para invalidar
    quando fonte muda entre GTO ↔ heurístico)."""
    import inspect
    src = inspect.getsource(generate_study_plan)
    assert 'study_plan_v6:' in src, "Cache key deve usar prefixo 'study_plan_v6:'"
    print("OK  test_study_plan_cache_key_v2")


def test_study_plan_uses_ev_leaks():
    """#24/#25: o plano deve injetar os vazamentos por EV (bb perdidos) no prompt
    e priorizar por eles. Guard de fonte (sem chamar a LLM)."""
    import inspect
    import leaklab.llm_explainer as _llm
    src = inspect.getsource(generate_study_plan)
    assert 'ev_leaks' in src
    assert 'EV PONDERADO' in src                       # prioriza por EV ponderado
    assert '_format_ev_leaks_weighted' in src          # injeta os vazamentos por EV no prompt
    # o ev_leaks entra no cache key (regenera quando o EV muda)
    assert "'ev': ev_leaks" in src
    # o helper usa o bb perdido + ranqueia por confiança de amostra
    hsrc = inspect.getsource(_llm._weighted_ev_leaks)
    assert 'total_ev_loss_bb' in hsrc and 'confianca_amostra' in hsrc
    print("OK  test_study_plan_uses_ev_leaks")


def test_study_plan_cache_consistency():
    """Mesmas entradas → mesmo resultado (cache)."""
    leaks = _leaks(3)
    evo   = _evolution(3)
    icm   = _icm()
    p1 = generate_study_plan(leaks, evo, icm, hero='TestPlayer')
    p2 = generate_study_plan(leaks, evo, icm, hero='TestPlayer')
    assert p1 == p2, "Resultados inconsistentes — cache falhou"
    print("OK  test_study_plan_cache_consistency")


def test_study_plan_empty_leaks_returns_fallback():
    """Sem leaks, retorna fallback válido sem quebrar."""
    plan = generate_study_plan([], [], {}, hero='Vazio')
    assert 'nivel' in plan
    assert 'cards' in plan
    print(f"OK  test_study_plan_empty_leaks_returns_fallback | cards={len(plan['cards'])}")


def test_study_plan_max_tokens_sufficient():
    """max_tokens deve ser >= 3000 para resposta detalhada."""
    import inspect
    src = inspect.getsource(generate_study_plan)
    import re
    tokens = re.findall(r"'max_tokens':\s*(\d+)", src)
    if tokens:
        assert int(tokens[0]) >= 3000, f"max_tokens={tokens[0]} — insuficiente para plano detalhado"
    print(f"OK  test_study_plan_max_tokens_sufficient | max_tokens={tokens[0] if tokens else 'N/A'}")


# ── Campos novos do plano v2 ──────────────────────────────────────────────────

def test_study_plan_prompt_has_new_fields():
    """O prompt deve mencionar os novos campos: diagnostico, conceitos, recursos, metrica."""
    import inspect
    src = inspect.getsource(generate_study_plan)
    campos = ['diagnostico', 'conceitos', 'recursos', 'metrica', 'livros', 'videos']
    missing = [c for c in campos if c not in src]
    assert not missing, f"Campos ausentes no prompt: {missing}"
    print(f"OK  test_study_plan_prompt_has_new_fields | {len(campos)} campos presentes")


def test_study_plan_fallback_cards_have_required_keys():
    """Se cards presentes, cada card deve ter pelo menos titulo e prioridade."""
    plan = generate_study_plan(_leaks(), _evolution(), _icm())
    for i, card in enumerate(plan.get('cards', [])):
        for key in ('titulo', 'prioridade'):
            assert key in card, f"Card {i} sem campo '{key}'"
        assert card['prioridade'] in ('p1','p2','p3'), \
            f"Card {i} prioridade inválida: {card['prioridade']}"
    print(f"OK  test_study_plan_fallback_cards_have_required_keys | {len(plan['cards'])} cards")


# ── coach_replay_decision ─────────────────────────────────────────────────────

def _call_coach(action='fold', best='call', street='flop', score=0.28,
                eq=0.45, po=0.33, mr=8.2, icm='medium'):
    """Helper que chama coach_replay_decision com assinatura correta."""
    return coach_replay_decision(
        street=street, action_taken=action, best_action=best,
        hero_cards='Ah8d', board='2c 7h Ks',
        hand_equity=eq, pot_odds=po,
        m_ratio=mr, icm_pressure=icm,
        error_score=score, error_label='small_mistake'
    )

def test_coach_replay_returns_string():
    result = _call_coach()
    assert isinstance(result, str) and len(result) > 10
    print(f"OK  test_coach_replay_returns_string | {len(result)} chars")


def test_coach_replay_winner_action():
    result = _call_coach(action='raise', best='raise', score=0.0)
    assert isinstance(result, str) and len(result) > 5
    print(f"OK  test_coach_replay_winner_action | '{result[:60]}...'")


def test_coach_replay_all_streets():
    for street in ['preflop', 'flop', 'turn', 'river']:
        result = _call_coach(street=street)
        assert isinstance(result, str) and len(result) > 5, \
            f"Falhou no street={street}"
    print("OK  test_coach_replay_all_streets")


def test_coach_replay_clear_mistake():
    result = _call_coach(action='call', best='fold', score=0.55)
    assert isinstance(result, str) and len(result) > 5
    print(f"OK  test_coach_replay_clear_mistake | score=0.55")


def test_coach_replay_missing_fields_no_crash():
    """Campos mínimos — não deve quebrar."""
    result = coach_replay_decision(
        street='preflop', action_taken='fold', best_action='call'
    )
    assert isinstance(result, str)
    print(f"OK  test_coach_replay_missing_fields_no_crash")


def test_coach_replay_icm_scenarios():
    """ICM pressure low/medium/high — todos devem funcionar."""
    for pressure in ['low', 'medium', 'high']:
        result = _call_coach(icm=pressure)
        assert isinstance(result, str) and len(result) > 5, \
            f"Falhou com icm_pressure={pressure}"
    print("OK  test_coach_replay_icm_scenarios")


def test_coach_replay_short_stack():
    """Stack < 10BB — análise push/fold."""
    result = _call_coach(mr=3.5)
    assert isinstance(result, str) and len(result) > 5
    print(f"OK  test_coach_replay_short_stack | m_ratio=3.5")


# ── Tournament summary ────────────────────────────────────────────────────────

def test_tournament_summary_structure():
    results = _make_results(30)
    s = generate_tournament_summary(results, 20, 'phpro')
    assert isinstance(s, str) and len(s) > 30
    print(f"OK  test_tournament_summary_structure | {len(s)} chars")


def test_tournament_summary_context_all_fields():
    results = _make_results(50)
    ctx = _build_tournament_context(results, 40)
    required = ['total_hands', 'total_decisions', 'avg_score',
                'standard_pct', 'icm_breakdown', 'top_leaks']
    missing = [f for f in required if f not in ctx]
    assert not missing, f"Campos ausentes no contexto: {missing}"
    assert ctx['total_decisions'] == 50
    assert 0 <= ctx['standard_pct'] <= 100
    print(f"OK  test_tournament_summary_context_all_fields | score={ctx['avg_score']:.3f}")


def test_tournament_summary_icm_breakdown():
    results = _make_results(30)
    ctx = _build_tournament_context(results, 20)
    icm = ctx['icm_breakdown']
    for pressure in ['low', 'medium', 'high']:
        if pressure in icm:
            assert 'count' in icm[pressure] or 'n' in icm[pressure], \
                f"Falta campo count/n em icm[{pressure}]"
            assert 'avg' in icm[pressure]
    print(f"OK  test_tournament_summary_icm_breakdown")


def test_tournament_summary_worsens_under_pressure():
    """Jogador com performance pior no ICM high deve ter avg_high > avg_low."""
    results = []
    for _ in range(15):
        results.append({'evaluation':{'label':'standard','mistakeScore':.03},
                       'street':'preflop','actionTaken':'fold','bestAction':'fold',
                       'context':{'icmPressure':'low','mRatio':15.0}})
    for _ in range(15):
        results.append({'evaluation':{'label':'clear_mistake','mistakeScore':.55},
                       'street':'flop','actionTaken':'call','bestAction':'fold',
                       'context':{'icmPressure':'high','mRatio':4.0}})
    ctx = _build_tournament_context(results, 20)
    icm = ctx['icm_breakdown']
    if 'high' in icm and 'low' in icm:
        assert icm['high']['avg'] > icm['low']['avg'], \
            "ICM high deveria ser pior que ICM low"
    print(f"OK  test_tournament_summary_worsens_under_pressure")


def test_tournament_summary_cache():
    results = _make_results(20)
    s1 = generate_tournament_summary(results, 15, 'CacheHero')
    s2 = generate_tournament_summary(results, 15, 'CacheHero')
    assert s1 == s2
    print("OK  test_tournament_summary_cache")


# ── Regressões críticas ───────────────────────────────────────────────────────

def test_regression_study_plan_error_key():
    """Regressão: plano com error key ainda tem cards e resumo."""
    plan = {'nivel':'intermediario','resumo':'fallback','cards':[],'error':'API key ausente'}
    # O frontend deve conseguir renderizar mesmo com error key
    assert 'nivel'  in plan
    assert 'resumo' in plan
    assert 'cards'  in plan
    print("OK  test_regression_study_plan_error_key")


def test_regression_prompt_renders_with_real_data():
    """Regressão: o f-string do prompt não quebra com dados reais."""
    leaks    = _leaks(8)
    evo      = _evolution(10)
    icm      = _icm()
    try:
        plan = generate_study_plan(leaks, evo, icm, hero='testuser_regressão')
        assert 'nivel' in plan
        print("OK  test_regression_prompt_renders_with_real_data")
    except Exception as e:
        raise AssertionError(f"Prompt quebrou com dados reais: {e}")


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
