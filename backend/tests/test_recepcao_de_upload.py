# -*- coding: utf-8 -*-
"""Receber o arquivo e processá-lo são coisas diferentes (14/09).

── O incidente ───────────────────────────────────────────────────────────────────────────────

Um fundador tentou subir três arquivos. Dois mostraram `NetworkError` e um passou. Nos logs:

    16:57:32 [CRITICAL] WORKER TIMEOUT (pid:8)     -> /analyze
    16:59:34 [CRITICAL] WORKER TIMEOUT (pid:3365)  -> /analyze

Os dois que "falharam" tinham gravado **22 torneios**. A tela disse que falhou o que deu certo,
e ele reenviou achando que havia perdido tudo. Sobrou um registro com cabeçalho e sem decisão
(o worker morreu 0,4 s depois do commit do torneio).

── A medição que fechou o desenho ────────────────────────────────────────────────────────────

O arquivo real dele, 3,1 MB e 18 torneios, pela rota pública, em conta VAZIA:

    homologação (Postgres no mesmo host) .....  36,1 s  →  1,9 s por torneio
    PRODUÇÃO    (Neon remoto) ................ 117,4 s  →  6,2 s por torneio   (fator 3,3x)

Passou por 2,6 s dos 120 s do gunicorn. O custo é dominado por rede: **311 viagens ao banco**
por torneio de 123 decisões, a **8,10 ms** cada. Agrupar as maiores economiza ~1,2 s por
torneio, o que levaria 117 s para ~96 s: **não compra segurança**. Por isso o conserto é sair
da requisição, e não otimizar dentro dela.

── O que este arquivo defende ────────────────────────────────────────────────────────────────

1. Que erro de FORMATO continua síncrono (o jogador precisa saber já que arrastou o arquivo
   errado) e que erro de PROCESSAMENTO não derruba a requisição.
2. Que o arquivo de **Tournament Summary** segue pelo caminho síncrono de sempre. A primeira
   versão deste código o recusava com 422, porque summary não é hand history -- regressão que
   eu ia entregar.
3. Que o mesmo arquivo do mesmo jogador devolve o MESMO recibo, e o de outro jogador não.
4. Que o worker processa e que o recibo conta certo o que entrou, o que já estava e o que falhou.
5. Que os bytes são apagados ao concluir, e que o recibo de um jogador não é legível por outro.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from leaklab.recepcao_de_upload import (CONCLUIDO, PROCESSANDO, RECEBIDO,        # noqa: E402
                                        _stmts, parece_hand_history)

from test_arquivo_com_varios_torneios import UID, banco_de_teste                 # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _um_torneio():
    import io
    return io.open(os.path.join(_FIX, 'revalidation_mini.txt'), encoding='utf-8').read()


# ══════════════════════════════════════════════════════════════════════════════════════════
# 1) A peneira de formato, que é o que fica síncrono
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_reconhece_os_dialetos_do_acervo():
    """Barata de propósito: uma regex, não o parse. Parsear 3,1 MB custa 9 s, e pagar isso na
    requisição era metade do problema desta frente."""
    assert parece_hand_history(_um_torneio()) is True
    for molde in ('PokerStars Hand #1: Tournament #2',
                  'PokerStars Zoom Hand #1: ',
                  'Game Hand #99 - Tournament',
                  '***** Hand History for Game 1 *****',
                  'Tourney Texas Holdem Game Table (NL)',
                  '#Game No : 123456'):
        assert parece_hand_history(molde) is True, molde


def test_recusa_o_que_nao_e_hand_history():
    """O outro lado. Sem ele, uma peneira que aceitasse tudo passaria nos casos de cima e a
    tela voltaria a aceitar qualquer arquivo para falhar depois, calada."""
    for lixo in ('', None, 'planilha,de,resultados\n1,2,3',
                 'Lorem ipsum dolor sit amet', '{"json": "qualquer"}'):
        assert parece_hand_history(lixo) is False, repr(lixo)


def test_a_ddl_existe_nas_DUAS_gramaticas():
    """Postgres e SQLite, testável sem servidor (padrão da casa). O que quebra aqui só apareceria
    no deploy, e a coluna que falta num dos dois é o defeito clássico desta base."""
    for pg in (True, False):
        sql = ' '.join(_stmts(pg))
        assert 'uploads_recebidos' in sql
        for col in ('user_id', 'sha256', 'conteudo', 'status', 'tentativas',
                    'torneios_no_arquivo', 'torneios_gravados', 'torneios_ja_estavam',
                    'torneios_com_erro', 'detalhe', 'erro', 'iniciado_em'):
            assert col in sql, (pg, col)
        assert 'UNIQUE (user_id, sha256)' in sql, pg      # a idempotência mora no BANCO
    assert 'SERIAL' in _stmts(True)[0]
    assert 'AUTOINCREMENT' in _stmts(False)[0]


# ══════════════════════════════════════════════════════════════════════════════════════════
# 2) A rota que recebe
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_recebe_e_devolve_recibo_sem_processar():
    with banco_de_teste() as (cliente, headers):
        r = cliente.post('/uploads', json={'content': _um_torneio(), 'filename': 'a.txt'},
                         headers=headers)
        assert r.status_code == 202, (r.status_code, r.get_data(as_text=True)[:200])
        j = r.get_json()
        assert j['recibo'] and j['status'] == RECEBIDO and j['repetido'] is False
        # e NADA foi importado ainda: é isso que tira o processamento da requisição
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn()
        n = dict(c.execute(_adapt(
            "SELECT COUNT(*) AS n FROM tournaments WHERE user_id=?"), (UID,)).fetchone())['n']
        c.close()
        assert n == 0, 'a rota processou o arquivo em vez de só recebê-lo'


def test_arquivo_que_nao_e_hand_history_falha_NA_HORA():
    """Erro de formato é síncrono de propósito: aceitar para recusar depois faria o jogador
    esperar para descobrir que arrastou o arquivo errado."""
    with banco_de_teste() as (cliente, headers):
        r = cliente.post('/uploads', json={'content': 'isto nao e nada', 'filename': 'x.txt'},
                         headers=headers)
        assert r.status_code == 422, r.status_code
        assert 'histórico de mãos' in (r.get_json() or {}).get('error', '')


def test_o_mesmo_arquivo_devolve_o_MESMO_recibo():
    """A idempotência que teria evitado a confusão do incidente: ele rearrastou e criou trabalho
    novo em vez de acompanhar o que já estava em curso."""
    with banco_de_teste() as (cliente, headers):
        texto = _um_torneio()
        a = cliente.post('/uploads', json={'content': texto}, headers=headers).get_json()
        b = cliente.post('/uploads', json={'content': texto}, headers=headers).get_json()
        assert a['recibo'] == b['recibo'], (a, b)
        assert a['repetido'] is False and b['repetido'] is True


def test_arquivo_DIFERENTE_cria_recibo_novo():
    """O controle do caso acima. Sem ele, uma idempotência que devolvesse sempre o primeiro
    recibo passaria no teste anterior e engoliria todo upload seguinte do jogador."""
    with banco_de_teste() as (cliente, headers):
        a = cliente.post('/uploads', json={'content': _um_torneio()},
                         headers=headers).get_json()
        b = cliente.post('/uploads', json={'content': _um_torneio() + '\n\n'},
                         headers=headers).get_json()
        assert a['recibo'] != b['recibo']


def test_o_summary_continua_SINCRONO():
    """Regressão que eu ia entregar: summary não é hand history, então a peneira o recusava com
    422. Ele não tem mãos para analisar, só atualiza colocação e prêmio de um torneio que já
    está lá, e a tela tem um ramo próprio (`kind === 'summary'`) que dependia disso."""
    with banco_de_teste() as (cliente, headers):
        summary = ('PokerStars Tournament #99887766, No Limit Hold\'em\n'
                   'Buy-In: $0.85/$0.15 USD\n9 players\n'
                   'Total Prize Pool: $7.65 USD\n'
                   'Tournament started 2026/09/07 21:00:00 ET\n'
                   '  1: alguem (Brazil), $3.00 (39.22%)\n'
                   'You finished in 2nd place.\n')
        r = cliente.post('/uploads', json={'content': summary, 'filename': 'TS.txt'},
                         headers=headers)
        j = r.get_json() or {}
        assert j.get('kind') == 'summary', (r.status_code, j)
        assert r.status_code != 422, 'o summary caiu na peneira de hand history'


def test_o_recibo_de_um_jogador_nao_e_legivel_por_outro():
    with banco_de_teste() as (cliente, headers):
        rid = cliente.post('/uploads', json={'content': _um_torneio()},
                           headers=headers).get_json()['recibo']
        from database.auth import generate_token
        outro = {'Authorization': 'Bearer ' + generate_token(UID + 1, 'player')}
        assert cliente.get('/uploads/%d' % rid, headers=headers).status_code == 200
        # NAO afirmo o codigo exato: com o outro usuario inexistente o `require_auth` devolve
        # 401, e com ele existente a rota devolve 404. O que este guarda defende e que ele NAO
        # LE o recibo; cravar 404 fazia o caso falhar por um detalhe do harness em vez de por
        # vazamento.
        r_outro = cliente.get('/uploads/%d' % rid, headers=outro)
        assert r_outro.status_code != 200, r_outro.status_code
        assert 'recibo' not in (r_outro.get_data(as_text=True) or '').lower() or                r_outro.status_code in (401, 403, 404), r_outro.get_data(as_text=True)[:120]


# ══════════════════════════════════════════════════════════════════════════════════════════
# 3) O worker, que é quem processa
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_o_worker_processa_e_o_recibo_conta_certo():
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        rid = cliente.post('/uploads', json={'content': _um_torneio(), 'filename': 'a.txt'},
                           headers=headers).get_json()['recibo']
        res = A._processar_uploads_recebidos()
        assert res.get('recibo') == rid, res
        assert res.get('gravados') == 1, res

        d = cliente.get('/uploads/%d' % rid, headers=headers).get_json()
        assert d['status'] == CONCLUIDO, d
        assert d['torneios_gravados'] == 1 and d['torneios_com_erro'] == 0, d
        assert d['torneios_no_arquivo'] == 1, d
        assert isinstance(d.get('detalhe'), list) and len(d['detalhe']) == 1, d
        # `analysis_waitlisted` viaja: sem ele a frase da fila de análise desaparece calada, e
        # foi o guarda de fiação do front que pegou isso.
        assert 'analysis_waitlisted' in d['detalhe'][0], d['detalhe'][0]

        # e o torneio ENTROU de verdade
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn()
        n = dict(c.execute(_adapt(
            "SELECT COUNT(*) AS n FROM tournaments WHERE user_id=?"), (UID,)).fetchone())['n']
        nd = dict(c.execute(_adapt(
            "SELECT COUNT(*) AS n FROM decisions d JOIN tournaments t ON t.id=d.tournament_id "
            "WHERE t.user_id=?"), (UID,)).fetchone())['n']
        c.close()
        assert n == 1 and nd > 0, (n, nd)


def test_os_bytes_sao_apagados_ao_concluir():
    """Sem isto o banco guardaria duas vezes o mesmo texto, porque cada torneio processado já
    grava o seu em `tournaments.raw_text`."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        rid = cliente.post('/uploads', json={'content': _um_torneio()},
                           headers=headers).get_json()['recibo']
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn()
        antes = dict(c.execute(_adapt(
            "SELECT conteudo FROM uploads_recebidos WHERE id=?"), (rid,)).fetchone())
        c.close()
        assert antes['conteudo'], 'o conteúdo não foi guardado, então nada disto funciona'

        A._processar_uploads_recebidos()
        c = get_conn()
        depois = dict(c.execute(_adapt(
            "SELECT conteudo FROM uploads_recebidos WHERE id=?"), (rid,)).fetchone())
        c.close()
        assert depois['conteudo'] is None, 'os bytes ficaram no banco depois de concluir'


