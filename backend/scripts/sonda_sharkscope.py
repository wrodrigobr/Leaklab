# -*- coding: utf-8 -*-
"""Sonda da API do SharkScope: prova a autenticacao ANTES de gastar busca.

── Por que existe (19/09) ────────────────────────────────────────────────────────────────────

O dono assinou um plano com 10 buscas por dia e quer testar. A API resolve um buraco medido: no
acervo, `buy_in` esta preenchido em 8,9% dos torneios e `profit` em 6,7% -- e o PartyPoker, que
nao gera summary, e totalmente rastreado por eles.

O que a API **nao** da: mao nenhuma. A base do SharkScope e de RESULTADO de torneio, zero hand
history. Ela completa a camada financeira, nunca a de analise.

── O que falta para rodar ───────────────────────────────────────────────────────────────────

`appname` e `application key`, alocados pelo SharkScope **mediante pedido** (nao vem com a
assinatura). A senha viaja como `md5(md5(senha) + application_key)`, entao sem a chave nao ha
como assinar a requisicao.

── Como rodar, sem o segredo encostar no repositorio ────────────────────────────────────────

    SHARKSCOPE_APP=nome_do_app SHARKSCOPE_KEY=chave \\
    SHARKSCOPE_USER=email@do.dono SHARKSCOPE_PASS=senha \\
      python scripts/sonda_sharkscope.py --jogador NomeNaSala --rede pokerstars

Nada e lido de arquivo e nada e gravado. As credenciais vem do ambiente e ficam nele.

── A ordem das chamadas e deliberada: o gratis primeiro ─────────────────────────────────────

1. `metadata` custa ZERO busca. Se a autenticacao estiver errada, o erro aparece aqui, de graca.
2. so entao o `summary` do jogador, que custa 1 busca.

Com 10 buscas por dia, queimar uma para descobrir que o usuario estava errado seria desperdicio
evitavel. A sonda so gasta depois de o gratis ter passado.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://www.sharkscope.com/api'


def senha_codificada(senha: str, chave_do_app: str) -> str:
    """`md5(md5(senha) + application_key)`, em hex minusculo.

    O documento e literal: "All MD5 encoded passwords must be re-encoded using MD5 encoding the
    second time post-fixed with the application key". Post-fixed = a chave vai DEPOIS do primeiro
    hash, e nao antes. Trocar a ordem devolve 401 sem dizer por que.
    """
    primeiro = hashlib.md5(senha.encode('utf-8')).hexdigest()
    return hashlib.md5((primeiro + chave_do_app).encode('utf-8')).hexdigest()


def chamar(app: str, caminho: str, usuario: str, senha_hash: str, params=None):
    """(status, corpo). Nunca levanta por erro HTTP: o corpo do erro e a informacao."""
    q = dict(params or {})
    q['Username'] = usuario
    q['Password'] = senha_hash
    url = '%s/%s/%s?%s' % (BASE, app, caminho.lstrip('/'), urllib.parse.urlencode(q))
    req = urllib.request.Request(url, headers={
        # Os dois sao exigidos pelo documento. `User-Agent` vazio derruba a chamada, e o
        # `Accept` e quem escolhe o formato da resposta.
        'Accept': 'application/json',
        'User-Agent': 'GrindLab/1.0 (sonda de integracao)',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jogador', help='nome na sala (sem ele, so o passo gratis roda)')
    ap.add_argument('--rede', default='pokerstars')
    args = ap.parse_args()

    faltando = [v for v in ('SHARKSCOPE_APP', 'SHARKSCOPE_KEY',
                            'SHARKSCOPE_USER', 'SHARKSCOPE_PASS') if not os.environ.get(v)]
    if faltando:
        print('Faltam no ambiente: %s' % ', '.join(faltando))
        print('A chave e o nome do app sao alocados pelo SharkScope mediante pedido.')
        return 2

    app = os.environ['SHARKSCOPE_APP']
    usuario = os.environ['SHARKSCOPE_USER']
    senha = senha_codificada(os.environ['SHARKSCOPE_PASS'], os.environ['SHARKSCOPE_KEY'])
    print('app=%s  usuario=%s  (senha codificada, %d chars)' % (app, usuario, len(senha)))

    print()
    print('== PASSO 1: metadata (custo ZERO) ==')
    st, corpo = chamar(app, 'metadata', usuario, senha)
    print('  HTTP %s' % st)
    print('  %s' % corpo[:400].replace('\n', ' '))
    if st != 200:
        print()
        print('A autenticacao NAO passou. Nenhuma busca foi gasta.')
        return 1

    if not args.jogador:
        print()
        print('Autenticacao OK. Rode de novo com --jogador para gastar 1 busca no summary.')
        return 0

    print()
    print('== PASSO 2: summary do jogador (custo 1 busca) ==')
    caminho = 'networks/%s/players/%s' % (urllib.parse.quote(args.rede),
                                          urllib.parse.quote(args.jogador))
    st, corpo = chamar(app, caminho, usuario, senha, {'filter': 'Type:Tourn'})
    print('  HTTP %s' % st)
    try:
        d = json.loads(corpo)
        print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])
    except Exception:
        print('  %s' % corpo[:2000])
    # O cabecalho de quota vem no corpo em alguns recursos; imprimir cru ajuda a conferir
    # quantas buscas sobraram sem precisar abrir o site.
    return 0 if st == 200 else 1


if __name__ == '__main__':
    sys.exit(main())
