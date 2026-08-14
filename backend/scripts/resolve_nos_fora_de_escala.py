# -*- coding: utf-8 -*-
"""Re-solve ESCOPADO dos nós de OUTRA ESCALA — a raiz da família 1 do coach (14/08).

Alvo: decisões postflop cujo |ev_loss_bb| gravado > pote + 2·stacks (o teto físico do
ev_loss_trustworthy). EV impossível = o nó que serviu o spot foi solvado num pote que não é o
dele (o pote não entra no spot_hash), e as FREQUÊNCIAS vieram da decisão errada junto com o
número. O cap de severidade (mesma data) trata o sintoma; isto cura: re-enfileira o spot com o
payload CORRETO — `enqueue_solver_spot` reseta nó `done` ao receber payload novo, e o solve
fresco substitui o nó sob o mesmo hash.

Hash e payload saem da FONTE ÚNICA (`montar_payload_postflop`): mesmo hash que o lookup, pote
em bb do pipeline, ranges pelo resolve, variante pela régua efetiva. Peneira de pote implausível
aplicada (dinheiro morto HU passa; dado quebrado não).

O re-solve NAO termina o servico sozinho (14/08): o re-attach automatico pos-fila e
FILL-ONLY e nunca reescreve decisao que ja tinha gto, entao o ev_loss envenenado continua
na LINHA depois que o no sara. Depois da fila drenar, rode o par deste script:
`python -m scripts.resync_ev_fora_de_escala --apply` (dry-run antes, varredura depois).

Uso:
    python -m scripts.resolve_nos_fora_de_escala            # dry-run
    python -m scripts.resolve_nos_fora_de_escala --apply
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from database.repositories import enqueue_solver_spot
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import normalize_position
from leaklab.gto_solver import montar_payload_postflop, pote_implausivel, _priority

APPLY = '--apply' in sys.argv


def main():
    conn = get_conn()
    alvos = [dict(r) for r in conn.execute("""
        SELECT d.id, d.tournament_id, d.hand_id, d.street, d.action_taken, d.label
          FROM decisions d
         WHERE lower(d.street) != 'preflop'
           AND d.ev_loss_bb IS NOT NULL AND d.stack_bb > 0
           AND ABS(d.ev_loss_bb) > COALESCE(d.pot_size, 0) + 2 * d.stack_bb
    """).fetchall()]
    print(f'decisões com EV fora de escala: {len(alvos)}')
    if not alvos:
        conn.close()
        return

    por_torneio = {}
    for a in alvos:
        por_torneio.setdefault(a['tournament_id'], []).append(a)

    vistos = set()
    enfileirados = recusados = sem_spot = insanos = 0
    for tid, dec_list in por_torneio.items():
        raw = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        raw_text = dict(raw).get('raw_text') if raw else None
        if not raw_text:
            sem_spot += len(dec_list)
            continue
        chaves = {(str(d['hand_id']), (d['street'] or '').lower(),
                   (d['action_taken'] or '').lower()) for d in dec_list}
        try:
            hands = parse_hand_history(raw_text)
        except Exception:
            sem_spot += len(dec_list)
            continue
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                k = (str(di.get('hand_id')), (di.get('street') or '').lower(),
                     (di.get('player_action') or '').lower())
                if k not in chaves:
                    continue
                chaves.discard(k)
                spot = di.get('spot') or {}
                pos = normalize_position(spot.get('position', ''))
                stack = float(spot.get('effectiveStackBb') or 20.0)
                pot_bb = float(spot.get('potBb') or 0)
                if pote_implausivel(pot_bb, stack, spot.get('nActiveOpponents')):
                    insanos += 1
                    continue
                montado = montar_payload_postflop(
                    street=di.get('street'), position=pos,
                    vs_position=normalize_position(spot.get('villainPosition', '')),
                    board=spot.get('board') or [], hero_cards=di.get('hero_cards') or [],
                    stack_bb=stack, facing_bb=float(spot.get('facingToBb') or 0),
                    pot_bb=pot_bb, pot_type=spot.get('potType', ''),
                    opener=spot.get('preflopOpener', ''),
                    threebettor=spot.get('preflop3bettor', ''))
                if not montado:
                    recusados += 1
                    continue
                h, payload = montado
                if h in vistos:
                    continue
                vistos.add(h)
                if APPLY:
                    # DELETE antes do enqueue: a blindagem do upsert ("não piora a
                    # exploitability") bloqueava o solve novo porque o nó do pote errado
                    # converge para 0.01 fraudulentamente perfeito — 40 de 40 re-solves
                    # bloqueados em silêncio na 1ª rodada (14/08). Nó provadamente de outra
                    # escala não merece blindagem: sai, e o solve fresco entra limpo.
                    conn.execute('DELETE FROM gto_nodes WHERE spot_hash = ?', (h,))
                    conn.commit()
                    enqueue_solver_spot(h, payload, priority=_priority(di.get('street')))
                enfileirados += 1
        sem_spot += len(chaves)
    conn.close()
    print(f"{'APLICADO' if APPLY else 'DRY-RUN (use --apply)'}: "
          f"spots re-enfileirados={enfileirados}, recusados pelo gate={recusados}, "
          f"pote insano={insanos}, decisão não reencontrada no parse={sem_spot}")


if __name__ == '__main__':
    main()
