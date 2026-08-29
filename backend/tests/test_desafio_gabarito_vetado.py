# -*- coding: utf-8 -*-
"""O desafio do dia grada pelo gabarito VETADO, nunca contra ele.

── O que originou (29/08) ──────────────────────────────────────────────────────────────────

O dono foldou 54o (LJ vs 3-bet do BB, 30bb) e o card disse "Não foi a melhor" — em cima de um
teaching que explicava, em dez linhas, por que fold é a jogada óbvia. O gabarito passa por 5
camadas (nó limpo, faixa de frequência, triangulação, voto adversarial de LLM, aprovação do
admin) e o `grade_challenge` jogava tudo fora e re-gradava ao vivo. Quando a fonte de
estratégia diverge entre a aprovação e o dia (dados diferentes entre ambientes), a tela
contradiz a si mesma. É a família lista×card de 26/08, num produto novo.

── As duas defesas, em ordem de força ──────────────────────────────────────────────────────

1. Spot novo SELA o mix aprovado no spot_json (`gto_strategy_vetada`) e o submit grada por
   ele. Fonte única com o teaching, por construção.
2. Spot antigo (todo o pool de prod) não tem o selo: vale o PISO — quem joga o `answer`
   vetado nunca é marcado errado, e a divergência vai para o log, não para a tela.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_TESTING', '1')

SPOT_BASE = {
    'scenario': 'vs_3bet', 'position': 'LJ', 'vs_position': 'BB', 'stack_bb': 30,
    'hand': '54o', 'hero_cards': [{'rank': '5', 'suit': 'h'}, {'rank': '4', 'suit': 'd'}],
    'options': ['fold', 'call', 'raise', 'allin'], 'is_3bet_pot': True,
    'hero_was_aggressor': True, 'facing_raises': 1, 'facing_size': 9.0,
}


def test_spot_SELADO_grada_pelo_mix_vetado():
    """Com o selo, a re-grade ao vivo nem é consultada: o veredito sai do mix aprovado."""
    from leaklab.daily_challenge import grade_challenge
    spot = dict(SPOT_BASE)
    # Um mix deliberadamente DIFERENTE do que o provider diria hoje: se o selo manda, o
    # veredito segue o selo. (allin 75/fold 20 — nenhum provider diria isso para 54o; 0.2 fica na
    # faixa co-otima: MIN_CREDITABLE 0.1 <= f < CORRECT_FREQ 0.3.)
    spot['gto_strategy_vetada'] = [{'action': 'allin', 'freq': 0.75}, {'action': 'fold', 'freq': 0.2}]
    r_all = grade_challenge(spot, 'allin')
    r_fold = grade_challenge(spot, 'fold')
    r_call = grade_challenge(spot, 'call')
    assert r_all['is_correct'] and not r_all['mixed'], 'a acao top do selo nao foi acerto pleno'
    assert r_fold['is_correct'] and r_fold['mixed'], 'a acao co-otima do selo nao foi Aceitavel'
    assert not r_call['is_correct'] and r_call['gto_tier'] == 'error', \
        'acao fora do selo passou -- o selo nao esta mandando'
    assert r_all['best_action'] == 'allin', 'best_action nao veio do selo'
    print('OK  test_spot_SELADO_grada_pelo_mix_vetado')


def test_spot_ANTIGO_piso_do_answer():
    """O caso do print: sem selo, jogar o `answer` vetado NUNCA e erro.

    Nao dependemos de reproduzir a divergencia de prod: forjamos a condicao com um answer que
    a re-grade condena em qualquer fonte (fold de AA no BTN) e exigimos que o piso mande."""
    from leaklab.daily_challenge import grade_challenge
    spot = {'scenario': 'rfi', 'position': 'BTN', 'vs_position': '', 'stack_bb': 40,
            'hand': 'AA', 'hero_cards': [{'rank': 'A', 'suit': 'h'}, {'rank': 'A', 'suit': 'd'}],
            'options': ['fold', 'raise', 'allin']}
    sem_piso = grade_challenge(spot, 'fold')
    assert not sem_piso['is_correct'], (
        'controle quebrado: a re-grade ao vivo NAO condena fold de AA no BTN -- este teste '
        'nao esta exercitando a divergencia e vira verde vazio')
    com_piso = grade_challenge(spot, 'fold', answer='fold')
    assert com_piso['is_correct'], 'jogador jogou o gabarito vetado e foi marcado errado'
    assert com_piso['gto_tier'] == 'correct'
    # 30/08, o dono pegou na tela: quem joga O GABARITO ve "Correto.", nao "Aceitavel" —
    # mixed=True afirmaria "o GTO mistura aqui" sem ninguem ter verificado.
    assert com_piso['mixed'] is False, 'o piso inventou uma mistura que ninguem verificou'
    assert com_piso['best_action'] == 'fold', 'best_action nao e o gabarito vetado'
    # E o mix da fonte DIVERGENTE nao pode ir para a tela como "Estrategia GTO".
    assert com_piso['gto_strategy'] == [], (
        'o card exibe a estrategia da politica que acabou de se provar errada: %s'
        % com_piso['gto_strategy'])
    assert com_piso['explanation'].startswith('Correto.'), com_piso['explanation']
    print('OK  test_spot_ANTIGO_piso_do_answer')


def test_o_piso_NAO_abencoa_outra_resposta():
    """CONTRAPROVA: o piso vale para o answer vetado, nao para qualquer acao. Sem isto o
    conserto silenciaria erro de verdade -- dano que o bug nao causava (regra 7)."""
    from leaklab.daily_challenge import grade_challenge
    spot = {'scenario': 'rfi', 'position': 'UTG', 'vs_position': '', 'stack_bb': 40,
            'hand': '72o', 'hero_cards': [{'rank': '7', 'suit': 'h'}, {'rank': '2', 'suit': 'd'}],
            'options': ['fold', 'raise', 'allin']}
    r = grade_challenge(spot, 'allin', answer='fold')
    assert not r['is_correct'], 'o piso do gabarito abencoou uma acao que NAO e o gabarito'
    print('OK  test_o_piso_NAO_abencoa_outra_resposta')


def test_a_divergencia_vai_para_o_LOG():
    """O piso silencioso esconderia o spot podre para sempre. O log e o que aciona a
    re-curadoria."""
    import logging
    from leaklab.daily_challenge import grade_challenge
    spot = {'scenario': 'rfi', 'position': 'BTN', 'vs_position': '', 'stack_bb': 40,
            'hand': 'AA', 'hero_cards': [{'rank': 'A', 'suit': 'h'}, {'rank': 'A', 'suit': 'd'}],
            'options': ['fold', 'raise', 'allin']}
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    log = logging.getLogger('leaklab.daily_challenge')
    log.addHandler(h)
    try:
        grade_challenge(spot, 'fold', answer='fold')
    finally:
        log.removeHandler(h)
    assert 'diverge do gabarito vetado' in buf.getvalue(), \
        'o piso corrigiu a tela mas nao avisou ninguem -- o spot podre fica no pool para sempre'
    print('OK  test_a_divergencia_vai_para_o_LOG')


def test_candidato_novo_NASCE_selado():
    """A defesa 1 por construcao: o que build_candidates grava carrega o mix vetado."""
    import json
    import random
    from leaklab import daily_challenge as dc
    cands = dc.build_candidates(1, rng=random.Random(3), with_explanation=False,
                                difficulty='facil', verify=False)
    if not cands:
        cands = dc.build_candidates(1, rng=random.Random(3), with_explanation=False,
                                    difficulty='dificil', verify=False)
    assert cands, 'build_candidates nao gerou nenhum candidato -- o teste nao mediu nada'
    spot = json.loads(cands[0]['spot_json'])
    selo = spot.get('gto_strategy_vetada')
    assert selo and isinstance(selo, list) and all('action' in s and 'freq' in s for s in selo), \
        'candidato novo nasceu sem o selo: o submit voltara a re-gradar ao vivo'
    print('OK  test_candidato_novo_NASCE_selado')



def test_revalidacao_aposenta_premissa_impossivel():
    """30/08, o caso de prod: candidato "LJ abriu 54o e levou 3-bet" nasceu ANTES do gate de
    premissa. A revalidacao tem que acha-lo no acervo e aposenta-lo — "certeza GTO" vale para
    o pool, nao so para o proximo candidato."""
    import json
    from database.schema import init_db
    init_db()
    from database.repositories import add_challenge_candidates, list_challenge_candidates
    from leaklab.daily_challenge import revalidar_pool
    ruim = dict(SPOT_BASE)                     # 54o LJ vs 3-bet: premissa impossivel
    add_challenge_candidates([{'spot_json': json.dumps(ruim), 'answer': 'fold',
                               'note': 'forjado pre-gate', 'difficulty': 'facil'}])
    forjado = max(c['id'] for c in list_challenge_candidates(status=None, limit=1000))
    r = revalidar_pool(aplicar=True)
    apos = {a['id']: a for a in r['aposentados']}
    assert forjado in apos, 'a revalidacao nao achou o candidato de premissa impossivel'
    assert 'premissa' in apos[forjado]['motivo'], apos[forjado]
    vivo = [c for c in list_challenge_candidates(status=None, limit=1000) if c['id'] == forjado]
    assert vivo and vivo[0]['status'] == 'retired_gto', 'reprovado continua sorteavel'
    print('OK  test_revalidacao_aposenta_premissa_impossivel')


def test_revalidacao_SELA_o_aprovado_e_dry_run_nao_escreve():
    """CONTRAPROVA dupla: quem passa ganha o selo (defesa 1 passa a valer para o acervo),
    e o dry-run mede sem escrever."""
    import json
    import random
    from database.schema import init_db
    init_db()
    from database.repositories import add_challenge_candidates, list_challenge_candidates
    from leaklab import daily_challenge as dc
    cands = dc.build_candidates(1, rng=random.Random(11), with_explanation=False,
                                difficulty='facil', verify=False)
    assert cands, 'sem candidato valido para o teste'
    spot = json.loads(cands[0]['spot_json'])
    spot.pop('gto_strategy_vetada', None)      # simula candidato antigo, sem selo
    add_challenge_candidates([{'spot_json': json.dumps(spot), 'answer': cands[0]['answer'],
                               'note': 'valido sem selo', 'difficulty': 'facil'}])
    alvo = max(c['id'] for c in list_challenge_candidates(status=None, limit=1000))

    dry = dc.revalidar_pool(aplicar=False)
    assert dry['dry_run'] is True
    sem_selo = [c for c in list_challenge_candidates(status=None, limit=1000) if c['id'] == alvo]
    assert 'gto_strategy_vetada' not in sem_selo[0]['spot_json'], 'dry-run ESCREVEU'

    r = dc.revalidar_pool(aplicar=True)
    assert r['selados'] >= 1, r
    com_selo = [c for c in list_challenge_candidates(status=None, limit=1000) if c['id'] == alvo]
    assert com_selo[0]['status'] != 'retired_gto', 'candidato valido foi aposentado'
    assert 'gto_strategy_vetada' in com_selo[0]['spot_json'], 'aprovado ficou sem o selo'
    print('OK  test_revalidacao_SELA_o_aprovado_e_dry_run_nao_escreve')



def test_agendado_aposentado_re_sorteia_SO_sem_tentativa():
    """30/08: a revalidacao aposentou o desafio JA AGENDADO de hoje. Regra: sem tentativa no
    dia, re-sorteia um aprovado; com tentativa gravada, mantem — trocar a pergunta debaixo de
    resposta gravada e dano que o bug nao causava (regra 7)."""
    import json
    import uuid
    from database.schema import init_db
    init_db()
    from database.repositories import (add_challenge_candidates, create_user,
                                       get_today_challenge, list_challenge_candidates,
                                       record_challenge_attempt, set_challenge_status)
    # dois candidatos: um bom (aprovado) e um que sera aposentado
    bom = {'scenario': 'rfi', 'position': 'BTN', 'vs_position': '', 'stack_bb': 40,
           'hand': 'A5s', 'hero_cards': [{'rank': 'A', 'suit': 'h'}, {'rank': '5', 'suit': 'h'}],
           'options': ['fold', 'raise', 'allin'],
           'gto_strategy_vetada': [{'action': 'raise', 'freq': 0.9}]}
    add_challenge_candidates([
        {'spot_json': json.dumps(dict(SPOT_BASE)), 'answer': 'fold', 'difficulty': 'facil'},
        {'spot_json': json.dumps(bom), 'answer': 'raise', 'difficulty': 'facil'},
    ])
    ids = sorted(c['id'] for c in list_challenge_candidates(status=None, limit=1000))[-2:]
    ruim_id, bom_id = ids[0], ids[1]
    set_challenge_status(ruim_id, 'approved')
    set_challenge_status(bom_id, 'approved')

    dia1 = 'T1-' + uuid.uuid4().hex[:6]
    ag = get_today_challenge(dia1)             # agenda o LRU (o ruim, id menor nunca usado)
    assert ag and ag['id'] == ruim_id, (ag, ruim_id)
    set_challenge_status(ruim_id, 'retired_gto')   # a revalidacao aposenta DEPOIS de agendado

    # sem tentativa: re-sorteia o aprovado
    novo = get_today_challenge(dia1)
    assert novo and novo['id'] == bom_id, 'agendado aposentado sem tentativa nao foi trocado: %s' % novo

    # com tentativa gravada: MANTEM mesmo aposentado
    dia2 = 'T2-' + uuid.uuid4().hex[:6]
    set_challenge_status(ruim_id, 'approved')
    ag2 = get_today_challenge(dia2)
    servido = ag2['id']
    u = create_user('resp_' + uuid.uuid4().hex[:8], 'r%s@t.local' % uuid.uuid4().hex[:8], 'x' * 12)
    record_challenge_attempt(u, dia2, 'fold', 'correct', True)
    set_challenge_status(servido, 'retired_gto')
    mantido = get_today_challenge(dia2)
    assert mantido and mantido['id'] == servido, (
        'trocou a pergunta debaixo de resposta gravada: %s' % mantido)
    print('OK  test_agendado_aposentado_re_sorteia_SO_sem_tentativa')


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
