"""
test_sanidade_do_gabarito.py — o corretor não pode responder ABSURDO com confiança.

**Este arquivo nasceu de um relato do usuário, e a frase dele é o requisito:** "dei um bet com AQs
e fala que o GTO indica fold... isto é bizarro e não pode acontecer. Precisamos ter algum tipo de
validação mais completa."

A causa era `'AdQd'` (cartas concretas) chegando onde se esperava `'AQs'` (hand type). O analisador
compara o TEXTO da mão com a string do range; `'AdQd'` não está em `'...,AQo,AQs,...'`, então ele
concluiu **"fora do range, fold 100%"** — sem erro, sem aviso, com confiança total.

**É o pior modo de falha que existe num corretor.** Erro que explode aparece; erro que responde
errado vira aprendizado errado. E nenhum teste estrutural pegava: o formato do payload estava
perfeito, o menu estava certo, o veredito voltou preenchido. Só o CONTEÚDO estava absurdo.

Por isso os testes daqui não olham forma, olham SUBSTÂNCIA: mãos cujo gabarito é conhecido por
qualquer jogador, e a exigência de que o motor não diga o contrário.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.strategy_provider import preflop_strategy, _normaliza_mao


def _freq(pos, mao, stack, acao, **kw):
    s = preflop_strategy(pos, mao, stack, **kw)
    return float((s.get('hand_freq') or {}).get(acao, 0.0)), s


def test_mao_premium_nunca_e_fold_100_por_cento_na_abertura():
    """AA de UTG jamais é fold. Se o motor disser que é, alguma coisa está muito errada — e o
    jogador vai acreditar, porque ele veio aqui justamente para aprender."""
    premium = ['AA', 'KK', 'QQ', 'AKs', 'AKo', 'AQs', 'JJ']
    posicoes = ['UTG', 'UTG+1', 'MP', 'LJ', 'HJ', 'CO', 'BTN']
    ruins = []
    for pos in posicoes:
        for mao in premium:
            fold, s = _freq(pos, mao, 50.0, 'fold', facing_size=0, vs_position='')
            if not s.get('available'):
                continue                     # sem cobertura é honesto; fold 100% não é
            if fold >= 0.99:
                ruins.append((pos, mao, s.get('hand_freq')))
    assert not ruins, f'mão premium marcada como fold 100% na abertura: {ruins[:5]}'
    print('OK  test_mao_premium_nunca_e_fold_100_por_cento_na_abertura')


def test_cartas_concretas_dao_a_MESMA_resposta_que_o_hand_type():
    """O bug exato do relato: `'AdQd'` respondia fold 100% e `'AQs'` respondia raise 100% — a
    mesma mão, dois gabaritos opostos, dependendo só do formato da string."""
    pares = [('AdQd', 'AQs'), ('AhQs', 'AQo'), ('KhKd', 'KK'),
             ('7c7d', '77'), ('JsTs', 'JTs'), ('9h8c', '98o')]
    for concreto, tipo in pares:
        assert _normaliza_mao(concreto) == tipo, f'{concreto} -> {_normaliza_mao(concreto)} != {tipo}'
        a = preflop_strategy('UTG+1', concreto, 58.4, facing_size=0, vs_position='')
        b = preflop_strategy('UTG+1', tipo, 58.4, facing_size=0, vs_position='')
        assert a.get('hand_freq') == b.get('hand_freq'), \
            f'{concreto} e {tipo} dão gabaritos diferentes: {a.get("hand_freq")} vs {b.get("hand_freq")}'
    print('OK  test_cartas_concretas_dao_a_MESMA_resposta_que_o_hand_type')


def test_mao_em_formato_desconhecido_responde_NAO_SEI():
    """Entrada que o motor não entende tem que virar "sem cobertura", nunca um veredito.

    Conferido no desenvolvimento: sem esta porta, `preflop_strategy(..., 'lixo')` voltava
    `available=True` e um gabarito. Responder com confiança sobre entrada não compreendida é
    exatamente o defeito que este arquivo existe para impedir.
    """
    for lixo in ('lixo', 'AdQdJs', 'Ad', 'ZZ', '???'):
        s = preflop_strategy('UTG+1', lixo, 50.0)
        assert s.get('available') is False, f'{lixo!r} respondeu com gabarito: {s}'
        assert not s.get('recommended'), f'{lixo!r} recomendou ação: {s.get("recommended")}'
    print('OK  test_mao_em_formato_desconhecido_responde_NAO_SEI')


def test_lixo_absoluto_nao_vira_abertura_de_UTG():
    """O contraponto: se TUDO virasse raise, os testes acima passariam sem significar nada.
    72o de UTG é fold, e o motor precisa dizer isso."""
    fold, s = _freq('UTG', '72o', 50.0, 'fold', facing_size=0, vs_position='')
    assert s.get('available'), 'sem cobertura para 72o de UTG — o teste não mediu nada'
    assert fold >= 0.9, f'72o de UTG não é fold? {s.get("hand_freq")}'
    print('OK  test_lixo_absoluto_nao_vira_abertura_de_UTG')


def test_o_modo_grind_nao_serve_veredito_absurdo():
    """A varredura de ponta a ponta: monta passos como o modo grind os monta e exige que nenhuma
    mão premium volte como fold 100%.

    É o teste que teria pegado o relato. Os anteriores cobrem a fonte; este cobre o CAMINHO — e
    foi o caminho que quebrou, porque quem chamava passava cartas concretas.
    """
    from leaklab.grind_mode import corrigir_passo
    ruins = []
    for mao in (['Ad', 'Qd'], ['As', 'Ah'], ['Kh', 'Kd'], ['Ac', 'Kc']):
        passo = {'street': 'preflop', 'position': 'UTG+1', 'vs_position': '',
                 'stack_bb': 58.4, 'pot_bb': 1.5, 'facing_size_bb': 0.0,
                 'hero_hand': mao, 'options': ['fold', 'raise'], 'board': []}
        g = corrigir_passo(passo, 'raise')
        if g is None:
            continue                         # sem gabarito é aceitável; gabarito absurdo não
        mix = {d['action']: d['freq'] for d in (g.get('gto_strategy') or [])}
        if mix.get('fold', 0) >= 0.99:
            ruins.append((''.join(mao), mix))
    assert not ruins, f'o modo grind mandaria foldar mão premium: {ruins}'
    print('OK  test_o_modo_grind_nao_serve_veredito_absurdo')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
    raise SystemExit(1 if fail else 0)
