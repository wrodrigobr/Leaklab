"""
Padrões do mapa posição × profundidade — o que o plano de estudos não conseguia enxergar.

O prompt recebia leaks como linhas soltas (posição × street × ação ideal) e NENHUM eixo de
profundidade. Um coach olhando o mesmo dado do jogador dizia três coisas que o prompt não tinha
como dizer:

  · "36-60bb é a faixa cara em quase toda posição" — padrão no eixo que não existia;
  · "BB vaza em TODAS as profundidades" — problema estrutural, não spot pontual;
  · "as aberturas já estão resolvidas, ficam de fora" — o prompt só recebia leaks, nunca o que
    já está bom, então não sabia o que NÃO estudar.

A saída não é pedir o padrão ao modelo: é calcular aqui e entregar pronto, o mesmo princípio que
o prompt já aplica ao ranking de EV ("já ranqueado em CÓDIGO"). Por isso estes testes existem —
é código que decide o topo do plano de estudos de alguém.
"""
import sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.llm_explainer import (
    extract_study_patterns, _format_study_patterns,
    _DOMINADO_MAX_BB100, _PADRAO_MIN_N,
)


def _cel(pos, bucket, bb, n):
    return {'position': pos, 'bucket': bucket, 'n': n, 'bb_100': bb}


# Espelha o perfil real medido em produção: inicial impecável, BB sangrando em toda profundidade,
# e a faixa 35-60bb pior que as demais.
_REAL = [
    _cel('UTG',   '10-20bb', 2.5, 50), _cel('UTG',   '20-35bb', 5.5, 100), _cel('UTG',   '35-60bb', 0.6, 52),
    _cel('UTG+1', '10-20bb', 6.2, 25), _cel('UTG+1', '20-35bb', 0.2, 49),  _cel('UTG+1', '35-60bb', 2.5, 36),
    _cel('BB',  '10-20bb', 19.2, 48), _cel('BB',  '20-35bb', 20.2, 73), _cel('BB',  '35-60bb', 17.7, 52),
    _cel('SB',  '10-20bb', 6.4, 41),  _cel('SB',  '20-35bb', 7.5, 97),  _cel('SB',  '35-60bb', 28.8, 59),
    _cel('CO',  '10-20bb', 1.7, 54),  _cel('CO',  '20-35bb', 4.6, 109), _cel('CO',  '35-60bb', 15.9, 67),
]


def test_acha_a_faixa_de_profundidade_cara():
    """A conclusão mais acionável do relatório real, e a que era invisível no prompt."""
    p = extract_study_patterns({'matriz': _REAL})
    assert any('35-60bb' in x and 'profundidade' in x for x in p['padroes']), p['padroes']
    print("OK  test_acha_a_faixa_de_profundidade_cara")


def test_acha_a_posicao_cara_em_todas_as_profundidades():
    """'Cara em TODAS as profundidades' é afirmação mais forte que 'cara na média' — é o que
    separa problema estrutural de spot pontual, e muda o card de p1."""
    p = extract_study_patterns({'matriz': _REAL})
    linha = next((x for x in p['padroes'] if x.startswith('posição mais cara')), None)
    assert linha and 'BB' in linha, p['padroes']
    assert 'TODAS as profundidades' in linha, linha
    print("OK  test_acha_a_posicao_cara_em_todas_as_profundidades")


def test_posicao_cara_so_numa_faixa_nao_vira_afirmacao_forte():
    """SB é caríssima a 35-60bb mas barata nas outras. Chamar isso de 'em todas' seria mentira, e
    mandaria o jogador estudar SB inteiro em vez da faixa."""
    so_sb = [c for c in _REAL if c['position'] == 'SB']
    p = extract_study_patterns({'matriz': so_sb})
    linha = next(x for x in p['padroes'] if x.startswith('posição mais cara'))
    assert 'TODAS as profundidades' not in linha, linha
    print("OK  test_posicao_cara_so_numa_faixa_nao_vira_afirmacao_forte")


def test_lista_o_que_ja_esta_dominado():
    """O prompt só recebia leaks, então não sabia o que NÃO estudar. Um plano que reabre assunto
    encerrado custa a confiança do jogador.

    Nota de calibragem: na leitura verbal deste mesmo dado eu chamei UTG de "impecável", mas a
    média ponderada dele é 3,5 bb/100 — acima do limiar. Quem está de fato dominado é UTG+1 (2,3).
    O teste segue o número, não a impressão."""
    p = extract_study_patterns({'matriz': _REAL})
    assert 'UTG+1' in p['dominados'], p['dominados']
    assert 'UTG' not in p['dominados'], 'UTG está em 3,5 bb/100 — não é assunto encerrado'
    assert 'BB' not in p['dominados'] and 'SB' not in p['dominados'], p['dominados']
    print("OK  test_lista_o_que_ja_esta_dominado")


