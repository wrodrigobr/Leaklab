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


def test_o_raw_que_o_replay_consome_tambem_esta_saneado():
    """O `/replay` NÃO lê `hand_freq` do dict externo: lê `['raw']`, o dict cru.

    O primeiro conserto zerou só o externo e passou por verificado — a sonda em produção ainda
    achou 1 caso vivo. Um zero parcial é pior que nenhum, porque encerra a investigação."""
    import leaklab.strategy_provider as sp
    from leaklab.strategy_provider import preflop_strategy

    original = sp.analyze_preflop
    sp.analyze_preflop = lambda **kw: {
        'available': False, 'scenario': 'vs_rfi', 'hand_freq': {'call': 1.0, 'fold': 0.0},
        'recommended_actions': ['call'], 'range_pct': None, 'raise_to_bb': None}
    try:
        r = preflop_strategy(position='BB', hand='J8o', stack_bb=15.8, action_taken='call',
                             vs_position='LJ', facing_size=2.0)
    finally:
        sp.analyze_preflop = original

    assert not (r.get('raw') or {}).get('hand_freq'), (
        "`raw.hand_freq` voltou a viajar sem carta — é ESTE dict que o /replay serve ao card")
    print('OK  test_o_raw_que_o_replay_consome_tambem_esta_saneado')


def test_toda_chamada_a_analyze_preflop_passa_pelo_saneador():
    """Regra 5 do CLAUDE.md: regra aplicada em N lugares vira função, com teste que varre os N+1.

    O defeito sobreviveu ao primeiro conserto porque `analyze_preflop` é chamado direto em mais
    de um lugar — a sonda em produção ainda achou 1 caso vivo depois do "conserto verificado".

    A varredura não usa lista de isentos: chamada que NÃO passa pelo saneador só é aceita se ela
    própria não tocar em `hand_freq`. Isso é verificável a cada rodada; lista declarada envelhece
    calada (regra 8: comentário não é evidência).
    """
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    isentos = {
        os.path.join(raiz, 'leaklab', 'strategy_provider.py'),   # a porta única (onde o saneador mora)
        os.path.join(raiz, 'leaklab', 'preflop_gto_ranges.py'),  # onde analyze_preflop é DEFINIDA
    }
    faltando = []
    vistas = 0
    for pasta in ('api', 'leaklab'):
        for base, _, arqs in os.walk(os.path.join(raiz, pasta)):
            for a in arqs:
                if not a.endswith('.py'):
                    continue
                caminho = os.path.join(base, a)
                if caminho in isentos:
                    continue
                with open(caminho, encoding='utf-8') as fh:
                    fonte = fh.read()
                for m in re.finditer(r'_?analyze_preflop\s*\(', fonte):
                    linha_ini = fonte.rfind(chr(10), 0, m.start()) + 1
                    if fonte[linha_ini:m.start()].lstrip().startswith('#'):
                        continue                     # citação em comentário, não chamada
                    vistas += 1
                    antes = fonte[max(0, m.start() - 220):m.start()]
                    if 'sem_carta_nao_afirma(' in antes:
                        continue
                    # sem saneador: então este chamador não pode LER hand_freq
                    depois = fonte[m.end():m.end() + 2500]
                    # Guard explícito `if not res.get('available'): return` protege igual: o
                    # chamador nunca chega no hand_freq sem carta. Aceitar as DUAS formas evita
                    # ruído que faria o guarda ser desligado.
                    pos_hf = depois.find('hand_freq')
                    entre = depois[:pos_hf] if pos_hf >= 0 else ''
                    # `sem_carta_nao_afirma(` com parêntese: o IMPORT sozinho não protege
                    # nada, e aceitá-lo deixou a mutação da academia passar verde.
                    protegido = ('sem_carta_nao_afirma(' in entre
                                 or re.search(r"not\s+res\.get\('available'\)", entre))
                    if pos_hf >= 0 and not protegido:
                        faltando.append('%s:%d' % (os.path.relpath(caminho, raiz),
                                                   fonte[:m.start()].count(chr(10)) + 1))

    assert vistas >= 5, ('a varredura achou só %d chamadas — o padrão do código mudou e ela '
                         'parou de enxergar' % vistas)
    assert not faltando, (
        'chamada a analyze_preflop que LÊ hand_freq sem passar por sem_carta_nao_afirma (a '
        'matriz volta a afirmar estratégia em spot que o produto diz não cobrir): %s'
        % ', '.join(faltando))
    print('OK  test_toda_chamada_a_analyze_preflop_passa_pelo_saneador (%d chamadas)' % vistas)


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
