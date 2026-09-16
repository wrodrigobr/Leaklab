# -*- coding: utf-8 -*-
"""Dry-run: quem a regra `carta_nao_acusa_fold_vs_allin` absolve, e quanto isso move.

Padrao da casa: medir o antes e o depois ANTES de gravar. Este script nao escreve nada sem
`--aplicar`, e o que ele aplica e apenas o que a regra pura decide, linha a linha.

    python -m scripts.dry_run_fold_vs_allin                 # so mede
    python -m scripts.dry_run_fold_vs_allin --por-usuario    # + o efeito por jogador
    python -m scripts.dry_run_fold_vs_allin --aplicar        # grava (pede confirmacao)

── Por que existe ────────────────────────────────────────────────────────────────────────────

O caso do dono (16/09): K7s no SB, 3-bet ALL-IN, fold acusado em 1,21bb por uma carta de balde
de 30bb que assume 3-bet de 15bb. O motor, na mesma decisao, mediu equity 43,4% contra 44,4%
exigidos: o fold estava certo. A regra derruba a acusacao quando o preco a contradiz.

Mudar rotulo gravado muda ELO, nivel, ranking, leaks e plano de estudos RETROATIVAMENTE, entao
o numero vem primeiro e a decisao de gravar e do dono.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from database.repositories import _adapt, get_conn          # noqa: E402
from leaklab.card_verdict import (carta_nao_acusa_fold_vs_allin,   # noqa: E402
                                  gto_label_de_quality)
from leaklab.decision_engine_v11 import facing_allin_row        # noqa: E402

# `facing_allin_row` e a FONTE UNICA de "a aposta enfrentada e all-in" (facing_bet >=
# effective_stack_bb * 0.98). A primeira versao deste script comparava com `stack_bb`, o stack
# do HEROI, e por isso NAO achava o caso que originou a frente: o dono tinha 94,7bb e o all-in
# do vilao era de 33,9bb -- o stack que importa e o EFETIVO. Reimplementar a regra no medidor e
# o vies mais caro que eu tenho registrado.


def _candidatas(conn):
    """Preflop, fold, a carta mandou pagar, e a aposta enfrentada era all-in."""
    return [dict(r) for r in conn.execute(_adapt("""
        SELECT d.id, d.tournament_id, t.user_id, d.hand_id, d.hero_cards, d.position,
               d.action_taken, d.gto_action, d.gto_label, d.label, d.ev_loss_bb,
               d.gto_played_freq, d.estimated_equity, d.pot_size, d.facing_bet, d.stack_bb,
               d.effective_stack_bb
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE d.street = 'preflop' AND d.action_taken = 'fold' AND d.gto_action = 'call'
          AND d.facing_bet IS NOT NULL AND d.effective_stack_bb IS NOT NULL
        ORDER BY d.ev_loss_bb DESC NULLS LAST
    """)).fetchall()
            if facing_allin_row(dict(r))]


def _exigida(d):
    """Equity que o pote exige. O pote GRAVADO ja inclui o que ha na mesa; o preco e a aposta."""
    pot, facing = d.get('pot_size'), d.get('facing_bet')
    if pot is None or facing is None:
        return None
    total = float(pot) + float(facing)
    return (float(facing) / total) if total > 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aplicar', action='store_true', help='GRAVA (pede confirmacao)')
    ap.add_argument('--por-usuario', action='store_true')
    args = ap.parse_args()

    conn = get_conn()
    try:
        cands = _candidatas(conn)
        print('candidatas (preflop, fold vs all-in, carta mandou pagar): %d' % len(cands))

        absolvidas, mantidas, sem_numero, nada_a_mudar = [], [], [], []
        for d in cands:
            ex = _exigida(d)
            q0 = d['gto_label'] or 'unknown'
            q1, ev1 = carta_nao_acusa_fold_vs_allin(
                q0, d['ev_loss_bb'], facing_allin=True, acao_jogada='fold',
                equity=d['estimated_equity'], equity_exigida=ex)
            if d['estimated_equity'] is None or ex is None:
                sem_numero.append(d)
            elif d['ev_loss_bb'] is None and q0 in ('correct', 'unknown'):
                # nada a absolver: a decisao ja nao acusava nada. A primeira versao contava
                # estas como "mantidas" e o CONTROLE acusou, porque o preco nao fechava nelas.
                nada_a_mudar.append(d)
            elif (q1, ev1) != (q0, d['ev_loss_bb']):
                d['_exigida'], d['_q1'] = ex, q1
                absolvidas.append(d)
            else:
                mantidas.append(d)

        bb = sum(float(x['ev_loss_bb'] or 0) for x in absolvidas)
        print()
        print('ABSOLVIDAS (o preco contradiz a carta): %d  |  %.1fbb saem dos leaks' % (len(absolvidas), bb))
        print('MANTIDAS   (o preco confirma a carta)  : %d' % len(mantidas))
        print('sem equity ou sem pote gravados        : %d  (a regra nao toca)' % len(sem_numero))
        print('ja nao acusavam nada                   : %d' % len(nada_a_mudar))
        print()

        if absolvidas:
            print('as 12 maiores absolvidas:')
            print('  %-7s %-6s %-6s %-9s %-8s %-8s %s' % (
                'MAO', 'POS', 'CUSTO', 'equity', 'exigida', 'freq', 'rotulo: antes -> depois'))
            for d in sorted(absolvidas, key=lambda x: -float(x['ev_loss_bb'] or 0))[:12]:
                print('  %-7s %-6s %-6s %-9s %-8s %-8s %s -> %s' % (
                    d['hero_cards'], d['position'], '-%.2f' % float(d['ev_loss_bb'] or 0),
                    '%.1f%%' % (float(d['estimated_equity']) * 100),
                    '%.1f%%' % (float(d['_exigida']) * 100),
                    ('%.0f%%' % (float(d['gto_played_freq']) * 100)) if d['gto_played_freq'] is not None else '-',
                    d['gto_label'], d['_q1']))
            print()
            # CONTROLE (regra 1): a regra nao pode absolver quem o preco CONFIRMA.
            erradas = [d for d in absolvidas
                       if float(d['estimated_equity']) >= float(d['_exigida'])]
            print('CONTROLE: absolvidas em que a equity ALCANCA a exigida: %d (tem de ser 0)' % len(erradas))
            piores = [d for d in mantidas
                      if d['estimated_equity'] is not None and _exigida(d) is not None
                      and float(d['estimated_equity']) < float(_exigida(d))
                      and d['ev_loss_bb'] is not None]
            print('CONTROLE: mantidas em que o preco NAO fecha: %d (tem de ser 0)' % len(piores))

        if args.por_usuario and absolvidas:
            por = {}
            for d in absolvidas:
                u = por.setdefault(d['user_id'], {'n': 0, 'bb': 0.0})
                u['n'] += 1
                u['bb'] += float(d['ev_loss_bb'] or 0)
            print()
            print('efeito por jogador (quem perde acusacao):')
            for uid, v in sorted(por.items(), key=lambda kv: -kv[1]['bb']):
                print('   user %-7s %3d decisoes  %6.1fbb' % (uid, v['n'], v['bb']))

        if not args.aplicar:
            print()
            print('DRY-RUN: nada foi gravado. Para aplicar: --aplicar')
            return

        print()
        print('Vai GRAVAR %d decisoes (rotulo e ev_loss). Isso muda ELO, nivel, ranking e leaks'
              % len(absolvidas))
        print('retroativamente. Escreva APLICAR para confirmar:')
        if (sys.stdin.readline() or '').strip() != 'APLICAR':
            print('cancelado')
            return
        for d in absolvidas:
            # TRADUZ antes de gravar: `_q1` e vocabulario da CARTA ('correct') e a coluna
            # `gto_label` so entende o do banco ('gto_correct'). A primeira versao gravou cru
            # em 83 decisoes de producao, e o ELO, que nao pontua valor fora do vocabulario,
            # simplesmente descartou as 83 -- um jogador caiu 0,2 por um conserto que so
            # removia acusacoes.
            conn.execute(_adapt("UPDATE decisions SET gto_label = ?, ev_loss_bb = NULL, "
                                "ev_loss_source = NULL WHERE id = ?"),
                         (gto_label_de_quality(d['_q1']), d['id']))
        conn.commit()
        print('gravadas: %d' % len(absolvidas))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
