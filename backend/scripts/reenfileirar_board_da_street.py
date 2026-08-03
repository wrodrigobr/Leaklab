# -*- coding: utf-8 -*-
"""reenfileirar_board_da_street.py — recupera os nós solvados com o board da street errada.

**O estrago, medido em produção 2026-08-03:** 1.977 dos 5.030 nós servíveis pelo trainer pool
(39,3%) foram solvados com o board COMPLETO da mão — um nó de `flop` cujo solve viu as cinco cartas
do river. Todos nasceram antes de 2026-07-28, quando o enfileiramento passou a cortar o board pela
street; **zero depois**. O código está certo, o estrago é legado.

O `trainer_pool` já foi ensinado a RECUSAR esses nós, então ninguém mais recebe veredito de river
numa decisão de flop. Isto aqui é a outra metade: devolver a cobertura perdida.

── O que este script NÃO faz ──────────────────────────────────────────────────────────────────────

**Não re-chaveia nó nenhum.** A memória deste projeto proíbe, e com razão: mudar a chave de um nó
órfão faria uma estratégia de river responder a uma decisão de flop — que é exatamente o dano que
estamos desfazendo. Aqui se ENFILEIRA UM SOLVE NOVO, com o board cortado e o hash recalculado a
partir dele. O nó antigo fica onde está, inerte, sem ser servido.

**Não apaga nada.** Se o solve novo falhar, o estado piora em zero.

── Uso ────────────────────────────────────────────────────────────────────────────────────────────

    python scripts/reenfileirar_board_da_street.py            # DRY-RUN (padrão): só relata
    python scripts/reenfileirar_board_da_street.py --executar  # enfileira de verdade
    python scripts/reenfileirar_board_da_street.py --limite 50 # teto de itens (teste)

Dry-run é o padrão de propósito. O script termina CONFERINDO o que fez: com `--executar` ele
recontas os pendentes e exige que o número tenha se mexido. Um `LIKE '%gto%'` num script anterior
deste projeto imprimiu "APLICANDO..." e escreveu ZERO em produção — só a reconferência pegou.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from database.schema import get_conn, USE_POSTGRES
from leaklab.gto_utils import (board_for_street, compute_spot_hash, normalize_position,
                               dinheiro_coerente)

_ESPERADO = {'flop': 3, 'turn': 4, 'river': 5}


def _adapt(sql: str) -> str:
    return sql.replace('?', '%s') if USE_POSTGRES else sql


def _carrega(v):
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return None


def _pendentes() -> int:
    with get_conn() as c:
        r = c.execute(_adapt("SELECT COUNT(*) AS n FROM gto_solver_queue "
                             "WHERE status IN ('pending','running')")).fetchone()
    return int(r['n'] or 0)


def levantar(limite: int | None = None) -> tuple:
    """`(alvos, descartados)` — as linhas cujo solve usou board maior que a street, e o que foi
    RECUSADO por dinheiro incoerente, com o motivo."""
    with get_conn() as c:
        linhas = c.execute(_adapt(
            "SELECT spot_hash, spot_json, status FROM gto_solver_queue "
            "WHERE spot_json IS NOT NULL")).fetchall()

    alvos = []
    descartados: dict = {}
    for r in linhas:
        sj = _carrega(r['spot_json']) or {}
        street = (sj.get('street') or '').lower()
        board = sj.get('board') or []
        n = _ESPERADO.get(street)
        if not n or not board or len(board) <= n:
            continue

        cortado = board_for_street(board, street)
        meta = sj.get('_meta') or {}
        pos = normalize_position(sj.get('position') or meta.get('position') or '')
        mao = sj.get('hero_hand') or meta.get('hero_hand') or []
        stack = float(sj.get('hero_stack_bb') or meta.get('hero_stack_bb') or 0)
        facing = float(sj.get('facing_size_bb') or meta.get('facing_size_bb') or 0)
        if not pos or not mao or not stack:
            continue                       # sem os campos da chave não dá para refazer o hash

        # **NÃO propagar payload podre.** A primeira versão deste script copiava o `spot_json`
        # inteiro e só trocava o board — e foi assim que ele reenfileirou **13 spots com pote ou
        # aposta em unidade errada**, um dos quais o usuário viu na tela ("aposta de 0.1bb?").
        # Copiar sem olhar transforma defeito legado em defeito de hoje, com data de hoje, e o
        # rastro se perde.
        _ok, _motivo = dinheiro_coerente(sj.get('pot_bb'), facing,
                                         sj.get('effective_stack_bb') or stack)
        if not _ok:
            descartados[_motivo] = descartados.get(_motivo, 0) + 1
            continue

        novo_hash = compute_spot_hash(street, pos, cortado, mao, stack, facing)
        if novo_hash == r['spot_hash']:
            continue                       # já está certo (não deveria cair aqui, mas não custa)

        novo_sj = dict(sj)
        novo_sj['board'] = cortado
        if meta:
            novo_meta = dict(meta)
            novo_meta['board'] = cortado
            novo_sj['_meta'] = novo_meta

        alvos.append({
            'hash_antigo': r['spot_hash'],
            'hash_novo': novo_hash,
            'street': street,
            'de': len(board),
            'para': len(cortado),
            'payload': json.dumps(novo_sj, sort_keys=True),
        })
        if limite and len(alvos) >= limite:
            break
    return alvos, descartados


def _ja_existe(hashes: list) -> set:
    """Quais dos hashes novos JÁ têm nó. Enfileirar esses seria refazer trabalho pronto."""
    if not hashes:
        return set()
    achados = set()
    with get_conn() as c:
        for i in range(0, len(hashes), 500):
            lote = hashes[i:i + 500]
            marks = ','.join('?' * len(lote))
            for r in c.execute(_adapt(
                    f"SELECT spot_hash FROM gto_nodes WHERE spot_hash IN ({marks})"),
                    tuple(lote)).fetchall():
                achados.add(r['spot_hash'])
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--executar', action='store_true',
                    help='enfileira de verdade (sem isto, apenas relata)')
    ap.add_argument('--limite', type=int, default=None, help='teto de itens')
    args = ap.parse_args()

    print('=' * 62)
    print('  Re-enfileiramento dos nós com board de street errada')
    print('=' * 62)

    alvos, descartados = levantar(args.limite)
    if descartados:
        print('\n  RECUSADOS por dinheiro incoerente (pote ou aposta em unidade impossivel):')
        for m, n in sorted(descartados.items()):
            print(f'    {m}: {n}')
    if not alvos:
        print('\n  Nenhum nó com board maior que a street. Nada a fazer.')
        return 0

    por_street = {}
    for a in alvos:
        por_street[a['street']] = por_street.get(a['street'], 0) + 1
    print(f'\n  encontrados: {len(alvos)}')
    print(f'  por street : {por_street}')

    existentes = _ja_existe([a['hash_novo'] for a in alvos])
    a_fazer = [a for a in alvos if a['hash_novo'] not in existentes]
    print(f'  já resolvidos sob o hash correto: {len(existentes)} (serão pulados)')
    print(f'  A ENFILEIRAR: {len(a_fazer)}')

    print('\n  amostra:')
    for a in a_fazer[:5]:
        print(f"    {a['street']:5s}  {a['de']} -> {a['para']} cartas   "
              f"{a['hash_antigo'][:10]} -> {a['hash_novo'][:10]}")

    if not args.executar:
        print('\n  DRY-RUN. Nada foi escrito.')
        print('  Para aplicar: python scripts/reenfileirar_board_da_street.py --executar')
        return 0

    if not a_fazer:
        print('\n  Nada a enfileirar.')
        return 0

    antes = _pendentes()
    print(f'\n  APLICANDO... (pendentes na fila antes: {antes})')

    from database.repositories import enqueue_solver_spot
    from leaklab.gto_solver import _priority

    feitos = falhas = 0
    for a in a_fazer:
        try:
            if enqueue_solver_spot(a['hash_novo'], a['payload'], priority=_priority(a['street'])):
                feitos += 1
        except Exception as e:
            falhas += 1
            if falhas <= 3:
                print(f"    falhou {a['hash_novo'][:10]}: {type(e).__name__}: {e}")

    depois = _pendentes()
    print(f'\n  enfileirados: {feitos}   falhas: {falhas}')
    print(f'  pendentes na fila: {antes} -> {depois}')

    # A CONFERÊNCIA. Script que imprime "APLICANDO" e escreve zero já aconteceu aqui.
    if feitos and depois <= antes:
        print('\n  ERRO: disse ter enfileirado e a fila NÃO cresceu. Nada foi confirmado.')
        return 1
    print('\n  OK — a fila cresceu, o que confirma a escrita.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
