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

class _StubDB:
    """Isola as funções puras do banco: `plan_session` e `missions_with_state` leem tentativas
    e o trilho lento em runtime. `attempts` = {category_key: [tentativas]}."""

    def __init__(self, curriculum, attempts=None, proofs=None, boom=False):
        self.curriculum, self.attempts = curriculum, attempts or {}
        self.proofs, self.boom = proofs or [], boom

    def __enter__(self):
        import leaklab.progression as prog
        import database.repositories as repos
        self._prog, self._repos = prog, repos
        self._orig = (prog.build_curriculum, repos.get_progression_attempts,
                      repos.get_training_proof)
        prog.build_curriculum = lambda uid, days=90: self.curriculum

        def _att_of(uid, key, limit=30, since=None):
            if self.boom:
                raise RuntimeError("banco fora do ar")
            # `since` (corte de reabertura) zera a janela: o jogador re-prova a partir dali
            return [] if since else self.attempts.get(key, [])[:limit]

        repos.get_progression_attempts = _att_of
        repos.get_training_proof = lambda uid, **kw: self.proofs
        return self

    def __exit__(self, *exc):
        self._prog.build_curriculum = self._orig[0]
        self._repos.get_progression_attempts = self._orig[1]
        self._repos.get_training_proof = self._orig[2]
        return False


def _cat(key, pos, ev, n=28, scenario='rfi', stack=30):
    return {'key': key, 'scenario': scenario, 'position': pos, 'vs_position': '',
            'stack_bb': stack, 'ev_loss_bb': ev, 'n': n, 'weight': ev}


def _plano_fake(size='curta'):
    with _StubDB([_cat('rfi:SB::30', 'SB', 12.2)]):
        return plan_session(1, size=size)


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


def test_mao_postflop_nao_derruba_a_camada_de_progressao():
    """O bug mais caro do dia, e ele era invisível.

    `hand_class` foi escrita para hand_type (`'A5s'`, `'77'`), mas TODO spot postflop grava a mão
    em CARTAS CONCRETAS (`'KhQc'`). O segundo caractere vira naipe, `ordem.index('H')` levanta
    `ValueError`, e `concept_for_spot` explode junto.

    O estrago não era o texto sumindo da tela. Em `/player/leaktrainer/grade` a exceção aborta o
    bloco inteiro, e `record_progression_attempt` fica DEPOIS dela: **nenhuma tentativa de postflop
    era gravada na progressão**, e o gate ficava parado enquanto o jogador treinava. O XP é dado
    fora do `try`, então a tela parecia funcionar. Um `except Exception` genérico manteve isso em
    silêncio — é o zero tranquilizador da regra 1 do CLAUDE.md, em forma de exceção engolida.

    Por isso este teste cobra as duas coisas: a classificação certa E a promessa de nunca levantar.
    """
    # cartas concretas viram a família certa
    assert hand_class('KhQc') == hand_class('KQo') == 'broadway_offsuit'
    assert hand_class('5h5d') == hand_class('55') == 'par_baixo'
    assert hand_class('AhKh') == hand_class('AKs') == 'ace_suited'
    assert hand_class('QsJs') == 'broadway_suited'
    # ordem das cartas não importa: o rank alto vem primeiro
    assert hand_class('QcKh') == hand_class('KhQc')
    # e NUNCA levanta, seja qual for a entrada: quem chama está no caminho quente da correção
    for lixo in ('', None, 'x', 'xx', 'KhQ', 'ZZZZ', '10h9c', 'KhQcJd'):
        hand_class(lixo)
    print("OK  test_mao_postflop_nao_derruba_a_camada_de_progressao")


