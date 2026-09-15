# -*- coding: utf-8 -*-
"""POST /player/xp: o valor vem do catalogo, nunca do cliente (auditoria SEG-4, 15/09).

Medido pela rota real, plano free: `amount=4000000, count=500` concedia +2.000.000.000 XP numa
chamada; `event_type` fora do catalogo entrava com 10; `amount` negativo deixava xp_total=-5000;
`amount=1e9 x 500` estourava int4 no Postgres e subia como 500 sem tratamento; e a rota nao
tinha rate limit. Nao alcanca o leaderboard (que nao le xp_total), mas nivel e conquistas
deixavam de significar o que o produto diz.

O que este arquivo defende:
1. O caminho honesto segue igual: evento do catalogo, `count` multiplica, unitario do catalogo.
2. `amount` do corpo e ignorado (positivo, negativo, gigante). O ganho e SEMPRE unitario x count.
3. `event_type` fora do catalogo responde 400 e nao concede nada.
4. `count` que nao e inteiro responde 400.
5. A academia continua passando o valor proprio por dentro (`add_xp` direto): so a ROTA mudou.
6. A rota declara rate limit por usuario (a mesma chave e teto da recepcao de upload).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from test_arquivo_com_varios_torneios import UID, banco_de_teste   # noqa: E402


def _xp(uid):
    from database.schema import get_conn
    from database.repositories import _adapt
    from database.rowutil import value
    c = get_conn()
    try:
        return int(value(c.execute(_adapt("SELECT xp_total FROM users WHERE id=?"),
                                   (uid,)).fetchone(), 'xp_total') or 0)
    finally:
        c.close()


def test_caminho_honesto_segue_igual():
    from database.repositories import _XP_AMOUNTS
    unit = _XP_AMOUNTS['tournament_imported']
    with banco_de_teste() as (cliente, headers):
        r = cliente.post('/player/xp', json={'event_type': 'tournament_imported'}, headers=headers)
        assert r.status_code == 200, (r.status_code, r.get_json())
        assert r.get_json()['xp_gained'] == unit
        r = cliente.post('/player/xp', json={'event_type': 'tournament_imported', 'count': 12},
                         headers=headers)
        assert r.get_json()['xp_gained'] == unit * 12, r.get_json()
        assert _xp(UID) == unit * 13


def test_amount_do_cliente_e_ignorado():
    from database.repositories import _XP_AMOUNTS
    unit = _XP_AMOUNTS['tournament_imported']
    with banco_de_teste() as (cliente, headers):
        for amount, count, esperado in ((4000000, 500, unit * 500),
                                        (1000000000, 500, unit * 500),
                                        (-999999, 1, unit),
                                        (0, 3, unit * 3)):
            antes = _xp(UID)
            r = cliente.post('/player/xp', json={'event_type': 'tournament_imported',
                                                 'amount': amount, 'count': count},
                             headers=headers)
            assert r.status_code == 200, (amount, count, r.status_code, r.get_json())
            ganho = _xp(UID) - antes
            assert ganho == esperado, ('amount=%s count=%s concedeu %d, esperado %d'
                                       % (amount, count, ganho, esperado))
        assert _xp(UID) >= 0


def test_evento_fora_do_catalogo_e_recusado():
    with banco_de_teste() as (cliente, headers):
        antes = _xp(UID)
        for ev in ('nao_existe_no_catalogo', '', None, 'academy_math_correct'):
            r = cliente.post('/player/xp', json={'event_type': ev, 'count': 500}, headers=headers)
            assert r.status_code == 400, (ev, r.status_code, r.get_json())
        r = cliente.post('/player/xp', json={}, headers=headers)
        assert r.status_code == 400
        assert _xp(UID) == antes, 'evento recusado concedeu XP'


def test_count_que_nao_e_inteiro_e_recusado():
    with banco_de_teste() as (cliente, headers):
        antes = _xp(UID)
        r = cliente.post('/player/xp', json={'event_type': 'tournament_imported', 'count': 'abc'},
                         headers=headers)
        assert r.status_code == 400, (r.status_code, r.get_json())
        assert _xp(UID) == antes


def test_a_academia_segue_passando_o_valor_por_dentro():
    """Regra 7: cortar `amount` na funcao quebraria a academia, que chama `add_xp` direto."""
    from database.repositories import add_xp
    with banco_de_teste() as (cliente, headers):
        r = add_xp(UID, 'academy_math_correct', 15)
        assert r.get('xp_gained') == 15, r
        assert _xp(UID) == 15


def test_a_rota_declara_rate_limit_por_usuario():
    """Pergunta ao REGISTRO do limiter, nao ao fonte: e la que o flask-limiter 3.x guarda o
    que os decoradores declararam (`limit_manager._decorated_limits`, chave modulo.func.func)."""
    import api.app as A
    registro = A.limiter.limit_manager._decorated_limits
    chave = 'api.app.player_add_xp.player_add_xp'
    assert chave in registro, ('POST /player/xp sem @limiter.limit; declaradas: %s'
                               % sorted(k for k in registro if 'player' in k))
    grupos = list(registro[chave])
    assert grupos, 'registro vazio para a rota'
    assert any(g.key_function is A._chave_do_upload for g in grupos), (
        'o limite precisa ser por usuario (key_func=_chave_do_upload), nao por IP')
    # E o limite e o mesmo da recepcao de upload: uma concessao por arquivo recebido.
    assert any(g.limit_provider() == '%d per hour' % A.LIMITE_DE_UPLOADS_POR_HORA for g in grupos)


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
