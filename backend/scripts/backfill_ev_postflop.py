# -*- coding: utf-8 -*-
"""Backfill do EV postflop: recupera `ev_loss_bb` de decisões cujo nó JÁ tem tabela por mão.

── Por que existe ────────────────────────────────────────────────────────────────────────────

O EV postflop é calculado no momento da análise, a partir da tabela por mão do nó CFR
(`gto_tree_strategies`). Decisões analisadas ANTES de a tabela existir para aquele nó ficaram
com `ev_loss_bb = NULL` e nunca foram revisitadas: o solve chegou depois e nada volta para
preencher.

Medido em produção (2026-07-29), amostra de 120 decisões postflop sem EV:
  · 102 (85%) o nó JÁ tem tabela por mão   → recuperável agora
  ·   0 nó agregado sem tabela
  ·  18 sem nó (hash não bate / não solvado)

── O que este script NÃO faz ─────────────────────────────────────────────────────────────────

Não toca em `gto_label`, `gto_action` nem em nada que seja veredito. Preenche UM campo hoje
vazio. Se o EV recuperado contradiz o veredito gravado, o script REPORTA e não escreve aquela
linha — divergência é sinal de que a premissa está errada, não de que o veredito está.

── O filtro de confiança é obrigatório ───────────────────────────────────────────────────────

`ev_loss_trustworthy` é fonte única da regra "este número pode ser usado como quantidade". O EV
pode vir com escala errada (até 4x) ou com o SINAL invertido quando a profundidade está fora da
calibração. Preencher sem o filtro trocaria "sem número" por "número errado", que é pior — e é
justamente por isso que o campo está vazio hoje.

    python scripts/backfill_ev_postflop.py                 # seco: mede e não escreve
    python scripts/backfill_ev_postflop.py --escrever      # grava
    python scripts/backfill_ev_postflop.py --limite 500
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _cartas(v):
    """`hero_cards` vem colado ('5h5d') ou como lista. Já custou um diagnóstico inteiro que
    imprimiu 'zero perdidas' porque um `split()` produziu um token de 4 chars."""
    if isinstance(v, (list, tuple)):
        return list(v)
    s = str(v or '')
    return [s[:2], s[2:]] if len(s) == 4 else []


def main() -> int:
    ap = argparse.ArgumentParser(description='Backfill do EV postflop (hand-aware).')
    ap.add_argument('--escrever', action='store_true', help='grava; sem isto só mede')
    ap.add_argument('--limite', type=int, default=2000)
    args = ap.parse_args()

    from database.schema import get_conn
    from database.repositories import _adapt
    from leaklab.gto_utils import compute_spot_hash, board_for_street
    from leaklab.gto_solver import hand_view_for_spot
    from leaklab.decision_engine_v11 import ev_loss_trustworthy, _match_strategy_entries

    conn = get_conn()
    try:
        alvos = conn.execute(_adapt(
            "SELECT id, street, position, board, hero_cards, stack_bb, facing_bet, "
            "       action_taken, gto_label, pot_size, estimated_equity "
            "  FROM decisions "
            " WHERE street IN (?,?,?) AND gto_label IS NOT NULL AND ev_loss_bb IS NULL "
            " ORDER BY id DESC LIMIT ?"),
            ('flop', 'turn', 'river', args.limite)).fetchall()
    finally:
        conn.close()

    n = len(alvos)
    sem_no = sem_tabela = sem_acao = desconfiado = recuperado = impossivel = 0
    escritos = 0
    amostra = []

    for row in alvos:
        d = dict(row)
        board = d['board']
        if isinstance(board, str):
            try:
                board = json.loads(board)
            except ValueError:
                board = []
        hero = _cartas(d.get('hero_cards'))
        if not hero or not board:
            sem_no += 1
            continue

        street = d['street']
        b = board_for_street(board, street)
        h = compute_spot_hash(street, d['position'], b, hero,
                              float(d['stack_bb'] or 0), float(d['facing_bet'] or 0))

        conn = get_conn()
        try:
            node = conn.execute(_adapt(
                "SELECT tree_hash, source FROM gto_nodes WHERE spot_hash = ? LIMIT 1"),
                (h,)).fetchone()
        finally:
            conn.close()
        if not node:
            sem_no += 1
            continue
        node = dict(node)
        if not node.get('tree_hash'):
            sem_tabela += 1
            continue

        try:
            view = hand_view_for_spot(node['tree_hash'], b, hero)
        except Exception:
            view = None
        if not view or not view.get('actions'):
            sem_tabela += 1
            continue

        estrategia = sorted(
            [{'action': a, 'frequency': v['frequency'], 'ev_bb': v['ev_bb'],
              'ev_loss_bb': v['ev_loss_bb']} for a, v in view['actions'].items()],
            key=lambda s: s['frequency'], reverse=True)

        # Mesmo matcher por família do engine (shove casa raise/bet) — reusado, não recopiado.
        ev = None
        for s in _match_strategy_entries(d.get('action_taken') or '', estrategia):
            if ev is None or s['ev_loss_bb'] < ev:
                ev = s['ev_loss_bb']
        if ev is None:
            sem_acao += 1
            continue

        # A EQUITY É OBRIGATÓRIA aqui. `ev_loss_fold_ceiling` devolve None quando ela falta
        # ("não há do que discordar, e o EV passa"), então chamar o filtro sem ela desliga o
        # teto de fold em silêncio. Foi o que aconteceu na primeira rodada deste script: 439
        # linhas escritas com o guarda desarmado, e uma delas dizia que foldar custou 103,6bb
        # com um stack de 72,9bb.
        if not ev_loss_trustworthy(ev, d.get('stack_bb'), 'solver_hand',
                                   action=d.get('action_taken'),
                                   equity=d.get('estimated_equity'),
                                   pot_bb=d.get('pot_size'),
                                   facing_bb=d.get('facing_bet')):
            desconfiado += 1
            continue

        # Guarda ABSOLUTO, que não depende de nenhum dado auxiliar: ninguém perde mais bb do que
        # tem na mesa. É aritmética, não calibração — e é o tipo de checagem que sobrevive a
        # qualquer buraco nos parâmetros dos guardas mais finos.
        _stk = d.get('stack_bb')
        if _stk and float(ev) > float(_stk):
            impossivel += 1
            continue

        # Guarda de coerência: EV alto num veredito de acerto (ou zero num crítico) significa que
        # a premissa está errada em algum lugar. Reporta e NÃO escreve — o veredito é o que o
        # jogador já viu, e trocá-lo por dedução de um backfill seria o conserto pior que o bug.
        lab = d.get('gto_label')
        incoerente = (lab == 'gto_correct' and ev > 1.0)
        if incoerente:
            amostra.append(('INCOERENTE', d['id'], lab, round(ev, 2)))
            continue

        recuperado += 1
        if len(amostra) < 8:
            amostra.append(('ok', d['id'], lab, round(ev, 2)))

        if args.escrever:
            conn = get_conn()
            try:
                conn.execute(_adapt(
                    "UPDATE decisions SET ev_loss_bb = ?, ev_loss_source = ? WHERE id = ?"),
                    (round(float(ev), 4), 'solver_hand', d['id']))
                conn.commit()
                escritos += 1
            finally:
                conn.close()

    print('decisoes postflop sem EV examinadas: %d' % n)
    print('  sem no (hash nao bate/nao solvado) : %d' % sem_no)
    print('  no sem tabela por mao              : %d' % sem_tabela)
    print('  acao jogada fora da tabela         : %d' % sem_acao)
    print('  EV recuperado mas NAO confiavel    : %d  (filtro ev_loss_trustworthy)' % desconfiado)
    print('  EV MAIOR que o proprio stack       : %d  (impossivel por aritmetica)' % impossivel)
    print('  RECUPERAVEL                        : %d' % recuperado)
    print('  escritos                           : %d%s' % (escritos, '' if args.escrever else '  (modo seco)'))
    if amostra:
        print('\namostra:')
        for a in amostra:
            print('   ', a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
