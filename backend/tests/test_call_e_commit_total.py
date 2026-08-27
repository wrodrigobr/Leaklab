# -*- coding: utf-8 -*-
"""O call que já leva o stack inteiro É o jam da carta.

── O caso que originou (27/08) ────────────────────────────────────────────────────────────

A varredura de invariantes acusou `MUDO: 0 → 1` — "solver diz 0% de frequência e o produto
devolve standard". A linha era a decisão 325499 em produção:

    AJo, BTN, 1,4566bb efetivos, enfrentando um raise de 2,0bb de UTG.
    O hero PAGOU (all-in, porque pagar já custa tudo o que ele tem).
    A carta manda `jam`.

O raise de UTG já cobre o hero: `raise` não existe como opção, e `jam` e `call` movem
exatamente as mesmas fichas. Mesmo assim `analyze_preflop` compara PALAVRAS, chamou de `leak` e
gravou `gto_critical` com `ev_loss_bb = 0,141` — a diferença de EV entre duas ações idênticas.

O que a tela entregava, medido na captura do torneio 142:

    veredito ...... "Correto"          (`label = standard`)
    recomendação .. "jam"              (`best_action`)
    custo ......... "-0,141bb"         (`verdict_has_cost = True`)

Três afirmações que não cabem juntas: se está correto, não há o que recomendar nem o que cobrar.

── Por que a regra IRMÃ não pegava ────────────────────────────────────────────────────────

`colapsa_shove_para_call` (12/08) já cobre a direção oposta: o hero deu SHOVE sobre um all-in
cujo excesso ninguém podia pagar, então o shove era o call. Ela exige que a ação jogada esteja
em `_ACOES_DE_COMMIT` — e aqui a ação jogada é `call`. A equivalência é simétrica; o código
tinha só metade dela.

── A direção ──────────────────────────────────────────────────────────────────────────────

Colapsar nunca cria acusação: iguala a jogada à recomendação. E `fold` fica de fora — recomendar
fold contra um commit é crítica legítima, e o leak seria entrar na mão, não a palavra usada.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_pagar_o_stack_inteiro_e_commit_total():
    from leaklab.card_verdict import call_e_commit_total as f
    # o caso real, com o arredondamento que ele traz: 1,46 gravado contra 1,4566667
    assert f(1.46, 1.4566666666666668) is True
    assert f(12.0, 12.0) is True
    print('OK  test_pagar_o_stack_inteiro_e_commit_total')


def test_quem_fica_com_fichas_atras_NAO_e_commit_total():
    """A contraprova que impede a regra de virar peneira: com fichas atrás, jam e call são
    decisões diferentes de verdade, e gradar a diferença é o trabalho do produto."""
    from leaklab.card_verdict import call_e_commit_total as f
    assert f(2.0, 12.0) is False, 'call de 2bb num stack de 12bb virou "commit total"'
    assert f(1.0, 1.5) is False
    print('OK  test_quem_fica_com_fichas_atras_NAO_e_commit_total')


def test_ausencia_de_dado_NAO_vira_o_caso_que_convem():
    """`float(None)` levanta, e um `except` largo devolveria o que desse menos trabalho. Sem um
    dos dois números não afirmamos nada — a mesma armadilha do estimador de equity."""
    from leaklab.card_verdict import call_e_commit_total as f
    assert f(None, 12.0) is False
    assert f(1.46, None) is False
    assert f(1.46, 0) is False, 'stack zero não é commit: é ausência de stack'
    print('OK  test_ausencia_de_dado_NAO_vira_o_caso_que_convem')


def test_so_colapsa_quando_a_jogada_foi_CALL():
    from leaklab.card_verdict import colapsa_commit_para_call as f
    spot = {'facingToCallBb': 1.46, 'effectiveStackBb': 1.4566666666666668}
    assert f(spot, 'call') is True
    assert f(spot, 'calls') is True
    for acao in ('fold', 'raise', 'jam', 'check', 'shove'):
        assert f(spot, acao) is False, 'colapsou uma jogada que não é call: %s' % acao
    print('OK  test_so_colapsa_quando_a_jogada_foi_CALL')


def test_a_regra_IRMA_continua_de_pe():
    """As duas metades da equivalência andam juntas. Quem "unificar" as duas numa só precisa
    manter que cada uma exige uma jogada diferente."""
    from leaklab.card_verdict import colapsa_shove_para_call as f
    assert f({'shoveEquivaleCall': True}, 'shove') is True
    assert f({'shoveEquivaleCall': True}, 'call') is False
    print('OK  test_a_regra_IRMA_continua_de_pe')


def test_a_carta_colapsada_devolve_correct_e_call():
    """COMPORTAMENTO, não presença de chamada. A 1ª versão deste arquivo tinha só guardas de
    fiação e passou verde com a condição do motor trocada por `False` — o mesmo viés de 25/08.
    Uma função pura tira a desculpa: aqui o teste vê o resultado."""
    from leaklab.card_verdict import carta_colapsada_por_commit_total as f
    spot = {'facingToCallBb': 1.46, 'effectiveStackBb': 1.4566666666666668}
    q, rec, custo_ok = f('leak', ['jam'], spot, 'call')
    assert q == 'correct', 'o call que já leva tudo voltou a ser `leak` por causa da PALAVRA'
    assert rec == ['call'], 'a recomendação continuou dizendo `jam` a quem já foi all-in'
    assert custo_ok is False, 'sobrou custo entre duas ações que movem as mesmas fichas'
    print('OK  test_a_carta_colapsada_devolve_correct_e_call')


def test_a_carta_NAO_e_tocada_quando_a_regra_nao_e_dela():
    """Cada condição conferida sozinha — senão a função vira "aprova tudo" com nome específico."""
    from leaklab.card_verdict import carta_colapsada_por_commit_total as f
    fundo = {'facingToCallBb': 2.0, 'effectiveStackBb': 12.0}     # sobra stack: são decisões diferentes
    curto = {'facingToCallBb': 1.46, 'effectiveStackBb': 1.4566666666666668}
    assert f('leak', ['jam'], fundo, 'call') == ('leak', ['jam'], True)
    assert f('leak', ['jam'], curto, 'fold') == ('leak', ['jam'], True), (
        'colapsou um FOLD: recomendar fold contra um commit é crítica legítima')
    assert f('leak', ['fold'], curto, 'call') == ('leak', ['fold'], True), (
        'colapsou contra uma recomendação de FOLD — o leak ali é entrar na mão')
    assert f('correct', ['jam'], curto, 'call') == ('correct', ['jam'], True), (
        'mexeu no que já estava correto, e de quebra apagou o custo')
    print('OK  test_a_carta_NAO_e_tocada_quando_a_regra_nao_e_dela')


def test_o_motor_CHAMA_a_funcao_pura():
    """Fiação — e só fiação. O que ela protege é a função ser chamada; o que a função FAZ está
    coberto pelos dois testes acima, que uma condição desligada não consegue enganar."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index('preflop_gto = _enrich_preflop_gto(input_data)')
    trecho = codigo[i:i + 1400]
    assert '_colapsa_carta(' in trecho, (
        'o motor parou de colapsar na porta da CARTA preflop — é ela que grava `gto_label` e '
        '`gto_action`; consertar em `range_eval` não alcança (errei exatamente isso na 1ª volta)')
    assert "'ev_loss_bb': None" in trecho, (
        'o colapso parou de zerar o EV: a tela volta a cobrar bb por diferença que não existe')
    print('OK  test_o_motor_CHAMA_a_funcao_pura')


