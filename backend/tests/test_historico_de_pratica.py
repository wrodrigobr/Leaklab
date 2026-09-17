# -*- coding: utf-8 -*-
"""O historico das maos praticadas, e o relatorio sobre ele.

Pedido do dono (16/09): "seria interessante armazenar este treino, para ficar no historico das
ultimas maos treinadas, e ter a possibilidade de gerar um relatorio como o do gto wizard".

O que estes casos protegem, e por que cada um existe:

1. O veredito gravado e o do SERVIDOR. Aceitar o do cliente faria o relatorio adulteravel, e
   recalcular aqui criaria a segunda implementacao da regua (regra 5).
2. Mao sem veredito NAO e espalhada nos quatro niveis. Contar como erro inventa acusacao, como
   acerto inventa merito, e as duas mentem no numero que o jogador usa para medir evolucao.
3. A taxa de acerto e sobre as maos JULGADAS. Dividir pelo total faria a taxa cair quando o
   solver nao respondeu, o que nao e culpa nem merito de quem treina.
4. Gravar nunca derruba a resposta do treino.
5. A exclusao de usuario leva o historico. A tabela `uploads_recebidos` ficou fora daquela lista
   e o achado e de ontem: usuario excluido deixava recibo orfao.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_SECRET', 'dev_local_apenas_para_testes_0000000000000000')

UID = 918273


def banco_de_teste():
    """SQLite descartavel, ou o Postgres do ambiente quando ele esta la.

    Nao impoe backend pelo motivo que `test_arquivo_com_varios_torneios` documenta: `USE_POSTGRES`
    e constante de modulo avaliada na importacao, e forcar SQLite com o Postgres ja importado faz
    o `_adapt` continuar trocando `?` por `%s`.
    """
    import importlib
    import tempfile
    if not os.environ.get('DATABASE_URL'):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        os.environ['LEAKLAB_DB'] = tmp.name
        from database import schema as _schema
        importlib.reload(_schema)
        _schema.init_db()
    from leaklab import historico_de_pratica as H
    importlib.reload(H)
    H.apagar_do_jogador(UID)
    return H


def _grade(nivel, ev=0.5, freq=None, melhor='jam'):
    return {'nivel': nivel, 'ev_loss_bb': ev, 'best_action': melhor,
            'hand_freq': freq if freq is not None else {'fold': 0.0, 'allin': 1.0}}


SPOT = {'position': 'SB', 'hand': '96s', 'stack_bb': 10, 'scenario': 'rfi', 'facing_size': 0,
        'is_3bet_pot': False}


def test_grava_e_lista_do_mais_recente_para_o_mais_antigo():
    H = banco_de_teste()
    for i, acao in enumerate(('call', 'allin', 'fold')):
        H.gravar(UID, dict(SPOT, hand='96s' if i else 'AKs'), acao, _grade('errada'))
    maos = H.ultimas(UID)
    assert len(maos) == 3, maos
    assert [m['acao'] for m in maos] == ['fold', 'allin', 'call'], [m['acao'] for m in maos]
    # e os campos que a tabela do relatorio mostra chegaram
    m = maos[-1]
    assert m['posicao'] == 'SB' and m['cenario'] == 'rfi' and m['acao_gto'] == 'jam', m
    assert m['stack_bb'] == 10, m
    assert m['resumo'], 'o resumo do spot alimenta a coluna de contexto'


def test_a_pagina_seguinte_nao_repete_nem_pula():
    """Keyset e nao OFFSET: o jogador pode estar praticando enquanto olha o historico, e com
    OFFSET cada mao nova empurra a lista e a pagina 2 repete o que a pagina 1 ja mostrou."""
    H = banco_de_teste()
    for i in range(10):
        H.gravar(UID, dict(SPOT, hand='h%d' % i), 'fold', _grade('errada'))

    p1 = H.ultimas(UID, limite=4)
    # chega uma mao NOVA entre as duas paginas, como aconteceria de verdade
    H.gravar(UID, dict(SPOT, hand='nova'), 'fold', _grade('errada'))
    p2 = H.ultimas(UID, limite=4, desde_id=p1[-1]['id'])

    ids1 = [m['id'] for m in p1]
    ids2 = [m['id'] for m in p2]
    assert not set(ids1) & set(ids2), 'a pagina 2 repetiu linha da pagina 1: %s / %s' % (ids1, ids2)
    assert max(ids2) < min(ids1), 'a pagina 2 tem de continuar de onde a 1 parou'
    # e a mao nova nao se intromete no meio da paginacao
    assert 'nova' not in [m['mao'] for m in p2]

    # CONTIGUIDADE, e nao so "vem depois". Sem estes dois asserts o guarda passava VERDE com a
    # pagina 2 ordenada ao contrario (`ORDER BY id ASC`): ela trazia as quatro maos MAIS ANTIGAS,
    # que tambem sao menores que as da pagina 1 e tambem nao repetem -- e o jogador perdia as maos
    # do meio sem nenhum sinal. Verificado quebrando de proposito.
    assert ids1 == sorted(ids1, reverse=True), ids1
    assert ids2 == sorted(ids2, reverse=True), ids2
    assert ids2[0] == ids1[-1] - 1, (
        'a pagina 2 comeca em %s e a 1 terminou em %s: %s maos ficaram no vao'
        % (ids2[0], ids1[-1], ids1[-1] - 1 - ids2[0]))


def test_mao_SEM_veredito_fica_fora_dos_niveis():
    H = banco_de_teste()
    H.gravar(UID, SPOT, 'fold', _grade('correta', ev=0.0))
    H.gravar(UID, SPOT, 'call', _grade(None, ev=None, freq={}))     # o solver nao respondeu

    maos = H.ultimas(UID)
    assert maos[0]['nivel'] is None, 'sem veredito nao se grava chute'

    r = H.relatorio(UID)
    assert r['maos'] == 2
    assert r['julgadas'] == 1
    assert r['sem_avaliacao'] == 1
    assert sum(r['por_nivel'].values()) == 1, r['por_nivel']
    # a taxa de acerto e sobre as JULGADAS: 1 de 1, e nao 1 de 2
    assert r['acerto'] == 100.0, r['acerto']


def test_o_relatorio_soma_o_custo_e_corta_por_posicao_e_cenario():
    H = banco_de_teste()
    H.gravar(UID, dict(SPOT, position='SB', scenario='rfi'), 'call', _grade('errada', ev=0.5))
    H.gravar(UID, dict(SPOT, position='BTN', scenario='rfi'), 'fold', _grade('grave', ev=4.0))
    H.gravar(UID, dict(SPOT, position='BTN', scenario='vs_rfi'), 'raise', _grade('correta', ev=0.0))

    r = H.relatorio(UID)
    assert r['bb_perdidos'] == 4.5, r['bb_perdidos']
    assert r['por_nivel'] == {'correta': 1, 'imprecisao': 0, 'errada': 1, 'grave': 1}, r['por_nivel']
    assert r['por_posicao']['BTN']['maos'] == 2
    assert r['por_posicao']['BTN']['corretas'] == 1
    assert r['por_posicao']['SB']['bb'] == 0.5
    assert r['por_cenario']['rfi']['maos'] == 2
    assert r['por_cenario']['vs_rfi']['corretas'] == 1
    assert r['bb_por_mao'] == round(4.5 / 3, 3), r['bb_por_mao']


def test_o_custo_NEGATIVO_entra_como_perda():
    """O motor pode devolver o custo com sinal, e a tela mostra "-0,03bb". Somar o sinal cru faria
    duas maos ruins se cancelarem e o relatorio dizer que a sessao nao custou nada."""
    H = banco_de_teste()
    H.gravar(UID, SPOT, 'call', _grade('errada', ev=-1.5))
    H.gravar(UID, SPOT, 'fold', _grade('errada', ev=1.5))
    assert H.relatorio(UID)['bb_perdidos'] == 3.0


def test_a_frequencia_da_acao_DELE_e_gravada_no_vocabulario_do_no():
    """`hand_freq` vem com o codigo do solver (`F`, `R2.5`, `RAI`) e a acao com o nome. Sem a
    normalizacao, a coluna diria 0% para toda mao certa -- e o relatorio inteiro mentiria."""
    H = banco_de_teste()
    H.gravar(UID, SPOT, 'raise', {'nivel': 'correta', 'ev_loss_bb': 0.0,
                                  'hand_freq': {'F': 0.2, 'R2.5': 0.8}})
    m = H.ultimas(UID)[0]
    assert m['freq_da_acao'] == 0.8, m['freq_da_acao']
    assert m['freq_melhor'] == 0.8, m['freq_melhor']

    H.gravar(UID, SPOT, 'allin', {'nivel': 'errada', 'ev_loss_bb': 1.0,
                                  'hand_freq': {'F': 0.9, 'RAI': 0.1}})
    m2 = H.ultimas(UID)[0]
    assert m2['freq_da_acao'] == 0.1 and m2['freq_melhor'] == 0.9, m2


def test_gravar_NAO_derruba_a_resposta_do_treino():
    """O jogador esta com quatro mesas abertas. Perder a resposta dele porque o historico falhou
    seria trocar um recurso novo pelo que ja funcionava."""
    H = banco_de_teste()
    import leaklab.historico_de_pratica as mod

    original = mod.get_conn

    def explode():
        raise RuntimeError('banco fora')

    mod.get_conn = explode
    try:
        try:
            r = H.gravar(UID, SPOT, 'fold', _grade('errada'))
            assert r is None, r
        except RuntimeError:
            raise AssertionError('gravar levantou em vez de devolver None')
    finally:
        mod.get_conn = original


def test_o_DDL_existe_nas_DUAS_gramaticas():
    """A casa ja pagou INSERT que falhava SO no Postgres. As duas versoes precisam declarar as
    MESMAS colunas, senao o relatorio funciona em dev e quebra em producao."""
    H = banco_de_teste()
    import re
    pg = ' '.join(H._stmts(True))
    lite = ' '.join(H._stmts(False))
    assert 'SERIAL' in pg and 'AUTOINCREMENT' in lite

    def colunas(ddl):
        corpo = ddl[ddl.index('pratica_maos ('):]
        return set(re.findall(r'^\s{0,40}([a-z_]+)\s+(?:TEXT|REAL|INTEGER|TIMESTAMP|SERIAL)',
                              corpo, re.M))

    cols_pg, cols_lite = colunas(pg), colunas(lite)
    # CONTROLE: sem isto um regex furado deixaria os dois conjuntos vazios e IGUAIS
    assert len(cols_pg) >= 10, cols_pg
    assert cols_pg == cols_lite, (cols_pg ^ cols_lite)


def test_a_exclusao_de_usuario_leva_o_historico():
    """A varredura N+1 da regra 5: a tabela tem de estar na lista declarada da exclusao, e nao
    apenas ser apagavel por uma funcao que ninguem chama. `uploads_recebidos` ficou de fora e o
    achado e de 16/09."""
    H = banco_de_teste()
    from leaklab.exclusao_de_usuario import TABELAS_DO_USUARIO
    nomes = [t[0] for t in TABELAS_DO_USUARIO]
    assert 'pratica_maos' in nomes, nomes

    H.gravar(UID, SPOT, 'fold', _grade('errada'))
    assert len(H.ultimas(UID)) == 1
    assert H.apagar_do_jogador(UID) == 1
    assert H.ultimas(UID) == []


def test_o_limite_de_pagina_tem_teto():
    """Pedir 10.000 maos de uma vez e latencia do Neon para uma tabela que ninguem le inteira."""
    H = banco_de_teste()
    for i in range(5):
        H.gravar(UID, dict(SPOT, hand='h%d' % i), 'fold', _grade('errada'))
    assert len(H.ultimas(UID, limite=99999)) == 5
    assert H.LIMITE_MAXIMO <= 500


def test_a_ROTA_do_grade_grava_e_as_rotas_de_leitura_devolvem():
    """Ponta a ponta pela rota, e nao so pela funcao.

    O que este caso protege que os outros nao: que o `/practice/grade` CHAMA o historico. A funcao
    `gravar` podia estar perfeita e ninguem invoca-la -- e o relatorio ficaria vazio para sempre,
    sem nenhum erro em lugar nenhum. A casa tem a cicatriz: uma flag desligada por sete semanas
    porque um comentario dizia que ela ainda nao valia.
    """
    import json as _json
    import os as _os
    import sqlite3
    import tempfile

    if _os.environ.get('DATABASE_URL'):
        return          # a rota carrega o app inteiro; contra Postugres isto e trabalho do host

    banco = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    banco.close()
    _os.environ['LEAKLAB_DB'] = banco.name

    import importlib
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
    cli = app.test_client()

    uid = create_user('qa_hist', 'qa.hist@teste.local', 'SenhaDeTeste!1')
    tok = generate_token(uid, 'player')
    cab = {'Authorization': 'Bearer %s' % tok}

    # o spot do caso do dono: o GTO faz allin 100% e ele limpa
    spot = {'position': 'SB', 'hand': '96s', 'stack_bb': 10, 'scenario': 'rfi',
            'facing_size': 0, 'is_3bet_pot': False}
    r = cli.post('/player/practice/grade', json={'spot': spot, 'action': 'call'}, headers=cab)
    assert r.status_code == 200, r.status_code
    corpo = _json.loads(r.data)
    assert corpo.get('nivel') == 'errada', corpo.get('nivel')
    assert corpo.get('historico_id'), 'a rota nao gravou: o relatorio ficaria vazio para sempre'

    h = _json.loads(cli.get('/player/practice/history', headers=cab).data)
    assert len(h['maos']) == 1, h
    assert h['maos'][0]['mao'] == '96s' and h['maos'][0]['nivel'] == 'errada', h['maos'][0]

    rel = _json.loads(cli.get('/player/practice/report', headers=cab).data)
    assert rel['maos'] == 1 and rel['por_nivel']['errada'] == 1, rel

    # e o veredito gravado e o do SERVIDOR: o que o cliente mandar no corpo e ignorado
    cli.post('/player/practice/grade',
             json={'spot': spot, 'action': 'call', 'nivel': 'correta'}, headers=cab)
    h2 = _json.loads(cli.get('/player/practice/history', headers=cab).data)
    assert h2['maos'][0]['nivel'] == 'errada', (
        'o nivel do cliente entrou no historico: o relatorio seria adulteravel')


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
