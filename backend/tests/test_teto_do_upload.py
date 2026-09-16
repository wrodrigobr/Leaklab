# -*- coding: utf-8 -*-
"""O teto do corpo da requisicao, e a mensagem que ele produz.

── O caso do Rullian (16/09) ─────────────────────────────────────────────────────────────────

Ele tentou importar o export de PartyPoker e "deu erro". O arquivo tem **15,0 MB** (11.722 maos,
117 torneios) e o `MAX_CONTENT_LENGTH` era de **5 MB**: o Flask recusava com 413 antes de qualquer
rota, entao nenhum log do produto registrava a tentativa e nada no parser estava errado.

Duas coisas se somavam para deixar o diagnostico caro:

1. O teto morava so no `app.config`, sem nenhum teste dizendo qual export o produto aceita.
2. A mensagem do 413 tinha o numero CRAVADO no texto ("limite: 5MB"). Subir o teto sem mexer nela
   mandaria o jogador dividir um arquivo que ja cabe -- a classe de defeito da regra 5, o mesmo
   numero em dois lugares.

Este arquivo trava as duas.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_SECRET', 'dev_local_apenas_para_testes_0000000000000000')
os.environ.setdefault('LEAKLAB_DB', ':memory:')

from api.app import MAX_UPLOAD_MB, app          # noqa: E402
from database.repositories import PLAN_LIMITS  # noqa: E402

#: O maior export REAL medido: o PartyPoker do Rullian, 16/09. Nao e numero redondo de propósito:
#: o teto tem de ser justificado por arquivo que existe, e nao por palpite.
MAIOR_EXPORT_REAL_MB = 15.0


def test_o_teto_COMPORTA_o_maior_export_real():
    mb = app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
    assert mb >= MAIOR_EXPORT_REAL_MB, (
        'o teto (%.0f MB) recusa o export de PartyPoker de 15,0 MB que um fundador mandou' % mb)
    # e sobra folga, porque o proximo export nao vem menor
    assert mb >= MAIOR_EXPORT_REAL_MB * 1.2, mb


def test_o_global_ACOMODA_o_maior_plano():
    """O ponto que decide o desenho inteiro.

    `MAX_CONTENT_LENGTH` e verificado na camada WSGI, antes de qualquer rota e antes do
    `@require_auth`: ele nao sabe de quem e a requisicao. Se ele valesse o teto do Free, o arquivo
    do Pro seria cortado com 413 genérico sem NUNCA chegar na regra do plano -- e o Pro pagante
    veria o limite do gratuito sem ninguem entender por que.
    """
    maior = max(int(p.get('upload_mb') or 0) for p in PLAN_LIMITS.values())
    assert MAX_UPLOAD_MB >= maior, (MAX_UPLOAD_MB, maior)
    assert app.config['MAX_CONTENT_LENGTH'] >= maior * 1024 * 1024


def test_todo_plano_declara_o_teto():
    """Plano sem `upload_mb` cairia no global (40 MB) por omissao, e um plano novo herdaria o
    teto do Pro de graca. Aqui a ausencia e erro, nao default."""
    for nome, p in PLAN_LIMITS.items():
        assert p.get('upload_mb'), 'plano %r sem upload_mb' % nome
        assert int(p['upload_mb']) > 0, nome
    assert int(PLAN_LIMITS['free']['upload_mb']) < int(PLAN_LIMITS['pro']['upload_mb']),         'o free precisa ser MENOR que o pro, senao o teto nao separa nada'


def test_o_FREE_e_recusado_pelo_HEADER_sem_ler_o_arquivo():
    """O caso do Rullian invertido: um free mandando o export de 15 MB.

    A recusa olha `Content-Length`, entao nenhum byte do arquivo sobe para a memoria do worker.
    Testar isso importa porque a versao obvia (ler o corpo e medir) aplica o teto pagando
    exatamente o custo que o teto existe para evitar.
    """
    from api.app import _recusa_por_tamanho
    import flask

    quinze_mb = int(15.0 * 1024 * 1024)
    # `headers={'Content-Length': ...}` NAO funciona aqui: o Werkzeug descarta e recalcula pelo
    # corpo, entao com corpo vazio o `content_length` vinha None, a funcao saia pelo `if not
    # n_bytes` e ESTE teste passava sem exercitar nada. `environ_base` monta o WSGI environ como
    # uma requisicao real chega.
    with app.test_request_context('/uploads', method='POST',
                                  environ_base={'CONTENT_LENGTH': str(quinze_mb)}):
        flask.g.user_id = 4242
        _finge_plano('free')
        try:
            r = _recusa_por_tamanho()
        finally:
            _restaura_plano()
    assert r is not None, 'free com 15 MB passou'
    resp, code = r
    assert code == 413, code
    d = resp.get_json()
    assert '15.0MB' in d['error'], d['error']
    assert '5MB' in d['error'], d['error']
    # a mensagem OFERECE saida: sem isso o jogador so sabe que falhou
    assert 'Pro' in d['error'], d['error']
    assert d['erro_de_tamanho']['limite_mb'] == 5, d['erro_de_tamanho']


def test_o_PRO_passa_com_o_MESMO_arquivo():
    """O controle do caso acima. Sem ele, um teto quebrado que recusa todo mundo passaria
    verde -- o guarda diria "recusou o free" sem provar que o pro entra."""
    from api.app import _recusa_por_tamanho
    import flask

    quinze_mb = int(15.0 * 1024 * 1024)
    # `headers={'Content-Length': ...}` NAO funciona aqui: o Werkzeug descarta e recalcula pelo
    # corpo, entao com corpo vazio o `content_length` vinha None, a funcao saia pelo `if not
    # n_bytes` e ESTE teste passava sem exercitar nada. `environ_base` monta o WSGI environ como
    # uma requisicao real chega.
    with app.test_request_context('/uploads', method='POST',
                                  environ_base={'CONTENT_LENGTH': str(quinze_mb)}):
        flask.g.user_id = 4242
        _finge_plano('pro')
        try:
            r = _recusa_por_tamanho()
        finally:
            _restaura_plano()
    assert r is None, ('o pro foi recusado com 15 MB', r[0].get_json() if r else None)


def test_sem_content_length_o_teto_do_plano_NAO_se_aplica():
    """CONTROLE do mecanismo, e a razao pela qual os dois testes acima quase passaram vazios.

    Sem o header nao ha o que medir antes de ler o corpo, e a funcao sai sem recusar -- o teto
    global (40 MB) e quem segura. Travar isto aqui deixa explicito que os casos do free e do pro
    dependem do header CHEGAR, que foi exatamente o que falhou na primeira versao deles.
    """
    from api.app import _recusa_por_tamanho
    import flask

    with app.test_request_context('/uploads', method='POST'):
        flask.g.user_id = 4242
        _finge_plano('free')
        try:
            assert flask.request.content_length in (None, 0), flask.request.content_length
            assert _recusa_por_tamanho() is None
        finally:
            _restaura_plano()


def test_falha_ao_ler_o_plano_NAO_barra_o_upload():
    """A regra da casa: barrar upload ataca a ativacao. Se a consulta do plano cai, o upload
    passa e o teto global (40 MB) segue valendo -- degrada para o generoso, nao para o fechado."""
    from api.app import _recusa_por_tamanho
    import flask

    with app.test_request_context('/uploads', method='POST',
                                  environ_base={'CONTENT_LENGTH': str(6 * 1024 * 1024)}):
        flask.g.user_id = 4242
        import api.app as mod
        orig = mod.__dict__.get('get_quota_status')
        import database.repositories as repo
        salvo = repo.get_quota_status

        def explode(_uid):
            raise RuntimeError('banco fora')
        repo.get_quota_status = explode
        try:
            r = _recusa_por_tamanho()
        finally:
            repo.get_quota_status = salvo
            if orig is not None:
                mod.__dict__['get_quota_status'] = orig
    assert r is None, 'plano ilegivel barrou o upload'


def test_as_DUAS_rotas_de_upload_checam_o_teto():
    """`/uploads` e o caminho do front novo e `/analyze` continua de pe para o bundle em cache.
    Um teto so numa delas deixaria o jogador com o bundle antigo sem limite nenhum."""
    import inspect

    import api.app as mod
    for nome in ('analyze', 'receber_upload'):
        fonte = inspect.getsource(getattr(mod, nome))
        assert '_recusa_por_tamanho()' in fonte, 'a rota %s nao checa o teto do plano' % nome


#: o plano fingido, para o teste nao depender de um usuario real no banco
_PLANO_FINGIDO = {'valor': None}


def _finge_plano(plano):
    import database.repositories as repo
    _PLANO_FINGIDO['orig'] = repo.get_quota_status
    _PLANO_FINGIDO['valor'] = plano
    repo.get_quota_status = lambda _uid: {
        'plan': plano, 'limits': dict(PLAN_LIMITS[plano]),
    }


def _restaura_plano():
    import database.repositories as repo
    if _PLANO_FINGIDO.get('orig'):
        repo.get_quota_status = _PLANO_FINGIDO['orig']


def test_a_mensagem_do_413_DERIVA_do_config():
    """O guarda da regra 5. Com o numero cravado no texto, este teste falha assim que o teto
    muda -- que e exatamente quando a mensagem passaria a mentir."""
    with app.test_request_context():
        from werkzeug.exceptions import RequestEntityTooLarge

        resp, code = app.error_handler_spec[None][413][RequestEntityTooLarge](
            RequestEntityTooLarge())
        assert code == 413, code
        texto = resp.get_json()['error']
    assert str(MAX_UPLOAD_MB) in texto, (texto, MAX_UPLOAD_MB)
    # e o numero VELHO nao pode estar sobrando no texto
    assert '5MB' not in texto or MAX_UPLOAD_MB == 5, texto


def test_o_teto_e_UM_numero_so():
    """`MAX_UPLOAD_MB` e a fonte; o config deriva dele. Dois literais aqui seriam a proxima
    divergencia calada."""
    assert app.config['MAX_CONTENT_LENGTH'] == MAX_UPLOAD_MB * 1024 * 1024


def test_o_teto_de_bytes_em_aberto_cabe_pelo_menos_UM_export_grande():
    """O outro teto da cadeia, e ele NAO foi revisado junto de propósito.

    `BYTES_EM_ABERTO_MAX_POR_USUARIO` justificava 40 MB como "13 vezes o maior arquivo real
    medido (3,1 MB)". Com 15 MB por export, esses 40 MB passaram a comportar DOIS arquivos, nao
    treze. Isso continua servindo o caso real (um export por mes), e subir o teto e decisao de
    custo de armazenamento, nao conserto de bug -- entao ficou para o dono.

    O que este teste impede e o teto de bytes ficar MENOR que o do corpo, caso em que o arquivo
    passaria pelo Flask e seria recusado depois, com mensagem de "espaco em aberto" para quem
    nunca mandou nada.
    """
    from leaklab.recepcao_de_upload import BYTES_EM_ABERTO_MAX_POR_USUARIO
    assert BYTES_EM_ABERTO_MAX_POR_USUARIO >= app.config['MAX_CONTENT_LENGTH'], (
        BYTES_EM_ABERTO_MAX_POR_USUARIO, app.config['MAX_CONTENT_LENGTH'])


if __name__ == '__main__':
    passed = failed = 0
    for nome, fn in sorted(list(globals().items())):
        if not nome.startswith('test_') or not callable(fn):
            continue
        try:
            fn()
            print('OK  %s' % nome)
            passed += 1
        except AssertionError as e:
            print('FALHOU  %s: %s' % (nome, e))
            failed += 1
        except Exception as e:
            import traceback
            print('ERRO    %s: %s: %s' % (nome, type(e).__name__, e))
            traceback.print_exc()
            failed += 1
    print('\nTotal: %d | Passed: %d | Failed: %d' % (passed + failed, passed, failed))
    sys.exit(1 if failed else 0)
