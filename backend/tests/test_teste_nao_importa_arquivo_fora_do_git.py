# -*- coding: utf-8 -*-
"""Nenhum teste importa um helper que o git nao rastreia (12/09).

── O caso ─────────────────────────────────────────────────────────────────────────────────

Criei `tests/_fonte.py` para dois guardas compartilharem a leitura "so codigo". O `.gitignore`
tem `backend/tests/_*.py` (a pasta usa esse prefixo para rascunho local), entao o `git add -A`
nao o pegou e o arquivo **nunca foi commitado**.

O efeito e o pior possivel: na minha maquina o arquivo existe e a suite passa verde; em qualquer
clone limpo os dois guardas morrem com `ImportError` — e guarda que nao roda nao protege nada.
Quem achou foi a homologacao, que clona do git para dentro do container. Mesma familia de
`reference_worktree_faltam_artefatos_de_teste`.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Varre os `import`/`from` de TODO arquivo de teste, fica com os que apontam para um modulo irmao
dentro de `tests/`, e exige que esse modulo esteja RASTREADO pelo git. Nao basta existir no
disco: o disco e o que enganou.

Degrada de proposito onde o git nao responde (tarball, worktree sem .git): sem a lista do git o
teste passa em vez de reprovar por motivo errado — mas imprime que degradou, para nao virar
verde silencioso.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TESTS = os.path.dirname(os.path.abspath(__file__))
_BACK = os.path.abspath(os.path.join(_TESTS, '..'))

#: `from X import ...` / `import X` onde X e um nome simples (modulo irmao, nao pacote).
_IMPORT = re.compile(r'^\s*(?:from\s+([a-zA-Z_][\w]*)\s+import|import\s+([a-zA-Z_][\w]*))\s*',
                     re.MULTILINE)


def _rastreados():
    """Nomes de modulo dentro de `tests/` que o git conhece. `None` se o git nao responder."""
    try:
        r = subprocess.run(['git', 'ls-files', 'tests/*.py'], cwd=_BACK,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        nomes = {os.path.splitext(os.path.basename(l))[0]
                 for l in r.stdout.splitlines() if l.strip()}
        return nomes or None
    except Exception:
        return None


def test_todo_helper_importado_por_teste_esta_no_git():
    rastreados = _rastreados()
    if rastreados is None:
        print('SKIP  o git nao respondeu: varredura degradada de proposito')
        return

    # Modulos irmaos que existem no DISCO: sao os unicos candidatos a import local.
    no_disco = {os.path.splitext(f)[0] for f in os.listdir(_TESTS) if f.endswith('.py')}
    faltando = []
    for f in sorted(os.listdir(_TESTS)):
        if not f.startswith('test_') or not f.endswith('.py'):
            continue
        fonte = open(os.path.join(_TESTS, f), encoding='utf-8').read()
        for m in _IMPORT.finditer(fonte):
            nome = m.group(1) or m.group(2)
            if nome not in no_disco or nome in rastreados:
                continue
            faltando.append('%s importa `%s`, que existe no disco e NAO esta no git' % (f, nome))
    assert not faltando, (
        'teste importando helper fora do git (passa aqui, quebra em clone limpo):\n  '
        + '\n  '.join(faltando))
    print('OK  test_todo_helper_importado_por_teste_esta_no_git (%d modulos no git)'
          % len(rastreados))


def test_o_varredor_ACHA_o_caso_que_escapou():
    """CONTROLE: o caso real de 12/09, forjado. Sem isto o teste acima passa sem provar nada."""
    fonte = ('import os\n'
             'from leitura_de_fonte import so_codigo\n'
             'from _fonte import so_codigo\n'
             'from database.rowutil import first_value\n')
    nomes = [(m.group(1) or m.group(2)) for m in _IMPORT.finditer(fonte)]
    assert 'leitura_de_fonte' in nomes, nomes
    assert '_fonte' in nomes, ('o varredor nao ve o import do helper ignorado', nomes)
    assert 'os' in nomes, nomes
    # `from database.rowutil import ...` NAO entra: o ponto nao casa, e e o que se quer. Import
    # com ponto e pacote do projeto, nao modulo irmao de `tests/`, e pacote nao sofre deste bug.
    # (Eu esperava o contrario ao escrever este controle, e o teste me corrigiu.)
    assert 'database' not in nomes, ('o varredor passou a casar import de PACOTE, e vai reclamar '
                                     'de coisa que nao e helper irmao', nomes)


def test_o_helper_que_os_guardas_usam_esta_no_git():
    """O caso concreto, nomeado: `leitura_de_fonte` e importado por dois guardas."""
    rastreados = _rastreados()
    if rastreados is None:
        print('SKIP  o git nao respondeu')
        return
    assert 'leitura_de_fonte' in rastreados, (
        '`tests/leitura_de_fonte.py` saiu do git: `test_row_access` e '
        '`test_linha_de_banco_por_nome` param de rodar em clone limpo')
    assert '_fonte' not in rastreados, ('o nome antigo voltou, e ele casa com '
                                        '`backend/tests/_*.py` do .gitignore')


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
