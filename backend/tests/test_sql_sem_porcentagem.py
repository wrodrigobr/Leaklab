"""
test_sql_sem_porcentagem.py — nenhuma consulta pode ter `%` literal.

**Este arquivo existe porque o mesmo defeito derrubou coisas TRES vezes em 2026-08-02**, sempre em
silencio e sempre de um jeito diferente:

1. `trainer_pool` — `LIKE '%all%'` deixou a selecao por leak DESLIGADA em producao, com a tela
   funcionando normalmente (o `except` do chamador engolia e caia no catalogo estatico).
2. `scripts/limpar_nos_pote_em_fichas` — `LIKE '%gto%'` fez o script imprimir "APLICANDO..." e
   escrever ZERO.
3. `get_drill_spots` — um `3%` dentro de um COMENTARIO SQL derrubou o Ghost Table inteiro.

O terceiro e o mais instrutivo: o psycopg2 **nao sabe que aquilo e comentario**. Ele varre a string
toda procurando placeholder, acha `% `, e levanta `IndexError: list index out of range` — que nem
parece erro de SQL. E a falha so acontece QUANDO ha parametros, entao a mesma consulta funciona ou
nao dependendo de um filtro opcional estar ligado.

E o teste local NAO pega: o dev roda SQLite, que nao interpola `%`.

Por isso o guarda e sobre o TEXTO das consultas, e varre o arquivo inteiro — regra que vale em N
lugares precisa de teste que varra os N+1.
"""
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_RAIZ = os.path.join(os.path.dirname(__file__), '..')

# Arquivos que montam SQL. `%s` (placeholder ja adaptado) e `%%` (escapado) sao legitimos.
_ALVOS = [
    os.path.join('database', 'repositories.py'),
    os.path.join('leaklab', 'trainer_pool.py'),
    os.path.join('leaklab', 'grind_mode.py'),
    os.path.join('leaklab', 'leak_trainer.py'),
    os.path.join('leaklab', 'progression.py'),
    os.path.join('api', 'app.py'),
    os.path.join('scripts', 'limpar_nos_pote_em_fichas.py'),
]

_PALAVRAS_SQL = ('SELECT ', 'INSERT INTO', 'UPDATE ', 'DELETE FROM')


def _blocos_sql(fonte: str):
    """Strings de tres aspas que parecem SQL. É onde as consultas do projeto moram."""
    for m in re.finditer(r'"""(.*?)"""', fonte, re.S):
        txt = m.group(1)
        if any(p in txt.upper() for p in _PALAVRAS_SQL):
            yield m.start(), txt


def _porcentagens_soltas(sql: str):
    """`%` que não é `%s` nem `%%`. Inclui os que estão dentro de comentário `--`, de propósito:
    o driver não distingue comentário de código."""
    fora = []
    i = 0
    while i < len(sql):
        if sql[i] == '%':
            seguinte = sql[i + 1] if i + 1 < len(sql) else ''
            if seguinte == '%':
                i += 2
                continue
            if seguinte == 's':
                i += 2
                continue
            fora.append(sql[max(0, i - 40):i + 20].replace('\n', ' '))
        i += 1
    return fora


def test_nenhuma_consulta_tem_porcentagem_literal():
    problemas = []
    vistos = 0
    for rel in _ALVOS:
        caminho = os.path.join(_RAIZ, rel)
        if not os.path.exists(caminho):
            continue
        with open(caminho, encoding='utf-8') as f:
            fonte = f.read()
        for _pos, sql in _blocos_sql(fonte):
            vistos += 1
            for trecho in _porcentagens_soltas(sql):
                problemas.append(f'{rel}: ...{trecho}...')
    assert vistos >= 20, f'a varredura achou só {vistos} consultas — passaria sem ler nada'
    assert not problemas, (
        'porcentagem literal em SQL (quebra no Postgres QUANDO há parâmetros, com IndexError):\n  '
        + '\n  '.join(problemas[:10]))
    print(f'OK  test_nenhuma_consulta_tem_porcentagem_literal ({vistos} consultas varridas)')


def test_a_varredura_ENXERGA_uma_porcentagem_plantada():
    """Guarda do guarda. Sem isto, um erro no regex faria a varredura passar por tudo em silêncio —
    e "zero problemas" de um detector cego é o pior resultado possível."""
    fake = 'SELECT * FROM t WHERE x LIKE \'%all%\' AND y = ?'
    assert _porcentagens_soltas(fake), 'a varredura não viu um LIKE com porcentagem'
    fake2 = 'SELECT * FROM t -- custa 3% do pool\n WHERE y = ?'
    assert _porcentagens_soltas(fake2), 'a varredura não viu porcentagem dentro de COMENTÁRIO SQL'
    assert not _porcentagens_soltas('SELECT * FROM t WHERE y = %s'), 'acusou placeholder legítimo'
    assert not _porcentagens_soltas("SELECT * FROM t WHERE x LIKE '%%gto%%'"), 'acusou escape legítimo'
    print('OK  test_a_varredura_ENXERGA_uma_porcentagem_plantada')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
