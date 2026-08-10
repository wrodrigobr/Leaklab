# -*- coding: utf-8 -*-
"""A range com que o vilao vai de ALL-IN — a metade 5b do relatorio do coach.

── O que estava registrado, e o que estava errado nisso ───────────────────────────────────────

O fechamento das cinco familias marcou esta metade como **bloqueada**: "exige a range de JAM, e
push/fold e secao morta". A parte sobre o ARQUIVO estava certa e foi reconferida — em
`leaklab_gto_ranges.json` nao ha chave nenhuma com push/jam/shove e `_other_spots` esta vazia.

A conclusao tirada dali e que estava errada. A range de jam nunca morou numa secao propria: ela e
a **coluna de all-in dos nos que ja consultamos todo dia**.

    open-jam    `RFI[pos].allin_hands`                 25 das 72 entradas tem mao jamando
    3-bet jam   `vs_RFI[opener][defender].allin_hands` 183 das 324, jam dominante em 105
    HU          coluna `allin` dos nos capturados      198 nos oferecem jam, 2.885 pares (no, mao)

Mesmo formato da familia 1: o dado vinha no payload e ninguem o consumia.

── Por que importa ────────────────────────────────────────────────────────────────────────────

Enfrentando all-in com dois ou mais raises, o produto media equity contra **mao aleatoria** — o
`pipeline` excluia `facing_allin` de proposito, porque a carta de 3-bet modela um aumento DE
TAMANHO. Medido nas 397 decisoes do acervo que enfrentam all-in: nas cobertas pelo no de 3-bet
jam, a equity cai **18 pontos na mediana**, 53 de 55 para baixo. E o AQo que o coach pegou (64,4%
exibidos para abencoar um call) vai a **52,5%**, o numero que ele disse na revisao.

── O que estes testes protegem ────────────────────────────────────────────────────────────────

Todo guarda aqui nasceu de um numero medido no acervo, nao de precaucao generica. Cada um foi
quebrado de proposito uma vez, e a mutacao esta descrita no teste que a acusa.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.preflop_gto_ranges as G                                          # noqa: E402
from leaklab.preflop_gto_ranges import villain_jam_range                        # noqa: E402


# ── A leitura ──────────────────────────────────────────────────────────────────────────────────

def test_le_a_coluna_de_jam_e_nao_a_range_de_abertura():
    """A prova de que estamos na coluna certa e quem NAO esta na range.

    No SB a 10bb heads-up, AA e KK dao **call** (limpam para trapear) e o jam sai com pares
    pequenos, Ax e Kx. Uma leitura que pegasse "tudo que nao e fold" traria AA junto — e foi
    exatamente essa a leitura que `villain_open_range` faz, de proposito, para outro fim.
    """
    r = villain_jam_range('SB', 'BB', 10.0, n_players=2, raises_faced=1)
    assert r, 'o no capturado de 10bb HU tem jam e voltou vazio'
    assert 'AA' not in r, 'AA nao jama a 10bb HU — leitura pegou a range de abertura inteira'
    assert 'KK' not in r
    assert 'A2o' in r and '22' in r, 'faltam maos que a carta jama'
    assert all(0 < w <= 1.0 for w in r.values()), 'peso fora de [0,1]'


def test_a_range_estreita_conforme_a_mesa_fica_mais_funda():
    """Sanidade de poker, e o sinal mais barato de que a leitura nao esta trocando de no: quanto
    mais fundo, menos maos jamam. Se a curva inverter, a selecao de profundidade esta errada."""
    tam = [len(villain_jam_range('BB', 'SB', float(d), n_players=2, raises_faced=2))
           for d in (10, 16, 25, 40)]
    assert tam == sorted(tam, reverse=True), tam
    assert tam[0] > tam[-1], tam


def test_o_no_e_o_do_ABRIDOR_nao_o_do_hero():
    """O defeito mais caro desta entrega, e ele passou pela primeira versao.

    `vs_RFI[opener][defender]`: quem manda no primeiro indice e quem ABRIU. A primeira versao
    exigia `hero_was_aggressor` e indexava pela posicao do HERO — media no acervo, isso descartava
    **57 das 80** decisoes que enfrentam 3-bet jam, todas aquelas em que o hero pagou ou estava
    nos blinds. Parecia funcionar porque nos 5 casos restantes o hero ERA o abridor, e ai os dois
    indices coincidem.
    """
    por_co = villain_jam_range('BB', 'SB', 14.0, n_players=8, raises_faced=2, opener_pos='CO')
    por_utg = villain_jam_range('BB', 'SB', 14.0, n_players=8, raises_faced=2, opener_pos='UTG')
    assert por_co and por_utg
    assert por_co != por_utg, ('o abridor nao mudou nada — o indice esta ignorando `opener_pos`')

    # CONTROLE: sem saber quem abriu nao ha no, e inventar um seria gradear pela carta errada.
    assert villain_jam_range('BB', 'SB', 14.0, n_players=8, raises_faced=2) == {}


# ── Os guardas, cada um com o numero que o originou ────────────────────────────────────────────

def test_jam_residual_NAO_vira_range():
    """MUTACAO: trocar `_jam_e_a_abertura` por `return True`.

    A 30bb o SB quase nao open-jama, e a cauda da carta tem 10 maos. Sem este guarda, `7h7s UTG+2
    vs SB a 29,8bb` saia com equity de **72,1%** em vez de 59,5% — 12,6 pontos, num fold que hoje
    e `gto_correct`, e a acusacao nasceria de uma range que a estrategia quase nao joga.

    Ha um motivo mais forte que o estatistico: a auditoria de 09/08 escolheu a range de ABERTURA
    ali de proposito, por ser mais larga e portanto conservadora a favor do hero.
    """
    assert villain_jam_range('SB', 'UTG+2', 29.8, n_players=8, raises_faced=1) == {}
    # CONTROLE: na profundidade em que abrir E jamar, a mesma posicao devolve range
    assert villain_jam_range('SB', 'UTG+2', 10.0, n_players=8, raises_faced=1)


def test_carta_de_outra_PROFUNDIDADE_nao_serve():
    """MUTACAO: fazer `_profundidade_compativel` devolver sempre True.

    `_stack_bucket` **satura**: a 3,9bb ele devolve a carta de 10bb sem avisar. O caminho do no
    capturado ja tinha janela de 25%; o da carta nao tinha nenhuma. Medido no A/B do acervo, isso
    produzia duas acusacoes falsas — `3hAh CO vs BTN a 3,9bb` e `KdJs BTN vs SB a 5,2bb` viravam
    `small_mistake`. A 4bb pagar um jam com A3s e obrigatorio; so saia erro porque a range de 10bb
    e bem mais tight que a de 4bb.
    """
    assert villain_jam_range('BTN', 'CO', 3.9, n_players=8, raises_faced=1) == {}
    assert villain_jam_range('SB', 'BTN', 5.2, n_players=8, raises_faced=2, opener_pos='CO') == {}
    # CONTROLE: dentro da janela, a MESMA carta responde
    assert villain_jam_range('BTN', 'CO', 10.0, n_players=8, raises_faced=1)


def test_piso_de_suporte_contra_range_de_tres_maos():
    """MUTACAO: baixar `_MASSA_MINIMA_DE_JAM` para 0.

    Range estreita demais nao e leitura, e ruido com cara de precisao — e a DIRECAO importa:
    range estreita puxa a equity para baixo, o que absolve fold e **condena call**, o lado onde
    acusacao nova nasce. No acervo o corpo da distribuicao ficou entre 21 e 33 maos, com um unico
    caso solto de **5 maos** (`AcTs UTG+2 vs SB a 27,4bb`, −24,6 pontos de equity).

    A carta e forjada porque no dado real esse spot nao aparece, e guarda que nunca foi visto
    discriminando nao esta verificado.
    """
    forjada = {'ranges': {G._stack_bucket(20.0): {'vs_RFI': {'CO': {'BB': {
        'raise_hands': '', 'allin_hands': 'AA,KK,QQ'}}}}}}
    antigo = G._load
    G._load = lambda: forjada
    try:
        assert villain_jam_range('BB', 'SB', 20.0, n_players=8, raises_faced=2,
                                 opener_pos='CO') == {}, 'range de 3 maos passou como leitura'
        # CONTROLE: a MESMA carta forjada com suporte de sobra devolve a range
        forjada['ranges'][G._stack_bucket(20.0)]['vs_RFI']['CO']['BB']['allin_hands'] = (
            'AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKo,AQo,AJo')
        assert villain_jam_range('BB', 'SB', 20.0, n_players=8, raises_faced=2, opener_pos='CO')
    finally:
        G._load = antigo


def test_spot_sem_allin_nao_inventa_range():
    """O outro jeito de nao haver range: o spot EXISTE e nao tem all-in nenhum. Somar
    `raise_hands` ali seria servir a carta de 3-bet dimensionado como se fosse jam — nos
    diferentes, que e o defeito que esta entrega inteira existe para nao repetir."""
    forjada = {'ranges': {G._stack_bucket(20.0): {'vs_RFI': {'CO': {'BB': {
        'raise_hands': 'AA,KK,QQ,JJ,TT,99,88,77,AKo,AQo', 'allin_hands': ''}}}}}}
    antigo = G._load
    G._load = lambda: forjada
    try:
        assert villain_jam_range('BB', 'SB', 20.0, n_players=8, raises_faced=2,
                                 opener_pos='CO') == {}, 'usou a range de aumento como se fosse jam'
    finally:
        G._load = antigo


def test_HEADS_UP_nunca_cai_na_carta_de_MESA_CHEIA():
    """MUTACAO: apagar a saida `if n_players == 2: return {}`.

    E a regra que originou o caminho HU inteiro. A revisao com o coach provou por oraculo externo
    que a carta ring mente em heads-up: JJ no BB vs open e "call 100%" na 9-max e **3-BET 100%**
    no GW HU, em toda profundidade de 10 a 60bb.

    Achado relendo o proprio codigo, nao por teste que falhou: quando o no HU capturado nao
    responde (profundidade fora da janela, jam residual), o fluxo caia no ramo da carta, que
    normaliza a posicao e consulta o `RFI[SB]` da mesa grande. So NAO explodia por acidente — o
    guarda de dominancia barrava antes na maioria das profundidades. Acidente nao e guarda.

    ── E a PRIMEIRA versao deste teste era cega ───────────────────────────────────────────────
    Ela afirmava `{}` a 16/20/30/60bb, e passava com o guarda REMOVIDO: naquelas profundidades a
    dominancia ja devolvia `{}` sozinha. Dois mecanismos produzindo o mesmo resultado, e o teste
    nao distinguia qual estava agindo — cobertura sem cobertura, o mesmo defeito que o projeto
    documenta em `assertEqual(correct_index, 0)`.

    A versao boa remove o no capturado e escolhe a profundidade em que a carta de mesa cheia
    RESPONDERIA. Ai so existe um mecanismo em jogo, e ele e o que esta sendo verificado.
    """
    import leaklab.preflop_gto_ranges as g
    antigo, g._hu_cache = g._hu_cache, {}          # sem no HU capturado: so a saida de mesa 2 barra
    try:
        # CONTROLE PRIMEIRO: a 10bb a carta de mesa cheia TEM range de jam para o SB. Sem isto o
        # `{}` abaixo nao prova nada, porque poderia vir de nao haver carta nenhuma.
        assert villain_jam_range('SB', 'BTN', 10.0, n_players=8, raises_faced=1), (
            'controle quebrado: a carta de mesa cheia deveria responder a 10bb')
        assert villain_jam_range('SB', 'BB', 10.0, n_players=2, raises_faced=1) == {}, (
            'HU sem no capturado pegou a carta de mesa cheia')
    finally:
        g._hu_cache = antigo
    # CONTROLE 2: com o no capturado de volta, o HU responde normalmente
    assert villain_jam_range('SB', 'BB', 10.0, n_players=2, raises_faced=1)


def test_captura_CLASSIC_nao_e_emprestada_ao_PKO():
    """Com bounty a range de jam ABRE. Emprestar a captura Classic estreitaria a range do vilao,
    inflaria a equity do hero e absolveria call ruim — dano que o buraco de hoje nao causa.

    O gate protege a CAPTURA. O ramo da carta segue o mesmo caminho que `villain_open_range` ja
    seguia: usa `_pko_ranges_for` quando ha entrada PKO e cai na Classic quando nao ha. Medido,
    hoje ele cai na Classic (`ring PKO == ring Classic`, 73 maos) — comportamento pre-existente do
    arquivo de ranges, nao algo que esta entrega introduz, e por isso nao esta afirmado aqui como
    se fosse garantia.
    """
    classic = villain_jam_range('SB', 'BB', 10.0, n_players=2, raises_faced=1)
    pko = villain_jam_range('SB', 'BB', 10.0, n_players=2, raises_faced=1, is_pko=True)
    assert classic, 'controle quebrado: a Classic deveria ter range'
    assert set(pko) != set(classic), 'PKO recebeu a captura Classic'


def test_linha_fora_do_modelo_nao_recebe_carta():
    """Nao ha no para 4-bet jam nem para "all-in sem raise antes". Sem gabarito, `{}` — que
    devolve o caller ao comportamento de hoje em vez de a um palpite."""
    assert villain_jam_range('SB', 'BB', 10.0, n_players=8, raises_faced=3, opener_pos='CO') == {}
    assert villain_jam_range('SB', 'BB', 10.0, n_players=8, raises_faced=0) == {}
    # CONTROLE: o assento errado em HU tambem nao recebe (o BB nao age primeiro)
    assert villain_jam_range('BB', 'SB', 10.0, n_players=2, raises_faced=1) == {}


# ── O caminho VIVO ─────────────────────────────────────────────────────────────────────────────

def _entrada(opener, allin=True, raises=2, cartas='AcQd'):
    from leaklab.models import HandState
    from leaklab.pipeline import build_decision_input
    st = HandState(
        hand_id='H', street='preflop', hero='hero', hero_cards=cartas, board=[],
        player_action='call', pot_size=9.0, facing_size=31.4, effective_stack_bb=20.3,
        position='UTG+2', villain_position='SB', is_in_position=False, is_multiway=False,
        actions=[], metadata={'preflop_raises_faced': raises, 'n_players': 8,
                              'facing_allin': allin, 'preflop_opener': opener})
    return build_decision_input(st)


def test_pipeline_usa_a_range_de_jam_e_a_equity_do_coach_aparece():
    """O AQo da revisao cruzada, de ponta a ponta. O card exibia **64,4%** e usava esse numero —
    medido contra mao aleatoria — para abencoar o call. Contra a range de jam do no certo sao
    ~52%, que foi o que o coach disse."""
    com = _entrada('UTG+2')
    assert com['math']['equitySource'] == 'vs_range', com['math']['equitySource']
    eq = float(com['math']['estimatedHandEquity'])
    assert 0.48 <= eq <= 0.57, f'equity {eq} fora do que a range de jam devolve'

    sem = _entrada('')
    assert sem['math']['equitySource'] == 'vs_random', 'inventou no sem saber quem abriu'
    assert float(sem['math']['estimatedHandEquity']) > eq, (
        'a range de jam tem de ser mais forte que mao aleatoria neste spot')


def test_o_open_simples_continua_como_estava():
    """CONTROLE do caminho vivo: sem all-in, nada aqui pode ter mexido. O 3-bet DE TAMANHO segue
    na `villain_reraise_range`, e o open simples na `villain_open_range`."""
    assert _entrada('UTG+2', allin=False)['math']['equitySource'] == 'vs_range'
    assert _entrada('', allin=False, raises=1)['math']['equitySource'] == 'vs_range'


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
