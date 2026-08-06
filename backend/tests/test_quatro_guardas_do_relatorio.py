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
