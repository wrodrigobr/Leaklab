# -*- coding: utf-8 -*-
"""O preco que a TELA anuncia e o que o Stripe COBRA sao o mesmo? Pergunte ao Stripe.

    python scripts/conferir_precos_no_stripe.py

── Por que existe (28/08) ──────────────────────────────────────────────────────────────────

O dono decidiu baixar o Pro de R$99 para R$39,90 e disse, olhando o painel do Stripe: "me parece
que ja esta configurado". Consultando a API com a chave live, a conta tinha **so R$99 e R$990** --
o preco novo estava no modo de TESTE, que e outra metade da conta e nao aparece na live.

Se eu tivesse trocado o numero na tela confiando no painel, o site anunciaria R$39,90 e o Stripe
cobraria R$99. E o pior defeito possivel deste dia inteiro: pior que uma captura faltando, pior
que uma seta de tendencia sem amostra.

É a regra 8 do CLAUDE.md aplicada a um sistema externo: **quando a decisao depende do
comportamento de outro sistema, pergunte ao sistema.** Painel nao e evidencia; comentario nao e
evidencia; constante no codigo nao e evidencia.

── As TRES fontes que precisam concordar ───────────────────────────────────────────────────

1. O Stripe (`price.unit_amount` do price_id configurado) -- o que o cartao e debitado.
2. `PLAN_AMOUNTS` / `PLAN_AMOUNTS_ANNUAL` -- o que o backend registra e serve a tela.
3. A landing, que le do backend.

A (3) le da (2), entao o guarda so precisa casar (1) com (2). Se um dia a landing voltar a cravar
o numero, `test_preco_da_landing_vem_da_api.py` acusa.

Saida 0 = concordam. Saida 1 = divergem, ou o price_id nao esta configurado. Roda no portao de
deploy: dois segundos, e impede de anunciar um preco e cobrar outro.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def main() -> int:
    if not os.environ.get('STRIPE_SECRET_KEY'):
        print('PULADO: STRIPE_SECRET_KEY ausente (ambiente sem cobranca).')
        return 0
    try:
        import stripe
    except Exception as e:                                     # noqa: BLE001
        print('PULADO: SDK do Stripe indisponivel (%s).' % e)
        return 0

    from leaklab.stripe_gateway import PLAN_AMOUNTS, PLAN_AMOUNTS_ANNUAL, price_id

    stripe.api_key = os.environ['STRIPE_SECRET_KEY']
    modo = 'LIVE' if stripe.api_key.startswith('sk_live') else 'TESTE'
    try:
        conta = stripe.Account.retrieve()
    except Exception as e:                                     # noqa: BLE001
        print('FALHOU: nao consegui falar com o Stripe: %s' % e)
        return 1
    print('conta %s | chave %s' % (conta.id, modo))

    esperado = {
        'monthly': PLAN_AMOUNTS.get('pro'),
        'annual':  PLAN_AMOUNTS_ANNUAL.get('pro'),
    }
    problemas = []
    for ciclo, valor_codigo in esperado.items():
        pid = price_id('pro', ciclo)
        if not pid:
            # NAO e so aviso: sem price_id o checkout cai no PaymentIntent avulso, que cobra o
            # valor da CONSTANTE. Ou seja, um price_id faltando faz o codigo virar a autoridade
            # sobre o preco sem ninguem decidir isso.
            problemas.append('%s: price_id nao configurado (o checkout cai no avulso e cobra a '
                             'constante R$ %.2f sem passar pelo Stripe)' % (ciclo, valor_codigo))
            continue
        try:
            p = stripe.Price.retrieve(pid)
        except Exception as e:                                 # noqa: BLE001
            problemas.append('%s: price_id %s nao existe nesta conta (%s)' % (ciclo, pid, e))
            continue
        valor_stripe = (p.unit_amount or 0) / 100.0
        # `p.recurring` e um StripeObject, nao um dict: `.get` cai no `__getattr__` dele e
        # levanta AttributeError. `getattr` com default e o acesso que funciona nos dois.
        intervalo = getattr(p.recurring, 'interval', None) if p.recurring else None
        marca = 'ok' if abs(valor_stripe - float(valor_codigo)) < 0.005 else 'DIVERGE'
        print('  %-8s %s  Stripe R$ %8.2f  codigo R$ %8.2f  %s  %s'
              % (ciclo, pid, valor_stripe, valor_codigo, intervalo or '?', marca))
        if marca == 'DIVERGE':
            problemas.append('%s: o Stripe cobra R$ %.2f e o codigo/tela anunciam R$ %.2f'
                             % (ciclo, valor_stripe, valor_codigo))
        if not p.active:
            problemas.append('%s: o price %s esta INATIVO no Stripe' % (ciclo, pid))
        esperado_intervalo = 'month' if ciclo == 'monthly' else 'year'
        if intervalo != esperado_intervalo:
            problemas.append('%s: o price recorre por %r, esperado %r'
                             % (ciclo, intervalo, esperado_intervalo))

    if problemas:
        print()
        print('PRECO DIVERGENTE -- o site anunciaria um valor e o Stripe cobraria outro:')
        for p in problemas:
            print('  - %s' % p)
        return 1
    print()
    print('PRECOS OK -- o que a tela anuncia e o que o Stripe cobra.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
