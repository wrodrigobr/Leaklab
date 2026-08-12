# -*- coding: utf-8 -*-
"""O nó postflop iniciativa-aware: quem ABRIU leva a range de opener, esteja onde estiver.

── O defeito ──────────────────────────────────────────────────────────────────────────────────

`resolve_solver_ranges` nasceu para matar o confronto espelhado ("cada jogador recebia a range
do outro") — e o ramo SRP o mantinha, escondido numa suposição de INICIATIVA: "o IP abriu (RFI)
e o OOP pagou". Em SB-vs-BB (o SB abre e é OOP) e em UTG-abre-BTN-paga, a suposição inverte as
ranges dos dois jogadores. O parâmetro `opener` sempre esteve na assinatura; o ramo o ignorava.

Medido no acervo antes de mexer: **468 decisões postflop cobertas com o opener OOP** (32% da
população SRP coberta), 354 delas `solver_hand`, 47 acusações.

── As três pernas do conserto, e por que o fallback NÃO existe ────────────────────────────────

1. RANGES: o ramo SRP honra o `opener` (fonte única, os dois caminhos passam por ela).
2. HASH: spot 'oop_pfr' ganha chave própria (`_effective_pot_type`, a MESMA fonte única que já
   decidia '3bet'). Nó legado sob o hash antigo foi solvado com as ranges trocadas para esses
   spots — divergir o hash é o que impede servi-lo.
3. SEM FALLBACK: diferente do pote 3-bet (onde o nó SRP é aproximação), o legado aqui é o
   confronto ESPELHADO. 'oop_pfr' sem nó fica heurístico até o solve certo existir.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.gto_solver import _effective_pot_type, resolve_solver_ranges
from leaklab.gto_utils import compute_spot_hash


def test_SB_abre_vs_BB_o_opener_OOP_leva_a_range_de_RFI():
    """SB abre, BB paga: postflop o SB age primeiro (OOP) e o BB é IP. A suposição antiga dava
    a range de RFI ao BB (que só pagou) e a de call ao SB (que abriu)."""
    ip_r, oop_r, hero_ip = resolve_solver_ranges('SB', 'BB', 40.0, opener='SB')
    ip_inv, oop_inv, _ = resolve_solver_ranges('SB', 'BB', 40.0)   # sem opener: suposição legada
    assert hero_ip is False   # SB é OOP
    # Com o opener certo, as ranges TROCAM em relação à suposição legada.
    assert (ip_r, oop_r) != (ip_inv, oop_inv), (
        'honrar o opener não mudou nada — o ramo SRP segue ignorando o parâmetro')
    # E os PAPÉIS ficam certos, conferidos contra a fonte direta das ranges: o SB (opener, OOP)
    # leva a RFI DELE; o BB (caller, IP) leva o call-vs-RFI DELE contra o open do SB. Comparar
    # com a outra chamada trocando papéis seria ingênuo: a RFI de SB não é a RFI de BB.
    from leaklab.gto_solver import _captured_range_str, _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE
    esperada_oop = (_captured_range_str('SB', 40.0, 'rfi')
                    or _DEFAULT_RANGES.get('SB', _DEFAULT_RANGE_WIDE))
    esperada_ip = (_captured_range_str('BB', 40.0, 'call_vs_rfi', opener='SB')
                   or _DEFAULT_RANGES.get('BB', _DEFAULT_RANGE_WIDE))
    assert oop_r == esperada_oop, 'o opener OOP não recebeu a própria range de RFI'
    assert ip_r == esperada_ip, 'o caller IP não recebeu o call-vs-RFI contra o opener certo'
    print('OK  test_SB_abre_vs_BB_o_opener_OOP_leva_a_range_de_RFI')


def test_CONTROLE_BTN_abre_vs_BB_nada_muda():
    """Opener IP é a suposição histórica — com ou sem `opener`, o resultado é o mesmo."""
    com = resolve_solver_ranges('BB', 'BTN', 40.0, opener='BTN')
    sem = resolve_solver_ranges('BB', 'BTN', 40.0)
    assert com == sem, 'o caso majoritário mudou — o conserto vazou para onde não devia'
    print('OK  test_CONTROLE_BTN_abre_vs_BB_nada_muda')


def test_pot_type_efetivo_decide_oop_pfr():
    # SB abriu e está OOP → variante nova
    assert _effective_pot_type('', 'SB', '', 40.0, hero_pos='SB', vs_pos='BB') == 'oop_pfr'
    # visto do OUTRO jogador (hero BB, vilão SB abriu): mesma variante
    assert _effective_pot_type('', 'SB', '', 40.0, hero_pos='BB', vs_pos='SB') == 'oop_pfr'
    # BTN abriu e é IP → legado
    assert _effective_pot_type('', 'BTN', '', 40.0, hero_pos='BB', vs_pos='BTN') == ''
    # sem opener ou sem vilão → legado (não dá para afirmar iniciativa)
    assert _effective_pot_type('', '', '', 40.0, hero_pos='SB', vs_pos='BB') == ''
    assert _effective_pot_type('', 'SB', '', 40.0, hero_pos='SB', vs_pos='') == ''
    # pote 3-bet segue a régua própria e NÃO vira oop_pfr
    assert _effective_pot_type('3bet', 'SB', 'BB', 40.0, hero_pos='SB', vs_pos='BB') in ('3bet', '')
    print('OK  test_pot_type_efetivo_decide_oop_pfr')


def test_o_hash_diverge_do_legado_apenas_para_oop_pfr():
    base = dict(street='flop', position='SB', board=['2h', '7c', '9d'],
                hero_hand=['Ah', 'Kd'], hero_stack_bb=40.0, facing_size_bb=0.0)
    legado = compute_spot_hash(**base)
    oop = compute_spot_hash(**base, pot_type='oop_pfr')
    srp = compute_spot_hash(**base, pot_type='srp')
    assert oop != legado, 'oop_pfr caiu no hash legado — o nó espelhado seria servido'
    assert srp == legado, 'srp deixou de ser o hash legado — TODA cobertura existente órfã'
    print('OK  test_o_hash_diverge_do_legado_apenas_para_oop_pfr')


def test_o_motor_NAO_le_no_legado_num_spot_oop_pfr():
    """A leitura viva: num spot SB-abriu-OOP, o motor só consulta hashes da variante nova.
    Capturado com dublê no `get_gto_node` — o que se testa é QUAIS chaves ele pede."""
    import database.repositories as repo
    import leaklab.decision_engine_v11 as eng
    pedidos = []
    original = repo.get_gto_node
    repo.get_gto_node = lambda h: pedidos.append(h) or None
    try:
        eng._enrich_gto({
            'street': 'flop', 'player_action': 'bet', 'hero_cards': ['Ah', 'Kd'],
            'spot': {'position': 'SB', 'villainPosition': 'BB', 'preflopOpener': 'SB',
                     'potType': '', 'board': ['2h', '7c', '9d'],
                     'effectiveStackBb': 40.0, 'facingToBb': 0.0, 'potSize': 5.0},
            'math': {'estimatedEquity': 0.5},
        })
    finally:
        repo.get_gto_node = original
    assert pedidos, 'o motor nao consultou nó nenhum'
    base = dict(street='flop', position='SB', board=['2h', '7c', '9d'],
                hero_stack_bb=40.0, facing_size_bb=0.0)
    legado_exato = compute_spot_hash(**base, hero_hand=['Ah', 'Kd'])
    legado_gen = compute_spot_hash(**base, hero_hand=[])
    assert legado_exato not in pedidos and legado_gen not in pedidos, (
        'o motor consultou o hash LEGADO num spot oop_pfr — o nó espelhado seria servido')
    esperado = compute_spot_hash(**base, hero_hand=['Ah', 'Kd'], pot_type='oop_pfr')
    assert esperado in pedidos, (esperado, pedidos)
    print('OK  test_o_motor_NAO_le_no_legado_num_spot_oop_pfr')


def test_CONTROLE_spot_de_opener_IP_segue_lendo_o_legado():
    """Sem esta âncora, "nunca ler nó nenhum" passaria no teste de cima."""
    import database.repositories as repo
    import leaklab.decision_engine_v11 as eng
    pedidos = []
    original = repo.get_gto_node
    repo.get_gto_node = lambda h: pedidos.append(h) or None
    try:
        eng._enrich_gto({
            'street': 'flop', 'player_action': 'fold', 'hero_cards': ['Ah', 'Kd'],
            'spot': {'position': 'BB', 'villainPosition': 'BTN', 'preflopOpener': 'BTN',
                     'potType': '', 'board': ['2h', '7c', '9d'],
                     'effectiveStackBb': 40.0, 'facingToBb': 3.0, 'potSize': 6.0},
            'math': {'estimatedEquity': 0.4},
        })
    finally:
        repo.get_gto_node = original
    legado = compute_spot_hash(street='flop', position='BB', board=['2h', '7c', '9d'],
                               hero_hand=['Ah', 'Kd'], hero_stack_bb=40.0, facing_size_bb=3.0)
    assert legado in pedidos, 'o caso majoritário parou de ler a cobertura existente'
    print('OK  test_CONTROLE_spot_de_opener_IP_segue_lendo_o_legado')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
