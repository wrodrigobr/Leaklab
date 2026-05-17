"""
Testes de regressão para o sistema de classificação GTO preflop.
Cobre todos os classificadores de qualidade, o lookup de opener,
a determinação de scenario e o ajuste de labels.

Rodar:
    python tests/test_preflop_gto_quality.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import (
    _rfi_quality, _vs_rfi_quality, _vs_3bet_quality,
    _find_opener_key, analyze_preflop,
)
from leaklab.decision_engine_v11 import _preflop_gto_label_adjust

_passed = 0
_failed = 0

def _check(test_name: str, got, expected):
    global _passed, _failed
    if got == expected:
        _passed += 1
        print(f"OK  {test_name}")
    else:
        _failed += 1
        print(f"FAIL {test_name}: got={got!r}, expected={expected!r}")


# ─────────────────────────────────────────────────────────────────────────────
# _rfi_quality — ação na abertura (Raise First In)
# ─────────────────────────────────────────────────────────────────────────────

def test_rfi_in_range_raise():
    _check("rfi_in_range_raise", _rfi_quality('raise', True, 40), 'correct')

def test_rfi_in_range_jam():
    _check("rfi_in_range_jam", _rfi_quality('jam', True, 15), 'correct')

def test_rfi_in_range_call_limp():
    # Limp com mão no range é subótimo mas defensável
    _check("rfi_in_range_call_limp", _rfi_quality('call', True, 40), 'acceptable')

def test_rfi_in_range_fold():
    # Foldar mão que deveria abrir = leak
    _check("rfi_in_range_fold", _rfi_quality('fold', True, 40), 'leak')

def test_rfi_out_of_range_fold():
    # Foldar mão fora do range = correto
    _check("rfi_out_of_range_fold", _rfi_quality('fold', False, 40), 'correct')

def test_rfi_out_of_range_raise_deep():
    # Abrir mão fora do range com stack profundo = erro grave
    _check("rfi_out_of_range_raise_deep", _rfi_quality('raise', False, 50), 'major_leak')

def test_rfi_out_of_range_raise_shallow():
    # Abrir mão fora do range com stack curto = erro (não major)
    _check("rfi_out_of_range_raise_shallow", _rfi_quality('raise', False, 20), 'leak')

def test_rfi_out_of_range_jam_deep():
    _check("rfi_out_of_range_jam_deep", _rfi_quality('jam', False, 30), 'major_leak')

def test_rfi_out_of_range_jam_shallow():
    _check("rfi_out_of_range_jam_shallow", _rfi_quality('jam', False, 15), 'leak')

def test_rfi_out_of_range_call_limp():
    # BUG CORRIGIDO: limp com mão fora do range = leak (antes retornava 'acceptable')
    _check("rfi_out_of_range_call_limp", _rfi_quality('call', False, 40), 'leak')

def test_rfi_out_of_range_call_limp_short():
    _check("rfi_out_of_range_call_limp_short", _rfi_quality('call', False, 15), 'leak')

def test_rfi_stack_boundary_25bb():
    # Stack exatamente em 25bb: jam fora do range = leak (não major_leak, pois stack<=25)
    _check("rfi_stack_boundary_25bb", _rfi_quality('raise', False, 25), 'leak')

def test_rfi_stack_boundary_26bb():
    # Stack em 26bb: jam fora do range = major_leak (stack>25)
    _check("rfi_stack_boundary_26bb", _rfi_quality('raise', False, 26), 'major_leak')


# ─────────────────────────────────────────────────────────────────────────────
# _vs_rfi_quality — defendendo vs abertura (Call/3-bet/Fold)
# acoes representa o conjunto de ações recomendadas pelo GTO range data
# ─────────────────────────────────────────────────────────────────────────────

_ACOES_CALL_FOLD   = ['CALL', 'FOLD']
_ACOES_CALL_ONLY   = ['CALL']           # sem FOLD → fold com mão in-range = leak
_ACOES_3BET_FOLD   = ['THREBET', 'FOLD']
_ACOES_3BET_CALL   = ['THREBET', 'CALL', 'FOLD']
_ACOES_ALLIN_FOLD  = ['ALLIN', 'FOLD']

def test_vs_rfi_in_range_correct_call():
    _check("vs_rfi_in_range_correct_call", _vs_rfi_quality('call', True, _ACOES_CALL_FOLD), 'correct')

def test_vs_rfi_in_range_correct_3bet():
    _check("vs_rfi_in_range_correct_3bet", _vs_rfi_quality('raise', True, _ACOES_3BET_FOLD), 'correct')

def test_vs_rfi_in_range_correct_call_in_mixed():
    _check("vs_rfi_in_range_correct_call_in_mixed", _vs_rfi_quality('call', True, _ACOES_3BET_CALL), 'correct')

def test_vs_rfi_in_range_fold_when_fold_in_acoes():
    # GTO mix inclui fold como opção → foldar é correto
    _check("vs_rfi_in_range_fold_mixed", _vs_rfi_quality('fold', True, _ACOES_CALL_FOLD), 'correct')

def test_vs_rfi_in_range_fold_when_fold_not_in_acoes():
    # GTO não inclui fold como opção → foldar é leak
    _check("vs_rfi_in_range_fold_no_mix", _vs_rfi_quality('fold', True, _ACOES_CALL_ONLY), 'leak')

def test_vs_rfi_in_range_wrong_action_3bet_when_only_call():
    # BUG CORRIGIDO: mão no range mas faz 3bet quando range data recomenda só call
    _check("vs_rfi_in_range_wrong_action", _vs_rfi_quality('raise', True, _ACOES_CALL_FOLD), 'leak')

def test_vs_rfi_in_range_wrong_action_call_when_only_3bet():
    # Mão no range mas chama quando deveria 3-bet
    _check("vs_rfi_in_range_wrong_call_vs_3bet_range", _vs_rfi_quality('call', True, _ACOES_3BET_FOLD), 'leak')

def test_vs_rfi_out_of_range_fold():
    # Foldar mão fora do range = correto
    _check("vs_rfi_out_of_range_fold", _vs_rfi_quality('fold', False, _ACOES_CALL_FOLD), 'correct')

def test_vs_rfi_out_of_range_call():
    # BUG CORRIGIDO: chamar com mão fora do range = leak (antes retornava 'acceptable')
    _check("vs_rfi_out_of_range_call", _vs_rfi_quality('call', False, _ACOES_CALL_FOLD), 'leak')

def test_vs_rfi_out_of_range_3bet():
    # 3-bet com mão fora do range = major_leak
    _check("vs_rfi_out_of_range_3bet", _vs_rfi_quality('raise', False, _ACOES_3BET_FOLD), 'major_leak')

def test_vs_rfi_out_of_range_jam():
    _check("vs_rfi_out_of_range_jam", _vs_rfi_quality('jam', False, _ACOES_CALL_FOLD), 'major_leak')

def test_vs_rfi_out_of_range_call_vs_3bet_range():
    # Mão fora do range, range só tem 3-bet/fold, hero chama = leak
    _check("vs_rfi_out_of_range_call_vs_3bet_range", _vs_rfi_quality('call', False, _ACOES_3BET_FOLD), 'leak')

def test_vs_rfi_allin_in_range():
    # Mão no range e range recomenda allin
    _check("vs_rfi_allin_in_range", _vs_rfi_quality('jam', True, _ACOES_ALLIN_FOLD), 'correct')


# ─────────────────────────────────────────────────────────────────────────────
# _vs_3bet_quality — respondendo a 3-bet
# ─────────────────────────────────────────────────────────────────────────────

def test_vs_3bet_4bet_correct():
    _check("vs_3bet_4bet_correct", _vs_3bet_quality('raise', True, False), 'correct')

def test_vs_3bet_jam_correct():
    _check("vs_3bet_jam_correct", _vs_3bet_quality('jam', True, False), 'correct')

def test_vs_3bet_call_correct():
    _check("vs_3bet_call_correct", _vs_3bet_quality('call', False, True), 'correct')

def test_vs_3bet_fold_when_should_4bet():
    _check("vs_3bet_fold_when_should_4bet", _vs_3bet_quality('fold', True, False), 'leak')

def test_vs_3bet_fold_when_should_call():
    _check("vs_3bet_fold_when_should_call", _vs_3bet_quality('fold', False, True), 'leak')

def test_vs_3bet_fold_correct():
    # Fora do range de 4bet e call: fold é correto
    _check("vs_3bet_fold_correct", _vs_3bet_quality('fold', False, False), 'correct')

def test_vs_3bet_call_when_should_4bet():
    # No range de 4bet mas chamou = major_leak
    _check("vs_3bet_call_when_should_4bet", _vs_3bet_quality('call', True, False), 'major_leak')

def test_vs_3bet_4bet_when_should_call():
    # No range de call mas 4betou = major_leak
    _check("vs_3bet_4bet_when_should_call", _vs_3bet_quality('raise', False, True), 'major_leak')

def test_vs_3bet_4bet_out_of_range():
    # Fora do range de 4bet e call mas 4betou = major_leak
    _check("vs_3bet_4bet_out_of_range", _vs_3bet_quality('raise', False, False), 'major_leak')

def test_vs_3bet_in_both_ranges():
    # Mão em ambos os ranges (4bet e call) e chama = correct
    _check("vs_3bet_in_both_ranges_call", _vs_3bet_quality('call', True, True), 'correct')


# ─────────────────────────────────────────────────────────────────────────────
# _find_opener_key — lookup da chave do opener no vs_RFI dict
# ─────────────────────────────────────────────────────────────────────────────

_VS_RFI_30BB = {
    'UTG_open': {'CO': {}, 'BTN': {}},
    'CO_open':  {'BTN': {}, 'SB': {}},
    'BTN_open': {'SB': {}, 'BB': {}},
}

def test_find_opener_utg_exact():
    _check("find_opener_utg_exact", _find_opener_key(_VS_RFI_30BB, 'UTG'), 'UTG_open')

def test_find_opener_co_exact():
    _check("find_opener_co_exact", _find_opener_key(_VS_RFI_30BB, 'CO'), 'CO_open')

def test_find_opener_btn_exact():
    _check("find_opener_btn_exact", _find_opener_key(_VS_RFI_30BB, 'BTN'), 'BTN_open')

def test_find_opener_sb_not_in_json():
    # BUG CORRIGIDO: SB não existe como opener no JSON → deve retornar None (antes retornava BTN_open)
    _check("find_opener_sb_not_in_json", _find_opener_key(_VS_RFI_30BB, 'SB'), None)

def test_find_opener_empty_pos():
    # vs_position vazio → deve retornar None
    _check("find_opener_empty_pos", _find_opener_key(_VS_RFI_30BB, ''), None)

def test_find_opener_unknown_pos():
    # vs_position desconhecido → deve retornar None (sem fallback silencioso)
    _check("find_opener_unknown_pos", _find_opener_key(_VS_RFI_30BB, 'unknown'), None)

def test_find_opener_empty_dict():
    _check("find_opener_empty_dict", _find_opener_key({}, 'UTG'), None)


# ─────────────────────────────────────────────────────────────────────────────
# _preflop_gto_label_adjust — ajuste de labels pelo quality GTO
# ─────────────────────────────────────────────────────────────────────────────

def test_label_adjust_correct_upgrades_to_standard():
    # Qualquer label + correct → standard
    for lbl in ('marginal', 'small_mistake', 'clear_mistake', 'standard'):
        _check(f"label_adjust_correct_{lbl}", _preflop_gto_label_adjust(lbl, 'correct'), 'standard')

def test_label_adjust_acceptable_caps_at_marginal():
    # acceptable capeia em marginal
    _check("label_adjust_acceptable_standard",      _preflop_gto_label_adjust('standard', 'acceptable'),      'standard')
    _check("label_adjust_acceptable_marginal",      _preflop_gto_label_adjust('marginal', 'acceptable'),      'marginal')
    _check("label_adjust_acceptable_small_mistake", _preflop_gto_label_adjust('small_mistake', 'acceptable'), 'marginal')
    _check("label_adjust_acceptable_clear_mistake", _preflop_gto_label_adjust('clear_mistake', 'acceptable'), 'marginal')

def test_label_adjust_leak_floors_at_small_mistake():
    # leak eleva ao mínimo para small_mistake
    _check("label_adjust_leak_standard",      _preflop_gto_label_adjust('standard', 'leak'),      'small_mistake')
    _check("label_adjust_leak_marginal",      _preflop_gto_label_adjust('marginal', 'leak'),      'small_mistake')
    _check("label_adjust_leak_small_mistake", _preflop_gto_label_adjust('small_mistake', 'leak'), 'small_mistake')
    _check("label_adjust_leak_clear_mistake", _preflop_gto_label_adjust('clear_mistake', 'leak'), 'clear_mistake')

def test_label_adjust_major_leak_floors_at_small_mistake():
    # major_leak também eleva ao mínimo small_mistake
    _check("label_adjust_major_leak_standard",      _preflop_gto_label_adjust('standard', 'major_leak'),      'small_mistake')
    _check("label_adjust_major_leak_marginal",      _preflop_gto_label_adjust('marginal', 'major_leak'),      'small_mistake')
    _check("label_adjust_major_leak_small_mistake", _preflop_gto_label_adjust('small_mistake', 'major_leak'), 'small_mistake')
    _check("label_adjust_major_leak_clear_mistake", _preflop_gto_label_adjust('clear_mistake', 'major_leak'), 'clear_mistake')

def test_label_adjust_unknown_no_change():
    for lbl in ('standard', 'marginal', 'small_mistake', 'clear_mistake'):
        _check(f"label_adjust_unknown_{lbl}", _preflop_gto_label_adjust(lbl, 'unknown'), lbl)


# ─────────────────────────────────────────────────────────────────────────────
# analyze_preflop — determinação de scenario e integração com dados reais
# ─────────────────────────────────────────────────────────────────────────────

def test_scenario_rfi_when_no_facing():
    r = analyze_preflop('BTN', 'AKo', 40, 'raise', facing_size=0.0, vs_position='')
    _check("scenario_rfi_when_no_facing", r['scenario'], 'rfi')

def test_scenario_vs_rfi_when_facing_with_pos():
    r = analyze_preflop('CO', '88', 30, 'call', facing_size=2.5, vs_position='UTG')
    _check("scenario_vs_rfi_with_pos", r['scenario'], 'vs_rfi')

def test_scenario_vs_rfi_when_facing_without_pos():
    # BUG CORRIGIDO: facing_size > 0 sem vs_position → vs_rfi (antes era rfi)
    r = analyze_preflop('CO', '88', 30, 'call', facing_size=2.5, vs_position='')
    _check("scenario_vs_rfi_without_pos", r['scenario'], 'vs_rfi')

def test_scenario_vs_rfi_without_pos_returns_unavailable():
    # Sem vs_position, opener_key=None → available=False (não analisa com dados errados)
    r = analyze_preflop('CO', '88', 30, 'call', facing_size=2.5, vs_position='')
    _check("vs_rfi_without_pos_unavailable", r['available'], False)

def test_scenario_vs_3bet_when_is_3bet_pot():
    r = analyze_preflop('UTG', 'AA', 40, 'raise', facing_size=9.0, vs_position='BTN', is_3bet_pot=True)
    _check("scenario_vs_3bet", r['scenario'], 'vs_3bet')

def test_rfi_in_range_correct_action():
    # CO com AKo, range de abertura inclui AKo → raise = correct
    r = analyze_preflop('CO', 'AKo', 30, 'raise', facing_size=0.0)
    if r['available']:
        _check("rfi_in_range_correct_action_quality", r['action_quality'], 'correct')
    else:
        _check("rfi_in_range_correct_action_available", r['available'], True)

def test_vs_rfi_out_of_range_call_is_leak():
    # CO com 88 vs UTG open @ 30bb — 88 fora do range → call = leak
    r = analyze_preflop('CO', '88', 30, 'call', facing_size=2.5, vs_position='UTG')
    _check("vs_rfi_88_call_available", r['available'], True)
    _check("vs_rfi_88_call_in_range", r['in_range'], False)
    _check("vs_rfi_88_call_quality", r['action_quality'], 'leak')

def test_vs_rfi_in_range_fold_mixed_strategy():
    # CO com AKo vs UTG open @ 30bb — AKo no range, acoes inclui FOLD (GTO mix)
    # fold é parte do mix GTO → quality='correct'
    r = analyze_preflop('CO', 'AKo', 30, 'fold', facing_size=2.5, vs_position='UTG')
    if r['available']:
        _check("vs_rfi_AKo_fold_quality", r['action_quality'], 'correct')
    else:
        _check("vs_rfi_AKo_fold_available", r['available'], True)

def test_vs_rfi_opener_not_in_json_unavailable():
    # SB como opener não tem dados no 30bb → available=False
    r = analyze_preflop('CO', '88', 30, 'fold', facing_size=2.5, vs_position='SB')
    _check("vs_rfi_sb_opener_unavailable", r['available'], False)

def test_bb_check_free_play_no_analysis():
    # BB checa em pot não contestado → sem análise
    r = analyze_preflop('BB', 'T9s', 30, 'check', facing_size=0.0)
    _check("bb_check_free_play_unavailable", r['available'], False)

def test_rfi_correct_fold_out_of_range():
    # BTN com 72o, fora do range de abertura → fold = correct
    r = analyze_preflop('BTN', '72o', 30, 'fold', facing_size=0.0)
    if r['available']:
        _check("rfi_72o_fold_quality", r['action_quality'], 'correct')
    else:
        _check("rfi_72o_fold_available", r['available'], True)


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        try:
            t()
        except Exception as e:
            _failed += 1
            print(f"FAIL {t.__name__}: exception: {e}")

    print(f"\nTotal: {_passed + _failed} | Passed: {_passed} | Failed: {_failed}")
    sys.exit(0 if _failed == 0 else 1)
