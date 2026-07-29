"""
`is_production()` tem que reconhecer o ambiente REAL, não só o que já foi usado um dia.

── O bug que isto impede (achado pela revisão de segurança de 2026-07-28) ────────────────────

O fail-safe do JWT recusa subir sem `LEAKLAB_SECRET` forte — mas só "em produção", e a condição
era `RENDER or LEAKLAB_PROD`. **Produção não é Render.** O runbook escreve `ENVIRONMENT=production`
e `DATABASE_URL` no `.env`, e nenhum arquivo do repositório escreve `RENDER` ou `LEAKLAB_PROD`.

Ou seja, o fail-safe existia e estava desarmado. Faltando o secret, o app subia com a chave
literal `dev-only-insecure-secret-...`, que está num repositório público: qualquer pessoa
assinaria um token de admin. O webhook do Stripe, no mesmo código, já testava a condição ampla —
o que mostra que era descuido, não decisão.

O teste trava os sinais que a produção REALMENTE usa. Se alguém adicionar um sinal novo (outro
provedor, outra var), acrescente aqui junto.
"""
import os, sys, importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_SINAIS = ['RENDER', 'LEAKLAB_PROD', 'ENVIRONMENT', 'DATABASE_URL']


_SEGREDO_OK = 'x' * 48   # ≥32 chars: deixa o módulo carregar para testar só o predicado


def _com_ambiente(_segredo=_SEGREDO_OK, **vars):
    """Recarrega o módulo com um ambiente limpo mais as vars dadas.

    O secret vai por padrão porque senão o próprio fail-safe barra o import e não dá para
    testar o predicado isoladamente — foi o que aconteceu na primeira versão deste arquivo, e
    a falha em si já era a prova de que o conserto pegou.
    """
    salvo = {k: os.environ.pop(k, None) for k in _SINAIS + ['LEAKLAB_SECRET']}
    try:
        if _segredo is not None:
            os.environ['LEAKLAB_SECRET'] = _segredo
        for k, v in vars.items():
            os.environ[k] = v
        import database.auth as auth
        importlib.reload(auth)
        return auth.is_production()
    finally:
        for k in list(vars) + ['LEAKLAB_SECRET']:
            os.environ.pop(k, None)
        for k, v in salvo.items():
            if v is not None:
                os.environ[k] = v


def test_reconhece_o_ambiente_real_de_producao():
    """Os dois sinais que o deploy de verdade escreve. Eram exatamente os que faltavam."""
    assert _com_ambiente(ENVIRONMENT='production') is True, \
        'ENVIRONMENT=production é o que o runbook escreve no .env'
    assert _com_ambiente(DATABASE_URL='postgres://u:p@h/db') is True, \
        'DATABASE_URL presente significa Postgres, que só existe em produção'
    print('OK  test_reconhece_o_ambiente_real_de_producao')


def test_mantem_os_sinais_legados():
    assert _com_ambiente(RENDER='1') is True
    assert _com_ambiente(LEAKLAB_PROD='1') is True
    print('OK  test_mantem_os_sinais_legados')


def test_dev_limpo_nao_e_producao():
    """Sem nenhum sinal, é desenvolvimento — senão o dev não sobe sem secret."""
    assert _com_ambiente() is False
    assert _com_ambiente(ENVIRONMENT='development') is False
    print('OK  test_dev_limpo_nao_e_producao')


def test_o_failsafe_do_jwt_DISPARA_em_producao():
    """A propriedade de segurança de verdade, e a que estava desarmada.

    Sem secret, em produção, o módulo tem que se RECUSAR a carregar. Antes do conserto ele subia
    com a chave literal `dev-only-insecure-secret-...`, que está num repositório público: qualquer
    pessoa assinaria `{"user_id": 1, "role": "admin"}` e entraria como admin.

    Testa os dois sinais reais separadamente, porque foram os dois que faltavam.
    """
    for sinal, valor in (('ENVIRONMENT', 'production'), ('DATABASE_URL', 'postgres://u:p@h/db')):
        try:
            _com_ambiente(_segredo=None, **{sinal: valor})
        except RuntimeError as e:
            assert 'LEAKLAB_SECRET' in str(e), f'erro inesperado com {sinal}: {e}'
        else:
            raise AssertionError(
                f'FALHA DE SEGURANÇA: com {sinal}={valor} e sem LEAKLAB_SECRET, o módulo carregou. '
                'O app subiria com a chave insegura versionada no repositório público.')

    # Secret CURTO também tem que barrar: 'segredo fraco' é tão explorável quanto ausente.
    try:
        _com_ambiente(_segredo='curto', ENVIRONMENT='production')
    except RuntimeError:
        pass
    else:
        raise AssertionError('secret com menos de 32 chars passou em produção')
    print('OK  test_o_failsafe_do_jwt_DISPARA_em_producao')


def test_ninguem_recria_a_condicao_por_fora():
    """Fonte única: a condição não pode voltar a existir copiada.

    O bug nasceu de DUAS versões da mesma pergunta, e a estreita era a que protegia o JWT.
    Procura a assinatura da condição inline no código de produção.
    """
    import re
    base = os.path.join(os.path.dirname(__file__), '..')
    padrao = re.compile(r"environ\.get\('RENDER'\)\s*or\s*os\.environ\.get\('LEAKLAB_PROD'\)")
    violacoes = []
    for rel in [os.path.join('api', 'app.py'), os.path.join('database', 'auth.py')]:
        caminho = os.path.join(base, rel)
        if not os.path.exists(caminho):
            continue
        with open(caminho, encoding='utf-8') as f:
            for n, linha in enumerate(f, 1):
                if linha.lstrip().startswith('#'):
                    continue
                if padrao.search(linha):
                    violacoes.append(f'{rel}:{n}  {linha.strip()[:80]}')
    assert not violacoes, (
        'condição de produção recriada fora de is_production():\n  ' + '\n  '.join(violacoes))
    print('OK  test_ninguem_recria_a_condicao_por_fora')


if __name__ == '__main__':
    falhas = 0
    testes = (test_reconhece_o_ambiente_real_de_producao, test_mantem_os_sinais_legados,
              test_dev_limpo_nao_e_producao, test_o_failsafe_do_jwt_DISPARA_em_producao,
              test_ninguem_recria_a_condicao_por_fora)
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
