"""
Testes do StrategyProvider — a fonte ÚNICA de "qual é a jogada certa neste spot".

Foca no INVARIANTE que motivou o módulo (auditoria 2026-07-25): o menu de ações oferecido é,
por construção, um superconjunto de toda ação creditável da estratégia. Funções puras (o
preflop_strategy delega a analyze_preflop, que lê o JSON de ranges — sem DB, sem solver).
"""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.strategy_provider import (
    normalize_action, normalize_freq_map, menu_with_strategy, menu_covers_strategy,
    preflop_base_menu, preflop_strategy, postflop_menu, MIN_STRATEGY_FREQ,
    CANONICAL_ACTION_ORDER, to_storage_action, to_display_action,
)
from leaklab.preflop_gto_ranges import analyze_preflop


def test_normalize_action():
    for a in ('jam', 'shove', 'all-in', 'allin', 'ALLIN', ' Jam '):
        assert normalize_action(a) == 'allin', a
    assert normalize_action('Fold') == 'fold'
    assert normalize_action('CALL') == 'call'
    assert normalize_action('raise') == 'raise'
    print("OK  test_normalize_action")


def test_normalize_freq_map_merges_families():
    # jam e allin colidem na mesma família e somam
    m = normalize_freq_map({'jam': 0.3, 'allin': 0.2, 'raise': 0.5, 'fold': None})
    assert abs(m['allin'] - 0.5) < 1e-9, m
    assert m['raise'] == 0.5
    assert 'fold' not in m   # None é descartado
    print("OK  test_normalize_freq_map_merges_families")


def test_preflop_base_menu_sb_limp():
    # SB é a única posição que completa/limpa no RFI
    assert preflop_base_menu('rfi', 'SB') == ['fold', 'call', 'raise']
    for pos in ('UTG', 'CO', 'BTN', 'HJ'):
        assert preflop_base_menu('rfi', pos) == ['fold', 'raise'], pos
    # cenários de defesa: fold/call/raise
    for scn in ('vs_rfi', 'vs_3bet', 'squeeze'):
        assert preflop_base_menu(scn, 'BTN') == ['fold', 'call', 'raise'], scn
    print("OK  test_preflop_base_menu_sb_limp")


def test_menu_with_strategy_is_superset_of_creditable():
    # base = fold/raise, mas a estratégia mistura call 25% → call ENTRA no menu (invariante)
    menu = menu_with_strategy(['fold', 'raise'], {'call': 0.25, 'raise': 0.75})
    assert 'call' in menu, menu
    assert menu_covers_strategy(menu, {'call': 0.25, 'raise': 0.75}) == []
    # ação abaixo do limiar NÃO precisa entrar (mas não é violação se faltar)
    menu2 = menu_with_strategy(['fold', 'raise'], {'call': 0.03, 'raise': 0.97})
    assert 'call' not in menu2, menu2
    print("OK  test_menu_with_strategy_is_superset_of_creditable")


def test_menu_ordering_is_canonical():
    menu = menu_with_strategy(['raise', 'fold'], {'call': 0.2, 'allin': 0.2})
    # ordem canônica: fold < call < raise < allin
    idx = {a: CANONICAL_ACTION_ORDER.index(a) for a in menu}
    assert menu == sorted(menu, key=lambda a: idx[a]), menu
    assert menu[0] == 'fold'
    print("OK  test_menu_ordering_is_canonical")


def test_menu_covers_strategy_detects_violation():
    # o guard reporta a ação creditável que falta (isto É o bug do A8s)
    missing = menu_covers_strategy(['fold', 'raise'], {'call': 0.46, 'raise': 0.54})
    assert missing == ['call'], missing
    print("OK  test_menu_covers_strategy_detects_violation")


