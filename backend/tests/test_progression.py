"""
Testes do Protocolo de Progressão (leaklab/progression.py) — missões, plano de sessão e a
camada didática. Funções puras + um plano montado com currículo injetado (sem DB).
"""
import sys, os, random, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.progression import (
    build_missions, mission_title, neighbor_category, plan_session, next_spot_for_plan,
    concept_for_spot, contrast_note, hand_class, SESSION_SIZES, MIX_ACTIVE, MIX_CONTRAST,
    stratum_of, mastery_status, state_for, MASTERY_MIN_N, MASTERY_WINDOW,
)
from leaklab.leak_trainer import _STACKS


# ── Missões (PIP) ─────────────────────────────────────────────────────────────

def test_mission_title_legivel():
    assert mission_title({'scenario': 'rfi', 'position': 'SB', 'stack_bb': 30}) == "Abertura de SB · 30bb"
    assert mission_title({'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'CO',
                          'stack_bb': 40}) == "Defesa de BB vs abertura de CO · 40bb"
    assert "3-bet" in mission_title({'scenario': 'vs_3bet', 'position': 'CO',
                                     'vs_position': 'BTN', 'stack_bb': 50})
    print("OK  test_mission_title_legivel")


def test_missions_ordenam_por_ev_ponderado(monkey=None):
    """Amostra pequena NUNCA lidera o plano: um leak de −21bb em 3 mãos pode ser variância;
    −11bb em 13 mãos é padrão. Ordenar por bb bruto colocaria o ruído no topo e o jogador
    passaria 30 dias corrigindo algo que não existe."""
    import leaklab.progression as prog
    fake = [
        {'key': 'rfi:UTG::30', 'scenario': 'rfi', 'position': 'UTG', 'vs_position': '',
         'stack_bb': 30, 'ev_loss_bb': 21.0, 'n': 3, 'weight': 21.0},          # ruído
        {'key': 'vs_rfi:BB:CO:40', 'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'CO',
         'stack_bb': 40, 'ev_loss_bb': 11.5, 'n': 13, 'weight': 11.5},         # padrão
    ]
    orig = prog.build_curriculum
    prog.build_curriculum = lambda uid, days=90: fake
    try:
        ms = build_missions(1)
        assert ms[0]['key'] == 'vs_rfi:BB:CO:40', [m['key'] for m in ms]
        assert ms[0]['confianca'] == 'alta' and ms[1]['confianca'] == 'baixa'
        # o EV bruto do ruído é maior, mas o ponderado o derruba
        assert ms[1]['ev_loss_bb'] > ms[0]['ev_loss_bb']
        assert ms[1]['ev_ponderado'] < ms[0]['ev_ponderado']
    finally:
        prog.build_curriculum = orig
    print("OK  test_missions_ordenam_por_ev_ponderado")


# ── Discriminação ─────────────────────────────────────────────────────────────

def test_contraste_vai_para_o_mais_curto():
    """O contraste tem que ir pro stack CURTO: aprofundar quase não muda a estratégia
    (30 e 50bb jogam parecido), encurtar VIRA a resposta — e é a virada que ensina."""
    n = neighbor_category({'scenario': 'rfi', 'position': 'SB', 'vs_position': '', 'stack_bb': 30})
    assert n['stack_bb'] < 30, n['stack_bb']
    assert n['stack_bb'] in _STACKS
    assert n['_contrast_of'] == 30
    assert n['key'].endswith(f":{n['stack_bb']}")
    print(f"OK  test_contraste_vai_para_o_mais_curto (30 → {n['stack_bb']}bb)")


def test_contraste_no_stack_minimo_sobe():
    """No degrau mais curto não há pra onde encurtar: sobe em vez de devolver None."""
    n = neighbor_category({'scenario': 'rfi', 'position': 'BTN', 'vs_position': '',
                           'stack_bb': _STACKS[0]})
    assert n is not None and n['stack_bb'] > _STACKS[0]
    print("OK  test_contraste_no_stack_minimo_sobe")


# ── Plano de sessão ───────────────────────────────────────────────────────────

