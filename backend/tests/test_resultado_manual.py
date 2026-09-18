# -*- coding: utf-8 -*-
"""O jogador preenche o resultado do torneio quando nao ha summary que saibamos ler.

── O pedido (17/09) ──────────────────────────────────────────────────────────────────────────

O dono: "nao haviamos criado um meio de torneios do party poker, o usuario conseguir preencher os
dados do summary que precisamos?". Nao haviamos: `/tournament/results` le o Tournament Summary do
PokerStars (.txt) e do ACR/WPN (.ots), e o PartyPoker nao esta entre eles -- aqueles torneios
ficavam para sempre com "resultado desconhecido", e sem prize nao existe ROI nem bankroll.

O que estes casos protegem, e por que cada um importa:

1. A hierarquia de confianca NAO e simetrica: o arquivo vence o digitado, e o digitado nao
   sobrescreve arquivo. Trocar dado real por dado lembrado seria perda, e ela seria silenciosa.
2. A procedencia fica GRAVADA. O ROI e o bankroll saem desses numeros, e o jogador precisa saber
   qual deles depende do que ele mesmo digitou.
3. O lucro e CALCULADO (`prize - buy_in`). Aceitar os tres do cliente deixaria entrar um conjunto
   que nao fecha, e ninguem saberia qual dos tres o ROI usou.
4. Erro vira FRASE, e nao codigo: "nao podemos retornar codigo de erro para o usuario, temos que
   ter o erro tratado" (o dono, 16/09).
"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_SECRET', 'dev_local_apenas_para_testes_0000000000000000')

TID = 'PARTY-13165152578'


def _ambiente():
    """App + banco descartavel. Devolve `(client, cabecalhos, user_id)`."""
    import importlib
    banco = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    banco.close()
    os.environ['LEAKLAB_DB'] = banco.name

    from database import schema
    importlib.reload(schema)

    def gc():
        conn = sqlite3.connect(banco.name)
        conn.row_factory = sqlite3.Row
        return conn

    from database import repositories
    schema.get_conn = gc
    repositories.get_conn = gc
    schema.init_db()

    from api.app import app
    from database.auth import generate_token
    from database.repositories import create_user
    app.config['TESTING'] = True

    uid = create_user('qa_manual', 'qa.manual@teste.local', 'SenhaDeTeste!1')
    tok = generate_token(uid, 'player')

    # um torneio SEM financeiro, como o PartyPoker chega
    conn = gc()
    conn.execute("INSERT INTO tournaments (user_id, tournament_id, site, hero) VALUES (?,?,?,?)",
                 (uid, TID, 'PartyPoker', 'Hero'))
    conn.commit()
    conn.close()
    return app.test_client(), {'Authorization': 'Bearer %s' % tok}, uid, gc


def _torneio(gc, uid):
    conn = gc()
    try:
        r = conn.execute("SELECT * FROM tournaments WHERE user_id=? AND tournament_id=?",
                         (uid, TID)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def test_preenche_e_o_lucro_e_CALCULADO():
    cli, cab, uid, gc = _ambiente()
    r = cli.post('/tournament/%s/results/manual' % TID, headers=cab,
                 json={'place': 6, 'prize': 12.40, 'buy_in': 5.50, 'field_size': 180})
    assert r.status_code == 200, (r.status_code, r.data)
    corpo = json.loads(r.data)
    assert corpo['profit'] == 6.90, corpo
    assert corpo['financeiro_origem'] == 'manual'

    t = _torneio(gc, uid)
    assert t['place'] == 6 and t['prize'] == 12.40 and t['buy_in'] == 5.50
    assert t['profit'] == 6.90
    assert t['field_size'] == 180
    assert t['financeiro_origem'] == 'manual', 'sem a procedencia o digitado se passa por arquivo'


def test_as_ENTRADAS_entram_no_custo_e_o_re_entries_fica_registrado():
    """Achado com os dados reais do dono: sete torneios do PartyPoker, um com re-entrada.

    O lucro so fechava se o buy-in digitado ja fosse o TOTAL -- e ai a etiqueta do torneio ficava
    errada (um torneio de $1,10 registrado como $2,20) e o `re_entries` nao existia, enquanto o
    caminho do ARQUIVO registra os dois.

    A convencao e a mesma dos dois caminhos, e esta escrita no codigo do arquivo: o custo real vai
    para a coluna `buy_in`, porque nao ha coluna de "total investido" e e dela que o ROI soma.
    Divergir aqui faria o mesmo torneio ter custo diferente conforme a fonte.
    """
    cli, cab, uid, gc = _ambiente()
    # o caso real: 22/94, buy-in de 1,10, DUAS entradas, premio de 2,08 -> lucro -0,12
    r = cli.post('/tournament/%s/results/manual' % TID, headers=cab,
                 json={'place': 22, 'prize': 2.08, 'buy_in': 1.10, 'field_size': 94,
                       'entradas': 2})
    assert r.status_code == 200, (r.status_code, r.data)
    corpo = json.loads(r.data)
    assert corpo['buy_in'] == 2.20, ('o buy_in de volta e o CUSTO', corpo)
    assert corpo['profit'] == -0.12, corpo
    assert corpo['entradas'] == 2 and corpo['re_entries'] == 1, corpo

    t = _torneio(gc, uid)
    assert t['buy_in'] == 2.20 and t['profit'] == -0.12, t
    assert t['re_entries'] == 1, 'a re-entrada nao ficou registrada: %s' % t.get('re_entries')


def test_SEM_entradas_o_custo_e_o_buy_in(_=None):
    """CONTROLE do caso acima: sem ele, um `entradas` cravado em 2 passaria verde la.

    O campo e opcional de proposito -- a maioria dos torneios nao tem re-entrada, e exigir o numero
    obrigaria todo jogador a preencher um campo que quase sempre vale 1.
    """
    cli, cab, uid, gc = _ambiente()
    r = cli.post('/tournament/%s/results/manual' % TID, headers=cab,
                 json={'place': 5, 'prize': 6.16, 'buy_in': 1.10, 'field_size': 92})
    corpo = json.loads(r.data)
    assert corpo['buy_in'] == 1.10 and corpo['profit'] == 5.06, corpo
    assert corpo['entradas'] == 1 and corpo['re_entries'] == 0, corpo

    # e entradas ZERO e recusada com frase, nao aceita como 1: quem digita 0 errou, e o silencio
    # transformaria o erro dele num numero plausivel
    r0 = cli.post('/tournament/%s/results/manual' % TID, headers=cab,
                  json={'place': 5, 'prize': 6.16, 'buy_in': 1.10, 'entradas': 0})
    assert r0.status_code == 422, (r0.status_code, r0.data)
    assert not json.loads(r0.data)['error'].isdigit(), 'erro numerico vazou para o usuario'


def test_o_lucro_que_o_CLIENTE_manda_e_ignorado():
    """Se o cliente pudesse mandar o lucro, entraria um conjunto que nao fecha -- e o ROI usaria
    um dos tres numeros sem ninguem saber qual."""
    cli, cab, uid, gc = _ambiente()
    cli.post('/tournament/%s/results/manual' % TID, headers=cab,
             json={'place': 1, 'prize': 100.0, 'buy_in': 10.0, 'profit': 9999.0})
    t = _torneio(gc, uid)
    assert t['profit'] == 90.0, t['profit']


def test_o_digitado_NAO_sobrescreve_o_arquivo():
    """A hierarquia de confianca: o arquivo e a fonte real. Trocar por digitacao seria perder dado
    bom por dado lembrado, e a perda seria silenciosa."""
    cli, cab, uid, gc = _ambiente()
    from database.repositories import update_tournament_financials
    update_tournament_financials(uid, TID, buy_in=5.5, prize=12.4, profit=6.9, place=6,
                                 origem='arquivo')

    r = cli.post('/tournament/%s/results/manual' % TID, headers=cab,
                 json={'place': 1, 'prize': 999.0, 'buy_in': 5.5})
    assert r.status_code == 409, r.status_code
    corpo = json.loads(r.data)
    assert 'arquivo' in corpo['error'].lower(), corpo
    # e o numero do arquivo continua de pe
    t = _torneio(gc, uid)
    assert t['prize'] == 12.4 and t['place'] == 6, t


def test_o_arquivo_SOBRESCREVE_o_digitado():
    """O outro sentido vale: quem digitou e depois conseguiu o arquivo tem o numero corrigido."""
    cli, cab, uid, gc = _ambiente()
    cli.post('/tournament/%s/results/manual' % TID, headers=cab,
             json={'place': 9, 'prize': 0.0, 'buy_in': 5.5})
    assert _torneio(gc, uid)['financeiro_origem'] == 'manual'

    from database.repositories import update_tournament_financials
    update_tournament_financials(uid, TID, buy_in=5.5, prize=12.4, profit=6.9, place=6,
                                 origem='arquivo')
    t = _torneio(gc, uid)
    assert t['prize'] == 12.4 and t['place'] == 6
    assert t['financeiro_origem'] == 'arquivo'


def test_digitado_sobre_digitado_PASSA():
    """Ele esta corrigindo o que ele mesmo pos: recusar aqui seria prender o jogador no erro dele."""
    cli, cab, uid, gc = _ambiente()
    cli.post('/tournament/%s/results/manual' % TID, headers=cab,
             json={'place': 9, 'prize': 0.0, 'buy_in': 5.5})
    r = cli.post('/tournament/%s/results/manual' % TID, headers=cab,
                 json={'place': 6, 'prize': 12.4, 'buy_in': 5.5})
    assert r.status_code == 200, r.status_code
    assert _torneio(gc, uid)['place'] == 6


def test_o_erro_vira_FRASE_e_nao_codigo():
    cli, cab, uid, gc = _ambiente()
    casos = [
        ({'prize': 10, 'buy_in': 5}, 'place'),                       # falta a colocacao
        ({'place': 0, 'prize': 10, 'buy_in': 5}, 'place'),           # colocacao invalida
        ({'place': 1, 'prize': -5, 'buy_in': 5}, 'prize'),           # premio negativo
        ({'place': 'sexto', 'prize': 10, 'buy_in': 5}, 'place'),     # nao numerico
        ({'place': 200, 'prize': 10, 'buy_in': 5, 'field_size': 180}, 'coloca'),
    ]
    for corpo, esperado in casos:
        r = cli.post('/tournament/%s/results/manual' % TID, headers=cab, json=corpo)
        assert r.status_code == 422, (corpo, r.status_code)
        msg = json.loads(r.data)['error']
        assert esperado in msg.lower(), (corpo, msg)
        # a frase nao pode ser um codigo nem um traceback na cara do jogador
        assert 'traceback' not in msg.lower() and '422' not in msg, msg
        assert len(msg) > 15, msg

    # e nada foi gravado por engano
    t = _torneio(gc, uid)
    assert t['prize'] is None and t['place'] is None, t


def test_torneio_de_OUTRO_jogador_nao_e_alcancavel():
    """A rota recebe o `tournament_id` da sala, que NAO e unico entre usuarios (cicatriz da casa).
    Sem o escopo por `user_id`, um jogador editaria o resultado do torneio de outro."""
    cli, cab, uid, gc = _ambiente()
    from database.auth import generate_token
    from database.repositories import create_user
    outro = create_user('qa_outro', 'qa.outro@teste.local', 'SenhaDeTeste!2')
    cab_outro = {'Authorization': 'Bearer %s' % generate_token(outro, 'player')}

    r = cli.post('/tournament/%s/results/manual' % TID, headers=cab_outro,
                 json={'place': 1, 'prize': 999.0, 'buy_in': 5.5})
    assert r.status_code == 404, r.status_code
    t = _torneio(gc, uid)
    assert t['prize'] is None, 'o torneio do outro jogador foi alterado'


def test_sem_login_nao_passa():
    cli, cab, uid, gc = _ambiente()
    r = cli.post('/tournament/%s/results/manual' % TID,
                 json={'place': 1, 'prize': 10.0, 'buy_in': 5.0})
    assert r.status_code in (401, 403), r.status_code


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
