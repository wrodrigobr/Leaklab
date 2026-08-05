# -*- coding: utf-8 -*-
"""Botao morto / small blind morto deslocavam a mesa inteira uma casa.

── O defeito ──────────────────────────────────────────────────────────────────────────────────

`_infer_position` derivava tudo do BOTAO: ordenava os assentos a partir do seguinte ao botao e
assumia `ordered[0] = SB`, `ordered[1] = BB`. Com o assento do botao VAZIO, ou com nenhum small
blind postado, a mesa inteira desloca uma casa.

Caso concreto do acervo (mao 2789041938):

    Seat #4 is the button
    Seat 2: MusashiBR       <- hero
    Seat 3: ...  Seat 4: ...  Seat 6: jippy
    jippy posts the big blind 2000.00     <- NENHUM small blind
    MusashiBR raises 4000.00              <- hero e o PRIMEIRO a agir

O hero abre de UTG e era rotulado `BB`. Consequencia real: a range preflop consultada e a da
posicao errada, para TODAS as decisoes daquela mao.

Medido em producao antes do conserto: **24 maos de 6.734** com quem postou o BB rotulado como
outra coisa, mais 13 com o SB errado.

── O conserto ─────────────────────────────────────────────────────────────────────────────────

Nao ha o que derivar: **o historico DECLARA quem postou cada blind**. `blinds_declarados` virou
a fonte unica, e os DOIS consumidores passaram a ler dela — `_infer_position` e
`_blind_posted_by`, que tinham cada um a sua gambiarra de botao morto e erravam junto.

── Por que estes testes tem a forma que tem ───────────────────────────────────────────────────

O oraculo esta DENTRO do dado. Entao o teste roda o proprio `_infer_position` e confere contra o
que o texto declara, em vez de reimplementar a regra e comparar duas implementacoes minhas.

Isso nao e preciosismo: reimplementando a regra no medidor eu produzi TRES numeros errados
seguidos, todos plausiveis (12,7% medindo um site so porque o regex nao casava `Nome: posts`;
depois 3,4% com 204 falsos positivos de heads-up, onde o botao E o SB e o codigo ja acertava).
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.hand_state_builder import _infer_position, blinds_declarados, _blind_posted_by


# ── Fixtures: mãos reais reduzidas ao preflop ─────────────────────────────────────────────────

# SB MORTO: ninguem posta small blind. Botao no assento 4 (ocupado). Hero (seat 2) age PRIMEIRO.
MAO_SB_MORTO = """Game Hand #2789041938 - Tournament #35598158 - Holdem (No Limit) - Level 5 (1000.00/2000.00) - 2026/07/29 21:07:11 UTC
Table '3' 8-max Seat #4 is the button
Seat 2: MusashiBR (76770.00)
Seat 3: JAMESHARPER (40447.00)
Seat 4: MoneyFunnel (66828.00)
Seat 6: jippy (33400.00)
MusashiBR posts ante 200.00
JAMESHARPER posts ante 200.00
MoneyFunnel posts ante 200.00
jippy posts ante 200.00
jippy posts the big blind 2000.00
*** HOLE CARDS ***
Dealt to MusashiBR [Ac Ah]
MusashiBR raises 4000.00 to 4000.00
JAMESHARPER folds
MoneyFunnel folds
jippy folds
*** SUMMARY ***
Total pot 6800.00
"""

# BOTAO MORTO: o assento 1 nao tem jogador. SB=assento 2, BB=assento 3. Hero (seat 4) e UTG.
MAO_BOTAO_MORTO = """Game Hand #2769802432 - Tournament #35409697 - Holdem (No Limit) - Level 6 (1250.00/2500.00) - 2026/06/30 21:19:19 UTC
Table '1' 8-max Seat #1 is the button
Seat 2: braddaman (35350.00)
Seat 3: jeffb443 (29250.00)
Seat 4: MusashiBR (109299.00)
Seat 6: elvin6161 (29100.00)
Seat 7: JAMESHARPER (68059.00)
Seat 8: UnDERSun (47050.00)
braddaman posts ante 250.00
jeffb443 posts ante 250.00
MusashiBR posts ante 250.00
elvin6161 posts ante 250.00
JAMESHARPER posts ante 250.00
UnDERSun posts ante 250.00
braddaman posts the small blind 1250.00
jeffb443 posts the big blind 2500.00
*** HOLE CARDS ***
Dealt to MusashiBR [5c 3c]
MusashiBR folds
elvin6161 folds
JAMESHARPER folds
UnDERSun folds
braddaman raises 4500.00 to 5750.00
jeffb443 folds
*** SUMMARY ***
Total pot 12250.00
"""

# Mesa NORMAL, formato PokerStars (`Nome: posts`) — controle negativo do conserto inteiro.
MAO_NORMAL_PS = """PokerStars Hand #900000001: Tournament #99, Hold'em No Limit (100/200) - 2026/07/01 12:00:00 ET
Table '99 3' 9-max Seat #3 is the button
Seat 1: Alice (10000 in chips)
Seat 2: Bob (10000 in chips)
Seat 3: Carol (10000 in chips)
Seat 4: Dave (10000 in chips)
Alice: posts small blind 100
Bob: posts big blind 200
*** HOLE CARDS ***
Dealt to Dave [Ah Kd]
Dave: raises 400 to 600
Carol: folds
Alice: folds
Bob: folds
*** SUMMARY ***
Total pot 900
"""


def _mao(txt):
    hands = parse_pokerstars_file_from_text(txt)
    assert hands, 'o parser nao devolveu mao — fixture quebrada'
    return hands[0]


def _quem_postou(txt, qual):
    """Le do TEXTO, nao do codigo sob teste. É o oraculo."""
    import re
    m = re.search(rf'^(?P<p>.+?):? posts (?:the )?{qual} blind\b', txt, re.M | re.I)
    return m.group('p').strip() if m else None


def test_quem_postou_o_BB_e_rotulado_BB():
    """O invariante central, nos dois formatos e nos dois defeitos."""
    for nome, txt in (('sb morto', MAO_SB_MORTO), ('botao morto', MAO_BOTAO_MORTO),
                      ('normal PS', MAO_NORMAL_PS)):
        h = _mao(txt)
        bb = _quem_postou(txt, 'big')
        assert bb, f'{nome}: fixture sem linha de big blind'
        assert _infer_position(h, bb) == 'BB', (
            f'{nome}: {bb} postou o big blind e foi rotulado '
            f'{_infer_position(h, bb)!r}')


def test_quem_postou_o_SB_e_rotulado_SB():
    for nome, txt in (('botao morto', MAO_BOTAO_MORTO), ('normal PS', MAO_NORMAL_PS)):
        h = _mao(txt)
        sb = _quem_postou(txt, 'small')
        assert sb, f'{nome}: fixture sem linha de small blind'
        assert _infer_position(h, sb) == 'SB', (
            f'{nome}: {sb} postou o small blind e foi rotulado {_infer_position(h, sb)!r}')


def test_quem_abre_a_mao_nao_e_rotulado_blind():
    """O caso que originou tudo: hero abre de posicao inicial e era chamado de BB.

    Prova mais forte que o rotulo em si — quem age PRIMEIRO no preflop nao pode estar num blind,
    porque blind age por ULTIMO.
    """
    h = _mao(MAO_SB_MORTO)
    pos = _infer_position(h, 'MusashiBR')
    assert pos not in ('BB', 'SB'), f'quem abriu a mao foi rotulado {pos!r}'

    h2 = _mao(MAO_BOTAO_MORTO)
    pos2 = _infer_position(h2, 'MusashiBR')
    assert pos2 not in ('BB', 'SB'), f'quem agiu primeiro apos os blinds foi rotulado {pos2!r}'


def test_botao_continua_sendo_o_ultimo():
    """Guarda do `n_virtual`: com o SB morto ha um lugar vago no indice 0. Sem contar esse lugar,
    o BTN escorregaria para o penultimo e a mesa erraria do outro lado."""
    h = _mao(MAO_SB_MORTO)
    assert _infer_position(h, 'MoneyFunnel') == 'BTN', (
        f"o assento do botao (MoneyFunnel, Seat 4) virou "
        f"{_infer_position(h, 'MoneyFunnel')!r}")


def test_blinds_declarados_le_os_dois_formatos():
    """`Nome: posts` (PokerStars/GG) e `nome posts the` (CoinPoker/ACR). O `:?` do regex e o que
    separa medir tudo de medir um site so."""
    assert blinds_declarados(_mao(MAO_NORMAL_PS)) == ('Alice', 'Bob')
    assert blinds_declarados(_mao(MAO_BOTAO_MORTO)) == ('braddaman', 'jeffb443')
    assert blinds_declarados(_mao(MAO_SB_MORTO)) == (None, 'jippy')


def test_blind_postado_usa_a_mesma_fonte():
    """FIAÇÃO: `_blind_posted_by` tinha a PROPRIA derivacao pelo botao e errava junto. Se ele
    voltar a derivar, as fichas ja investidas no preflop saem do jogador errado — e isso
    contamina pote, pot odds e stack efetivo, nao so o rotulo."""
    h = _mao(MAO_BOTAO_MORTO)
    assert _blind_posted_by(h, 'braddaman') == h.sb, 'quem postou o SB nao recebeu o SB'
    assert _blind_posted_by(h, 'jeffb443') == h.bb, 'quem postou o BB nao recebeu o BB'
    assert _blind_posted_by(h, 'MusashiBR') == 0.0, 'hero fora dos blinds recebeu blind'

    h2 = _mao(MAO_SB_MORTO)
    assert _blind_posted_by(h2, 'jippy') == h2.bb
    assert _blind_posted_by(h2, 'MusashiBR') == 0.0


def test_sem_linha_de_blind_cai_no_caminho_antigo():
    """Nao ha regressao para historico truncado: sem declaracao, segue derivando do botao."""
    txt = MAO_NORMAL_PS.replace('Alice: posts small blind 100\n', '').replace(
        'Bob: posts big blind 200\n', '')
    h = _mao(txt)
    assert blinds_declarados(h) == (None, None)
    assert _infer_position(h, 'Dave') != 'unknown', 'perdeu a posicao sem linha de blind'


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
