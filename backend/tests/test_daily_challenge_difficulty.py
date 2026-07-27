"""
Desafio do Dia — faixas de dificuldade.

O desafio nascia sempre FÁCIL por construção: só entrava spot com a ação top do GTO ≥85% E com
a heurística local concordando. Sobreviviam os spots mais óbvios do jogo ("K5o no BTN vs open
do CO a 50bb → fold 100%"), e o jogador respondia no automático.

O que estes testes protegem é a linha que separa "difícil" de "injusto": um spot misto só vale
como pergunta se ainda existir uma ação claramente ERRADA no menu. Sem isso, qualquer resposta
é aceitável e o desafio ensina que tanto faz.
"""
import sys, os, random, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.daily_challenge import (
    build_candidates, _discriminates, _certainty, DIFFICULTIES,
    DOMINANT_FREQ, MEDIUM_FREQ, HARD_FREQ, MIN_CREDITABLE, _CH_STACKS,
)


# ── O filtro que mantém o spot misto significativo ────────────────────────────

def _strat(*pares):
    return [{'action': a, 'freq': f} for a, f in pares]


def test_menu_todo_creditavel_nao_discrimina():
    """Se fold, call e raise são todos ≥10%, qualquer resposta é 'aceitável'. Não é desafio."""
    spot = {'options': ['fold', 'call', 'raise']}
    assert not _discriminates(spot, _strat(('call', 0.45), ('raise', 0.35), ('fold', 0.20)))
    print("OK  test_menu_todo_creditavel_nao_discrimina")


def test_spot_misto_com_acao_errada_discrimina():
    """55/45 é misto, mas foldar continua sendo erro — a pergunta mede algo."""
    spot = {'options': ['fold', 'call', 'raise']}
    assert _discriminates(spot, _strat(('call', 0.55), ('raise', 0.45), ('fold', 0.0)))
    print("OK  test_spot_misto_com_acao_errada_discrimina")


def test_acao_ausente_da_estrategia_conta_como_errada():
    """Ação no menu que nem aparece na estratégia tem freq 0 — é a mais errada possível."""
    spot = {'options': ['fold', 'call', 'allin']}
    assert _discriminates(spot, _strat(('call', 0.60), ('fold', 0.40)))
    print("OK  test_acao_ausente_da_estrategia_conta_como_errada")


def test_menu_vazio_nao_discrimina():
    assert not _discriminates({'options': []}, _strat(('call', 1.0)))
    print("OK  test_menu_vazio_nao_discrimina")


# ── Faixas ────────────────────────────────────────────────────────────────────

def test_faixas_nao_se_sobrepoem():
    """As bordas têm que ser exclusivas, senão o mesmo spot cai em duas faixas."""
    assert HARD_FREQ < MEDIUM_FREQ < DOMINANT_FREQ
    assert MIN_CREDITABLE < HARD_FREQ
    print("OK  test_faixas_nao_se_sobrepoem")


def test_stack_curto_entrou_na_grade():
    """É onde a decisão de MTT vira difícil: a mesma mão é shove a 12bb e fold a 40bb."""
    assert min(_CH_STACKS) <= 12, _CH_STACKS
    assert any(s <= 20 for s in _CH_STACKS)
    print("OK  test_stack_curto_entrou_na_grade")


# ── Geração real (usa as ranges) ──────────────────────────────────────────────

def test_gera_candidatos_em_cada_faixa():
    """Não basta a faixa existir no código: o gerador precisa ACHAR spots nela."""
    for d in DIFFICULTIES:
        c = build_candidates(n=3, rng=random.Random(7), with_explanation=False, difficulty=d)
        assert c, f"nenhum candidato para {d}"
        assert all(x['difficulty'] == d for x in c), [x['difficulty'] for x in c]
    print("OK  test_gera_candidatos_em_cada_faixa")


def test_dificil_e_de_fato_misto():
    """O ponto do pedido: spot difícil não pode ser resposta unânime disfarçada."""
    c = build_candidates(n=4, rng=random.Random(7), with_explanation=False, difficulty='dificil')
    assert c
    for x in c:
        # a nota carrega a frequência do GTO — abaixo de MEDIUM_FREQ é mistura de verdade
        pct = int(x['note'].rsplit(' ', 1)[-1].rstrip('%'))
        assert HARD_FREQ * 100 <= pct < MEDIUM_FREQ * 100, x['note']
    print(f"OK  test_dificil_e_de_fato_misto ({len(c)} spots)")


def test_facil_continua_unanime():
    """A faixa fácil não pode ter regredido — é a que sustenta a promessa de gabarito certo."""
    c = build_candidates(n=4, rng=random.Random(7), with_explanation=False, difficulty='facil')
    assert c
    for x in c:
        pct = int(x['note'].rsplit(' ', 1)[-1].rstrip('%'))
        assert pct >= DOMINANT_FREQ * 100, x['note']
    print("OK  test_facil_continua_unanime")


def test_faixa_invalida_cai_no_facil():
    c = build_candidates(n=2, rng=random.Random(1), with_explanation=False, difficulty='impossivel')
    assert all(x['difficulty'] == 'facil' for x in c), c
    print("OK  test_faixa_invalida_cai_no_facil")


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
