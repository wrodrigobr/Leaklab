# -*- coding: utf-8 -*-
"""Cartas de MESA CHEIA do GTO Wizard: preenchem buraco, e so buraco.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

149 decisoes do acervo tem `coverage_reason='pairing_uncovered'`: o par (hero, 3-bettor) nunca foi
semeado nas nossas cartas de ring. O plano `docs/gw_plano_ring.json` captura os 7 pares que cobrem
~91 delas.

── Por que este arquivo existe ────────────────────────────────────────────────────────────────

A captura ainda nao aconteceu (cota do GW), entao a integracao foi escrita ANTES do dado. Isso
seria imprudente sem teste: aqui um acervo de ring SINTETICO exercita o caminho inteiro — indice,
derivacao de papeis, janela de profundidade e graduacao — para que o dia da captura seja so
importar.

O que este arquivo NAO prova, e nao ha como provar sem dado: o efeito no acervo. Quantas das 149
de fato passam a ter gabarito e uma medicao para depois da captura.
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import leaklab.preflop_gto_ranges as g
from leaklab.preflop_gto_ranges import analyze_preflop

_R = '23456789TJQKA'
_MAOS = sorted([r + r for r in _R]
               + [_R[j] + _R[i] + s for j in range(13) for i in range(j) for s in ('o', 's')])


def _no(ator, node, mesa=8, maos=None):
    return {
        'gametype': 'MTTGeneral_8m', 'depth': '20.125', 'preflop_actions': node,
        'ator': ator, 'mesa': mesa, 'pot': '9.0',
        'acoes': ['FOLD', 'CALL 6.5', 'RAISE 20.000'],
        'codigos': ['F', 'C', 'RAI'],
        'maos': maos if maos is not None else {
            'AA': {'RAISE 20.000': {'f': 1.0, 'ev': 12.0}},
            'JJ': {'CALL 6.5': {'f': 0.75, 'ev': 3.0}, 'RAISE 20.000': {'f': 0.25, 'ev': 2.8}},
            'A5s': {'FOLD': {'f': 0.6, 'ev': 0.0}, 'CALL 6.5': {'f': 0.4, 'ev': 0.2}},
            '72o': {'FOLD': {'f': 1.0, 'ev': 0.0}},
        },
    }


def _com_acervo(nos: dict, fn):
    """Roda `fn` com um acervo de ring sintetico no lugar do arquivo real."""
    with tempfile.TemporaryDirectory() as d:
        caminho = os.path.join(d, 'ring.json')
        io.open(caminho, 'w', encoding='utf-8').write(json.dumps({'MTTGeneral_8m': nos}))
        antigo_path, antigo_cache = g._RING_PATH, g._ring_cache
        g._RING_PATH, g._ring_cache = caminho, None
        try:
            return fn()
        finally:
            g._RING_PATH, g._ring_cache = antigo_path, antigo_cache


# `F-F-F-F-R2-F-R6.5`: UTG/UTG+1/LJ/HJ foldam, CO abre, BTN folda, SB da squeeze, BB decide.
_NODE_BB_VS_SB = 'F-F-F-F-R2-F-R6.5'
_ACERVO = {f'20.125|{_NODE_BB_VS_SB}': _no('BB', _NODE_BB_VS_SB)}


def _bb_vs_squeeze(mao='JJ', acao='call', stack=20.0):
    return analyze_preflop(position='BB', hero_hand_type=mao, stack_bb=stack, action_taken=acao,
                           facing_size=6.5, vs_position='SB', facing_raises=2,
                           hero_was_aggressor=False, facing_to_bb=6.5, n_players=8)


def test_papeis_saem_do_nome_do_no():
    """`F-F-F-F-R2-F-R6.5` diz quem abriu (CO), quem deu squeeze (SB) e quem decide (BB)."""
    p = g._ring_papeis(_NODE_BB_VS_SB, 8, 'BB')
    assert p == {'abriu': 'CO', 'vilao': 'SB', 'cenario': 'faces_squeeze'}, p
    # UTG/UTG+1/LJ foldam, HJ abre -> quem decide e o CO. (Escrevi 'CO abre, BTN decide' na
    # primeira versao e o proprio guarda de discordancia reprovou — que e para o que ele serve.)
    assert g._ring_papeis('F-F-F-R2', 8, 'CO') == {
        'abriu': 'HJ', 'vilao': 'HJ', 'cenario': 'vs_rfi'}


def test_derivacao_discordando_do_payload_descarta_o_no():
    """A contagem de tokens diz quem age; o payload TAMBEM diz. Se discordarem, o nó nao entra —
    indexar torto seria carta certa sob chave errada, que nao se denuncia depois."""
    assert g._ring_papeis(_NODE_BB_VS_SB, 8, 'CO') is None, 'indexou com ator divergente'
    assert g._ring_papeis(_NODE_BB_VS_SB, 6, 'BB') is None, 'usou ordem de mesa errada'


def test_preenche_o_buraco_e_gradua():
    """O par BB x SB nao existe nas nossas cartas: hoje e `pairing_uncovered`. Com a carta do GW
    ele passa a ter veredito."""
    # o "antes" tem que rodar com acervo VAZIO explicito: desde 07/08 existe um
    # `ring_ranges_har.json` de verdade no disco, e um teste que dependesse dele estaria medindo
    # o ambiente, nao a regra.
    sem = _com_acervo({}, _bb_vs_squeeze)
    assert sem['available'] is False and sem.get('coverage_reason') == 'pairing_uncovered'

    com = _com_acervo(_ACERVO, _bb_vs_squeeze)
    assert com['available'] is True, com.get('coverage_reason')
    assert com['source'] == 'gw_ring_har'
    assert com['action_quality'] == 'correct'          # JJ paga 75%
    assert com.get('coverage_reason') is None
    # e a acao fora do range vira leak, provando que a carta foi de fato consultada
    ruim = _com_acervo(_ACERVO, lambda: _bb_vs_squeeze(mao='72o', acao='call'))
    assert ruim['action_quality'] == 'major_leak', ruim['action_quality']


def test_nao_encosta_onde_ja_ha_carta():
    """Preenche buraco, nao substitui fonte. Um spot que hoje TEM gabarito nao pode mudar de
    veredito por causa desta integracao — seria dano que o buraco nao causava."""
    kw = dict(position='BB', hero_hand_type='JJ', stack_bb=20.0, action_taken='call',
              facing_size=2.0, vs_position='CO', facing_raises=1, hero_was_aggressor=False,
              facing_to_bb=2.0, n_players=8)
    antes = _com_acervo({}, lambda: analyze_preflop(**kw))
    assert antes['available'] is True, 'o controle precisa de um spot JA coberto'
    # BB contra open do CO com todos foldando ate o SB: `F-F-F-F-R2-F-F`. Precisa ser no VALIDO
    # — a primeira versao usou um no que o guarda de discordancia rejeitava, entao o acervo ficava
    # vazio e o teste passava por vacuidade, provando nada.
    no_valido = _no('BB', 'F-F-F-F-R2-F-F')
    assert g._ring_papeis('F-F-F-F-R2-F-F', 8, 'BB') == {
        'abriu': 'CO', 'vilao': 'CO', 'cenario': 'vs_rfi'}
    depois = _com_acervo({'20.125|F-F-F-F-R2-F-F': no_valido}, lambda: analyze_preflop(**kw))
    for campo in ('available', 'source', 'action_quality', 'recommended_actions'):
        assert antes.get(campo) == depois.get(campo), (campo, antes.get(campo), depois.get(campo))


def test_mesa_de_2_nunca_usa_carta_de_ring():
    """O defeito que originou tudo isto: carta de mesa cheia gradeando heads-up.

    Pelo caminho publico, mesa de 2 nem chega aqui — o roteador HU devolve `hu_uncovered`, e o
    gatilho deste preenchimento e `pairing_uncovered`. Entao o guarda de `n_players` e SEGUNDA
    barreira, e a verificacao por mutacao provou que o teste de ponta a ponta nao o exercitava:
    desligar o guarda nao quebrava nada. Aqui ele e chamado direto, com o gatilho forjado, que e
    o unico jeito de mostrar que discrimina.
    """
    def chama(n_players):
        base = {'available': False, 'coverage_reason': 'pairing_uncovered',
                'scenario': 'faces_squeeze'}
        g._preenche_buraco_com_ring(base, (), dict(
            position='BB', hero_hand_type='JJ', stack_bb=20.0, action_taken='call',
            vs_position='SB', n_players=n_players))
        return base

    assert _com_acervo(_ACERVO, lambda: chama(2)).get('source') != 'gw_ring_har', \
        'carta de mesa cheia vazou para heads-up'
    # CONTROLE: com 8 jogadores o MESMO gatilho preenche — o guarda separa mesa, nao bloqueia tudo
    assert _com_acervo(_ACERVO, lambda: chama(8)).get('source') == 'gw_ring_har'


def _em_mesa(n, mao='72o', acao='call'):
    return _com_acervo(_ACERVO, lambda: analyze_preflop(
        position='BB', hero_hand_type=mao, stack_bb=20.0, action_taken=acao,
        facing_size=6.5, vs_position='SB', facing_raises=2, hero_was_aggressor=False,
        facing_to_bb=6.5, n_players=n))


def test_carta_de_outra_mesa_nao_acusa_criticamente():
    """No GW gratuito so ha 8-max, e o acervo esta espalhado (41 decisoes em mesa de 8, 30 em 7,
    16 em 6, 11 em 9). A politica sai da ASSIMETRIA: hoje estas decisoes sao NULL, entao absolver
    com carta aproximada e aditivo, e acusar CRITICAMENTE com ela e dano que o buraco nao causava.

    distancia 0 -> normal | distancia 1 -> gradua marcado, sem veredito duro | 2+ -> nao usa.
    """
    exata = _em_mesa(8)
    assert exata['source'] == 'gw_ring_har'
    assert exata['action_quality'] == 'major_leak', '72o pagando squeeze e leak na mesa certa'
    assert 'ring_mesa_aproximada' not in exata

    for n in (7, 9):
        ap = _em_mesa(n)
        assert ap['source'] == 'gw_ring_har_aprox', (n, ap.get('source'))
        assert ap['action_quality'] == 'gto_minor_deviation', (n, ap['action_quality'])
        assert ap['ring_mesa_aproximada'] == {'carta': 8, 'decisao': n}

    # mesa distante: nem gradua
    for n in (6, 5):
        r = _em_mesa(n)
        assert r['available'] is False, (n, r.get('source'))
        assert r.get('coverage_reason') == 'pairing_uncovered'


def test_aproximada_ainda_absolve_normalmente():
    """O rebaixamento e so do veredito DURO. Mao que a carta aprova segue aprovada — senao a
    aproximacao viraria ruido em vez de informacao."""
    r = _em_mesa(7, mao='JJ', acao='call')
    assert r['available'] is True and r['source'] == 'gw_ring_har_aprox'
    assert r['action_quality'] == 'correct', r['action_quality']


def test_profundidade_distante_continua_null():
    """A janela de 25% vale igual aqui: nó de 20bb nao gradeia um spot de 40bb."""
    # 10bb e buraco E esta a 50% do no de 20.125. (Escolhi 40bb primeiro e o teste falhou: ali
    # JA existe carta, entao nem era buraco — a premissa e que estava errada, nao o motor.)
    r = _com_acervo(_ACERVO, lambda: _bb_vs_squeeze(stack=10.0))
    assert r['available'] is False and r.get('coverage_reason') == 'pairing_uncovered'
    # CONTROLE: dentro da janela, gradeia
    assert _com_acervo(_ACERVO, lambda: _bb_vs_squeeze(stack=22.0))['available'] is True


# ── "so absolve" no par SB x BB (decisao do dono, 15/08, com o experimento na mesa) ───────────
#
# BB vs open unico do SB (mesa inteira folda). O caso real que motivou: J6s 10bb pagou
# min-raise, a HEURISTICA acusou `small_mistake` (gto_label None — a carta nem respondia,
# `open_size_off_tree`), e o GW joga call ~97%.
_NODE_BB_VS_SB_OPEN = 'F-F-F-F-F-F-R2'
_ACERVO_SB_BB = {f'20.125|{_NODE_BB_VS_SB_OPEN}': _no('BB', _NODE_BB_VS_SB_OPEN, maos={
    'J6s': {'CALL 6.5': {'f': 0.97, 'ev': 0.4}, 'FOLD': {'f': 0.03, 'ev': 0.0}},
    '72o': {'FOLD': {'f': 1.0, 'ev': 0.0}, 'CALL 6.5': {'f': 0.0, 'ev': -0.3}},
    'A7o': {'RAISE 20.000': {'f': 1.0, 'ev': 2.1}, 'CALL 6.5': {'f': 0.0, 'ev': 1.2}},
})}

_KW_SB_BB = dict(position='BB', stack_bb=20.0, vs_position='SB', n_players=8)


def _absolve_direto(mao, acao, base):
    """Chama o gancho direto, com o gatilho forjado — o idioma do test_mesa_de_2: e o unico
    jeito de exercitar cada condicao sem depender do que a carta REAL do ambiente responde."""
    def roda():
        g._gw_ring_absolve(base, (), dict(_KW_SB_BB, hero_hand_type=mao, action_taken=acao))
        return base
    return _com_acervo(_ACERVO_SB_BB, roda)


def test_gw_absolve_buraco_que_a_heuristica_acusaria():
    """O caso J6s real: carta nao responde (off_tree) e o GW aprova o call — o buraco vira
    carta, com recomendacao/freqs/fonte viajando JUNTOS (um veredito absolvido com a
    recomendacao antiga seria card contraditorio)."""
    r = _absolve_direto('J6s', 'call',
                        {'available': False, 'coverage_reason': 'open_size_off_tree',
                         'scenario': 'vs_rfi'})
    assert r.get('available') is True, r
    assert r['source'] == 'gw_ring_har', r.get('source')
    assert r['action_quality'] == 'correct', r['action_quality']
    assert r['recommended_actions'][0] == 'call', r['recommended_actions']
    assert r.get('coverage_reason') is None


def test_gw_nao_gradeia_buraco_quando_acusaria():
    """A protecao dos 9 folds baratos: 72o pagou, o GW acusaria (call freq 0) — o buraco FICA
    buraco, a heuristica decide como antes. 'Carta vizinha absolve, nao acusa'."""
    base = {'available': False, 'coverage_reason': 'open_size_off_tree', 'scenario': 'vs_rfi'}
    r = _absolve_direto('72o', 'call', dict(base))
    assert r.get('available') is False, r
    assert r.get('source') != 'gw_ring_har'


def test_gw_absolve_acusacao_da_propria_carta():
    """Segundo gatilho: a carta atual respondeu ACUSANDO e o GW aprova — a acusacao cai."""
    r = _absolve_direto('J6s', 'call',
                        {'available': True, 'action_quality': 'major_leak',
                         'scenario': 'vs_rfi', 'recommended_actions': ['fold']})
    assert r['action_quality'] == 'correct', r['action_quality']
    assert r['source'] == 'gw_ring_har'
    assert r['recommended_actions'][0] == 'call'


def test_gw_discordando_sem_aprovar_nao_absolve():
    """A7o foldou; o GW manda RAISE (fold freq 0). Discordar da carta nao basta — absolver
    exige o GW dizer 'a jogada esta certa', nao apenas 'a carta esta errada'."""
    base = {'available': True, 'action_quality': 'major_leak', 'scenario': 'vs_rfi',
            'recommended_actions': ['call']}
    r = _absolve_direto('A7o', 'fold', base)
    assert r['action_quality'] == 'major_leak', r
    assert r.get('source') != 'gw_ring_har'


def test_gw_nao_toca_veredito_bom_nem_outro_par():
    """Carta aprovando (sem acusacao) o gancho nem olha; e par fora da lista deliberada
    (BB vs CO) fica exatamente como antes, mesmo com no valido no acervo."""
    bom = {'available': True, 'action_quality': 'correct', 'scenario': 'vs_rfi',
           'recommended_actions': ['call'], 'source': None}
    r = _absolve_direto('J6s', 'call', dict(bom))
    assert r == bom, r
    # outro par, pelo caminho publico
    no_co = _no('BB', 'F-F-F-F-R2-F-F')
    acervo = {'20.125|F-F-F-F-R2-F-F': no_co}
    kw = dict(position='BB', hero_hand_type='72o', stack_bb=20.0, action_taken='call',
              facing_size=2.0, vs_position='CO', facing_raises=1, hero_was_aggressor=False,
              facing_to_bb=2.0, n_players=8)
    antes = _com_acervo({}, lambda: analyze_preflop(**kw))
    depois = _com_acervo(acervo, lambda: analyze_preflop(**kw))
    for campo in ('action_quality', 'source', 'recommended_actions'):
        assert antes.get(campo) == depois.get(campo), (campo, antes.get(campo), depois.get(campo))


def test_gw_absolve_fiacao_no_caminho_publico():
    """O gancho esta ligado no analyze_preflop de verdade: 72o pagando min-raise do SB cai em
    off_tree na carta real (pre-requisito conferido), e com um no FORJADO em que o GW aprova o
    call, o caminho publico absolve de ponta a ponta."""
    kw = dict(position='BB', hero_hand_type='72o', stack_bb=20.0, action_taken='call',
              facing_size=2.0, vs_position='SB', facing_raises=1, hero_was_aggressor=False,
              facing_to_bb=2.0, n_players=8)
    antes = _com_acervo({}, lambda: analyze_preflop(**kw))
    assert antes.get('available') is False, ('pre-requisito: o spot precisa ser buraco', antes)
    acervo_aprova = {f'20.125|{_NODE_BB_VS_SB_OPEN}': _no('BB', _NODE_BB_VS_SB_OPEN, maos={
        '72o': {'CALL 6.5': {'f': 0.9, 'ev': 0.1}, 'FOLD': {'f': 0.1, 'ev': 0.0}}})}
    depois = _com_acervo(acervo_aprova, lambda: analyze_preflop(**kw))
    assert depois.get('available') is True and depois.get('source') == 'gw_ring_har', depois


def test_acervo_vazio_nao_muda_nada():
    """Enquanto nao houver captura, o motor tem que se comportar exatamente como antes."""
    antes = _com_acervo({}, _bb_vs_squeeze)
    depois = _com_acervo({}, _bb_vs_squeeze)
    assert antes.get('available') == depois.get('available')
    assert antes.get('coverage_reason') == depois.get('coverage_reason')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
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