def test_concept_for_spot_sobrevive_a_spot_postflop():
    """`concept_for_spot` é chamado ANTES de gravar a tentativa. Se ele levanta, o gate não anda —
    e nada na tela denuncia."""
    spot = {'kind': 'postflop', 'street': 'flop', 'position': 'BB', 'vs_position': 'BTN',
            'stack_bb': 40, 'hand': 'KhQc', 'board': ['Ks', '6c', '7d']}
    c = concept_for_spot(spot, {'gto_tier': 'correct'})
    assert c and c.get('principio'), c
    # e para toda street e mão que o acervo serve
    for street in ('flop', 'turn', 'river'):
        for mao in ('KhQc', '5h5d', 'AhKh', '2d7c'):
            r = concept_for_spot({**spot, 'street': street, 'hand': mao}, {})
            assert r and r.get('principio'), (street, mao, r)
    print("OK  test_concept_for_spot_sobrevive_a_spot_postflop")


def test_contraste_fala_de_profundidade():
    """No spot de contraste a lição é o STACK. Se falasse de posição, o jogador não entenderia
    por que a profundidade mudou no meio da sessão."""
    c = concept_for_spot({'scenario': 'rfi', 'position': 'SB', 'stack_bb': 17, 'hand': '87s',
                          'block_kind': 'contrast', 'contrast_of': 30})
    assert c['gatilho'] == 'stack'
    assert '30bb' in c['principio'] and '17bb' in c['principio']
    print("OK  test_contraste_fala_de_profundidade")


# Reportado pelo jogador: o texto do contraste dizia "Mesmo spot, 10bb em vez de 17bb" e "a mesma
# mão pede outra linha". Ele leu como continuidade do exercício ANTERIOR, que não era parecido, e
# estranhou. As duas afirmações são falsas: a sessão é INTERCALADA (o anterior pode ser revisão de
# outra família) e a mão é sorteada de novo. O que de fato se repete é o CENÁRIO.
_CONTINUIDADE_PROIBIDA = ('mesmo spot', 'mesma mão', 'mesma mao', 'spot anterior',
                          'exercício anterior', 'exercicio anterior', 'como antes',
                          'de novo aquele', 'a mesma situação de antes')


def _sem_promessa_de_continuidade(texto: str, onde: str):
    baixo = (texto or '').lower()
    for frase in _CONTINUIDADE_PROIBIDA:
        assert frase not in baixo, (
            f'{onde} promete continuidade com o exercício anterior ("{frase}"), '
            f'e a sessão é intercalada: {texto!r}')


def test_contraste_nao_promete_continuidade_com_o_anterior():
    """Varre os DOIS textos do contraste e as duas ramificações de cada um.

    Nasceu de uma queixa concreta, e vale como regra: o contraste compartilha o cenário com a
    missão, e só isso. Prometer "mesmo spot" ou "a mesma mão" é afirmar algo que a ordem
    intercalada e o sorteio da mão não garantem.
    """
    spot = {'scenario': 'rfi', 'position': 'SB', 'stack_bb': 10, 'hand': '87s',
            'block_kind': 'contrast', 'contrast_of': 17}
    vistos = 0
    for grade in ({}, {'hand_freq': {'allin': 1.0}}, {'hand_freq': {'allin': 0.1}}):
        c = concept_for_spot(dict(spot), grade)
        _sem_promessa_de_continuidade(c['principio'], 'principio do contraste')
        vistos += 1
    nota = contrast_note(dict(spot))
    assert nota, 'contrast_note devolveu vazio: o teste passaria sem ler nada'
    _sem_promessa_de_continuidade(nota, 'contrast_note')
    # e o texto continua dizendo o que PRECISA dizer: as duas profundidades
    assert '10bb' in nota and '17bb' in nota, nota
    assert vistos == 3
    print("OK  test_contraste_nao_promete_continuidade_com_o_anterior")


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


def test_sizing_note_ensina_o_tamanho():
    """O dado carrega o sizing ('R2.1' = raise para 2,1bb) e o parser o descartava. ENSINAMOS o
    tamanho porque 0% dos 1.036 nós têm mais de um: virar pergunta seria decoreba de tabela."""
    from leaklab.progression import sizing_note
    n = sizing_note({'scenario': 'rfi', 'position': 'UTG', 'stack_bb': 100}, 2.1, 'raise')
    assert '2.1bb' in n and 'blinds' in n
    # SB abre maior, e o texto explica POR QUÊ (fora de posição), não só o número
    sb = sizing_note({'scenario': 'rfi', 'position': 'SB', 'stack_bb': 30}, 3.0, 'raise')
    assert '3bb' in sb and 'fora de posição' in sb
    assert sb != n
    print("OK  test_sizing_note_ensina_o_tamanho")


