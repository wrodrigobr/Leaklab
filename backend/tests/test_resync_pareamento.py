# -*- coding: utf-8 -*-
"""O resync pulava as decisoes que MAIS precisam de par.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

`resync_postflop_gto` casa a linha do banco com o recalculo por
`(hand_id, street, action_taken)`. Essa chave **nao e unica**: o hero age duas vezes na mesma
street sempre que paga e depois enfrenta um raise. Quando isso acontecia o script PULAVA a chave
inteira ("multi-decision ambiguo"), e essas decisoes simplesmente nunca eram reconciliadas.

Medido no acervo de producao em 05/08: 2 chaves, 4 decisoes. Pareadas por ordem, as quatro batem
CAMPO A CAMPO com o recalculo — e o sinal e distinguivel (`gto_action` = raise na primeira, call
na segunda), o que prova a correspondencia em vez de supo-la.

── Por que contagem diferente continua pulada ─────────────────────────────────────────────────

Quando os dois lados tem numero DIFERENTE de decisoes na mesma chave (torneio analisado por
versao anterior do parser), a correspondencia nao esta provada. Gravar no palpite escreveria o
solve na decisao errada — nesta base isso ja pos 90 vereditos errados na tela. Perder cobertura
e honesto; trocar veredito nao e.

── O pre-requisito silencioso ─────────────────────────────────────────────────────────────────

Parear por ordem so vale se a ordem for a MESMA dos dois lados. O `SELECT` do banco nao tinha
`ORDER BY` — no Postgres a ordem das linhas nao e garantida sem ele. Ha teste varrendo isso,
porque e o tipo de pre-requisito que some num refactor e nao quebra teste nenhum: o pareamento
continua "funcionando", so que casando as decisoes erradas.
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from resync_postflop_gto import _pares_por_ordem

_CAMINHO = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'resync_postflop_gto.py')


def _linha(i, gto):
    return {'id': i, 'gto_label': gto, 'gto_action': None, 'label': 'standard',
            'best_action': 'call'}


def _fresh(gto):
    return {'gto_label': gto, 'gto_action': None, 'label': 'standard', 'best': 'call'}


def test_duas_decisoes_na_mesma_chave_sao_pareadas_por_ordem():
    """O caso real: hero paga o open e depois paga o 3-bet, mesma street, mesma acao."""
    s = [_linha(10, 'gto_mixed'), _linha(11, None)]
    f = [_fresh('gto_mixed'), _fresh('gto_correct')]
    pares = _pares_por_ordem(s, f)
    assert len(pares) == 2, f'chave com 2 de cada lado voltou {len(pares)} pares'
    assert pares[0][0]['id'] == 10 and pares[0][1]['gto_label'] == 'gto_mixed'
    assert pares[1][0]['id'] == 11 and pares[1][1]['gto_label'] == 'gto_correct'


def test_o_caso_simples_continua_funcionando():
    pares = _pares_por_ordem([_linha(1, None)], [_fresh('gto_correct')])
    assert len(pares) == 1 and pares[0][0]['id'] == 1


def test_contagem_diferente_nao_pareia():
    """A guarda que impede o dano. Duas linhas no banco e uma recalculada nao dizem QUAL das duas
    e a recalculada — parear a primeira seria chute com cara de conserto."""
    assert _pares_por_ordem([_linha(1, None), _linha(2, None)], [_fresh('gto_correct')]) == []
    assert _pares_por_ordem([_linha(1, None)], [_fresh('a'), _fresh('b')]) == []
    assert _pares_por_ordem([], [_fresh('a')]) == []
    assert _pares_por_ordem([_linha(1, None)], []) == []


def test_nenhuma_linha_do_banco_e_usada_duas_vezes():
    """Reusar uma linha e o mesmo defeito por outro caminho: duas decisoes exibiriam o veredito
    de uma so."""
    s = [_linha(10, None), _linha(11, None), _linha(12, None)]
    pares = _pares_por_ordem(s, [_fresh('a'), _fresh('b'), _fresh('c')])
    ids = [p[0]['id'] for p in pares]
    assert ids == [10, 11, 12], ids
    assert len(set(ids)) == len(ids), 'linha do banco pareada mais de uma vez'


def test_os_selects_ordenam_por_id():
    """PRE-REQUISITO do pareamento por ordem, e o que some calado num refactor.

    Sem `ORDER BY id` o Postgres nao garante ordem, e o pareamento passa a casar as decisoes
    erradas sem quebrar nada visivelmente.
    """
    # SO CODIGO: os comentarios deste trecho CITAM "ORDER BY id" para explicar por que ele e
    # obrigatorio, e varrer prosa junto faria o guarda passar com o codigo quebrado. A primeira
    # versao deste teste fez exatamente isso — removi o ORDER BY de verdade e ele nao acusou.
    src = '\n'.join(l for l in open(_CAMINHO, encoding='utf-8').read().splitlines()
                    if not l.lstrip().startswith('#'))
    selects = re.findall(r'"SELECT id, hand_id, street, action_taken.*?\(tid,\)\)', src,
                         re.S)
    assert len(selects) >= 2, f'esperava 2 SELECTs de decisions, achei {len(selects)}'
    for i, sel in enumerate(selects):
        assert 'ORDER BY id' in sel, (
            f'SELECT #{i+1} de decisions perdeu o ORDER BY id — o pareamento por ordem passa a '
            f'casar decisoes erradas sem quebrar teste nenhum')


def test_a_chave_do_pareamento_nao_e_tratada_como_unica():
    """Regressao do comportamento antigo: `len(srows) != 1` era o descarte."""
    src = open(_CAMINHO, encoding='utf-8').read()
    assert 'len(srows) != 1' not in src, (
        'voltou o descarte por "chave tem mais de uma decisao" — as decisoes multiplas na mesma '
        'street param de ser reconciliadas de novo')


def test_avaliacao_fresca_e_fonte_unica_e_carrega_os_campos_viajantes():
    """Duas provas num teste: (1) o modulo tem UM SO lugar montando o dict fresco — eram dois
    builders copiados e em 12/08 o conserto editou um enquanto o comparador lia o outro;
    (2) a funcao carrega freq/ev/fonte junto do label, senao a linha gravada vira quimera
    (321149: gto_correct + small_mistake com ev=0.0 velho no banco e 1.61 na avaliacao)."""
    import inspect
    import scripts.resync_postflop_gto as R
    fonte = inspect.getsource(R)
    builders = fonte.count('"played":')
    assert builders == 1, (
        f'{builders} lugares montando o dict fresco — a regra dos N lugares: use _avaliacao_fresca')
    d = R._avaliacao_fresca({
        'evaluation': {'label': 'small_mistake'}, 'bestAction': 'allin',
        'gto': {'available': True, 'gto_label': 'gto_correct', 'gto_action': 'allin',
                'played_freq': 0.864, 'gto_freq': 0.864, 'ev_loss_bb': 1.61,
                'ev_loss_source': 'solver_hand'},
    })
    assert (d['played'], d['top'], d['ev'], d['ev_src']) == (0.864, 0.864, 1.61, 'solver_hand'), d
    # sem cobertura, os campos viajam como None — nunca sobra valor de outra avaliacao
    d2 = R._avaliacao_fresca({'evaluation': {}, 'gto': {'available': False, 'ev_loss_bb': 9.9}})
    assert d2['played'] is None and d2['ev'] is None and d2['tem_gto'] is False, d2
    print('OK  test_avaliacao_fresca_e_fonte_unica_e_carrega_os_campos_viajantes')


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
