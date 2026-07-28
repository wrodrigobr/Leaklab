"""
Duas convenções opostas de flag na mesma base — e usar a errada quebra SÓ em produção.

Descoberto ao escrever uma consulta de diagnóstico que morreu no Postgres com
`argument of CASE/WHEN must be type boolean, not type integer`. O SQLite aceita as duas formas,
então o teste local passa, o dev passa, e o erro aparece quando um usuário abre a tela.

    tipo no Postgres          colunas                                   idioma correto
    BOOLEAN (SQLite INTEGER)  is_3bet, is_aggregate, leaderboard_opt_in CASE WHEN col THEN 1 ELSE 0 END
    INTEGER nos dois          gto_depth_capped, email_opt_in,           col = 1
                              email_verified, is_public

Trocar os idiomas dá erro em tempo de execução no PG, nos DOIS sentidos:
  · `CASE WHEN gto_depth_capped THEN` → integer onde se espera boolean;
  · `is_3bet = 1`                     → boolean onde se espera integer.

Este teste lê a classificação **do próprio schema.py** — não de uma lista escrita à mão que
envelheceria em silêncio — e varre o SQL do código atrás dos dois erros.
"""
import sys, os, re, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_RAIZ = os.path.join(os.path.dirname(__file__), '..')
_ALVOS = ('database', 'api', 'leaklab', 'scripts')

# Declarações no schema: nome + tipo. Uma coluna declarada BOOLEAN em ALGUM lugar é booleana no
# Postgres (o bloco SQLite a declara INTEGER, e isso é esperado — SQLite não tem BOOL).
#
# DOIS padrões, porque metade das colunas-flag desta base não nasce em `CREATE TABLE`: elas
# chegam por `ALTER TABLE ... ADD COLUMN` nos blocos de migração. Uma primeira versão deste teste
# só olhava o CREATE e classificava `gto_depth_capped` como inexistente — passaria verde sem
# proteger justamente a coluna que originou o incidente.
_DECL_CREATE = re.compile(r'^\s*["\']?(\w+)["\']?\s+(BOOLEAN|INTEGER)\b', re.I | re.M)
_DECL_ALTER = re.compile(
    r'ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+(BOOLEAN|INTEGER)\b', re.I)
_FLAG = re.compile(r'(^|_)(is|has)_|_(capped|opt_in|verified|public|enabled|active)$')


def _classificar():
    src = open(os.path.join(_RAIZ, 'database', 'schema.py'), encoding='utf-8').read()
    tipos = {}
    for padrao in (_DECL_CREATE, _DECL_ALTER):
        for m in padrao.finditer(src):
            nome, tipo = m.group(1), m.group(2).upper()
            if not _FLAG.search(nome):
                continue
            tipos.setdefault(nome, set()).add(tipo)
    booleanas = {n for n, t in tipos.items() if 'BOOLEAN' in t}
    inteiras = {n for n, t in tipos.items() if 'BOOLEAN' not in t}
    return booleanas, inteiras


def _arquivos():
    for pasta in _ALVOS:
        base = os.path.join(_RAIZ, pasta)
        for raiz, _, nomes in os.walk(base):
            if '__pycache__' in raiz:
                continue
            for n in nomes:
                if n.endswith('.py'):
                    yield os.path.join(raiz, n)


_SQL = re.compile(r'\b(SELECT|UPDATE|INSERT|DELETE|WHERE|CASE WHEN|GROUP BY)\b', re.I)


def _violacoes(padrao, so_em_sql=True):
    """Varre o SQL do código. Docstrings ficam de fora com rastreio de estado — a primeira versão
    só pulava linhas que COMEÇAM com aspas triplas e acusou uma frase em português no meio de uma
    docstring ("where facing_bet > 0 AND is_3bet = 0"), que não é SQL nenhum."""
    achados = []
    for caminho in _arquivos():
        dentro_doc = False
        for i, linha in enumerate(open(caminho, encoding='utf-8').read().splitlines(), 1):
            crua = linha.strip()
            # abre/fecha docstring (par de delimitadores na mesma linha não muda o estado)
            for delim in ('"""', "'''"):
                if crua.count(delim) % 2:
                    dentro_doc = not dentro_doc
                    break
            if dentro_doc or crua.startswith('#'):
                continue
            if so_em_sql and not _SQL.search(linha):
                continue
            if padrao.search(linha):
                achados.append(f"{os.path.relpath(caminho, _RAIZ)}:{i}  {crua[:110]}")
    return achados


def test_schema_declara_as_duas_familias():
    """Se a classificação vier vazia, o teste abaixo passa sem medir nada."""
    booleanas, inteiras = _classificar()
    assert 'is_3bet' in booleanas, booleanas
    assert 'gto_depth_capped' in inteiras, inteiras
    assert len(booleanas) >= 2 and len(inteiras) >= 3
    print(f"OK  test_schema_declara_as_duas_familias "
          f"({len(booleanas)} booleanas, {len(inteiras)} inteiras)")


def test_coluna_inteira_nao_e_usada_como_booleana():
    """`CASE WHEN gto_depth_capped THEN` → no Postgres: 'argument of CASE/WHEN must be type
    boolean, not type integer'. Foi exatamente assim que isto foi descoberto."""
    _, inteiras = _classificar()
    alt = '|'.join(sorted(inteiras))
    padrao = re.compile(rf'\b(?:CASE\s+WHEN|AND|OR|WHERE)\s+(?:\w+\.)?({alt})\s+(?:THEN|AND|OR)\b', re.I)
    v = _violacoes(padrao)
    assert not v, ("coluna INTEIRA usada como booleana (quebra no Postgres, passa no SQLite):\n  "
                   + "\n  ".join(v) + "\n  → compare explicitamente: `col = 1`")
    print("OK  test_coluna_inteira_nao_e_usada_como_booleana")


def test_coluna_booleana_nao_e_comparada_a_numero():
    """`is_3bet = 1` → no Postgres: 'operator does not exist: boolean = integer'. O idioma
    portável é `CASE WHEN col THEN 1 ELSE 0 END`, que o código já usa em vários lugares."""
    booleanas, _ = _classificar()
    alt = '|'.join(sorted(booleanas))
    padrao = re.compile(rf'\b(?:\w+\.)?({alt})\s*(?:=|<>|!=)\s*[01]\b')
    v = _violacoes(padrao)
    assert not v, ("coluna BOOLEANA comparada a número (quebra no Postgres):\n  "
                   + "\n  ".join(v) + "\n  → use `CASE WHEN col THEN 1 ELSE 0 END`")
    print("OK  test_coluna_booleana_nao_e_comparada_a_numero")


def test_coalesce_em_booleana_nao_usa_zero():
    """`COALESCE(is_3bet, 0)` também estoura no PG — o default de coluna booleana é FALSE."""
    booleanas, _ = _classificar()
    alt = '|'.join(sorted(booleanas))
    padrao = re.compile(rf'COALESCE\s*\(\s*(?:\w+\.)?({alt})\s*,\s*[01]\s*\)', re.I)
    v = _violacoes(padrao)
    assert not v, ("COALESCE numérico em coluna booleana (quebra no Postgres):\n  "
                   + "\n  ".join(v) + "\n  → `COALESCE(col, FALSE)` ou `CASE WHEN col THEN 1 ELSE 0 END`")
    print("OK  test_coalesce_em_booleana_nao_usa_zero")


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
