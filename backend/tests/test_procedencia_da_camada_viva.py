# -*- coding: utf-8 -*-
"""A procedência acompanha quem teve a ÚLTIMA palavra, não quem está gravado.

── O caso que originou (26/08) ────────────────────────────────────────────────────────────

Um juiz de coerência achou três decisões do torneio 72 exibindo, na MESMA linha,
`gto_label: gto_critical` e `verdict_source: motor`. O objeto se contradizia: dizia "isto veio do
heurístico" e "o solver classificou como desvio crítico" ao mesmo tempo.

A causa é a de sempre — dois fatos, duas fontes. O `/replay` recomputa o veredito numa cadeia de
camadas (`card_verdict.LAYERS`), e a camada viva costuma ser mais severa que a gravada:

    banco:  marginal 0,13   gto_label NULO      verdict_source motor
    card:   small_mistake 0,19   gto_critical   verdict_source motor   <- a contradição

`error_label` e `gto_label` já saíam recomputados; `verdict_source` continuava vindo da coluna.
Zero decisões do banco têm `gto_label` com procedência `motor` — a contradição só existia na tela.

── O que NÃO muda ─────────────────────────────────────────────────────────────────────────

O CUSTO. A camada viva traz rótulo, não traz EV. Então `pode_falar_como_gto` segue False nesses
casos, e é o certo: procedência sem custo não autoriza a palavra "leak". Se este teste um dia
falhar dizendo que a linguagem foi liberada sem custo, o conserto quebrou mais do que consertou.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_a_camada_viva_responde_pela_procedencia():
    from leaklab.verdict import procedencia_da_camada, SOLVER, CARTA
    assert procedencia_da_camada('live', 'motor') == SOLVER, (
        'a camada viva do solver decidiu o veredito e a tela continuou dizendo `motor`')
    assert procedencia_da_camada('preflop', 'motor') == CARTA, (
        'o override de carta preflop decidiu e a tela continuou dizendo `motor`')
    print('OK  test_a_camada_viva_responde_pela_procedencia')


def test_quem_NAO_troca_a_fonte_devolve_a_gravada():
    """Contraprova. As camadas de multiway não trocam a FONTE do veredito — elas suprimem ou
    suavizam o que a fonte disse. Um mapa que promovesse todas passaria no teste acima e daria
    autoridade de solver a quem não tem."""
    from leaklab.verdict import procedencia_da_camada, MOTOR
    for camada in ('stored', 'multiway_advice', 'multiway_engine', 'multiway_safe'):
        assert procedencia_da_camada(camada, 'carta') == 'carta', (
            'a camada %s passou a inventar procedência' % camada)
    assert procedencia_da_camada(None, 'solver') == 'solver'
    assert procedencia_da_camada('camada_que_nao_existe', None) == MOTOR, (
        'camada desconhecida passou a promover autoridade que ninguém provou')
    print('OK  test_quem_NAO_troca_a_fonte_devolve_a_gravada')


def test_a_procedencia_nova_NAO_libera_a_linguagem_sem_custo():
    """O risco do conserto, e o motivo de ele parar no rótulo. Virar `solver` sem custo medido
    não pode destravar "leak"/"erro contra o equilíbrio" — seria trocar uma contradição por uma
    falsa autoridade, que é pior."""
    from leaklab.verdict import pode_falar_como_gto, procedencia_da_camada
    viva = procedencia_da_camada('live', 'motor')
    assert pode_falar_como_gto(viva, False) is False, (
        'a camada viva passou a autorizar linguagem de GTO SEM custo medido')
    assert pode_falar_como_gto(viva, True) is True, (
        'com custo medido a linguagem deixou de ser autorizada — o gate virou peneira')
    print('OK  test_a_procedencia_nova_NAO_libera_a_linguagem_sem_custo')


def test_o_replay_consulta_a_camada_e_nao_so_a_coluna():
    """Fiação. A regra pode existir e não ser chamada — foi assim que `pode_falar_como_gto`
    passou semanas gravada e não lida (coluna write-only)."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    codigo = '\n'.join(l.split('#')[0] for l in fonte.split('\n'))
    assert 'procedencia_da_camada(' in codigo, (
        'o /replay voltou a servir `verdict_source` direto da coluna: a tela pode exibir rótulo '
        'de solver ao lado de procedência `motor` de novo')
    # O gate tem que julgar a MESMA fonte que a tela exibe — mas SÓ no /replay. A lista do
    # torneio lê a coluna de propósito (lá não há camada viva), então o guarda ancora no site do
    # replay pelo `multiway=_mw_spot`, que só existe lá. Ancorar na primeira ocorrência da chave
    # pegava a lista e acusava com o conserto no lugar.
    # Janela para FRENTE apenas. Olhando para trás ela alcançava a linha de `verdict_source`, que
    # também nomeia `procedencia_da_camada` — e o guarda passava verde com o gate desligado.
    i = codigo.index('multiway=_mw_spot')
    trecho = codigo[i:i + 260]
    assert 'procedencia=' in trecho, (
        'o gate de linguagem do /replay voltou a julgar a procedência GRAVADA enquanto a tela '
        'exibe a viva')
    print('OK  test_o_replay_consulta_a_camada_e_nao_so_a_coluna')


