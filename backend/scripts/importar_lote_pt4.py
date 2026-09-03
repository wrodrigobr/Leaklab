#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""importar_lote_pt4.py — importa um export de mãos do PokerTracker 4 (multi-torneio) para
um usuário, pela ROTA REAL de análise.

── Por que pela rota, e não por funções soltas (03/09) ─────────────────────────────────────

O /analyze não tem núcleo extraível: parse, merge por T#, financials, gravação, perfis de
vilão e os pós-processos moram na rota. Duplicar a sequência num script é a receita da regra
5 (a cópia diverge calada). Então o script fatia o arquivo POR TORNEIO e envia cada fatia à
rota via test_client — mesmo caminho do upload do jogador, mesmos gates, mesmo merge.

── Os dois desvios do lote (env LEAKLAB_IMPORT_LOTE, só neste processo) ────────────────────

1. Quota isenta (364 torneios estouram até o Pro de 200/mês) — `_check_upload_quota`.
2. Solver no PORÃO: `_priority()` devolve 1 → qualquer spot orgânico fura o lote inteiro.

── Uso (no host, dentro do container web) ──────────────────────────────────────────────────

  docker compose exec -T web python scripts/importar_lote_pt4.py \
      --arquivo /data/lote/Export_PS.txt --usuario <username|email>          # DRY-RUN
  ... --aplicar                                                             # importa

Dry-run é o default: lista torneios/mãos/site e NÃO grava nada. Idempotente ao aplicar:
re-rodar cai no merge por T# da rota (mãos novas somam, repetidas não duplicam).
"""
import argparse
import collections
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arquivo', required=True, help='export PT4 de UM site (multi-torneio)')
    ap.add_argument('--usuario', required=True, help='username ou email do dono das mãos')
    ap.add_argument('--aplicar', action='store_true', help='sem isto: dry-run, nada é gravado')
    ap.add_argument('--max', type=int, default=None, help='importar só os N primeiros torneios (amostra)')
    args = ap.parse_args()

    # Os desvios de lote valem SÓ neste processo — setar antes de importar o app.
    os.environ['LEAKLAB_IMPORT_LOTE'] = '1'

    from leaklab.parser import parse_hand_history
    from database.repositories import get_user_by_email, get_user_by_username

    texto = io.open(args.arquivo, encoding='utf-8', errors='replace').read()
    maos = parse_hand_history(texto)
    if not maos:
        sys.exit('nenhuma mão parseada — site sem suporte neste arquivo? (PTY exige flag)')

    por_torneio = collections.OrderedDict()
    sem_tid = 0
    for m in maos:
        tid = getattr(m, 'tournament_id', None)
        if not tid:
            sem_tid += 1
            continue
        por_torneio.setdefault(tid, []).append(m)

    alvo = get_user_by_username(args.usuario) or get_user_by_email(args.usuario)
    if not alvo:
        sys.exit(f'usuário {args.usuario!r} não encontrado — ele precisa ter conta antes do lote.')

    itens = list(por_torneio.items())[: args.max]
    total_maos = sum(len(v) for _, v in itens)
    print(f'arquivo: {os.path.basename(args.arquivo)}')
    print(f'torneios: {len(itens)} (de {len(por_torneio)}) | mãos: {total_maos} | sem T#: {sem_tid}')
    print(f'destino: {alvo["username"]} (id {alvo["id"]}, plano {alvo.get("plan")})')

    if not args.aplicar:
        for tid, ms in itens[:10]:
            print(f'  T#{tid}: {len(ms)} mãos')
        if len(itens) > 10:
            print(f'  ... e mais {len(itens) - 10} torneios')
        print('\nDRY-RUN — nada gravado. Rode com --aplicar para importar.')
        return

    # Token do usuário-alvo emitido server-side (operação de admin do lote; sem senha).
    from database.auth import generate_token
    # 2º argumento é ROLE (não username) — passar o nick aqui viraria um role inventado.
    token = generate_token(alvo['id'], alvo.get('role') or 'user')
    from api.app import app
    cliente = app.test_client()

    ok = err = 0
    for i, (tid, ms) in enumerate(itens, 1):
        bruto = '\n\n'.join(getattr(m, 'raw_text', '') for m in ms if getattr(m, 'raw_text', None))
        # A rota aceita JSON {content}, multipart 'file' ou form 'content' — corpo cru NAO
        # (o smoke pegou: 400 "Conteudo ausente"). JSON é o caminho do front.
        r = cliente.post('/analyze?explain=false', json={'content': bruto},
                         headers={'Authorization': f'Bearer {token}'})
        if r.status_code == 200:
            ok += 1
        else:
            err += 1
            print(f'  FALHOU T#{tid}: HTTP {r.status_code} — {r.get_data(as_text=True)[:120]}')
        if i % 10 == 0 or i == len(itens):
            print(f'  [{i}/{len(itens)}] ok={ok} err={err}')
    print(f'\nPLACAR: {ok} importados, {err} falhas, {total_maos} mãos. '
          f'Solver: spots do lote em prioridade 1 (porão).')


if __name__ == '__main__':
    principal()
