"""
Invariante do veredito: qualquer indício de erro de DIREÇÃO (GTO folda a mão mas hero agrediu)
⇒ a mão NUNCA pode ser 'standard'/'marginal' (não-erro). Cobre o sinal canônico
(is_verdict_error_signal) + a rede de segurança da reconciliação (_reconcile_label).
Regressão do caso KTo UTG (decisão 36471).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from database.repositories import is_verdict_error_signal, _reconcile_label


def test_signal_gto_fold_aggressive():
    assert is_verdict_error_signal('fold', 'raise') is True
    assert is_verdict_error_signal('fold', 'shove') is True
    assert is_verdict_error_signal('fold', 'bet') is True
    print("OK  test_signal_gto_fold_aggressive")


def test_signal_correct_actions_not_flagged():
    assert is_verdict_error_signal('fold', 'fold') is False     # foldar quando GTO folda = correto
    assert is_verdict_error_signal('raise', 'raise') is False   # agride quando GTO agride = correto
    assert is_verdict_error_signal('fold', 'call') is False     # call não-agressivo (depende do gto_label)
    print("OK  test_signal_correct_actions_not_flagged")


def test_signal_freq_zero_aggressive():
    assert is_verdict_error_signal('raise', 'bet', played_freq=0.0) is True   # bet com freq ~0
    assert is_verdict_error_signal('call', 'bet', played_freq=0.30) is False  # freq alta = ok
    print("OK  test_signal_freq_zero_aggressive")


def test_reconcile_floors_kto_case():
    # KTo UTG (36471): raise quando GTO folda, gto_label leniente → DEVE virar small_mistake.
    assert _reconcile_label('marginal', 'gto_minor_deviation', street='preflop',
                            action_taken='raise', gto_action='fold') == 'small_mistake'
    print("OK  test_reconcile_floors_kto_case")


def test_reconcile_floors_gto_critical():
    assert _reconcile_label('marginal', 'gto_critical', street='preflop',
                            action_taken='raise', gto_action='fold') == 'small_mistake'
    print("OK  test_reconcile_floors_gto_critical")


def test_reconcile_preserves_legit_mix():
    # gto_mixed: a agressão pode ser co-ótima → NÃO pune (não vira erro).
    assert _reconcile_label('standard', 'gto_mixed', street='preflop',
                            action_taken='raise', gto_action='fold') == 'standard'
    print("OK  test_reconcile_preserves_legit_mix")


def test_reconcile_keeps_existing_higher_severity():
    # Se já era clear_mistake, não rebaixa.
    assert _reconcile_label('clear_mistake', 'gto_minor_deviation', street='preflop',
                            action_taken='raise', gto_action='fold') == 'clear_mistake'
    print("OK  test_reconcile_keeps_existing_higher_severity")


def test_score_aligns_to_label_band():
    # Classe C: o score é clampado na banda do label (verdictLevelFromScore == verdictLevel(label)).
    from database.repositories import _align_score_to_label
    assert _align_score_to_label('standard', 0.89) == 0.08        # poluído → teto standard (<=0.08)
    assert _align_score_to_label('small_mistake', 0.0) == 0.19    # erro com score 0 → piso erro (>0.18)
    assert _align_score_to_label('marginal', 0.04) == 0.09        # abaixo → piso marginal (>0.08)
    assert _align_score_to_label('marginal', 0.12) == 0.12        # in-banda → preserva
    assert _align_score_to_label('clear_mistake', 0.0) == 0.36
    print("OK  test_score_aligns_to_label_band")


def test_mix_LEGITIMO_nao_leva_piso_de_direcao():
    """Num no MISTO, agredir e o outro lado do mix — nao e erro de direcao.

    Medido em producao em 11/08: 12 decisoes com o selo `GTO Correto` e o veredito
    `small_mistake` no MESMO card, todas com score 0,19 exato. Eram nos em que o solver tomava a
    acao do hero entre 30% e 49% do tempo. A regra existia em dois lugares e so a copia do
    reconcile excluia o mix; a do motor estava escrita a mao, sem a exclusao, sob um comentario
    afirmando que espelhava a outra.
    """
    from leaklab.verdict import piso_por_direcao
    for mix in ('gto_correct', 'gto_mixed'):
        assert piso_por_direcao('standard', mix, 'fold', 'raise') == 'standard', mix
        assert piso_por_direcao('marginal', mix, 'fold', 'shove') == 'marginal', mix
    # CONTROLE: fora do mix o piso continua caindo. Sem isto, "nunca acusa" passaria aqui.
    assert piso_por_direcao('standard', 'gto_critical', 'fold', 'raise') == 'small_mistake'
    assert piso_por_direcao('standard', None, 'fold', 'raise') == 'small_mistake'
    # CONTROLE: o piso so SOBE, nunca rebaixa quem ja era mais grave.
    assert piso_por_direcao('clear_mistake', 'gto_critical', 'fold', 'raise') == 'clear_mistake'
    # CONTROLE: acao nao-agressiva nao tem erro de direcao.
    assert piso_por_direcao('standard', 'gto_critical', 'fold', 'call') == 'standard'
    print("OK  test_mix_LEGITIMO_nao_leva_piso_de_direcao")


def test_unificar_nao_e_SOMAR():
    """O motor nao pode ficar MAIS severo que o reconcile ao passar a chamar a mesma funcao.

    `is_verdict_error_signal` tem tres gatilhos: recomendacao=fold, frequencia ~0, e fora do
    range. O reconcile so alimenta o PRIMEIRO — chama a funcao com dois argumentos. Na primeira
    versao deste conserto eu passei `played_freq` no motor "porque a funcao aceita", e o dry-run
    de producao mostrou 110 bets postflop de `gto_minor_deviation` subindo de `marginal` para
    `small_mistake`. Unificar duas copias e faze-las concordar, nao somar o que cada uma tinha.
    """
    import os
    motor = open(os.path.join(os.path.dirname(__file__), '..',
                              'leaklab', 'decision_engine_v11.py'), encoding='utf-8').read()
    alvo = 'label = piso_por_direcao('
    assert alvo in motor, 'o motor nao chama piso_por_direcao'
    # Regex com parenteses aninhados e onde a primeira versao DESTE teste falhou: a chamada tem
    # dois niveis (`_norm_gto_action(input_data.get(...))`) e o padrao so casava um. Contar
    # parenteses e chato e correto; regex de parenteses balanceados e curta e errada.
    i = motor.index(alvo) + len(alvo)
    nivel, fim = 1, i
    while nivel and fim < len(motor):
        nivel += {'(': 1, ')': -1}.get(motor[fim], 0)
        fim += 1
    chamada = motor[i:fim]
    assert 'played_freq' not in chamada, (
        'o motor passa played_freq e o reconcile nao — volta a ser mais severo que ele: %s'
        % chamada)
    print("OK  test_unificar_nao_e_SOMAR")


def test_a_regra_de_direcao_tem_UM_dono():
    """A varredura dos N+1: quem quiser o piso importa a funcao, nao reescreve a lista.

    A PRIMEIRA versao deste teste varria conjuntos literais com tres sinonimos de agressao e
    acusou SETE modulos — `bet_intent`, `gto_utils`, `preflop_gto_ranges`, `differ` e outros
    tem listas dessas para outros fins. Rede de arrasto nao mede: ou vira ruido ignorado, ou
    obriga uma lista de excecoes que cresce ate nao significar nada. Ficaram tres tells exatos.

    LIMITE CONHECIDO: isto pega a funcao COPIADA e o padrao inline antigo. Nao pega a mesma
    regra reescrita do zero com outro nome e outra forma.
    """
    import os, re
    raiz = os.path.join(os.path.dirname(__file__), '..')

    def fonte(rel):
        return open(os.path.join(raiz, rel), encoding='utf-8').read()

    # 1. Cada funcao da regra e definida UMA vez em todo o backend.
    for fn in ('piso_por_direcao', 'is_verdict_error_signal'):
        onde = []
        for pasta in ('leaklab', 'database', 'api'):
            for dirpath, _, arquivos in os.walk(os.path.join(raiz, pasta)):
                for nome in arquivos:
                    if not nome.endswith('.py'):
                        continue
                    caminho = os.path.join(dirpath, nome)
                    n = len(re.findall(r'^def %s\(' % fn, open(caminho, encoding='utf-8').read(),
                                       re.M))
                    onde += [f'{pasta}/{nome}'] * n
        assert onde == ['leaklab/verdict.py'], f'{fn} definida em {onde}'

    # 2. Os dois consumidores CHAMAM a funcao, nao so a importam.
    for arq in ('leaklab/decision_engine_v11.py', 'database/repositories.py'):
        assert 'piso_por_direcao(' in fonte(arq), f'{arq} nao chama piso_por_direcao'

    # 3. O padrao inline exato que causou o defeito nao voltou: comparar a recomendacao com
    #    'fold' e a acao do hero com uma tupla de agressao, no motor.
    motor = fonte('leaklab/decision_engine_v11.py')
    inline = re.search(r"==\s*'fold'[^\n]*\n?[^\n]*in \(('raise'|'bet')[^\)]*\)", motor)
    assert inline is None, f'piso de direcao remontado inline no motor: {inline.group(0)!r}'
    print("OK  test_a_regra_de_direcao_tem_UM_dono")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
