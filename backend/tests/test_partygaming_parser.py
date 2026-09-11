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


# ── Dialeto NOVO do PartyPoker (arquivo real do Rullian, 11/09) ───────────────────────────
# `partypoker_mtt_novo.txt` sao QUATRO maos do export de verdade (3.482 maos, 36 torneios), uma
# de cada caso que quebrava: ante + all-in marcador, botao morto (sem small blind), side pot e
# pos-flop completo com bets e calls. O arquivo ja vem anonimizado pela sala (Hero, Player1..7).
#
# Antes do conserto: 0 maos parseadas, 0 com big blind, 0 acoes com valor. O cabecalho e
# `Hand History For Game <id alfanumerico>` (F maiusculo), os blinds vem no INICIO da linha do
# cabecalho, os valores em parenteses ou na forma `raises X to Y`, e `is all-In.` nao traz valor.


def _novo():
    return parse_hand_history(_load('partypoker_mtt_novo.txt'))


def test_dialeto_novo_e_detectado_e_todas_as_maos_saem():
    texto = _load('partypoker_mtt_novo.txt')
    assert _detect_site(texto) == 'partypoker', _detect_site(texto)
    maos = _novo()
    assert len(maos) == 4, len(maos)
    # id ALFANUMERICO (o dialeto antigo era numerico)
    assert maos[0].hand_id == '1789080917076n9u7twfk01', maos[0].hand_id
    assert all(m.tournament_id == '422627148' for m in maos), [m.tournament_id for m in maos]
    print('OK  test_dialeto_novo_e_detectado_e_todas_as_maos_saem')


def test_dialeto_novo_extrai_sb_bb_do_CABECALHO():
    """O PORTAO (ver `reference_parser_bb_extraction_gate`): sem bb, stack e pote ficam em FICHAS
    e os nos do solver degeneram. Aqui os blinds nao estao em `Blinds(...)` nem em `$x/$y`: estao
    no inicio da linha do cabecalho, "12500/25000 Tourney ...". Conferido no arquivo inteiro: o
    bb daqui bate com o blind POSTADO em 3.476 das 3.482 maos."""
    maos = _novo()
    assert [(m.sb, m.bb) for m in maos] == [(12500.0, 25000.0), (5000.0, 10000.0),
                                            (2500.0, 5000.0), (10000.0, 20000.0)], \
        [(m.sb, m.bb) for m in maos]
    assert all(m.bb and m.bb > 0 for m in maos), 'mao sem big blind: o portao nao pode passar'
    print('OK  test_dialeto_novo_extrai_sb_bb_do_CABECALHO')


def test_dialeto_novo_le_o_VALOR_das_acoes():
    """35.364 linhas de acao casavam e perdiam o valor: o novo escreve `calls (395615)` e
    `raises X to Y`, e a regex antiga so lia `[425]`. Valor vazio e pior que linha perdida — o
    motor calcula pote e `facing_bet` com zero."""
    maos = _novo()
    com_dinheiro = [a for m in maos for a in m.actions
                    if (a.action or '').lower() in ('calls', 'bets', 'raises', 'all-in')]
    assert com_dinheiro, 'nenhuma acao com dinheiro no fixture: o teste nao exercita nada'
    sem_valor = [(a.player, a.action, a.raw) for a in com_dinheiro if not a.amount]
    assert not sem_valor, ('acao com dinheiro e sem valor', sem_valor[:4])
    # `raises 279610 to 279610` vale o TOTAL (o "to")
    r = next(a for a in maos[0].actions if a.player == 'Player4')
    assert r.amount == 279610.0, (r.action, r.amount)
    # `calls (10000)` — valor em parenteses
    c = next(a for a in maos[1].actions if (a.action or '').lower() == 'calls')
    assert c.amount == 10000.0, (c.player, c.amount)
    print('OK  test_dialeto_novo_le_o_VALOR_das_acoes')


def test_o_all_in_do_dialeto_novo_e_MARCADOR_da_acao_anterior():
    """`P is all-In.` nao traz valor, e em 1.369 de 1.377 linhas do arquivo real e marcador da
    acao anterior DO MESMO jogador: o valor esta na linha de cima. Tratar como acao nova daria a
    mao uma decisao que nao existiu, com valor nenhum."""
    maos = _novo()
    # mao 1: "Player4 raises 279610 to 279610" + "Player4 is all-In."
    do_p4 = [a for a in maos[0].actions if a.player == 'Player4']
    assert len(do_p4) == 1, ('o marcador virou acao a mais', [(a.action, a.amount) for a in do_p4])
    assert do_p4[0].action == 'all-in' and do_p4[0].amount == 279610.0, (do_p4[0].action,
                                                                        do_p4[0].amount)
    # mao 3 (side pot): tres jogadores all-in, cada um com o valor da propria acao
    valores = {a.player: a.amount for a in maos[2].actions if (a.action or '').lower() == 'all-in'}
    assert valores == {'Player6': 73207.0, 'Player1': 34496.0, 'Hero': 136268.0}, valores
    print('OK  test_o_all_in_do_dialeto_novo_e_MARCADOR_da_acao_anterior')


