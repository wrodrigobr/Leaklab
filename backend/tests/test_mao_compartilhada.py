# -*- coding: utf-8 -*-
"""Compartilhar uma mão: link público, e nenhuma pessoa exposta.

── O que originou (29/08) ──────────────────────────────────────────────────────────────────

Do benchmark: um link que o jogador posta num grupo e quem clica vê o que o GrindLab disse da mão.
É a única coisa deste produto que sai dele.

── Por que estes guardas são mais duros que os outros ──────────────────────────────────────

Em 28/08 uma captura para a landing saiu com os **43 screen names reais** de um torneio — pessoas
que não concordaram em aparecer. Ali era uma imagem, e deu para refazer antes de publicar. **Aqui
é um link que qualquer um abre**, e o dano seria contínuo e fora do nosso alcance.

Por isso a proteção é lista BRANCA e não lista negra: blacklist protege do que alguém lembrou;
whitelist protege do que ainda não existe. Uma coluna nova em `decisions` amanhã não vaza por
esquecimento.

E há uma decisão de desenho que estes testes fixam: **compartilhar é ATO, não derivação.** O
`grind_mode` já tem `token_da_mao`, um hash da mão com o segredo — reusá-lo aqui daria link a TODA
mão sem ninguém decidir, sem registro de quem quis, e sem como revogar.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _banco():
    from database.schema import init_db
    init_db()


def _semeia():
    """Um torneio com uma mão, do usuário A. Devolve (uid_a, uid_b, tid, hid)."""
    import uuid
    from database.repositories import create_user
    from database.schema import get_conn
    from database.repositories import _adapt

    m = uuid.uuid4().hex[:8]
    a = create_user('dono_' + m, 'dono_%s@t.local' % m, 'x' * 12)
    b = create_user('outro_' + m, 'outro_%s@t.local' % m, 'x' * 12)
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, site, hero) VALUES (?,?,?,?)"),
            (a, 'T' + m, 'PokerStars', 'nick_do_dono'))
        tid = dict(conn.execute(_adapt(
            'SELECT id FROM tournaments WHERE tournament_id = ?'), ('T' + m,)).fetchone())['id']
        conn.execute(_adapt(
            "INSERT INTO decisions (tournament_id, hand_id, street, position, vs_position, "
            "hero_cards, action_taken, best_action, label, score) VALUES (?,?,?,?,?,?,?,?,?,?)"),
            (tid, 'H' + m, 'flop', 'BB', 'BTN', 'AhKd', 'call', 'raise', 'small_mistake', 0.5))
        conn.commit()
    finally:
        conn.close()
    return a, b, tid, 'H' + m


def test_o_link_nasce_de_um_ATO_e_e_aleatorio():
    """Dois tokens do mesmo par de mãos diferentes seriam derivação; iguais para a MESMA mão
    do mesmo dono é reuso do link já criado, que é o certo."""
    _banco()
    from leaklab.mao_compartilhada import criar
    a, _b, tid, hid = _semeia()
    t1 = criar(a, tid, hid)
    t2 = criar(a, tid, hid)
    assert t1 and t2 and t1 == t2, 'compartilhar duas vezes criou dois links'
    assert len(t1) >= 20, 'token curto demais para não ser enumerável: %r' % t1
    # E NÃO pode ser o token derivado do grind: aquele existe para toda mão, sem ato nenhum.
    try:
        from leaklab.grind_mode import token_da_mao
        assert t1 != token_da_mao(tid, hid), (
            'o link é o token DERIVADO do grind: toda mão passaria a ter link sem ninguém decidir')
    except ImportError:
        pass
    print('OK  test_o_link_nasce_de_um_ATO_e_e_aleatorio')


def test_so_o_DONO_compartilha():
    """Sem isto, qualquer um publicaria a mão de qualquer um."""
    _banco()
    from leaklab.mao_compartilhada import criar
    a, b, tid, hid = _semeia()
    assert criar(a, tid, hid), 'o dono não conseguiu compartilhar'
    assert criar(b, tid, hid) is None, 'um estranho compartilhou a mão de outro'
    print('OK  test_so_o_DONO_compartilha')


def test_o_payload_NAO_carrega_nick_de_ninguem():
    """O guarda mais importante do arquivo.

    Não confere campo a campo: varre o JSON INTEIRO procurando os nicks semeados. É a diferença
    entre "os campos que eu lembrei estão limpos" e "nada vazou".
    """
    _banco()
    import json
    from leaklab.mao_compartilhada import criar, ler
    a, _b, tid, hid = _semeia()
    bruto = json.dumps(ler(criar(a, tid, hid)), ensure_ascii=False)
    for proibido in ('nick_do_dono', 'PokerStars', str(tid), hid):
        assert proibido not in bruto, (
            'o payload público carrega %r. Em 28/08 uma captura saiu com 43 nicks reais; aqui o '
            'link é aberto e o dano seria contínuo.' % proibido)
    print('OK  test_o_payload_NAO_carrega_nick_de_ninguem')


def test_a_lista_e_BRANCA_e_nao_negra():
    """CONTRAPROVA do teste acima: uma blacklist passaria nele e vazaria a coluna que alguém
    adicionar amanhã. Aqui o payload é comparado contra a whitelist declarada."""
    _banco()
    from leaklab.mao_compartilhada import criar, ler, CAMPOS_PUBLICOS, CAMPOS_PROIBIDOS
    a, _b, tid, hid = _semeia()
    dados = ler(criar(a, tid, hid))
    for passo in dados['passos']:
        fora = set(passo) - CAMPOS_PUBLICOS
        assert not fora, 'campo fora da lista branca no payload: %s' % sorted(fora)
    assert not (CAMPOS_PUBLICOS & CAMPOS_PROIBIDOS), (
        'um campo está nas duas listas: %s' % sorted(CAMPOS_PUBLICOS & CAMPOS_PROIBIDOS))
    print('OK  test_a_lista_e_BRANCA_e_nao_negra (%d campos permitidos)' % len(CAMPOS_PUBLICOS))


def test_o_payload_ENTREGA_o_que_faz_o_link_valer():
    """CONTRAPROVA da anonimização: um payload vazio passaria em tudo acima e não serviria para
    nada. O link existe para mostrar a mão e o veredito."""
    _banco()
    from leaklab.mao_compartilhada import criar, ler
    a, _b, tid, hid = _semeia()
    passo = ler(criar(a, tid, hid))['passos'][0]
    for campo in ('hero_cards', 'position', 'action_taken', 'label'):
        assert passo.get(campo), 'o payload não traz %r: o link não mostra nada' % campo
    print('OK  test_o_payload_ENTREGA_o_que_faz_o_link_valer')


def test_revogar_apaga_o_link():
    """Quem compartilhou tem de poder voltar atrás, e só ele."""
    _banco()
    from leaklab.mao_compartilhada import criar, ler, revogar
    a, b, tid, hid = _semeia()
    token = criar(a, tid, hid)
    assert ler(token), 'o link nasceu morto'
    assert revogar(b, token) is False, 'um estranho revogou o link de outro'
    assert ler(token), 'o link caiu com a revogação de um estranho'
    assert revogar(a, token) is True, 'o dono não conseguiu revogar'
    assert ler(token) is None, 'o link continua vivo depois de revogado'
    print('OK  test_revogar_apaga_o_link')


def test_token_inexistente_devolve_None():
    _banco()
    from leaklab.mao_compartilhada import ler
    assert ler('nao-existe-este-token') is None
    assert ler('') is None
    print('OK  test_token_inexistente_devolve_None')



def test_a_pergunta_do_dono_viaja_no_link():
    """Camada 2: quem compartilha marca a decisão e escreve a dúvida; o link abre nela."""
    _banco()
    from leaklab.mao_compartilhada import criar, ler
    a, _b, tid, hid = _semeia()
    t = criar(a, tid, hid, step_idx=0, pergunta='call ou jam aqui?')
    d = ler(t)
    assert d['pergunta'] == 'call ou jam aqui?' and d['passo_marcado'] == 0
    # Compartilhar de novo ATUALIZA a pergunta no MESMO link (o link é da mão).
    t2 = criar(a, tid, hid, step_idx=0, pergunta='mudei de ideia: e vs jam?')
    assert t2 == t and ler(t)['pergunta'] == 'mudei de ideia: e vs jam?'
    print('OK  test_a_pergunta_do_dono_viaja_no_link')


def test_voto_agrega_e_nao_identifica():
    """Camada 3a: anônimo vota; o gravado é o AGREGADO por ação, nunca quem votou."""
    _banco()
    from leaklab.mao_compartilhada import criar, votar
    a, _b, tid, hid = _semeia()
    t = criar(a, tid, hid)
    votar(t, 'call'); votar(t, 'call')
    placar = votar(t, 'fold')
    assert placar == {'call': 2, 'fold': 1}, placar
    assert votar(t, 'xeque-mate') is None, 'acao fora da whitelist foi aceita'
    assert votar('token-inexistente', 'call') is None
    # O agregado não tem coluna de identidade: conferido na própria tabela.
    from database.schema import get_conn
    from database.repositories import _adapt
    conn = get_conn()
    try:
        cols = [d[0] for d in conn.execute(_adapt(
            'SELECT * FROM shared_hand_votes LIMIT 1')).description]
    finally:
        conn.close()
    assert 'user_id' not in cols and 'ip' not in cols, (
        'a tabela de votos identifica o visitante: %s' % cols)
    print('OK  test_voto_agrega_e_nao_identifica')


def test_comentario_exige_conta_e_assina_username():
    """Camada 3b: comentário tem autor visível (username), e o DONO da mão segue anônimo."""
    _banco()
    import json
    from leaklab.mao_compartilhada import criar, comentar, ler
    a, b, tid, hid = _semeia()
    t = criar(a, tid, hid)
    assert comentar(t, b, 'fold facil, sem odds') is not None
    assert comentar(t, b, '   ') is None, 'comentario vazio foi aceito'
    d = ler(t)
    assert len(d['comentarios']) == 1
    assert d['comentarios'][0]['autor'].startswith('outro_'), 'o autor nao veio assinado'
    # O guarda de anonimato do DONO continua valendo com os comentarios no payload.
    bruto = json.dumps(d, ensure_ascii=False)
    assert 'nick_do_dono' not in bruto and 'dono_' not in bruto, (
        'as camadas novas vazaram a identidade do dono da mao')
    print('OK  test_comentario_exige_conta_e_assina_username')


def test_apagar_comentario_autor_ou_dono():
    """Moderação mínima: o autor apaga o que escreveu; o dono da mão modera a própria página.
    Um terceiro não apaga nada."""
    _banco()
    from leaklab.mao_compartilhada import criar, comentar, apagar_comentario, ler
    a, b, tid, hid = _semeia()
    t = criar(a, tid, hid)
    c1 = comentar(t, b, 'primeiro')
    c2 = comentar(t, b, 'segundo')
    assert apagar_comentario(c1, b) is True, 'o autor nao conseguiu apagar'
    assert apagar_comentario(c2, a) is True, 'o dono da mao nao conseguiu moderar'
    assert apagar_comentario(c2, a) is False, 'apagar duas vezes devolveu True'
    assert ler(t)['comentarios'] == [], 'comentario apagado continua no payload'
    c3 = comentar(t, b, 'terceiro')
    estranho = 999999
    assert apagar_comentario(c3, estranho) is False, 'um terceiro apagou comentario alheio'
    print('OK  test_apagar_comentario_autor_ou_dono')


def test_link_revogado_nao_aceita_voto_nem_comentario():
    """Revogar desliga TUDO, não só a leitura."""
    _banco()
    from leaklab.mao_compartilhada import criar, revogar, votar, comentar
    a, b, tid, hid = _semeia()
    t = criar(a, tid, hid)
    revogar(a, t)
    assert votar(t, 'call') is None, 'link revogado aceitou voto'
    assert comentar(t, b, 'oi') is None, 'link revogado aceitou comentario'
    print('OK  test_link_revogado_nao_aceita_voto_nem_comentario')



def test_feed_mostra_autor_e_NAO_mostra_veredito():
    """As duas regras do feed (30/08): o username GrindLab de quem ESCOLHEU compartilhar
    aparece (identidade de plataforma; a regra de 28/08 protege nick de POKER, e esses
    continuam invisíveis); o veredito NÃO aparece no card — quem clica vota antes de ver."""
    _banco()
    import json
    from leaklab.mao_compartilhada import criar, listar_feed
    a, _b, tid, hid = _semeia()
    criar(a, tid, hid, step_idx=0, pergunta='call ou fold?')
    feed = listar_feed('recentes')
    meu = next((f for f in feed if f.get('pergunta') == 'call ou fold?'), None)
    assert meu, 'o link nao apareceu no feed'
    assert meu['autor'].startswith('dono_'), 'o autor (username GrindLab) nao aparece'
    bruto = json.dumps(meu, ensure_ascii=False)
    assert 'nick_do_dono' not in bruto, 'nick de POKER vazou no feed'
    for campo in ('label', 'best_action', 'gto_label', 'gto_strategy', 'ev_loss_bb'):
        assert campo not in meu['previa'], (
            'o card do feed entrega o veredito (%s) que a pagina pede para votar' % campo)
    assert meu['previa'].get('hero_cards'), 'a previa nao mostra a mao'
    print('OK  test_feed_mostra_autor_e_NAO_mostra_veredito')


def test_feed_revogado_some_e_ordenacoes_validas():
    _banco()
    from leaklab.mao_compartilhada import criar, listar_feed, revogar
    a, _b, tid, hid = _semeia()
    t = criar(a, tid, hid)
    assert any(f['token'] == t for f in listar_feed('recentes'))
    revogar(a, t)
    assert not any(f['token'] == t for f in listar_feed('recentes')), 'revogado segue no feed'
    # ordenacao desconhecida nao explode nem vira SQL: cai em recentes
    assert isinstance(listar_feed('DROP TABLE'), list)
    print('OK  test_feed_revogado_some_e_ordenacoes_validas')


def test_feed_sem_resposta_e_pergunta_sem_comentario():
    _banco()
    from leaklab.mao_compartilhada import comentar, criar, listar_feed
    a, b, tid, hid = _semeia()
    t = criar(a, tid, hid, step_idx=0, pergunta='e agora?')
    assert any(f['token'] == t for f in listar_feed('sem_resposta')), (
        'pergunta sem comentario nao apareceu em sem_resposta')
    comentar(t, b, 'fold tranquilo')
    assert not any(f['token'] == t for f in listar_feed('sem_resposta')), (
        'pergunta JA respondida continua em sem_resposta')
    print('OK  test_feed_sem_resposta_e_pergunta_sem_comentario')


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
