# -*- coding: utf-8 -*-
"""
Catalogo de perguntas de range.

── O que o usuario reportou ───────────────────────────────────────────────────────────────────────

*"Estes desafios de range estao muito basicos e repetitivos. Temos que criar mais opcoes, algumas
mais basicas, outras mais avancadas, sempre com a explicacao apos escolha do usuario."*

Medido antes de construir: existia UM tipo, "que fatia das maos {pos} tem aqui?". Variava posicao e
stack, mas a forma era sempre a mesma.

── O que este arquivo trava, e por que cada guarda existe ─────────────────────────────────────────

1. **Explicacao sempre.** Foi pedido explicito, e sem ela o exercicio vira sorteio com feedback
   binario: o aluno acerta e nao sabe por que, erra e nao aprende.

2. **A correta nao mora numa posicao fixa.** Este projeto ja congelou por meses um quiz vencivel
   sem ler, com o comentario "a opcao certa e sempre a 1a" dentro do teste. Aqui a distribuicao e
   medida em muitas geracoes.

3. **Nunca perguntar o que nao tem resposta certa.** "A mao entra?" so pode usar nucleo (>=90%) ou
   lixo (<10%). Perguntar isso de uma mao MISTA e cobrar uma resposta que o GTO nao da, e ensinar
   errado e pior que repetir exercicio.

4. **Sem cobertura, devolve None.** Nao inventa alternativa. Alternativa falsa nao e um exercicio
   ruim, e um exercicio que mente.
"""
import os, random, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.perguntas_de_range import (gerar, DIFICULDADES, p_mao_entra, p_quem_abre_mais,
                                        p_efeito_do_stack, p_qual_e_mista)


def _muitas(n=60, **kw):
    rng = random.Random(11)
    out = []
    for _ in range(n):
        q = gerar(rng, **kw)
        if q:
            out.append(q)
    return out


def test_toda_pergunta_tem_explicacao():
    qs = _muitas()
    assert qs, 'nenhuma pergunta gerada — sem isso o resto do arquivo nao prova nada'
    for q in qs:
        assert q.get('explicacao') and len(q['explicacao']) > 40, q


def test_toda_pergunta_tem_opcoes_e_indice_valido():
    for q in _muitas():
        assert len(q['opcoes']) >= 2, q
        assert 0 <= q['correta'] < len(q['opcoes']), q
        assert len(set(q['opcoes'])) == len(q['opcoes']), f'alternativas repetidas: {q}'


def test_a_correta_NAO_mora_numa_posicao_fixa():
    """O bug historico deste projeto: quiz vencivel sem ler, congelado por um teste que dizia
    'a opcao certa e sempre a 1a'."""
    pos = Counter(q['correta'] for q in _muitas(120))
    assert len(pos) >= 2, f'a correta caiu sempre no mesmo indice: {dict(pos)}'
    # nenhuma posicao pode concentrar quase tudo
    total = sum(pos.values())
    assert max(pos.values()) / total < 0.8, dict(pos)


def test_as_tres_dificuldades_produzem():
    for d in DIFICULDADES:
        qs = _muitas(30, dificuldade=d)
        assert qs, f'dificuldade sem nenhuma pergunta: {d}'
        assert all(q['dificuldade'] == d for q in qs), d


def test_ha_mais_de_UM_tipo_de_pergunta():
    """O ponto do usuario. Um catalogo com um tipo so e o que ele reclamou."""
    tipos = {q['tipo'] for q in _muitas(120)}
    assert len(tipos) >= 3, tipos


def test_mao_entra_NUNCA_pergunta_de_mao_mista():
    """Uma mao de fronteira nao tem resposta certa para 'entra?'. Cobrar uma ensinaria errado."""
    from leaklab.leak_trainer import _estratos, _HANDS
    rng = random.Random(3)
    for _ in range(25):
        for pos in ('UTG', 'CO', 'BTN'):
            q = p_mao_entra(rng, pos, 30)
            if not q:
                continue
            mao = q['pergunta'].split()[1]
            est = _estratos(pos, list(_HANDS), 30)
            assert mao not in (est.get('fronteira') or []), (pos, mao, q['pergunta'])


def test_quem_abre_mais_usa_posicoes_com_larguras_DISTANTES():
    """Sem distancia, a resposta depende de arredondamento e duas alternativas viram a mesma."""
    from leaklab.academy_questions import _larguras_por_posicao
    larg = _larguras_por_posicao(30) or {}
    rng = random.Random(5)
    for _ in range(30):
        q = p_quem_abre_mais(rng, 30)
        if not q:
            continue
        a, b = q['opcoes']
        if a in larg and b in larg:
            assert abs(larg[a] - larg[b]) >= 6, (a, b, larg[a], larg[b])


