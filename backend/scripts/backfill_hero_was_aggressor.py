# -*- coding: utf-8 -*-
"""Backfill de `decisions.hero_was_aggressor` no POSTFLOP — a iniciativa que nunca foi gravada.

Ate 12/08 o builder so computava o campo no preflop; as 2.903 decisoes postflop gravavam 0 e
quem c-betava ficava identico a quem pagava o c-bet (invariante COL-AGRESSOR). O builder foi
consertado (`hand_state_builder`, semantica de INICIATIVA — ver `test_iniciativa_postflop.py`);
este script aplica o mesmo calculo ao acervo, reprocessando SO esta coluna.

Escreve SO `hero_was_aggressor`, SO em street != 'preflop'. Nao toca label/gto/score/ev — nao ha
consumidor postflop do campo hoje, entao nenhum veredito muda (conferido com dry-run do relabel
depois). O preflop fica intocado: la a semantica e outra ("ja agrediu", roteamento vs_3bet).

O pareamento decisao-do-parse -> linha-do-banco usa (hand_id, street, action) + ORDINAL, o mesmo
do religamento de anotacoes: essa chave NAO e unica (o hero paga e enfrenta raise na mesma
street), e parear so pela chave colaria o valor na linha errada.

Uso:
    python scripts/backfill_hero_was_aggressor.py            # dry-run (conta e mostra amostra)
    python scripts/backfill_hero_was_aggressor.py --apply
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand

APPLY = '--apply' in sys.argv


def main():
    conn = get_conn()
    tids = [r['id'] for r in conn.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()]

    candidatas = viram_1 = ficam_0 = sem_par = 0
    amostra = []
    for tid in tids:
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id = ?", (tid,)).fetchone()
        if not raw or not raw['raw_text']:
            continue
        try:
            hands = parse_hand_history(raw['raw_text'])
        except Exception:
            continue

        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            # ordinal por chave, nos DOIS lados, na mesma ordem cronologica
            ord_parse: dict = defaultdict(int)
            valores = {}
            for di in dis:
                if di.get('street') == 'preflop':
                    continue
                act = (di['spot'].get('actionTaken') or di.get('player_action') or '').lower()
                chave = (str(di.get('hand_id')), di.get('street'), act)
                valores[chave + (ord_parse[chave],)] = 1 if di['spot'].get('heroWasAggressor') else 0
                ord_parse[chave] += 1
            if not valores:
                continue

            rows = conn.execute(
                "SELECT id, street, action_taken, hero_was_aggressor FROM decisions "
                "WHERE tournament_id = ? AND hand_id = ? AND street <> 'preflop' "
                "ORDER BY id", (tid, str(hand.hand_id))).fetchall()
            ord_db: dict = defaultdict(int)
            for row in rows:
                chave = (str(hand.hand_id), row['street'], (row['action_taken'] or '').lower())
                k = chave + (ord_db[chave],)
                ord_db[chave] += 1
                if k not in valores:
                    sem_par += 1
                    continue
                candidatas += 1
                novo = valores[k]
                if novo == (row['hero_was_aggressor'] or 0):
                    ficam_0 += (novo == 0)
                    continue
                viram_1 += 1
                if len(amostra) < 6:
                    amostra.append((row['id'], hand.hand_id, row['street'],
                                    row['action_taken'], novo))
                if APPLY:
                    conn.execute("UPDATE decisions SET hero_was_aggressor = ? WHERE id = ?",
                                 (novo, row['id']))
    if APPLY:
        conn.commit()
    conn.close()

    print(f"pareadas: {candidatas} | mudam 0->1: {viram_1} | seguem 0: {ficam_0} "
          f"| sem par: {sem_par}")
    for a in amostra:
        print("  id=%s hand=%s %s/%s -> %s" % a)
    if not APPLY:
        print("== DRY-RUN — nada foi gravado ==")


if __name__ == '__main__':
    main()