def test_fila_vazia_nao_faz_nada():
    with banco_de_teste():
        import api.app as A
        assert A._processar_uploads_recebidos() == {'recibo': None}


def test_arquivo_ilegivel_vira_ERRO_no_recibo_e_nao_na_requisicao():
    """O molde de sala está lá mas o conteúdo não produz mão nenhuma. A requisição já respondeu
    202 e o jogador não precisa reenviar: o arquivo está guardado e o motivo vai para o recibo."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        # passa pela peneira (tem o cabeçalho) e não produz mão
        texto = 'PokerStars Hand #1: Tournament #2, isto termina aqui e nao tem mesa\n'
        r = cliente.post('/uploads', json={'content': texto}, headers=headers)
        assert r.status_code == 202, r.status_code
        rid = r.get_json()['recibo']
        A._processar_uploads_recebidos()
        d = cliente.get('/uploads/%d' % rid, headers=headers).get_json()
        assert d['status'] == 'erro', d
        assert d['erro'], 'o recibo não diz o motivo'
        assert d['torneios_gravados'] == 0, d


def test_os_pendentes_voltam_na_lista():
    """Serve o F5: a fila do upload reaparece em vez de o jogador achar que o arquivo se perdeu.
    Recibo concluído NÃO entra, senão a lista cresceria para sempre."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        rid = cliente.post('/uploads', json={'content': _um_torneio()},
                           headers=headers).get_json()['recibo']
        pend = cliente.get('/uploads', headers=headers).get_json()['recibos']
        assert [p['id'] for p in pend] == [rid], pend
        A._processar_uploads_recebidos()
        pend2 = cliente.get('/uploads', headers=headers).get_json()['recibos']
        assert pend2 == [], pend2


