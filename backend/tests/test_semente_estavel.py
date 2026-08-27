# -*- coding: utf-8 -*-
"""A equity de Monte Carlo decide veredito — então a semente não pode mudar entre processos.

── O caso que originou (27/08) ────────────────────────────────────────────────────────────

Duas capturas do torneio 72, sem nada entre elas além de um restart de container. Uma decisão
multiway de flop (mão 260054126928, o check do hero):

    captura 1 ....... `small_mistake`, score 0,19, "Erro" na tela
    captura 2 ....... `standard`,      score 0,0,  "Correto" na tela

0,19 é exatamente o piso da faixa `small_mistake`. A equity mexeu o suficiente para atravessar o
limiar. Na tela isso é o mesmo card dizendo coisas opostas em dois acessos.

A causa: `seed = hash((hs, tuple(board), n_opp))`. Desde o PEP 456 o hash de string é salgado por
processo (`PYTHONHASHSEED` aleatório por padrão). Medido em 4 processos:

    hash()  -> 1543247217 / 547438465 / 809049314 / 251416502
    crc32   -> 1009894888 / 1009894888 / 1009894888 / 1009894888

── Por que passou despercebido ────────────────────────────────────────────────────────────

A lição já estava aprendida no MESMO arquivo: `_equity_vs_range_de_continuacao` usava `crc32`
desde sempre, com o comentário "daria equity diferente a cada reprocesso — e aqui a equity decide
VEREDITO". Duas outras sementes ficaram com `hash()`, uma delas em outro módulo. Regra 5: regra
aplicada em N lugares vira função, com teste que varre os N+1.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# `normpath` não é cosmético: sem ele `_RAIZ` é `backend/tests/..`, e o filtro que pula
# diretórios de teste via `'tests' in base` casa com TODO caminho varrido. A varredura devolvia
# zero por não ter olhado nada — pego quebrando de propósito.
_RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def test_a_semente_e_a_MESMA_em_outro_processo():
    """O teste que a versão antiga não teria como passar. Um processo só nunca vê o defeito:
    dentro dele `hash()` é perfeitamente estável. É preciso um segundo interpretador."""
    from leaklab.multiway_advisor import semente_estavel
    aqui = semente_estavel('AhKd', ('2h', '7c', '2d'), 2)
    codigo = ('import sys; sys.path.insert(0, %r);'
              'from leaklab.multiway_advisor import semente_estavel;'
              "print(semente_estavel('AhKd', ('2h','7c','2d'), 2))" % _RAIZ)
    outros = set()
    for _ in range(3):
        r = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True)
        assert r.returncode == 0, 'subprocesso falhou: %s' % r.stderr[-300:]
        outros.add(int(r.stdout.strip()))
    assert outros == {aqui}, (
        'a semente mudou entre processos (%s aqui, %s fora): o mesmo card volta a dizer "Erro" '
        'num acesso e "Correto" no outro' % (aqui, sorted(outros)))
    print('OK  test_a_semente_e_a_MESMA_em_outro_processo')


def test_entradas_diferentes_dao_sementes_diferentes():
    """CONTROLE. Uma função que devolvesse uma constante passaria no teste acima e destruiria o
    Monte Carlo — toda mão simulando o mesmo runout."""
    from leaklab.multiway_advisor import semente_estavel
    vistas = {semente_estavel('AhKd', ('2h', '7c', '2d'), n) for n in (2, 3, 4)}
    vistas |= {semente_estavel(m, ('2h', '7c', '2d'), 2) for m in ('AhKd', 'AhKs', '7c2d')}
    assert len(vistas) >= 5, 'a semente colapsou entradas diferentes: %d valores' % len(vistas)
    print('OK  test_entradas_diferentes_dao_sementes_diferentes')


def test_nenhuma_semente_de_monte_carlo_usa_hash_NATIVO():
    """Varredura N+1: as três sementes conhecidas foram unificadas; esta pega a QUARTA.

    Ela olha o repositório inteiro, não a lista de arquivos que eu conhecia — que é exatamente
    como as duas sobreviventes passaram meses ao lado da versão certa.

    O CONTROLE de arquivos varridos não é zelo: a 1ª versão deste teste passou verde com um
    `hash()` novo plantado de propósito, porque `_RAIZ` terminava em `tests/..` e o filtro de
    diretório cegava a varredura inteira. Zero de uma sonda que não olhou nada é o pior
    resultado possível numa ferramenta de medição.
    """
    suspeitas = []
    varridos = 0
    padrao = re.compile(r'(seed|rng|Random)\s*[=(].*[^_\w]hash\(')
    pular = ('__pycache__', 'node_modules', '.git', 'tests')
    for base, _dirs, arqs in os.walk(_RAIZ):
        if any(x in base.split(os.sep) for x in pular):
            continue
        for a in arqs:
            if not a.endswith('.py'):
                continue
            caminho = os.path.join(base, a)
            varridos += 1
            with open(caminho, encoding='utf-8', errors='replace') as fh:
                for n, linha in enumerate(fh, 1):
                    if linha.lstrip().startswith('#'):
                        continue
                    if padrao.search(linha):
                        suspeitas.append('%s:%d  %s' % (os.path.relpath(caminho, _RAIZ),
                                                        n, linha.strip()[:90]))
    assert varridos >= 50, (
        'a varredura olhou %d arquivos — ela não está varrendo o repositório, e o zero de '
        'suspeitas abaixo não significa nada' % varridos)
    assert not suspeitas, ('semente de Monte Carlo com `hash()` nativo (salgado por processo): '
                           + ' | '.join(suspeitas))
    print('OK  test_nenhuma_semente_de_monte_carlo_usa_hash_NATIVO (%d arquivos)' % varridos)


def test_as_TRES_sementes_passam_pela_funcao():
    """Fiação nos consumidores conhecidos. A varredura acima pega o `hash()` que voltar; esta
    pega a semente reescrita à mão com outro método estável, divergindo em silêncio."""
    alvos = [('leaklab', 'multiway_advisor.py'), ('leaklab', 'multiway_safety.py')]
    n = 0
    for rel in alvos:
        with open(os.path.join(_RAIZ, *rel), encoding='utf-8') as fh:
            codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
        n += codigo.count('semente_estavel(')
    assert n >= 4, (   # 1 definição + 3 chamadas
        'as sementes deixaram de compartilhar a função: %d ocorrências, esperado 4' % n)
    print('OK  test_as_TRES_sementes_passam_pela_funcao')


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
