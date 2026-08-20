# -*- coding: utf-8 -*-
"""O DNS do nosso domínio autoriza o provedor a enviar e-mail em nome dele?

Rode antes de confiar em qualquer coisa que dependa de e-mail chegar (confirmação de
cadastro, win-back, digest). "O SMTP autenticou" NÃO é evidência de entrega — foi
exatamente isso que mascarou 7 contas presas na confirmação em agosto/2026.

    python scripts/verificar_dns_email.py
    python scripts/verificar_dns_email.py --dominio grindlabpoker.com --provedor brevo

Resolve por DNS-over-HTTPS (o container não tem dig nem dnspython) e imprime o conserto
de cada problema. Sai com código 1 quando a entrega está em risco, para poder ser usado
como gate em automação.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from leaklab.dns_email_health import PROVEDORES, avaliar_dns_email  # noqa: E402

DOH = 'https://cloudflare-dns.com/dns-query'


def resolver(nome: str, tipo: str) -> list[str]:
    """Consulta DoH e devolve os valores de resposta do tipo pedido (lista vazia se nada)."""
    r = requests.get(DOH, params={'name': nome, 'type': tipo},
                     headers={'accept': 'application/dns-json'}, timeout=15)
    r.raise_for_status()
    dados = r.json()
    out = []
    for ans in dados.get('Answer', []) or []:
        v = (ans.get('data') or '').strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        # TXT longo vem partido em pedaços entre aspas: junta.
        v = v.replace('" "', '')
        if v:
            out.append(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dominio', default=os.environ.get('EMAIL_DOMAIN', 'grindlabpoker.com'))
    ap.add_argument('--provedor', default='brevo', choices=sorted(PROVEDORES))
    args = ap.parse_args()

    cfg = PROVEDORES[args.provedor]
    print(f'Domínio: {args.dominio}   Provedor de envio: {cfg["nome"]}\n')

    txts = resolver(args.dominio, 'TXT')
    spf = next((t for t in txts if t.lower().startswith('v=spf1')), None)
    dmarc = next((t for t in resolver(f'_dmarc.{args.dominio}', 'TXT')
                  if t.lower().startswith('v=dmarc1')), None)
    dkim = {}
    for sel in cfg['seletores_dkim']:
        alvo = f'{sel}._domainkey.{args.dominio}'
        vals = resolver(alvo, 'TXT') or resolver(alvo, 'CNAME')
        dkim[sel] = vals[0] if vals else None

    print(f'  SPF   : {spf or "(nenhum)"}')
    print(f'  DMARC : {dmarc or "(nenhum)"}')
    for sel, v in dkim.items():
        print(f'  DKIM  : {sel}._domainkey -> {v or "(nenhum)"}')

    res = avaliar_dns_email(spf, dkim, dmarc, provedor=args.provedor)
    print(f'\n{res["resumo"]}\n')
    for p in res['problemas']:
        marca = 'CRÍTICO' if p['gravidade'] == 'critico' else 'aviso  '
        print(f'  [{marca}] {p["codigo"]}')
        print(f'      {p["detalhe"]}')
        print(f'      conserto: {p["conserto"]}\n')

    if res['entrega_em_risco']:
        print('Enquanto isto não for corrigido, trate TODO e-mail transacional como não entregue.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
