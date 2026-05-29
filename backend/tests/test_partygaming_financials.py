"""
Testa a extração financeira (buy-in, prêmio, place, profit), data e nome do
torneio para 888poker e PartyPoker — funções _extract_* do app.py.

Usa as mesmas fixtures reais de tests/fixtures/ do parser PartyGaming.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock flask_cors se não disponível (mesmo padrão do test_api_endpoints)
try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from api.app import (
    _extract_financials, _extract_date, _extract_tournament_name, _detect_site
)

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load(fn: str) -> str:
    with open(os.path.join(FIX, fn), encoding='utf-8', errors='ignore') as f:
        return f.read()


def test_888_tourney_buyin_and_date():
    raw = _load('pp888_tourney.txt')
    assert _detect_site(raw) == '888poker'
    fin = _extract_financials(raw, 'DiggErr555', '888poker')
    # "Tournament #... $18.30 + $1.70" → 20.00
    assert fin['buy_in'] == 20.0
    # "*** 08 08 2016 23:03:27" (DD MM YYYY)
    assert _extract_date(raw) == '2016-08-08'
    # sem nome amigável → heurístico SNG/MTT
    assert _extract_tournament_name(raw, '888poker', fin['buy_in']) == 'SNG $20.00'
    print("OK  test_888_tourney_buyin_and_date")


def test_party_stt_winner():
    raw = _load('partypoker_tourney_stt.txt')
    assert _detect_site(raw) == 'partypoker'
    fin = _extract_financials(raw, 'Hero', 'partypoker')
    # "$1 USD Buy-in" + "Hero finished in 1 place and received $3 USD"
    assert fin['buy_in'] == 1.0
    assert fin['place'] == 1
    assert fin['prize'] == 3.0
    assert fin['profit'] == 2.0
    assert _extract_date(raw) == '2016-07-24'   # "Sunday, July 24, ... 2016"
    assert _extract_tournament_name(raw, 'partypoker', fin['buy_in']) == '$1 Sit & Go Hero'
    print("OK  test_party_stt_winner")


def test_party_mtt_busted():
    raw = _load('partypoker_tourney_mtt.txt')
    fin = _extract_financials(raw, 'DiggErr555', 'partypoker')
    # "$215 USD Buy-in" + "Player DiggErr555 finished in 840." (bustou, sem prêmio)
    assert fin['buy_in'] == 215.0
    assert fin['place'] == 840
    assert fin['prize'] == 0.0
    assert fin['profit'] == -215.0
    assert _extract_date(raw) == '2016-09-26'   # "Monday, September 26, ... 2016"
    assert _extract_tournament_name(raw, 'partypoker', fin['buy_in']) == 'Powerfest #193 - Main Event $500,000 Gtd'
    print("OK  test_party_mtt_busted")


def test_cash_has_no_tournament_financials():
    for fn, site in [('partypoker_cash_9max.txt', 'partypoker'),
                     ('pp888_cash_6max.txt', '888poker')]:
        raw = _load(fn)
        fin = _extract_financials(raw, '', site)
        assert fin['buy_in'] is None, f"{fn}: cash não deveria ter buy-in"
        assert fin['prize'] is None and fin['place'] is None
        assert _extract_tournament_name(raw, site, fin['buy_in']) is None
        # data ainda deve sair
        assert _extract_date(raw) is not None, f"{fn}: data não extraída"
    print("OK  test_cash_has_no_tournament_financials")


def test_does_not_break_pokerstars():
    """Branch novo não deve afetar extração PokerStars (site != PartyGaming)."""
    ps = (
        "PokerStars Hand #1: Tournament #999, $4.60+$0.40 USD Hold'em No Limit"
        " - Level I (10/20) - 2025/07/22 21:00:00 ET\n"
        "phpro finished the tournament in 2nd place and received $9.20.\n"
    )
    fin = _extract_financials(ps, 'phpro', 'pokerstars')
    assert fin['buy_in'] == 5.0           # 4.60 + 0.40
    assert fin['place'] == 2
    assert fin['prize'] == 9.20
    assert _extract_date(ps) == '2025-07-22'
    print("OK  test_does_not_break_pokerstars")


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
