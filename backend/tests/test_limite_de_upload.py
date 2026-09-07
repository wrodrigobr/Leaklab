# -*- coding: utf-8 -*-
"""O limite de upload e por USUARIO, alto, e o 429 e honesto (hotfix 07/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Um fundador subiu o mes inteiro de historico e viu "Erro do servidor (HTTP 429)" em dezenas de
arquivos: nas 12 horas, 120 uploads aceitos e 712 recusados. O teto era 30 por hora POR IP, e o
limitador respondia texto, que a fila do front nao sabe ler. Em 03/09 o lote do Rullian ja tinha
perdido 189 de 280 torneios pelo mesmo teto; a "solucao" isentou so o script de importacao.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. O teto e `LIMITE_DE_UPLOADS_POR_HORA` por usuario: o (N+1)-esimo upload do MESMO usuario leva
   429; OUTRO usuario, no mesmo IP, passa.
2. O 429 e JSON com `code`, `limite`, `retry_after` e uma frase honesta ("ultrapassou o limite
   de N torneios por hora... tente de novo em X minutos"), com o header Retry-After.
3. O limitador conta mesmo com `app.testing` desligado; o teste desliga o filtro de isencao.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)
os.environ.pop('LEAKLAB_IMPORT_LOTE', None)

from database.schema import init_db                                       # noqa: E402
import database.repositories as repo                                      # noqa: E402
from database.auth import generate_token                                  # noqa: E402
import api.app as app_module                                              # noqa: E402
from api.app import app, limiter                                          # noqa: E402


def _dois_usuarios():
    init_db()
    from database.schema import get_conn
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    a = repo.create_user('lote_a', 'lote_a@t.local', 'senha12345', 'player')
    b = repo.create_user('lote_b', 'lote_b@t.local', 'senha12345', 'player')
    return ({'Authorization': 'Bearer %s' % generate_token(a, 'player')},
            {'Authorization': 'Bearer %s' % generate_token(b, 'player')})


def _envia(c, h):
    # corpo vazio: o endpoint responde 400 antes de ler arquivo, e o limitador conta a chamada
    return c.post('/analyze', headers=h, data={})


def _com_limitador_ligado(teste):
    """`app.testing` isenta o limitador (request_filter); aqui ele tem de contar."""
    antes = app.testing
    app.testing = False
    limiter.reset()
    try:
        teste()
    finally:
        app.testing = antes
        limiter.reset()


def test_o_teto_e_por_usuario_e_o_429_e_honesto():
    ha, hb = _dois_usuarios()
    original = app_module.LIMITE_DE_UPLOADS_POR_HORA
    app_module.LIMITE_DE_UPLOADS_POR_HORA = 3
    try:
        def corpo():
            c = app.test_client()
            for i in range(3):
                r = _envia(c, ha)
                assert r.status_code != 429, (i, r.status_code)
            r = _envia(c, ha)
            assert r.status_code == 429, r.status_code
            j = r.get_json()
            assert j and j['code'] == 'upload_rate_limit' and j['limite'] == 3, j
            assert j['retry_after'] >= 1 and r.headers.get('Retry-After') == str(j['retry_after']), (j, dict(r.headers))
            assert 'limite de 3 torneios por hora' in j['error'] and 'Tente de novo em' in j['error'] and 'minuto' in j['error'], j['error']
            # outro usuario, o MESMO cliente (mesmo IP): passa
            r = _envia(c, hb)
            assert r.status_code != 429, r.status_code
        _com_limitador_ligado(corpo)
    finally:
        app_module.LIMITE_DE_UPLOADS_POR_HORA = original


def test_o_teto_de_producao_absorve_um_lote_grande():
    """O caso real: 120 arquivos numa sentada. Com 300 por hora, nenhum leva 429."""
    ha, _ = _dois_usuarios()
    assert app_module.LIMITE_DE_UPLOADS_POR_HORA >= 300

    def corpo():
        c = app.test_client()
        for i in range(120):
            r = _envia(c, ha)
            assert r.status_code != 429, i
    _com_limitador_ligado(corpo)


def test_o_limitador_sem_o_hotfix_recusaria_o_lote():
    """Guarda do guarda: com o teto antigo (30), o 31o do mesmo usuario leva 429. Prova que o
    teste anterior ACHARIA a regressao (o limitador esta contando de verdade)."""
    ha, _ = _dois_usuarios()
    original = app_module.LIMITE_DE_UPLOADS_POR_HORA
    app_module.LIMITE_DE_UPLOADS_POR_HORA = 30
    try:
        def corpo():
            c = app.test_client()
            codigos = [_envia(c, ha).status_code for _ in range(31)]
            assert codigos[30] == 429 and 429 not in codigos[:30], codigos
        _com_limitador_ligado(corpo)
    finally:
        app_module.LIMITE_DE_UPLOADS_POR_HORA = original


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