def test_sem_cobertura_devolve_None_em_vez_de_inventar():
    rng = random.Random(1)
    assert p_mao_entra(rng, 'POSICAO_QUE_NAO_EXISTE', 30) is None
    assert p_qual_e_mista(rng, 'POSICAO_QUE_NAO_EXISTE', 30) is None
    assert p_efeito_do_stack(rng, 'POSICAO_QUE_NAO_EXISTE', 20, 50) is None


def test_efeito_do_stack_so_pergunta_quando_ha_diferenca_real():
    """Mesma profundidade, ou diferenca dentro do ruido, nao tem resposta defensavel."""
    rng = random.Random(9)
    assert p_efeito_do_stack(rng, 'BTN', 30, 30) is None


def test_dificuldade_inexistente_nao_estoura():
    assert gerar(random.Random(2), dificuldade='impossivel') is None


# ── Ligacao no fluxo do treino ─────────────────────────────────────────────────────────────────

def test_o_catalogo_chega_no_SPOT_do_treino():
    """Sem isto, o catalogo existiria e ninguem o veria — o modo mais silencioso de nao entregar."""
    import random as _r, collections
    from leaklab.leak_trainer import generate_canonical_spot
    rng = _r.Random(4)
    cat = {'kind': 'preflop', 'scenario': 'rfi', 'position': 'UTG',
           'vs_position': '', 'stack_bb': 30, 'key': 'rfi:UTG::30'}
    tipos = collections.Counter()
    for _ in range(120):
        sp = generate_canonical_spot(cat, rng)
        if sp and sp.get('range_probe'):
            tipos[sp['range_probe'].get('tipo')] += 1
    # `rfi` NAO tinha pergunta nenhuma antes: a sondagem exige vilao a ler
    assert sum(tipos.values()) > 0, 'spot rfi continua sem pergunta'
    assert len(tipos) >= 2, tipos


def test_excluir_mao_e_DETERMINISTICO():
    """A armadilha da ligacao: um spot "UTG a 30bb, o que fazer com KTo?" precedido de "UTG abre
    KTo a 30bb?" da a resposta de graca.

    A primeira versao deste teste gerava 150 spots e conferia se a mao do spot aparecia na
    pergunta. Ele passava mesmo com `excluir_mao` DESLIGADO, porque a colisao depende de o
    catalogo sortear exatamente aquela mao entre dezenas — ou seja, dependia de sorte. Guarda que
    depende de sorte nao e guarda. Agora exclui uma mao especifica e exige que ela NUNCA saia.
    """
    from leaklab.leak_trainer import _estratos, _HANDS
    pos = 'UTG'
    est = _estratos(pos, list(_HANDS), 30)
    assert est, 'sem cobertura para UTG a 30bb — o teste nao provaria nada'
    # Um alvo por estrato basta: o que se testa e o FILTRO, e ele nao distingue estrato. Mais
    # alvos so multiplicariam o custo do `_estratos`, que reanalisa cada mao.
    alvos = [g[0] for g in (est.get('nucleo'), est.get('lixo'), est.get('fronteira')) if g]
    assert alvos, est
    for alvo in alvos:
        rng = random.Random(21)
        for _ in range(25):
            for q in (p_mao_entra(rng, pos, 30, excluir_mao=alvo),
                      p_qual_e_mista(rng, pos, 30, excluir_mao=alvo)):
                if not q:
                    continue
                assert alvo not in q['pergunta'].split(), (alvo, q['pergunta'])
                assert alvo not in q['opcoes'], (alvo, q['opcoes'])


def test_o_treino_PASSA_a_mao_do_spot_para_a_exclusao():
    """O outro lado: a funcao aceita `excluir_mao`, mas alguem precisa passar. Sem esta linha o
    parametro existiria sem nunca ser usado."""
    fonte = open('leaklab/leak_trainer.py', encoding='utf-8').read()
    assert 'excluir_mao=_hand' in fonte, 'o treino nao esta passando a mao do spot'


def test_a_sondagem_antiga_continua_existindo_e_identificavel():
    """Ela e a mais forte pedagogicamente (fala da mao que o aluno vai jogar). O catalogo entrou
    para SOMAR, nao para substituir. E agora ela carrega `tipo`, senao qualquer contagem a
    confundia com "nenhuma pergunta" — foi o que aconteceu na minha primeira medicao."""
    import random as _r
    from leaklab.leak_trainer import generate_canonical_spot
    rng = _r.Random(4)
    cat = {'kind': 'preflop', 'scenario': 'vs_rfi', 'position': 'BB',
           'vs_position': 'BTN', 'stack_bb': 30, 'key': 'k'}
    vistos = set()
    for _ in range(150):
        sp = generate_canonical_spot(cat, rng)
        rp = (sp or {}).get('range_probe')
        if rp:
            vistos.add(rp.get('tipo'))
    assert 'largura_do_vilao' in vistos, vistos
    assert None not in vistos, 'pergunta sem `tipo` (invisivel em contagem)'


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