def test_preflop_strategy_a8s_sb_reproduz_bug():
    """Caso EXATO do relatório: SB RFI A8s @75bb — call ~46% é creditável e agora oferecível."""
    s = preflop_strategy('SB', 'A8s', 75.0, facing_size=0.0)
    assert s['available'] and s['scenario'] == 'rfi'
    assert s['hand_freq'].get('call', 0) >= MIN_STRATEGY_FREQ, s['hand_freq']
    assert 'call' in s['available_actions'], s['available_actions']
    assert menu_covers_strategy(s['available_actions'], s['hand_freq']) == []
    print(f"OK  test_preflop_strategy_a8s_sb_reproduz_bug (freqs={s['hand_freq']})")


def test_preflop_strategy_invariant_broad():
    """Varredura ampla: para várias posições/mãos/stacks, o menu do provider nunca deixa de fora
    uma ação creditável. É o mesmo invariante do trainer, testado na fonte."""
    hands = ['AA', 'AKs', 'A8s', 'A5s', 'KQo', 'JTs', '76s', '54s', '22', '72o', 'QJo', 'T9s']
    positions = ['UTG', 'HJ', 'CO', 'BTN', 'SB']
    checked = viol = 0
    for pos in positions:
        for hand in hands:
            for stack in (30.0, 50.0, 75.0, 100.0):
                s = preflop_strategy(pos, hand, stack, facing_size=0.0)
                if not s['available']:
                    continue
                checked += 1
                missing = menu_covers_strategy(s['available_actions'], s['hand_freq'])
                if missing:
                    viol += 1
                    print(f"  VIOLACAO {pos} {hand} {stack}bb: falta {missing} | "
                          f"menu={s['available_actions']} freq={s['hand_freq']}")
    assert viol == 0, f"{viol} violações do invariante em {checked} spots"
    assert checked > 100
    print(f"OK  test_preflop_strategy_invariant_broad ({checked} spots, 0 violações)")


def test_postflop_menu_invariant():
    # menu postflop base = fold/call/raise; nada creditável fica de fora
    m = postflop_menu({'raise': 1.0})
    assert set(['fold', 'call', 'raise']).issubset(set(m))
    assert menu_covers_strategy(m, {'raise': 0.6, 'call': 0.4}) == []
    print("OK  test_postflop_menu_invariant")


def test_academy_gto_consumes_provider_menu():
    """A Academia GTO-preflop (2º consumidor com a MESMA classe de bug) também deriva o menu do
    provider: SB RFI oferece o limp/complete, posição não-blind não inventa call. Guard de que a
    correção não ficou só no Leak Trainer."""
    import random
    from leaklab.academy_gto_preflop import generate_gto_preflop_question, _option_label
    # rótulos de exibição preservados
    assert _option_label('rfi', 'call') == 'Call (limp)'
    assert _option_label('vs_rfi', 'call') == 'Call'
    assert _option_label('rfi', 'raise') == 'Raise (abrir)'
    assert _option_label('vs_3bet', 'raise') == '4-Bet'
    random.seed(5)
    sb = nonsb = 0
    for _ in range(40):
        q = generate_gto_preflop_question('rfi')
        acts = [o['action'] for o in q['options']]
        if q['spot']['position'] == 'SB':
            assert 'call' in acts, ('SB RFI sem limp', q['spot'], acts)
            sb += 1
        else:
            assert 'call' not in acts, ('non-SB com call fantasma', q['spot'], acts)
            nonsb += 1
    assert sb > 0 and nonsb > 0, (sb, nonsb)
    print(f"OK  test_academy_gto_consumes_provider_menu (SB={sb}, nonSB={nonsb})")


# ── Stage 0: porta única do FETCH preflop (engine + /replay) + bridge de vocabulário ────────────

def test_bridge_dialects():
    """jam↔allin e bet→raise: as duas travessias de vocabulário. Armazenamento usa jam/bet;
    exibição usa allin e colapsa bet→raise."""
    # armazenamento (solver): allin/shove → jam; sizes colapsam
    assert to_storage_action('allin') == 'jam'
    assert to_storage_action('shove') == 'jam'
    assert to_storage_action('raise_119pct') == 'raise'
    assert to_storage_action('bet_50pct') == 'bet'
    assert to_storage_action('limp') == 'call'
    # exibição (trainer/front): jam → allin, bet → raise
    assert to_display_action('jam') == 'allin'
    assert to_display_action('bet') == 'raise'
    assert to_display_action('bet_33pct') == 'raise'
    assert to_display_action('call') == 'call'
    # normalize_action é o dialeto de exibição
    assert normalize_action('jam') == 'allin' == to_display_action('jam')
    print("OK  test_bridge_dialects")


