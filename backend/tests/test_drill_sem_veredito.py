"""
test_drill_sem_veredito.py — o drill não pode servir spot que ele mesmo não consegue corrigir.

**Reportado pelo usuário, com dois exemplos de causas diferentes:** revisou a mão, indicou shove,
e recebeu "≈ Fora da cobertura" sem ação recomendada. Um print trazia o selo `≈ APROXIMAÇÃO` (mão
fora da range solvada), o outro `≈ MULTIWAY` (o solver é heads-up e não resolve 3-way).

**A causa não era falta de gabarito.** A seleção já exigia `gto_label IN (...)`. O problema é que
a SELEÇÃO lia o rótulo GRAVADO no import e a CORREÇÃO faz um lookup AO VIVO — e os dois discordam.
O jogador recebia um exercício, respondia, e levava um veredito que não era veredito. Pior: o spot
ainda ocupava uma das 10 vagas da sessão.

Medido no acervo real antes de mexer: de 200 spots servidos, 6 eram multiway (3,0%) e 11 off-tree
(5,5%). O filtro custa 8,5% e deixa 183 — muito acima dos 10 de uma sessão.

O que estes testes travam:

1. **Preflop nunca é excluído.** O off-tree é um problema de postflop; excluir preflop mataria 80%
   do pool por engano.
2. **Multiway postflop é excluído.**
3. **Postflop resolvido por range AGREGADA é excluído** — é a definição de `gto_off_tree` no
   gradeamento, e as duas precisam concordar.
4. **Falha de lookup NÃO exclui.** Perder spot por erro transitório é pior que arriscar um: o
   jogador com pouco volume ficaria sem treino nenhum.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import api.app as A


def _spot(street='flop', oponentes=0):
    return {'id': 1, 'street': street, 'n_active_opponents': oponentes,
            'position': 'BTN', 'stack_bb': 30, 'facing_bet': 0, 'gto_action': 'bet'}


def _com_fonte(fonte):
    """Troca o resolvedor por um dublê que devolve a fonte pedida."""
    original = A._resolve_best_action_from_node
    A._resolve_best_action_from_node = lambda row, return_strategy=False: ('bet', {}, fonte)
    return original


def test_preflop_nunca_e_excluido():
    """O off-tree é problema de postflop. Excluir preflop mataria a maior parte do pool."""
    original = _com_fonte('gto_range')   # a pior fonte possível, e ainda assim preflop passa
    try:
        assert A._spot_sem_veredito(_spot(street='preflop')) is False
    finally:
        A._resolve_best_action_from_node = original
    print('OK  test_preflop_nunca_e_excluido')


def test_multiway_postflop_e_excluido():
    original = _com_fonte('gto_tree')
    try:
        assert A._spot_sem_veredito(_spot(street='flop', oponentes=2)) is True
        assert A._spot_sem_veredito(_spot(street='turn', oponentes=3)) is True
        assert A._spot_sem_veredito(_spot(street='flop', oponentes=1)) is False
    finally:
        A._resolve_best_action_from_node = original
    print('OK  test_multiway_postflop_e_excluido')


def test_postflop_por_range_agregada_e_excluido():
    """Range agregada nunca é hand-aware: postflop assim NUNCA crava veredito. É a mesma regra
    que o gradeamento usa para acender `gto_off_tree`."""
    for fonte in ('gto_range', 'gto_stored'):
        original = _com_fonte(fonte)
        try:
            assert A._spot_sem_veredito(_spot(street='river')) is True, fonte
        finally:
            A._resolve_best_action_from_node = original
    print('OK  test_postflop_por_range_agregada_e_excluido')


def test_postflop_hand_aware_passa():
    original = _com_fonte('gto_tree')
    try:
        assert A._spot_sem_veredito(_spot(street='flop')) is False
    finally:
        A._resolve_best_action_from_node = original
    print('OK  test_postflop_hand_aware_passa')


def test_falha_de_lookup_nao_exclui():
    """Fail-open de propósito: quem tem pouco volume ficaria sem treino nenhum por um erro
    transitório de consulta. Perder um spot bom é pior que arriscar um duvidoso."""
    def explode(row, return_strategy=False):
        raise RuntimeError('banco fora do ar')
    original = A._resolve_best_action_from_node
    A._resolve_best_action_from_node = explode
    try:
        assert A._spot_sem_veredito(_spot(street='turn')) is False
    finally:
        A._resolve_best_action_from_node = original
    print('OK  test_falha_de_lookup_nao_exclui')


def test_selecao_pede_folga_para_poder_descartar():
    """Sem folga, filtrar entregaria menos spots que o pedido — e o jogador veria a sessão
    encurtar sem entender por quê."""
    import re
    src = open(os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py'), encoding='utf-8').read()
    trecho = src[src.index('def player_drill_spots'): src.index('def player_drill_spots') + 1800]
    assert re.search(r'get_drill_spots\([^)]*limit\s*=\s*limit\s*\*\s*\d', trecho), \
        'a selecao nao pede folga antes de filtrar'
    assert '_spot_sem_veredito' in trecho, 'a selecao nao aplica o filtro'
    print('OK  test_selecao_pede_folga_para_poder_descartar')


def test_sql_exclui_multiway_postflop():
    """O multiway sai no SQL, e nao so no Python: sem isso ele consumiria a folga da selecao."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py'),
               encoding='utf-8').read()
    i = src.index('def get_drill_spots')
    trecho = src[i:i + 3000]
    assert "n_active_opponents, 0) >= 2" in trecho, 'filtro multiway ausente no SQL da selecao'
    assert 'd.n_active_opponents,' in trecho, \
        'a coluna nao vem no SELECT — o filtro em Python nao teria como conferir'
    print('OK  test_sql_exclui_multiway_postflop')


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f'FAIL {name}: {e}')
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f'Total: {passed+failed} | Passed: {passed} | Failed: {failed}')