def test_amostra_pequena_nao_vira_padrao():
    """UTG+1 com 33,4 bb/100 e n=3 apareceu no relatório real. É ruído, e afirmar sobre ele
    mandaria o jogador estudar o que não existe."""
    ruido = [_cel('UTG+1', '0-10bb', 33.4, 3), _cel('UTG+1', '10-20bb', 6.2, 25)]
    p = extract_study_patterns({'matriz': ruido})
    assert not any('0-10bb' in x for x in p['padroes']), p['padroes']
    print("OK  test_amostra_pequena_nao_vira_padrao")


def test_dominado_exige_amostra():
    """Zero bb/100 em 4 decisões não é domínio, é ausência de dado."""
    p = extract_study_patterns({'matriz': [_cel('HJ', '20-35bb', 0.0, 4)]})
    assert p['dominados'] == [], p['dominados']
    print("OK  test_dominado_exige_amostra")


def test_acha_a_acao_recorrente():
    """Quatro folds entre os cinco spots mais caros é diagnóstico de DISPOSIÇÃO, não de range —
    e muda o tipo de treino (call-ou-fold com pot odds, não drill de abertura)."""
    p = extract_study_patterns({'matriz': _REAL, 'acoes_caras': [
        {'action': 'fold', 'n': 7, 'bb': 40.0},
        {'action': 'raise', 'n': 3, 'bb': 9.0},
    ]})
    assert any(x.startswith('ação recorrente') and 'fold' in x for x in p['padroes']), p['padroes']
    print("OK  test_acha_a_acao_recorrente")


def test_acao_sem_dominancia_nao_vira_padrao():
    """Distribuição equilibrada não é padrão. Afirmar 'você folda demais' de 4 em 10 seria
    inventar tendência."""
    p = extract_study_patterns({'matriz': _REAL, 'acoes_caras': [
        {'action': 'fold', 'n': 4, 'bb': 12.0},
        {'action': 'call', 'n': 3, 'bb': 9.0},
        {'action': 'raise', 'n': 3, 'bb': 8.0},
    ]})
    assert not any(x.startswith('ação recorrente') for x in p['padroes']), p['padroes']
    print("OK  test_acao_sem_dominancia_nao_vira_padrao")


def test_sem_dado_nao_inventa_bloco():
    """Sem relatório, o prompt tem que ficar idêntico ao de antes — falha em silêncio, não em
    alucinação."""
    assert _format_study_patterns(None) == ''
    assert _format_study_patterns({'matriz': []}) == ''
    assert extract_study_patterns({})['padroes'] == []
    print("OK  test_sem_dado_nao_inventa_bloco")


def test_texto_marca_celula_vazia_como_sem_amostra():
    """A mentira mais fácil num mapa: célula sem dado lida como acerto. O prompt precisa dizer
    isso em palavras, porque o modelo não vê a diferença entre '—' e 0."""
    txt = _format_study_patterns({'matriz': [
        _cel('BTN', '10-20bb', 5.3, 51), _cel('BB', '20-35bb', 20.2, 73)]})
    assert '—' in txt and 'SEM AMOSTRA' in txt, txt
    assert 'não gere card sobre ela' in txt, txt
    print("OK  test_texto_marca_celula_vazia_como_sem_amostra")


def test_prompt_recebe_o_bloco():
    """Ponta a ponta no texto: mapa, padrões e dominado chegam formatados."""
    txt = _format_study_patterns({'matriz': _REAL, 'acoes_caras': [
        {'action': 'fold', 'n': 7, 'bb': 40.0}]})
    for esperado in ('MAPA POSIÇÃO × PROFUNDIDADE', 'PADRÕES JÁ EXTRAÍDOS', 'JÁ DOMINADO',
                     'BB', 'UTG', '35-60bb'):
        assert esperado in txt, f"falta {esperado!r}"
    print("OK  test_prompt_recebe_o_bloco")


def test_regras_do_prompt_travadas():
    """As três regras que fazem o bloco valer alguma coisa. Sem elas o modelo recebe o mapa e
    continua gerando seis cards do mesmo assunto."""
    import inspect
    from leaklab import llm_explainer
    src = inspect.getsource(llm_explainer.generate_study_plan)
    assert 'PADRÃO ANTES DE SPOT' in src, 'a regra que faz o padrão virar o card p1 sumiu'
    assert 'JÁ DOMINADO' in src, 'a regra de não reabrir assunto encerrado sumiu'
    assert 'SEM AMOSTRA, nunca acerto' in src, 'a regra da célula vazia sumiu'
    print("OK  test_regras_do_prompt_travadas")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