def test_travado_volta_para_a_fila_e_o_batimento_impede_roubo():
    """Worker morto não pode prender o arquivo de alguém para sempre. E quem está VIVO mantém a
    própria vez: sem o batimento, um arquivo de 100 torneios (que passa dos 15 min) seria
    devolvido à fila no meio do próprio processamento, com dois passes concorrentes."""
    with banco_de_teste() as (cliente, headers):
        from leaklab import recepcao_de_upload as R
        from database.schema import get_conn
        from database.repositories import _adapt
        rid = cliente.post('/uploads', json={'content': _um_torneio()},
                           headers=headers).get_json()['recibo']
        assert R.reivindicar()['id'] == rid
        assert R.reivindicar() is None, 'reivindicou duas vezes o mesmo recibo'

        # envelhece a reivindicação à mão e confirma que ela volta
        c = get_conn()
        c.execute(_adapt("UPDATE uploads_recebidos SET iniciado_em=? WHERE id=?"),
                  ('2020-01-01 00:00:00', rid))
        c.commit(); c.close()
        assert R.devolver_travados() >= 1
        assert R.reivindicar()['id'] == rid, 'o recibo travado não voltou para a fila'

        # agora o batimento: renovado, ele NÃO pode ser devolvido
        R.tocar(rid)
        c = get_conn()
        st = dict(c.execute(_adapt(
            "SELECT status FROM uploads_recebidos WHERE id=?"), (rid,)).fetchone())['status']
        c.close()
        assert st == PROCESSANDO
        assert R.devolver_travados() == 0, 'o batimento não protegeu quem está vivo'


