# -*- coding: utf-8 -*-
"""As miniaturas dos cards de treino ilustram a range — e ilustração errada ensina errado.

── Por que existem (28/08) ────────────────────────────────────────────────────────────────

O dono leu a proposta da tela de treino e disse que a gente enche a tela de texto. Estava certo, e
dava para medir: o mockup tinha 127 palavras e **um** elemento visual.

A regra que ficou: *a imagem tem que carregar a informação que a frase carregava, para a frase
poder sair*. "Abrir o pote" não precisa de "com que mãos abrir de cada posição" quando mostra o
formato real da range. Por isso a miniatura sai dos nossos dados, não de um desenho.

── O que este arquivo guarda ──────────────────────────────────────────────────────────────

1. Que ela continua batendo com a carta. Sem isto, o mesmo problema do recorte da vitrine: um
   literal colado que envelhece calado.
2. Que o nó consultado é o do herói e do vilão pedidos. A 1ª versão do gerador procurou a posição
   no nível errado de `vs_3bet[herói][3bettor]` e devolveu 13 células de um spot alheio. O
   controle de células ativas pegou.
3. Que ela NÃO vira ferramenta de consulta: um caractere por célula, sem rótulo e sem frequência.
   Quem quer consultar vai em `/ranges`. Miniatura que ganha detalhe vira segunda fonte de verdade
   sobre a range.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                                    'frontend', 'src', 'data', 'miniaturasDeTreino.ts'))


def _do_arquivo():
    fonte = io.open(_TS, encoding='utf-8').read()
    tiras = dict(re.findall(r'(\w+):\s*"([rcamf]+)"', fonte))
    assert tiras, 'nao achei nenhuma tira em miniaturasDeTreino.ts'
    return tiras


def _da_carta():
    from scripts.gerar_miniaturas_de_treino import MINIATURAS, spot, tira
    from leaklab.preflop_gto_ranges import _load
    ranges = _load().get('ranges') or {}
    return {nome: (spot(ranges, b, s, h, v), tira(spot(ranges, b, s, h, v)))
            for nome, b, s, h, v in MINIATURAS}


def test_toda_tira_tem_169_celulas():
    """Uma célula por mão da grade 13×13. Menos que isso e o desenho sai torto; mais e sobra."""
    for nome, t in _do_arquivo().items():
        assert len(t) == 169, '%s tem %d caracteres, esperado 169' % (nome, len(t))
    print('OK  test_toda_tira_tem_169_celulas')


def test_o_no_consultado_EXISTE_na_carta():
    """O controle que pegou o lookup errado. Nó ausente devolve dict vazio e a miniatura vira uma
    grade toda cinza — que na tela tem cara de dado, não de erro."""
    vazios = [nome for nome, (sp, _) in _da_carta().items() if not sp.get('hand_freqs')]
    assert not vazios, ('nó não encontrado para %s: herói/vilão errados no gerador'
                        % ', '.join(vazios))
    print('OK  test_o_no_consultado_EXISTE_na_carta')


def test_a_miniatura_BATE_com_a_carta():
    """O guarda que impede o literal de envelhecer calado."""
    arquivo, carta = _do_arquivo(), _da_carta()
    for nome, (_sp, esperada) in carta.items():
        atual = arquivo.get(nome)
        assert atual is not None, 'a carta tem %s e o arquivo não' % nome
        if atual != esperada:
            difs = [i for i in range(169) if atual[i] != esperada[i]]
            raise AssertionError(
                '%s divergiu em %d células (ex.: posição %d, arquivo %r, carta %r). '
                'Rode `python scripts/gerar_miniaturas_de_treino.py`'
                % (nome, len(difs), difs[0], atual[difs[0]], esperada[difs[0]]))
    print('OK  test_a_miniatura_BATE_com_a_carta (%d spots)' % len(carta))


def test_cada_miniatura_ILUSTRA_alguma_coisa():
    """CONTRAPROVA dos testes acima: uma tira de 169 `f` passaria nos dois e não ilustraria nada.

    O limiar é baixo de propósito. Contra um 3-bet a 30bb o herói folda 93% e a forma REAL é
    pequena — a 1ª versão do controle usava 20 e deu alarme falso justamente ali.
    """
    for nome, t in _do_arquivo().items():
        vivas = sum(1 for ch in t if ch != 'f')
        assert vivas >= 5, '%s tem %d células ativas: não ilustra nada' % (nome, vivas)
    print('OK  test_cada_miniatura_ILUSTRA_alguma_coisa')


def test_as_tiras_sao_DIFERENTES_entre_si():
    """Se todas saíssem iguais, os cards ensinariam a mesma coisa com nomes diferentes — que é
    pior que não ter ilustração. Também pega um gerador que devolve sempre o mesmo nó."""
    tiras = _do_arquivo()
    assert len(set(tiras.values())) == len(tiras), (
        'duas miniaturas são idênticas: %s' % sorted(tiras))
    print('OK  test_as_tiras_sao_DIFERENTES_entre_si (%d spots)' % len(tiras))


def test_a_miniatura_NAO_carrega_detalhe_de_consulta():
    """Ela é ilustração. Ganhar rótulo de mão ou frequência a transforma numa segunda fonte de
    verdade sobre a range, ao lado de `/ranges` — o defeito que este projeto passa a semana
    consertando."""
    comp = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                                         'frontend', 'src', 'components', 'training',
                                         'MiniRange.tsx'))
    codigo = chr(10).join(l.split('//')[0] for l in io.open(comp, encoding='utf-8').read().split(chr(10)))
    for proibido in ('title=', 'cellHand', 'getHandFreq', 'HandCellLabel'):
        assert proibido not in codigo, (
            'MiniRange ganhou %r: ela virou consulta, e consulta mora em /ranges' % proibido)
    print('OK  test_a_miniatura_NAO_carrega_detalhe_de_consulta')


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