def test_a_CAMADA_VIVA_do_replay_tambem_colapsa():
    """O /replay reconsulta a carta por conta propria, entao o conserto no motor nao chega la.

    Medido depois do regrade em producao: a LISTA ja dizia `call`/`gto_correct` e o CARD seguia
    com "Correto" ao lado de "recomendado: jam" e o selo `gto_critical`. E a mesma forma que ja
    custou voltas com o score, com o piso de custo e com a coerencia da recomendacao — regra 5:
    a regra vale nas N portas, e o guarda varre N+1.
    """
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index("preflop_override_action = _pf['recommended_actions'][0]")
    # a janela olha para TRAS: o colapso precisa acontecer ANTES de a recomendacao ser lida
    assert '_colapsa_carta_viva(' in codigo[max(0, i - 900):i], (
        'a camada viva do /replay parou de colapsar: o card volta a dizer "recomendado: jam" '
        'para quem pagou all-in, com "Correto" do lado')
    print('OK  test_a_CAMADA_VIVA_do_replay_tambem_colapsa')


def test_as_DUAS_portas_usam_a_MESMA_funcao():
    """Regra 5 com varredura N+1: motor e camada viva. Se alguem reintroduzir a condicao inline
    numa delas, as duas divergem em silencio e so uma recebe o proximo conserto."""
    base = os.path.dirname(__file__)
    n = 0
    for rel in (('..', 'leaklab', 'decision_engine_v11.py'), ('..', 'api', 'app.py')):
        with open(os.path.join(base, *rel), encoding='utf-8') as fh:
            codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
        n += codigo.count('carta_colapsada_por_commit_total')
    assert n >= 2, 'a funcao deixou de ser compartilhada: %d consumidor(es) de 2' % n
    print('OK  test_as_DUAS_portas_usam_a_MESMA_funcao')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