def test_sizing_note_ausente_quando_nao_ha_raise():
    """Sem tamanho a ensinar: fold, shove (a 14bb a linha é all-in, não raise-to) e sem dado."""
    from leaklab.progression import sizing_note
    base = {'scenario': 'rfi', 'position': 'BTN', 'stack_bb': 14}
    assert sizing_note(base, None, 'raise') is None          # sem tamanho no nó
    assert sizing_note(base, 2.0, 'allin') is None           # a linha é shove
    assert sizing_note(base, 2.0, 'fold') is None            # a linha é fold
    print("OK  test_sizing_note_ausente_quando_nao_ha_raise")


def test_sizing_por_cenario_difere():
    """3-bet e 4-bet têm lógicas de tamanho próprias — o texto não pode ser genérico."""
    from leaklab.progression import sizing_note
    tres = sizing_note({'scenario': 'vs_rfi', 'position': 'BB', 'stack_bb': 40}, 8.5, 'raise')
    quatro = sizing_note({'scenario': 'vs_3bet', 'position': 'CO', 'stack_bb': 50}, 14.3, 'raise')
    assert '3-bet' in tres and '8.5bb' in tres
    assert '4-bet' in quatro and '14.3bb' in quatro
    assert tres != quatro
    print("OK  test_sizing_por_cenario_difere")


# ── Leak de SIZING (dimensão própria) ─────────────────────────────────────────
# Um open de tamanho errado tem a AÇÃO certa, então o ev_loss da range é ~0 e o leak fica
# invisível ao diagnóstico normal. Estes testes travam os falsos positivos vistos em dado real.

def _mock_sizing_rows(monkeypatch_rows):
    import leaklab.progression as prog
    from database import repositories as repo
    orig = repo.get_open_sizing_rows
    repo.get_open_sizing_rows = lambda uid, days=90: monkeypatch_rows
    return orig


def test_sizing_mission_exige_padrao_nao_mao_avulsa():
    """Uma abertura grande é ruído; um HÁBITO é que custa fichas. Abaixo da amostra mínima
    não vira missão — senão o protocolo mandaria corrigir variância."""
    from database import repositories as repo
    from leaklab.progression import build_sizing_missions, SIZING_MIN_N
    orig = repo.get_open_sizing_rows
    try:
        # 3 aberturas monstruosas, mas amostra pequena → NÃO vira missão
        repo.get_open_sizing_rows = lambda uid, days=90: [
            {'position': 'UTG', 'stack_bb': 50.0, 'raise_to_bb': 5.0}] * 3
        assert build_sizing_missions(1) == []
        # amostra suficiente e padrão consistente → vira missão
        repo.get_open_sizing_rows = lambda uid, days=90: [
            {'position': 'UTG', 'stack_bb': 50.0, 'raise_to_bb': 5.0}] * SIZING_MIN_N
        ms = build_sizing_missions(1)
        assert len(ms) == 1 and ms[0]['direcao'] == 'grande'
        assert ms[0]['position'] == 'UTG' and ms[0]['tipo'] == 'sizing'
        assert 'acima' in ms[0]['diagnostico']
    finally:
        repo.get_open_sizing_rows = orig
    print("OK  test_sizing_mission_exige_padrao_nao_mao_avulsa")


def test_sizing_nao_acusa_quem_abre_certo():
    from database import repositories as repo
    from leaklab.progression import build_sizing_missions, SIZING_MIN_N
    orig = repo.get_open_sizing_rows
    try:
        repo.get_open_sizing_rows = lambda uid, days=90: [
            {'position': 'BTN', 'stack_bb': 50.0, 'raise_to_bb': 2.5}] * SIZING_MIN_N
        assert build_sizing_missions(1) == []
    finally:
        repo.get_open_sizing_rows = orig
    print("OK  test_sizing_nao_acusa_quem_abre_certo")


