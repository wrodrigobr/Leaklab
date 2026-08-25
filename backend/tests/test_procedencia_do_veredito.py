# -*- coding: utf-8 -*-
"""Todo veredito declara DE ONDE veio: solver, carta ou motor.

── A pergunta que originou (24/08) ────────────────────────────────────────────────────────

"O que precisamos para garantir que o veredito seja confiável?" Medindo o acervo antes de
responder: **1.503 decisões (14,8%) não conseguiam dizer de onde veio o veredito** — não estavam
erradas, estavam MUDAS, porque o campo nunca existiu. Sem ele, "confiável" não é verificável:
não dá para separar "o solver disse" de "o motor achou" olhando o dado gravado.

O dano concreto: **189 de 495 acusações** em que a carta reprova a jogada (38%) saíam sem um bb
de custo e usavam a linguagem de GTO na tela assim mesmo. Um juiz de poker leu o sintoma sem ver
o código: "quanto menos o motor sabe do custo, mais duro ele acusa".

── Dois erros que a MEDIÇÃO pegou, e que este teste congela ────────────────────────────────

1. A 1ª versão olhava só `gto.available` e classificou **378 decisões preflop como `solver`** —
   no preflop o motor também preenche `gto`, com `ev_loss_source: 'gw_har'`, que é a CARTA do
   GTO Wizard, não um nó resolvido. Campo preenchido e errado é pior que vazio.
2. A 1ª regra de linguagem exigia `solver` para falar como GTO, e teria calado 358 decisões
   preflop legítimas: a carta É estratégia de equilíbrio. O que a regra barra é `motor`.

── Por que dois campos, e não um ──────────────────────────────────────────────────────────

`verdict_source` e `verdict_has_cost` são separados de propósito. Um nó do solver pode não
trazer EV utilizável (fora da calibração, nó degenerado), e juntar as duas coisas foi o que
deixou a acusação herdar a autoridade do solver sem herdar o número.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_a_procedencia_segue_a_FONTE_e_nao_o_available():
    """Controle: sem estes casos, classificar tudo como 'solver' passaria."""
    from leaklab.verdict import procedencia, SOLVER, CARTA, MOTOR

    # preflop com carta do GW: é CARTA, mesmo com `gto.available` True
    gw = {'available': True, 'ev_loss_source': 'gw_har'}
    assert procedencia(gw, None, 'preflop') == CARTA, (
        'carta do GTO Wizard voltou a ser classificada como nó do solver — foi assim que 378 '
        'decisões preflop saíram com procedência errada')
    # nó resolvido postflop: é SOLVER
    no = {'available': True, 'ev_loss_source': 'solver_hand'}
    assert procedencia(no, None, 'turn') == SOLVER, 'nó do solver deixou de ser solver'
    # sem fonte declarada, a street decide
    assert procedencia({'available': True}, None, 'preflop') == CARTA
    assert procedencia({'available': True}, None, 'flop') == SOLVER
    # sem gabarito nenhum: motor, nunca None
    assert procedencia(None, None, 'flop') == MOTOR, 'spot sem cobertura ficou sem procedência'
    print('OK  test_a_procedencia_segue_a_FONTE_e_nao_o_available')


def test_procedencia_NUNCA_e_vazia():
    """Campo "às vezes preenchido" é pior que campo inexistente: some a base de qualquer
    invariante."""
    from leaklab.verdict import procedencia, SOLVER, CARTA, MOTOR
    validos = (SOLVER, CARTA, MOTOR)
    for gto in (None, {}, {'available': False}, {'available': True, 'ev_loss_source': 'x'}):
        for pf in (None, {}, {'available': True}):
            for st in (None, '', 'preflop', 'flop', 'turn', 'river'):
                v = procedencia(gto, pf, st)
                assert v in validos, 'procedência inválida: %r' % v
    print('OK  test_procedencia_NUNCA_e_vazia')


def test_so_quem_tem_equilibrio_E_custo_fala_como_GTO():
    from leaklab.verdict import pode_falar_como_gto, SOLVER, CARTA, MOTOR

    assert pode_falar_como_gto(SOLVER, True) is True
    assert pode_falar_como_gto(CARTA, True) is True, (
        'a carta do GW deixou de poder falar como GTO — ela É equilíbrio, e a regra calaria '
        '358 decisões preflop legítimas')
    assert pode_falar_como_gto(SOLVER, False) is False, 'acusação sem custo voltou a falar GTO'
    assert pode_falar_como_gto(MOTOR, True) is False, (
        'heurístico voltou a poder dizer "leak": é a falsa confiança que a procedência existe '
        'para eliminar')
    print('OK  test_so_quem_tem_equilibrio_E_custo_fala_como_GTO')


def test_o_motor_declara_procedencia_em_TODA_saida():
    """Fiação no motor. `evaluate_decision` tem DOIS pontos de saída — o principal e o atalho do
    check de BB em pote não contestado. O atalho foi esquecido na primeira versão e devolvia a
    procedência vazia, o que só apareceu ao medir 485 decisões e achar 1 com None."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    i = fonte.index('def evaluate_decision')
    j = fonte.index(chr(10) + 'def ', i + 10)
    corpo = fonte[i:j]
    n_saidas = corpo.count('"handId": input_data["hand_id"]')
    n_proc = corpo.count('"verdictSource"')
    assert n_saidas >= 2, 'a varredura perdeu os pontos de saída (achou %d)' % n_saidas
    assert n_proc == n_saidas, (
        'ponto de saída do motor sem `verdictSource`: %d saídas, %d declaram procedência'
        % (n_saidas, n_proc))
    print('OK  test_o_motor_declara_procedencia_em_TODA_saida (%d saídas)' % n_saidas)


