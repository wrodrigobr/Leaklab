# -*- coding: utf-8 -*-
"""`leak` de custo infimo e rebaixado uma vez so, e as duas portas leem a MESMA regra.

-- O defeito (auditoria VER-6, 15/09) ------------------------------------------------------

O motor rebaixa `leak` cujo EV medido fica abaixo de `_PREFLOP_EV_MINOR_BB` (0,12bb): o
`gto_label` critico vira `gto_minor_deviation` e o score e capeado em marginal. O card
(`card_verdict.verdict_from_preflop`) mapeava `leak` direto para `gto_critical`, sem receber o
EV. Medido no acervo de auditoria: mao 257045975775 (A8o UTG 4,2bb, fold, carta manda jam,
qualidade `leak`, EV 0,0bb) tinha `gto_minor_deviation` na coluna e `gto_critical` no card, que
entao imprimia "desvio caro" ao lado de "Correto". ELO e drill leem a coluna; o jogador le o
card.

-- O que este arquivo defende --------------------------------------------------------------

1. A mesma qualidade + o mesmo EV dao o MESMO `gto_label` nas duas portas, sobre uma grade que
   cobre as seis qualidades e os dois lados do limiar.
2. O que NAO pode ser rebaixado continua critico: `major_leak` (erro de DIRECAO), `leak` sem EV
   medido, `leak` acima do limiar.
3. O spot real (A8o UTG 4,2bb) sai da porta de estrategia com quality `leak` e EV 0,0 e chega
   ao card ja rebaixado.
4. Varredura (regra 5): so `card_verdict` compara EV com o limiar; ninguem reimplementa.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RAIZ = os.path.join(os.path.dirname(__file__), '..')

# O mapa quality -> gto_label que o motor persiste (decision_engine_v11.analyze_decision).
QUALITY_TO_GTO_LABEL = {
    'correct':             'gto_correct',
    'acceptable':          'gto_mixed',
    'gto_minor_deviation': 'gto_minor_deviation',
    'minor_mistake':       'gto_minor_deviation',
    'leak':                'gto_critical',
    'major_leak':          'gto_critical',
}


def label_do_motor(quality, ev):
    from leaklab.card_verdict import rebaixa_gto_label_por_custo
    return rebaixa_gto_label_por_custo(
        QUALITY_TO_GTO_LABEL.get(quality, 'gto_critical'), quality, ev)


def label_do_card(quality, ev):
    from leaklab.card_verdict import verdict_from_preflop
    v = verdict_from_preflop(quality, 'jam', 'fold', ev)
    return (v or {}).get('gto_label')


def test_as_duas_portas_dao_o_mesmo_label_na_grade_inteira():
    from leaklab.card_verdict import limiar_de_ev_desprezivel
    lim = limiar_de_ev_desprezivel()
    evs = [None, 0.0, 0.006, lim - 0.001, lim, lim + 0.001, 0.281, 4.4]
    divergem = []
    for q in QUALITY_TO_GTO_LABEL:
        for ev in evs:
            m, c = label_do_motor(q, ev), label_do_card(q, ev)
            if m != c:
                divergem.append((q, ev, m, c))
    assert not divergem, 'motor e card discordam: %s' % divergem


def test_leak_barato_e_rebaixado_e_so_ele():
    from leaklab.card_verdict import leak_de_custo_infimo, limiar_de_ev_desprezivel
    lim = limiar_de_ev_desprezivel()
    assert leak_de_custo_infimo('leak', 0.0) is True
    assert leak_de_custo_infimo('leak', lim - 0.001) is True
    assert label_do_card('leak', 0.0) == 'gto_minor_deviation'
    # No limiar e acima, nao rebaixa.
    assert leak_de_custo_infimo('leak', lim) is False
    assert label_do_card('leak', 0.281) == 'gto_critical'
    # RC-A: major_leak e erro de DIRECAO, nunca rebaixa por EV.
    assert leak_de_custo_infimo('major_leak', 0.0) is False
    assert label_do_card('major_leak', 0.0) == 'gto_critical'
    # Sem EV medido nao ha atenuante (custo nao declarado nao vira desconto).
    assert leak_de_custo_infimo('leak', None) is False
    assert label_do_card('leak', None) == 'gto_critical'
    # Lixo no campo nao derruba nem rebaixa.
    assert leak_de_custo_infimo('leak', 'abc') is False


def test_quality_desconhecida_segue_devolvendo_none():
    from leaklab.card_verdict import verdict_from_preflop
    assert verdict_from_preflop('unknown', 'raise', 'call', 0.0) is None
    assert verdict_from_preflop(None, 'raise', 'call') is None


def test_o_resto_do_veredito_nao_muda():
    """Regra 7: o conserto so rebaixa o rotulo. is_error e a recomendacao ficam."""
    from leaklab.card_verdict import verdict_from_preflop
    sem_ev = verdict_from_preflop('leak', 'jam', 'fold')
    com_ev = verdict_from_preflop('leak', 'jam', 'fold', 0.0)
    assert sem_ev['is_error'] is True and com_ev['is_error'] is True
    assert sem_ev['reconciled_best'] == com_ev['reconciled_best'] == 'jam'
    correto = verdict_from_preflop('correct', 'jam', 'fold', 0.0)
    assert correto['is_error'] is False and correto['reconciled_best'] == 'fold'


def test_o_spot_real_a8o_utg_chega_rebaixado_ao_card():
    """A mao 257045975775 da auditoria, pela porta de estrategia que o /replay consulta."""
    from leaklab.strategy_provider import preflop_strategy
    pf = preflop_strategy(is_pko=False, position='UTG', hero_hand_type='A8o', stack_bb=4.2,
                          action_taken='fold', facing_size=0.0, vs_position='',
                          is_3bet_pot=False, n_players=9)['raw']
    assert pf.get('action_quality') == 'leak', pf.get('action_quality')
    assert pf.get('ev_loss_bb') == 0.0, pf.get('ev_loss_bb')
    assert label_do_card(pf['action_quality'], pf.get('ev_loss_bb')) == 'gto_minor_deviation'
    assert label_do_motor(pf['action_quality'], pf.get('ev_loss_bb')) == 'gto_minor_deviation'


def test_o_replay_passa_o_ev_ao_veredito_do_card():
    """Varredura da FIACAO: a chamada em api/app.py entrega 4 argumentos, nao 3."""
    with open(os.path.join(RAIZ, 'api', 'app.py'), encoding='utf-8') as f:
        arvore = ast.parse(f.read())
    chamadas = [n for n in ast.walk(arvore)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == '_v_pf']
    assert chamadas, 'a chamada do veredito preflop do card sumiu de api/app.py'
    for ch in chamadas:
        assert len(ch.args) + len(ch.keywords) >= 4, \
            'api/app.py:%d chama verdict_from_preflop sem o EV' % ch.lineno


# -- Varredura do limiar (regra 5) -----------------------------------------------------------

# Onde a comparacao com o limiar PODE aparecer. `preflop_gto_ranges._EV_MINOR_BB` fica de fora
# de proposito: la a regra e outra (rebaixa a QUALIDADE de `major_leak`/`minor_mistake` quando a
# acao tem frequencia zero mas a mao esta no range), e o comentario no fonte explica por que nao
# contradiz o RC-A.
DONO_DA_REGRA = ('leaklab', 'card_verdict.py')
VARRIDOS = [('leaklab', 'decision_engine_v11.py'), ('api', 'app.py'),
            ('leaklab', 'card_verdict.py')]


_NOMES_DO_LIMIAR = ('_PREFLOP_EV_MINOR_BB', 'limiar_de_ev_desprezivel')


def comparacoes_com_o_limiar(fonte):
    """Comparacoes (AST, nao texto: docstring nao conta) contra o limiar de EV desprezivel."""
    achados = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Compare):
            continue
        alvo = ast.dump(no)
        if any(("id='%s'" % n) in alvo or ("attr='%s'" % n) in alvo for n in _NOMES_DO_LIMIAR):
            achados.append((no.lineno, ast.dump(no)[:90]))
    return achados


def test_varredura_so_o_dono_da_regra_compara_com_o_limiar():
    for partes in VARRIDOS:
        with open(os.path.join(RAIZ, *partes), encoding='utf-8') as f:
            achados = comparacoes_com_o_limiar(f.read())
        if partes == DONO_DA_REGRA:
            assert len(achados) == 1, 'card_verdict deveria comparar UMA vez: %s' % achados
        else:
            assert not achados, '%s reimplementa o rebaixamento: %s' % ('/'.join(partes), achados)


def test_varredura_acha_o_caso_forjado():
    """Regra 1: o medidor tem de se mexer. O trecho e o do motor antes do conserto."""
    antigo = (
        "def analyze(quality, ev):\n"
        "    low = (quality == 'leak' and ev is not None and ev < _PREFLOP_EV_MINOR_BB)\n"
        "    return low\n"
    )
    assert len(comparacoes_com_o_limiar(antigo)) == 1
    consertado = (
        "def analyze(quality, ev):\n"
        "    from leaklab.card_verdict import leak_de_custo_infimo\n"
        "    return leak_de_custo_infimo(quality, ev)\n"
    )
    assert comparacoes_com_o_limiar(consertado) == []


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
