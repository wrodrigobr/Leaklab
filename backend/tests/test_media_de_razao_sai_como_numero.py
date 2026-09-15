# -*- coding: utf-8 -*-
"""Razao calculada em SQL sai como NUMERO nas duas gramaticas, nunca como string.

-- O defeito (auditoria TEL-5, 15/09) ------------------------------------------------------

`AVG(CASE WHEN d.label='standard' THEN 1.0 ELSE 0.0 END) AS standard_rate` vira NUMERIC no
Postgres, e o driver entrega `Decimal`. O `dict(r)` de `get_breakdown` e de
`get_pressure_profile` nao passava pelo `_jsonable` (a funcao da casa que converte Decimal para
float), e o `jsonify` serializava o campo como STRING: medido no banco de auditoria,
`"standard_rate": "1.00000000000000000000"` no Postgres e `1.0` no SQLite.

`IcmBreakdown` e `PositionChart` sobrevivem porque `string * 100` coage em JS. Um `.toFixed`
direto quebraria SO em producao, que e o pior lugar para descobrir.

-- O que este arquivo defende --------------------------------------------------------------

1. `standard_rate` e `avg_score` das duas rotas sao float, e o dict inteiro serializa com
   `json.dumps` sem `default=str` (o que falha em Decimal e em datetime).
2. Varredura (regra 5): TODA funcao de `repositories.py` cujo SELECT calcula uma razao com
   `AVG(CASE WHEN ...)` passa o resultado por `_jsonable`. Sao 4 hoje; eram 4 com 1 coberta.
   A varredura PROVA que acha: recebe o fonte de antes do conserto e acusa.
"""
import ast
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RAIZ = os.path.join(os.path.dirname(__file__), '..')
UID = 9702


def _ex(sql, params=()):
    from database.schema import get_conn
    from database.repositories import _adapt
    c = get_conn()
    try:
        cur = c.execute(_adapt(sql), params)
        try:
            linhas = [dict(r) for r in cur.fetchall()]
        except Exception:
            linhas = []
        c.commit()
        return linhas
    finally:
        c.close()


def _limpar():
    for t in _ex("SELECT id FROM tournaments WHERE user_id=?", (UID,)):
        _ex("DELETE FROM decisions WHERE tournament_id=?", (t['id'],))
    _ex("DELETE FROM tournaments WHERE user_id=?", (UID,))
    _ex("DELETE FROM users WHERE id=?", (UID,))


def _semear():
    _limpar()
    _ex("INSERT INTO users (id, username, email, password_hash, plan) VALUES (?,?,?,?,?)",
        (UID, 'tel5g', 'tel5g@teste.local', 'h', 'pro'))
    _ex("INSERT INTO tournaments (user_id, tournament_id, hero, hands_count, decisions_count) "
        "VALUES (?,?,?,?,?)", (UID, '999905100', 'Hero', 1, 0))
    tid = _ex("SELECT id FROM tournaments WHERE user_id=? ORDER BY id DESC", (UID,))[0]['id']
    for i in range(6):
        _ex("INSERT INTO decisions (tournament_id, hand_id, street, position, icm_pressure, "
            "action_taken, best_action, label, score, n_active_opponents) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tid, 'H%d' % i, 'preflop', 'BTN', 'high', 'fold', 'fold', 'standard', 0.9, 1))


def test_as_duas_rotas_devolvem_razao_como_float():
    from database.schema import init_db
    from database.repositories import get_breakdown, get_pressure_profile
    init_db()
    _semear()
    try:
        pos = get_breakdown(UID, days=3650, last_n=0)['by_position'].get('BTN') or {}
        pres = get_pressure_profile(UID, days=3650, last_n=0)['by_pressure'].get('high') or {}
        assert pos.get('n') == 6 and pres.get('n') == 6, (pos, pres)   # o teste mede algo
        for nome, d in (('by_position[BTN]', pos), ('by_pressure[high]', pres)):
            for campo in ('standard_rate', 'avg_score'):
                v = d.get(campo)
                assert isinstance(v, float), '%s %s veio %s (%r)' % (nome, campo, type(v).__name__, v)
            # sem `default=str`: Decimal e datetime estouram aqui, que e o ponto.
            texto = json.dumps(d)
            assert '"1.0' not in texto and '"0.9' not in texto, texto
        assert pos['standard_rate'] == 1.0 and pres['standard_rate'] == 1.0, (pos, pres)
    finally:
        _limpar()


# -- Varredura das razoes em SQL (regra 5) ---------------------------------------------------

MARCA_DE_RAZAO = 'AVG(CASE WHEN'


def razoes_sem_jsonable(fonte):
    """Funcoes cujo SELECT calcula razao com AVG(CASE WHEN ...) e nas quais alguma linha vira
    `dict(...)` FORA de um `_jsonable`.

    A checagem e por `dict(...)`, e nao "a funcao cita `_jsonable` em algum lugar": `get_breakdown`
    monta quatro dicionarios e so um deles estava coberto, o que um teste no nivel da funcao
    deixaria passar."""
    arvore = ast.parse(fonte)
    faltantes, achadas = [], []
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corpo = ast.dump(no)
        if MARCA_DE_RAZAO not in corpo:
            continue
        achadas.append(no.name)
        cobertos = [ast.dump(a) for c in ast.walk(no)
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id == '_jsonable' for a in c.args]
        for c in ast.walk(no):
            if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id == 'dict'):
                continue
            alvo = ast.dump(c)
            if not any(alvo in cob for cob in cobertos):
                faltantes.append('%s:%d' % (no.name, c.lineno))
    return sorted(achadas), sorted(faltantes)


def test_varredura_toda_razao_em_sql_passa_pelo_jsonable():
    with open(os.path.join(RAIZ, 'database', 'repositories.py'), encoding='utf-8') as f:
        achadas, faltantes = razoes_sem_jsonable(f.read())
    assert achadas, 'a varredura nao achou nenhuma razao em SQL: o marcador mudou?'
    assert not faltantes, 'razao em SQL sem `_jsonable` (vira string no Postgres): %s' % faltantes


def test_varredura_acha_o_caso_forjado():
    """Regra 1: o medidor tem de se mexer. O trecho e o `get_breakdown` de antes do conserto."""
    antigo = (
        "def get_breakdown(user_id):\n"
        "    rows = conn.execute(f'''\n"
        "        SELECT d.position, AVG(CASE WHEN d.label='standard' THEN 1.0 ELSE 0.0 END) AS r\n"
        "    ''').fetchall()\n"
        "    return {'by_position': {x['position']: dict(x) for x in rows}}\n"
    )
    assert razoes_sem_jsonable(antigo) == (['get_breakdown'], ['get_breakdown:5'])
    consertado = antigo.replace("dict(x) for x in rows", "_jsonable(dict(x)) for x in rows")
    assert razoes_sem_jsonable(consertado) == (['get_breakdown'], [])
    sem_razao = "def outra():\n    return dict(r)\n"
    assert razoes_sem_jsonable(sem_razao) == ([], [])


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