def _plano_fake(size='curta'):
    import leaklab.progression as prog
    fake = [{'key': 'rfi:SB::30', 'scenario': 'rfi', 'position': 'SB', 'vs_position': '',
             'stack_bb': 30, 'ev_loss_bb': 12.2, 'n': 28, 'weight': 12.2}]
    orig = prog.build_curriculum
    prog.build_curriculum = lambda uid, days=90: fake
    try:
        return plan_session(1, size=size)
    finally:
        prog.build_curriculum = orig


def test_plano_soma_o_tamanho_pedido():
    """A sessão TEM forma: o total bate com o tamanho escolhido (grind infinito cansa)."""
    for size, esperado in SESSION_SIZES.items():
        p = _plano_fake(size)
        assert p['total'] == esperado, (size, p['total'], esperado)
    print("OK  test_plano_soma_o_tamanho_pedido")


def test_plano_tem_missao_unica_e_contraste():
    """Um leak ativo por vez (foco) + fatia de discriminação (transferência)."""
    p = _plano_fake('media')
    assert p['mission']['key'] == 'rfi:SB::30'
    kinds = [b['kind'] for b in p['blocks']]
    assert kinds.count('active') == 1, kinds
    assert 'contrast' in kinds, kinds
    contraste = next(b for b in p['blocks'] if b['kind'] == 'contrast')
    assert contraste['category']['stack_bb'] != 30
    print("OK  test_plano_tem_missao_unica_e_contraste")


def test_sem_revisao_o_espaco_vai_pra_missao():
    """Sem histórico não se inventa revisão — melhor treinar o que importa."""
    p = _plano_fake('curta')
    assert not any(b['kind'] == 'review' for b in p['blocks'])
    ativo = next(b for b in p['blocks'] if b['kind'] == 'active')
    # o espaço da revisão foi absorvido pela missão
    assert ativo['n'] > round(SESSION_SIZES['curta'] * MIX_ACTIVE)
    print("OK  test_sem_revisao_o_espaco_vai_pra_missao")


def test_sessao_intercala_de_verdade():
    """Interleaving real: o contraste não fica todo no fim. Prática blocada gera domínio
    aparente que não transfere."""
    p = _plano_fake('media')
    rng = random.Random(3)
    done, ordem = {}, []
    for _ in range(p['total']):
        sp = next_spot_for_plan(p, done, rng)
        if not sp:
            break
        done[sp['block_kind']] = done.get(sp['block_kind'], 0) + 1
        ordem.append(sp['block_kind'])
    assert 'contrast' in ordem, ordem
    # o 1º contraste aparece antes do último terço da sessão
    assert ordem.index('contrast') < len(ordem) * 0.8, ordem
    print(f"OK  test_sessao_intercala_de_verdade ({ordem.count('contrast')} contrastes)")


# ── Camada didática ───────────────────────────────────────────────────────────

def test_sb_rfi_nao_fala_de_jogadores_atras():
    """Regressão de conteúdo: do SB só o BB está atrás. O texto genérico de RFI ('quantos
    jogadores ainda podem te enfrentar') seria FALSO ali — e feedback falso destrói confiança."""
    c = concept_for_spot({'scenario': 'rfi', 'position': 'SB', 'stack_bb': 30, 'hand': 'A5s'})
    assert 'BB está atrás' in c['principio'], c['principio']
    assert 'vários jogadores' not in c['principio']
    # e a posição não-blind mantém o texto de gente atrás
    c2 = concept_for_spot({'scenario': 'rfi', 'position': 'UTG', 'stack_bb': 30, 'hand': 'A5s'})
    assert 'atrás' in c2['principio']
    print("OK  test_sb_rfi_nao_fala_de_jogadores_atras")


def test_contraste_fala_de_profundidade():
    """No spot de contraste a lição é o STACK. Se falasse de posição, o jogador não entenderia
    por que a profundidade mudou no meio da sessão."""
    c = concept_for_spot({'scenario': 'rfi', 'position': 'SB', 'stack_bb': 17, 'hand': '87s',
                          'block_kind': 'contrast', 'contrast_of': 30})
    assert c['gatilho'] == 'stack'
    assert '30bb' in c['principio'] and '17bb' in c['principio']
    print("OK  test_contraste_fala_de_profundidade")