# ══════════════════════════════════════════════════════════════════════════════════════════
# 4) A COTA do mes: o que excede fica guardado, e entram os MAIS RECENTES
# ══════════════════════════════════════════════════════════════════════════════════════════

def _cinco_torneios_datados():
    """Cinco torneios do mesmo fixture, de MAIO a SETEMBRO.

    Datas diferentes de proposito: sem elas o teste provaria que tres entraram, mas nao que
    entraram os tres que o dono pediu. Construido do fixture real porque mao forjada a mao nao
    passa pelo parser, e um teste que nao passa pelo parser nao prova nada sobre o dialeto.
    """
    import io as _io
    import re as _re
    raw = _io.open(os.path.join(_FIX, 'revalidation_mini.txt'), encoding='utf-8').read()
    blocos = [b for b in _re.split(r'(?=PokerStars Hand #)', raw) if b.strip()]
    partes = []
    for i, dia in enumerate(['2026/05/10', '2026/06/11', '2026/07/12',
                             '2026/08/13', '2026/09/14']):
        novo = []
        for b in blocos:
            b2 = _re.sub(r'Tournament #\d+', 'Tournament #6660%d' % i, b)
            b2 = _re.sub(r'PokerStars Hand #(\d+)',
                         lambda m: 'PokerStars Hand #%d%s' % (i + 1, m.group(1)), b2)
            b2 = _re.sub(r'\d{4}/\d{2}/\d{2}', dia, b2)
            novo.append(b2)
        partes.append(''.join(novo))
    return chr(10).join(partes)