def test_a_camada_viva_NAO_promove_para_acusacao():
    """O segundo achado do mesmo juiz, e o maior.

    Quando a cadeia viva dizia "erro" e o rótulo gravado não era acusação, a tela exibia
    `small_mistake` por conta própria — uma SEGUNDA política de veredito por cima da do motor.

    Medido em 26/08 no torneio 72: **24 divergências entre a lista e o card em 486 decisões**, e a
    direção denuncia — **22 do card acusando mais, 0 do card absolvendo**. O aluno abre a lista,
    lê "Correto", e o card da mesma decisão diz "Erro".

    Quem está certo respondeu-se com duas medições: o regrade completo devolveu `MUDAM: 0` (banco
    e motor concordam), e em **22 das 24 o motor USOU o nó do solver** — não era falta de
    cobertura, era o motor aplicando suas regras e a cadeia viva ignorando todas.
    """
    from leaklab.verdict import label_exibido_da_camada_viva as exibe

    label, erro = exibe('standard', True)
    assert (label, erro) == ('standard', False), (
        'a camada viva voltou a promover `standard` para acusação: a lista diz Correto e o card '
        'diz Erro na mesma decisão')
    label, erro = exibe('marginal', True)
    assert (label, erro) == ('marginal', False), 'a camada viva voltou a promover `marginal`'
    print('OK  test_a_camada_viva_NAO_promove_para_acusacao')


def test_a_camada_viva_PRESERVA_a_acusacao_do_motor():
    """Contraprova. Uma regra que devolvesse sempre `is_error=False` passaria no teste acima e
    apagaria TODAS as acusações da tela — o dano que o defeito não causava."""
    from leaklab.verdict import label_exibido_da_camada_viva as exibe

    for label in ('small_mistake', 'clear_mistake'):
        assert exibe(label, True) == (label, True), (
            'a acusação do motor foi apagada da tela: %s' % label)
        assert exibe(label, False) == (label, True), (
            'a acusação gravada deixou de valer quando a camada viva não opinou')
    print('OK  test_a_camada_viva_PRESERVA_a_acusacao_do_motor')


def test_o_replay_usa_a_regra_e_nao_o_else_antigo():
    """Fiação, ancorada na CONDIÇÃO. O ramo antigo terminava em `else 'small_mistake'` — se ele
    voltar, a divergência volta com ele."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    codigo = chr(10).join(l.split('#')[0] for l in fonte.split(chr(10)))
    assert 'label_exibido_da_camada_viva(' in codigo, (
        'o /replay parou de consultar a regra: a camada viva pode voltar a promover')
    i = codigo.index('_el_efetivo')
    assert "else 'small_mistake'" not in codigo[i:i + 900], (
        "o `else 'small_mistake'` voltou ao cálculo do label exibido")
    print('OK  test_o_replay_usa_a_regra_e_nao_o_else_antigo')


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
