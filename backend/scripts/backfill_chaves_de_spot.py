#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preenche `spot_family_key` e `spot_hash` nas decisoes ja gravadas (Protocolo de Progressao, Fase 0).

SECO POR PADRAO. Sem `--aplicar` nao escreve nada, so mede.

── Por que este script nao recalcula nada por conta propria ───────────────────────────────────────

Ele chama `familia_spot.chaves_de_decisao`, exatamente a mesma funcao que a gravacao usa. Ter uma
rotina que grava o presente e outra que preenche o passado e como a base fica com duas populacoes
de chave que nao casam — foi literalmente o bug do board no hash (gravava com 5 cartas, procurava
com 3, tres meses, 74,6% das decisoes postflop sem cobertura).

── O que ele NAO faz, de proposito ────────────────────────────────────────────────────────────────

Nao inventa chave onde falta insumo. Decisao sem posicao, sem stack ou sem cartas fica com a coluna
NULL, e o relatorio final diz quantas ficaram e por que. Chave chutada contaminaria a agregacao em
silencio, que e pior do que coluna vazia: a serie de EV da familia viraria media de coisas
diferentes.

Uso:
    python scripts/backfill_chaves_de_spot.py                 # so mede
    python scripts/backfill_chaves_de_spot.py --aplicar       # grava
    python scripts/backfill_chaves_de_spot.py --aplicar --refazer   # inclui as ja preenchidas
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from database.schema import get_conn                      # noqa: E402
from leaklab.familia_spot import chaves_de_decisao        # noqa: E402


def _board(valor):
    """O board e gravado como JSON. Lista ja decodificada tambem passa (SQLite vs PG)."""
    if not valor:
        return []
    if isinstance(valor, list):
        return valor
    try:
        v = json.loads(valor)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--aplicar', action='store_true', help='grava (sem isto, so mede)')
    ap.add_argument('--refazer', action='store_true',
                    help='recalcula tambem as decisoes que ja tem chave')
    ap.add_argument('--limite', type=int, default=0, help='0 = todas')
    args = ap.parse_args()

    conn = get_conn()
    onde = '' if args.refazer else 'WHERE spot_family_key IS NULL OR spot_hash IS NULL'
    lim = f' LIMIT {int(args.limite)}' if args.limite else ''
    rows = conn.execute(
        'SELECT id, street, position, stack_bb, vs_position, is_3bet, board, hero_cards, '
        f'facing_bet FROM decisions {onde} ORDER BY id{lim}').fetchall()

    print(f'decisoes a processar: {len(rows)}'
          + ('' if args.refazer else ' (so as que estao sem chave)'))

    motivos = Counter()
    updates = []
    for r in rows:
        fam, h = chaves_de_decisao(
            street=r['street'], position=r['position'], stack_bb=r['stack_bb'],
            vs_position=r['vs_position'], is_3bet=r['is_3bet'],
            board=_board(r['board']), hero_cards=r['hero_cards'],
            facing_bet=r['facing_bet'],
        )
        # Falha FECHADA e o comportamento certo, mas precisa ser CONTADA E ATRIBUIDA: "sem
        # familia" sozinho nao diz o que consertar, e diagnostico inacionavel encerra a
        # investigacao do mesmo jeito que um zero tranquilizador.
        if fam is None or h is None:
            falta = []
            if not (r['street'] or '').strip():
                falta.append('street')
            if not (r['position'] or '').strip():
                falta.append('position')
            if r['stack_bb'] is None:
                falta.append('stack_bb')
            if not str(r['hero_cards'] or '').strip():
                falta.append('hero_cards')
            rotulo = ', '.join(falta) or '(insumo presente, hash recusado pelo motor)'
            if fam is None:
                motivos[f'sem familia — falta: {rotulo}'] += 1
            if h is None:
                motivos[f'sem hash — falta: {rotulo}'] += 1
        if fam is not None or h is not None:
            updates.append((fam, h, r['id']))

    print(f'  com ao menos uma chave calculada: {len(updates)}')
    for k, v in motivos.most_common():
        print(f'    {k}: {v}')

    if not args.aplicar:
        print('\nSECO — nada gravado. Rode com --aplicar para escrever.')
        conn.close()
        return 0

    # `_adapt` converte `?` para `%s` no PG. Escrever a conversao aqui a mao seria a segunda copia
    # de uma regra que ja tem dono, e a versao que eu tinha escrito estava com precedencia errada.
    from database.repositories import _adapt
    sql = _adapt('UPDATE decisions SET spot_family_key = ?, spot_hash = ? WHERE id = ?')
    for fam, h, did in updates:
        conn.execute(sql, (fam, h, did))
    conn.commit()

    # CONFERENCIA EXPLICITA: `UPDATE` que nao casa linha nenhuma nao da erro, apenas nao faz nada.
    # Sem reler o banco, "gravei 9216" seria a mesma frase para sucesso e para falha silenciosa.
    n_fam = conn.execute(
        'SELECT COUNT(*) AS n FROM decisions WHERE spot_family_key IS NOT NULL').fetchone()['n']
    n_hash = conn.execute(
        'SELECT COUNT(*) AS n FROM decisions WHERE spot_hash IS NOT NULL').fetchone()['n']
    total = conn.execute('SELECT COUNT(*) AS n FROM decisions').fetchone()['n']
    print(f'\nAPLICADO. Conferido no banco: {n_fam}/{total} com familia, {n_hash}/{total} com hash.')
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
