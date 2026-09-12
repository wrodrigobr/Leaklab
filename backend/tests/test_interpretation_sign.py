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


#: TODOS os pares (acao, recomendacao) que o gerador de frases distingue. A lista existe porque
#: a varredura anterior percorria (equity, exigido) mas SO com o par default `call` x `fold` — e
#: por isso ficou verde por meses com o ramo da AGRESSAO invertendo o sinal. Regra 5: o padrao
#: vive em N ramos, a varredura tem de cobrir os N+1.
_PARES = [(a, b) for a in ('call', 'fold', 'raise', 'bet', 'shove', 'jam', 'check')
          for b in ('fold', 'call', 'raise', 'bet', 'shove', 'jam', 'check')
          if a != b]


def test_nenhuma_frase_inverte_o_sinal():
    """Varredura: para qualquer (equity, exigido, acao, recomendacao), a palavra 'abaixo' so
    pode aparecer quando a equity e REALMENTE menor que o exigido.

    Medido em producao em 12/09, ANTES do conserto: das 87 notas deste formato nas acusacoes
    preflop sem carta, **60 tinham o sinal invertido** — todas de `shove`, o ramo que esta
    varredura nao exercitava. O caso mais claro: equity 66,3% contra 42,5% exigidos, e o texto
    dizendo "ficou 23,8pp abaixo" com a conclusao "a agressao nao tinha suporte matematico".
    """
    vistos = 0
    for eq in (0.10, 0.30, 0.45, 0.464, 0.50, 0.663, 0.90):
        for req in (0.20, 0.464, 0.70):
            for acao, best in _PARES:
                txt = _texto(eq, req, action=acao, best=best)
                vistos += 1
                if 'abaixo' in txt:
                    assert round(eq * 100, 1) < round(req * 100, 1), (acao, best, eq, req, txt)
    # Controle: a varredura tem de ter exercitado MUITOS pares, senao ela volta a medir um ramo.
    assert vistos >= 400, ('a varredura encolheu: %d combinacoes' % vistos)
    print("OK  test_nenhuma_frase_inverte_o_sinal (%d combinacoes)" % vistos)


def test_a_agressao_com_equity_ACIMA_nao_diz_que_faltou_matematica():
    """O caso de producao, nomeado: 60 shoves acusados com a frase afirmando o contrario do
    numero ao lado. Explicacao que contradiz a evidencia exibida e pior que nenhuma."""
    txt = _texto(0.663, 0.425, action='shove', best='fold')
    assert 'abaixo' not in txt, txt
    assert 'não tinha suporte' not in txt and 'nao tinha suporte' not in txt, txt
    # e precisa DIZER de onde vem o fold, senao so calou
    assert 'RANGE' in txt or 'range' in txt, txt
    assert '66.3' in txt and '42.5' in txt, txt
    print("OK  test_a_agressao_com_equity_ACIMA_nao_diz_que_faltou_matematica")


def test_a_agressao_com_equity_ABAIXO_continua_acusando():
    """Controle negativo: o conserto nao pode calar o caso legitimo."""
    txt = _texto(0.20, 0.425, action='shove', best='fold')
    assert 'abaixo' in txt, txt
    assert 'suporte matem' in txt, txt
    print("OK  test_a_agressao_com_equity_ABAIXO_continua_acusando")


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
