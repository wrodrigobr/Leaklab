# -*- coding: utf-8 -*-
"""Recomputa os `*_pct` e o `avg_score` GRAVADOS em `tournaments` sem as decisoes multiway.

Por que existe (15/09): `recalcula_agregados_do_torneio` e `build_session_metrics` passaram a
excluir multiway postflop do denominador (`_SQL_MULTIWAY_FORA`), mas `tournaments.standard_pct`
e colunas irmas sao GRAVADAS por torneio na importacao e no resync. O acervo antigo continua
com o denominador velho ate alguem reescrever, e reescrever o acervo e decisao do dono, nao de
um conserto: o historico, o nivel e o feedback pos-torneio leem essas colunas.

Uso (SEMPRE com dry-run primeiro, contra a copia):

    cd backend
    DATABASE_URL=... python scripts/recomputa_standard_pct_sem_multiway.py --dry-run
    DATABASE_URL=... python scripts/recomputa_standard_pct_sem_multiway.py --dry-run --user 62
    DATABASE_URL=... python scripts/recomputa_standard_pct_sem_multiway.py --aplicar

`--dry-run` (padrao) so imprime o antes e o depois, torneio a torneio, e o resumo. `--aplicar`
grava pela MESMA funcao que o resync usa (`recalcula_agregados_do_torneio`), para nao existir
uma segunda formula em script. Sem `--aplicar` nada e escrito.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.schema import get_conn                                            # noqa: E402
from database.repositories import (_SQL_MULTIWAY_FORA, _adapt, _fetchall,       # noqa: E402
                                   _fetchone, recalcula_agregados_do_torneio)

COLS = ('standard_pct', 'marginal_pct', 'small_pct', 'clear_pct', 'avg_score')


def _depois(conn, tid):
    """O que `recalcula_agregados_do_torneio` gravaria: a MESMA consulta, sem o UPDATE."""
    r = _fetchone(conn, _adapt(
        "SELECT COUNT(CASE WHEN d.label='standard' THEN 1 END)*100.0/COUNT(*) AS s, "
        "COUNT(CASE WHEN d.label='marginal' THEN 1 END)*100.0/COUNT(*) AS m, "
        "COUNT(CASE WHEN d.label='small_mistake' THEN 1 END)*100.0/COUNT(*) AS sm, "
        "COUNT(CASE WHEN d.label='clear_mistake' THEN 1 END)*100.0/COUNT(*) AS c, "
        "AVG(d.score) AS a, COUNT(*) AS n FROM decisions d WHERE d.tournament_id=? AND " + _SQL_MULTIWAY_FORA
    ), (tid,))
    return {'standard_pct': round(float(r['s'] or 0), 2), 'marginal_pct': round(float(r['m'] or 0), 2),
            'small_pct': round(float(r['sm'] or 0), 2), 'clear_pct': round(float(r['c'] or 0), 2),
            'avg_score': round(float(r['a'] or 0), 4), 'n_medidas': int(r['n'] or 0)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--dry-run', action='store_true', default=True, help='so mostra (padrao)')
    g.add_argument('--aplicar', action='store_true', help='grava, pela funcao do resync')
    ap.add_argument('--user', type=int, default=None, help='so os torneios deste user_id')
    args = ap.parse_args()
    aplicar = bool(args.aplicar)

    conn = get_conn()
    try:
        where = "WHERE t.user_id = ?" if args.user else ""
        params = (args.user,) if args.user else ()
        torneios = _fetchall(conn, _adapt(f"""
            SELECT t.id, t.user_id, t.tournament_id, t.standard_pct, t.marginal_pct, t.small_pct,
                   t.clear_pct, t.avg_score,
                   (SELECT COUNT(*) FROM decisions d WHERE d.tournament_id = t.id) AS n_total,
                   (SELECT COUNT(*) FROM decisions d WHERE d.tournament_id = t.id
                      AND NOT ({_SQL_MULTIWAY_FORA})) AS n_multiway
            FROM tournaments t {where} ORDER BY t.user_id, t.id"""), params)

        print('modo: %s | torneios: %d' % ('APLICAR' if aplicar else 'dry-run', len(torneios)))
        print('%-8s %-6s %-14s %6s %6s | %-8s %-8s %-8s %-8s %-8s' % (
            'id', 'user', 'torneio', 'n', 'multi', 'std', 'marg', 'small', 'clear', 'avg'))
        mudam, com_multiway, delta_std = 0, 0, []
        for t in torneios:
            if not t['n_total']:
                continue
            dep = _depois(conn, t['id'])
            antes = {c: (round(float(t[c]), 4 if c == 'avg_score' else 2) if t[c] is not None else None)
                     for c in COLS}
            if int(t['n_multiway'] or 0):
                com_multiway += 1
            mudou = any(antes[c] != dep[c] for c in COLS)
            if not mudou:
                continue
            mudam += 1
            if antes['standard_pct'] is not None:
                delta_std.append(dep['standard_pct'] - antes['standard_pct'])
            print('%-8s %-6s %-14s %6d %6d | %s' % (
                t['id'], t['user_id'], str(t['tournament_id'])[:14], t['n_total'], t['n_multiway'],
                '  '.join('%s->%s' % (antes[c], dep[c]) for c in COLS)))
            if aplicar:
                recalcula_agregados_do_torneio(conn, t['id'])
        if aplicar:
            conn.commit()
        print('\nresumo: %d torneios com multiway, %d mudariam de numero%s' % (
            com_multiway, mudam, ' (GRAVADOS)' if aplicar else ' (nada gravado)'))
        if delta_std:
            print('standard_pct: delta medio %+.2f pp, maior %+.2f, menor %+.2f' % (
                sum(delta_std) / len(delta_std), max(delta_std), min(delta_std)))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
