# -*- coding: utf-8 -*-
"""O webhook do Stripe funciona quando o evento chega ASSINADO — que é o caminho da produção.

── O que originou (28/08) ──────────────────────────────────────────────────────────────────

Percorrendo a jornada de pagamento inteira contra o Stripe em modo de teste: o cartão foi
aprovado, a assinatura ficou `active`, **R$ 39,90 foram cobrados**, os 13 tipos de webhook
chegaram e todos responderam **200** — e o usuário **continuou `free`**. Pagou e não recebeu.

Três defeitos empilhados, todos silenciosos:

**1. `validate_webhook` devolve um `StripeObject`, e ele NÃO responde a `.get`.** O
`__getattr__` dele procura a chave `'get'` nos dados e levanta `AttributeError`. O handler inteiro
é escrito com `obj.get(...)`. Cada evento estourava, o `except` genérico engolia, e devolvia 200 —
o Stripe considera entregue e nunca reenvia. E `dict(obj)` também não serve: tenta iterar como
sequência e levanta `KeyError: 0`. Tropecei nas duas formas, em três lugares.

**2. Campos que mudaram de lugar** na API `2026-04-22.dahlia`: `invoice.subscription` foi para
`invoice.parent.subscription_details.subscription`, e `subscription.current_period_end` foi para
`items[0].current_period_end`. Sem o segundo, o `customer.subscription.updated` — que chega DEPOIS
do `invoice.paid` — apagava a validade que o primeiro tinha acabado de gravar.

**3. Grava com uma chave, procura com outra.** `invoice.paid` grava `gateway_id` = id da FATURA;
`charge.refunded` traz o PaymentIntent. Nenhum payload da API atual liga os dois. O estorno era
concluído e o usuário **continuava Pro**: dinheiro devolvido, produto mantido.

── Por que a suíte não pegava ──────────────────────────────────────────────────────────────

**O defeito só existe com `STRIPE_WEBHOOK_SECRET` configurado.** Sem segredo, o handler faz
`json.loads(payload)` e recebe um dicionário de verdade — que é o caminho que todos os testes
existentes exercitavam. A suíte inteira passava por cima, verde, testando a metade que funciona.

É o caso mais puro de "teste que não falha quando deveria" que este projeto já registrou. Por isso
este arquivo força o caminho ASSINADO, com um objeto que se comporta como o do SDK.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class FalsoStripeObject:
    """Imita o `StripeObject` no que importa: **não** tem `.get` e **não** vira `dict()`.

    Não é um dublê genérico: é a reprodução exata das duas formas de falha medidas. Um dublê que
    fosse só `dict` deixaria o teste verde e não provaria nada.
    """

    def __init__(self, dados):
        self._data = dados

    def __getattr__(self, k):
        try:
            return self._data[k]
        except KeyError as e:
            raise AttributeError(*e.args) from e     # é assim que o SDK falha em `.get`

    def __iter__(self):
        return iter(range(len(self._data)))          # dict(obj) -> KeyError: 0

    def __getitem__(self, k):
        return self._data[k]

    def __len__(self):
        return len(self._data)

    def __str__(self):
        return json.dumps(self._data)                # o SDK serializa em JSON válido


def _evento_invoice_paid(uid=4242, sub='sub_T1', inv='in_T1', fim=1790000000):
    """Um `invoice.paid` na FORMA ATUAL da API: sem `subscription` no topo, com `parent`."""
    return FalsoStripeObject({
        'type': 'invoice.paid',
        'data': {'object': {
            'id': inv,
            'amount_paid': 3990,
            'lines': {'data': [{'period': {'end': fim, 'start': fim - 2592000}}]},
            'parent': {'subscription_details': {
                'subscription': sub,
                'metadata': {'user_id': str(uid), 'plan_name': 'pro',
                             'billing_cycle': 'monthly'},
            }},
        }},
    })


def test_o_dublê_REPRODUZ_as_duas_falhas_do_SDK():
    """CONTRAPROVA do dublê. Se ele virar um dict comum, todo o resto deste arquivo passa a
    testar o caminho que já funcionava — que é exatamente como o defeito sobreviveu."""
    o = FalsoStripeObject({'a': 1})
    try:
        o.get('a')
        raise AssertionError('o dublê respondeu a `.get`: ele não imita o StripeObject')
    except AttributeError:
        pass
    try:
        dict(o)
        raise AssertionError('dict(dublê) funcionou: ele não imita o StripeObject')
    except (KeyError, TypeError, ValueError):
        pass
    assert json.loads(str(o)) == {'a': 1}, 'str() do dublê precisa ser JSON válido, como no SDK'
    print('OK  test_o_dublê_REPRODUZ_as_duas_falhas_do_SDK')


def test_como_dict_converte_o_objeto_do_sdk():
    from api.app import _como_dict
    o = FalsoStripeObject({'x': 1, 'y': {'z': 2}})
    assert _como_dict(o) == {'x': 1, 'y': {'z': 2}}
    assert _como_dict({'a': 1}) == {'a': 1}
    assert _como_dict(None) == {}
    print('OK  test_como_dict_converte_o_objeto_do_sdk')


def test_a_assinatura_da_invoice_e_lida_na_forma_NOVA_e_na_antiga():
    """O campo mudou de lugar, e eventos antigos reentregues ainda chegam na forma velha."""
    from api.app import _subscription_da_invoice
    novo = json.loads(str(_evento_invoice_paid(sub='sub_NOVO')))['data']['object']
    assert _subscription_da_invoice(novo) == 'sub_NOVO', 'não leu a forma ATUAL da API'
    antigo = {'id': 'in_X', 'subscription': 'sub_VELHO'}
    assert _subscription_da_invoice(antigo) == 'sub_VELHO', 'quebrou o formato antigo'
    assert _subscription_da_invoice({}) is None
    print('OK  test_a_assinatura_da_invoice_e_lida_na_forma_NOVA_e_na_antiga')


def test_o_fim_do_periodo_e_lido_nos_DOIS_lugares():
    """Sem isto, o `customer.subscription.updated` apagava a validade que o `invoice.paid` gravou."""
    from api.app import _fim_do_periodo
    assert _fim_do_periodo({'items': {'data': [{'current_period_end': 123}]}}) == 123, (
        'não leu o período no ITEM, que é onde a API atual o coloca')
    assert _fim_do_periodo({'current_period_end': 999}) == 999, 'quebrou o formato antigo'
    assert _fim_do_periodo({}) is None
    assert _fim_do_periodo({'items': {'data': []}}) is None
    print('OK  test_o_fim_do_periodo_e_lido_nos_DOIS_lugares')


def test_o_handler_PROMOVE_com_evento_assinado():
    """O teste que a suíte não tinha: o caminho da PRODUÇÃO, ponta a ponta.

    Ele monta um evento na forma atual da API, dentro de um `StripeObject`, e exige que o usuário
    saia de `free` para `pro` com validade. Com qualquer um dos três defeitos de volta, ele falha.
    """
    os.environ['STRIPE_WEBHOOK_SECRET'] = 'whsec_teste'
    import api.app as app_mod
    from database.schema import init_db

    init_db()
    cli = app_mod.app.test_client()

    # E-mail UNICO por execucao, e NADA de pular. A 1a versao fazia
    # `except: uid=None` + `print('PULADO'); return`, e na segunda execucao o usuario ja existia:
    # `create_user` falhava, o teste se auto-desligava e **passava verde**. Foi assim que a
    # mutacao que remove a normalizacao do evento -- o defeito principal deste arquivo --
    # sobreviveu a varredura. Terceira vez no mesmo dia que "pular = verde" me morde.
    import uuid
    from database.repositories import create_user, get_user_by_id
    marca = uuid.uuid4().hex[:10]
    uid = create_user('pagante_' + marca, 'pagante_%s@test.local' % marca, 'x' * 12)
    assert uid, 'nao consegui criar o usuario de teste'

    # Ids UNICOS por execucao, pelo mesmo motivo do e-mail: com `sub_PROMO` fixo, a 2a
    # rodada achava pelo `get_user_by_subscription` o usuario da rodada ANTERIOR (que
    # ficou com esse `mp_subscription_id`) e promovia ele -- o usuario novo continuava
    # free e o teste acusava o produto por um defeito do proprio teste.
    evento = _evento_invoice_paid(uid=uid, sub='sub_' + marca, inv='in_' + marca)
    # `validate_webhook` é o que devolve o StripeObject em produção: é ele que o teste substitui,
    # e não o `request.json` -- trocar o request testaria o caminho do dict outra vez.
    original = app_mod.validate_webhook
    app_mod.validate_webhook = lambda payload, sig: evento
    try:
        # O usuário precisa ser encontrável pela assinatura OU pelo metadata; aqui exercitamos o
        # metadata, que é a porta que cobre a corrida da 1ª fatura.
        r = cli.post('/subscription/webhook', data='{}',
                     headers={'Stripe-Signature': 'x', 'Content-Type': 'application/json'})
        assert r.status_code == 200, r.status_code
    finally:
        app_mod.validate_webhook = original
        os.environ.pop('STRIPE_WEBHOOK_SECRET', None)

    u = get_user_by_id(uid)
    assert u and u['plan'] == 'pro', (
        'o webhook ASSINADO não promoveu: usuário ficou %r. É o defeito de 28/08, em que o '
        'cartão foi cobrado e o plano não mudou.' % (u or {}).get('plan'))
    assert u.get('plan_expires_at'), (
        'promoveu sem validade: se a renovação falhar, não há quando rebaixar')
    print('OK  test_o_handler_PROMOVE_com_evento_assinado (plan=%s ate %s)'
          % (u['plan'], u.get('plan_expires_at')))


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
