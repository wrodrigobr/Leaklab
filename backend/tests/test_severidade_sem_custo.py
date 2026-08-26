# -*- coding: utf-8 -*-
"""Sem CUSTO medido, o veredito não afirma MAGNITUDE.

── O caso que originou (26/08) ────────────────────────────────────────────────────────────

`pode_falar_como_gto` já tinha resolvido a LINGUAGEM: sem custo medido a tela não chama o desvio
de leak. Faltava a magnitude, e ela vazava por dois caminhos, medidos no acervo:

  * **47 `clear_mistake` com `ev_loss_bb` NULL nos 47** — o veredito mais duro do produto, sem um
    bb atrás dele.
  * **score até 0,900 sem custo**, com a MESMA mediana de quem tem custo (0,270 contra 0,267). A
    origem é `opp_cost = top_freq - played_freq` multiplicado por 0,90 no motor: um gap de
    FREQUÊNCIA com nome de custo. É a família de `project_severidade_por_ev` ("o motor sabia com
    que frequência e não sabia quanto custa") viva em outro caminho. E como
    `priority_score = COUNT(*) * AVG(score)` ordena o plano de estudo, a magnitude inventada
    decidia o que o aluno estuda primeiro.

A linha é: **frequência é medida, custo não.** Jogada que a carta faz 0% das vezes sustenta "isto
está fora da estratégia"; não sustenta "isto custou caro".

── Por que a acusação NÃO cai ─────────────────────────────────────────────────────────────

Regra 7 do CLAUDE.md ao contrário: o conserto fácil seria absolver tudo sem custo, e isso apagaria
leaks reais que a carta acusa com razão. O que cai é só o topo da escala.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_o_topo_da_escala_exige_custo():
    from leaklab.verdict import severidade_sem_custo
    assert severidade_sem_custo('clear_mistake', False) == 'small_mistake', (
        'o veredito mais duro do produto voltou a sair sem um bb de custo medido')
    print('OK  test_o_topo_da_escala_exige_custo')


def test_com_custo_NADA_muda():
    """Contraprova — é ela que dá valor ao teste acima. Um guarda que rebaixasse sempre também
    passaria na primeira asserção, e teria apagado 45 acusações legítimas."""
    from leaklab.verdict import severidade_sem_custo
    assert severidade_sem_custo('clear_mistake', True) == 'clear_mistake', (
        'acusação COM custo medido foi rebaixada: o guarda virou peneira geral')
    for label in ('standard', 'marginal', 'small_mistake'):
        assert severidade_sem_custo(label, True) == label
    print('OK  test_com_custo_NADA_muda')


def test_a_regra_NAO_absolve():
    """Sem custo, `small_mistake` continua acusação. Frequência zero é evidência de verdade — o
    que falta é base para o TAMANHO, não para o fato."""
    from leaklab.verdict import severidade_sem_custo
    assert severidade_sem_custo('small_mistake', False) == 'small_mistake', (
        'a regra passou a absolver: sem custo o desvio deixou de ser acusação, e isso apaga leak '
        'real que a carta acusa com razão')
    assert severidade_sem_custo('marginal', False) == 'marginal'
    assert severidade_sem_custo('standard', False) == 'standard'
    print('OK  test_a_regra_NAO_absolve')


def test_o_score_CAI_JUNTO_sem_precisar_de_regra_propria():
    """A outra metade do problema — e a lição de que ela NÃO precisava de código novo.

    Minha primeira versão capava o score no piso da banda quando não havia custo. **Dois guardas
    antigos acusaram, com razão:** `_align_score_to_label` não pode mexer em score que já está
    dentro da banda, senão 59 de 77 acusações voltam a valer exatamente 0,19 e o plano de estudo
    volta a ordenar só pela contagem (a lesão de 24/08).

    O teto do RÓTULO resolve sozinho: com `clear_mistake` virando `small_mistake`, a banda passa
    a ser [0,19; 0,35] e o 0,900 é clampado pelo `hi` que sempre existiu. O score cai de 0,900
    para 0,35 sem uma linha de regra nova.
    """
    from database.repositories import _align_score_to_label
    from leaklab.verdict import severidade_sem_custo

    label_cru, score_cru = 'clear_mistake', 0.90
    label = severidade_sem_custo(label_cru, False)
    assert _align_score_to_label(label, score_cru, None) == 0.35, (
        'o score sem custo voltou a afirmar magnitude; era 0,900 com zero bb medido')
    # com custo, o mesmo par segue valendo 0,900
    assert _align_score_to_label(severidade_sem_custo(label_cru, True), score_cru, 3.0) == 0.90
    print('OK  test_o_score_CAI_JUNTO_sem_precisar_de_regra_propria')


def test_o_alinhador_NAO_foi_tocado():
    """O guarda que me pegou. `_align_score_to_label` não pode mexer em score válido dentro da
    banda — foi assim que a versão de 24/08 achatou 59 de 77 acusações em 0,19."""
    from database.repositories import _align_score_to_label
    assert _align_score_to_label('small_mistake', 0.324) == 0.324, (
        'o alinhador voltou a mexer em score que já está dentro da banda')
    baixo = _align_score_to_label('small_mistake', 0.05, 0.20)
    alto = _align_score_to_label('small_mistake', 0.05, 2.00)
    assert alto > baixo, 'o score parou de escalar com o custo medido'
    print('OK  test_o_alinhador_NAO_foi_tocado')


def _fonte(caminho):
    with open(os.path.join(os.path.dirname(__file__), '..', *caminho.split('/')),
              encoding='utf-8') as fh:
        return '\n'.join(l.split('#')[0] for l in fh.read().split('\n'))


def test_as_DUAS_camadas_aplicam_a_regra():
    """Regra 5 + a lição do `/replay`: o motor grava e a camada viva RECOMPUTA. Conserto que só
    existe num dos dois deixa a tela contradizendo o banco — já custou duas voltas com o score e
    uma com o piso de custo."""
    motor = _fonte('leaklab/decision_engine_v11.py')
    vivo = _fonte('api/app.py')
    assert 'severidade_sem_custo' in motor, (
        'o motor parou de aplicar o teto de severidade: volta a gravar clear_mistake sem custo')
    assert 'severidade_sem_custo' in vivo, (
        'a camada viva do /replay parou de aplicar o teto: a tela volta a exibir o veredito mais '
        'duro sem custo, contradizendo o que o banco passou a gravar')
    print('OK  test_as_DUAS_camadas_aplicam_a_regra')


def test_o_card_nao_chama_de_CARO_o_que_nao_tem_preco():
    """A terceira superfície. O card dizia `card.costCritical` — em pt-BR, **"desvio caro"** — sob
    o rótulo "Custo", derivado só de `gto_label`, que é FREQUÊNCIA. Bug de vitrine escapa da
    suíte de backend, então a varredura é textual mesmo."""
    raiz = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src')
    with open(os.path.join(raiz, 'components', 'replayer', 'SidePanels.tsx'), encoding='utf-8') as fh:
        card = fh.read()
    # `qualificadorDeCusto(` e nao `qualificadorDeCusto`: a MENCAO e satisfeita pelo import no
    # topo do arquivo, e o guarda passou verde com a chamada trocada. Mesmo vies da varredura de
    # `balde_rfi` hoje de manha -- ancorar na condicao, nao no efeito.
    assert 'qualificadorDeCusto({' in card, (
        'o card voltou a derivar o qualificador de CUSTO direto do `gto_label`: sem custo medido '
        'ele volta a dizer "desvio caro"')
    with open(os.path.join(raiz, 'lib', 'cardLogic.ts'), encoding='utf-8') as fh:
        logica = fh.read()
    assert 'unmeasured' in logica, 'o estado "custo não medido" sumiu do qualificador'
    for loc in ('pt-BR', 'en', 'es'):
        with open(os.path.join(raiz, 'i18n', 'locales', loc, 'replayer.json'), encoding='utf-8') as fh:
            assert 'costUnmeasured' in fh.read(), 'locale %s sem a string do custo não medido' % loc
    print('OK  test_o_card_nao_chama_de_CARO_o_que_nao_tem_preco')


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
