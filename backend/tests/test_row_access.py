"""
Ninguém volta a ler coluna por posição direto da linha.

── O bug que isto impede ─────────────────────────────────────────────────────────────────────

No SQLite a linha é tupla e `row[0]` devolve a primeira coluna. No Postgres, com o cursor de
dicionário que a aplicação usa, a linha é `dict` e `row[0]` levanta `KeyError: 0`.

O sintoma é sempre o mesmo e sempre tardio: o script roda perfeito no desenvolvimento, alguém o
executa em produção meses depois, e ele morre com um traceback cru na primeira linha lida. Já
aconteceu com backfill, com auditoria e com diagnóstico nesta base — e os testes rodam em SQLite,
então nenhum deles pegaria.

Havia 23 ocorrências em 9 scripts quando este teste nasceu. Foram todas convertidas para
`first_value`, de `database/rowutil.py`.

── Por que um teste, e não só corrigir ───────────────────────────────────────────────────────

Porque corrigir já foi feito antes, e voltou. A defesa que falhou foi cada script definir o seu
próprio `_v` local: funciona nos nove primeiros e o décimo esquece, porque não há nada que avise.
Este teste é o que avisa, no momento em que o décimo é escrito.
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# `.fetchone()[0]` e `.fetchone()[1]`: o acesso posicional logo após a leitura.
_PADRAO = re.compile(r'\.fetchone\(\)\s*\[\s*\d+\s*\]')

# O alcance é o REPOSITÓRIO, não o disco.
#
# A primeira versão varria o diretório e reprovou num `check_gto_nodes.py` que é gitignored: um
# rascunho local, que não vai para lugar nenhum. Regra que depende do que cada dev deixou na pasta
# é regra que falha diferente em cada máquina, e a primeira reação de quem topa com ela é desligar
# o teste. Perguntar ao git resolve, e degrada para a varredura onde ele não estiver disponível.
#
# Fora do alcance de qualquer forma: rascunhos com prefixo `_` e os próprios testes, que criam as
# linhas em SQLite e sabem o formato delas.
_IGNORADOS = ('.git', '__pycache__', 'node_modules', 'venv', 'tests', 'docs')


def _rastreados_pelo_git():
    import subprocess
    try:
        saida = subprocess.run(['git', 'ls-files', '*.py'], cwd=_BACKEND,
                               capture_output=True, text=True, timeout=30)
        if saida.returncode != 0:
            return None
        return [os.path.join(_BACKEND, l.replace('/', os.sep))
                for l in saida.stdout.splitlines() if l.strip()]
    except Exception:
        return None


def _relevantes():
    do_git = _rastreados_pelo_git()
    if do_git is not None:
        candidatos = do_git
    else:
        candidatos = []
        for raiz, dirs, arquivos in os.walk(_BACKEND):
            dirs[:] = [d for d in dirs if d not in _IGNORADOS]
            candidatos += [os.path.join(raiz, a) for a in arquivos if a.endswith('.py')]

    for caminho in candidatos:
        rel = os.path.relpath(caminho, _BACKEND).replace('\\', '/')
        if any(p in rel.split('/') for p in _IGNORADOS):
            continue
        if os.path.basename(caminho).startswith('_'):
            continue
        if not os.path.exists(caminho):
            continue
        yield caminho


def test_ninguem_le_coluna_por_posicao_no_fetchone():
    violacoes = []
    vistos = 0
    for caminho in _relevantes():
        vistos += 1
        with open(caminho, encoding='utf-8') as f:
            for n, linha in enumerate(f, 1):
                if _PADRAO.search(linha):
                    rel = os.path.relpath(caminho, _BACKEND).replace('\\', '/')
                    violacoes.append(f"{rel}:{n}  {linha.strip()[:88]}")

    assert vistos > 50, f"varredura não encontrou arquivos suficientes ({vistos}) — caminho errado?"
    assert not violacoes, (
        "acesso posicional a coluna quebra em Postgres (a linha e dict, entao KeyError: 0).\n"
        "Use `first_value(...)` de database/rowutil.py, ou `value(row, 'alias')` com alias no SQL:\n  "
        + "\n  ".join(violacoes))
    print(f"OK  test_ninguem_le_coluna_por_posicao_no_fetchone ({vistos} arquivos)")


def test_first_value_funciona_nos_dois_formatos():
    """O contrato que o resto depende: dict (PG) e tupla (SQLite) dão o MESMO resultado."""
    from database.rowutil import first_value, value, values

    assert first_value({'n': 42}) == 42,       'dict do Postgres'
    assert first_value((42,)) == 42,           'tupla do SQLite'
    assert first_value([42, 7]) == 42,         'lista'
    assert first_value(None) is None,          'linha ausente vira None, não estoura'
    assert first_value(None, default=0) == 0,  'default respeitado'
    assert first_value({}) is None,            'dict vazio não estoura'
    assert first_value(()) is None,            'tupla vazia não estoura'

    # nome primeiro, posição como último recurso
    assert value({'total': 9, 'outro': 1}, 'total') == 9
    assert value((9, 1), 'total', 0) == 9,     'sem nome, cai para a posição'
    assert value({'a': 1}, 'inexistente', 0) == 1, 'nome ausente em dict cai para a posição'
    assert value(None, 'x', 0, default=-1) == -1

    assert values({'a': 1, 'b': 2}) == [1, 2]
    assert values((1, 2)) == [1, 2]
    assert values(None) == []
    print("OK  test_first_value_funciona_nos_dois_formatos")


if __name__ == '__main__':
    falhas = 0
    for t in (test_ninguem_le_coluna_por_posicao_no_fetchone,
              test_first_value_funciona_nos_dois_formatos):
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f"FALHOU  {t.__name__}: {e}")
    print(f"\nTotal: 2 | Passed: {2 - falhas} | Failed: {falhas}")
    sys.exit(1 if falhas else 0)
