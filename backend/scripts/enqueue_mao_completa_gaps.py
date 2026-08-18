# -*- coding: utf-8 -*-
"""enqueue_mao_completa_gaps.py — fila das LACUNAS da mão inteira (Fase 3 do catálogo).

Medido em prod (17/08): 167 mãos jogáveis ponta a ponta e **224 a UMA street** de virarem
jogáveis (163 a duas). Este script enfileira o solve exatamente dessas streets — trabalho de
FILA, não de produto: o consumer drena, o sync pós-solve grava os labels, e o acervo cresce
sem mexer em código.

Portas únicas, nada recriado aqui:
- candidatas/linhas/gate: `leaklab.mao_completa` (o MESMO seletor do drill);
- o hash do solve: `_hashes_da_linha(...)` da api (a 1ª variante é a que o resolver procura
  primeiro — enfileirar outro hash seria gravar com uma chave e procurar com outra);
- ranges: `resolve_solver_ranges` (fonte única do espelho hero/vilão).

DRY-RUN por padrão; --apply enfileira; --max-streets=N (default 1) controla a distância.
Uso (container): docker exec app-web-1 python scripts/enqueue_mao_completa_gaps.py [--apply]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repositories import enqueue_solver_spot, get_gto_node            # noqa: E402
from leaklab import mao_completa as mc                                         # noqa: E402
from leaklab.gto_solver import (_priority, _solver_params_for_stack,           # noqa: E402
                                resolve_solver_ranges)
from leaklab.gto_utils import board_for_street                                 # noqa: E402

apply = '--apply' in sys.argv
max_streets = next((int(a.split('=', 1)[1]) for a in sys.argv
                    if a.startswith('--max-streets=')), 1)

from api.app import _hashes_da_linha, _resolve_best_action_from_node           # noqa: E402

maos_1 = enfileirados = ja_na_fila = sem_dados = 0
vistos: set = set()
for chave in mc.maos_candidatas():
    linhas = mc._linhas_da_mao(*chave)
    pf = [d for d in linhas if (d.get('street') or '').lower() in mc._POSTFLOP]
    if not pf:
        continue
    faltando = [d for d in pf if not mc.street_gradeavel_gto(d, _resolve_best_action_from_node)]
    if not faltando or len(faltando) > max_streets:
        continue
    maos_1 += 1
    for d in faltando:
        street = (d.get('street') or '').lower()
        try:
            board = d.get('board') or []
            board = json.loads(board) if isinstance(board, str) else list(board)
        except Exception:
            board = []
        board = board_for_street(board, street)
        hc = (d.get('hero_cards') or '').replace(' ', '')
        hero = [hc[i:i + 2] for i in range(0, len(hc), 2)] if hc else []
        stack = float(d.get('stack_bb') or 0)
        facing = round(float(d.get('facing_bet') or 0), 2)
        pos = (d.get('position') or '').upper()
        vs = (d.get('vs_position') or '').upper()
        if not board or len(hero) != 2 or stack <= 0 or not pos:
            sem_dados += 1
            continue
        hashes = _hashes_da_linha(street, pos, board, hero, stack, facing, d.get('is_3bet'))
        if not hashes:
            sem_dados += 1
            continue
        h = hashes[0]                      # a variante que o resolver procura PRIMEIRO
        if h in vistos:
            continue
        vistos.add(h)
        if get_gto_node(h):
            ja_na_fila += 1                # nó existe (sem hand_table utilizável) — re-solve
        params = _solver_params_for_stack(stack)
        rr = resolve_solver_ranges(pos, vs, stack)
        pot = round(float(d.get('pot_size') or 0), 2) or (facing * 2 + 2 or 4.0)
        payload = json.dumps({
            'street': street, 'board': board, 'position': pos, 'hero_hand': hero,
            'hero_stack_bb': stack, 'facing_size_bb': facing,
            'oop_range': rr[1], 'ip_range': rr[0],
            'pot_bb': pot,
            'effective_stack_bb':        params['effective_stack_bb'],
            'max_iterations':            params['max_iterations'],
            'target_exploitability_pct': params['target_exploitability_pct'],
            '_meta': {'position': pos, 'vs_position': vs, 'hero_hand': hero,
                      'origem': 'mao_completa_gap'},
        })
        if apply:
            # Regra 6: o retorno diz se REALMENTE entrou (pending/running não são tocados);
            # ignorá-lo faria o script declarar 228 com a fila intacta.
            if not enqueue_solver_spot(h, payload, priority=_priority(street)):
                ja_na_fila += 1
                continue
        enfileirados += 1

modo = 'ENFILEIRADOS' if apply else 'SERIAM enfileirados (dry-run)'
print(f'maos a <= {max_streets} street(s) de jogaveis: {maos_1} | {modo}: {enfileirados} '
      f'(hashes distintos) | com no existente (re-solve): {ja_na_fila} | sem dados: {sem_dados}')
if not apply and enfileirados:
    print('Rode com --apply. O consumer drena a fila e o sync pos-solve grava os labels.')
