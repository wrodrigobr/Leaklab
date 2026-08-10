# -*- coding: utf-8 -*-
"""Equity contra a range REAL de 3-bet, nao contra mao aleatoria.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Familia 2 das cinco que a revisao com o coach isolou. O coach pegou um **AQo enfrentando 4-bet
all-in por 20bb**: o card exibia **64,4% de equity** e rotulava o call de `standard`. Mas 64,4% e
contra mao ALEATORIA — contra quem 4-beta 20bb, AQo esta bem atras. O produto usou um numero
medido contra outra coisa para abencoar a jogada.

O `pipeline` injetava range so no open simples, com a justificativa escrita no codigo: "3bet/4bet
tem ranges mais estreitas e ficam no vs-random". **E justamente por serem mais estreitas que o
vs-random mente mais ali.**

── O que este arquivo trava ───────────────────────────────────────────────────────────────────

Que a range de re-raise sai das cartas que ja temos, que ela e mais estreita que a de abertura, e
que **ausencia de cobertura devolve vazio** em vez de uma range inventada — equity contra range
errada e pior que equity contra aleatoria, porque parece precisa.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.equity import equity_vs_range, has_matrix
from leaklab.preflop_gto_ranges import villain_open_range, villain_reraise_range


def test_range_de_3bet_e_mais_estreita_que_a_de_abertura():
    """Se a range de re-raise nao for mais estreita que a de abertura, ou o lookup esta errado
    ou estamos lendo a familia de acao errada — em qualquer dos casos o numero seria pior."""
    achou = 0
    for vil, her, st in (('SB', 'HJ', 20.0), ('BTN', 'CO', 30.0), ('CO', 'UTG', 50.0)):
        rr = villain_reraise_range(vil, her, st)
        ab = villain_open_range(vil, st)
        if not rr or not ab:
            continue
        achou += 1
        assert len(rr) < len(ab), (vil, her, st, len(rr), len(ab))
    assert achou >= 2, 'as cartas de vs_RFI sumiram — o teste virou vacuo'


def test_equity_cai_ao_medir_contra_quem_3beta():
    """O numero do caso do coach. AQo contra a range de 3-bet perde varios pontos para o AQo
    contra a range de ABERTURA — e mais ainda para o vs-aleatoria (~64%)."""
    assert has_matrix(), 'sem matriz de equity o teste nao mede nada'
    rr = villain_reraise_range('SB', 'HJ', 20.0)
    ab = villain_open_range('SB', 20.0)
    assert rr and ab
    eq_rr, eq_ab = equity_vs_range('AQo', rr), equity_vs_range('AQo', ab)
    assert eq_rr is not None and eq_ab is not None
    assert eq_rr < eq_ab - 0.05, f'vs 3-bet {eq_rr} nao ficou abaixo de vs open {eq_ab}'
    assert eq_rr < 0.60, f'AQo contra range de 3-bet deveria ficar bem abaixo de 60%: {eq_rr}'


def test_sem_cobertura_devolve_VAZIO_e_nao_range_inventada():
    """O caller so troca para `vs_range` quando ha range. Devolver algo parecido seria pior: o
    card exibiria precisao que nao existe.

    Par IMPOSSIVEL de proposito (UTG nao 3-beta um open do BB — o BB age por ultimo). Tentei
    primeiro com stack absurdo e o teste falhou: `_stack_bucket` satura no bucket mais fundo,
    entao 4000bb devolve a carta de 100bb. A premissa e que estava errada, nao o codigo.
    """
    assert villain_reraise_range('UTG', 'BB', 20.0) == {}
    assert villain_reraise_range('LJ', 'BB', 20.0) == {}
    assert villain_reraise_range('XX', 'YY', 20.0) == {}
    # CONTROLE: o par possivel na mesma profundidade TEM carta
    assert villain_reraise_range('BB', 'UTG', 20.0)


def test_spot_que_existe_mas_nao_tem_aumento_tambem_devolve_vazio():
    """Ha dois jeitos de nao haver range, e o teste anterior so cobria um.

    `UTG 3-beta open do BB` nem tem spot na carta, entao a funcao retorna antes. O outro caso e o
    spot EXISTIR e nao ter familia de aumento — a mutacao que inventava `{'AA': 1.0}` ali passou
    cega ate este teste existir. Injeto uma carta forjada porque no dado real esse spot nao
    aparece, e um guarda que nunca foi visto discriminando nao esta verificado.
    """
    import leaklab.preflop_gto_ranges as g

    forjada = {'ranges': {g._stack_bucket(20.0): {'vs_RFI': {'HJ': {'SB': {
        'raise_hands': '', 'allin_hands': '', 'call_hands': 'AA,KK'}}}}}}
    antigo = g._load
    g._load = lambda: forjada
    try:
        assert villain_reraise_range('SB', 'HJ', 20.0) == {}, 'inventou range num spot sem aumento'
        # CONTROLE: com mao de aumento na MESMA carta forjada, devolve a range
        forjada['ranges'][g._stack_bucket(20.0)]['vs_RFI']['HJ']['SB']['raise_hands'] = 'AA,KK'
        assert villain_reraise_range('SB', 'HJ', 20.0) == {'AA': 1.0, 'KK': 1.0}
    finally:
        g._load = antigo


def test_pipeline_injeta_a_range_quando_ha_3bet():
    """O caminho VIVO, nao so a funcao. A versao anterior parava no open simples, e este teste
    quebra se alguem restaurar aquele `== 1`."""
    from leaklab.models import HandState
    from leaklab.pipeline import build_decision_input

    def _entrada(raises):
        st = HandState(
            hand_id='H', street='preflop', hero='hero', hero_cards='AcQd', board=[],
            player_action='call', pot_size=9.0, facing_size=6.0, effective_stack_bb=20.0,
            position='HJ', villain_position='SB', is_in_position=False, is_multiway=False,
            actions=[], metadata={'preflop_raises_faced': raises, 'n_players': 8})
        return build_decision_input(st)

    tres_bet = _entrada(2)
    assert tres_bet['math']['equitySource'] == 'vs_range', tres_bet['math']['equitySource']

    # CONTROLE: o caso de open simples, que ja funcionava, continua funcionando
    assert _entrada(1)['math']['equitySource'] == 'vs_range'
    # CONTROLE: sem raise nenhum nao ha villain definido — segue vs_random
    assert _entrada(0)['math']['equitySource'] == 'vs_random'


def test_ALLIN_nunca_e_gradeado_pela_range_de_3BET_DIMENSIONADO():
    """A carta `vs_RFI` modela um 3-bet DE TAMANHO, nao um jam — sao nos diferentes.

    Pego ao regerar o relatorio do coach: com a range de 3-bet injetada num 4-bet ALL-IN, o AQo
    ganhou equity mais verdadeira (64,4% -> 51,7%) e mesmo assim **subiu** para `standard`, porque
    o G2 so rebaixa quando a fonte e `vs_random`. Trocar aleatoria por uma range do no errado e a
    precisao falsa contra a qual eu mesmo tinha escrito o comentario no codigo.

    ── Atualizado em 09/08 ────────────────────────────────────────────────────────────────────
    A versao anterior afirmava `equitySource == 'vs_random'` enfrentando all-in, e isso era
    DESCRICAO DO ESTADO, nao invariante: o vs-random nao era a resposta certa, era a ausencia de
    resposta. Hoje existe `villain_jam_range`, que le a coluna de all-in do MESMO no — e o
    principio deste teste continua de pe, so que agora ele pode ser verificado direito: o que
    nunca pode acontecer e o all-in receber a range de AUMENTO DIMENSIONADO.

    O teste passou a comparar as duas ranges em vez de olhar so o rotulo da fonte. Um rotulo
    `vs_range` nao diz de qual no ele veio, e era exatamente isso que precisava ser garantido.
    """
    from leaklab.models import HandState
    from leaklab.pipeline import build_decision_input
    from leaklab.preflop_gto_ranges import villain_jam_range, villain_reraise_range

    def _entrada(facing_allin, opener='UTG+2'):
        st = HandState(
            hand_id='H', street='preflop', hero='hero', hero_cards='AcQd', board=[],
            player_action='call', pot_size=9.0, facing_size=31.4, effective_stack_bb=20.3,
            position='UTG+2', villain_position='SB', is_in_position=False, is_multiway=False,
            actions=[], metadata={'preflop_raises_faced': 2, 'n_players': 8,
                                  'facing_allin': facing_allin, 'preflop_opener': opener})
        return build_decision_input(st)

    jam = villain_jam_range('SB', 'UTG+2', 20.3, 8, 2, opener_pos='UTG+2')
    dimensionado = villain_reraise_range('SB', 'UTG+2', 20.3, 8)
    assert jam and dimensionado, 'controle quebrado: as duas cartas precisam existir aqui'
    assert set(jam) != set(dimensionado), 'as duas ranges sao iguais — o teste nao discrimina nada'

    com_allin = _entrada(True)
    assert com_allin['math']['equitySource'] == 'vs_range'
    # A prova de qual no foi usado: a equity tem de bater com a range de JAM, nao com a de aumento.
    from leaklab.equity import equity_vs_range
    eq = round(float(com_allin['math']['estimatedHandEquity']), 3)
    assert eq == round(float(equity_vs_range('AQo', jam)), 3), (
        f'{eq} nao veio da range de jam')
    assert eq != round(float(equity_vs_range('AQo', dimensionado)), 3), (
        'jam gradeado por carta de 3-bet dimensionado')

    # CONTROLE 1: o MESMO spot SEM all-in usa a range de 3-bet dimensionado.
    sem_allin = _entrada(False)
    assert sem_allin['math']['equitySource'] == 'vs_range'
    assert round(float(sem_allin['math']['estimatedHandEquity']), 3) == round(
        float(equity_vs_range('AQo', dimensionado)), 3)

    # CONTROLE 2: sem saber quem abriu nao ha no de jam, e o vs-random volta — null honesto em vez
    # de carta adivinhada.
    assert _entrada(True, opener='')['math']['equitySource'] == 'vs_random'


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