def test_stack_curto_manda_no_gatilho():
    c = concept_for_spot({'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'SB',
                          'stack_bb': 12, 'hand': 'A7o'}, {'hand_freq': {'allin': 1.0}})
    assert c['gatilho'] == 'stack'
    assert 'shove' in c['principio'].lower() or 'decide agora' in c['principio']
    print("OK  test_stack_curto_manda_no_gatilho")


def test_mao_mista_ensina_a_misturar():
    c = concept_for_spot({'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'CO',
                          'stack_bb': 40, 'hand': 'KTs'}, {'mixed': True})
    assert c['gatilho'] == 'fronteira'
    assert 'SEMPRE a mesma' in c['principio']
    print("OK  test_mao_mista_ensina_a_misturar")


def test_nota_da_mao_varia_por_classe():
    """A parte VARIÁVEL do feedback: sem ela o jogador lê a mesma frase 10x e para de prestar
    atenção (a fadiga que o protocolo existe pra evitar)."""
    base = {'scenario': 'rfi', 'position': 'SB', 'stack_bb': 30}
    notas = {concept_for_spot({**base, 'hand': h})['nota_mao']
             for h in ('77', 'AKs', 'JTo', '65s', '92o')}
    assert len(notas) >= 4, notas
    print(f"OK  test_nota_da_mao_varia_por_classe ({len(notas)} notas distintas)")


def test_hand_class():
    assert hand_class('AA') == 'par_alto'
    assert hand_class('77') == 'par_baixo'
    assert hand_class('A5s') == 'ace_suited'
    assert hand_class('A5o') == 'ace_offsuit'
    assert hand_class('KQs') == 'broadway_suited'
    assert hand_class('JTo') == 'broadway_offsuit'
    assert hand_class('76s') == 'conector_suited'
    assert hand_class('92o') == 'lixo'
    print("OK  test_hand_class")


def test_conector_suited_curto_perde_implied_odds():
    """Par conceito×profundidade: o mesmo conector muda de sentido quando o stack encurta."""
    fundo = concept_for_spot({'scenario': 'rfi', 'position': 'BTN', 'stack_bb': 50, 'hand': '76s'})
    curto = concept_for_spot({'scenario': 'rfi', 'position': 'BTN', 'stack_bb': 12, 'hand': '76s'})
    assert 'implied odds' in fundo['nota_mao']
    assert 'implied odds' in curto['nota_mao'] and '12bb' in curto['nota_mao']
    assert fundo['nota_mao'] != curto['nota_mao']
    print("OK  test_conector_suited_curto_perde_implied_odds")


def test_contrast_note_explica_a_troca():
    n = contrast_note({'stack_bb': 17, 'contrast_of': 30})
    assert n and '30bb' in n and '17bb' in n
    assert contrast_note({'stack_bb': 30}) is None
    print("OK  test_contrast_note_explica_a_troca")


# ── Estratos e gate de domínio (Fase 2) ───────────────────────────────────────

def test_stratum_of():
    """Onde a mão cai na range. Acertar 90% foldando lixo NÃO é domínio — por isso o gate
    precisa saber o estrato, não só o acerto."""
    assert stratum_of({'hand_freq': {'raise': 1.0}}) == 'nucleo'
    assert stratum_of({'hand_freq': {'fold': 0.95, 'raise': 0.05}}) == 'lixo'
    assert stratum_of({'hand_freq': {'raise': 0.55, 'call': 0.45}}) == 'fronteira'
    assert stratum_of({'hand_freq': {'allin': 0.9}}) == 'nucleo'
    assert stratum_of(None) == 'sem_dado'
    print("OK  test_stratum_of")


def _att(n, correct=True, stratum='nucleo', block='active'):
    return [{'stratum': stratum, 'block_kind': block, 'correct': correct} for _ in range(n)]


def test_gate_exige_volume():
    ms = mastery_status(_att(5))
    assert not ms['dominado'] and 'volume' in ms['faltando']
    print("OK  test_gate_exige_volume")


def test_gate_exige_amplitude_nao_so_a_parte_facil():
    """Só lixo, 100% de acerto, volume ok — e MESMO ASSIM não domina: o jogador provou que
    sabe foldar, não que domina a range."""
    ms = mastery_status(_att(25, stratum='lixo'))
    assert not ms['dominado']
    assert 'amplitude' in ms['faltando'] or 'fronteira' in ms['faltando']
    print("OK  test_gate_exige_amplitude_nao_so_a_parte_facil")


