"""
Testa o parser do dialeto PartyGaming (888poker / PartyPoker).

Fixtures reais (hand histories de exemplo) em tests/fixtures/, extraídas do
repositório de referência thlorenz/hhp. Cobre cash e torneio dos dois sites,
incluindo os formatos que divergem do PokerStars/GGPoker: header próprio,
ações sem ":", all-in "is all-In [x]", board separado por vírgula, e blinds em
"Blinds(sb/bb)", "Blinds-Antes(sb/bb -ante)" e "$sb/$bb".
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Detecção 888/PartyPoker está desligada por padrão (foco PS/GG); o parser
# PartyGaming segue íntegro — reativamos a flag aqui para validá-lo.
import leaklab.parser as _lkparser
_lkparser.PARTYGAMING_ENABLED = True

from leaklab.parser import parse_hand_history, _detect_site
from leaklab.hand_state_builder import build_hand_state
from leaklab.pipeline import build_decision_input
from leaklab.decision_engine_v11 import evaluate_decision

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load(fn: str) -> str:
    with open(os.path.join(FIX, fn), encoding='utf-8', errors='ignore') as f:
        return f.read()


def test_site_detection():
    assert _detect_site(_load('pp888_cash_6max.txt')) == '888poker'
    assert _detect_site(_load('pp888_tourney.txt')) == '888poker'
    assert _detect_site(_load('partypoker_cash_9max.txt')) == 'partypoker'
    assert _detect_site(_load('partypoker_tourney_stt.txt')) == 'partypoker'
    assert _detect_site(_load('partypoker_tourney_mtt.txt')) == 'partypoker'
    # 888 detectado antes de PartyPoker (header do 888 também tem "Hand History for Game")
    assert _detect_site('***** 888poker Hand History for Game 1 *****') == '888poker'
    print("OK  test_site_detection")


def test_hand_counts():
    cases = {
        'pp888_cash_6max.txt': 3,
        'pp888_tourney.txt': 1,
        'partypoker_cash_9max.txt': 5,
        'partypoker_tourney_stt.txt': 5,
        'partypoker_tourney_mtt.txt': 1,
    }
    for fn, n in cases.items():
        hands = parse_hand_history(_load(fn))
        assert len(hands) == n, f"{fn}: esperado {n} mãos, veio {len(hands)}"
    print("OK  test_hand_counts")


def test_888_tourney_fields():
    h = parse_hand_history(_load('pp888_tourney.txt'))[0]
    assert h.hand_id == '655462938'
    assert h.tournament_id == '83728678'
    assert h.button_seat == 5
    assert h.sb == 100.0 and h.bb == 200.0
    assert h.hero == 'DiggErr555'
    assert h.hero_cards == '8cQs'              # "[ 8c, Qs ]" → normalizado
    assert len(h.players) == 5
    assert h.board == ['6d', '7s', 'Kd', '5c', '8d']   # flop+turn+river acumulados
    # valor com vírgula de milhar: "raises [$1,594]" → 1594.0
    assert any(a.action == 'raises' and a.amount == 1594.0 for a in h.actions)
    print("OK  test_888_tourney_fields")


def test_party_mtt_allin_and_blinds():
    h = parse_hand_history(_load('partypoker_tourney_mtt.txt'))[0]
    assert h.tournament_id == '128730277'
    # Blinds-Antes(1 200/2 400 -400) — espaço como separador de milhar
    assert h.sb == 1200.0 and h.bb == 2400.0
    assert h.hero == 'DiggErr555' and h.hero_cards == 'ThKh'
    assert len(h.players) == 9
    # "Player is all-In  [x]" vira ação all-in com o valor
    allins = [a for a in h.actions if a.action == 'all-in']
    assert {a.amount for a in allins} == {53328.0, 202281.0}
    print("OK  test_party_mtt_allin_and_blinds")


def test_party_stt_blinds_paren():
    hands = parse_hand_history(_load('partypoker_tourney_stt.txt'))
    h = hands[0]
    # "Blinds(10/20)"
    assert h.sb == 10.0 and h.bb == 20.0
    assert h.hero == 'Hero' and h.hero_cards == '3hJs'
    # mão com showdown all-in mais à frente também deve parsear all-in
    allin_hand = next(hh for hh in hands if any(a.action == 'all-in' for a in hh.actions))
    assert any(a.amount == 425.0 for a in allin_hand.actions if a.action == 'all-in')
    print("OK  test_party_stt_blinds_paren")


def test_cash_blinds_and_board_comma():
    h = parse_hand_history(_load('partypoker_cash_9max.txt'))[0]
    # "$0.10/$0.25 USD"
    assert h.sb == 0.10 and h.bb == 0.25
    # board separado por vírgula sem espaço nas cartas
    assert h.board == ['4c', '3s', '7c', '2s', 'Qs']
    # amount com sufixo USD: "calls [$0.25 USD]" → 0.25
    assert any(a.action == 'calls' and a.amount == 0.25 for a in h.actions)

    h888 = parse_hand_history(_load('pp888_cash_6max.txt'))[0]
    assert h888.sb == 3.0 and h888.bb == 6.0
    assert h888.board == ['Qc', '6h', '5h']
    print("OK  test_cash_blinds_and_board_comma")


def test_pipeline_runs_without_crash():
    """Mãos PartyGaming devem atravessar todo o pipeline sem exceção."""
    total = errors = 0
    for fn in ['pp888_cash_6max.txt', 'pp888_tourney.txt',
               'partypoker_cash_9max.txt', 'partypoker_tourney_stt.txt',
               'partypoker_tourney_mtt.txt']:
        for h in parse_hand_history(_load(fn)):
            total += 1
            try:
                evaluate_decision(build_decision_input(build_hand_state(h)))
            except Exception:
                errors += 1
    assert errors == 0, f"{errors}/{total} mãos quebraram o pipeline"
    print(f"OK  test_pipeline_runs_without_crash ({total} mãos)")


def test_no_noise_lines_as_actions():
    """Linhas de ruído (time bank, 'has joined', 'finished in', posts) não viram ações."""
    for fn in ['partypoker_tourney_stt.txt', 'partypoker_tourney_mtt.txt',
               'partypoker_cash_9max.txt']:
        for h in parse_hand_history(_load(fn)):
            valid = {'folds', 'checks', 'calls', 'bets', 'raises', 'all-in', 'shows'}
            for a in h.actions:
                assert a.action in valid, f"{fn}: ação inválida {a.action!r} em {a.raw!r}"
                # posts de blind/ante nunca devem virar ação
                assert 'posts' not in a.raw.lower(), f"{fn}: 'posts' virou ação: {a.raw!r}"
    print("OK  test_no_noise_lines_as_actions")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
