# -*- coding: utf-8 -*-
"""A equity de continuação pode ABSOLVER um fold, nunca CONDENAR.

── O que originou (28/08) ──────────────────────────────────────────────────────────────────

Medido no acervo inteiro de produção, 2.651 decisões de flop/turn: a troca da equity heurística
pela conta contra a range de continuação deixa **98,4% dos vereditos idênticos**, com 14 acusações
entrando e 13 saindo.

O agregado parecia inócuo. A lista, não: **7 das 14 que entram são FOLD, e as 4 que viram
`clear_mistake` são todas folds** — mãos sem par, com projeto, acusadas porque a equity subiu.

Essa é a família que este produto já derrubou em 26/08, quando a equity estimada era a ÚNICA
evidência em 22 de 22 acusações de fold pós-flop e a ablação desmentiu metade da leitura do juiz.

E a subida vem de uma escolha nossa, não de um fato do jogo: contar projetos como mãos que
continuam alarga a range do vilão em ~45% (798 combos contra 552 num turn real). Escolher o
critério da range do vilão e depois usar o resultado para acusar quem foldou fecha um círculo.

── O que este arquivo protege ──────────────────────────────────────────────────────────────

A assimetria. Ela é fácil de perder num refactor porque parece um `if` sobrando, e quando some não
quebra nada: só volta a acusar folds, calado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _snapshot(street, hero, board, acao, monkey_equity):
    """Roda o motor de matemática com a conta de continuação forçada a um valor."""
    import leaklab.equity_real as er
    import leaklab.street_math_engine as sme
    from leaklab.models import HandState

    original = er.equity_flop_turn_vs_continuacao
    er.equity_flop_turn_vs_continuacao = lambda *a, **k: monkey_equity
    os.environ['LEAKLAB_EQUITY_FLOP_TURN'] = '1'
    try:
        st = HandState(
            hand_id='T', street=street, hero='Voce', hero_cards=hero, board=board,
            player_action=acao, pot_size=10.0, facing_size=3.0, effective_stack_bb=40.0,
            position='BB', villain_position='BTN', is_in_position=False, is_multiway=False,
            actions=[], metadata={'n_active_opponents': 1},
        )
        return sme.build_math_snapshot(st), st.metadata
    finally:
        er.equity_flop_turn_vs_continuacao = original
        os.environ.pop('LEAKLAB_EQUITY_FLOP_TURN', None)


def _eq(snap):
    if snap is None:
        return None
    return getattr(snap, 'estimated_hand_equity', None) or (
        snap.get('estimatedHandEquity') if isinstance(snap, dict) else None)


def test_a_conta_nova_NAO_sobe_a_equity_de_um_fold():
    """O caso que originou o freio: `TdJh` em `9d3dQh5s` ia de 0,32 para 0,53 e o fold virava
    erro claro."""
    try:
        snap, meta = _snapshot('turn', 'TdJh', ['9d', '3d', 'Qh', '5s'], 'fold', 0.99)
    except Exception as e:                                     # noqa: BLE001
        # NAO "pula": pular passa verde, e um teste que nunca roda e cobertura sem dar cobertura.
        # Foi o `achou >= 4` de outro teste deste arquivo que denunciou os dois primeiros pulando.
        raise AssertionError('nao consegui montar o estado: %s' % e)
    eq = _eq(snap)
    assert eq is None or eq < 0.99, (
        'a equity de continuação (0,99) foi usada para julgar um FOLD: %r' % eq)
    assert meta.get('equity_continuacao_freada_no_fold'), (
        'o freio pegou mas não deixou rastro: sem o sinal ninguém consegue medir quantas vezes '
        'ele age, e "não se aplicou" fica indistinguível de "não existe conta para este spot"')
    print('OK  test_a_conta_nova_NAO_sobe_a_equity_de_um_fold')


def test_a_conta_nova_ABSOLVE_um_fold_quando_baixa():
    """CONTRAPROVA: um freio que barrasse a conta em TODO fold passaria no teste acima e mataria
    as 6 absolvições reais -- inclusive `3d3c` em `8d4h8s`, que saía com 0,720 de equity por causa
    do board pareado e hoje é acusado com esse número."""
    try:
        snap, meta = _snapshot('flop', '3d3c', ['8d', '4h', '8s'], 'fold', 0.05)
    except Exception as e:                                     # noqa: BLE001
        raise AssertionError('nao consegui montar o estado: %s' % e)
    eq = _eq(snap)
    assert eq is not None and abs(eq - 0.05) < 0.02, (
        'a conta nova deveria valer quando BAIXA a equity de um fold, e não valeu: %r' % eq)
    assert not meta.get('equity_continuacao_freada_no_fold'), 'freou onde deveria absolver'
    assert meta.get('equity_vs_continuacao'), 'absolveu mas não declarou a fonte'
    print('OK  test_a_conta_nova_ABSOLVE_um_fold_quando_baixa')


def test_acao_que_NAO_e_fold_usa_a_conta_nova_nos_dois_sentidos():
    """O freio é só no fold. Em bet/raise/call a conta vale subindo ou descendo -- é o que produz
    as acusações legítimas, como `55` apostando em `QJT` com equity caindo de 0,42 para 0,33."""
    achou = 0
    for acao in ('bet', 'raise', 'call'):
        for valor in (0.05, 0.95):
            try:
                snap, meta = _snapshot('flop', '5h5d', ['Qd', 'Js', 'Tc'], acao, valor)
            except Exception:                                  # noqa: BLE001
                continue
            eq = _eq(snap)
            if eq is None:
                continue
            achou += 1
            assert abs(eq - valor) < 0.02, (
                'em %s a conta nova não foi usada (esperado ~%.2f, veio %r)' % (acao, valor, eq))
            assert not meta.get('equity_continuacao_freada_no_fold')
    assert achou >= 4, 'só %d combinações exercitadas: o teste não prova nada' % achou
    print('OK  test_acao_que_NAO_e_fold_usa_a_conta_nova_nos_dois_sentidos (%d casos)' % achou)


def test_o_freio_MORA_no_motor_e_nao_na_tela():
    """Se a regra vazar para o `/replay` ou para um endpoint, volta a haver duas políticas de
    veredito -- o defeito de 26/08, em que a lista dizia Correto e o card dizia Erro em 24 de 486
    decisões."""
    import io
    import re
    raiz = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    suspeitas, varridos = [], 0
    for base, _d, arqs in os.walk(raiz):
        if any(x in base for x in ('.git', '__pycache__', 'node_modules', 'tests')):
            continue
        for a in arqs:
            if not a.endswith('.py'):
                continue
            varridos += 1
            corpo = io.open(os.path.join(base, a), encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'equity_flop_turn_vs_continuacao', corpo):
                trecho = corpo[max(0, m.start() - 600):m.end() + 600]
                if re.search(r"['\"]fold['\"]", trecho) and 'street_math_engine' not in a:
                    suspeitas.append(a)
    assert varridos >= 50, 'a varredura olhou %d arquivos: não varreu nada' % varridos
    assert not suspeitas, (
        'a regra do freio aparece fora do motor: %s' % sorted(set(suspeitas)))
    print('OK  test_o_freio_MORA_no_motor_e_nao_na_tela (%d arquivos)' % varridos)


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
