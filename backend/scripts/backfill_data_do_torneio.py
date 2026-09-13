# -*- coding: utf-8 -*-
"""Preenche `played_at`, `started_at` e `ended_at` de quem ficou sem, a partir do `raw_text`.

── Por que existe ─────────────────────────────────────────────────────────────────────────────

A regra "quando esta mao foi jogada" vivia em dois lugares com listas PARCIAIS de formato: o
`_extract_date` nao conhecia o PartyPoker NOVO ("Thu Sep 10 18:54:46 EDT 2026") e o `_HAND_TS_RE`
nao conhecia nem o Party nem o 888. Medido em 13/09:

    played_at nulo:   5 de 5 registros do partypoker (100%)  |  0 nas outras 4 salas
    started_at nulo:  5 de 5 do partypoker                   |  0 nas outras

`timestamps_das_maos` unificou os quatro formatos, mas isso so vale para upload NOVO. Os
registros que ja entraram continuam sem data, e `played_at` e o eixo de tempo do produto (AY-4):
sem ele o torneio fica fora de todo filtro por periodo, do relatorio de evolucao e da projecao
de carreira.

── O que ele NAO faz, de proposito ────────────────────────────────────────────────────────────

Nao toca em registro que JA tem data. Mesmo onde ela possa estar errada (um registro misturado
podia ter a data de outra noite), trocar dado existente e decisao de produto, nao de backfill.
O alvo e so a ausencia.

    python -m scripts.backfill_data_do_torneio                 # dry-run (padrao)
    python -m scripts.backfill_data_do_torneio --apply --dump /tmp/datas.jsonl
    python -m scripts.backfill_data_do_torneio --reverter /tmp/datas.jsonl
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.schema import get_conn                                           # noqa: E402
from database.repositories import _adapt                                       # noqa: E402
from leaklab.parser import timestamps_das_maos                                  # noqa: E402


def _alvos(conn, site=None):
    """Registros com hand history e SEM pelo menos um dos tres campos de tempo."""
    where = ("raw_text IS NOT NULL AND raw_text <> '' AND "
             "(played_at IS NULL OR started_at IS NULL OR ended_at IS NULL)")
    params = []
    if site:
        where += " AND site=?"
        params.append(site)
    return [dict(r) for r in conn.execute(_adapt(
        "SELECT id, user_id, tournament_id, site, played_at, started_at, ended_at, raw_text "
        "FROM tournaments WHERE %s ORDER BY id" % where), tuple(params)).fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', help='so esta sala')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dump', help='registro para desfazer (exigido com --apply)')
    ap.add_argument('--reverter')
    a = ap.parse_args()

    if a.reverter:
        linhas = [json.loads(l) for l in io.open(a.reverter, encoding='utf-8') if l.strip()]
        conn = get_conn()
        for l in linhas:
            conn.execute(_adapt(
                "UPDATE tournaments SET played_at=?, started_at=?, ended_at=? WHERE id=?"),
                (l['played_at'], l['started_at'], l['ended_at'], l['id']))
        conn.commit(); conn.close()
        print('revertidos %d registros' % len(linhas))
        return

    if a.apply and not a.dump:
        print('ERRO: --apply exige --dump.')
        sys.exit(2)

    conn = get_conn()
    alvos = _alvos(conn, a.site)
    print('registros sem algum campo de tempo: %d' % len(alvos))
    print('=' * 86)
    plano = []
    sem_data_no_texto = []
    for d in alvos:
        ts = timestamps_das_maos(d.get('raw_text') or '')
        if not ts:
            sem_data_no_texto.append(d)
            continue
        novo = {'played_at': d['played_at'] or min(ts)[:10],
                'started_at': d['started_at'] or min(ts),
                'ended_at': d['ended_at'] or max(ts)}
        plano.append((d, novo))
        print('   t%-6s %-11s %-12s played %-12s -> %-12s | sessao %s .. %s' % (
            d['id'], d['site'], d['tournament_id'], str(d['played_at'] or '-'),
            novo['played_at'], novo['started_at'], novo['ended_at']))
    if sem_data_no_texto:
        print()
        print('   %d registro(s) em que o TEXTO nao declara data (nada a preencher):' %
              len(sem_data_no_texto))
        for d in sem_data_no_texto[:8]:
            print('      t%-6s %s' % (d['id'], d['site']))
    print()
    print('   a preencher: %d' % len(plano))
    if not a.apply:
        print('   dry-run. Para aplicar: --apply --dump <arquivo>')
        conn.close()
        return

    # O registro para desfazer vai para o disco ANTES de cada escrita: dump que fica no buffer
    # e dump que nao existe (regra 6, cicatriz do reparo multi-torneio).
    f = io.open(a.dump, 'w', encoding='utf-8')
    n = 0
    for d, novo in plano:
        f.write(json.dumps({'id': d['id'], 'played_at': d['played_at'],
                            'started_at': str(d['started_at']) if d['started_at'] else None,
                            'ended_at': str(d['ended_at']) if d['ended_at'] else None},
                           ensure_ascii=False) + chr(10))
        f.flush()
        os.fsync(f.fileno())
        conn.execute(_adapt(
            "UPDATE tournaments SET played_at=?, started_at=?, ended_at=? WHERE id=?"),
            (novo['played_at'], novo['started_at'], novo['ended_at'], d['id']))
        n += 1
    conn.commit()
    f.close()
    conn.close()
    print('   preenchidos: %d   |   para desfazer: --reverter %s' % (n, a.dump))


if __name__ == '__main__':
    main()
