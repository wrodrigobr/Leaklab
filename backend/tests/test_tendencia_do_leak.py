# -*- coding: utf-8 -*-
"""A seta de tendência do leak: uma fonte só, e com porta de amostra.

── O que originou (28/08) ──────────────────────────────────────────────────────────────────

O dono pediu a estatística recente ao lado da histórica: *"pra ver se mesmo com poucas mãos a
tendência diz que as estatísticas estão melhorando, antes de sensibilizarem os dados históricos
que precisam de grandes amostras"*.

Medindo o que já existia antes de construir — quarta suposição minha sobre este produto que morreu
na conferência —, a tendência **já era calculada e já aparecia** no painel de leaks. O que faltava
era o contrário do que eu ia construir: ela afirmava direção sem amostra que a sustentasse.

── Os dois defeitos ────────────────────────────────────────────────────────────────────────

**1. Não havia porta, e nem como pôr.** As consultas traziam só `AVG(score)`: o `COUNT(*)` não era
sequer buscado. Duas decisões recentes contra quarenta antigas viravam seta verde de "melhorando".
Isso contradiz o resto do produto, onde célula sem amostra fica cinza e o card nunca vira zero — e
é pior aqui, porque a seta não mostra ausência, ela AFIRMA uma direção.

**2. Duas cópias da regra**, com os limiares 0,85 e 1,15 repetidos em `get_leak_roi_impact` e em
`get_gto_leak_ranking`. Regra 5 do CLAUDE.md.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def test_amostra_curta_nao_vira_seta():
    """O defeito que originou o arquivo, no seu formato mais direto."""
    from database.repositories import tendencia_do_spot as t, TENDENCIA_MIN_AMOSTRA as M
    assert t(0.10, 2, 0.45, 40) == 'amostra_curta', (
        '2 decisões recentes contra 40 antigas afirmaram "melhorando"')
    assert t(0.10, 40, 0.45, 2) == 'amostra_curta', (
        'o piso tem de valer nos DOIS lados: 40 recentes contra 2 antigas é igualmente frágil')
    assert t(0.10, M, 0.45, M) == 'improving', (
        'exatamente no piso a seta deveria poder falar; senão o piso é outro')
    print('OK  test_amostra_curta_nao_vira_seta (piso %d por lado)' % M)


def test_a_direcao_continua_certa_quando_ha_amostra():
    """CONTRAPROVA: uma porta que barra tudo passaria no teste acima e mataria a funcionalidade."""
    from database.repositories import tendencia_do_spot as t
    assert t(0.10, 12, 0.45, 40) == 'improving'
    assert t(0.60, 12, 0.45, 40) == 'regressing'
    assert t(0.45, 12, 0.45, 40) == 'stagnant'
    assert t(0.10, 12, None, 0) == 'new', 'spot sem lado anterior não é tendência, é novidade'
    assert t(None, 0, 0.45, 40) == 'new'
    print('OK  test_a_direcao_continua_certa_quando_ha_amostra')


def test_os_limiares_moram_num_lugar_SO():
    """A varredura N+1. Ela precisa PROVAR que varreu: uma varredura minha já olhou zero arquivos
    e devolveu 'nenhuma suspeita'."""
    suspeitas, varridos = [], 0
    for base, _dirs, arqs in os.walk(_RAIZ):
        if any(x in base for x in ('.git', '__pycache__', 'node_modules', 'tests')):
            continue
        for a in arqs:
            if not a.endswith('.py'):
                continue
            caminho = os.path.join(base, a)
            varridos += 1
            corpo = io.open(caminho, encoding='utf-8', errors='replace').read()
            # O CORPO da fonte única, para excluir os acertos que são ela mesma. A 1a versão
            # excluía por janela de 400 caracteres em volta do acerto, e a docstring da função
            # empurrou o `def` para fora da janela: a varredura acusou a própria fonte única de
            # ser uma cópia. Janela é heurística; o corpo da função é a condição.
            span = (0, 0)
            if 'def tendencia_do_spot' in corpo:
                ini = corpo.index('def tendencia_do_spot')
                fim = corpo.find(chr(10) + 'def ', ini + 10)
                span = (ini, fim if fim > 0 else len(corpo))
            # A assinatura da regra: o limiar 0.85 ao lado de um rótulo de tendência.
            for m in re.finditer(r"['\"](improving|regressing)['\"]", corpo):
                if span[0] <= m.start() < span[1]:
                    continue            # é a fonte única
                trecho = corpo[max(0, m.start() - 400):m.end() + 400]
                if '0.85' in trecho or '1.15' in trecho:
                    suspeitas.append(os.path.relpath(caminho, _RAIZ))
    assert varridos >= 50, 'a varredura olhou %d arquivos: ela não varreu nada' % varridos
    assert not suspeitas, (
        'limiar de tendência fora de `tendencia_do_spot`: %s' % sorted(set(suspeitas)))
    print('OK  test_os_limiares_moram_num_lugar_SO (%d arquivos varridos)' % varridos)


def test_as_consultas_TRAZEM_a_contagem():
    """Sem `COUNT(*)` no SQL não há porta possível, e foi assim que o defeito viveu.

    Ancora na CONDIÇÃO (o SQL busca a contagem) e não no efeito, porque um `n=0` embutido faria a
    função devolver `amostra_curta` sempre e passaria nos testes de comportamento acima.
    """
    corpo = io.open(os.path.join(_RAIZ, 'database', 'repositories.py'),
                    encoding='utf-8', errors='replace').read()
    # CONTA as consultas em vez de checar presença. A 1ª versão perguntava "existe `COUNT(*) AS n`
    # nesta função?" e passou verde com a mutação que tirou o COUNT de UMA das duas consultas: a
    # outra mantinha o literal no arquivo. Presença não é cobertura.
    faltando = []
    for nome, minimo in (('get_leak_roi_impact', 2), ('get_gto_leak_ranking', 1)):
        i = corpo.index('def %s(' % nome)
        j = corpo.index('\ndef ', i + 10)
        trecho = corpo[i:j]
        if 'recent_map' not in trecho and '_proxy_rows' not in trecho:
            continue
        achou = trecho.count('COUNT(*) AS n')
        if achou < minimo:
            faltando.append('%s (%d de %d consultas)' % (nome, achou, minimo))
    assert not faltando, (
        'as consultas de %s não trazem COUNT(*): a porta de amostra não tem o que ler'
        % ', '.join(faltando))
    print('OK  test_as_consultas_TRAZEM_a_contagem')


def test_a_contagem_VIAJA_para_a_tela():
    """O número que sustenta a seta acompanha a seta.

    Sem isso a tela mostraria "amostra curta" sem dizer curta quanto, e o jogador não teria como
    saber se falta uma mão ou trinta. É a mesma disciplina do resto do produto: quem muda o
    veredito carrega a evidência junto."""
    corpo = io.open(os.path.join(_RAIZ, 'database', 'repositories.py'),
                    encoding='utf-8', errors='replace').read()
    assert corpo.count("r['trend_n']") >= 2, (
        'a contagem não viaja nas DUAS portas que produzem `trend`')
    print('OK  test_a_contagem_VIAJA_para_a_tela')


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
