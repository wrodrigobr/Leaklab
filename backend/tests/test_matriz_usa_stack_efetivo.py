# -*- coding: utf-8 -*-
"""A matriz é consultada na profundidade EFETIVA, não no stack do hero.

── Por que este teste existe: para proteger o certo, não para consertar o errado ──────────

Na auditoria de 24/08 dois juízes de poker independentes acusaram o mesmo comportamento como
defeito: "a matriz foi consultada em 9,1bb num spot de 40bb, e 9,11 é exatamente o
`facing_to_call_bb` — o valor do call entrou no lugar da profundidade".

A leitura é compreensível e está errada. Naquele spot o vilão estava ALL-IN por 9,1bb: o hero
tem 40bb, mas só 9,1 estão em jogo. `min(eu, ele)` é a profundidade que decide a estratégia, e
quando o vilão está all-in por menos, o efetivo COINCIDE com o valor do call. Coincidência
aritmética, não bug.

Medido antes de concluir, em 1.077 decisões preflop do acervo: a profundidade servida bate com
o EFETIVO em 1.077, com o stack do hero em 0, com o call em 0. Controle vivo — 904 dessas
decisões têm efetivo diferente do stack do hero, então a medição conseguia distinguir.

O risco que este teste cobre não é o produto regredir sozinho: é alguém "consertar" o falso
positivo. Trocar o efetivo pelo stack do hero faria a ferramenta ensinar estratégia de 40bb
para quem está enfrentando um jam de 9bb — o erro que a acusação pediria.

Ver [[project_stack_efetivo]]: `still_in_now` MENTE preflop, e é por isso que o efetivo tem
fonte própria.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_vs_jam_curto_a_matriz_usa_o_efetivo_e_nao_o_stack_do_hero():
    """Hero fundo enfrentando all-in curto: a carta consultada é a do JAM, não a de 40bb."""
    from leaklab.strategy_provider import preflop_strategy

    def bucket(stack):
        r = preflop_strategy(position='BB', hand='A4s', stack_bb=stack, action_taken='call',
                             vs_position='UTG+2', facing_size=9.1, facing_allin=True)
        return (r.get('raw') or {}).get('stack_bb'), r.get('raw', {}).get('stack_bucket')

    curto, _ = bucket(9.1)      # efetivo (vilão all-in por 9,1)
    fundo, _ = bucket(40.0)     # stack do hero — o que o "conserto" usaria

    assert curto is not None and fundo is not None, 'a carta parou de reportar a profundidade'
    assert abs(float(curto) - 9.1) < 0.5, (
        'consultando a 9,1bb a carta respondeu %s: a profundidade efetiva deixou de mandar' % curto)
    assert abs(float(fundo) - float(curto)) > 1.0, (
        'as duas profundidades caíram na MESMA carta (%s): o teste não distingue mais nada e '
        'passaria verde mesmo com o efetivo trocado pelo stack do hero' % curto)
    print('OK  test_vs_jam_curto_a_matriz_usa_o_efetivo_e_nao_o_stack_do_hero')


def test_o_pipeline_entrega_o_efetivo_e_nao_o_stack_do_hero():
    """Prova de fiação: quem chama a carta precisa passar `effectiveStackBb`.

    O teste acima prova que a CARTA responde por profundidade; este prova que o produto entrega
    a profundidade certa. Sem ele, alguém troca o argumento no chamador e a carta continua
    respondendo corretamente — sobre a pergunta errada."""
    import re
    raiz = os.path.join(os.path.dirname(__file__), '..')
    # "pelo menos um chamador usa o efetivo" NÃO basta: a primeira versão exigia isso e a
    # mutação que trocava o `app.py` por `heroStackBb` passou VERDE, porque o outro arquivo
    # sustentava a asserção sozinho. Cada chamador responde por si.
    ruins, vistos = [], 0
    for pasta, arquivo in (('api', 'app.py'), ('leaklab', 'decision_engine_v11.py')):
        caminho = os.path.join(raiz, pasta, arquivo)
        with open(caminho, encoding='utf-8') as fh:
            fonte = fh.read()
        # `(?<![\w])` no início: sem isso o padrão casava o SUFIXO de `hero_stack_bb = ...`, e o
        # teste acusava a leitura de parâmetro de um endpoint admin como se fosse a passagem da
        # profundidade para a carta.
        for m in re.finditer(r'(?<![\w])stack_bb\s*=\s*([^,\n]+)', fonte):
            trecho = m.group(1)
            if 'stack' not in trecho.lower():
                continue                       # variável local já resolvida, não é a fonte
            if 'heroStackBb' not in trecho and 'hero_stack' not in trecho:
                continue                       # não usa o stack do hero: nada a cobrar
            vistos += 1
            if 'effectiveStackBb' not in trecho and 'effective_stack' not in trecho:
                linha = fonte[:m.start()].count(chr(10)) + 1
                ruins.append('%s/%s:%d' % (pasta, arquivo, linha))
    assert vistos, ('a varredura não achou nenhuma passagem de profundidade — o padrão do '
                    'código mudou e ela parou de enxergar')
    assert not ruins, (
        'chamador passa o stack do HERO sem o efetivo na frente (%s): um jam de 9bb volta a ser '
        'gradeado pela carta de 40bb' % ', '.join(ruins))
    print('OK  test_o_pipeline_entrega_o_efetivo_e_nao_o_stack_do_hero (%d passagens)' % vistos)


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
