# -*- coding: utf-8 -*-
"""Arquivo com vários torneios vira vários torneios, não um só (13/09).

── O que estava acontecendo ───────────────────────────────────────────────────────────────

O `/analyze` lia `hands[0].tournament_id` e gravava o arquivo inteiro sob esse id. Medido no
acervo de produção: **42 registros continham mãos de 224 torneios diferentes**, em 3 contas. E em
vários deles o torneio gravado não era nem o majoritário:

    t238  gravado como T#3754315744 (40 mãos)   <- o nome do registro
          mas a maioria das mãos era T#3754316163 (231 mãos)

Ou seja, a tela mostrava um torneio com o nome de um e as mãos de outro, somando colocação,
prêmio e field size alheios. **Isso é dano de DADO, não de desempenho.**

O dano de desempenho vinha junto: o export do PartyPoker é por INTERVALO DE DATAS, não por
torneio. O arquivo real do Rullian tem 3.482 mãos e 36 torneios, ~4.932 decisões, ~159s de
processamento — acima do timeout de 120s do gunicorn. Dividido, cada torneio cabe folgado.

── Onde a divisão mora, e por quê ─────────────────────────────────────────────────────────

No BACKEND. A regra "de qual torneio é esta mão" já existe no parser, com os cinco dialetos do
acervo (PokerStars, GGPoker, ACR, CoinPoker, PartyGaming). Replicá-la no front seria a sexta
cópia da mesma regra, e a que quebraria calada quando um dialeto mudasse — o front só entende
PokerStars hoje (`hhImport.splitHands`).

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Que a divisão acontece, que ela agrupa pelo torneio certo, e — o mais importante — que o caminho
de UM torneio só **não muda em nada**, porque ele é 97% dos uploads do acervo e não pode pagar o
preço de uma correção que não é para ele.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.app import _pedacos_por_torneio                                       # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _um_torneio():
    return io.open(os.path.join(_FIX, 'revalidation_mini.txt'), encoding='utf-8').read()


def _dois_torneios():
    """O mesmo arquivo com metade das mãos trocada para outro Tournament #.

    Construído do fixture real em vez de inventado: mão forjada à mão não passa pelo parser, e
    um teste que não passa pelo parser não prova que a divisão funciona no dialeto de verdade.
    """
    raw = _um_torneio()
    blocos = [b for b in re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]
    metade = len(blocos) // 2
    saida = []
    for i, b in enumerate(blocos):
        if i >= metade:
            b = re.sub(r'Tournament #(\d+)', 'Tournament #999888777', b)
        saida.append(b)
    return ''.join(saida)


def test_um_torneio_so_NAO_divide():
    """CONTROLE, e é o caso de 97% dos uploads: sem nada a dividir, o caminho é o de sempre.

    `[]` é o sinal de "siga pelo fluxo antigo". Se este teste cair, a correção passou a cobrar
    imposto de quem não tinha o problema."""
    assert _pedacos_por_torneio(_um_torneio()) == []


def test_arquivo_vazio_ou_ilegivel_NAO_divide():
    for entrada in ('', '   ', 'isto nao e hand history nenhuma'):
        assert _pedacos_por_torneio(entrada) == [], repr(entrada)


def test_dois_torneios_viram_dois_pedacos():
    pedacos = _pedacos_por_torneio(_dois_torneios())
    assert len(pedacos) == 2, [(t, n) for t, n, _ in pedacos]
    ids = sorted(t for t, _, _ in pedacos)
    assert '999888777' in ids, ids
    # nenhuma mão se perde na divisão
    total = sum(n for _, n, _ in pedacos)
    assert total == 5, total


def test_cada_pedaco_contem_SO_as_maos_do_seu_torneio():
    """O erro que o defeito produzia era exatamente este: mãos de um torneio sob o id de outro."""
    for tid, n, texto in _pedacos_por_torneio(_dois_torneios()):
        achados = set(re.findall(r'Tournament #(\d+)', texto))
        assert achados == {tid}, ('pedaco de %s contem mãos de %s' % (tid, achados - {tid}))
        assert texto.count('PokerStars Hand #') == n, (tid, n, texto.count('PokerStars Hand #'))


def test_o_pedaco_ainda_e_PARSEAVEL():
    """Dividir texto é fácil; dividir de um jeito que o parser ainda leia é o que importa. Sem
    isto, a divisão poderia cortar no meio de uma mão e o upload falharia depois."""
    from leaklab.parser import parse_pokerstars_file_from_text
    for tid, n, texto in _pedacos_por_torneio(_dois_torneios()):
        maos = parse_pokerstars_file_from_text(texto)
        assert len(maos) == n, (tid, len(maos), n)
        assert {str(m.tournament_id) for m in maos} == {tid}, tid


def _por_json(cliente, headers, texto):
    return cliente.post('/analyze', json={'content': texto, 'filename': 'dois.txt'},
                        headers=headers)


def _por_multipart(cliente, headers, texto):
    """O outro jeito de subir, e o que quebrou de verdade.

    Em `multipart/form-data` o stream do arquivo e consumido na PRIMEIRA leitura. A primeira
    versao do orquestrador lia o request para dividir e deixava o `_analyze_impl` ler de novo:
    a segunda leitura vinha vazia e o upload devolvia 400. Passou verde neste arquivo inteiro,
    porque aqui tudo subia por JSON, e so caiu na suite completa (`test_api.py`)."""
    from io import BytesIO
    return cliente.post('/analyze', data={'file': (BytesIO(texto.encode('utf-8')), 'dois.txt')},
                        content_type='multipart/form-data', headers=headers)


def test_PONTA_A_PONTA_o_upload_gera_dois_torneios(envio=_por_json):
    """O único guarda que prova o comportamento, e ele existe porque os de texto NAO bastaram.

    Quebrando de propósito, duas alterações que desligam a divisão passaram verdes nos guardas
    de fiação: trocar a chamada por `pedacos = []`, e fazer o `_analyze_impl` ignorar o pedaço.
    Nos dois casos as STRINGS que aqueles guardas procuram continuavam no arquivo (a definição
    da função, o nome do parâmetro na assinatura). Presença de texto não é comportamento — este
    sobe o arquivo pela rota real e conta os registros no banco.
    """
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    anterior = os.environ.get('LEAKLAB_DB')
    os.environ['LEAKLAB_DB'] = tmp.name
    os.environ.pop('DATABASE_URL', None)
    try:
        import importlib
        from database import schema as _schema
        importlib.reload(_schema)
        _schema.init_db()
        from database.schema import get_conn
        from database.repositories import _adapt
        from database.auth import generate_token
        conn = get_conn()
        conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash, plan) "
                            "VALUES (1,'u','u@e.st','h','pro')"))
        conn.commit(); conn.close()

        import api.app as _app
        _app.app.config['TESTING'] = True
        cliente = _app.app.test_client()
        tok = generate_token(1, 'player')
        r = envio(cliente, {'Authorization': 'Bearer ' + tok}, _dois_torneios())
        assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:200])
        dados = r.get_json() or {}
        assert dados.get('torneios_no_arquivo') == 2, (
            'a resposta nao diz que o arquivo tinha 2 torneios (veio %r): o orquestrador '
            'nao dividiu' % (dados.get('torneios_no_arquivo'),))

        conn = get_conn()
        linhas = [dict(x) for x in conn.execute(
            "SELECT tournament_id, hands_count FROM tournaments ORDER BY id").fetchall()]
        conn.close()
        assert len(linhas) == 2, ('o arquivo de DOIS torneios virou %d registro(s)' % len(linhas),
                                  linhas)
        ids = {str(l['tournament_id']) for l in linhas}
        assert '999888777' in ids, ids
        # e nenhuma mão se perdeu: 5 no arquivo, 5 somadas nos dois registros
        assert sum(int(l['hands_count'] or 0) for l in linhas) == 5, linhas
    finally:
        if anterior is not None:
            os.environ['LEAKLAB_DB'] = anterior
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def test_PONTA_A_PONTA_por_MULTIPART_tambem_gera_dois():
    """Mesma prova, outro transporte. Existe porque a suite filtrada NAO basta."""
    test_PONTA_A_PONTA_o_upload_gera_dois_torneios(envio=_por_multipart)


def test_multipart_de_UM_torneio_so_continua_entrando():
    """CONTROLE do conserto: o caminho que nao divide tambem le o request uma vez so.

    Este e literalmente o caso que quebrou — arquivo de um torneio, enviado por multipart, com
    o orquestrador relendo um stream ja consumido."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    anterior = os.environ.get('LEAKLAB_DB')
    os.environ['LEAKLAB_DB'] = tmp.name
    os.environ.pop('DATABASE_URL', None)
    try:
        import importlib
        from database import schema as _schema
        importlib.reload(_schema)
        _schema.init_db()
        from database.schema import get_conn
        from database.repositories import _adapt
        from database.auth import generate_token
        conn = get_conn()
        conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash, plan) "
                            "VALUES (1,'u','u@e.st','h','pro')"))
        conn.commit(); conn.close()

        import api.app as _app
        _app.app.config['TESTING'] = True
        cliente = _app.app.test_client()
        r = _por_multipart(cliente, {'Authorization': 'Bearer ' + generate_token(1, 'player')},
                           _um_torneio())
        assert r.status_code == 200, (
            'upload de UM torneio por multipart devolveu %s: o request foi lido duas vezes'
            % r.status_code, r.get_data(as_text=True)[:200])
        dados = r.get_json() or {}
        assert (dados.get('total_hands') or 0) > 0, dados
        # e o caminho de um torneio so nao ganha o campo de divisao
        assert 'torneios_no_arquivo' not in dados, (
            'arquivo de um torneio so passou a ser tratado como dividido', dados.get(
                'torneios_no_arquivo'))
    finally:
        if anterior is not None:
            os.environ['LEAKLAB_DB'] = anterior
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def test_REEXPORTAR_o_mesmo_intervalo_nao_e_falha():
    """O caso NORMAL da sala que motivou tudo isto, achado na homologacao contra o Postgres.

    O export do PartyPoker e por INTERVALO DE DATAS. Quem reexporta uma semana reenvia a semana
    anterior inteira, entao "torneio que ja estava" e o uso comum, nao o excepcional.

    A primeira versao do orquestrador achatava os 409 `duplicate` dos pedacos num 422 generico
    e devolvia a mensagem de UM torneio ("Torneio 999900001 ja foi importado") para um arquivo
    que tinha varios. Duas coisas erradas de uma vez: o contrato (o caminho de um torneio so
    responde 409 com `duplicate`) e a frase que o jogador le.
    """
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    anterior = os.environ.get('LEAKLAB_DB')
    os.environ['LEAKLAB_DB'] = tmp.name
    os.environ.pop('DATABASE_URL', None)
    try:
        import importlib
        from database import schema as _schema
        importlib.reload(_schema)
        _schema.init_db()
        from database.schema import get_conn
        from database.repositories import _adapt
        from database.auth import generate_token
        conn = get_conn()
        conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash, plan) "
                            "VALUES (1,'u','u@e.st','h','pro')"))
        conn.commit(); conn.close()

        import api.app as _app
        _app.app.config['TESTING'] = True
        cliente = _app.app.test_client()
        headers = {'Authorization': 'Bearer ' + generate_token(1, 'player')}

        r1 = _por_json(cliente, headers, _dois_torneios())
        assert r1.status_code == 200, r1.status_code
        assert (r1.get_json() or {}).get('torneios_no_arquivo') == 2

        # segunda volta: o MESMO arquivo, nenhuma mao nova
        r2 = _por_json(cliente, headers, _dois_torneios())
        d2 = r2.get_json() or {}
        assert r2.status_code == 409, (
            'reexportar o mesmo intervalo devolveu %s; o caminho de um torneio so devolve 409 '
            'com `duplicate`, e o orquestrador nao pode achatar isso' % r2.status_code, d2)
        assert d2.get('duplicate') is True, ('o sinal `duplicate` se perdeu na divisao', d2)
        assert d2.get('torneios_ja_importados') == 2, d2.get('torneios_ja_importados')
        # e a frase fala dos DOIS, nao de um
        assert '2 torneios' in (d2.get('error') or ''), (
            'a mensagem fala de um torneio so num arquivo que tinha 2', d2.get('error'))

        # nada duplicou no banco
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) AS n FROM tournaments").fetchone()
        conn.close()
        from database.rowutil import value
        assert value(n, 'n') == 2, ('a segunda volta criou registro', value(n, 'n'))
    finally:
        if anterior is not None:
            os.environ['LEAKLAB_DB'] = anterior
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def test_XP_por_TORNEIO_e_nao_por_arquivo():
    """Decisao do dono, 13/09: *"acho que deveria ser por torneio"*.

    O `count` existe para isso, e o VALOR unitario fica no backend de proposito — se o front
    multiplicasse, a tabela `_XP_AMOUNTS` passaria a viver em dois lugares e o cliente decidiria
    quanto vale cada evento (regra 5).
    """
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    anterior = os.environ.get('LEAKLAB_DB')
    os.environ['LEAKLAB_DB'] = tmp.name
    os.environ.pop('DATABASE_URL', None)
    try:
        import importlib
        from database import schema as _schema
        importlib.reload(_schema)
        _schema.init_db()
        from database.schema import get_conn
        from database.repositories import _adapt, add_xp, _XP_AMOUNTS
        from database.rowutil import value
        conn = get_conn()
        for uid in (1, 2, 3):
            conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                                "VALUES (?,?,?,'h')"), (uid, 'u%d' % uid, 'u%d@e.st' % uid))
        conn.commit(); conn.close()

        unit = _XP_AMOUNTS.get('tournament_imported', 10)

        # sem `count`, nada muda: e o caminho de 97% dos uploads
        r1 = add_xp(1, 'tournament_imported')
        assert r1.get('xp_gained') == unit, (r1, unit)

        # com 12 torneios, doze vezes o valor de um
        r2 = add_xp(2, 'tournament_imported', None, count=12)
        assert r2.get('xp_gained') == unit * 12, (r2.get('xp_gained'), unit * 12)

        # e o teto protege de `count` vindo de fora
        r3 = add_xp(3, 'tournament_imported', None, count=10 ** 9)
        assert r3.get('xp_gained') == unit * 500, r3.get('xp_gained')

        # o STREAK conta dias, nao eventos: 12 torneios de uma vez nao viram 12 dias
        assert r2.get('streak') == 1, ('o count inflou o streak', r2.get('streak'))

        conn = get_conn()
        linha = conn.execute(_adapt("SELECT xp_total FROM users WHERE id=?"), (2,)).fetchone()
        conn.close()
        assert value(linha, 'xp_total') == unit * 12, value(linha, 'xp_total')
    finally:
        if anterior is not None:
            os.environ['LEAKLAB_DB'] = anterior
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def test_o_endpoint_de_xp_repassa_o_count():
    """FIACAO: o `count` so serve se a rota o entregar a funcao."""
    src = io.open(os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py'),
                  encoding='utf-8').read()
    codigo = chr(10).join(l.split('#', 1)[0] for l in src.splitlines())
    assert "count=body.get('count')" in codigo, (
        'a rota /player/xp parou de repassar o `count`: o front manda a quantidade e o XP '
        'volta a ser um por arquivo, calado')