def test_sizing_ignora_shove_e_stack_curto():
    """Falso positivo visto em dado REAL: 'ACR UTG stack 10,2 abriu 10,14' foi contado como
    'open 5x maior que o GTO'. Era um SHOVE. E abaixo de ~20bb a decisão é entrar ou sair,
    não quanto apostar — os dois casos são excluídos na query."""
    import inspect
    from database import repositories as repo
    src = inspect.getsource(repo.get_open_sizing_rows)
    assert 'raise_to_bb < d.stack_bb * 0.9' in src, "shove não está sendo excluído"
    assert 'stack_bb >= 22' in src, "stack curto não está sendo excluído"
    print("OK  test_sizing_ignora_shove_e_stack_curto")


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


# ── Foco: o gate tem que ABRIR A PORTA ────────────────────────────────────────
# Regressão do bug de 2026-07-26: o gate acendia 5/5 e "Dominado no treino", e o jogador
# continuava sendo servido o MESMO leak — o foco era `missions[0]` (maior EV) em dois lugares
# independentes, e nenhum dos dois lia o estado.

def _att_dominado():
    """Tentativas que passam os 5 critérios (mesma composição do test_gate_completo_domina)."""
    return (_att(14, stratum='nucleo') + _att(5, stratum='lixo')
            + _att(5, stratum='fronteira') + _att(4, stratum='nucleo', block='contrast'))


def _dois_leaks():
    return [_cat('rfi:SB::30', 'SB', 12.2), _cat('rfi:UTG::30', 'UTG', 8.0)]


def test_foco_avanca_quando_o_leak_e_dominado():
    from leaklab.progression import missions_with_state
    with _StubDB(_dois_leaks(), attempts={'rfi:SB::30': _att_dominado()}):
        est = missions_with_state(1)
    assert est['ativa']['key'] == 'rfi:UTG::30', est['ativa']['key']
    assert [d['key'] for d in est['dominadas']] == ['rfi:SB::30']
    assert est['dominadas'][0]['estado'] == 'dominado_no_treino'
    assert est['restantes'] == 1
    print("OK  test_foco_avanca_quando_o_leak_e_dominado")


def test_plano_treina_a_missao_ativa_nao_a_de_maior_ev():
    """O coração do bug: avançar no painel sem avançar no drill seria pior que não avançar."""
    with _StubDB(_dois_leaks(), attempts={'rfi:SB::30': _att_dominado()}):
        p = plan_session(1, size='curta')
    assert p['mission']['key'] == 'rfi:UTG::30', p['mission']['key']
    assert p['modo'] == 'missao'
    assert p['blocks'][0]['category']['key'] == 'rfi:UTG::30'
    print("OK  test_plano_treina_a_missao_ativa_nao_a_de_maior_ev")


def test_tudo_dominado_vira_revisao_e_nao_sessao_vazia():
    """Sem leak em treino a sessão não pode acabar: o selo ainda depende do jogo real e é o
    SRS que impede o domínio de apodrecer."""
    att = {c['key']: _att_dominado() for c in _dois_leaks()}
    with _StubDB(_dois_leaks(), attempts=att):
        from leaklab.progression import missions_with_state
        est = missions_with_state(1)
        p = plan_session(1, size='curta')
    assert est['ativa'] is None and est['restantes'] == 0
    assert len(est['dominadas']) == 2
    assert p['modo'] == 'revisao' and p['total'] == SESSION_SIZES['curta']
    assert p['mission'] is not None
    print("OK  test_tudo_dominado_vira_revisao_e_nao_sessao_vazia")


