"""
Parser CoinPoker: detecção do site (NÃO cair em ggpoker), split, id, e o GATE do bb
(blinds "(sb/bb/ante)" com barras). Sem bb → potBb/stack em FICHAS → nós GTO degenerados.
Ver [[reference_parser_bb_extraction_gate]].
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from leaklab.parser import parse_hand_history, _detect_site   # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand    # noqa: E402

SAMPLE = """CoinPoker Hand #92891200001: NLH (50/100/15) 2026/07/03 04:30:11 -05
Tournament '₮1.10 Asia Rapid Fire PKO [Turbo]' '72561' 7-max Seat #3 is the button
Seat 1: a795d8ee (10,000 in chips)
Seat 2: 00753a40 (10,000 in chips)
Seat 3: 7fcb544c (10,000 in chips)
Seat 5: Hero (10,000 in chips)
Seat 6: 14998850 (10,000 in chips)
a795d8ee: posts ante 15
Hero: posts ante 15
14998850: posts ante 15
7fcb544c: posts small blind 50
Hero: posts big blind 100
*** HOLE CARDS ***
Dealt to Hero [7c 2d]
14998850: raises 300 to 400
a795d8ee: folds
Hero: folds
14998850: RETURN 300
*** SHOWDOWN ***
14998850 collected 340 from pot
*** SUMMARY ***
Total pot 340
Board [  ]

CoinPoker Hand #92891200002: NLH (100/200/25) 2026/07/03 04:31:34 -05
Tournament '₮1.10 Asia Rapid Fire PKO [Turbo]' '72561' 7-max Seat #4 is the button
Seat 3: f9752f49 (9,985 in chips)
Seat 4: c7dc0845 (9,935 in chips)
Seat 5: Hero (9,885 in chips)
f9752f49: posts ante 25
Hero: posts small blind 100
c7dc0845: posts big blind 200
*** HOLE CARDS ***
Dealt to Hero [As 5h]
f9752f49: raises 200 to 400
Hero: calls 300
c7dc0845: folds
*** FLOP *** [6d 5d 4d]
Hero: checks
f9752f49: bets 216
Hero: calls 216
*** TURN *** [6d 5d 4d] [Qs]
Hero: checks
f9752f49: checks
*** RIVER *** [6d 5d 4d Qs] [2h]
Hero: checks
f9752f49: checks
*** SHOWDOWN ***
Hero: shows [As 5h] (a pair of Fives)
f9752f49: shows [Ah Kd] (Ace high)
Hero collected 1132 from pot
*** SUMMARY ***
Total pot 1132
Board [6d 5d 4d Qs 2h]
"""


def test_coinpoker_detected_not_ggpoker():
    """'CoinPoker Hand #' contém 'Poker Hand #' → tem que detectar coinpoker, não ggpoker."""
    assert _detect_site(SAMPLE) == "coinpoker", _detect_site(SAMPLE)
    print("OK  test_coinpoker_detected_not_ggpoker")


def test_coinpoker_bb_gate_and_fields():
    hands = parse_hand_history(SAMPLE)
    assert len(hands) == 2, len(hands)
    h0, h1 = hands
    # GATE: toda mão tem bb (das blinds "(sb/bb/ante)")
    assert h0.sb == 50 and h0.bb == 100, (h0.sb, h0.bb)
    assert h1.sb == 100 and h1.bb == 200, (h1.sb, h1.bb)
    assert not [h for h in hands if not h.bb], "mão sem bb → bug das fichas"
    # campos principais
    assert h0.hand_id == "92891200001" and h0.tournament_id == "72561"
    assert h0.button_seat == 3 and h0.hero == "Hero" and h0.hero_cards == "7c2d"
    assert h0.is_pko is True, "PKO no header"
    assert h1.board == ["6d", "5d", "4d", "Qs", "2h"]
    print("OK  test_coinpoker_bb_gate_and_fields")


def test_coinpoker_pipeline_bb_normalized():
    """O pipeline produz potBb/stack em BB (não fichas). Sano = valores baixos, não milhares."""
    h1 = parse_hand_history(SAMPLE)[1]
    inp = build_decision_inputs_for_hand(h1)
    assert inp, "sem decisões"
    spot = inp[0].get("spot", {})
    assert 0 < spot.get("effectiveStackBb", 0) < 500, spot.get("effectiveStackBb")
    assert 0 <= spot.get("potBb", 0) < 200, spot.get("potBb")   # BB, não fichas
    print("OK  test_coinpoker_pipeline_bb_normalized")


def test_replay_winner_action_has_seat():
    """Regressão: a linha do SUMMARY 'Seat N: X showed [..] and won (1,110) with ...' também
    casava a regex de assento (o '(1,110)' virava stack) e SOBRESCREVIA o roster com o nome
    corrompido → o lookup ação→assento do VENCEDOR dava None e a ação não renderizava na mesa.
    O parse de seats do replay deve PARAR no *** SUMMARY ***."""
    import os as _os
    _os.environ.setdefault('LEAKLAB_DB', tempfile.mktemp(suffix='.db'))
    try:
        import flask_cors  # noqa
    except ImportError:
        import unittest.mock as _mock
        sys.modules['flask_cors'] = _mock.MagicMock()
        sys.modules['flask_cors'].CORS = lambda app, **kw: None
    import api.app as A

    hands = parse_hand_history(SAMPLE)
    h1 = hands[1]   # mão 2 tem showdown com vencedor
    A._apply_alias_to_hand(h1, A._build_gg_alias_map(h1.raw_text, 'Hero'))
    rd = A._build_replay_data(h1, [])
    # o roster não pode ter nome corrompido por linha de summary
    for _s, d in rd['seats'].items():
        assert 'showed' not in d['player'] and 'won' not in d['player'], (d['player'])
    # toda ação de showdown/bet de um jogador com assento no roster tem 'seat' resolvido
    roster_players = {d['player'] for d in rd['seats'].values()}
    for st in rd['timeline']:
        if st.get('type') == 'action' and st.get('player') in roster_players:
            assert st.get('seat') is not None, (st.get('player'), st.get('action'))
    print("OK  test_replay_winner_action_has_seat")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
