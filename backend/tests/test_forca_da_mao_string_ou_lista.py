# -*- coding: utf-8 -*-
"""A forca da mao nao pode depender do FORMATO em que as cartas chegam.

── O defeito ──────────────────────────────────────────────────────────────────────────────────

`_ranks_of` fazia `for c in cards`. Numa LISTA (`['9d','Qc']`) isso itera cartas; numa STRING
(`'9dQc'`) itera CARACTERE, entao os naipes viravam ranks. Como `_rv('d')` devolve 0, o heroi
entrava com **dois ranks fantasma de valor 0**, e o par de zeros contava como par: num board com
trinca, `sorted_cnt` virava `[3, 2, ...]` e `is_monster_hand` declarava **full house** para um 9Q
qualquer.

A MESMA mao respondia `monstro=True / cat=value` como string e `monstro=False / cat=air` como
lista. **O motor chama com string** (`input_data['hero_cards']`), entao o caminho vivo era o
quebrado.

── O tamanho, medido em 470 decisoes postflop reais ───────────────────────────────────────────

    cat=value    203 -> 63     (140 decisoes reclassificadas)
    cat=middle     0 -> 132    (o tier nem aparecia: o par fantasma curto-circuitava tudo)
    cat=air      267 -> 275
    monstro       44 -> 37

Consumidores afetados: o guarda "apostar monstro por valor nunca e erro grave", o G4 (que so age
com mao `air`), o `_estimador_infla` e a classificacao de intencao da aposta.

── Por que este teste existe assim ────────────────────────────────────────────────────────────

Um teste que so chamasse com lista (ou so com string) passaria com o bug presente. O que prova a
ausencia do defeito e **a mesma mao pelos DOIS formatos, exigindo resposta identica**.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.bet_intent import _ranks_of, _suits_of, is_monster_hand, made_hand_category

# (cartas do heroi, board, o que a mao realmente e)
_CASOS = [
    ('9dQc', ['3h', '3d', '3s'], 'trinca do BOARD: o heroi tem Q-alta, nao full house'),
    ('6c8c', ['Ks', '8s', '8d'], 'trinca de 8 COM o heroi'),
    ('JdJc', ['Qc', '2h', 'Jh'], 'set de valetes'),
    ('AsKd', ['Qc', '7h', '2s'], 'A-alta sem par'),
    ('9d5c', ['7d', 'Tc', '6h'], 'sem par, so gutshot'),
    ('4d4s', ['8h', 'Th', '4h', 'As', 'Tc'], 'full: 44 com o board pareado'),
    ('AhKh', ['2h', '7h', 'Qh'], 'flush com carta do heroi'),
    ('2c3d', ['Ah', 'Kh', 'Qh'], 'nada, board de tres naipes iguais'),
]


def _lista(compacta):
    return [compacta[i:i + 2] for i in range(0, len(compacta), 2)]


def test_string_e_lista_dao_a_MESMA_forca():
    """O guarda central. Vale para as duas funcoes e para todos os casos."""
    for compacta, board, porque in _CASOS:
        em_lista = _lista(compacta)
        assert is_monster_hand(compacta, board) == is_monster_hand(em_lista, board), \
            f'monstro divergiu por formato em {compacta} / {board} ({porque})'
        assert made_hand_category(compacta, board) == made_hand_category(em_lista, board), \
            f'categoria divergiu por formato em {compacta} / {board} ({porque})'


def test_trinca_do_BOARD_nao_e_monstro_do_heroi():
    """O caso que denunciou o bug. `9dQc` num board `333` tem Q-alta: quem tem a trinca e a mesa,
    e todo mundo a compartilha. Antes, os dois zeros fantasma formavam o 'par' do full house."""
    assert is_monster_hand('9dQc', ['3h', '3d', '3s']) is False
    assert made_hand_category('9dQc', ['3h', '3d', '3s']) == 'air'
    # CONTROLE: com a trinca de fato do heroi, segue monstro
    assert is_monster_hand('3c3d', ['3h', 'Kd', '7s']) is True


def test_ranks_e_suits_nao_leem_naipe_como_rank():
    """A raiz, testada direto: `_rv('d')` devolve 0, entao qualquer naipe lido como rank vira um
    fantasma que se pareia com outro fantasma."""
    assert _ranks_of('9dQc') == ['9', 'Q']
    assert _ranks_of(['9d', 'Qc']) == ['9', 'Q']
    assert _suits_of('9dQc') == ['d', 'c']
    assert _suits_of(['9d', 'Qc']) == ['d', 'c']
    # tolera espacos e virgulas, que aparecem em texto colado
    assert _ranks_of('9d Qc') == ['9', 'Q']
    assert _ranks_of('9d,Qc') == ['9', 'Q']


def test_o_tier_middle_existe():
    """`middle` nao aparecia em NENHUMA das 470 decisoes medidas: o par fantasma mandava tudo
    para `value` antes de chegar la. Se este teste falhar, o curto-circuito voltou."""
    assert made_hand_category('Kd7c', ['Kh', '4s', '9d']) == 'middle', 'top pair kicker fraco'
    assert made_hand_category('8d8c', ['Ah', '4s', '9d']) == 'middle', 'underpair'
    # CONTROLE das duas pontas, para o teste nao virar "tudo e middle"
    assert made_hand_category('AdKc', ['Kh', '4s', '9d']) == 'value', 'top pair kicker forte'
    assert made_hand_category('7d2c', ['Kh', '4s', '9d']) == 'air'


def test_sem_cartas_ou_sem_board_nao_inventa_forca():
    for cartas, board in (('', ['Kh']), (None, ['Kh']), ('AdKc', []), ('AdKc', None)):
        assert is_monster_hand(cartas, board) is False
        assert made_hand_category(cartas, board) == 'air'


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
