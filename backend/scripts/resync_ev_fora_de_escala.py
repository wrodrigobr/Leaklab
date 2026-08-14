# -*- coding: utf-8 -*-
"""Resync ESCOPADO das decisoes cujo ev_loss e residuo de no de outra escala (14/08).

O par deste script e `resolve_nos_fora_de_escala.py`: aquele cura o NO (re-solve com o
payload certo), este cura a LINHA. Sao dois passos porque o re-attach automatico pos-fila
(`resync_tournament_postflop`) e FILL-ONLY por design -- nunca reescreve decisao que ja
tinha gto -- entao o re-solve sozinho deixa o EV envenenado gravado. Medido em 14/08: os
10 postflop remanescentes tinham no NOVO e sao (exploitability 0,34-1,64%, pote da fila =
pote vivo) e ev_loss_bb de 631 a 41.605bb na linha.

Reavalia cada alvo com `evaluate_decision` (autoritativo) e regrava os 8 campos JUNTOS
(label, best, gto_label, gto_action, played, top, ev, ev_src) -- regra dos campos-viajantes
do `resync_postflop_gto`, de onde vem `_avaliacao_fresca` e o pareamento posicional. No caso
medido a unica mudanca foi ev/src -> NULL: a mao real do heroi esta fora do range do solve
novo (hand_view None), e ausencia honesta e melhor que numero de outra escala.

Uso:
    python -m scripts.resync_ev_fora_de_escala            # dry-run
    python -m scripts.resync_ev_fora_de_escala --apply
"""
import sys, os, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from scripts.resync_postflop_gto import _avaliacao_fresca, _pares_por_ordem

APPLY = '--apply' in sys.argv

CAMPOS = ('label', 'best_action', 'gto_label', 'gto_action',
          'gto_played_freq', 'gto_top_freq', 'ev_loss_bb', 'ev_loss_source')


def main():
    init_db()
    conn = get_conn()
    alvos = [dict(r) for r in conn.execute("""
        SELECT d.id, d.tournament_id, d.hand_id, d.street, d.action_taken
          FROM decisions d
         WHERE lower(d.street) != 'preflop'
           AND d.ev_loss_bb IS NOT NULL
           AND ABS(d.ev_loss_bb) > COALESCE(d.pot_size,0) + 2*COALESCE(d.stack_bb,0)
         ORDER BY d.id
    """).fetchall()]
    ids_alvo = {a['id'] for a in alvos}
    print(f'alvos postflop fora de escala: {len(alvos)}')

    por_t = defaultdict(list)
    for a in alvos:
        por_t[a['tournament_id']].append(a)

    atualizadas = pareamento_reprovado = 0
    for tid in sorted(por_t):
        chaves_alvo = {(str(a['hand_id']), (a['street'] or '').lower(),
                        (a['action_taken'] or '').lower()) for a in por_t[tid]}
        raw = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        raw_text = dict(raw).get('raw_text') if raw else None
        if not raw_text:
            print(json.dumps({'t': tid, 'status': 'SEM_RAW'}))
            continue
        hands = parse_hand_history(raw_text)
        fresh = defaultdict(list)
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                k = (str(di.get('hand_id')), (di.get('street') or '').lower(),
                     (di.get('player_action') or '').lower())
                if k not in chaves_alvo:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                fresh[k].append(_avaliacao_fresca(r))

        stored = defaultdict(list)
        for r in conn.execute(
                "SELECT id, hand_id, street, action_taken, label, best_action, gto_label, "
                "gto_action, gto_played_freq, gto_top_freq, ev_loss_bb, ev_loss_source "
                "FROM decisions WHERE tournament_id=? AND lower(street)!='preflop' "
                "ORDER BY id", (tid,)).fetchall():
            d = dict(r)
            k = (str(d['hand_id']), (d['street'] or '').lower(),
                 (d['action_taken'] or '').lower())
            if k in chaves_alvo:
                stored[k].append(d)

        for k in sorted(chaves_alvo):
            pares = _pares_por_ordem(stored.get(k) or [], fresh.get(k) or [])
            if not pares:
                # Contagem diferente entre banco e recalculo: correspondencia nao provada,
                # gravar no palpite escreveria a avaliacao na decisao errada. Perder e honesto.
                pareamento_reprovado += len(stored.get(k) or [])
                print(json.dumps({'t': tid, 'chave': list(k), 'status': 'CONTAGEM_DIVERGE',
                                  'stored': len(stored.get(k) or []),
                                  'fresh': len(fresh.get(k) or [])}))
                continue
            for s, f in pares:
                if s['id'] not in ids_alvo:
                    continue
                velho = {c: s[c] for c in CAMPOS}
                novo = {'label': f['label'], 'best_action': f['best'],
                        'gto_label': f['gto_label'], 'gto_action': f['gto_action'],
                        'gto_played_freq': f.get('played'), 'gto_top_freq': f.get('top'),
                        'ev_loss_bb': f.get('ev'), 'ev_loss_source': f.get('ev_src')}
                print(json.dumps({'id': s['id'], 't': tid, 'velho': velho, 'novo': novo},
                                 ensure_ascii=False, default=str))
                if APPLY:
                    conn.execute(
                        "UPDATE decisions SET label=?, best_action=?, gto_label=?, "
                        "gto_action=?, gto_played_freq=?, gto_top_freq=?, ev_loss_bb=?, "
                        "ev_loss_source=? WHERE id=?",
                        tuple(novo[c] for c in CAMPOS) + (s['id'],))
                atualizadas += 1
    if APPLY:
        conn.commit()
    conn.close()
    print(f"{'APLICADO' if APPLY else 'DRY-RUN (use --apply)'}: {atualizadas} decisoes; "
          f"pareamento reprovado: {pareamento_reprovado}")


if __name__ == '__main__':
    main()
