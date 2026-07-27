"""
Regressão: a narrativa do card NÃO pode assumir a premissa do veredito.

Caso real que gerou este teste (torneio 4019075794, mão 261557136356): hero no SB com AQs,
UTG abre, UTG+2 3-beta, hero paga 16,8bb fora de posição. O engine recomendou FOLD (correto:
é cold-call de 3-bet OOP), mas a frase dizia "Equity de 66.3% ficou 19.9pp ABAIXO dos 46.4%
exigidos — sem valor para continuar no pot", enquanto o próprio card exibia "+19.9pp".

O texto assumia que "fold recomendado ⇒ preço não fecha" e escrevia `abs(diff)` com a palavra
"abaixo" fixa. Quando o fold vem da RANGE (mão dominada, fora de posição) e não do preço, a
frase afirmava o oposto do número ao lado. Uma explicação que contradiz a evidência exibida é
pior que nenhuma: o jogador deixa de confiar no resto da análise.
"""
import sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import build_interpretation


def _input(equity, action='call', best='fold'):
    return {
        'player_action': action,
        'street': 'preflop',
        'range_evaluation': {'recommendedPrimaryAction': best},
        'math': {'estimatedHandEquity': equity},
        'spot': {'position': 'SB'},
        'context': {'icmPressure': 'low'},
    }


def _texto(equity, required, action='call', best='fold'):
    r = build_interpretation(_input(equity, action, best), 'small_mistake', required)
    return ' '.join(str(v) for v in r.values())


def test_equity_abaixo_do_exigido_diz_abaixo():
    """O caso normal segue igual: preço não fecha, a frase diz que não fecha."""
    txt = _texto(0.30, 0.464)
    assert 'abaixo' in txt, txt
    assert 'sem valor para continuar' in txt, txt
    print("OK  test_equity_abaixo_do_exigido_diz_abaixo")


def test_equity_acima_do_exigido_nao_diz_abaixo():
    """O bug: 66.3% contra 46.4% exigidos NÃO é 'abaixo'. A frase tem que parar de mentir."""
    txt = _texto(0.663, 0.464)
    assert 'abaixo' not in txt, txt
    assert 'sem valor para continuar' not in txt, txt
    print("OK  test_equity_acima_do_exigido_nao_diz_abaixo")


def test_equity_acima_explica_que_o_fold_vem_da_range():
    """Não basta calar: o jogador precisa saber POR QUE foldar com o preço fechando."""
    txt = _texto(0.663, 0.464)
    assert 'range' in txt.lower(), txt
    assert '66.3' in txt and '46.4' in txt, txt
    print("OK  test_equity_acima_explica_que_o_fold_vem_da_range")


def test_nenhuma_frase_inverte_o_sinal():
    """Varredura: para qualquer par (equity, exigido), a palavra 'abaixo' só pode aparecer
    quando a equity é REALMENTE menor que o exigido."""
    for eq in (0.10, 0.30, 0.45, 0.464, 0.50, 0.663, 0.90):
        for req in (0.20, 0.464, 0.70):
            txt = _texto(eq, req)
            if 'abaixo' in txt:
                assert round(eq * 100, 1) < round(req * 100, 1), (eq, req, txt)
    print("OK  test_nenhuma_frase_inverte_o_sinal")


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
