# -*- coding: utf-8 -*-
"""`facing_allin_row` — fonte unica do "a aposta enfrentada e um all-in?" no dialeto-linha.

A derivacao (`facing_bet >= effective_stack_bb * 0.98`) vivia COPIADA em `api/app.py` (rota
do replay) e no `sync_gto_labels_from_ranges.py`, apontada pelo QA de aceitacao em 09/08.
Regra 5 do CLAUDE.md: regra aplicada em N lugares vira funcao, com teste que varre os N+1 —
a varredura abaixo e esse teste.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import facing_allin_row

BACKEND = os.path.join(os.path.dirname(__file__), '..')


def test_limiar_de_98_por_cento():
    assert facing_allin_row({'facing_bet': 20.0, 'effective_stack_bb': 20.0}) is True
    assert facing_allin_row({'facing_bet': 19.6, 'effective_stack_bb': 20.0}) is True   # == 98%
    assert facing_allin_row({'facing_bet': 19.5, 'effective_stack_bb': 20.0}) is False
    # aposta MAIOR que o stack (vilao cobre): continua all-in do ponto de vista do hero
    assert facing_allin_row({'facing_bet': 35.0, 'effective_stack_bb': 20.0}) is True


def test_linha_antiga_sem_effective_stack_cai_em_false():
    """`effective_stack_bb` NULL (linha pre-migracao) = comportamento de antes, sem chute."""
    assert facing_allin_row({'facing_bet': 20.0, 'effective_stack_bb': None}) is False
    assert facing_allin_row({'facing_bet': None, 'effective_stack_bb': 20.0}) is False
    assert facing_allin_row({}) is False
    assert facing_allin_row({'facing_bet': 'lixo', 'effective_stack_bb': 20.0}) is False


def test_varredura_nao_ha_copia_da_regra():
    """Varre o backend por reaparicoes do limiar. So a fonte unica pode conter a conta.

    O criterio e deliberadamente sensivel (linha com `0.98` E um insumo da regra): melhor um
    falso alarme que se explica do que uma quinta copia divergindo calada por tres meses —
    ja aconteceu com o corte do board e com o piso por direcao.
    """
    permitidos = {os.path.join('leaklab', 'decision_engine_v11.py')}
    achados = []
    for raiz, _dirs, files in os.walk(BACKEND):
        if any(p in raiz for p in ('.git', '__pycache__', 'node_modules', '.gw_profile')):
            continue
        for f in files:
            if not f.endswith('.py') or f == os.path.basename(__file__):
                continue
            caminho = os.path.join(raiz, f)
            rel = os.path.relpath(caminho, BACKEND)
            try:
                texto = open(caminho, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            for i, linha in enumerate(texto.splitlines(), 1):
                if '0.98' in linha and ('facing' in linha or 'effective_stack' in linha):
                    if rel not in permitidos:
                        achados.append(f'{rel}:{i}: {linha.strip()[:100]}')
    assert not achados, 'copia(s) da regra do all-in fora da fonte unica:\n  ' + '\n  '.join(achados)


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