def test_as_portas_de_gravacao_e_leitura_carregam_a_procedencia():
    """Regra 5: a política vale onde o veredito é GRAVADO e onde é SERVIDO."""
    raiz = os.path.join(os.path.dirname(__file__), '..')
    faltando = []

    with open(os.path.join(raiz, 'database', 'repositories.py'), encoding='utf-8') as fh:
        repo = fh.read()
    i = repo.index('INSERT INTO decisions')
    cabecalho = repo[i:i + 1400]
    if 'verdict_source' not in cabecalho or 'verdict_has_cost' not in cabecalho:
        faltando.append('INSERT nao grava a procedencia')
    # e o valor vem da RAIZ do retorno do motor, não de `evaluation` (erro real de 24/08)
    corpo_valores = repo[max(0, i - 3000):i]
    if "r.get('verdictSource')" not in corpo_valores:
        faltando.append('valores do INSERT nao leem verdictSource da raiz')

    with open(os.path.join(raiz, 'api', 'app.py'), encoding='utf-8') as fh:
        app = fh.read()
    # CHAVE DE SAÍDA (com dois-pontos), não qualquer menção: a string também aparece nos
    # helpers que LEEM a coluna, e por isso a mutação "a API para de servir" passou verde.
    if "'verdict_source':" not in app:
        faltando.append('/replay nao serve verdict_source')
    if "'verdict_has_cost':" not in app:
        faltando.append('/replay nao serve verdict_has_cost')
    if 'pode_falar_como_gto' not in app:
        faltando.append('/replay nao serve o gate de linguagem GTO')

    assert not faltando, 'portas sem procedencia: %s' % '; '.join(faltando)
    print('OK  test_as_portas_de_gravacao_e_leitura_carregam_a_procedencia')


def test_a_coluna_existe_nos_DOIS_backends():
    """SQLite (dev/testes) e PostgreSQL (prod). Migração num só backend passa verde no CI e
    quebra em produção."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    assert 'ADD COLUMN verdict_source TEXT' in fonte, 'migração SQLite ausente'
    assert 'ADD COLUMN IF NOT EXISTS verdict_source TEXT' in fonte, 'migração PG ausente'
    assert 'verdict_has_cost' in fonte, 'coluna de custo ausente'
    print('OK  test_a_coluna_existe_nos_DOIS_backends')


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