def _teto(conn, valor):
    from database.repositories import _adapt as _a
    conn.execute(_a("UPDATE users SET tournaments_limit_override=? WHERE id=?"), (valor, UID))
    conn.commit()


def test_cota_estourada_GUARDA_o_resto_em_vez_de_perder():
    """Medido ANTES deste tratamento, com teto de 3 e arquivo de 5: o recibo dizia `concluido`
    com "2 com erro" e os bytes eram APAGADOS. O jogador lia que algo quebrou (nao quebrou, ele
    bateu o teto) e perdia dois torneios, tendo que lembrar de reenviar no mes seguinte."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn(); _teto(c, 3); c.close()

        rid = cliente.post('/uploads', json={'content': _cinco_torneios_datados()},
                           headers=headers).get_json()['recibo']
        A._processar_uploads_recebidos()
        d = cliente.get('/uploads/%d' % rid, headers=headers).get_json()

        assert d['status'] == 'aguardando_cota', d['status']
        assert d['torneios_gravados'] == 3, d
        assert d['torneios_com_erro'] == 0, ('cota virou "erro" de novo', d)
        # o total e o do arquivo ORIGINAL: sem isto a tela passaria de "3 de 5" para "3 de 2"
        assert d['torneios_no_arquivo'] == 5, d
        # e o que falta continua GUARDADO
        c = get_conn()
        g = dict(c.execute(_adapt(
            "SELECT conteudo FROM uploads_recebidos WHERE id=?"), (rid,)).fetchone())
        c.close()
        assert g['conteudo'], 'os torneios que faltam foram perdidos'


def test_entram_os_MAIS_RECENTES():
    """A decisao do dono. Antes entravam os tres PRIMEIROS do arquivo, que e a ordem do export
    e nao a do calendario: o jogador ficava com o que a ferramenta dele escreveu primeiro, em
    vez das sessoes que ele acabou de jogar."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn(); _teto(c, 3); c.close()

        cliente.post('/uploads', json={'content': _cinco_torneios_datados()}, headers=headers)
        A._processar_uploads_recebidos()

        c = get_conn()
        entraram = [dict(r)['tournament_id'] for r in c.execute(_adapt(
            "SELECT tournament_id FROM tournaments WHERE user_id=? ORDER BY played_at DESC"),
            (UID,)).fetchall()]
        c.close()
        # setembro, agosto e julho; maio e junho esperam
        assert entraram == ['66604', '66603', '66602'], entraram


