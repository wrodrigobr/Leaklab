# -*- coding: utf-8 -*-
"""A nota que discorda do veredito da propria linha nao vai para a tela (14/09).

── O que estava acontecendo ───────────────────────────────────────────────────────────────

A nota do card e TEXTO congelado no instante da analise. O resync do solver reescreve
`best_action`, `gto_action`, `label` e `ev_loss_bb` horas depois e NAO reescreve o texto. Medido
em producao:

    1.497 decisoes servindo uma ordem no texto e exibindo outra na linha
    1.167 delas na forma pior: o veredito ABSOLVE o jogador e o texto o ACUSA

A forma pior, numa linha de verdade (dec 431286, conta 65):

    Flop: Fold          [chip verde: Correto]
    "... o call tinha valor positivo (+24.3pp) ... Acao esperada: CALL."

O jogador foldou, o sistema concorda que o fold estava certo, e o texto manda dar call.

── O controle que sustenta a causa ────────────────────────────────────────────────────────

A contradicao aparece em 39,7% das linhas cujo custo veio de `solver_hand` (reescritas depois
da nota) contra **0,1%** das de `gw_har` (carta preflop, nunca reescrita). Se o defeito fosse do
gerador de texto, as duas fontes empatariam. Nao empatam, e e por isso que o conserto e na
LEITURA e nao no gerador.

── Por que retirar e nao reescrever ───────────────────────────────────────────────────────

Apagar so a frase final seria cosmetico: o corpo da nota tambem e escrito em funcao de `best`,
em nove pontos de `decision_engine_v11`. Reescrever o texto aqui seria TROCAR a resposta, que e
o que a regra 7 do CLAUDE.md proibe depois do episodio do board no hash. Silencio e honesto.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. Que a funcao acusa quando tem que acusar, e **que ela se cala quando a nota confere** — sem
   esse lado, um guarda que zera tudo passaria verde.
2. Que ela julga pelo campo que a TELA mostra (`gto_action or best_action`), nao por outro.
3. Que as tres portas de leitura silenciam, e que a nota BOA sobrevive nas tres.
4. Que a rota HTTP real nao serve o texto velho, porque e na rota que o jogador le.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from leaklab.card_verdict import (acao_declarada_na_nota,                      # noqa: E402
                                  nota_contradiz_o_veredito)

# Reusa o harness em vez de copia-lo: aquele bloco ja teve CINCO copias num arquivo so, e a
# regra 5 nasceu exatamente disso. Ele sobe Postgres quando `DATABASE_URL` existe (homolog) e
# SQLite descartavel quando nao, entao o mesmo caso vale nos dois ambientes.
from test_arquivo_com_varios_torneios import UID, banco_de_teste              # noqa: E402

# O texto real da dec 444811, da mao que o dono mandou avaliar. Nota copiada do banco, nao
# inventada: nota forjada a mao nao prova que o regex casa com o que o motor escreve.
NOTA_VELHA = ('Com equity de 53.1% vs 37.9% exigidos pelo pot, o call tinha valor positivo '
              '(+15.2pp). A aposta/raise que veio representava uma oferta matematicamente '
              'atraente para o pot odds da situação. Ação esperada: CALL.')

# A nota que CONFERE: mesmo texto, com a frase apontando a acao que a linha recomenda. O motor
# escreve 'ALL-IN' para `jam` (o mapa `_act` de decision_engine_v11:2085).
NOTA_BOA = NOTA_VELHA.replace('Ação esperada: CALL.', 'Ação esperada: ALL-IN.')

# A sentenca de contexto, que e o que as 1.200 notas sem a frase tem. Ela e condicionada a
# jogada do HEROI e a forca da mao, nunca a `best`, entao nao envelhece.
NOTA_DE_CONTEXTO = ('Sua mão está no topo do range aqui. A linha passiva protege o pote '
                    'pequeno, mas é apostando que ele cresce — vale conferir se havia valor '
                    'a extrair.')


# ══════════════════════════════════════════════════════════════════════════════════════════
# 1) A funcao
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_a_frase_declarada_e_normalizada():
    assert acao_declarada_na_nota('Ação esperada: CALL.') == 'call'
    assert acao_declarada_na_nota('Ação esperada: ALL-IN.') == 'allin'
    assert acao_declarada_na_nota('Acao esperada: fold.') == 'fold'
    assert acao_declarada_na_nota(NOTA_VELHA) == 'call'


def test_nota_sem_a_frase_nao_declara_nada():
    """As 1.200 notas de contexto do acervo. Ausencia da frase nao pode virar acusacao: se
    virasse, o conserto apagaria 1.200 notas boas de uma vez."""
    assert acao_declarada_na_nota(NOTA_DE_CONTEXTO) == ''
    assert acao_declarada_na_nota('') == ''
    assert acao_declarada_na_nota(None) == ''
    assert nota_contradiz_o_veredito(NOTA_DE_CONTEXTO, 'bet', 'bet') is False
    assert nota_contradiz_o_veredito(NOTA_DE_CONTEXTO, 'check', 'check') is False


def test_acusa_a_nota_velha():
    """O caso da mao 262009780504: a linha recomenda jam e o texto manda dar call."""
    assert nota_contradiz_o_veredito(NOTA_VELHA, 'jam', 'jam') is True


def test_se_cala_quando_a_nota_confere():
    """O OUTRO lado, sem o qual o guarda nao vale nada: uma funcao que devolvesse True sempre
    passaria em todos os casos de acusacao acima."""
    assert nota_contradiz_o_veredito(NOTA_BOA, 'jam', 'jam') is False
    assert nota_contradiz_o_veredito('Ação esperada: FOLD.', 'fold', 'fold') is False
    assert nota_contradiz_o_veredito('Ação esperada: CALL.', 'call', 'call') is False


def test_allin_jam_e_shove_sao_a_mesma_acao():
    """Cobrar a diferenca entre tres palavras para o mesmo lance seria inventar 1.497 falsos
    positivos. `norm_action` e a fonte unica dessa equivalencia."""
    for rec in ('jam', 'allin', 'all-in', 'shove'):
        assert nota_contradiz_o_veredito('Ação esperada: ALL-IN.', rec, rec) is False, rec
        assert nota_contradiz_o_veredito('Ação esperada: SHOVE.', rec, rec) is False, rec


def test_o_sizing_nao_conta_como_divergencia():
    """`bet` e `bet_75pct` sao a mesma decisao. A equivalencia sai de `_matches`, a mesma que o
    resto do veredito usa."""
    assert nota_contradiz_o_veredito('Ação esperada: BET.', 'bet_75pct', 'bet') is False
    assert nota_contradiz_o_veredito('Ação esperada: RAISE.', 'raise_77pct', 'raise') is False


def test_julga_pelo_campo_que_a_TELA_mostra():
    """A tela mostra `gto_action || best_action` (TournamentDetail.tsx:153). Os dois divergem em
    191 decisoes do acervo, e e nelas que julgar pelo campo errado avaliaria uma recomendacao
    que o jogador nao ve na linha."""
    # gto_action='call' vence best_action='shove': a linha mostra Call
    assert nota_contradiz_o_veredito('Ação esperada: CALL.', 'call', 'shove') is False
    assert nota_contradiz_o_veredito('Ação esperada: ALL-IN.', 'call', 'shove') is True
    # sem gto_action a tela cai em best_action, e a funcao tambem
    assert nota_contradiz_o_veredito('Ação esperada: RAISE.', None, 'raise') is False
    assert nota_contradiz_o_veredito('Ação esperada: FOLD.', '', 'raise') is True


def test_sem_recomendacao_nao_da_para_julgar():
    """Linha sem `gto_action` e sem `best_action` nao tem contra o que comparar. Acusar ali seria
    apagar a nota por falta de dado, nao por contradicao."""
    assert nota_contradiz_o_veredito(NOTA_VELHA, None, None) is False
    assert nota_contradiz_o_veredito(NOTA_VELHA, '', '') is False


# ══════════════════════════════════════════════════════════════════════════════════════════
# 2) As portas de leitura, contra o banco
# ══════════════════════════════════════════════════════════════════════════════════════════

def _semeia(nota, best='jam', gto='jam', street='flop', position='CO'):
    """Grava um torneio e UMA decisao com a nota dada. Devolve (db_id, decision_id, codigo).

    O `codigo` sai daqui porque a rota `/history/tournament/<x>` casa pela COLUNA TEXT
    `tournament_id` (`get_tournament`), nao pelo id interno. Passar o id devolvia 404, e um 404
    e um caso que passa sem exercitar a rota se o assert nao olhar o status.

    Os campos nao sao decorativos: `gto_label`, `position`, `hero_cards` e
    `n_active_opponents` sao os filtros que o `get_drill_spots` aplica, e sem eles a decisao
    nao apareceria no drill — o caso passaria verde sem ter exercitado a porta.
    """
    from database.schema import get_conn
    from database.repositories import _adapt
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, hero, hands_count, "
            "decisions_count) VALUES (?,?,?,?,?)"), (UID, 'T-NOTA-%s' % street, 'Hero', 1, 1))
        tid = dict(conn.execute(_adapt(
            "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
            (UID, 'T-NOTA-%s' % street)).fetchone())['id']
        conn.execute(_adapt(
            "INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, label, score, note, gto_action, gto_label, position, "
            "num_players, stack_bb, facing_bet, n_active_opponents) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"),
            (tid, '900000000%d' % len(street), street, 'JcQc', '["5h", "Qs", "8c"]',
             'fold', best, 'clear_mistake', 1.0, nota, gto, 'gto_critical', position,
             9, 74.4, 16.0, 1))
        did = dict(conn.execute(_adapt(
            "SELECT id FROM decisions WHERE tournament_id=?"), (tid,)).fetchone())['id']
        conn.commit()
        return tid, did, 'T-NOTA-%s' % street
    finally:
        conn.close()


def test_get_decisions_retira_a_velha_e_acende_a_flag():
    with banco_de_teste():
        from database.repositories import get_decisions
        tid, _, _ = _semeia(NOTA_VELHA)
        d = get_decisions(tid)[0]
        assert d['note'] is None, ('a nota velha vazou pelo get_decisions', d['note'])
        assert d.get('note_desatualizada') is True, 'a tela nao vai saber o motivo'


def test_get_decisions_preserva_a_nota_boa():
    """O controle da porta. Sem ele, um `d['note'] = None` incondicional passaria no caso acima
    e apagaria as 135.728 notas que estao certas."""
    with banco_de_teste():
        from database.repositories import get_decisions
        tid, _, _ = _semeia(NOTA_BOA)
        d = get_decisions(tid)[0]
        assert d['note'] == NOTA_BOA, ('a nota boa foi apagada', d['note'])
        assert d.get('note_desatualizada') is None, 'flag acesa sem contradicao'


def test_get_decisions_preserva_a_nota_de_contexto():
    with banco_de_teste():
        from database.repositories import get_decisions
        tid, _, _ = _semeia(NOTA_DE_CONTEXTO)
        d = get_decisions(tid)[0]
        assert d['note'] == NOTA_DE_CONTEXTO, ('nota de contexto apagada', d['note'])


def test_get_decision_for_drill_silencia_e_preserva():
    with banco_de_teste():
        from database.repositories import get_decision_for_drill
        _, did, _ = _semeia(NOTA_VELHA, street='turn')
        r = get_decision_for_drill(UID, did)
        assert r is not None, 'a decisao nao foi encontrada, o caso nao exercitou nada'
        assert r['note'] is None, ('vazou pelo drill', r['note'])
        assert r.get('note_desatualizada') is True

    with banco_de_teste():
        from database.repositories import get_decision_for_drill
        _, did, _ = _semeia(NOTA_BOA, street='turn')
        r = get_decision_for_drill(UID, did)
        assert r['note'] == NOTA_BOA, ('o drill apagou a nota boa', r['note'])


def test_get_drill_spots_silencia_e_preserva():
    with banco_de_teste():
        from database.repositories import get_drill_spots
        _semeia(NOTA_VELHA, street='river')
        spots = [s for s in get_drill_spots(UID, limit=10)]
        assert spots, 'nenhum spot voltou: os filtros do drill nao foram satisfeitos'
        assert all(s['note'] is None for s in spots), 'vazou pelo get_drill_spots'
        assert all(s.get('note_desatualizada') is True for s in spots)

    with banco_de_teste():
        from database.repositories import get_drill_spots
        _semeia(NOTA_BOA, street='river')
        spots = [s for s in get_drill_spots(UID, limit=10)]
        assert spots, 'nenhum spot voltou'
        assert all(s['note'] == NOTA_BOA for s in spots), 'o drill apagou a nota boa'


# ══════════════════════════════════════════════════════════════════════════════════════════
# 3) A rota que o jogador le
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_a_rota_do_torneio_troca_o_texto_velho_por_um_coerente():
    """O que vale e a PORTA, nao a funcao. E foi aqui que o resultado saiu melhor do que o
    desenho previa.

    `/history/tournament` passa por `_enrich_note`, que devolve a nota guardada quando ela e
    boa e **regera** quando ela esta vazia. Silenciada a nota velha, ele monta uma nova a partir
    das colunas VIVAS da linha (`action_taken`, `best_action`, `label`, `score`, stack, ICM), que
    o resync reescreve todas juntas -- logo a nota nova e coerente por construcao, e o jogador
    ganha explicacao curta e certa em vez de nenhuma:

        "Flop · CO · 74bb · aposta 16.0bb. Voce deu FOLD, mas o esperado era ALL-IN.
         Erro grave (score 1.000)."

    O caso trava as duas pontas: o texto velho nao pode chegar, e o que chega no lugar tem de
    concordar com a recomendacao da linha. Sem a segunda metade, uma nota nova ERRADA passaria.
    """
    with banco_de_teste() as (cliente, headers):
        _, _, codigo = _semeia(NOTA_VELHA)
        r = cliente.get('/history/tournament/%s' % codigo, headers=headers)
        assert r.status_code == 200, r.status_code
        assert 'Ação esperada' not in r.get_data(as_text=True), (
            'a ordem velha chegou na resposta da rota')
        d = r.get_json()['decisions'][0]
        assert 'o call tinha valor positivo' not in (d['note'] or ''), (
            'o corpo velho sobreviveu', d['note'])
        assert d.get('note_desatualizada') is True, 'a rota nao mandou o motivo para a tela'
        # e a nota NOVA nao pode contradizer a linha: mesma funcao, aplicada ao que a rota serviu
        assert not nota_contradiz_o_veredito(d['note'], d.get('gto_action'),
                                             d.get('best_action')), (
            'a nota regerada contradiz a recomendacao', d['note'])


def test_a_rota_do_torneio_preserva_a_nota_boa():
    with banco_de_teste() as (cliente, headers):
        _, _, codigo = _semeia(NOTA_BOA)
        r = cliente.get('/history/tournament/%s' % codigo, headers=headers)
        assert r.status_code == 200, r.status_code
        d = r.get_json()['decisions'][0]
        assert d['note'] == NOTA_BOA, ('a rota apagou a nota boa', d['note'])
        assert d.get('note_desatualizada') is None


# ══════════════════════════════════════════════════════════════════════════════════════════
# 4) A nota REGERADA e copy de jogador, e a regra do travessao vale para ela
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_a_nota_regerada_nao_tem_travessao():
    """A casa proibe travessao em TODO texto visivel ao jogador, por soar a texto de IA.

    Isto aqui e o terceiro lugar da mesma regra: ela era vigiada na copy de e-mail
    (`test_cobranca_email.py`) e na copy do front (`test_i18n_copy_do_frontend.py`), e **copy
    gerada no backend nao era varrida por ninguem**. `_enrich_note` escrevia
    "Flop — CO · 74bb", e antes desta mudanca isso aparecia so nas notas genericas; agora
    aparece nas 1.519 cujo texto velho foi retirado.

    A varredura cobre as formas que a funcao sabe montar, nao um caso: o cabecalho com e sem
    contexto, o board com draw e o M-Ratio curto, que sao as tres sentencas onde o travessao
    morava.
    """
    from api.app import _enrich_note
    formas = [
        dict(street='flop', position='CO', stack_bb=74.4, facing_bet=16.0,
             action_taken='fold', best_action='jam', label='clear_mistake', score=1.0,
             draw_profile='none', icm_pressure='low', m_ratio=26.1),
        dict(street='turn', position='BB', stack_bb=9.0, facing_bet=0.0,
             action_taken='check', best_action='bet', label='small_mistake', score=0.5,
             draw_profile='flush_draw', icm_pressure='high', m_ratio=2.1),
        dict(street='preflop', action_taken='call', best_action='raise',
             label='clear_mistake', score=0.9, draw_profile='BDFD+BDSD',
             icm_pressure='medium', m_ratio=12.0, is_3bet=1, pot_at_decision_bb=8.5),
        # sem nenhum campo de contexto: o cabecalho fica so com a street
        dict(street='river', action_taken='fold', best_action='call',
             label='clear_mistake', score=0.7),
    ]
    for i, linha in enumerate(formas):
        texto = _enrich_note(dict(linha))
        assert texto, 'forma %d nao gerou texto, o caso nao varreu nada' % i
        assert '—' not in texto, ('travessao na nota regerada (forma %d): %s' % (i, texto))
        assert ' - ' not in texto, ('hifen como pontuacao (forma %d): %s' % (i, texto))


# ══════════════════════════════════════════════════════════════════════════════════════════
# 5) Auditoria VER-5 / NLU-13 (15/09): a nota REGERADA tambem e julgada, e nao troca a resposta
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# O resync reescreve so `gto_action`. A tela mostra `gto_action or best_action`. Silenciada a
# nota velha, `_enrich_note` regerava a partir de `best_action`: "o esperado era RAISE" ao lado
# de um ideal JAM, com `note_desatualizada` aceso na mesma linha. E a regua nao lia essa frase
# (so "Ação esperada:"), entao a contradicao nova passava sem ser julgada. O deep-dive, com
# SELECT proprio, recebia a nota velha crua e a repetia ao LLM.

def test_a_regua_le_a_frase_que_o_enrich_note_escreve():
    regerada = 'Pré-flop · UTG · 30bb. Você deu FOLD, mas o esperado era RAISE. Pequeno erro.'
    assert acao_declarada_na_nota(regerada) == 'raise'
    assert nota_contradiz_o_veredito(regerada, 'jam', 'raise') is True
    assert nota_contradiz_o_veredito(regerada, 'raise', 'raise') is False
    assert nota_contradiz_o_veredito(regerada, None, 'raise') is False


def test_enrich_note_silencia_quando_gto_e_best_discordam():
    """A opcao que nao TROCA a resposta (regra 7): sem texto, a tela mostra o aviso."""
    from api.app import _enrich_note
    linha = dict(street='preflop', position='UTG', stack_bb=30.0, action_taken='fold',
                 best_action='raise', gto_action='jam', label='small_mistake', score=0.25,
                 note=None, note_desatualizada=True)
    assert _enrich_note(dict(linha)) == '', _enrich_note(dict(linha))
    # nota generica com as colunas discordando: volta a generica, nao inventa texto
    from api.app import _GENERIC_NOTES
    generica = sorted(_GENERIC_NOTES)[0]
    assert _enrich_note(dict(linha, note=generica, note_desatualizada=None)) == generica


def test_enrich_note_regera_quando_as_colunas_concordam():
    """O outro lado, e o comportamento de 14/09 que fica: colunas vivas coerentes dao texto."""
    from api.app import _enrich_note
    for gto in ('raise', None, 'raises'):
        linha = dict(street='preflop', position='UTG', stack_bb=30.0, action_taken='fold',
                     best_action='raise', gto_action=gto, label='small_mistake', score=0.25,
                     note=None, note_desatualizada=True)
        texto = _enrich_note(dict(linha))
        assert 'o esperado era RAISE' in texto, (gto, texto)
        assert not nota_contradiz_o_veredito(texto, gto, 'raise')


def test_a_rota_do_torneio_silencia_quando_o_resync_mexeu_so_no_gto_action():
    with banco_de_teste() as (cliente, headers):
        # a nota velha manda CALL; o resync deixou `best_action=call` e escreveu `gto_action=jam`
        _, _, codigo = _semeia(NOTA_VELHA, best='call', gto='jam', street='turn')
        r = cliente.get('/history/tournament/%s' % codigo, headers=headers)
        assert r.status_code == 200, r.status_code
        d = r.get_json()['decisions'][0]
        assert d.get('note_desatualizada') is True, 'a nota velha (CALL) nao foi silenciada contra o ideal JAM'
        assert not d.get('note'), ('a rota regerou texto contra o ideal exibido', d.get('note'))


def test_o_deep_dive_recebe_a_nota_silenciada():
    """`/analyze/decision` faz SELECT proprio; o que chega ao LLM tem de passar pela mesma regua."""
    import leaklab.llm_explainer as L
    import api.app as A
    with banco_de_teste() as (cliente, headers):
        _, did, _ = _semeia(NOTA_VELHA, best='jam', gto='jam', street='river')
        capturado = {}

        def fake_deep(decision, user_id, **kw):
            capturado['dec'] = dict(decision)
            return 'analise falsa'

        def fake_single(decision):
            capturado['dec'] = dict(decision)
            return 'analise falsa'

        orig = (L.deep_dive_decision_agentic, L.analyze_single_decision, A._check_ai_quota)
        L.deep_dive_decision_agentic, L.analyze_single_decision = fake_deep, fake_single
        A._check_ai_quota = lambda uid: None
        try:
            r = cliente.post('/analyze/decision', json={'decision_id': did, 'force_new': True},
                             headers=headers)
        finally:
            L.deep_dive_decision_agentic, L.analyze_single_decision, A._check_ai_quota = orig
        assert r.status_code == 200, (r.status_code, r.get_json())
        dec = capturado.get('dec') or {}
        assert dec, 'o LLM nao foi chamado'
        assert not dec.get('note'), ('a nota velha chegou crua ao LLM', dec.get('note'))
        assert dec.get('note_desatualizada') is True


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