def test_gate_exige_fronteira_e_transferencia():
    """Núcleo + lixo perfeitos não bastam: falta a fronteira (onde se erra) e o contraste
    (que prova que não decorou)."""
    ms = mastery_status(_att(15, stratum='nucleo') + _att(10, stratum='lixo'))
    assert not ms['dominado']
    assert 'fronteira' in ms['faltando'] and 'transferencia' in ms['faltando']
    print("OK  test_gate_exige_fronteira_e_transferencia")


def test_gate_completo_domina():
    att = (_att(14, stratum='nucleo') + _att(5, stratum='lixo')
           + _att(5, stratum='fronteira') + _att(4, stratum='nucleo', block='contrast'))
    ms = mastery_status(att)
    assert ms['dominado'], ms['faltando']
    assert ms['janela']['n'] >= MASTERY_MIN_N
    print("OK  test_gate_completo_domina")


def test_gate_usa_janela_movel():
    """A janela é MÓVEL: erro antigo sai de cena quando o jogador melhora (senão o domínio
    ficaria refém de um dia ruim de semanas atrás)."""
    # a janela é MASTERY_WINDOW: as recentes têm que preenchê-la inteira pra as antigas saírem
    recentes = (_att(17, stratum='nucleo') + _att(5, stratum='fronteira')
                + _att(4, stratum='nucleo', block='contrast') + _att(4, stratum='lixo'))
    assert len(recentes) == MASTERY_WINDOW
    antigos  = _att(40, correct=False, stratum='nucleo')
    ms = mastery_status(recentes + antigos)          # ordem: mais novo → mais velho
    assert ms['janela']['n'] == MASTERY_WINDOW
    assert ms['dominado'], ms['faltando']
    print("OK  test_gate_usa_janela_movel")


def test_criterios_sao_transparentes():
    """O gate mostra o que falta. Barra sem critério visível vira mistério e o jogador desiste."""
    ms = mastery_status(_att(8))
    for c in ms['criterios']:
        assert {'key', 'ok', 'atual', 'alvo', 'label', 'desc'} <= set(c), c
    assert len(ms['criterios']) == 5
    print("OK  test_criterios_sao_transparentes")


# ── Os 3 estados ──────────────────────────────────────────────────────────────

def test_estado_em_treino():
    assert state_for({'dominado': False}) == 'em_treino'
    print("OK  test_estado_em_treino")


def test_treino_sozinho_nunca_comprova():
    """O SELO exige o jogo real. Domínio no treino libera o próximo leak, não declara correção
    — é o que separa isto de um simulador."""
    assert state_for({'dominado': True}) == 'dominado_no_treino'
    assert state_for({'dominado': True}, {'confident': False, 'delta': 30}) == 'dominado_no_treino'
    # amostra confiável mas SEM melhora também não comprova
    assert state_for({'dominado': True}, {'confident': True, 'delta': -5}) == 'dominado_no_treino'
    print("OK  test_treino_sozinho_nunca_comprova")


def test_estado_comprovado_exige_jogo_real_com_amostra():
    assert state_for({'dominado': True}, {'confident': True, 'delta': 12}) == 'comprovado_no_jogo'
    print("OK  test_estado_comprovado_exige_jogo_real_com_amostra")


def test_contraste_conta_pra_missao_nao_pra_vizinha():
    """Regressão: o spot de contraste é de OUTRA profundidade, então `category` é da família
    vizinha. Sem `mission_key`, a tentativa caía na categoria errada e o critério de
    Transferência ficava eternamente em 0."""
    p = _plano_fake('media')
    rng = random.Random(9)
    achou = False
    for _ in range(p['total']):
        sp = next_spot_for_plan(p, {}, rng)
        if sp and sp.get('block_kind') == 'contrast':
            assert sp.get('mission_key') == p['mission']['key'], sp.get('mission_key')
            assert sp['category'] != sp['mission_key']     # é mesmo outra família
            achou = True
            break
    assert achou, "nenhum spot de contraste gerado"
    print("OK  test_contraste_conta_pra_missao_nao_pra_vizinha")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
