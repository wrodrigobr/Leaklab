# -*- coding: utf-8 -*-
"""Liga (ou confere) o webhook do bot de boas-vindas dos fundadores.

    python scripts/configurar_bot_telegram.py --status    # só mostra o estado atual
    python scripts/configurar_bot_telegram.py --ligar     # registra o webhook
    python scripts/configurar_bot_telegram.py --desligar  # remove o webhook

Precisa de duas variáveis no ambiente do container:

    TELEGRAM_BOT_TOKEN      o token que o @BotFather te deu
    TELEGRAM_WEBHOOK_SECRET uma senha qualquer, longa, inventada por você

O segredo é a ÚNICA coisa entre o endpoint e a internet inteira: o webhook é público por
natureza, e sem ele qualquer pessoa poderia fazer o bot escrever no grupo dos fundadores.
O `--status` mostra também `last_error_message`, que é onde o Telegram conta, com todas as
letras, por que as entregas estão falhando — vale mais que qualquer suposição nossa.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

API = 'https://api.telegram.org/bot{token}/{metodo}'


def _chamar(token: str, metodo: str, **params):
    r = requests.post(API.format(token=token, metodo=metodo), json=params or {}, timeout=15)
    try:
        return r.json()
    except Exception:
        return {'ok': False, 'description': f'resposta nao-JSON ({r.status_code})'}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--status', action='store_true')
    g.add_argument('--ligar', action='store_true')
    g.add_argument('--desligar', action='store_true')
    ap.add_argument('--url', default=os.environ.get('APP_API_URL',
                                                    'https://api.grindlabpoker.com'))
    args = ap.parse_args()

    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        print('TELEGRAM_BOT_TOKEN não está no ambiente. Pegue com o @BotFather e coloque '
              'no .env do servidor.')
        return 2

    eu = _chamar(token, 'getMe')
    if not eu.get('ok'):
        print('o token não foi aceito pelo Telegram:', eu.get('description'))
        return 2
    bot = eu['result']
    print(f"bot: @{bot.get('username')} ({bot.get('first_name')})")
    if os.environ.get('TELEGRAM_BOT_USERNAME', '').strip().lstrip('@') != (bot.get('username') or ''):
        print(f"  AVISO: TELEGRAM_BOT_USERNAME no ambiente não bate com @{bot.get('username')}."
              "\n  Sem isso, o link de boas-vindas do grupo sai quebrado.")

    if args.status:
        info = _chamar(token, 'getWebhookInfo').get('result', {})
        print('\nwebhook atual:', info.get('url') or '(nenhum)')
        print('  pendentes na fila:', info.get('pending_update_count', 0))
        if info.get('last_error_message'):
            print('  ÚLTIMO ERRO:', info['last_error_message'])
            print('  (o Telegram só reporta aqui; nosso log não vê entrega que não chegou)')
        return 0

    if args.desligar:
        r = _chamar(token, 'deleteWebhook')
        print('desligado' if r.get('ok') else f"falhou: {r.get('description')}")
        return 0 if r.get('ok') else 1

    segredo = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '').strip()
    if len(segredo) < 16:
        print('TELEGRAM_WEBHOOK_SECRET ausente ou curto demais (mínimo 16 caracteres).')
        print('Este segredo é o que impede estranhos de falarem pelo bot. Gere um longo.')
        return 2

    destino = args.url.rstrip('/') + '/telegram/webhook'
    r = _chamar(token, 'setWebhook', url=destino, secret_token=segredo,
                allowed_updates=['message'], drop_pending_updates=True)
    if not r.get('ok'):
        print('falhou ao registrar:', r.get('description'))
        return 1
    print(f'webhook registrado em {destino}')

    info = _chamar(token, 'getWebhookInfo').get('result', {})
    if info.get('url') != destino:
        print('CONFERÊNCIA FALHOU: o Telegram diz que a URL é', info.get('url'))
        return 1
    print('conferido: o Telegram confirma a URL registrada')
    return 0


if __name__ == '__main__':
    sys.exit(main())
