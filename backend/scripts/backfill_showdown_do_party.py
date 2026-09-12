# -*- coding: utf-8 -*-
"""Preenche `decisions.showdown_result` dos torneios ja importados que ficaram sem ele.

── Por que existe ─────────────────────────────────────────────────────────────────────────

O construtor de `ParsedHand` do caminho PartyGaming nunca passou por
`_extract_showdown_result`, e o extrator nao conhecia o formato do Party. Resultado na tela:
**o WTSD do dono zerou** depois do primeiro torneio do PartyPoker (11/09). O conserto vale para
import NOVO; o que ja esta no banco tem a coluna nula e continua mostrando zero.

── Por que nao usar `reprocess_tournament` ────────────────────────────────────────────────

Aquele script faz `save_decisions`, que e DELETE + insert. `decisions(id)` tem referencias com
FK CASCADE (anotacoes de coach, revisoes), e elas somem CALADAS — cicatriz registrada em
`project_cascade_apagava_anotacoes`. Para preencher UMA coluna derivada do `raw_text` que ja
esta guardado, isso e risco sem necessidade.

Este script escreve so `showdown_result`, so onde ele difere do que esta gravado, por id e em
ordem crescente (ver `grava_decisions_em_ordem`: escritor em massa de `decisions` roda junto com
o solver-consumer, e ordem comum e o que impede deadlock).

Uso:
    python -m scripts.backfill_showdown_do_party                   # dry-run, todas as salas
    python -m scripts.backfill_showdown_do_party --site partypoker
    python -m scripts.backfill_showdown_do_party --user 62 --apply
    python -m scripts.backfill_showdown_do_party --tid 422627148 --apply
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn                                    # noqa: E402
from database.repositories import _adapt, grava_decisions_em_ordem      # noqa: E402
from leaklab.parser import parse_hand_history, heroi_das_maos            # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--site', default=None, help="ex.: partypoker")
    ap.add_argument('--user', type=int, default=None)
    ap.add_argument('--tid', default=None, help="tournament_id da SALA, nao o id interno")
    args = ap.parse_args()

    conn = get_conn()
    sql = ("SELECT id, tournament_id, site, hero, raw_text FROM tournaments "
           "WHERE raw_text IS NOT NULL AND raw_text != ''")
    par = []
    if args.site:
        sql += " AND lower(site) = ?"; par.append(args.site.lower())
    if args.user:
        sql += " AND user_id = ?"; par.append(args.user)
    if args.tid:
        sql += " AND tournament_id = ?"; par.append(str(args.tid))
    sql += " ORDER BY id"
    torneios = conn.execute(_adapt(sql), tuple(par)).fetchall()
    print('torneios: %d' % len(torneios))

    total = Counter()
    por_id_global = {}
    for trow in torneios:
        t = dict(trow)
        try:
            maos = parse_hand_history(t['raw_text'])
        except Exception as e:
            total['torneio ilegivel'] += 1
            print('  t%s (%s): parse falhou: %s' % (t['id'], t['site'], e))
            continue
        if not maos:
            total['torneio sem mao'] += 1
            continue
        # O heroi do ARQUIVO, nao da primeira mao: mao em que o heroi nao age sai sem nome, e o
        # showdown e POR heroi. Mesma funcao que o import usa.
        heroi = (t['hero'] or '').strip() or heroi_das_maos(maos)
        fresco = {}
        for m in maos:
            if m.showdown_result is not None:
                fresco[str(m.hand_id)] = m.showdown_result

        linhas = conn.execute(_adapt(
            "SELECT id, hand_id, showdown_result FROM decisions "
            "WHERE tournament_id = ? ORDER BY id"), (t['id'],)).fetchall()
        mudou = 0
        for r in linhas:
            d = dict(r)
            novo = fresco.get(str(d['hand_id']))
            # NUNCA apaga: quem ja tem resultado gravado fica como esta. Este script existe para
            # preencher vazio, e trocar um valor existente seria outra decisao, com outro risco.
            if novo is not None and (d['showdown_result'] or None) is None:
                por_id_global[d['id']] = {'showdown_result': novo}
                mudou += 1
        total['linhas a preencher'] += mudou
        total['torneios tocados'] += 1 if mudou else 0
        if mudou:
            print('  t%-6s %-11s heroi=%-14s maos=%-5d showdowns=%-4d linhas=%d'
                  % (t['id'], t['site'], heroi[:14], len(maos), len(fresco), mudou))

    print()
    for k, v in sorted(total.items()):
        print('  %-22s %6d' % (k, v))
    if not args.apply:
        print('\nDRY-RUN. Repita com --apply para gravar.')
        conn.close()
        return
    n = grava_decisions_em_ordem(conn, por_id_global)
    conn.commit()
    conn.close()
    print('\nGRAVADAS %d linhas.' % n)


if __name__ == '__main__':
    main()
