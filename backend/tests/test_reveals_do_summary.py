# -*- coding: utf-8 -*-
"""O SUMMARY revela as cartas do vilao, e a gente jogava tudo fora.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

O parser lia a secao SUMMARY so para saber se o hero ganhou ou perdeu, e **descartava as cartas**.
Medido no acervo de producao em 05/08:

    maos com carta revelada .... 2.185 de 6.736
    revelacoes do HERO .........   708
    revelacoes de VILAO ........ 3.830   <- descartadas

── O segundo achado, que so apareceu porque eu contei os FORMATOS ─────────────────────────────

O regex antigo casava so `showed`. O acervo tem **405 linhas de `mucked`**, e elas nunca vem com
"and won" (405 de 405 sem resultado, contra 2.329 ganhas e 1.804 perdidas entre as de `showed`).
Quem da muck no showdown chegou la e PERDEU.

Consequencia: 50 showdowns do hero voltavam `None` e saiam do denominador do W$SD — **todos
derrotas**. Tirar so derrotas do denominador e o unico jeito de errar a taxa exclusivamente para
cima. Por isso `mucked` agora conta como `lost`.

Eu nao teria achado isso lendo o codigo: veio de contar os verbos que aparecem de verdade, em vez
de assumir o formato do PokerStars que eu ja conhecia.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import reveals_do_summary, _extract_showdown_result

_SUMMARY = """*** SUMMARY ***
Total pot 3836 | Rake 0
Board [Ts Jh Qd 2c 7h]
Seat 1: jojosetubal showed [Qc Ad] and won (3836) with a straight, Ten to Ace
Seat 3: Andrew Willian (button) mucked [Qc 6c]
Seat 4: phpro (big blind) showed [Th As] and lost with high card Ace
Seat 6: naoRevelou folded before Flop (didn't bet)
"""


def test_captura_hero_e_vilao():
    r = reveals_do_summary(_SUMMARY)
    assert r == {'jojosetubal': ['Qc', 'Ad'],
                 'Andrew Willian': ['Qc', '6c'],
                 'phpro': ['Th', 'As']}, r


def test_nome_com_espaco_e_rotulo_de_posicao():
    """Metade das linhas do acervo traz "(button)"/"(big blind)", e ha nome com espaco.
    Os dois quebram um regex ingenuo de formas diferentes."""
    r = reveals_do_summary(_SUMMARY)
    assert 'Andrew Willian' in r, 'nome com espaco virou outra coisa'
    assert 'phpro' in r, 'o rotulo de posicao entrou no nome'
    for nome in r:
        assert '(' not in nome, f'rotulo de posicao vazou para o nome: {nome!r}'


def test_mucked_e_capturado():
    """405 linhas do acervo. O regex antigo so casava `showed` e perdia todas."""
    assert reveals_do_summary(_SUMMARY).get('Andrew Willian') == ['Qc', '6c']


def test_muck_do_hero_conta_como_derrota():
    """O que corrige o W$SD. Antes voltava None e saia do denominador."""
    assert _extract_showdown_result(_SUMMARY, 'Andrew Willian') == 'lost'


def test_showdown_ganho_e_perdido_seguem_certos():
    """Controle negativo: se estes cairem junto, o conserto do muck quebrou o que funcionava."""
    assert _extract_showdown_result(_SUMMARY, 'jojosetubal') == 'won'
    assert _extract_showdown_result(_SUMMARY, 'phpro') == 'lost'
    assert _extract_showdown_result(_SUMMARY, 'naoRevelou') is None


def test_so_a_secao_summary():
    """As linhas de showdown do corpo da mao descrevem o mesmo fato e duplicariam. Sem a secao,
    nao ha revelacao."""
    corpo = """*** SHOW DOWN ***
Seat 1: alguem showed [Ac Kc] and won
"""
    assert reveals_do_summary(corpo) == {}
    assert reveals_do_summary('') == {}
    assert reveals_do_summary(None) == {}


def test_carta_em_formato_estranho_nao_derruba_a_mao():
    """Revelacao e dado OPCIONAL: preferimos perder a revelacao a perder o parse da mao."""
    ruim = """*** SUMMARY ***
Seat 1: alguem showed [lixo aqui] and won (10)
Seat 2: outro showed [Ac Kc] and lost
"""
    r = reveals_do_summary(ruim)
    assert 'outro' in r and r['outro'] == ['Ac', 'Kc']


def test_o_parser_expoe_no_ParsedHand():
    """FIACAO: extrair e nao anexar deixaria a funcao sem consumidor, e o dado seguiria perdido."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'parser.py')
    src = open(caminho, encoding='utf-8').read()
    assert src.count('reveals=reveals_do_summary(raw_text)') >= 2, (
        'algum construtor de ParsedHand parou de anexar as revelacoes')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
