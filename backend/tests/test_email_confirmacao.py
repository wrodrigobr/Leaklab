"""
test_email_confirmacao.py — o e-mail de confirmação e a saída de quem perdeu a tela do código.

**O caso real, de um usuário em produção:** cadastrou-se pelo celular, saiu sem querer da tela de
confirmação e ficou com o código na mão, sem onde digitá-lo. O e-mail só trazia o código, e nada
na interface dizia que tentar entrar de novo devolveria a tela.

O que estes testes defendem:

1. **O e-mail traz os DOIS caminhos.** Botão que conclui num clique e código para digitar. Um
   deles falha na hora errada: o botão morre em cliente de e-mail que bloqueia link, e o código
   morre quando a pessoa perde a tela.
2. **O link carrega e-mail E código**, senão a tela não tem como se preencher.
3. **Tentar entrar com conta não confirmada devolve `email_unverified` e reenvia.** É a saída que
   já existia; agora é testada, porque virou caminho oficial e não mais acidente.
4. **O código novo invalida o anterior.** Isto é o que faz a pessoa achar que continua quebrado:
   ela digita o código que já tinha e leva "inválido". Fica travado por teste para ninguém
   documentar o contrário.
"""
import os
import sys
import traceback
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None


def _html(code='123456', email='alguem@exemplo.com'):
    from leaklab.email_digest import build_verification_email_html
    return build_verification_email_html('Fulano', code, 15, email=email)


def test_email_tem_botao_e_codigo():
    h = _html()
    assert '123456' in h, 'o código sumiu do corpo'
    assert 'Confirmar meu email' in h, 'o botão de um clique não está no email'
    print('OK  test_email_tem_botao_e_codigo')


def test_link_carrega_email_e_codigo():
    """Sem os dois parâmetros a tela não tem como se preencher, e o botão vira decoração."""
    import re
    h = _html(code='998877', email='alguem+tag@exemplo.com')
    m = re.search(r'href="([^"]*/login\?[^"]*)"', h)
    assert m, 'não achei o link de confirmação no email'
    q = parse_qs(urlparse(m.group(1).replace('&amp;', '&')).query)
    assert q.get('verificar') == ['alguem+tag@exemplo.com'], q
    assert q.get('codigo') == ['998877'], q
    print('OK  test_link_carrega_email_e_codigo')


def test_email_sem_endereco_ainda_entrega_o_codigo():
    """Degradação honesta: sem e-mail não há link, mas o código continua lá."""
    from leaklab.email_digest import build_verification_email_html
    h = build_verification_email_html('Fulano', '555444', 15)
    assert '555444' in h
    assert 'Confirmar meu email' not in h, 'botão sem destino no email'
    print('OK  test_email_sem_endereco_ainda_entrega_o_codigo')


def _app_com_verificacao():
    """Banco TEMPORÁRIO por chamada.

    A primeira versão escrevia no SQLite de desenvolvimento com e-mails fixos: passou uma vez e
    falhou em toda execução seguinte com "Email já cadastrado". Teste que só passa em banco limpo
    é teste que mente na segunda vez — e ainda suja o banco de quem está desenvolvendo.
    """
    import sqlite3, tempfile
    from database import schema, repositories
    caminho = tempfile.mktemp(suffix='_emailtest.db')

    def conectar():
        conn = sqlite3.connect(caminho)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    schema.get_conn = conectar
    repositories.get_conn = conectar
    schema.init_db()

    import api.app as A
    A.app.config['TESTING'] = True
    A._email_verification_enabled = lambda: True
    enviados = []
    A.send_verification_email = lambda email, user, code, ttl: (enviados.append(code) or True)
    return A.app.test_client(), enviados


def test_login_nao_confirmado_devolve_a_tela_e_reenvia():
    """A saída de quem perdeu a tela. Existia e não era testada — nem visível."""
    cli, enviados = _app_com_verificacao()
    em = 'perdeu_a_tela@local.test'
    r = cli.post('/auth/register', json={'username': 'perdeu1', 'email': em,
                                         'password': 'Senha!1234', 'role': 'player'})
    assert r.status_code == 201 and r.get_json().get('pending_verification'), r.get_json()
    assert len(enviados) == 1

    r2 = cli.post('/auth/login', json={'email': em, 'password': 'Senha!1234'})
    assert r2.status_code == 403, r2.status_code
    assert r2.get_json().get('code') == 'email_unverified', r2.get_json()
    assert len(enviados) == 2, 'não reenviou o código ao tentar entrar'
    print('OK  test_login_nao_confirmado_devolve_a_tela_e_reenvia')


def test_codigo_novo_invalida_o_anterior():
    """O detalhe que faz a pessoa achar que continua quebrado."""
    cli, enviados = _app_com_verificacao()
    em = 'codigo_velho@local.test'
    cli.post('/auth/register', json={'username': 'velho1', 'email': em,
                                     'password': 'Senha!1234', 'role': 'player'})
    cli.post('/auth/login', json={'email': em, 'password': 'Senha!1234'})
    antigo, novo = enviados[0], enviados[-1]
    assert antigo != novo, 'o reenvio devolveu o MESMO código'

    r = cli.post('/auth/verify-email', json={'email': em, 'code': antigo})
    assert r.status_code == 400, f'código antigo ainda aceito ({r.status_code})'

    r2 = cli.post('/auth/verify-email', json={'email': em, 'code': novo})
    assert r2.status_code == 200 and r2.get_json().get('token'), r2.get_json()
    print('OK  test_codigo_novo_invalida_o_anterior')


def test_codigo_do_link_conclui_o_cadastro():
    """O caminho de um clique, ponta a ponta: o código que vai no link é o que verifica."""
    import re
    cli, enviados = _app_com_verificacao()
    em = 'um_clique@local.test'
    cli.post('/auth/register', json={'username': 'clique1', 'email': em,
                                     'password': 'Senha!1234', 'role': 'player'})
    h = _html(code=enviados[-1], email=em)
    q = parse_qs(urlparse(re.search(r'href="([^"]*/login\?[^"]*)"', h)
                          .group(1).replace('&amp;', '&')).query)
    r = cli.post('/auth/verify-email', json={'email': q['verificar'][0], 'code': q['codigo'][0]})
    assert r.status_code == 200 and r.get_json().get('token'), r.get_json()
    print('OK  test_codigo_do_link_conclui_o_cadastro')


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f'FAIL {name}: {e}')
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f'Total: {passed+failed} | Passed: {passed} | Failed: {failed}')
