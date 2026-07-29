"""
Memorização de range: a correção não pune jogada defensável, e o SRS manda na ordem.

── O defeito que originou este arquivo ───────────────────────────────────────────────────────

A primeira versão do exercício corrigia com `hand_in_open_range`, cujo corte é
MIN_PREMISE_OPEN_FREQ = 0.05. Aquela função foi escrita para outra pergunta — validar a PREMISSA
de um spot vs_3bet ("o vilão podia ter aberto isto?") — e como gabarito ela é injusta.

Medido no UTG a 50bb, família conectores: quem marcava exatamente as mãos que o GTO abre ≥90%
das vezes (JTs, T9s) era REPROVADO, e o exercício cobrava 98s/87s/76s/65s/54s como faltantes.
54s o UTG abre 12% das vezes. O exercício reprovava a resposta certa e ensinava uma range mais
larga que a real — num produto cujo veredito é de 3 níveis justamente para não chamar frequência
mista de erro.

Agora são três estratos: núcleo (≥90%, obrigatório), fronteira (10–90%, o GTO mistura e as duas
respostas passam) e lixo (<10%, marcar é erro).

── O que este arquivo trava ──────────────────────────────────────────────────────────────────

  · que marcar SÓ o núcleo passe, e que marcar núcleo + mistas TAMBÉM passe;
  · que esquecer núcleo e que marcar lixo continuem sendo erro (senão a correção vira decoração);
  · que a fronteira em palavras seja a mão mais fraca do NÚCLEO — afirmação sem ressalva;
  · que a sugestão mire o VILÃO num leak de vs_RFI (a range que falta é a de quem abriu);
  · que amostra pequena e leak postflop não virem sugestão de estudo;
  · que o SRS sirva vencida antes de nova, e nunca repita dentro da sessão.
"""
import os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.leak_trainer as lt
from leaklab.leak_trainer import (_estratos, _FREQ_NUCLEO, _FREQ_LIXO, card_key_de_range,
                                  grade_range_grid_spot, generate_range_grid_spot,
                                  proximo_card_de_range, sugerir_memorizacao_de_range,
                                  universo_de_cartas, POSICOES_DE_ABERTURA)

_CONECTORES = ['JTs', 'T9s', '98s', '87s', '76s', '65s', '54s', '43s', '32s']
_SPOT_UTG = {'kind': 'range_grid', 'position': 'UTG', 'stack_bb': 50, 'familia': 'conectores',
             'familia_label': 'Conectores suited', 'hands': _CONECTORES, 'xp_value': 30,
             'card_key': 'grid:UTG:conectores:50'}


def _banco(user_id=None):
    """Prepara o banco e LIMPA o usuário do teste.

    Limpar é obrigatório: o arquivo do SQLite sobrevive entre execuções, e sem isso o intervalo
    de SRS do teste anterior vira o ponto de partida do próximo. Pego assim — a suíte passou
    verde, foi rodada de novo e um teste falhou sozinho, sem ninguém tocar no código.
    """
    os.environ.pop('DATABASE_URL', None)
    from database.schema import init_db, get_conn
    init_db()
    if user_id is not None:
        from database.repositories import _adapt
        c = get_conn()
        try:
            c.execute(_adapt('DELETE FROM range_card_srs WHERE user_id = ?'), (user_id,))
            c.commit()
        finally:
            c.close()


# ── A correção não pune o defensável ──────────────────────────────────────────────────────────

def test_o_caso_que_expos_o_defeito():
    """UTG conectores: JTs/T9s são núcleo; 98s..54s o GTO mistura; 43s/32s é lixo."""
    est = _estratos('UTG', _CONECTORES, 50.0)
    assert est['nucleo'] == ['JTs', 'T9s'], est['nucleo']
    assert '54s' in est['fronteira'], 'mão de 12% não pode ser cobrada como obrigatória'
    assert '32s' in est['lixo']
    for h in est['fronteira']:
        f = est['freqs'][h]
        assert _FREQ_LIXO <= f < _FREQ_NUCLEO, f'{h} em {f} não é fronteira'