def test_o_analyze_usa_o_orquestrador():
    """FIACAO. A divisão só vale se o endpoint passar por ela."""
    src = io.open(os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py'),
                  encoding='utf-8').read()
    codigo = chr(10).join(l.split('#', 1)[0] for l in src.splitlines())
    assert '_analyze_orquestrado()' in codigo, 'o /analyze parou de usar o orquestrador'
    assert '_pedacos_por_torneio(' in codigo, 'o orquestrador parou de dividir'
    # e o `_analyze_impl` precisa aceitar o pedaço, senão o loop analisa o arquivo inteiro N vezes
    assert 'content_override' in codigo, (
        '`_analyze_impl` nao aceita mais o conteudo do pedaco: o loop reprocessaria o arquivo '
        'inteiro uma vez por torneio')


def test_a_divisao_preserva_o_texto_das_maos():
    """Nenhum pedaço pode ganhar texto que não era dele, nem perder o seu: a soma dos pedaços
    tem as mesmas mãos do arquivo, sem duplicar."""
    arquivo = _dois_torneios()
    pedacos = _pedacos_por_torneio(arquivo)
    ids_no_arquivo = re.findall(r'PokerStars Hand #(\d+)', arquivo)
    ids_nos_pedacos = []
    for _, _, texto in pedacos:
        ids_nos_pedacos += re.findall(r'PokerStars Hand #(\d+)', texto)
    assert sorted(ids_nos_pedacos) == sorted(ids_no_arquivo), (
        'a divisao perdeu ou duplicou mao', len(ids_nos_pedacos), len(ids_no_arquivo))


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
