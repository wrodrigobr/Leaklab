# -*- coding: utf-8 -*-
"""Captura a TELA, monta o dossie e roda o portao de aceite -- tudo em um comando.

    docker exec app-web-1 python /app/scripts/portao_pos_deploy.py          # torneio padrao
    docker exec app-web-1 python /app/scripts/portao_pos_deploy.py 72 142   # varios

Sai com codigo != 0 quando alguma porta reprova OU quando a amostra nao exercita todas as
portas. Foi feito para pendurar no deploy: a suite prova as funcoes, este prova a COMPOSICAO
das camadas na tela, que e onde os defeitos deste projeto moraram.

Na auditoria de 27/08 ele pegou quatro violacoes que a suite inteira nao pegaria, porque
nenhuma delas mora dentro de uma funcao: `pode_falar_como_gto` verdadeiro ao lado de custo
filtrado, acusacao sem recomendacao, coverage dizendo "covered" sem entregar rotulo, e o card
recomendando `jam` para quem ja tinha pago all-in.

── Sobre a captura vazia ──────────────────────────────────────────────────────────────────

Logo depois de `docker compose up` o container aceita conexao antes de estar pronto, e a
captura volta com zero passos. Isso aconteceu tres vezes numa tarde. O portao ja recusa
aprovar amostra sem denominador, mas aqui a espera e explicita: sem ela o deploy "passaria"
por nao ter medido nada.
"""
import json
import os
import subprocess
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
TORNEIOS_PADRAO = ['72']
TENTATIVAS = 4
ESPERA_S = 8


def _roda(args, saida=None):
    with (open(saida, 'w', encoding='utf-8') if saida else open(os.devnull, 'w')) as fh:
        return subprocess.run([sys.executable] + args, stdout=fh, stderr=subprocess.PIPE,
                              text=True)


def _captura(tid, destino):
    """Captura com reespera: container recem-subido devolve zero passos."""
    for tentativa in range(1, TENTATIVAS + 1):
        r = _roda([os.path.join(_AQUI, 'capturar_torneio_para_auditoria.py'), str(tid)], destino)
        linhas = sum(1 for _ in open(destino, encoding='utf-8')) if os.path.exists(destino) else 0
        if linhas:
            return linhas
        print('   captura do torneio %s veio VAZIA (tentativa %d/%d): %s'
              % (tid, tentativa, TENTATIVAS, (r.stderr or '').strip()[-160:]))
        time.sleep(ESPERA_S)
    return 0


def main():
    torneios = sys.argv[1:] or TORNEIOS_PADRAO
    dossies = []
    for tid in torneios:
        bruto = '/tmp/portao_%s.jsonl' % tid
        dossie = '/tmp/portao_%s.dossie.jsonl' % tid
        print('capturando torneio %s ...' % tid)
        linhas = _captura(tid, bruto)
        if not linhas:
            print('PORTAO: INCONCLUSIVO — a captura do torneio %s nao produziu nada apos %d '
                  'tentativas. Sem amostra nao ha aprovacao.' % (tid, TENTATIVAS))
            return 1
        print('   %d registros' % linhas)
        r = _roda([os.path.join(_AQUI, 'dossies_para_auditoria.py'), bruto, dossie])
        if r.returncode != 0 or not os.path.exists(dossie):
            print('PORTAO: INCONCLUSIVO — falha ao montar o dossie: %s'
                  % (r.stderr or '').strip()[-200:])
            return 1
        dossies.append(dossie)

    # Um dossie so por vez: cada torneio tem seu proprio denominador, e somar mascara a porta
    # que este torneio nao exercita.
    pior = 0
    for d in dossies:
        print()
        r = subprocess.run([sys.executable, os.path.join(_AQUI, 'portao_de_aceite.py'), d],
                           text=True)
        pior = max(pior, r.returncode)
    return pior


if __name__ == '__main__':
    sys.exit(main())