def test_marcar_so_o_nucleo_PASSA():
    """O caso exato que a versão anterior reprovava."""
    est = _estratos('UTG', _CONECTORES, 50.0)
    g = grade_range_grid_spot(_SPOT_UTG, est['nucleo'])
    assert g['acertou'], f"marcar só o núcleo foi reprovado: faltaram={g['faltaram']}"


def test_marcar_nucleo_MAIS_as_mistas_TAMBEM_passa():
    """As duas respostas são defensáveis quando o GTO mistura; nenhuma pode ser erro."""
    est = _estratos('UTG', _CONECTORES, 50.0)
    g = grade_range_grid_spot(_SPOT_UTG, est['nucleo'] + est['fronteira'])
    assert g['acertou'], f"sobraram={g['sobraram']}"


def test_esquecer_o_nucleo_continua_ERRO():
    """Sem isto a correção vira decoração: tudo passa e o exercício não mede nada."""
    est = _estratos('UTG', _CONECTORES, 50.0)
    g = grade_range_grid_spot(_SPOT_UTG, est['nucleo'][1:])
    assert not g['acertou'] and g['faltaram'] == [est['nucleo'][0]], g


def test_marcar_lixo_continua_ERRO():
    est = _estratos('UTG', _CONECTORES, 50.0)
    g = grade_range_grid_spot(_SPOT_UTG, est['nucleo'] + est['lixo'][:1])
    assert not g['acertou'] and g['sobraram'] == [est['lixo'][0]], g


def test_nao_marcar_nada_NAO_e_acerto():
    """Numa família em que 2 de 9 entram, quem não marca nada 'acerta' 78% das células."""
    g = grade_range_grid_spot(_SPOT_UTG, [])
    assert not g['acertou'] and g['xp'] == 0


def test_a_fronteira_em_palavras_e_a_mais_fraca_do_NUCLEO():
    """Antes apontava uma mão de 12% de frequência, e o jogador levava isso para a mesa."""
    est = _estratos('UTG', _CONECTORES, 50.0)
    g = grade_range_grid_spot(_SPOT_UTG, [])
    assert g['fronteira'] == est['nucleo'][-1] == 'T9s', g['fronteira']


def test_as_mistas_viajam_com_a_frequencia():
    """É o que transforma 'errei' em 'aqui não há resposta certa'."""
    g = grade_range_grid_spot(_SPOT_UTG, [])
    mistas = {m['hand']: m['freq'] for m in g['mistas']}
    assert '54s' in mistas and 0.10 <= mistas['54s'] < 0.90, mistas


def test_gerador_e_corretor_usam_a_MESMA_regua():
    """Se o gerador escolhesse a família por um critério e o corretor cobrasse por outro, existiria
    exercício servido cuja resposta é 'marque tudo' — e ele seria reprovado por não marcar tudo."""
    for pos in ('UTG', 'LJ', 'CO'):
        for fam in ('as_suited', 'pares', 'conectores'):
            sp = generate_range_grid_spot(position=pos, familia=fam, stack=50)
            if not sp:
                continue
            est = _estratos(pos, sp['hands'], 50.0)
            assert est['nucleo'], f'{pos}/{fam} servido sem núcleo'
            assert len(est['nucleo']) < len(est['freqs']), f'{pos}/{fam} servido sem fronteira'


# ── A sugestão ────────────────────────────────────────────────────────────────────────────────

def _com_curriculo(cats, fn):
    orig = lt.build_curriculum
    lt.build_curriculum = lambda uid, days=90: cats
    try:
        return fn()
    finally:
        lt.build_curriculum = orig


def test_leak_de_vs_rfi_mira_a_posicao_do_VILAO():
    """Quem defende mal contra o open do LJ precisa da range DO LJ. Sugerir a range do BB ali
    seria a ferramenta errada com cara de conselho."""
    cats = [{'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'LJ', 'stack_bb': 30.0,
             'ev_loss_bb': 14.4, 'n': 21, 'weight': 14.4, 'key': 'vs_rfi:BB:LJ:30'}]
    sug = _com_curriculo(cats, lambda: sugerir_memorizacao_de_range(1))
    assert sug and sug['position'] == 'LJ' and sug['de_quem'] == 'vilao', sug
    assert sug['stack_bb'] == 30, 'a profundidade medida tem que cair numa carta que existe'


