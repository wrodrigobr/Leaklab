# -*- coding: utf-8 -*-
"""Catálogo de TREINOS NOMEADOS (Fase 1, 17/08) — a lacuna de AGÊNCIA de
[[project_catalogo_de_treinos]]: quem sabe o que quer treinar agora consegue pedir.

Contratos: todo `cat:<id>` rende currículo E spot (vitrine sem 404); os filtros de BvB e
stack curto recortam certo; a estatística agrega da persistência que JÁ existia
(training_skill_progress), ponderada por tentativas.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.leak_trainer import (
    CATALOGO_TREINOS, curriculo_do_catalogo, next_spot, stats_do_catalogo,
    _chaves_da_entrada,
)


def test_bvb_recorta_so_blind_vs_blind():
    cats = curriculo_do_catalogo('bvb')
    assert cats, 'BvB vazio'
    for c in cats:
        par = {c['position'], c.get('vs_position') or ''}
        assert par <= {'SB', 'BB', ''}, f'categoria fora do BvB: {c["key"]}'
    assert any(c['scenario'] == 'rfi' and c['position'] == 'SB' for c in cats), 'faltou o RFI de SB'
    assert any(c['scenario'] == 'vs_rfi' for c in cats), 'faltou a defesa SBxBB'


def test_stack_curto_treina_a_12bb():
    cats = curriculo_do_catalogo('short')
    assert cats
    assert all(c['stack_bb'] == 12 for c in cats), 'stack curto tem que ser curto'


def test_todo_cat_do_catalogo_rende_spot():
    """Vitrine sem porta falsa: cada entrada `cat:` gera um spot de verdade (dev tem as ranges
    preflop gold; o catálogo postflop estático não depende de nó para GERAR — só para gradear)."""
    os.environ['TRAINER_POOL_POSTFLOP'] = '0'
    try:
        for e in CATALOGO_TREINOS:
            if not e['focus'].startswith('cat:'):
                continue
            cid = e['focus'].split(':', 1)[1]
            cats = curriculo_do_catalogo(cid)
            assert cats, f'{e["id"]}: curriculo vazio'
            spot = next_spot(cats, rng=random.Random(3))
            assert spot is not None, f'{e["id"]}: nenhum spot gerado'
    finally:
        os.environ.pop('TRAINER_POOL_POSTFLOP', None)


def test_id_desconhecido_devolve_vazio_sem_explodir():
    assert curriculo_do_catalogo('nao_existe') == []


def test_estatistica_agrega_da_persistencia_existente():
    skills = [
        {'category_key': 'vs_rfi:SB:BB:40', 'attempts': 20, 'correct': 15, 'mastery': 70.0},
        {'category_key': 'vs_rfi:CO:BTN:40', 'attempts': 50, 'correct': 40, 'mastery': 90.0},
        {'category_key': 'rfi:SB::12', 'attempts': 10, 'correct': 8, 'mastery': 60.0},
        {'category_key': 'pf:bb_3bet_pot', 'attempts': 5, 'correct': 4, 'mastery': 80.0},
    ]
    s = stats_do_catalogo(skills)
    # BvB = SBxBB (20) + rfi:SB (10); o CO×BTN fica fora
    assert s['bvb']['attempts'] == 30, s['bvb']
    assert abs(s['bvb']['mastery'] - (70 * 20 + 60 * 10) / 30) < 0.11, s['bvb']['mastery']
    # short = só a chave de 12bb
    assert s['short']['attempts'] == 10
    # postflop 3-bet = chave exata
    assert s['pf_bb_3bet']['attempts'] == 5 and s['pf_bb_3bet']['mastery'] == 80.0
    # adaptativo agrega tudo
    assert s['adaptive']['attempts'] == 85
    # sem tentativas: zero honesto, não ausência
    assert s['pf_bb_defense'] == {'attempts': 0, 'correct': 0, 'mastery': 0.0,
                                  'tier': s['pf_bb_defense']['tier'], 'last_practiced_at': None}


def test_chaves_da_entrada_nao_vazam_entre_treinos():
    assert _chaves_da_entrada('bvb', 'vs_rfi:BB:SB:25') is True
    assert _chaves_da_entrada('bvb', 'vs_rfi:BB:BTN:25') is False
    assert _chaves_da_entrada('short', 'vs_rfi:CO:BTN:15') is True
    assert _chaves_da_entrada('short', 'vs_rfi:CO:BTN:40') is False
    assert _chaves_da_entrada('short', 'pf:bb_defense') is False
    assert _chaves_da_entrada('fund_vs_3bet', 'vs_3bet:CO:BTN:40') is True
    assert _chaves_da_entrada('fund_vs_3bet', 'vs_rfi:CO:BTN:40') is False


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
