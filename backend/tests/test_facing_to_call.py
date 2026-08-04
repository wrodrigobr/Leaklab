# -*- coding: utf-8 -*-
"""
`facing_bet` e o TAMANHO da aposta do vilao; o CUSTO de paga-la e outro numero.

── O caso ─────────────────────────────────────────────────────────────────────────────────────────

Mao 93440400037 (CoinPoker). Hero sobe para 1.600, um vilao paga, outro faz all-in. O proprio
historico diz quanto o hero pagou:

    Hero: raises 1,200 to 1,600
    0450b46f: calls 1,600
    1f32e0e3: ALLIN 1,677.41
    Hero: calls 277.41          <-- 0,69bb

O motor gravava `facingToBb = 4,19` e calculava as pot odds em cima de 1.677 fichas: equity exigida
de 27,2% para uma decisao que custa 5,4%. Cinco vezes mais.

Os dois numeros tem uso e NAO se substituem:

  · `facingToBb`    — to-total do vilao. Identifica o NO: uma aposta "to 12bb" e o mesmo no
                      independente de quem ja pos quanto. Entra no `spot_hash`, e por isso nao foi
                      mexido (trocar re-chaveia e invalida solve — ver [[project_board_hash_bug]]).
  · `facingToCallBb`— o que sai do bolso. Manda nas pot odds.

── O oraculo ──────────────────────────────────────────────────────────────────────────────────────

Quando o hero PAGA, o valor do `calls` no historico E o custo. Medido em 168 calls reais:

    facingSize (incremento cru) ....  66,1% de acerto
    facingToTotal (o que gravamos) .  44,0%
    facing_to_call (novo) .........   98,8%   (as 2 restantes sao fixtures sinteticas incoerentes)

── O que mais caiu junto ──────────────────────────────────────────────────────────────────────────

Perseguir as divergencias do oraculo derrubou tres defeitos vizinhos, todos com teste aqui:

  1. `ALLIN` sem "to" (CoinPoker) era lido como to-total. E incremento: quem tinha 6.000 de SB e
     escreve `ALLIN 107.315,65` esta indo a 113.315,65. Subestimava a aposta em um blind inteiro.
  2. Botao MORTO (assento do botao sem linha `Seat N:`, jogador saiu) zerava o blind do hero.
  3. O gasto do hero somava o INCREMENTO do raise, entao um `raises 120 to 240` de quem nao tinha
     nada contava 120. O stack restante saia maior do que e.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedHand, ParsedAction                       # noqa: E402
from leaklab.hand_state_builder import (_facing_to_call_at, _facing_to_total_at,   # noqa: E402
                                        _hero_committed_at, _blind_posted_by,
                                        _hero_remaining_chips, extract_decision_points)


def _mao(seats, actions, sb=200.0, bb=400.0, button=1, hero='Hero', antes=None):
    """ParsedHand minima. `seats` = [(assento, nome, stack)], `actions` = [(street, quem, acao,
    valor, raw)]. O raw importa: e dele que sai o 'to Y'."""
    raw = ['Fake Hand #1: Tournament #1']
    for s, nome, stack in seats:
        raw.append(f'Seat {s}: {nome} ({stack:,.0f} in chips)')
    return ParsedHand(
        hand_id='teste', hero=hero, button_seat=button, sb=sb, bb=bb,
        seats=[{'seat': s, 'name': n, 'stack': st} for s, n, st in seats],
        actions=[ParsedAction(player=p, street=stt, action=a, amount=v, raw=r)
                 for stt, p, a, v, r in actions],
        raw_text='\n'.join(raw), antes=antes or {},
    )


# ── o caso do relato ───────────────────────────────────────────────────────────────────────────────

def test_custo_e_o_incremento_quando_o_hero_ja_subiu():
    """Hero sobe para 1.600 e leva all-in de 1.877,41 total: paga 277,41, nao 1.877."""
    h = _mao(
        seats=[(1, 'Vilao', 50000), (2, 'Hero', 40000), (3, 'Curto', 1877.41)],
        actions=[('preflop', 'Hero',  'raises', 1200.0, 'Hero: raises 1,200 to 1,600'),
                 ('preflop', 'Vilao', 'calls',  1600.0, 'Vilao: calls 1,600'),
                 # Curto e o BB: ja tinha 400 na frente, entao o ALLIN de 1.477,41 leva o
                 # total dele a 1.877,41 (o `ALLIN` do CoinPoker e incremento).
                 ('preflop', 'Curto', 'all-in', 1477.41, 'Curto: ALLIN 1,477.41'),
                 ('preflop', 'Hero',  'calls',   277.41, 'Hero: calls 277.41')],
        button=1)
    idx = 3
    assert _facing_to_total_at(h.actions, idx, 'preflop', h) == 1877.41
    assert _hero_committed_at(h, h.actions, idx, 'preflop', 'Hero') == 1600.0
    custo = _facing_to_call_at(h, h.actions, idx, 'preflop', 'Hero')
    assert abs(custo - 277.41) < 0.01, custo


def test_o_blind_do_hero_conta_como_ja_investido():
    """BB enfrentando open de 2bb paga 1bb, nao 2bb — o blind ja esta na frente dele."""
    h = _mao(
        seats=[(1, 'Btn', 20000), (2, 'SB', 20000), (3, 'Hero', 20000)],
        actions=[('preflop', 'Btn',  'raises', 800.0, 'Btn: raises 400 to 800'),
                 ('preflop', 'SB',   'folds',  None,  'SB: folds'),
                 ('preflop', 'Hero', 'calls',  400.0, 'Hero: calls 400')],
        button=1)
    assert _blind_posted_by(h, 'Hero') == 400.0            # assento 3 = BB com botao no 1
    assert _facing_to_call_at(h, h.actions, 2, 'preflop', 'Hero') == 400.0
    assert _facing_to_total_at(h.actions, 2, 'preflop', h) == 800.0   # o no continua "to 2bb"


def test_ninguem_paga_mais_do_que_tem():
    """Vilao aposta 240 num pote de 120, hero so tem 150: o custo e 150."""
    h = _mao(
        seats=[(3, 'Vilao', 5000), (4, 'Hero', 210)],
        actions=[('preflop', 'Hero',  'raises', 30.0,  'Hero: raises 30 to 60'),
                 ('preflop', 'Vilao', 'calls',  30.0,  'Vilao: calls 30'),
                 ('flop',    'Hero',  'checks', None,  'Hero: checks'),
                 ('flop',    'Vilao', 'bets',   240.0, 'Vilao: bets 240 and is all-in'),
                 ('flop',    'Hero',  'folds',  None,  'Hero: folds')],
        sb=15.0, bb=30.0, button=3)
    assert _facing_to_total_at(h.actions, 4, 'flop', h) == 240.0
    assert _facing_to_call_at(h, h.actions, 4, 'flop', 'Hero') == 150.0    # 210 - 60 do preflop


# ── os tres vizinhos que cairam junto ──────────────────────────────────────────────────────────────

def test_allin_sem_to_e_incremento_nao_total():
    """CoinPoker: quem tem 6.000 de SB e escreve `ALLIN 107.315,65` esta indo a 113.315,65."""
    h = _mao(
        seats=[(1, 'Vilao', 114815.65), (4, 'Hero', 333184.35)],
        actions=[('preflop', 'Vilao', 'all-in', 107315.65, 'Vilao: ALLIN 107,315.65'),
                 ('preflop', 'Hero',  'calls',  101315.65, 'Hero: calls 101,315.65')],
        sb=6000.0, bb=12000.0, button=1, antes={'Vilao': 1500.0, 'Hero': 1500.0})
    # heads-up: o botao E o SB, entao o Vilao (assento 1, botao) postou 6.000
    assert _blind_posted_by(h, 'Vilao') == 6000.0
    assert _facing_to_total_at(h.actions, 1, 'preflop', h) == 113315.65
    custo = _facing_to_call_at(h, h.actions, 1, 'preflop', 'Hero')
    assert abs(custo - 101315.65) < 0.01, custo     # exatamente o que o historico diz que pagou


def test_botao_morto_nao_apaga_o_blind():
    """O assento do botao pode nao ter jogador. O SB e o primeiro assento VIVO depois dele."""
    h = _mao(
        seats=[(1, 'A', 35000), (2, 'B', 11850), (4, 'Hero', 94149), (5, 'BB', 22800)],
        actions=[('preflop', 'Hero', 'calls', 2000.0, 'Hero calls 2000.00')],
        sb=2000.0, bb=4000.0, button=3)          # assento 3 vazio
    assert _blind_posted_by(h, 'Hero') == 2000.0, 'assento 4 e o SB com botao morto no 3'
    assert _blind_posted_by(h, 'BB') == 4000.0


def test_stack_restante_usa_o_total_do_raise_nao_o_incremento():
    """`raises 120 to 240` de quem nao tinha nada custa 240. Somar 120 inflava o stack."""
    h = _mao(
        seats=[(9, 'Hero', 280), (1, 'Vilao', 4213)],
        actions=[('preflop', 'Hero',  'raises', 120.0, 'phpro: raises 120 to 240'),
                 ('preflop', 'Vilao', 'raises', 120.0, 'Vilao: raises 120 to 360'),
                 ('preflop', 'Hero',  'calls',   25.0, 'phpro: calls 25 and is all-in')],
        sb=60.0, bb=120.0, button=9, antes={'Hero': 15.0})
    resto = _hero_remaining_chips(h, 'Hero', h.actions[:2])
    assert resto == 25.0, f'280 - 15 de ante - 240 do raise = 25, veio {resto}'
    assert _facing_to_call_at(h, h.actions, 2, 'preflop', 'Hero') == 25.0


# ── o campo chega ate o spot ───────────────────────────────────────────────────────────────────────

def test_o_spot_carrega_os_dois_numeros_separados():
    """`facingToBb` (tamanho) e `facingToCallBb` (custo) coexistem e divergem quando devem."""
    from leaklab.pipeline import build_decision_input
    h = _mao(
        seats=[(1, 'Btn', 20000), (2, 'SB', 20000), (3, 'Hero', 20000)],
        actions=[('preflop', 'Btn',  'raises', 800.0, 'Btn: raises 400 to 800'),
                 ('preflop', 'SB',   'folds',  None,  'SB: folds'),
                 ('preflop', 'Hero', 'calls',  400.0, 'Hero: calls 400')],
        button=1)
    h.hero_cards = 'AsKd'
    estados = extract_decision_points(h)
    assert estados, 'a mao precisa gerar decisao'
    spot = build_decision_input(estados[0], h)['spot']
    assert spot['facingToBb'] == 2.0,     spot['facingToBb']       # aposta de 2bb
    assert spot['facingToCallBb'] == 1.0, spot['facingToCallBb']   # custa 1bb


def test_pot_odds_usam_o_custo_e_nao_o_tamanho():
    """O guarda que fecha o caso: sem ele, a equity exigida sai calculada sobre a aposta cheia."""
    from leaklab.pipeline import build_decision_input
    h = _mao(
        seats=[(1, 'Vilao', 50000), (2, 'Hero', 40000), (3, 'Curto', 1877.41)],
        actions=[('preflop', 'Hero',  'raises', 1200.0, 'Hero: raises 1,200 to 1,600'),
                 ('preflop', 'Vilao', 'calls',  1600.0, 'Vilao: calls 1,600'),
                 # Curto e o BB: ja tinha 400 na frente, entao o ALLIN de 1.477,41 leva o
                 # total dele a 1.877,41 (o `ALLIN` do CoinPoker e incremento).
                 ('preflop', 'Curto', 'all-in', 1477.41, 'Curto: ALLIN 1,477.41'),
                 ('preflop', 'Hero',  'calls',   277.41, 'Hero: calls 277.41')],
        button=1)
    h.hero_cards = 'AsJc'
    estados = extract_decision_points(h)
    alvo = [e for e in estados if e.player_action == 'call']
    assert alvo, 'a mao precisa ter a decisao de call'
    di = build_decision_input(alvo[0], h)
    po = di['math']['potOddsEquity']
    # pote no motor = 4.477,41 (soma dos amounts). Com o custo certo (277,41) a exigencia
    # fica em ~5,8%; com a aposta cheia (1.677,41) ia a 27,2%.
    assert po is not None and po < 0.10, f'equity exigida deveria ser de um digito, veio {po}'


# ── a convencao mora em DOIS lugares; este guarda exige que nao divirjam ───────────────────────────

def test_committed_on_street_bate_com_a_mesa_do_replayer():
    """`_committed_on_street` e o loop do `build_table_state_at_decision` aplicam a MESMA regra
    ("raise grava to-total, bets/calls somam, blind conta") em dois lugares. Se um for ajustado
    sozinho, o pote da tela e o custo do motor passam a discordar em silencio. Aqui as duas
    contas sao confrontadas sobre um torneio real inteiro.

    O ideal seria uma funcao so, mas o loop da mesa calcula stacks e folds no mesmo passe; ate
    que valha extrair, este guarda e o que impede a deriva."""
    from leaklab.parser import parse_hand_history
    from leaklab.hand_state_builder import build_table_state_at_decision

    caminho = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')
    if not os.path.exists(caminho):
        return                                  # sem a fixture nao ha o que confrontar
    maos = parse_hand_history(open(caminho, encoding='utf-8', errors='ignore').read())
    assert maos, 'a fixture precisa produzir maos'

    conferidas, divergentes = 0, []
    for mao in maos:
        hero, bb = mao.hero, (mao.bb or 0)
        if not hero or not bb:
            continue
        for idx, a in enumerate(mao.actions):
            if a.player != hero or a.action not in {'folds', 'checks', 'calls', 'bets', 'raises', 'all-in'}:
                continue
            alvo = round(_facing_to_total_at(mao.actions, idx, a.street, mao) / bb, 2)
            try:
                mesa = build_table_state_at_decision(mao, a.street, hero, alvo)
            except Exception:
                continue
            assento = next((s for s in mesa.get('seats', []) if s.get('hero')), None)
            if assento is None:
                continue
            meu = _hero_committed_at(mao, mao.actions, idx, a.street, hero)
            conferidas += 1
            if abs(round(meu, 1) - float(assento.get('bet') or 0)) > 0.15:
                divergentes.append((mao.hand_id, a.street, round(meu, 1), assento.get('bet')))

    assert conferidas >= 50, f'confrontou so {conferidas} decisoes — a fixture encolheu?'
    # A mesa para na acao do hero casando o facing; quando ela para num ponto ANTERIOR (duas
    # acoes do hero na street), a divergencia e legitima. Exigimos que seja a excecao.
    assert len(divergentes) <= conferidas * 0.05, \
        f'{len(divergentes)}/{conferidas} divergem: {divergentes[:5]}'


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