def test_leak_de_rfi_mira_a_posicao_do_HEROI():
    cats = [{'scenario': 'rfi', 'position': 'CO', 'vs_position': '', 'stack_bb': 50.0,
             'ev_loss_bb': 8.0, 'n': 11, 'weight': 8.0, 'key': 'rfi:CO::50'}]
    sug = _com_curriculo(cats, lambda: sugerir_memorizacao_de_range(1))
    assert sug and sug['position'] == 'CO' and sug['de_quem'] == 'heroi', sug


def test_amostra_pequena_NAO_vira_sugestao():
    """Duas mãos ruins não são um buraco de conhecimento; são duas mãos ruins."""
    cats = [{'scenario': 'rfi', 'position': 'CO', 'vs_position': '', 'stack_bb': 50.0,
             'ev_loss_bb': 9.0, 'n': 2, 'weight': 9.0, 'key': 'rfi:CO::50'}]
    assert _com_curriculo(cats, lambda: sugerir_memorizacao_de_range(1)) is None


def test_leak_POSTFLOP_nao_sugere_memorizar_abertura():
    """Marcar range de abertura não conserta um c-bet ruim."""
    cats = [{'kind': 'postflop', 'scenario': 'pf_bb_defense', 'position': 'BB',
             'vs_position': 'BTN', 'stack_bb': 40.0, 'ev_loss_bb': 30.0, 'n': 50,
             'weight': 30.0, 'key': 'pf:bb_defense'}]
    assert _com_curriculo(cats, lambda: sugerir_memorizacao_de_range(1)) is None


def test_o_maior_EV_vence():
    cats = [{'scenario': 'rfi', 'position': 'CO', 'vs_position': '', 'stack_bb': 50.0,
             'ev_loss_bb': 3.0, 'n': 9, 'weight': 3.0, 'key': 'a'},
            {'scenario': 'rfi', 'position': 'UTG', 'vs_position': '', 'stack_bb': 50.0,
             'ev_loss_bb': 19.0, 'n': 30, 'weight': 19.0, 'key': 'b'}]
    sug = _com_curriculo(cats, lambda: sugerir_memorizacao_de_range(1))
    assert sug['position'] == 'UTG', sug


# ── O SRS ─────────────────────────────────────────────────────────────────────────────────────

def test_nao_repete_dentro_da_sessao():
    _banco(990001)
    servidas, u = [], 990001
    for i in range(6):
        sp = proximo_card_de_range(u, servidas=servidas, alvo='LJ', rng=random.Random(i))
        assert sp, 'acabaram as cartas cedo demais'
        servidas.append(sp['card_key'])
    assert len(set(servidas)) == 6, servidas


def test_carta_vencida_vem_antes_de_carta_nova():
    """É o ponto inteiro do SRS: sem isto o jogador reencontra por sorteio o que já sabe,
    enquanto o que ele errou nunca volta."""
    _banco(990002)
    from datetime import datetime, timedelta
    from database.repositories import registrar_carta_de_range, _adapt
    from database.schema import get_conn
    u, ck = 990002, 'grid:UTG:pares:20'
    registrar_carta_de_range(u, ck, 'UTG', 'pares', 20, False)
    c = get_conn()
    c.execute(_adapt('UPDATE range_card_srs SET due_at = ? WHERE user_id = ? AND card_key = ?'),
              ((datetime.utcnow() - timedelta(days=9)).isoformat(), u, ck))
    c.commit(); c.close()
    sp = proximo_card_de_range(u, alvo='LJ', rng=random.Random(7))
    assert sp['card_key'] == ck, f'a vencida devia vir antes do alvo LJ, veio {sp["card_key"]}'
    assert sp['srs']['revisao'] is True


def test_acerto_espaca_e_erro_reseta():
    """Erro RESETA em vez de recuar um degrau: quem errou a fronteira do LJ não a sabe 'um pouco
    menos', não a sabe. Espaçar mesmo assim é agendar o esquecimento."""
    _banco(990003)
    from database.repositories import registrar_carta_de_range
    u, ck = 990003, 'grid:HJ:pares:50'
    a = registrar_carta_de_range(u, ck, 'HJ', 'pares', 50, True)
    b = registrar_carta_de_range(u, ck, 'HJ', 'pares', 50, True)
    c = registrar_carta_de_range(u, ck, 'HJ', 'pares', 50, False)
    assert b['interval_days'] > a['interval_days'], (a, b)
    assert c['interval_days'] == a['interval_days'] and c['streak'] == 0, c


