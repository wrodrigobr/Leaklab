# -*- coding: utf-8 -*-
"""Login com Google: vincula por e-mail, nunca duplica, e a sessão continua sendo a nossa.

── O que estes guardas fixam (30/08) ────────────────────────────────────────────────────────

1. Conta existente com o e-mail → o Google entra NELA (google_sub gravado); a senha antiga
   continua valendo. Duplicata é o dano que não tem conserto barato depois.
2. Mesmo sub duas vezes → o mesmo usuário.
3. Conta nova nasce com username do prefixo (sufixo em colisão), email_verified=1 e
   acquisition_source='google'.
4. E-mail NÃO verificado no Google → recusa (o vínculo por e-mail só é seguro porque o
   Google atesta a posse).
5. Sem GOOGLE_CLIENT_ID → indisponível (a rota devolve 503; o front nem mostra o botão).

O verificador real (`_verificar_token_google`) é substituído: teste que depende do Google
de verdade não roda em CI.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_TESTING', '1')
os.environ.setdefault('GOOGLE_CLIENT_ID', 'teste-client-id')


def _banco():
    from database.schema import init_db
    init_db()


def _com_claims(claims):
    """Substitui o verificador pelo dublê que devolve `claims`."""
    from leaklab import google_auth
    google_auth._verificar_token_google = lambda cred, cid: dict(claims)


def test_conta_nova_nasce_do_prefixo_com_email_verificado():
    _banco()
    from database.repositories import get_user_by_email
    from leaklab.google_auth import entrar_com_google
    m = uuid.uuid4().hex[:8]
    email = f'grinder_{m}@gmail.com'
    _com_claims({'sub': 'sub-' + m, 'email': email, 'email_verified': True})
    r = entrar_com_google('tok')
    assert r['criado'] is True
    assert r['username'].startswith('grinder_'), r['username']
    u = get_user_by_email(email)
    assert int(u.get('email_verified') or 0) == 1, 'conta Google nasceu nao-verificada'
    assert u.get('google_sub') == 'sub-' + m
    assert (u.get('acquisition_source') or '') == 'google'
    print('OK  test_conta_nova_nasce_do_prefixo_com_email_verificado')


def test_email_existente_VINCULA_e_a_senha_continua():
    """A regra 1: nunca duplica; e o caminho antigo (senha) segue vivo."""
    _banco()
    from database.repositories import create_user, verify_password
    from leaklab.google_auth import entrar_com_google
    m = uuid.uuid4().hex[:8]
    email = f'antigo_{m}@gmail.com'
    uid = create_user('antigo_' + m, email, 'senha-forte-123')
    _com_claims({'sub': 'sub2-' + m, 'email': email, 'email_verified': True})
    r = entrar_com_google('tok')
    assert r['id'] == uid and r['vinculado'] is True and r['criado'] is False, r
    assert verify_password(email, 'senha-forte-123'), 'o vinculo Google matou a senha antiga'
    print('OK  test_email_existente_VINCULA_e_a_senha_continua')


def test_mesmo_sub_nao_duplica():
    _banco()
    from leaklab.google_auth import entrar_com_google
    m = uuid.uuid4().hex[:8]
    _com_claims({'sub': 'sub3-' + m, 'email': f'um_{m}@gmail.com', 'email_verified': True})
    a = entrar_com_google('tok')
    b = entrar_com_google('tok')
    assert a['id'] == b['id'] and b['criado'] is False, (a, b)
    print('OK  test_mesmo_sub_nao_duplica')


def test_colisao_de_username_ganha_sufixo():
    _banco()
    from database.repositories import create_user
    from leaklab.google_auth import entrar_com_google
    m = uuid.uuid4().hex[:8]
    create_user('colide' + m, f'dono_{m}@x.com', 'x' * 12)
    _com_claims({'sub': 'sub4-' + m, 'email': f'colide{m}@gmail.com', 'email_verified': True})
    r = entrar_com_google('tok')
    assert r['username'] != 'colide' + m and r['username'].startswith('colide'), r['username']
    print('OK  test_colisao_de_username_ganha_sufixo')


def test_email_nao_verificado_no_google_e_recusado():
    _banco()
    from leaklab.google_auth import entrar_com_google
    m = uuid.uuid4().hex[:8]
    _com_claims({'sub': 'sub5-' + m, 'email': f'nv_{m}@gmail.com', 'email_verified': False})
    try:
        entrar_com_google('tok')
        raise AssertionError('e-mail nao verificado no Google foi aceito')
    except ValueError:
        pass
    print('OK  test_email_nao_verificado_no_google_e_recusado')


def test_sem_client_id_fica_indisponivel():
    _banco()
    from leaklab.google_auth import entrar_com_google
    salvo = os.environ.pop('GOOGLE_CLIENT_ID', None)
    try:
        entrar_com_google('tok')
        raise AssertionError('sem client_id deveria recusar')
    except ValueError as e:
        assert 'indisponivel' in str(e)
    finally:
        if salvo:
            os.environ['GOOGLE_CLIENT_ID'] = salvo
    print('OK  test_sem_client_id_fica_indisponivel')


def test_rota_devolve_o_contrato_do_login():
    """A sessão é a NOSSA: token + user_id + username + role, igual ao /auth/login."""
    _banco()
    import api.app as A
    from leaklab import google_auth
    m = uuid.uuid4().hex[:8]
    google_auth._verificar_token_google = lambda cred, cid: {
        'sub': 'sub6-' + m, 'email': f'rota_{m}@gmail.com', 'email_verified': True}
    c = A.app.test_client()
    r = c.post('/auth/google', json={'credential': 'tok'})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    d = r.get_json()
    for campo in ('token', 'user_id', 'username', 'role'):
        assert campo in d, 'contrato do login sem %r' % campo
    assert d['created'] is True
    # e o token emitido e NOSSO: /auth/me responde com ele
    me = c.get('/auth/me', headers={'Authorization': 'Bearer ' + d['token']})
    assert me.status_code == 200, 'o JWT emitido nao abre a sessao'
    print('OK  test_rota_devolve_o_contrato_do_login')


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
