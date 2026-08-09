# -*- coding: utf-8 -*-
"""Uma decisao so pode ser gradeada pelo NO que a descreve — senao, null honesto.

Tres defeitos da mesma familia, achados em 09/08. Em todos, a porta unica respondia com
confianca usando uma carta que modela OUTRO spot:

  A. Mesa cheia enfrentando ALL-IN. `vs_RFI[opener][defender]` e a defesa contra um open de 2 a
     3,5bb — e o proprio no declara isso em `preflop_actions`. Nao existe no de open-jam em mesa
     cheia (varredura: 324 de 324 nos declaram open pequeno). Pagar um shove de 14bb com J9o saia
     "Correto / GTO joga Call 100%", identico ao veredito de um open de 2bb. Medido com eval7
     contra a propria range de ABERTURA do vilao (mais larga que a de jam, logo conservadora a
     favor do hero): J9o a 14bb vs UTG tem 31,1% e precisa de 45,6%. Call de −2 a −3bb absolvido.

  B. Heads-up, 3-bet de qualquer tamanho. O no `SB_VS_3BET` modela UM tamanho por profundidade
     (`R2-R6` a 40bb) e o roteador so separava jam de nao-jam. Um 3-bet real de 25bb era gradeado
     pela estrategia de pagar 6bb; a 26,5bb — 1,5bb a mais, agora acima do limiar de jam — o MESMO
     fold trocava de veredito. O guarda de tamanho ja existia no ramo IRMAO (BB vs open) e faltava
     aqui.

  C. Mao OFF-TREE lida como "fold 100%". Nas secoes vs_3bet/faces_squeeze/squeeze/vs_4bet o no so
     e alcancado pela range de ABERTURA do hero. A 10bb o GW jama KK, nao min-raisa — entao KK nao
     aparece em lista nenhuma do no de vs_3bet, nem em `fold_hands`. O codigo tratava a ausencia
     como fold puro (o comentario dizia "GW so popula maos com acao nao-fold", o que e FALSO:
     `fold_hands` e populado a parte). Resultado: o produto dava `correct` a quem FOLDOU KK a um
     3-bet all-in e `major_leak` a quem pagou — com o selo de −7,3bb impresso ao lado do
     "Correto", porque `leaklab_gto_evs.json` publica KK = {'F': 0.0, 'C': 7.27}. Duas fontes para
     o mesmo fato, contradizendo-se no mesmo card.

Cada teste tem CONTROLE: o caso vizinho que continua sendo gradeado. Guarda que so prova ausencia
nao prova que a linha ficou no lugar certo.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import (analyze_preflop, _raise_declarado_bb,  # noqa: E402
                                        _tamanho_cabe_no_no, _direcao_do_tamanho,
                                        _veredito_sobrevive_ao_tamanho, _load)


def _ring(**kw):
    base = dict(n_players=9, facing_raises=1, vs_position='UTG')
    base.update(kw)
    return analyze_preflop(**base)


# ── A. mesa cheia vs all-in ────────────────────────────────────────────────────────────────────

def test_A_nenhum_no_vs_RFI_modela_open_jam():
    """O premissa do conserto, medida na base — nao afirmada em comentario."""
    total = jam = 0
    for _bk, bd in _load()['ranges'].items():
        for _op, od in (bd.get('vs_RFI') or {}).items():
            for _de, no in (od or {}).items():
                if not isinstance(no, dict) or 'preflop_actions' not in no:
                    continue
                total += 1
                if 'RAI' in (no.get('preflop_actions') or ''):
                    jam += 1
    assert total >= 300, f'a varredura achou so {total} nos vs_RFI — o formato mudou'
    assert jam == 0, (
        f'{jam} nos vs_RFI passaram a modelar open-jam; o guarda de cobertura precisa saber disso')


def test_A_pagar_open_shove_em_mesa_cheia_nao_tem_gabarito():
    for mao, stack, to in (('J9o', 14.0, 14.0), ('96s', 20.0, 20.0), ('T9o', 20.0, 20.0)):
        r = _ring(position='BB', hero_hand_type=mao, stack_bb=stack, action_taken='call',
                  facing_size=to, facing_to_bb=to, facing_allin=True)
        assert r['available'] is False, f'{mao} vs shove {to}bb foi gradeado: {r}'
        assert r.get('coverage_reason') == 'open_jam_uncovered', r.get('coverage_reason')


def test_A_CONTROLE_open_normal_segue_gradeado():
    """Se o guarda comesse o open pequeno tambem, a cobertura de mesa cheia desapareceria."""
    r = _ring(position='BB', hero_hand_type='J9o', stack_bb=14.0, action_taken='call',
              facing_size=2.0, facing_to_bb=2.0, facing_allin=False)
    assert r['available'] is True and r['action_quality'] == 'correct', r


def test_A_CONTROLE_vilao_muito_curto_cujo_jam_CABE_no_no_segue_gradeado():
    """Jam de 2bb num no que modela open de 2bb: o tamanho e o mesmo, o preco e o mesmo. Aqui o
    honesto e gradear — o guarda pergunta pelo TAMANHO, nao pela palavra 'all-in'."""
    r = _ring(position='BB', hero_hand_type='J9o', stack_bb=3.0, action_taken='call',
              facing_size=2.0, facing_to_bb=2.0, facing_allin=True)
    assert r['available'] is True, r


def test_A_o_tamanho_vem_do_que_o_no_DECLARA():
    no = _load()['ranges']['14bb']['vs_RFI']['UTG']['BB']
    assert no.get('preflop_actions', '').startswith('R2'), no.get('preflop_actions')
    assert _raise_declarado_bb(no) == 2.0
    assert _tamanho_cabe_no_no(no, 2.0) is True
    assert _tamanho_cabe_no_no(no, 14.0) is False
    assert _tamanho_cabe_no_no(no, 0.0) is False, 'sem numero nao da para afirmar que cabe'


# ── A2. o teto de tamanho NAO e so para all-in, e e DIRECIONAL ─────────────────────────────────
# Bloqueio do QA de 09/08: `_tamanho_cabe_no_no` existia e so era consultado sob "e jam" (>=65%
# do stack). Reproduzido: BB/K9o/40bb vs CO enfrentando 2, 5 ou 20bb saia `correct` com o MESMO
# "GTO joga Call / Raise" — 10x o preco que o no modela — e a 26,5bb, 1,5bb acima do limiar de
# jam, o veredito sumia. Degrau no mesmo spot.
#
# O conserto NAO e teto seco. Medido no acervo local (1.688 decisoes preflop, 587 chegam a um no
# vs_RFI): 185 enfrentam tamanho fora da tolerancia e 59 ainda tinham veredito — mas 55 desses sao
# FOLDS que a carta tambem folda, e subir o preco so REFORCA um fold. Teto seco perderia 55
# vereditos certos para consertar 4. A regra direcional derruba so os que dependem do preco.

def _k9o(to, acao='call', mao='K9o', stack=40.0):
    return _ring(position='BB', hero_hand_type=mao, stack_bb=stack, action_taken=acao,
                 vs_position='CO', facing_size=to, facing_to_bb=to, facing_allin=False)


def test_A2_open_grande_nao_e_gradeado_pelo_no_de_open_pequeno():
    """O repro exato do bloqueio: pagar 20bb num no que modela 2bb saia `correct`."""
    for to in (3.0, 5.0, 10.0, 20.0):
        r = _k9o(to)
        assert r['available'] is False, f'K9o pagando {to}bb gradeado pelo no de 2bb: {r}'
        assert r.get('coverage_reason') in ('open_size_off_tree', 'open_jam_uncovered'), r


def test_A2_CONTROLE_o_tamanho_que_o_no_modela_segue_gradeado():
    """Sem este controle o guarda poderia ter comido a cobertura de vs_RFI inteira."""
    for to in (2.0, 2.5):
        r = _k9o(to)
        assert r['available'] is True and r['action_quality'] == 'correct', (to, r)
        assert 'call' in r['recommended_actions'], r


def test_A2_CONTROLE_fold_que_a_carta_TAMBEM_folda_mantem_veredito_a_qualquer_preco():
    """A assimetria que decidiu a politica: com a range do vilao fixa, subir o preco so pode
    tornar o FOLD mais certo. Tirar o veredito de 72o vs 20bb custaria cobertura sem comprar
    correcao nenhuma — sao 55 dos 59 casos do acervo."""
    for to in (2.0, 3.0, 5.0, 20.0, 26.5):
        r = _k9o(to, acao='fold', mao='72o')
        assert r['available'] is True, f'72o foldando vs {to}bb perdeu veredito: {r}'
        assert r['recommended_actions'] == ['fold'] and r['action_quality'] == 'correct', (to, r)


def test_A2_nao_ha_degrau_no_limiar_de_jam():
    """O sintoma: 20bb dava veredito e 26,5bb (>=65% do stack) nao. Os dois lados da fronteira
    tem que responder a mesma coisa — o que muda e o TAMANHO, nao a palavra 'all-in'."""
    for mao, acao in (('K9o', 'call'), ('72o', 'fold')):
        antes, depois = _k9o(20.0, acao=acao, mao=mao), _k9o(26.5, acao=acao, mao=mao)
        assert antes['available'] == depois['available'], (mao, antes, depois)


def test_A2_a_direcao_e_medida_nos_dois_sentidos():
    no = _load()['ranges']['40bb']['vs_RFI']['CO']['BB']
    assert _raise_declarado_bb(no) == 2.0
    assert _direcao_do_tamanho(no, 2.0) == 'dentro'
    assert _direcao_do_tamanho(no, 2.8) == 'dentro', 'a tolerancia e 1,4x, a mesma regua do projeto'
    assert _direcao_do_tamanho(no, 3.0) == 'maior'
    assert _direcao_do_tamanho(no, 1.0) == 'menor'
    assert _direcao_do_tamanho(no, 0.0) == 'indeterminado'
    assert _direcao_do_tamanho({}, 3.0) == 'indeterminado'


def test_A2_a_regra_de_sobrevivencia_e_o_espelho_de_si_mesma():
    """Preco MAIOR salva quem manda foldar; preco MENOR salva quem manda defender."""
    assert _veredito_sobrevive_ao_tamanho('maior', ['fold']) is True
    assert _veredito_sobrevive_ao_tamanho('maior', ['call'], 0.14, 1.3) is False
    assert _veredito_sobrevive_ao_tamanho('menor', ['call']) is True
    assert _veredito_sobrevive_ao_tamanho('menor', ['fold']) is False
    # dentro/indeterminado nao removem nada — o guarda so age quando sabe a direcao
    for d in ('dentro', 'indeterminado'):
        assert _veredito_sobrevive_ao_tamanho(d, ['fold']) is True
        assert _veredito_sobrevive_ao_tamanho(d, ['call']) is True
    # sem margem conhecida nao ha prova, entao nao ha veredito
    assert _veredito_sobrevive_ao_tamanho('maior', ['call'], None, 1.3) is False


def test_A2_a_margem_de_EV_e_que_salva_a_acusacao_nao_a_frequencia():
    """Um open maior torna defensavel o fold de uma mao marginal, mas NUNCA o de AA — suprimir ali
    apagaria acusacao certa. O criterio e a margem que a carta de EV publica sobre o fold, nao "e
    mao de value": pela frequencia, 22 que o no jama a 23bb cairia no mesmo grupo de AA, e acusar
    quem folda 22 contra um open de 4,7bb e justamente a falsa condenacao que este guarda evita."""
    assert _veredito_sobrevive_ao_tamanho('maior', ['raise'], 11.43, 1.3) is True
    assert _veredito_sobrevive_ao_tamanho('maior', ['jam'], 0.38, 2.7) is False
    for mao in ('AA', 'KK', 'QQ', 'AKs', '99'):
        r = _ring(position='BB', hero_hand_type=mao, stack_bb=30.0, action_taken='fold',
                  vs_position='CO', facing_size=3.3, facing_to_bb=3.3)
        assert r['available'] is True, f'{mao}: a acusacao sumiu — {r.get("coverage_reason")}'
        assert r['action_quality'] in ('leak', 'major_leak'), (mao, r['action_quality'])


def test_A2_CONTROLE_defesa_call_dominada_NAO_e_salva_pela_excecao():
    """O outro lado da regua: 75o o no defende com call 100%, entao vale o teto e nao a excecao.
    Sem este controle a excecao poderia ter engolido o guarda inteiro."""
    for acao in ('fold', 'call'):
        r = _ring(position='BB', hero_hand_type='75o', stack_bb=30.0, action_taken=acao,
                  vs_position='CO', facing_size=3.3, facing_to_bb=3.3)
        assert r['available'] is False, (acao, r)
        assert r.get('coverage_reason') == 'open_size_off_tree', r.get('coverage_reason')


# ── B. heads-up vs 3-bet ───────────────────────────────────────────────────────────────────────

def _hu_3bet(to, stack=40.0, mao='QTo', acao='fold'):
    return analyze_preflop(position='SB', hero_hand_type=mao, stack_bb=stack, action_taken=acao,
                           facing_size=to, vs_position='BB', n_players=2, facing_raises=1,
                           hero_was_aggressor=True, facing_to_bb=to)


def test_B_3bet_muito_maior_que_o_no_nao_tem_gabarito():
    for to in (15.0, 20.0, 25.0):
        r = _hu_3bet(to)
        assert r['available'] is False, f'3-bet de {to}bb gradeado pelo no de 6bb: {r}'
        assert r['scenario'] == 'hu_uncovered', r['scenario']


def test_B_CONTROLE_o_tamanho_que_o_no_modela_segue_gradeado():
    """`R2-R6` a 40bb e `R2-R4.5` a 16bb. Sem este controle o guarda poderia matar o no inteiro."""
    r40 = _hu_3bet(6.0)
    assert r40['available'] is True and r40['scenario'] == 'hu_vs_3bet', r40
    r16 = _hu_3bet(4.5, stack=16.0, mao='AJo')
    assert r16['available'] is True and r16['scenario'] == 'hu_vs_3bet', r16
    assert r16['action_quality'] == 'major_leak', 'foldar AJo a 3-bet pequeno a 16bb segue leak'


def test_B_CONTROLE_o_jam_continua_indo_para_o_no_de_jam():
    r = _hu_3bet(26.5)
    assert r['available'] is True and r['scenario'] == 'hu_vs_3bet_jam', r
    assert r['action_quality'] == 'correct'


def test_B_nao_ha_mais_degrau_no_meio_do_intervalo():
    """O sintoma que denunciou: 25bb e 26,5bb davam veredito OPOSTO no mesmo spot. Agora os dois
    lados da fronteira de jam ou tem cobertura coerente ou nao tem cobertura."""
    antes, depois = _hu_3bet(25.0), _hu_3bet(26.5)
    assert not (antes['available'] and antes['recommended_actions'] == ['call']
                and depois['recommended_actions'] == ['fold']), (antes, depois)


# ── C. mao off-tree ────────────────────────────────────────────────────────────────────────────

def _vs3bet(mao, acao):
    return analyze_preflop(position='CO', hero_hand_type=mao, stack_bb=10.0, action_taken=acao,
                           facing_size=9.0, vs_position='BB', n_players=8, facing_raises=1,
                           hero_was_aggressor=True, facing_to_bb=9.0)


def test_C_o_dado_cru_confirma_que_KK_esta_fora_de_TODAS_as_listas():
    """Sem isto o teste abaixo poderia estar medindo outra coisa."""
    from leaklab.preflop_gto_ranges import _expand_range
    no = _load()['ranges']['10bb']['vs_3bet']['CO']['BB']
    assert 'KK' not in (no.get('hand_freqs') or {})
    for k in ('fold_hands', 'call_hands', 'raise_hands', 'allin_hands'):
        assert 'KK' not in _expand_range(no.get(k, '') or ''), k
    # e o oraculo que ja mora no repositorio diz que foldar custa caro
    import json
    evs = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'docs',
                                      'leaklab_gto_evs.json'), encoding='utf-8'))
    kk = evs['ranges']['10bb']['vs_3bet']['CO']['BB']['KK']
    assert kk['C'] - kk['F'] > 1.0, kk


def test_C_mao_off_tree_nao_recebe_veredito():
    for acao in ('fold', 'call', 'jam'):
        r = _vs3bet('KK', acao)
        assert r['available'] is False, f'KK off-tree gradeada em {acao}: {r}'
        assert r.get('coverage_reason') == 'hand_out_of_node_range', r.get('coverage_reason')


def test_C_off_tree_nao_sai_com_ev_loss_ao_lado_de_um_veredito():
    """A contradicao que o card exibia: `correct` no mesmo payload que `ev_loss_bb = 7,27`."""
    r = _vs3bet('KK', 'fold')
    assert r.get('ev_loss_bb') is None, r.get('ev_loss_bb')
    assert r['action_quality'] == 'unknown', r['action_quality']


def test_C_CONTROLE_mao_no_no_segue_gradeada():
    """87s tem freq no no (F 56% / C 44%) — nada a ver com off-tree."""
    r = _vs3bet('87s', 'call')
    assert r['available'] is True and r['action_quality'] == 'correct', r


def test_C_CONTROLE_fold_puro_declarado_pelo_no_continua_sendo_fold():
    """97s esta em `fold_hands` e NAO esta em `hand_freqs`. E o caso que o codigo antigo acertava
    por acidente, e que o conserto tinha que preservar: aqui a carta REALMENTE manda foldar."""
    r = _vs3bet('97s', 'fold')
    assert r['available'] is True, r
    assert r['recommended_actions'] == ['fold'] and r['action_quality'] == 'correct', r


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
