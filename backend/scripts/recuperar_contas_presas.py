# -*- coding: utf-8 -*-
"""Reemite o código de confirmação para quem ficou preso na porta de entrada.

Contexto (20/08/2026): 7 contas com email_verified=0 e ZERO tentativas de digitar o código.
Não desistiram — nunca receberam o e-mail, porque o DNS do domínio não autorizava o Brevo
e o DMARC mandava quarentenar.

ORDEM IMPORTA. Reenviar antes de consertar o DNS gasta a segunda chance no mesmo spam e
ainda queima reputação do domínio com mais um envio não autenticado. Por isso o script
RECUSA enviar enquanto `verificar_dns_email.py` acusar entrega em risco — passar por cima
exige --ignorar-dns explicitamente.

    python scripts/recuperar_contas_presas.py                 # só lista (padrão)
    python scripts/recuperar_contas_presas.py --enviar        # reemite de verdade

Envia e-mail para pessoas reais: é decisão de quem opera, não do script.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn  # noqa: E402
from database.repositories import _adapt  # noqa: E402


def _dns_em_risco() -> bool:
    """Pergunta ao DNS, não ao comentário. Falha de rede não vira permissão para enviar."""
    try:
        import requests
        from leaklab.dns_email_health import PROVEDORES, avaliar_dns_email
        from scripts.verificar_dns_email import resolver  # noqa: F401
    except Exception as e:
        print(f'não consegui checar o DNS ({type(e).__name__}: {e}) — tratando como EM RISCO')
        return True
    try:
        dominio = os.environ.get('EMAIL_DOMAIN', 'grindlabpoker.com')
        cfg = PROVEDORES['brevo']
        txts = resolver(dominio, 'TXT')
        spf = next((t for t in txts if t.lower().startswith('v=spf1')), None)
        dmarc = next((t for t in resolver(f'_dmarc.{dominio}', 'TXT')
                      if t.lower().startswith('v=dmarc1')), None)
        dkim = {}
        for sel in cfg['seletores_dkim']:
            alvo = f'{sel}._domainkey.{dominio}'
            v = resolver(alvo, 'TXT') or resolver(alvo, 'CNAME')
            dkim[sel] = v[0] if v else None
        res = avaliar_dns_email(spf, dkim, dmarc)
        print(f'DNS: {res["resumo"]}')
        return bool(res['entrega_em_risco'])
    except Exception as e:
        print(f'checagem de DNS falhou ({type(e).__name__}: {e}) — tratando como EM RISCO')
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--enviar', action='store_true', help='reemite e envia de verdade')
    ap.add_argument('--ignorar-dns', action='store_true',
                    help='envia mesmo com o DNS acusando entrega em risco')
    args = ap.parse_args()

    conn = get_conn()
    try:
        presos = [dict(r) for r in conn.execute(_adapt(
            "SELECT id, email, username, created_at, "
            "COALESCE(verification_attempts,0) AS tentativas "
            "FROM users WHERE COALESCE(role,'player')='player' "
            "AND COALESCE(email_verified,1)=0 ORDER BY created_at")).fetchall()]
    finally:
        conn.close()

    print(f'presos na confirmação: {len(presos)}')
    for p in presos:
        marca = 'nunca digitou nada' if p['tentativas'] == 0 else f"{p['tentativas']} tentativa(s)"
        print(f"  id={p['id']:>4}  {str(p['created_at'])[:10]}  {p['email']}  ({marca})")
    if not presos:
        return 0

    if not args.enviar:
        print('\n(nada enviado — rode com --enviar quando o DNS estiver corrigido)')
        return 0

    if _dns_em_risco() and not args.ignorar_dns:
        print('\nRECUSADO: o DNS ainda não autoriza nosso remetente, então este reenvio '
              'cairia no mesmo spam e gastaria a segunda chance.\n'
              'Conserte SPF/DKIM primeiro (scripts/verificar_dns_email.py diz como) '
              'ou force com --ignorar-dns.')
        return 2

    from api.app import _issue_verification
    ok = 0
    for p in presos:
        enviado = _issue_verification(p['id'], p['email'], p.get('username') or '')
        ok += 1 if enviado else 0
        print(f"  {'enviado ' if enviado else 'FALHOU  '} {p['email']}")
    print(f'\nreemitidos: {ok}/{len(presos)}')
    return 0 if ok == len(presos) else 1


if __name__ == '__main__':
    sys.exit(main())