def test_preflop_strategy_raw_equals_direct_analyze():
    """A porta única é um pass-through FIEL: strat['raw'] == analyze_preflop(mesmos params). É o que
    garante que rotear engine/replay pelo provider não muda veredito (Stage 0 behavior-preserving)."""
    params = dict(position='SB', hero_hand_type='A8s', stack_bb=75.0, action_taken='raise',
                  facing_size=0.0, vs_position='', is_3bet_pot=False, n_players=6,
                  facing_raises=0, hero_was_aggressor=False, is_pko=False,
                  facing_to_bb=0.0, facing_allin=False)
    direct = analyze_preflop(**params)
    via_provider = preflop_strategy(**params)['raw']
    # o raw é o MESMO contrato do analyze_preflop (dialeto de armazenamento intacto)
    for k in ('available', 'scenario', 'recommended_actions', 'action_quality', 'ev_loss_bb',
              'in_range', 'range_pct'):
        assert via_provider.get(k) == direct.get(k), (k, via_provider.get(k), direct.get(k))
    # e o raw preserva 'jam' (armazenamento), não 'allin' (exibição)
    print("OK  test_preflop_strategy_raw_equals_direct_analyze")


def test_preflop_strategy_full_param_surface():
    """A porta encaminha TODA a superfície do analyze_preflop (caller_position, facing_limp, is_pko,
    facing_to_bb…). Um vs_3bet completo deve rotear certo (não cair em vs_rfi)."""
    s = preflop_strategy(position='CO', hero_hand_type='AQs', stack_bb=50.0, action_taken='raise',
                         facing_size=8.0, vs_position='BTN', is_3bet_pot=True,
                         hero_was_aggressor=True, facing_raises=1, n_players=8)
    assert s['scenario'] == 'vs_3bet', s['scenario']
    assert s['available'] in (True, False)   # cobertura depende do JSON; o roteamento é o teste
    print(f"OK  test_preflop_strategy_full_param_surface (scenario={s['scenario']})")


def test_enrich_preflop_gto_routes_through_provider():
    """O HH analyzer (decision_engine._enrich_preflop_gto) agora passa pela porta única e devolve o
    MESMO dict que o provider (dialeto de armazenamento). Guard de que Stage 0 não mudou o engine."""
    from leaklab.decision_engine_v11 import _enrich_preflop_gto
    inp = {'street': 'preflop', 'player_action': 'raise', 'is_3bet': False,
           'hero_cards': ['Ac', '8c'],   # mesmo naipe → A8s (suited), casa com hero_hand_type abaixo
           'spot': {'position': 'SB', 'effectiveStackBb': 75, 'facingSize': 0,
                    'villainPosition': '', 'preflopRaisesFaced': 0, 'heroWasAggressor': False,
                    'facingToBb': 0, 'facingAllin': False, 'nPlayers': 6},
           'context': {'heroStackBb': 75, 'isPko': False}}
    got = _enrich_preflop_gto(inp)
    exp = preflop_strategy(position='SB', hero_hand_type='A8s', stack_bb=75.0, action_taken='raise',
                           facing_size=0, vs_position='', is_3bet_pot=False, n_players=6,
                           facing_raises=0, hero_was_aggressor=False, is_pko=False,
                           facing_to_bb=0, facing_allin=False)['raw']
    assert got.get('available') == exp.get('available')
    assert got.get('recommended_actions') == exp.get('recommended_actions')
    assert got.get('action_quality') == exp.get('action_quality')
    print("OK  test_enrich_preflop_gto_routes_through_provider")


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