def test_dialeto_novo_captura_ante_assentos_e_cartas_reveladas():
    """Tres coisas que o parser Party nunca preenchia e o motor usa: o ante (dead money no pote,
    23.421 linhas no arquivo), o stack inicial por assento (mesa fiel e stack efetivo) e as
    cartas reveladas do vilao (2.159 linhas — era tudo o que se sabia dele)."""
    maos = _novo()
    m = maos[0]
    assert len(m.antes) == 7 and set(m.antes.values()) == {3000.0}, m.antes
    assert sum(m.antes.values()) == 21000.0, sum(m.antes.values())
    assert len(m.seats) == 7, m.seats
    assert m.seats[1] == {'seat': 2, 'name': 'Hero', 'stack': 336615.0}, m.seats[1]
    # blind postado NAO entra como acao (e o valor ja veio do cabecalho)
    assert not [a for a in m.actions if 'blind' in (a.raw or '')], \
        [a.raw for a in m.actions if 'blind' in (a.raw or '')]
    # cartas reveladas na linha de balance do summary
    rev = maos[2].reveals
    assert rev.get('Hero') == ['Td', 'Tc'], rev
    assert rev.get('Player1') == ['4s', '6s'] and rev.get('Player6') == ['Ts', 'Ks'], rev
    print('OK  test_dialeto_novo_captura_ante_assentos_e_cartas_reveladas')


def test_botao_morto_nao_inventa_small_blind():
    """87 das 3.482 maos nao tem linha de small blind: assento vazio no meio da mesa (6 de 7
    jogadores), o botao morto que a casa ja conhece. O parser nao pode inventar o post nem perder
    o bb do cabecalho."""
    m = _novo()[1]
    assert m.sb == 5000.0 and m.bb == 10000.0, (m.sb, m.bb)     # do cabecalho, nao do post
    assert len(m.seats) == 6, m.seats                            # 6 de 7: o assento 6 nao existe
    assert [s['seat'] for s in m.seats] == [1, 2, 3, 4, 5, 7], [s['seat'] for s in m.seats]
    print('OK  test_botao_morto_nao_inventa_small_blind')


def test_buyin_do_dialeto_novo_e_o_resultado_que_NAO_existe():
    """O buy-in do dialeto novo vem do cabecalho, "(Buyin $5.0 + $0.5)", somando buy-in e rake
    como nas outras salas — seis variacoes no arquivo real, nenhuma com tres parcelas.

    E colocacao e premio ficam VAZIOS de proposito: medido no arquivo inteiro, zero ocorrencias de
    qualquer palavra de resultado (`finished`, `place`, `won`, `prize`). O formato nao traz, e
    assumir busted seria inventar prejuizo — o mesmo tratamento que o ACR ja tem."""
    from api.app import _extract_financials
    texto = "\n".join(m.raw_text for m in _novo())
    f = _extract_financials(texto, 'Hero', 'partypoker', None)
    assert f['buy_in'] == 5.5, f
    assert f['place'] is None and f['prize'] is None, ('o formato nao traz resultado', f)
    print('OK  test_buyin_do_dialeto_novo_e_o_resultado_que_NAO_existe')


def test_pipeline_do_dialeto_novo_produz_decisao_SA():
    """Parser lendo o arquivo nao e compatibilidade. O que decide e a decisao: posicao conhecida e
    stack em BB plausivel. Medido nas 400 primeiras maos do arquivo real: 548 decisoes, zero
    posicao invalida, zero stack implausivel, mediana de 28,9bb. Se os blinds estivessem errados,
    o stack viria em MILHARES — e a casa tem cicatriz disso (nos GTO degenerados)."""
    from leaklab.pipeline import build_decision_inputs_for_hand
    POSICOES = {'UTG', 'UTG+1', 'UTG+2', 'MP1', 'MP2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}
    vistas = 0
    for m in _novo():
        for di in (build_decision_inputs_for_hand(m) or []):
            vistas += 1
            spot, ctx = di.get('spot') or {}, di.get('context') or {}
            pos = spot.get('position') or ctx.get('position') or ''
            assert pos in POSICOES, (pos, m.hand_id)
            s = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 0)
            assert 0 < s <= 500, ('stack em FICHAS, nao em bb', s, m.hand_id)
    assert vistas >= 3, ('o fixture nao produziu decisao do heroi', vistas)
    print('OK  test_pipeline_do_dialeto_novo_produz_decisao_SA (%d decisoes)' % vistas)


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
    raise SystemExit(1 if failed else 0)
