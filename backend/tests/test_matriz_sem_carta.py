# -*- coding: utf-8 -*-
"""Spot sem carta GTO não pode exibir frequência de mão.

── O caso que originou (24/08, auditoria pré-lançamento) ──────────────────────────────────

Em 12 decisões auditadas a matriz declarava `available: false` ("não há carta GTO para este
spot") e MESMO ASSIM servia `hand_freq` — às vezes com 100% numa ação. Em 4 delas a matriz
dizia na tela o CONTRÁRIO do veredito exibido ao lado.

O juiz de poker foi categórico: "call 100%" numa matriz é a afirmação mais forte que uma
ferramenta faz — é o tipo de linha que o jogador DECORA. Fazer essa afirmação sobre um spot
que o próprio produto diz não cobrir é falsa confiança, não informação.

── Por que o teste cobre OS DOIS LADOS ────────────────────────────────────────────────────

Consertar só o backend criava um defeito PIOR. O `RangePanel` tratava `hand_freq` ausente como
"fold puro 100%" (`hf ? ... : 1`), e `{}` é *truthy* em JS: mandar o mapa vazio faria a tela
afirmar **"Fold 100%"** onde não há carta nenhuma. O defeito não morava em nenhum dos lados —
morava na costura.

O motor nunca dependeu disto: `decision_engine_v11:435` já fazia
`hand_freq if available else None`. Quem lia sem checar era a exibição.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_FRONT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src'))


def test_porta_unica_nao_serve_frequencia_sem_carta():
    from leaklab.strategy_provider import preflop_strategy

    # spot coberto: a frequência VEM (senão o teste abaixo não provaria nada)
    bom = preflop_strategy(position='BTN', hand='A5s', stack_bb=50.0, action_taken='fold',
                           facing_size=0.0)
    assert bom.get('available') is True, 'o spot de controle deixou de ser coberto'
    assert bom.get('hand_freq'), 'spot COBERTO parou de servir frequência — o conserto foi longe demais'

    # Spot SEM carta mas com frequência no dict cru — o caso real dos 12 auditados.
    #
    # Não dá para reproduzi-lo por parâmetros com confiança (o `available` daqueles casos vem
    # de uma combinação que o /replay monta), e a primeira versão deste teste usava
    # `hand='ZZ9'`, que cai num `return` ANTERIOR já devolvendo `{}`: a mutação do backend
    # passou verde. Um duplo força o caminho exato que o conserto toca.
    import leaklab.strategy_provider as sp

    original = sp.analyze_preflop
    sp.analyze_preflop = lambda **kw: {
        'available': False, 'scenario': 'vs_rfi', 'hand_freq': {'call': 1.0, 'fold': 0.0},
        'recommended_actions': ['call'], 'range_pct': None, 'raise_to_bb': None}
    try:
        ruim = preflop_strategy(position='BB', hand='J8o', stack_bb=15.8, action_taken='call',
                                vs_position='LJ', facing_size=2.0)
    finally:
        sp.analyze_preflop = original

    assert ruim.get('available') is False, 'o duplo não chegou na porta única'
    assert not ruim.get('hand_freq'), (
        'spot SEM carta voltou a servir hand_freq — a matriz vai afirmar uma estratégia que o '
        'produto não tem (foi o caso de 12 decisões auditadas)')
    print('OK  test_porta_unica_nao_serve_frequencia_sem_carta')


def test_a_tela_nao_transforma_ausencia_em_fold_100():
    """O ramo `hf ? (...) : 1` fazia ausência virar fold puro. Com o mapa vazio (truthy em JS)
    o efeito seria o mesmo por outro caminho. A tela precisa decidir por `available`."""
    caminho = os.path.join(_FRONT, 'components', 'replayer', 'RangePanel.tsx')
    assert os.path.exists(caminho), 'RangePanel.tsx sumiu — o teste perdeu o alvo'
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()

    assert 'semCarta' in fonte, (
        'o RangePanel não tem mais o estado "sem carta" — ausência de carta volta a ser '
        'desenhada como se fosse estratégia')
    assert 'gto.available === false' in fonte, (
        'o RangePanel parou de olhar `available` para decidir se desenha a barra')
    # o ramo antigo não pode voltar
    assert not re.search(r'const fold = hf \? \(hf\.fold', fonte), (
        'voltou o ramo que transforma hand_freq ausente em "fold 100%"')
    print('OK  test_a_tela_nao_transforma_ausencia_em_fold_100')


def test_o_estado_sem_carta_esta_traduzido():
    """Chave sem tradução vaza crua na tela — e esta aparece justamente quando o produto está
    admitindo que não sabe, que é o pior momento para mostrar um identificador."""
    import json
    for idioma in ('pt-BR', 'en', 'es'):
        caminho = os.path.join(_FRONT, 'i18n', 'locales', idioma, 'replayer.json')
        with open(caminho, encoding='utf-8') as fh:
            dados = json.load(fh)
        texto = (dados.get('rangePanel') or {}).get('semCarta')
        assert texto, 'rangePanel.semCarta ausente em %s' % idioma
        assert len(texto) > 15, '%s: texto curto demais para explicar o estado' % idioma
    print('OK  test_o_estado_sem_carta_esta_traduzido')


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
