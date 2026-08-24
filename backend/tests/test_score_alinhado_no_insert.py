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


def test_as_DUAS_portas_do_score_alinham():
    """Regra 5: a política score↔label vale onde o número é GRAVADO e onde ele é SERVIDO.

    O conserto de 24/08 pegou só a gravação. O `/replay` recomputa o `error_label` ao vivo (e
    costuma sair mais severo que o do banco) mas servia o `score` da COLUNA — então a tela
    mostrava `small_mistake` com score 0 mesmo depois do backfill. Medido no torneio 7: 61 de
    485 abaixo do piso do label EXIBIDO, enquanto o banco reportava zero. Duas portas para o
    mesmo fato, uma consertada: o defeito mais recorrente deste projeto.
    """
    raiz = os.path.join(os.path.dirname(__file__), '..')
    portas = []
    # O alvo é a CHAVE DE SAÍDA (`'error_score':` com dois-pontos), não qualquer menção: a
    # primeira versão casou `error_score = d.get('error_score')` — uma linha que só repassa — e
    # acusou a porta certa como se estivesse quebrada.
    for pasta, arquivo, alvo in (('database', 'repositories.py', 'mistakeScore'),
                                 ('api', 'app.py', "'error_score':")):
        caminho = os.path.join(raiz, pasta, arquivo)
        with open(caminho, encoding='utf-8') as fh:
            fonte = fh.read()
        assert alvo in fonte, 'a porta %s/%s perdeu o alvo %s' % (pasta, arquivo, alvo)
        for m in __import__('re').finditer(alvo.replace('(', r'\('), fonte):
            trecho = fonte[max(0, m.start() - 400):m.start() + 400]
            codigo = chr(10).join(l.split('#')[0] for l in trecho.split(chr(10)))
            portas.append(('%s/%s:%d' % (pasta, arquivo,
                                         fonte[:m.start()].count(chr(10)) + 1),
                           '_align_score_to_label(' in codigo))

    faltando = [nome for nome, ok in portas if not ok]
    assert len(portas) >= 2, 'a varredura perdeu uma das portas'
    assert not faltando, (
        'porta que entrega score SEM alinhar ao label: %s — o número volta a contradizer o '
        'veredito ao lado dele' % ', '.join(faltando))
    print('OK  test_as_DUAS_portas_do_score_alinham (%d portas)' % len(portas))


def test_o_score_ESCALA_pelo_custo_em_vez_de_carimbar_o_piso():
    """Clampar no piso resolvia a contradição e criava outra: 59 de 77 acusações de um torneio
    ficaram com EXATAMENTE 0,19, com `ev_loss` de 0,000 a 3,816bb. Coerente e cego — e como
    `priority_score = COUNT(*) * AVG(score)` ordena o plano, a ordenação passou a depender só da
    contagem. Um juiz de poker leu o sintoma direto na tela: "quanto menos o motor sabe do custo,
    mais duro ele acusa"."""
    from database.repositories import _align_score_to_label as alinha

    barato = alinha('small_mistake', 0.0, 0.1)
    caro   = alinha('small_mistake', 0.0, 3.8)
    assert barato < caro, 'custo de 0,1bb e de 3,8bb recebem o mesmo score: voltou o achatamento'
    assert caro > barato + 0.10, (
        'a escala distingue de menos (%s vs %s): metade da banda tem que separar ruído de 3,8bb'
        % (barato, caro))
    # extremos continuam dentro da banda
    assert 0.19 <= barato <= 0.35 and 0.19 <= caro <= 0.35, 'a escala saiu da banda'
    # sem custo medido, o piso — é o que se pode afirmar sem base
    assert alinha('small_mistake', 0.0) == 0.19, 'sem gabarito deixou de ficar no piso'
    # e o teto não é dominado pela cauda (max do acervo é 116bb)
    assert alinha('small_mistake', 0.0, 116.0) == 0.35, 'a cauda passou a estourar a banda'
    print('OK  test_o_score_ESCALA_pelo_custo_em_vez_de_carimbar_o_piso')


def test_as_duas_portas_PASSAM_o_custo():
    """A escala só vale se alguém a alimentar. Melhorar a função e deixar os chamadores passando
    dois argumentos é o mesmo buraco do clamp RC-D, que ficou desligado por não receber o 5º."""
    import re
    raiz = os.path.join(os.path.dirname(__file__), '..')
    sem_custo = []
    for pasta, arquivo in (('database', 'repositories.py'), ('api', 'app.py')):
        caminho = os.path.join(raiz, pasta, arquivo)
        with open(caminho, encoding='utf-8') as fh:
            fonte = fh.read()
        for m in re.finditer(r'_align_score_to_label\(', fonte):
            i = m.end()
            nivel, j = 1, i
            while j < len(fonte) and nivel > 0:
                if fonte[j] == '(':
                    nivel += 1
                elif fonte[j] == ')':
                    nivel -= 1
                j += 1
            chamada = fonte[m.start():j]
            codigo = chr(10).join(l.split('#')[0] for l in chamada.split(chr(10)))
            if 'ev_loss' not in codigo:
                sem_custo.append('%s/%s:%d' % (pasta, arquivo,
                                               fonte[:m.start()].count(chr(10)) + 1))
    assert not sem_custo, (
        'chamada a _align_score_to_label SEM o custo (%s): o score volta a carimbar o piso e '
        'todas as acusações viram o mesmo número' % ', '.join(sem_custo))
    print('OK  test_as_duas_portas_PASSAM_o_custo')


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
