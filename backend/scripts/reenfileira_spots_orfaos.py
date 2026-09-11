# -*- coding: utf-8 -*-
"""Re-enfileira para solve os spots cujo NO existe sob a chave velha e nao sob a chave de hoje.

── O que originou (11/09/2026) ────────────────────────────────────────────────────────────

As 727 decisoes que o reparo classificou como `vanished` (veredito gravado, avaliacao fresca sem
cobertura) nao eram falta de gabarito. Medido, e com o motor dizendo o motivo com as proprias
palavras (`coverage_reason`): **97% sao `sem_no_para_o_spot`**, e ao mesmo tempo **693 das 727
tem no COMPLETO sob o `spot_hash` gravado na decisao**. Em 81% de uma amostra a mao ate esta na
tabela desse no. Ou seja: o no existe, a CHAVE mudou. O solve ficou guardado sob um hash que o
lookup de hoje nao consulta.

── Por que re-enfileirar, e nao re-chavear ────────────────────────────────────────────────

Re-chavear no orfao e proibido nesta casa, e a razao esta em [[project_board_hash_bug]]: colar a
estrategia de um nó numa chave nova pode significar servir river em decisao de flop. Aqui o
caminho honesto e pedir o solve de novo, sob a chave atual, e deixar o no velho onde esta.

── Por que reusar o caminho do UPLOAD ─────────────────────────────────────────────────────

A chave tem de sair IDENTICA a que o motor procura. Reimplementar o enfileiramento aqui criaria
uma terceira chave e o mesmo bug com outro nome. Entao a passagem faz o que o upload faz:
`parse_hand_history` -> `_analyze_hands` -> `_enqueue_postflop_spots`. O enfileiramento do upload
ja pula o que tem no, entao rodar duas vezes nao duplica trabalho.

Depois do solve, NINGUEM precisa rodar reparo: o `solved_at` novo fica mais recente que
`labels_reconciled_at`, o gancho da fila drenada dispara e anexa o veredito (e corrige o rotulo
velho, que e o que o `MODO_PRESERVA` faz desde 10/09).

Uso:
    python scripts/reenfileira_spots_orfaos.py --tids "154 363 364"        # dry-run
    python scripts/reenfileira_spots_orfaos.py --tids-arquivo van.txt --apply
"""
import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt, get_gto_node                        # noqa: E402
from leaklab.gto_utils import compute_spot_hash, normalize_position, board_for_street  # noqa: E402
from leaklab.parser import parse_hand_history                                 # noqa: E402


def _spots_do_torneio(tid: int):
    """Os spots postflop do torneio pela MESMA receita do upload, com o hash de hoje.

    Devolve [(spot_hash, tem_no)], para o dry-run contar sem escrever nada. A montagem do hash
    usa `board_for_street` + `normalize_position`, como `_enqueue_postflop_spots`: o banco guarda
    o runout inteiro de proposito e quem consome corta (ver a docstring de `board_for_street`).
    """
    from api.app import _analyze_hands
    conn = get_conn()
    try:
        raw = conn.execute(_adapt("SELECT raw_text FROM tournaments WHERE id = ?"), (tid,)).fetchone()
        raw = dict(raw).get('raw_text') if raw else None
    finally:
        conn.close()
    if not raw:
        return [], []
    try:
        hands = parse_hand_history(raw)
    except Exception:
        return [], []
    results, _hand_results, _erros = _analyze_hands(hands)
    saida = []
    for d in results:
        if d.get('street') not in ('flop', 'turn', 'river'):
            continue
        spot = d.get('spot') or {}
        ctx = d.get('context') or {}
        board = board_for_street(d.get('board', []), d.get('street'))
        hero = d.get('hero_cards') or []
        pos = normalize_position(spot.get('position', ctx.get('position', '')))
        if not board or not hero or not pos:
            continue
        try:
            stack = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
            facing = float(spot.get('facingToBb') or 0)
        except (TypeError, ValueError):
            continue
        h = compute_spot_hash(d.get('street'), pos, board, hero, stack, facing,
                              spot.get('potType', '') or '')
        saida.append((h, bool(get_gto_node(h))))
    return results, saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tids', default=None, help='ids separados por espaco')
    ap.add_argument('--tids-arquivo', default=None)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    bruto = args.tids or (io.open(args.tids_arquivo, encoding='utf-8').read()
                          if args.tids_arquivo else '')
    tids = [int(x) for x in bruto.replace(',', ' ').split() if x.strip().isdigit()]
    if not tids:
        print('nenhum torneio informado'); return
    print('torneios: %d | modo: %s' % (len(tids), 'APLICA' if args.apply else 'dry-run'))

    from api.app import _enqueue_postflop_spots
    conn = get_conn()
    try:
        donos = {}
        for t in tids:
            r = conn.execute(_adapt("SELECT user_id FROM tournaments WHERE id = ?"), (t,)).fetchone()
            donos[t] = dict(r)['user_id'] if r else None
    finally:
        conn.close()

    total_spots = sem_no = 0
    for i, tid in enumerate(tids, 1):
        try:
            results, spots = _spots_do_torneio(tid)
        except Exception as e:                                        # noqa: BLE001
            print('  tid %-6s ERRO: %s' % (tid, e))
            continue
        faltando = [h for h, tem in spots if not tem]
        total_spots += len(spots)
        sem_no += len(faltando)
        if faltando and args.apply:
            # O MESMO enfileiramento do upload: ele proprio pula o que ja tem no.
            _enqueue_postflop_spots(results, tournament_id=tid, user_id=donos.get(tid))
        if faltando:
            print('  [%3d/%3d] tid %-6s %4d spots, %4d sem no%s'
                  % (i, len(tids), tid, len(spots), len(faltando),
                     ' -> enfileirados' if args.apply else ''))
    print()
    print('spots postflop olhados : %d' % total_spots)
    print('SEM no (para solvar)   : %d' % sem_no)
    print('\n%s' % ('APLICADO' if args.apply else 'DRY-RUN (use --apply)'))


if __name__ == '__main__':
    main()