def test_falha_de_leitura_nao_derruba_a_sessao():
    """Banco fora do ar na leitura de tentativas: cair no maior EV é ruim, não abrir sessão
    nenhuma é pior."""
    with _StubDB(_dois_leaks(), boom=True):
        p = plan_session(1, size='curta')
    assert p['mission']['key'] == 'rfi:SB::30'
    assert p['total'] == SESSION_SIZES['curta']
    print("OK  test_falha_de_leitura_nao_derruba_a_sessao")


def test_selo_do_jogo_real_aparece_no_estado():
    proof = [{'category_key': 'rfi:SB::30', 'confident': True, 'delta': 12}]
    with _StubDB(_dois_leaks(), attempts={'rfi:SB::30': _att_dominado()}, proofs=proof):
        from leaklab.progression import missions_with_state
        est = missions_with_state(1)
    assert est['dominadas'][0]['estado'] == 'comprovado_no_jogo'
    print("OK  test_selo_do_jogo_real_aparece_no_estado")


# ── Fase 3: o trilho lento manda no estado ────────────────────────────────────

def _proof(key, veredito, **kw):
    return [{'category_key': key, 'validacao': {'veredito': veredito}, **kw}]


def test_so_o_veredito_estatistico_sela():
    """Com `validacao` presente, a regra antiga (delta > 0 e amostra confiável) não vale mais:
    `sem_mudanca` é 'a amostra não permite afirmar', e selar isso seria mentir."""
    from leaklab.progression import missions_with_state
    for veredito, esperado in [('melhorou', 'comprovado_no_jogo'),
                               ('sem_mudanca', 'dominado_no_treino'),
                               ('sem_amostra', 'dominado_no_treino')]:
        pr = _proof('rfi:SB::30', veredito, confident=True, delta=12)   # delta ótimo de propósito
        with _StubDB(_dois_leaks(), attempts={'rfi:SB::30': _att_dominado()}, proofs=pr):
            est = missions_with_state(1)
        assert est['dominadas'][0]['estado'] == esperado, (veredito, est['dominadas'][0]['estado'])
    print("OK  test_so_o_veredito_estatistico_sela")


def test_regressao_no_jogo_reabre_o_leak_e_devolve_o_foco():
    """O gate existe pra prever o jogo. Quando o jogo diz o contrário, quem está errado é o
    gate — o leak volta a ser a missão ativa mesmo com os 5 critérios cumpridos."""
    from leaklab.progression import missions_with_state
    pr = _proof('rfi:SB::30', 'piorou', reopen_count=1, reopened_at='2026-07-26 12:00:00')
    with _StubDB(_dois_leaks(), attempts={'rfi:SB::30': _att_dominado()}, proofs=pr):
        est = missions_with_state(1)
    assert est['ativa']['key'] == 'rfi:SB::30', est['ativa']['key']
    assert est['ativa']['estado'] == 'em_treino'
    assert est['ativa']['reaberto'] is True
    assert est['dominadas'] == []
    print("OK  test_regressao_no_jogo_reabre_o_leak_e_devolve_o_foco")


def test_reabertura_zera_a_janela_do_gate():
    """A armadilha do desenho ingênuo: sem cortar a janela, o leak reabriria e 're-dominaria'
    no mesmo instante com tentativas que já não valem — ou pior, ficaria preso para sempre
    sendo reaberto pela mesma evidência antiga. O corte é o que fecha o laço."""
    from leaklab.progression import missions_with_state
    pr = _proof('rfi:SB::30', 'sem_amostra', reopen_count=1, reopened_at='2026-07-26 12:00:00')
    with _StubDB(_dois_leaks(), attempts={'rfi:SB::30': _att_dominado()}, proofs=pr):
        est = missions_with_state(1)
    ativa = est['ativa']
    assert ativa['key'] == 'rfi:SB::30' and ativa['estado'] == 'em_treino'
    assert ativa['mastery']['janela']['n'] == 0, "as tentativas pré-reabertura não podem contar"
    assert 'volume' in ativa['mastery']['faltando']
    print("OK  test_reabertura_zera_a_janela_do_gate")


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
    raise SystemExit(1 if failed else 0)
