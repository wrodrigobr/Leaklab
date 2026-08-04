# -*- coding: utf-8 -*-
"""
O pote que alimenta as pot odds, e a equity de quem nao tem nada no river.

── Defeito 1: o pote acertava 1,2% das vezes ──────────────────────────────────────────────────────

`_pot_up_to` soma o `amount` cru de cada acao, e isso erra DUAS vezes ao mesmo tempo:

  1. perde os blinds, que nao chegam como acao do parser;
  2. conta o INCREMENTO do raise (`raises 120 to 240` -> 120) em vez do total do jogador.

O numero ia para `state.pot_size`, que e o denominador das pot odds de TODO o motor.

Oraculo: a linha `Total pot` do SUMMARY. Soma-se o que cada jogador pos, desconta-se a aposta
devolvida (`Uncalled bet (X) returned` no PS/GG, `Jogador: RETURN X` no CoinPoker) e compara-se.
E medicao contra o texto do site, nao contra outra funcao nossa.

    _pot_up_to (o que o motor usava) ....   1,2% de acerto em 1.682 maos
    reconstrucao por jogador ............  99,6%

`pot_size` NAO foi trocado: ele alimenta SPR, display e a coluna do banco. So o denominador das
pot odds passou a usar o numero certo.

── Defeito 2: equity de POTENCIAL no river ────────────────────────────────────────────────────────

O estimador dava valor por "overcards vivas" -- quantas cartas ainda podem parear. **No river nao
ha carta por vir.** E o mesmo numero servia a dois spots opostos. Medido nos showdowns reais do
acervo, com o hero SEM PAR PROPRIO no river:

    high card,     river passado ...... n=24, venceu 25,0%
    high card,     pagou aposta ....... n= 0
    par do board,  river passado ...... n=16, venceu 37,5%
    par do board,  pagou aposta ....... n= 0

**Zero nos dois.** Ninguem paga aposta de river sem ter par -- o campo inteiro folda, e era
justamente esse spot que recebia 34-40%. O 0.10 e um TETO conservador de bluff-catcher, nao uma
medicao. No pote PASSADO os valores antigos batem com o campo e ficaram como estao.
"""
import os, re, sys, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedHand, ParsedAction                      # noqa: E402
from leaklab.parser import parse_hand_history                            # noqa: E402
from leaklab.hand_state_builder import (_pot_at_decision, _pot_up_to,    # noqa: E402
                                        extract_decision_points, _committed_on_street)
from leaklab.street_math_engine import _postflop_made_equity             # noqa: E402

TOTAL_RE = re.compile(r'Total pot\s+([\d.,]+)', re.IGNORECASE)
DEVOLVIDO_RE = re.compile(r'Uncalled bet \(?\s*([\d.,]+)\s*\)?\s*returned'
                          r'|^.+?:\s*RETURN\s+([\d.,]+)', re.IGNORECASE | re.MULTILINE)


def _mao(seats, actions, sb=100.0, bb=200.0, button=1, hero='Hero', antes=None):
    raw = ['PokerStars Hand #1: Tournament #1']
    raw += [f'Seat {s}: {n} ({st:,.0f} in chips)' for s, n, st in seats]
    return ParsedHand(
        hand_id='teste', hero=hero, button_seat=button, sb=sb, bb=bb, hero_cards='AsKd',
        seats=[{'seat': s, 'name': n, 'stack': st} for s, n, st in seats],
        players=[n for _, n, _ in seats],
        actions=[ParsedAction(player=p, street=stt, action=a, amount=v, raw=r)
                 for stt, p, a, v, r in actions],
        raw_text='\n'.join(raw), antes=antes or {},
    )


# ── o pote ─────────────────────────────────────────────────────────────────────────────────────────

def test_o_pote_inclui_os_blinds_que_nao_sao_acao():
    """Open de 2bb no BTN: o pote e 2 (BTN) + 0,5 (SB) + 1 (BB) = 3,5bb. `_pot_up_to` via 1,5."""
    h = _mao(
        seats=[(1, 'BTN', 20000), (2, 'SB', 20000), (3, 'Hero', 20000)],
        actions=[('preflop', 'BTN', 'raises', 400.0, 'BTN: raises 200 to 400'),
                 ('preflop', 'SB',  'folds',  None,  'SB: folds'),
                 ('preflop', 'Hero','calls',  200.0, 'Hero: calls 200')],
        button=1)
    pote = _pot_at_decision(h, h.actions, 2, 'preflop')
    assert pote == 700.0, f'400 + 100 (SB) + 200 (BB do hero) = 700, veio {pote}'
    assert _pot_up_to(h.actions, 2) == 400.0, 'o calculo antigo via so a acao do BTN'


def test_o_pote_usa_o_TOTAL_do_raise_nao_o_incremento():
    h = _mao(
        seats=[(1, 'Vilao', 20000), (3, 'Hero', 20000)],
        actions=[('preflop', 'Hero',  'raises', 400.0,  'Hero: raises 400 to 600'),
                 ('preflop', 'Vilao', 'raises', 1200.0, 'Vilao: raises 1200 to 1800'),
                 ('preflop', 'Hero',  'calls',  1200.0, 'Hero: calls 1200')],
        button=1)
    # heads-up: o botao E o SB. Hero (assento 3) e o BB.
    assert _committed_on_street(h, h.actions, 2, 'preflop', 'Hero') == 600.0
    pote = _pot_at_decision(h, h.actions, 2, 'preflop')
    assert pote == 2400.0, f'600 (hero) + 1800 (vilao) = 2400, veio {pote}'


