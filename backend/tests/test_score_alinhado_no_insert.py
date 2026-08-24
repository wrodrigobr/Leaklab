# -*- coding: utf-8 -*-
"""Score gravado tem que estar na banda do label — inclusive no INSERT, não só no reconcile.

── O caso que originou (24/08, auditoria pré-lançamento) ──────────────────────────────────

27 decisões estavam gravadas com `label` de erro e `score` 0 ou nulo. Não era aleatório:
**27 de 27 tinham `gto_label = gto_critical`**, e 20 delas tinham `math_penalty`/`range_penalty`
maiores que zero ao lado do score zerado.

A causa: `_gto_label_cap` promove o LABEL quando a carta reprova a jogada (`gto_critical` → piso
em `small_mistake`) e não toca no SCORE. O `save_decisions` gravava `evaluation.mistakeScore`
cru, então saía uma linha dizendo "erro" com desvio zero.

`_align_score_to_label` já existia e resolvia — mas só rodava no reconcile. A prova de que o
caminho era esse: a banda de `small_mistake` é 0,19–0,35, então qualquer linha que tivesse
passado por ela teria 0,19, nunca 0.

── Por que isso não era cosmético ─────────────────────────────────────────────────────────

`repositories.py` calcula `priority_score = COUNT(*) * AVG(d.score)` para ordenar os leaks do
plano de estudo. Com score 0, as decisões que o SOLVER considera críticas eram justamente as
que puxavam a média da família para baixo e caíam no ranking do que estudar primeiro — o
inverso do pretendido.

Medido antes de aplicar: 63 linhas tocadas, 1 usuário de 8 com troca de ordem, e o topo do
plano não muda em nenhum. O conserto arruma a coerência sem virar o plano de cabeça para baixo.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_score_zero_com_label_de_erro_sobe_para_o_piso_da_banda():
    """Controle da função: sem isto, o teste de fiação abaixo protegeria um alinhador quebrado."""
    from database.repositories import _align_score_to_label as alinha

    assert alinha('small_mistake', 0.0) == 0.19, 'piso de small_mistake mudou'
    assert alinha('clear_mistake', 0.0) == 0.36, 'piso de clear_mistake mudou'
    # não infla quem já está dentro da banda
    assert alinha('small_mistake', 0.324) == 0.324, 'o alinhador passou a mexer em score válido'
    # e não rebaixa standard
    assert alinha('standard', 0.0) == 0.0, 'standard deixou de aceitar score 0'
    print('OK  test_score_zero_com_label_de_erro_sobe_para_o_piso_da_banda')


def test_o_insert_grava_o_score_alinhado():
    """Prova de fiação. O reconcile já alinhava; o INSERT é que gravava cru — e é por ele que
    passa TODA decisão nova. Testar só a função deixaria o buraco exatamente onde ele estava."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()

    i = fonte.index('def save_decisions')
    j = fonte.index('INSERT INTO decisions', i)
    corpo = fonte[i:j]
    # só o código: um comentário que menciona a função não prova que ela é chamada (regra 8)
    codigo = chr(10).join(l.split('#')[0] for l in corpo.split(chr(10)))

    assert 'mistakeScore' in codigo, 'save_decisions parou de ler o mistakeScore — alvo perdido'
    assert '_align_score_to_label(' in codigo, (
        '`save_decisions` voltou a gravar `mistakeScore` cru: acusação promovida pela carta '
        'entra com score 0 e afunda no priority_score do plano de estudo')
    print('OK  test_o_insert_grava_o_score_alinhado')


def test_label_e_score_gravados_ficam_coerentes():
    """A invariante de verdade, escrita como o consumidor a lê: para cada label, o score gravado
    cai na banda daquele label. É o que `priority_score` assume ao tirar média."""
    from database.repositories import _align_score_to_label as alinha, _LABEL_SCORE_BAND

    for label, (lo, hi) in _LABEL_SCORE_BAND.items():
        for bruto in (None, 0.0, 0.05, 0.25, 0.9, 2.0):
            v = alinha(label, bruto)
            assert lo - 1e-9 <= v <= hi + 1e-9, (
                'label %s com score bruto %s saiu %s, fora da banda (%s, %s)'
                % (label, bruto, v, lo, hi))
    print('OK  test_label_e_score_gravados_ficam_coerentes')


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
