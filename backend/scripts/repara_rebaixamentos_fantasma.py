# -*- coding: utf-8 -*-
"""Repara os rebaixamentos causados por checkout abandonado (05/09).

── O que aconteceu ───────────────────────────────────────────────────────────────────────

`apply_stripe_subscription` tratava `incomplete_expired` — a assinatura criada e nunca paga,
que o Stripe expira ~24h depois — como cancelamento. Resultado medido em produção: 10
rebaixamentos, 100% deles por assinatura fantasma, nenhuma cancelação real. O conserto do
CÓDIGO está em `apply_stripe_subscription` + no handler do webhook; este script conserta o
DADO que ficou para trás.

── O que ele repara, e o que deliberadamente NÃO repara ─────────────────────────────────

REPARA:
  1. O vínculo da assinatura ATIVA de quem paga. `mp_subscription_id` foi apagado pelo
     downgrade indevido, e o painel do admin não o restaura — a assinatura real ficou órfã
     no nosso banco: renovação chega, `get_user_by_subscription` não acha ninguém.
  2. A procedência de quem está Pro com `plan_source` nulo. Essa combinação é o estado
     DESARMADO: sem procedência, a guarda nova não consegue distinguir concessão do admin
     de pagante legado, e o usuário segue rebaixável.
  3. As marcas de churn falsas (`subscription_status='canceled'`, `canceled_at`,
     `cancel_reason='incomplete_expired'`) de quem NÃO cancelou. Elas sujam o churn e o
     dunning do painel financeiro.

NÃO REPARA:
  - Não devolve Pro a ninguém que esteja Free hoje. Cinco dos atingidos podem ter estado
    Free ANTES do evento fantasma, e não existe registro para distinguir — a trilha
    `plan_audit` nasceu justamente desta investigação e só vale daqui para frente.
    Conceder Pro por suposição seria inventar assinante; quem precisar volta pelo painel,
    que agora grava estado coerente. Ver regra 7: o conserto não pode causar dano que o
    bug não causava.

Uso:
    python scripts/repara_rebaixamentos_fantasma.py --dry-run
    python scripts/repara_rebaixamentos_fantasma.py --aplicar
"""
import argparse
import os
import sys

sys.path.insert(0, ".")

from database.schema import get_conn, init_db
from database.repositories import _adapt, _now_str, auditar_plano

#: A assinatura ACTIVE conferida no Stripe em 05/09 (status, preço e período lidos da API).
VINCULOS_A_RESTAURAR = {
    58: {'sub': 'sub_1UB50GDLmkrPxhrvyT2Wzj7x', 'ate': '2026-10-02 03:38:24'},
}

_MOTIVO_FANTASMA = 'incomplete_expired'


def _linhas(conn):
    return [dict(r) for r in conn.execute(_adapt(
        "SELECT id, username, plan, plan_source, subscription_status, mp_subscription_id, "
        "plan_expires_at, canceled_at, cancel_reason FROM users "
        "WHERE cancel_reason = ? OR (plan = 'pro' AND plan_source IS NULL)"),
        (_MOTIVO_FANTASMA,)).fetchall()]


def _planeja(conn):
    """Devolve [(user_id, rotulo, sets, params)] — o que faria, sem fazer."""
    plano = []
    for u in _linhas(conn):
        uid = u['id']
        # 1. religa a assinatura de quem paga
        if uid in VINCULOS_A_RESTAURAR:
            v = VINCULOS_A_RESTAURAR[uid]
            plano.append((uid, u['username'], 'religa assinatura ATIVA %s (ate %s)' % (v['sub'], v['ate']),
                          "plan='pro', plan_source='stripe_sub', subscription_status='active', "
                          "mp_subscription_id=?, plan_expires_at=?, canceled_at=NULL, cancel_reason=NULL",
                          [v['sub'], v['ate']]))
            continue
        sets, params, rotulos = [], [], []
        # 2. procedencia de quem esta Pro sem ela (estado desarmado)
        if u['plan'] == 'pro' and not u['plan_source']:
            sets.append("plan_source='admin'")
            rotulos.append('procedencia -> admin (sai do estado desarmado)')
        # 3. limpa marca de churn falsa
        if u['cancel_reason'] == _MOTIVO_FANTASMA:
            sets.append("subscription_status=NULL, canceled_at=NULL, cancel_reason=NULL")
            rotulos.append('apaga churn falso')
        if sets:
            plano.append((uid, u['username'], ' + '.join(rotulos), ', '.join(sets), params))
    return plano


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--aplicar', action='store_true')
    args = ap.parse_args()
    if not (args.dry_run or args.aplicar):
        ap.error('escolha --dry-run ou --aplicar')

    init_db()
    conn = get_conn()
    try:
        print('== ANTES ==')
        for u in _linhas(conn):
            print('  %-4s %-22s plan=%-5s src=%-11s status=%-9s sub=%-28s motivo=%s' % (
                u['id'], u['username'], u['plan'], str(u['plan_source']),
                str(u['subscription_status']), str(u['mp_subscription_id']), str(u['cancel_reason'])))

        plano = _planeja(conn)
        print()
        print('== PLANO (%d usuarios) ==' % len(plano))
        for uid, nome, rotulo, _sets, _params in plano:
            print('  %-4s %-22s %s' % (uid, nome, rotulo))
        if not plano:
            print('  nada a fazer')
            return

        if args.dry_run:
            print()
            print('DRY-RUN: nada foi alterado')
            return

        for uid, nome, rotulo, sets, params in plano:
            with auditar_plano(conn, uid, 'reparo_fantasma', rotulo):
                conn.execute(_adapt("UPDATE users SET %s WHERE id = ?" % sets), params + [uid])
        conn.commit()

        print()
        print('== DEPOIS ==')
        for u in _linhas(conn):
            print('  %-4s %-22s plan=%-5s src=%-11s status=%-9s sub=%-28s motivo=%s' % (
                u['id'], u['username'], u['plan'], str(u['plan_source']),
                str(u['subscription_status']), str(u['mp_subscription_id']), str(u['cancel_reason'])))
        print()
        print('aplicado em %s' % _now_str())
    finally:
        conn.close()


if __name__ == '__main__':
    main()