def test_quando_a_cota_VIRA_o_resto_entra_e_os_contadores_ACUMULAM():
    """E o recibo tem de bater com a conta. Na primeira versao os contadores reiniciavam na
    retomada e a tela dizia "2 de 5" com os 5 torneios ja na conta."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn(); _teto(c, 3); c.close()

        rid = cliente.post('/uploads', json={'content': _cinco_torneios_datados()},
                           headers=headers).get_json()['recibo']
        A._processar_uploads_recebidos()

        # a cota vira (o reset e preguicoso na leitura: basta o mes gravado ser outro)
        c = get_conn()
        c.execute(_adapt("UPDATE users SET quota_reset_at=? WHERE id=?"), ('2020-01-01', UID))
        c.commit(); c.close()

        A._processar_uploads_recebidos()
        d = cliente.get('/uploads/%d' % rid, headers=headers).get_json()
        assert d['status'] == CONCLUIDO, d
        assert d['torneios_gravados'] == 5, ('os contadores nao acumularam', d)
        assert len(d['detalhe']) == 5, ('o detalhe nao acumulou', len(d['detalhe']))

        c = get_conn()
        n = dict(c.execute(_adapt(
            "SELECT COUNT(*) AS n FROM tournaments WHERE user_id=?"), (UID,)).fetchone())['n']
        g = dict(c.execute(_adapt(
            "SELECT conteudo FROM uploads_recebidos WHERE id=?"), (rid,)).fetchone())
        c.close()
        assert n == 5 and d['torneios_gravados'] == n, (n, d['torneios_gravados'])
        assert g['conteudo'] is None, 'os bytes ficaram depois de concluir'


def test_quem_NAO_tem_teto_nao_e_afetado():
    """O controle. Sem ele, um tratamento que pausasse sempre passaria nos casos acima e
    pararia o upload de todo Pro no meio do arquivo."""
    with banco_de_teste() as (cliente, headers):
        import api.app as A
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn()
        # `coach` e o plano SEM teto (`tournaments=None`) -- conferido em PLAN_LIMITS. A 1a
        # versao usou 'unlimited', que nao existe: `PLAN_LIMITS.get(plan, PLAN_LIMITS['free'])`
        # cai em FREE, cujo teto e 30, e o teste media o oposto do que pretendia. Passou em
        # SQLite por sorte (banco novo, contador zerado) e caiu no Postgres.
        c.execute(_adapt("UPDATE users SET plan=?, tournaments_limit_override=NULL WHERE id=?"),
                  ('coach', UID))
        c.commit(); c.close()

        rid = cliente.post('/uploads', json={'content': _cinco_torneios_datados()},
                           headers=headers).get_json()['recibo']
        A._processar_uploads_recebidos()
        d = cliente.get('/uploads/%d' % rid, headers=headers).get_json()
        assert d['status'] == CONCLUIDO, d
        assert d['torneios_gravados'] == 5, d


def test_a_espera_tem_TETO_por_jogador():
    """Aceitar e guardar e o que da valor, mas sem teto um Free empilharia arquivo sem limite e
    nos pagariamos o armazenamento. Mesmo espirito do `max_pending_solves` dos planos."""
    with banco_de_teste() as (cliente, headers):
        from leaklab.recepcao_de_upload import (AGUARDANDO_COTA, ESPERA_MAX_POR_USUARIO,
                                                em_espera_por_cota)
        from database.schema import get_conn
        from database.repositories import _adapt
        c = get_conn()
        for k in range(ESPERA_MAX_POR_USUARIO):
            c.execute(_adapt(
                "INSERT INTO uploads_recebidos (user_id, sha256, bytes_total, conteudo, status) "
                "VALUES (?,?,?,?,?)"), (UID, 'falso%d' % k, 10, 'x', AGUARDANDO_COTA))
        c.commit(); c.close()
        assert em_espera_por_cota(UID) == ESPERA_MAX_POR_USUARIO

        r = cliente.post('/uploads', json={'content': _um_torneio()}, headers=headers)
        assert r.status_code == 429, r.status_code
        assert (r.get_json() or {}).get('espera_cheia') is True, r.get_json()


def _recibo_falso(c, k, status, n_bytes):
    from database.repositories import _adapt
    c.execute(_adapt(
        "INSERT INTO uploads_recebidos (user_id, sha256, bytes_total, conteudo, status) "
        "VALUES (?,?,?,?,?)"), (UID, 'bytes%s%d' % (status, k), n_bytes, 'x', status))


def test_os_bytes_em_aberto_tem_TETO_por_jogador():
    """Auditoria SEG-2/SEG-3 (15/09): o teto de arquivos so ve `aguardando_cota`, que o worker
    atribui DEPOIS do POST. Em rajada 20 arquivos entraram com teto 5, e 10 POSTs de 4,5 MB
    guardaram 45 MB de um free. O freio que vale e em bytes, sobre tudo que ainda esta guardado."""
    with banco_de_teste() as (cliente, headers):
        from leaklab.recepcao_de_upload import (AGUARDANDO_COTA, BYTES_EM_ABERTO_MAX_POR_USUARIO,
                                                PROCESSANDO, RECEBIDO, bytes_em_aberto)
        from database.schema import get_conn
        arquivo = _um_torneio()
        n_arquivo = len(arquivo.encode('utf-8'))
        c = get_conn()
        # Tres estados em aberto somam ate faltar menos que um arquivo para o teto.
        fatia = (BYTES_EM_ABERTO_MAX_POR_USUARIO - n_arquivo + 1) // 3
        _recibo_falso(c, 1, RECEBIDO, fatia)
        _recibo_falso(c, 2, PROCESSANDO, fatia)
        _recibo_falso(c, 3, AGUARDANDO_COTA, fatia)
        c.commit(); c.close()
        em_aberto = bytes_em_aberto(UID)
        assert em_aberto == 3 * fatia, em_aberto
        assert em_aberto + n_arquivo > BYTES_EM_ABERTO_MAX_POR_USUARIO

        r = cliente.post('/uploads', json={'content': arquivo}, headers=headers)
        assert r.status_code == 429, (r.status_code, r.get_json())
        j = r.get_json() or {}
        assert j.get('code') == 'upload_bytes_em_aberto', j
        assert j.get('bytes_em_aberto') == em_aberto and j.get('teto_bytes') == BYTES_EM_ABERTO_MAX_POR_USUARIO
        assert 'envie este arquivo de novo' in j.get('error', ''), j
        assert bytes_em_aberto(UID) == em_aberto, 'a recusa gravou o arquivo'


def test_bytes_concluidos_NAO_contam_no_teto():
    """O outro lado: um jogador com um historico enorme JA importado nao pode ficar barrado.
    `concluido` e `erro` zeram o conteudo; so `bytes_total` fica como registro."""
    with banco_de_teste() as (cliente, headers):
        from leaklab.recepcao_de_upload import (BYTES_EM_ABERTO_MAX_POR_USUARIO, CONCLUIDO,
                                                ERRO, RECEBIDO, bytes_em_aberto)
        from database.schema import get_conn
        c = get_conn()
        _recibo_falso(c, 1, CONCLUIDO, 3 * BYTES_EM_ABERTO_MAX_POR_USUARIO)
        _recibo_falso(c, 2, ERRO, 3 * BYTES_EM_ABERTO_MAX_POR_USUARIO)
        c.commit(); c.close()
        assert bytes_em_aberto(UID) == 0

        r = cliente.post('/uploads', json={'content': _um_torneio()}, headers=headers)
        assert r.status_code == 202, (r.status_code, r.get_json())
        assert (r.get_json() or {}).get('status') == RECEBIDO
        assert bytes_em_aberto(UID) == len(_um_torneio().encode('utf-8'))


def test_o_teto_de_bytes_segura_a_RAJADA():
    """O caso que o teto de arquivos deixava passar: varios POSTs antes de o worker rodar. Cada
    arquivo diferente entra em `recebido` e soma; o que passar do teto e recusado NA HORA."""
    with banco_de_teste() as (cliente, headers):
        from leaklab.recepcao_de_upload import BYTES_EM_ABERTO_MAX_POR_USUARIO, bytes_em_aberto
        base = _um_torneio()
        n = len(base.encode('utf-8'))
        cabem = BYTES_EM_ABERTO_MAX_POR_USUARIO // n
        # Encurta a rajada: enche quase tudo com UM recibo falso e manda 4 arquivos distintos.
        from database.schema import get_conn
        c = get_conn()
        _recibo_falso(c, 1, 'recebido', (cabem - 2) * n)
        c.commit(); c.close()
        codigos = []
        for k in range(4):
            corpo = base.replace('Tournament #', 'Tournament #%d' % (7000 + k))
            r = cliente.post('/uploads', json={'content': corpo, 'filename': 'r%d.txt' % k},
                             headers=headers)
            codigos.append(r.status_code)
        assert codigos == [202, 202, 429, 429], codigos
        assert bytes_em_aberto(UID) <= BYTES_EM_ABERTO_MAX_POR_USUARIO


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
