# -*- coding: utf-8 -*-
"""Ensaio dirigido do e-mail de cobrança: manda para UMA pessoa, escolhida na linha de comando.

Existe para responder a pergunta que nenhum teste automatizado responde: como o e-mail chega de
verdade, no cliente de e-mail de verdade. É o passo antes de ligar `ENGAGEMENT_EMAIL_ENABLED`
para a base inteira.

    python scripts/testar_cobranca_email.py <email>                    # seco (não envia)
    python scripts/testar_cobranca_email.py <email> --enviar           # envia o gatilho REAL
    python scripts/testar_cobranca_email.py <email> --tipo todos --enviar

── Travas, e por que cada uma existe ─────────────────────────────────────────────────────────

1. **Destinatário explícito e obrigatório.** Sem argumento, o script não faz nada. Não existe
   caminho aqui que alcance mais de uma pessoa, nem por engano nem por flag esquecida.
2. **Modo seco é o padrão.** Enviar exige `--enviar` digitado. O oposto (enviar por padrão, com
   `--dry` para não) já bastou para muita gente mandar e-mail sem querer.
3. **NÃO grava em `engagement_emails`.** Se gravasse, o ensaio queimaria o teto semanal daquela
   pessoa e ela ficaria sete dias sem receber a cobrança de verdade — o teste sabotaria o que
   veio testar.
4. **Ignora `ENGAGEMENT_EMAIL_ENABLED` de propósito**, no mesmo espírito do disparo manual do
   comunicado do admin: a flag protege o disparo AUTOMÁTICO em massa; um envio nominal pedido na
   linha de comando é outra coisa.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TIPOS = ('leak_reaberto', 'relatorio_gerado', 'revisao_vencida', 'inatividade')

# Dados plausíveis para ver a copy de cada modelo quando a pessoa não tem aquele evento agora.
# Marcados como forjados no relatório do script — número inventado passando por medição é
# exatamente o que este projeto não faz.
_FORJADOS = {
    'leak_reaberto':    {'titulo': 'Abertura (RFI) de HJ · 50bb'},
    'relatorio_gerado': {'id': 0, 'motivo': 'veredito'},
    'revisao_vencida':  {'total': 3, 'drills': 1, 'ranges': 2},
    'inatividade':      {'missao': {'titulo': 'BB vs open do LJ · 30bb',
                                    'ev_loss_bb': 14.4, 'hands': 21}, 'dias': 9},
}


def main() -> int:
    ap = argparse.ArgumentParser(description='Ensaio dirigido do e-mail de cobrança.')
    ap.add_argument('email', help='destinatário (precisa existir como usuário)')
    ap.add_argument('--tipo', default='auto',
                    help="'auto' (o gatilho real da pessoa), um dos %s, ou 'todos'" % (TIPOS,))
    ap.add_argument('--enviar', action='store_true',
                    help='envia de verdade; sem isto o script só mostra o que enviaria')
    args = ap.parse_args()

    from datetime import datetime
    from database.schema import get_conn
    from database.repositories import _adapt, _fetchone, ultimo_email_de_cobranca
    from leaklab.cobranca_email import coletar_eventos, decidir_email_cobranca, montar_email
    from leaklab.email_digest import send_transactional_email, _email_unsub_token

    conn = get_conn()
    try:
        u = _fetchone(conn, _adapt(
            "SELECT id, email, username, email_opt_in, email_verified FROM users WHERE email = ?"),
            (args.email,))
    finally:
        conn.close()
    if not u:
        print(f'ERRO: nenhum usuário com o e-mail {args.email}')
        return 2
    u = dict(u)
    uid = int(u['id'])
    base = os.environ.get('APP_BASE_URL', 'https://grindlabpoker.com')
    agora = datetime.utcnow().isoformat()

    print(f"destinatário : {u['email']} (id={uid}, username={u.get('username')})")
    print(f"opt-in       : {u.get('email_opt_in')} | verificado: {u.get('email_verified')}")
    print(f"último envio : {ultimo_email_de_cobranca(uid) or 'nenhum'}")
    print(f"SMTP         : {'configurado' if os.environ.get('SMTP_HOST') else 'AUSENTE (não enviaria)'}")

    eventos = coletar_eventos(uid, agora)
    print(f"eventos reais: {[e['tipo'] for e in eventos] or 'nenhum'}")

    if args.tipo == 'todos':
        alvos = [(t, _FORJADOS[t], True) for t in TIPOS]
    elif args.tipo in TIPOS:
        real = next((e for e in eventos if e['tipo'] == args.tipo), None)
        alvos = [(args.tipo, real['dados'] if real else _FORJADOS[args.tipo], real is None)]
    else:
        # 'auto': o gatilho REAL, pela mesma função pura que o worker usa — e sem histórico,
        # para ver o que a pessoa receberia se o teto não estivesse no caminho.
        escolhido = decidir_email_cobranca(agora, eventos, None)
        if not escolhido:
            print('\nNada a enviar: esta pessoa não tem evento de cobrança agora.')
            print("Use --tipo todos para ver a copy dos quatro modelos.")
            return 0
        alvos = [(escolhido['tipo'], escolhido.get('dados') or {}, False)]

    token = _email_unsub_token(uid)
    unsub = f'{base}/api/player/email/unsubscribe?uid={uid}&token={token}'
    enviados = 0
    for tipo, dados, forjado in alvos:
        montado = montar_email(tipo, dados, u.get('username') or '', base, unsub)
        if not montado:
            print(f'  {tipo}: sem corpo (tipo desconhecido)')
            continue
        assunto, html = montado
        marca = ' [DADOS FORJADOS]' if forjado else ' [dados reais]'
        print(f"\n  tipo    : {tipo}{marca}")
        print(f"  assunto : {assunto}")
        print(f"  tamanho : {len(html)} bytes")
        if args.enviar:
            ok = send_transactional_email(u['email'], assunto, html)
            print(f"  enviado : {'SIM' if ok else 'FALHOU (ver log do SMTP)'}")
            enviados += 1 if ok else 0
        else:
            print('  enviado : não (modo seco; use --enviar)')

    print(f"\n{enviados} e-mail(s) enviado(s). "
          f"NADA foi gravado em engagement_emails — o teto semanal desta pessoa segue intacto.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