def test_a_carta_recem_agendada_nao_volta_na_sequencia():
    _banco(990004)
    from database.repositories import registrar_carta_de_range
    u = 990004
    sp = proximo_card_de_range(u, alvo='LJ', rng=random.Random(3))
    registrar_carta_de_range(u, sp['card_key'], sp['position'], sp['familia'],
                             int(sp['stack_bb']), True)
    prox = proximo_card_de_range(u, alvo='LJ', rng=random.Random(3))
    assert prox['card_key'] != sp['card_key'], 'carta agendada para daqui a 3 dias voltou agora'


def test_a_chave_da_carta_e_fonte_unica():
    """O gerador, o agendador e a correção têm que concordar em o que é a mesma carta. Gravar com
    uma chave e procurar com outra é o defeito que já custou três meses no hash de board."""
    sp = generate_range_grid_spot(position='LJ', familia='pares', stack=30)
    assert sp['card_key'] == card_key_de_range('LJ', 'pares', 30) == sp['category']


def test_familia_majoritariamente_mista_NAO_e_servida():
    """Visto na tela: um exercicio saiu com 6 de 9 maos misturando, sobrando 3 celulas com
    resposta e um muro de percentuais no feedback. Nao ha fronteira a memorizar onde quase tudo
    e tanto faz."""
    from leaklab.leak_trainer import _FAMILIAS
    fam_h = {k: h for k, _lab, h in _FAMILIAS}
    for pos, fam, st in universo_de_cartas():
        if not generate_range_grid_spot(position=pos, familia=fam, stack=st):
            continue
        est = _estratos(pos, fam_h[fam], float(st))
        assert len(est['fronteira']) <= len(est['nucleo']) + len(est['lixo']),             f'{pos}/{fam}/{st}bb servido com mistas em maioria'


def test_o_universo_tem_tamanho_de_curriculo():
    """Se a maioria das combinações não fosse ensinável, o SRS giraria em meia dúzia de cartas e
    'memorizar ranges' seria uma promessa vazia."""
    ensinaveis = [c for c in universo_de_cartas()
                  if generate_range_grid_spot(position=c[0], familia=c[1], stack=c[2])]
    assert len(ensinaveis) >= 100, f'só {len(ensinaveis)} cartas ensináveis'
    posicoes = {c[0] for c in ensinaveis}
    assert posicoes >= set(POSICOES_DE_ABERTURA) - {'BTN'}, posicoes


if __name__ == '__main__':
    falhas = 0
    testes = (test_o_caso_que_expos_o_defeito,
              test_marcar_so_o_nucleo_PASSA,
              test_marcar_nucleo_MAIS_as_mistas_TAMBEM_passa,
              test_esquecer_o_nucleo_continua_ERRO,
              test_marcar_lixo_continua_ERRO,
              test_nao_marcar_nada_NAO_e_acerto,
              test_a_fronteira_em_palavras_e_a_mais_fraca_do_NUCLEO,
              test_as_mistas_viajam_com_a_frequencia,
              test_gerador_e_corretor_usam_a_MESMA_regua,
              test_leak_de_vs_rfi_mira_a_posicao_do_VILAO,
              test_leak_de_rfi_mira_a_posicao_do_HEROI,
              test_amostra_pequena_NAO_vira_sugestao,
              test_leak_POSTFLOP_nao_sugere_memorizar_abertura,
              test_o_maior_EV_vence,
              test_nao_repete_dentro_da_sessao,
              test_carta_vencida_vem_antes_de_carta_nova,
              test_acerto_espaca_e_erro_reseta,
              test_a_carta_recem_agendada_nao_volta_na_sequencia,
              test_a_chave_da_carta_e_fonte_unica,
              test_familia_majoritariamente_mista_NAO_e_servida,
              test_o_universo_tem_tamanho_de_curriculo)
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
