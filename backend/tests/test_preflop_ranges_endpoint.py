# -*- coding: utf-8 -*-
"""`/preflop-ranges` — o endpoint que a página `/ranges` passou a consumir clique a clique.

── Por que estes guardas existem (28/08) ──────────────────────────────────────────────────

A página nova trocou o padrão de uso do endpoint: era **uma** chamada por sessão de replayer e
virou **uma por clique** numa barra de 14 stacks × 9 posições. A revisão de segurança mediu o
efeito e achou três coisas, todas causadas por esse uso novo:

1. `float(request.args.get('stack_bb', 30.0))` cru devolvia **500** em `stack_bb=abc`.
2. Pior: `NaN` e `Infinity` PASSAVAM. Os dois saturavam no balde de 100bb e a resposta saía
   **200** dizendo `stack_bucket: "100bb"` para o stack pedido, sem nenhum sinal de saturação.
   É o mesmo padrão que `_balde_da_carta` existe para recusar nos outros consumidores.
3. E `"stack_bb": NaN` não é JSON válido (RFC 8259), então o `JSON.parse` do próprio front
   quebrava dentro de um 200.

A correção **recusa** em vez de fazer clamp para a faixa válida. Clamp transformaria a ameaça em
entrega silenciosa da carta errada — o conserto causando o dano que o bug só ameaçava (regra 7).

Sem rate limit e sem cache, 30 requisições seguidas custavam 2,9s de CPU do worker e 1 MB de
egress para um conteúdo 100% determinístico, que não depende do usuário.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


_CACHE = {}


def _cliente():
    """Banco SQLite isolado + usuario de verdade. `require_auth` confere que o usuario EXISTE,
    entao um token assinado sobre um id inventado devolve 401 — a 1a versao deste arquivo caiu
    nisso e seis testes falharam por motivo errado."""
    if 'c' in _CACHE:
        return _CACHE['c']
    import sqlite3
    import tempfile
    import database.schema as schema
    import database.repositories as repositories
    caminho = tempfile.mktemp(suffix='_rangestest.db')

    def gc():
        conn = sqlite3.connect(caminho)
        conn.row_factory = sqlite3.Row
        return conn

    schema.get_conn = gc
    repositories.get_conn = gc
    schema.init_db()
    from api.app import app
    app.config['TESTING'] = True
    c = app.test_client()
    r = c.post('/auth/register',
               json={'username': 'guarda', 'email': 'guarda@ranges.local', 'password': 'pass1234'},
               content_type='application/json')
    tok = (r.get_json() or {}).get('token', '')
    assert tok, 'nao consegui registrar o usuario do teste: %s' % r.get_data(as_text=True)[:200]
    _CACHE['c'], _CACHE['t'] = c, tok
    return c


def _get(c, qs):
    return c.get('/preflop-ranges?%s' % qs,
                 headers={'Authorization': 'Bearer %s' % _CACHE['t']})


def test_exige_autenticacao():
    """CONTROLE de base: se o endpoint respondesse sem token, todo o resto seria irrelevante."""
    r = _cliente().get('/preflop-ranges?position=BTN&stack_bb=20')
    assert r.status_code == 401, 'endpoint respondeu %d sem token' % r.status_code
    print('OK  test_exige_autenticacao')


def test_stack_nao_numerico_e_400_e_nao_500():
    """Um 500 é ruído de alarme onde cabia uma recusa. Não vaza nada (o handler devolve só a
    mensagem genérica), mas polui Sentry e esconde erro de verdade."""
    c = _cliente()
    for ruim in ('abc', '', '0x20', 'null'):
        r = _get(c, 'position=BTN&stack_bb=%s' % ruim)
        assert r.status_code == 400, (
            'stack_bb=%r devolveu %d, esperado 400' % (ruim, r.status_code))
    print('OK  test_stack_nao_numerico_e_400_e_nao_500')


def test_NaN_e_infinito_sao_RECUSADOS_e_nao_saturados():
    """O achado que mais importa. Antes, os dois viravam 200 com a carta de 100bb — estratégia de
    mesa funda entregue como resposta ao stack que o cliente pediu."""
    c = _cliente()
    for ruim in ('NaN', 'Infinity', '-Infinity', '-999', '0'):
        r = _get(c, 'position=BTN&stack_bb=%s' % ruim)
        assert r.status_code == 400, (
            'stack_bb=%r devolveu %d — se for 200, confira se veio a carta de 100bb saturada'
            % (ruim, r.status_code))
    print('OK  test_NaN_e_infinito_sao_RECUSADOS_e_nao_saturados')


def test_o_corpo_e_sempre_JSON_VALIDO():
    """`"stack_bb": NaN` passa no `json.dumps` do Python e é rejeitado por parser estrito — o
    front recebia 200 e estourava no `JSON.parse`. Este guarda usa `parse_constant` para falhar
    exatamente onde um parser de verdade falharia."""
    c = _cliente()
    def _estrito(txt):
        return json.loads(txt, parse_constant=lambda x: (_ for _ in ()).throw(
            ValueError('token nao-JSON: %s' % x)))
    r = _get(c, 'position=BTN&stack_bb=20')
    assert r.status_code == 200
    _estrito(r.get_data(as_text=True))          # levanta se houver NaN/Infinity no corpo
    print('OK  test_o_corpo_e_sempre_JSON_VALIDO')


def test_stack_valido_continua_respondendo():
    """CONTRAPROVA das recusas acima: uma validação que rejeitasse tudo passaria nos três testes
    anteriores e mataria a página."""
    c = _cliente()
    for bom in ('3', '20', '100', '20.5'):
        r = _get(c, 'position=CO&stack_bb=%s' % bom)
        assert r.status_code == 200, 'stack_bb=%s foi recusado' % bom
        d = r.get_json()
        assert d['position'] == 'CO'
        assert d['stack_bucket'], 'resposta sem balde'
    print('OK  test_stack_valido_continua_respondendo')


def test_a_resposta_declara_que_pode_ser_CACHEADA():
    """Nada na resposta depende do usuário: a carta é um JSON estático e o corpo é função pura de
    (posição, balde). Sem o header, cada clique da barra de stacks paga CPU e banda de novo."""
    r = _get(_cliente(), 'position=BTN&stack_bb=20')
    cc = r.headers.get('Cache-Control', '')
    assert 'max-age' in cc, 'resposta sem Cache-Control: %r' % cc
    print('OK  test_a_resposta_declara_que_pode_ser_CACHEADA (%s)' % cc)


def test_position_hostil_nao_quebra_nem_vaza():
    """`position` vira chave de dict, não toca SQL nem filesystem. O guarda existe para que isso
    continue verdade se alguém trocar o lookup por uma query ou um caminho de arquivo."""
    c = _cliente()
    for ruim in ('../../../../etc/passwd', "BTN' OR 1=1--", '__proto__', ''):
        r = _get(c, 'position=%s&stack_bb=20' % ruim)
        assert r.status_code == 200, 'position=%r devolveu %d' % (ruim, r.status_code)
        assert r.get_json().get('rfi') is None, (
            'position=%r retornou uma carta — o lookup deixou de ser por chave exata' % ruim)
    print('OK  test_position_hostil_nao_quebra_nem_vaza')


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