def test_o_pote_bate_com_o_SUMMARY_do_proprio_site():
    """O guarda que fecha o caso: confronta a reconstrucao com o que o site declarou."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')
    if not os.path.exists(caminho):
        return
    maos = parse_hand_history(open(caminho, encoding='utf-8', errors='ignore').read())
    ok = velho_ok = n = 0
    for mao in maos:
        m = TOTAL_RE.search(mao.raw_text or '')
        if not m or not mao.actions:
            continue
        declarado = float(m.group(1).replace(',', ''))
        devolvido = sum(float((a or b).replace(',', ''))
                        for a, b in DEVOLVIDO_RE.findall(mao.raw_text or ''))
        ultima = mao.actions[-1].street
        novo = _pot_at_decision(mao, mao.actions, len(mao.actions), ultima) - devolvido
        n += 1
        tol = max(1.0, declarado * 0.005)
        ok       += abs(novo - declarado) <= tol
        velho_ok += abs(_pot_up_to(mao.actions, len(mao.actions)) - declarado) <= tol
    assert n >= 20, f'a fixture precisa ter maos com SUMMARY, achei {n}'
    assert ok >= n * 0.95, f'a reconstrucao bateu em so {ok}/{n}'
    assert velho_ok < n * 0.5, \
        f'`_pot_up_to` acertou {velho_ok}/{n} — se ele passou a acertar, este teste perdeu o sentido'


def test_aposta_que_o_hero_nao_cobre_nao_entra_no_pote_disputavel():
    """Vilao aposta 240 num pote de 120 e o hero so tem 150: 90 voltam pra ele."""
    from leaklab.pipeline import build_decision_input
    h = _mao(
        seats=[(3, 'Vilao', 5000), (4, 'Hero', 210)],
        # heads-up: o botao E o SB, entao o Vilao ja tem 15 na frente e paga 45 para igualar 60.
        actions=[('preflop', 'Hero',  'raises', 30.0,  'Hero: raises 30 to 60'),
                 ('preflop', 'Vilao', 'calls',  45.0,  'Vilao: calls 45'),
                 ('flop',    'Hero',  'checks', None,  'Hero: checks'),
                 ('flop',    'Vilao', 'bets',   240.0, 'Vilao: bets 240 and is all-in'),
                 ('flop',    'Hero',  'folds',  None,  'Hero: folds')],
        sb=15.0, bb=30.0, button=3)
    st = [e for e in extract_decision_points(h) if e.player_action == 'fold'][0]
    assert st.metadata['facing_excesso_devolvido'] == 90.0, st.metadata['facing_excesso_devolvido']
    po = build_decision_input(st, h)['math']['potOddsEquity']
    # paga 150 num pote efetivo de 270 -> 150/420
    assert abs(po - 150 / 420) < 0.005, f'esperado {150/420:.4f}, veio {po}'


# ── a equity de quem nao tem nada no river ─────────────────────────────────────────────────────────

_RIVER = ['9s', '8s', '4d', '3d', '5c']


def test_high_card_no_river_enfrentando_aposta_e_bluff_catcher():
    """QJs que errou o flush draw: Q-high. Valia 34% porque contava 'overcards vivas'."""
    assert _postflop_made_equity('QsJs', _RIVER, True) == 0.10


def test_o_mesmo_high_card_em_pote_PASSADO_mantem_o_valor_antigo():
    """Sem aposta na frente o numero antigo bate com o campo (24 showdowns, 25% de vitoria)."""
    assert _postflop_made_equity('QsJs', _RIVER, False) == 0.34


def test_par_so_do_BOARD_tambem_e_bluff_catcher_no_river():
    """76o em Q-3-3-x-x: o eval7 diz 'Pair' por causa do board, e o hero nao tem par nenhum."""
    board = ['Qs', '3c', '3d', '8h', '2c']
    assert _postflop_made_equity('7d6h', board, True)  == 0.10
    assert _postflop_made_equity('7d6h', board, False) == 0.40   # pote passado: como antes


def test_par_de_VERDADE_nao_e_tocado():
    """A regra vale para quem nao tem NADA de seu. Par proprio segue valendo o que valia."""
    board = ['Qs', '3c', '9d', '8h', '2c']
    assert _postflop_made_equity('Qd7h', board, True) > 0.5, 'top pair segue top pair'
    assert _postflop_made_equity('AhAd', board, True) > 0.6, 'overpair segue overpair'


def test_flop_e_turn_nao_sao_tocados():
    """No flop e no turn o potencial de melhorar e real — a regra e so do river."""
    assert _postflop_made_equity('QsJs', ['9s', '8s', '4d'], True) == 0.34
    assert _postflop_made_equity('QsJs', ['9s', '8s', '4d', '3d'], True) == 0.34


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
