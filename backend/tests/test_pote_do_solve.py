# -*- coding: utf-8 -*-
"""Pote implausível não vai para o solver — e agora isso inclui pote PEQUENO demais.

── O caso que originou (25/08, investigação dos nós de all-in) ────────────────────────────

Três juízes de poker apontaram que o card recomendava all-in de até 22x o pote. Investigando os
nós: **524 nós postflop recomendam all-in**, e o pior deles foi solvado com `pot_bb: 0.5` num
FLOP — impossível, porque depois do preflop o pote tem no mínimo os blinds.

Com pote minúsculo e stack de 60bb, o SPR DENTRO DA ÁRVORE passa de 100, e o solver empurra tudo
para o jam. O all-in não era estratégia: era artefato do pote.

── A prova, medida no solver de produção ──────────────────────────────────────────────────

Mesmo spot (`9hJd` em `5h 7s 7c`, 61bb), trocando SÓ o pote:

    pot_bb 0.5  ->  HTTP 500: "spot requer 7.2GB — excede limite de 6GB"
    pot_bb 3.0  ->  59s, exploitability 2,5%, estratégia **check 67,6% / bet_50pct 32,4%**

Com o pote certo o solver recomenda meio pote, exatamente o que os juízes disseram ser correto.

── Por que 1,0bb ──────────────────────────────────────────────────────────────────────────

É o piso FÍSICO do postflop: small blind + big blind, antes de qualquer ante. Abaixo disso o
número não é um pote pequeno — é um pote errado. Os nós existentes são legado: `spot.potBb` só
passou a apontar para o pote real em 24/08.

Ver [[project_pote_reconstruido]] e [[project_degenerate_pot_nodes]].
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_pote_abaixo_dos_blinds_nao_vai_para_o_solver():
    from leaklab.gto_solver import pote_implausivel

    assert pote_implausivel(0.5, 60.0, 1) is True, (
        'pote de 0,5bb no postflop voltou a ser enfileirado: é menor que os blinds, e foi ele '
        'que produziu os nós que recomendam all-in de 20x o pote')
    assert pote_implausivel(0.9, 30.0, 1) is True, 'pote abaixo de 1bb passou'
    print('OK  test_pote_abaixo_dos_blinds_nao_vai_para_o_solver')


def test_o_piso_NAO_barra_pote_legitimo():
    """Contraprova — é ela que dá valor ao teste acima. O piso não pode virar peneira geral."""
    from leaklab.gto_solver import pote_implausivel

    assert pote_implausivel(1.0, 60.0, 1) is False, 'pote de exatamente 1bb (os blinds) foi barrado'
    assert pote_implausivel(3.0, 60.0, 1) is False, 'pote normal de flop foi barrado'
    assert pote_implausivel(50.0, 20.0, 1) is False, (
        'pote grande heads-up com dinheiro morto voltou a ser barrado — é solvável, e essa '
        'exceção já custou 13 decisões barradas por engano em 13/08')
    # `None`/0 significa "não sei", não "pote zero": não é assunto deste guarda
    assert pote_implausivel(0, 60.0, 1) is False, 'pote ausente virou implausível'
    assert pote_implausivel(None, 60.0, 1) is False, 'pote None virou implausível'
    print('OK  test_o_piso_NAO_barra_pote_legitimo')


def test_o_teto_continua_valendo():
    """O guarda tinha só teto; o piso foi adicionado ao lado, não no lugar."""
    from leaklab.gto_solver import pote_implausivel

    assert pote_implausivel(400.0, 60.0, 2) is True, 'o teto de pote implausível sumiu'
    print('OK  test_o_teto_continua_valendo')


def test_o_payload_do_solve_passa_pelo_guarda():
    """Fiação: o piso só vale se o enfileiramento consultar o guarda."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    codigo = chr(10).join(l.split('#')[0] for l in fonte.split(chr(10)))
    assert 'pote_implausivel' in codigo, (
        'o enfileiramento parou de consultar o guarda de pote: volta a mandar pote quebrado '
        'para o solver')
    print('OK  test_o_payload_do_solve_passa_pelo_guarda')


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
