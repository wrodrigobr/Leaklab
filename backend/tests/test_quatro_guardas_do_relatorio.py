# -*- coding: utf-8 -*-
"""Os quatro defeitos que a revisao cruzada com o coach expos (05/08).

Vieram de comparar 71 anotacoes de um coach humano com o veredito do produto. Nenhum deles
estava em lista de bug — sairam de ler mao a mao.

  G1  fold cujo preco nao paga vira `clear_mistake`
  G2  equity vs mao ALEATORIA abencoando call contra range estreita
  G3  abaixo de ~10bb o motor recomendava `raise`, onde a arvore e jam-ou-fold
  G4  blefe em pote com jogador JA all-in rotulado como linha padrao

── Uma correcao minha, que vale mais que os guardas ───────────────────────────────────────────

No relatorio eu acusei o produto de cravar `clear_mistake` em tres folds "de moeda ao alto",
calculando o pot odds como `to_call / (pot_size + to_call)` a partir de colunas do banco. **Estava
errado.** O motor RECONSTROI o pote (trabalho desta mesma sessao, que levou a precisao de 1,2%
para 99,6%), e o pot odds real daquelas maos era 25%, nao 33-37%. Com o numero certo a equity
PAGA o preco e o `clear_mistake` esta correto.

Ou seja: dois campos do banco somados nao sao pot odds. O guarda G1 continua valendo como
principio — se nem a equity inflada alcanca o preco, o fold nao pode ser "erro claro" — mas ele
NAO se aplica aquelas tres maos, e o teste abaixo trava a referencia certa para que a proxima
versao nao volte a usar a errada.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import evaluate_decision

_ARQ = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')


def _base(**kw):
    d = {
        'hand_id': 'H', 'street': 'flop', 'player_action': 'fold', 'hero_cards': '9d5c',
        'spot': {'position': 'BB', 'board': ['7d', 'Tc', '6h'], 'effectiveStackBb': 24.0,
                 'facingSize': 2.0, 'facingToBb': 2.0, 'nPlayers': 7, 'nActiveOpponents': 1},
        'math': {'estimatedHandEquity': 0.28, 'potOddsEquity': 0.37, 'drawProfile': 'none',
                 'equitySource': 'vs_random'},
        'range_evaluation': {'recommendedPrimaryAction': 'call', 'rangeZone': 'outside_range'},
        'hand_profile': {}, 'context': {},
    }
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k] = {**d[k], **v}
        else:
            d[k] = v
    return d


def _lab(di):
    return (evaluate_decision(di).get('evaluation') or {}).get('label')


# ── G1 ─────────────────────────────────────────────────────────────────────────────────────
def test_g1_fold_que_o_preco_nao_paga_nao_e_erro_claro():
    """equity 28% contra pot odds 37%: o fold e +EV pela nossa propria conta."""
    assert _lab(_base()) not in ('clear_mistake', 'small_mistake')


def test_g1_empate_tecnico_tambem_nao_e_erro_claro():
    """Diferenca de meio ponto percentual e moeda ao alto, nao erro."""
    assert _lab(_base(math={'estimatedHandEquity': 0.240, 'potOddsEquity': 0.235})) \
        not in ('clear_mistake', 'small_mistake')


def test_g1_nao_absolve_fold_com_preco_folgado():
    """CONTROLE NEGATIVO: com equity bem acima do preco, foldar segue sendo acusavel. Sem isto o
    guarda viraria anistia geral de fold."""
    # Mao FEITA de proposito: com `air` quem manda e o bloco "sem gabarito nao e erro", que ja
    # capa em marginal por outro motivo, e o controle nao testaria o G1.
    di = _base(hero_cards='TdTs', math={'estimatedHandEquity': 0.55, 'potOddsEquity': 0.25})
    assert _lab(di) in ('small_mistake', 'clear_mistake'), _lab(di)


def test_g1_usa_pot_odds_e_nao_o_exigido_ajustado():
    """A referencia. `adjustedRequiredEquity` ja vem descontado por realizacao/pressao e fica
    quase sempre ABAIXO da equity — usa-lo fazia o guarda nunca disparar. Foi o que aconteceu na
    primeira versao, em silencio."""
    src = open(_ARQ, encoding='utf-8').read()
    i = src.index('_EMPATE_PP')
    trecho = src[i:i + 1400]
    linhas = [l for l in trecho.splitlines() if not l.lstrip().startswith('#')]
    corpo = '\n'.join(linhas)
    assert "math.get('potOddsEquity')" in corpo, 'o guarda parou de usar o pot odds cru'
    assert corpo.index("math.get('potOddsEquity')") < (
        corpo.index("adjustedRequiredEquity") if 'adjustedRequiredEquity' in corpo else 10**9), \
        'o exigido ajustado voltou a ter precedencia sobre o pot odds'


# ── G2 ─────────────────────────────────────────────────────────────────────────────────────
def _aqo(**m):
    return _base(street='preflop', player_action='call', hero_cards='AhQd',
                 spot={'position': 'UTG+2', 'board': [], 'effectiveStackBb': 20.3,
                       'facingSize': 31.4, 'facingToBb': 31.4, 'facingAllin': True,
                       'preflopRaisesFaced': 2, 'nPlayers': 8, 'nActiveOpponents': 1},
                 math={'estimatedHandEquity': 0.644, 'potOddsEquity': 0.40,
                       'equitySource': 'vs_random', **m},
                 range_evaluation={'recommendedPrimaryAction': 'call', 'rangeZone': 'in_range'})


def test_g4_o_card_NOMEIA_o_pote_com_allin_mesmo_sem_erro():
    """Familia 4, releitura de 07/08. A anotacao do coach era um CONCEITO, e o motor so tratava o
    assunto no veredito: em `standard`/`marginal` o `build_interpretation` retornava cedo e o card
    ficava mudo justamente onde havia algo a ensinar.

    Medido em 470 decisoes postflop reais: 50 tem all-in vivo no pote, o hero apostou em 3, e as
    tres eram mao de VALOR — o veredito ja estava certo nas tres. O que faltava era o texto.
    """
    from leaklab.decision_engine_v11 import evaluate_decision

    def _texto(di):
        return (evaluate_decision(di).get('interpretation') or {}).get('strategicExplanation', '')

    com = _base(player_action='bet', hero_cards='AdKd',
                spot={'hasAllinOpponent': True, 'board': ['7d', 'Tc', '6h'],
                      'nActiveOpponents': 2},
                range_evaluation={'recommendedPrimaryAction': 'bet', 'rangeZone': 'in_range'},
                math={'estimatedHandEquity': 0.72, 'potOddsEquity': 0.30})
    assert 'all-in' in _texto(com).lower(), _texto(com)
    assert 'pote lateral' in _texto(com), 'a frase precisa dizer O QUE muda, nao so que ha all-in'

    # CONTROLE 1: sem all-in no pote, o card `standard` segue mudo como sempre foi
    sem = _base(player_action='bet', hero_cards='AdKd',
                spot={'hasAllinOpponent': False, 'board': ['7d', 'Tc', '6h']},
                range_evaluation={'recommendedPrimaryAction': 'bet', 'rangeZone': 'in_range'},
                math={'estimatedHandEquity': 0.72, 'potOddsEquity': 0.30})
    assert _texto(sem) == '', repr(_texto(sem))

    # CONTROLE 2: quem so PAGA nao esta disputando pote lateral nenhum
    pagando = _base(player_action='call', hero_cards='AdKd',
                    spot={'hasAllinOpponent': True, 'board': ['7d', 'Tc', '6h']},
                    range_evaluation={'recommendedPrimaryAction': 'call', 'rangeZone': 'in_range'},
                    math={'estimatedHandEquity': 0.72, 'potOddsEquity': 0.30})
    assert _texto(pagando) == '', repr(_texto(pagando))

    # CONTROLE 3: preflop nao tem pote lateral formado por all-in de rua anterior
    pf = _base(player_action='bet', street='preflop', hero_cards='AdKd',
               spot={'hasAllinOpponent': True, 'board': []},
               range_evaluation={'recommendedPrimaryAction': 'bet', 'rangeZone': 'in_range'},
               math={'estimatedHandEquity': 0.72, 'potOddsEquity': 0.30})
    assert _texto(pf) == '', repr(_texto(pf))


def test_g5_familia_monstro_passivo_e_NOMEADO_sem_virar_acusacao():
    """Familia 5. "Foi pro slow play, tinha que crescer o pote" (#24) e "eu daria raise" (#74):
    nos DOIS o solver concordava com a linha passiva, entao acusar seria trocar o gabarito pela
    opiniao do coach. O que faltava era o card dizer que a mao estava no TOPO do range.

    Medido em 470 decisoes postflop reais: 37 monstros, 12 jogados passivamente.
    """
    from leaklab.decision_engine_v11 import evaluate_decision

    def _r(di):
        out = evaluate_decision(di)
        return ((out.get('evaluation') or {}).get('label'),
                (out.get('interpretation') or {}).get('strategicExplanation', ''))

    monstro = _base(player_action='call', hero_cards='6c8c',
                    spot={'board': ['Ks', '8s', '8d'], 'hasAllinOpponent': False},
                    range_evaluation={'recommendedPrimaryAction': 'call', 'rangeZone': 'in_range'},
                    math={'estimatedHandEquity': 0.88, 'potOddsEquity': 0.25})
    lab, txt = _r(monstro)
    assert 'topo do range' in txt, txt
    assert lab not in ('small_mistake', 'clear_mistake'), f'a nota virou acusacao: {lab}'

    # CONTROLE 1: trinca do BOARD nao e monstro do heroi — foi o caso que denunciou o bug do
    # `_ranks_of`, e sem o conserto esta linha receberia a nota indevidamente.
    _l2, t2 = _r(_base(player_action='call', hero_cards='9dQc',
                       spot={'board': ['3h', '3d', '3s']},
                       range_evaluation={'recommendedPrimaryAction': 'call',
                                         'rangeZone': 'in_range'},
                       math={'estimatedHandEquity': 0.30, 'potOddsEquity': 0.25}))
    assert 'topo do range' not in t2, t2

    # CONTROLE 2: quem JA apostou o monstro nao precisa ser lembrado de apostar
    _l3, t3 = _r(_base(player_action='bet', hero_cards='6c8c',
                       spot={'board': ['Ks', '8s', '8d']},
                       range_evaluation={'recommendedPrimaryAction': 'bet',
                                         'rangeZone': 'in_range'},
                       math={'estimatedHandEquity': 0.88, 'potOddsEquity': 0.25}))
    assert 'topo do range' not in t3, t3

    # CONTROLE 3: preflop nao tem board, entao nao ha monstro a nomear
    _l4, t4 = _r(_base(player_action='call', street='preflop', hero_cards='6c8c',
                       spot={'board': []},
                       range_evaluation={'recommendedPrimaryAction': 'call',
                                         'rangeZone': 'in_range'},
                       math={'estimatedHandEquity': 0.55, 'potOddsEquity': 0.25}))
    assert 'topo do range' not in t4, t4


def _call_barato(**kw):
    """Jogador PAGOU um preco folgado e o produto acusou. `pot odds` 10%, equity 48%."""
    d = dict(
        player_action='call', street='preflop', hero_cards='TdTs',
        spot={'position': 'BTN', 'board': [], 'effectiveStackBb': 38.0,
              'facingSize': 2.5, 'facingToBb': 2.5, 'preflopRaisesFaced': 2},
        math={'estimatedHandEquity': 0.48, 'potOddsEquity': 0.10, 'equitySource': 'vs_random'},
        range_evaluation={'recommendedPrimaryAction': 'fold', 'rangeZone': 'outside_range'})
    for k, v in kw.items():                     # o override do teste FUNDE, nao duplica
        d[k] = {**d[k], **v} if isinstance(v, dict) and isinstance(d.get(k), dict) else v
    return _base(**d)


def test_g5_call_com_preco_folgado_nao_e_erro():
    """O ESPELHO do G1, achado na releitura de 07/08. Em 72 decisoes o proprio card dizia "o preco
    fechava ... mas o fold vem da RANGE" e mesmo assim cravava `small_mistake`. Saber que o preco
    fecha e acusar assim mesmo e severidade contra a propria evidencia."""
    assert _lab(_call_barato()) not in ('small_mistake', 'clear_mistake')


def test_g5_nao_absolve_call_com_preco_apertado():
    """CONTROLE: com o preco perto da equity, a acusacao continua de pe — o guarda separa preco
    folgado de preco justo, nao absolve todo call."""
    caro = _call_barato(math={'estimatedHandEquity': 0.36, 'potOddsEquity': 0.33})
    assert _lab(caro) in ('small_mistake', 'clear_mistake'), _lab(caro)


def test_g4_PINO_semi_blefe_com_allin_no_pote_nao_e_linha_padrao():
    """PINO de regressão (15/08, P10 dos 'perdidos'): o G4 original JÁ cobre o semi-blefe,
    porque draws são 'air' para made_hand_category ("não conta draws"). Este teste fixa isso —
    se um dia a categoria ganhar 'draw' de verdade, o G4 precisa acompanhar ou este teste
    acusa. Nunca vira Erro: a categoria é grossa demais (AdKd high com 72% também é 'air');
    marginal tira a linha-padrão sem criar culpa."""
    # 8h4h em 7h-Ts-Qh: flush draw — 'draw', não 'air' nem mão feita.
    com_draw = _base(player_action='bet', hero_cards='4h8h',
                     spot={'hasAllinOpponent': True, 'board': ['7h', 'Ts', 'Qh'],
                           'position': 'BTN'},
                     range_evaluation={'recommendedPrimaryAction': 'bet', 'rangeZone': 'in_range'},
                     math={'estimatedHandEquity': 0.34, 'potOddsEquity': 0.0})
    assert _lab(com_draw) == 'marginal', _lab(com_draw)
    # CONTROLE: o MESMO semi-blefe sem all-in no pote segue standard (fold equity existe).
    sem_allin = _base(player_action='bet', hero_cards='4h8h',
                      spot={'hasAllinOpponent': False, 'board': ['7h', 'Ts', 'Qh'],
                            'position': 'BTN'},
                      range_evaluation={'recommendedPrimaryAction': 'bet', 'rangeZone': 'in_range'},
                      math={'estimatedHandEquity': 0.34, 'potOddsEquity': 0.0})
    assert _lab(sem_allin) == 'standard', _lab(sem_allin)
    print('OK  test_g4_ESTENDIDO_semi_blefe_com_allin_no_pote_nao_e_linha_padrao')


def test_g2_ESTENDIDO_um_raise_tambem_e_range_estreita():
    """Extensão de 15/08 (P7 dos 'perdidos'): defender o próprio open contra 3-bet-JAM
    (raisesFaced=1) é a mesma situação epistêmica do squeeze — vs-random não absolve.
    K3o exibia 51% vs-random e saía standard; contra a range real do jam não há base."""
    um_raise = _base(street='preflop', player_action='call', hero_cards='3dKc',
                     spot={'position': 'BTN', 'board': [], 'effectiveStackBb': 6.5,
                           'facingSize': 8.5, 'facingToBb': 8.51, 'facingAllin': True,
                           'preflopRaisesFaced': 1},
                     range_evaluation={'recommendedPrimaryAction': 'call', 'rangeZone': 'in_range'},
                     math={'estimatedHandEquity': 0.51, 'potOddsEquity': 0.34,
                           'equitySource': 'vs_random'})
    assert _lab(um_raise) == 'marginal', _lab(um_raise)
    # CONTROLE: equity medida contra RANGE (não aleatória) mantém a absolvição.
    com_range = _base(street='preflop', player_action='call', hero_cards='3dKc',
                      spot={'position': 'BTN', 'board': [], 'effectiveStackBb': 6.5,
                            'facingSize': 8.5, 'facingToBb': 8.51, 'facingAllin': True,
                            'preflopRaisesFaced': 1},
                      range_evaluation={'recommendedPrimaryAction': 'call', 'rangeZone': 'in_range'},
                      math={'estimatedHandEquity': 0.51, 'potOddsEquity': 0.34,
                            'equitySource': 'vs_range'})
    assert _lab(com_range) == 'standard', _lab(com_range)
    print('OK  test_g2_ESTENDIDO_um_raise_tambem_e_range_estreita')


def test_g5_nao_passa_por_cima_do_tratamento_de_range_estreita():
    """All-in com 2+ raises e a linha mais estreita do preflop, e ali a equity vs mao ALEATORIA
    nao vale como argumento — e o que o G2 trata.

    Medido ao escrever este teste: por este caminho o call contra all-in **nunca chega ao G5**,
    porque ja e capado antes (G2 rebaixa `standard`, e o facing-allin normaliza). Entao a clausula
    `not _range_estreita` e SEGUNDA BARREIRA, e dizer que ela "discrimina" seria mentira: eu
    escrevi o teste esperando `small_mistake` e o resultado era `marginal` com o guarda ligado ou
    desligado. O que da para provar, e esta provado aqui, e que o resultado nao piora nem melhora
    por causa do G5 — e que o G2 continua fazendo o trabalho dele.
    """
    estreito = _call_barato(
        spot={'position': 'BTN', 'board': [], 'effectiveStackBb': 20.0, 'facingSize': 20.0,
              'facingToBb': 20.0, 'facingAllin': True, 'preflopRaisesFaced': 2})
    assert _lab(estreito) == 'marginal', _lab(estreito)
    # e o G2 e quem faz isso: com equity medida contra RANGE, o mesmo spot volta a `standard`
    com_range = _call_barato(
        spot={'position': 'BTN', 'board': [], 'effectiveStackBb': 20.0, 'facingSize': 20.0,
              'facingToBb': 20.0, 'facingAllin': True, 'preflopRaisesFaced': 2},
        math={'equitySource': 'vs_range'})
    assert _lab(com_range) == 'standard', _lab(com_range)


def test_g5_nao_absolve_call_CARO_mesmo_com_margem_grande():
    """O teto de preco nao e decoracao, e a margem sozinha nao basta.

    Quanto mais caro o call, mais pesa a inflacao da equity estimada: 65% "de equity" contra um
    preco de 45% absolveria justamente o caso que o coach mandou FOLDAR (AQo contra 4-bet all-in,
    onde o 64,4% era vs mao aleatoria). O argumento do coach era sobre continuacao BARATA — "voce
    ja pos 2bb, pagar o all-in e so mais 5" —, e e so ate ali que o guarda vai.
    """
    caro = _call_barato(math={'estimatedHandEquity': 0.65, 'potOddsEquity': 0.45})
    assert _lab(caro) in ('small_mistake', 'clear_mistake'), _lab(caro)


def test_g5_usa_o_pot_odds_do_motor():
    """A referencia e `potOddsEquity`, calculado pelo motor com o pote RECONSTRUIDO. Somar duas
    colunas do banco foi como eu acusei o produto errado em 06/08 — sem o campo, nao age."""
    sem_preco = _call_barato(math={'estimatedHandEquity': 0.48, 'potOddsEquity': None})
    assert _lab(sem_preco) in ('small_mistake', 'clear_mistake'), _lab(sem_preco)


def test_g2_equity_vs_aleatoria_nao_abencoa_call_contra_4bet_allin():
    """64% vs mao aleatoria nao diz nada sobre uma range de 4-bet all-in por 20bb."""
    assert _lab(_aqo()) == 'marginal', _lab(_aqo())


def test_g2_nao_dispara_quando_a_equity_e_vs_RANGE():
    """CONTROLE: medida contra a range certa, a evidencia vale e o veredito fica de pe."""
    assert _lab(_aqo(equitySource='vs_range')) == 'standard'


def test_g2_nao_acusa_ninguem():
    """O guarda tira a absolvicao, nunca cria culpa: `marginal` nao conta como erro."""
    assert _lab(_aqo()) not in ('small_mistake', 'clear_mistake')


# ── G3 ─────────────────────────────────────────────────────────────────────────────────────
def _curto(stack, acao='raise'):
    return _base(street='preflop', player_action=acao, hero_cards='AhTd',
                 spot={'position': 'UTG', 'board': [], 'effectiveStackBb': stack,
                       'facingSize': 0.0, 'facingToBb': 0.0, 'nPlayers': 6,
                       'nActiveOpponents': 1},
                 math={'estimatedHandEquity': 0.63, 'potOddsEquity': None,
                       'equitySource': 'vs_random'},
                 range_evaluation={'recommendedPrimaryAction': 'raise', 'rangeZone': 'in_range'})


def test_g3_abaixo_de_10bb_a_recomendacao_vira_jam():
    r = evaluate_decision(_curto(9.2))
    assert (r.get('bestAction') or '').lower() == 'jam', r.get('bestAction')


def test_g3_acima_de_10bb_segue_raise():
    """CONTROLE: a 20bb o open pequeno existe na arvore e a recomendacao nao pode mudar."""
    r = evaluate_decision(_curto(20.0))
    assert (r.get('bestAction') or '').lower() == 'raise', r.get('bestAction')


# ── G4 ─────────────────────────────────────────────────────────────────────────────────────
def _blefe(allin_no_pote=True, cartas='4h8h'):
    return _base(street='flop', player_action='bet', hero_cards=cartas,
                 spot={'position': 'BTN', 'board': ['7h', 'Ts', 'Qh'],
                       'effectiveStackBb': 56.6, 'facingSize': 0.0, 'facingToBb': 0.0,
                       'hasAllinOpponent': allin_no_pote, 'nPlayers': 5, 'nActiveOpponents': 2},
                 math={'estimatedHandEquity': 0.34, 'potOddsEquity': None,
                       'equitySource': 'vs_random'},
                 # `bet` de proposito: com `check` o spot ja sai `marginal` por OUTRA regra, e
                 # ai o controle nao conseguiria mostrar diferenca nenhuma — foi o que aconteceu
                 # na primeira versao deste teste.
                 range_evaluation={'recommendedPrimaryAction': 'bet', 'rangeZone': 'in_range'})


def test_g4_blefe_em_pote_com_allin_nao_e_linha_padrao():
    """Contra quem nao pode foldar nao existe fold equity. Nao vira erro — deixa de ser padrao."""
    assert _lab(_blefe()) == 'marginal', _lab(_blefe())


def test_g4_sem_allin_no_pote_nada_muda():
    """CONTROLE: o guarda e do pote com all-in, nao de todo bet com mao fraca.

    Compara COM x SEM a flag em vez de cravar rotulo absoluto: o spot sintetico passa por outras
    regras do motor, e fixar "standard" testaria essas outras em vez desta."""
    # A afirmacao e simples: a flag TEM que mudar o veredito. A primeira versao deste controle
    # era um `or` que passava com o guarda quebrado (ignorando a flag), o que e cobertura sem
    # cobrir — verificado quebrando de proposito.
    com, sem = _lab(_blefe(allin_no_pote=True)), _lab(_blefe(allin_no_pote=False))
    assert com == 'marginal', com
    assert sem != com, f'a flag nao fez diferenca: com={com} sem={sem}'


def test_g4_nao_toca_mao_de_valor():
    """CONTROLE: apostar mao feita num pote com all-in e por VALOR, nao blefe. Com QQ em
    7-T-Q o hero tem trinca, e o guarda nao pode encostar nele."""
    com   = _lab(_blefe(cartas='QdQs', allin_no_pote=True))
    sem   = _lab(_blefe(cartas='QdQs', allin_no_pote=False))
    assert com == sem, f'o guarda mexeu numa mao de valor: {sem} -> {com}'


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
