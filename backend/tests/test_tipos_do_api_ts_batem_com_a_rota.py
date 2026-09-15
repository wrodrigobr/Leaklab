# -*- coding: utf-8 -*-
"""O que a rota MANDA esta declarado em `frontend/src/lib/api.ts`, e o que o tipo PROMETE chega.

-- O defeito (auditoria TEL-5, 15/09) ------------------------------------------------------

`TEL_tipos.py` comparou 68 pares (interface, objeto real) e achou 1 promessa quebrada
(`ConfidenceDrift.baseline_score`, obrigatorio, nunca enviado: quem mostra baseline le o de
`PressureProfile`, outra rota) e 55 campos que o backend manda e o tipo nao declara, 36 deles em
`Tournament` e `TournamentDecision`. Nada quebrava a tela, porque ninguem lia. E onde a proxima
tela erraria sem o compilador avisar: `ev_loss_bb`, a severidade que a casa usa, estava sem tipo
ao lado de `score`.

-- O que este arquivo defende --------------------------------------------------------------

O contrato das DUAS rotas de torneio, medido na rota de verdade (test_client), contra as
interfaces lidas do `api.ts`:

1. Todo campo que a rota manda esta declarado na interface.
2. Todo campo obrigatorio da interface chega na resposta.
3. `ConfidenceDrift` nao volta a prometer `baseline_score`.

O parser PROVA que le: um fonte forjado com campo faltando e outro com campo sobrando tem de
ser acusados.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

RAIZ = os.path.join(os.path.dirname(__file__), '..')
API_TS = os.path.abspath(os.path.join(RAIZ, '..', 'frontend', 'src', 'lib', 'api.ts'))
UID = 9703


# -- Leitor de `export interface` do api.ts ---------------------------------------------------

def _sem_comentario(s):
    return re.sub(r'/\*.*?\*/|(?<![:\w])//[^\n]*', '', s, flags=re.S)


def interfaces(fonte):
    """{nome: {campo: opcional_bool}} das `export interface` de nivel de cima."""
    out = {}
    fonte = _sem_comentario(fonte)
    for m in re.finditer(r'export interface (\w+)\s*(?:extends[^{]+)?\{', fonte):
        nome = m.group(1)
        i, prof = m.end(), 1
        while i < len(fonte) and prof:
            prof += {'{': 1, '}': -1}.get(fonte[i], 0)
            i += 1
        corpo = fonte[m.end():i - 1]
        nivel, atual, partes = 0, '', []
        for c in corpo:
            if c in '{([<':
                nivel += 1
            elif c in '})]>':
                nivel -= 1
            if c in ';\n' and nivel == 0:
                partes.append(atual)
                atual = ''
            else:
                atual += c
        partes.append(atual)
        campos = {}
        for p in partes:
            mm = re.match(r'(?:readonly\s+)?"?([\w$]+)"?\s*(\?)?\s*:\s*(.+)$', p.strip(), re.S)
            if mm:
                # `| null` sozinho nao torna opcional; `?` sim.
                campos[mm.group(1)] = bool(mm.group(2))
        out[nome] = campos
    return out


def divergencias(campos_da_interface, objeto):
    """(nao_declarados, prometidos_e_ausentes) entre a interface e um objeto real da rota."""
    nao_declarados = sorted(k for k in objeto if k not in campos_da_interface)
    ausentes = sorted(k for k, opcional in campos_da_interface.items()
                      if not opcional and k not in objeto)
    return nao_declarados, ausentes


# -- A rota de verdade ------------------------------------------------------------------------

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
        (UID, 'tel5t', 'tel5t@teste.local', 'h', 'pro'))
    _ex("INSERT INTO tournaments (user_id, tournament_id, hero, raw_text, hands_count, "
        "decisions_count) VALUES (?,?,?,?,?,?)",
        (UID, '999905200', 'Hero', 'PokerStars Hand #1', 1, 1))
    tid = _ex("SELECT id FROM tournaments WHERE user_id=? ORDER BY id DESC", (UID,))[0]['id']
    _ex("INSERT INTO decisions (tournament_id, hand_id, street, position, action_taken, "
        "best_action, label, score, hero_cards, board, n_active_opponents) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (tid, '100000000001', 'preflop', 'BTN', 'raise', 'raise', 'standard', 0.9,
         'AhAd', '[]', 1))
    return tid


def _resposta_do_torneio():
    from database.schema import init_db
    from database.auth import generate_token
    import api.app as A
    init_db()
    _semear()
    A.app.config['TESTING'] = True
    c = A.app.test_client()
    h = {'Authorization': 'Bearer ' + generate_token(UID, 'player')}
    r = c.get('/history/tournament/999905200', headers=h)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return r.get_json()


def test_tournament_e_tournament_decision_batem_com_a_rota():
    with open(API_TS, encoding='utf-8') as f:
        ifaces = interfaces(f.read())
    try:
        corpo = _resposta_do_torneio()
    finally:
        _limpar()
    assert corpo.get('decisions'), 'a rota nao devolveu decisao: o teste nao mede nada'
    for nome, objeto in (('Tournament', corpo['tournament']),
                         ('TournamentDecision', corpo['decisions'][0])):
        campos = ifaces.get(nome)
        assert campos, 'interface %s sumiu do api.ts' % nome
        nao_declarados, ausentes = divergencias(campos, objeto)
        assert not nao_declarados, '%s: a rota manda e o tipo nao declara: %s' % (
            nome, nao_declarados)
        assert not ausentes, '%s: o tipo promete e a rota nao manda: %s' % (nome, ausentes)


def test_confidence_drift_nao_promete_baseline_score():
    """Quem mostra baseline le o de `PressureProfile`, que e outra rota e outro numero."""
    with open(API_TS, encoding='utf-8') as f:
        ifaces = interfaces(f.read())
    assert 'baseline_score' not in ifaces['ConfidenceDrift'], \
        'ConfidenceDrift voltou a prometer baseline_score, que /player/confidence-drift nao manda'
    assert 'baseline_score' in ifaces['PressureProfile'], \
        'PressureProfile deixou de declarar baseline_score (e la que ele existe)'


def test_o_leitor_de_interface_prova_que_le():
    """Regra 1: o medidor tem de se mexer nos dois sentidos."""
    fonte = (
        'export interface Alvo {\n'
        '  id: number;\n'
        '  nome?: string | null;\n'
        '  // um comentario com dois-pontos: nao e campo\n'
        '  obrigatorio: string;\n'
        '}\n'
    )
    campos = interfaces(fonte)['Alvo']
    assert campos == {'id': False, 'nome': True, 'obrigatorio': False}, campos
    assert divergencias(campos, {'id': 1, 'obrigatorio': 'x'}) == ([], [])
    assert divergencias(campos, {'id': 1, 'obrigatorio': 'x', 'extra': 2}) == (['extra'], [])
    assert divergencias(campos, {'id': 1}) == ([], ['obrigatorio'])
    # o objeto real serializa; se nao serializar, o proprio jsonify da 500
    json.dumps({'id': 1, 'obrigatorio': 'x'})


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
