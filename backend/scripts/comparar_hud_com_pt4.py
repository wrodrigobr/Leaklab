#!/usr/bin/env python
"""Compara o HUD do GrindLab com o PokerTracker 4, no MESMO acervo.

── Por que existe (04/09/2026) ────────────────────────────────────────────────────────────

O Rullian, fundador com PT4 do lado, viu que o nosso HUD nao batia com o dele. O primeiro
diagnostico quase saiu errado: a tela mostrava 4.973 maos contra 26.852 do PT4, e a tentacao
era acusar o parser. Era o filtro de Volume (50 torneios) contra o historico inteiro dele.
**Comparar percentual antes de igualar o denominador nao mede nada.**

Igualado o escopo, sobrou defeito de verdade: o parser grava `shove` e as consultas do HUD
procuravam `jam`, entao TODO all-in preflop era invisivel para VPIP, PFR, AF, C-bet,
fold-to-3bet, BB defense e steal.

Este script existe para que "bate com o PT4" seja um NUMERO na tela, nao uma opiniao.

── Como usar ─────────────────────────────────────────────────────────────────────────────

    # 1) importa os torneios num banco DESCARTAVEL (nunca toca prod)
    python scripts/comparar_hud_com_pt4.py --pasta "C:/.../teste p4" --importar

    # 2) compara com o gabarito do PT4 (JSON ao lado, ver ALVO_EXEMPLO)
    python scripts/comparar_hud_com_pt4.py --pasta "C:/.../teste p4" --alvo alvo_pt4.json

O gabarito e um JSON com os numeros que o PT4 mostra PARA ESSE MESMO RECORTE:

    {"hands": 832, "vpip": 24.34, "pfr": 17.59, "three_bet": 7.92,
     "wtsd": 40.35, "w_at_sd": 54.68}

Chave ausente e simplesmente pulada — da para comecar com 2 numeros e crescer.
"""
import argparse
import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


# Tolerancia por stat, em pontos percentuais. NAO e zero de proposito: PT4 conta MAO RECEBIDA
# e nos contamos MAO COM DECISAO, entao existe diferenca legitima de definicao. O que a
# tolerancia nao pode fazer e esconder defeito: 0,5pp em 832 maos sao ~4 maos.
TOLERANCIA_PP = 0.5
TOLERANCIA_MAOS_PCT = 2.0   # diferenca aceitavel na CONTAGEM de maos, em %

ROTULOS = [
    ('hands',      'Maos',          'total_hands'),
    ('vpip',       'VPIP',          'vpip'),
    ('pfr',        'PFR',           'pfr'),
    ('three_bet',  '3Bet PF',       'three_bet'),
    ('wtsd',       'WTSD',          'wtsd'),
    ('w_at_sd',    'W$SD',          'w_at_sd'),
    ('af',         'AF',            'af'),
    ('cbet_pct',   'C-Bet',         'cbet_pct'),
    ('steal_pct',  'Steal',         'steal_pct'),
    ('fold_to_3bet', 'Fold to 3Bet', 'fold_to_3bet'),
]


def _banco_descartavel(nome: str = 'grindlab_pt4_compare', zerar: bool = False):
    """Banco proprio, sempre. Um script de comparacao NUNCA pode escrever no acervo real.

    `nome` permite bancos separados por recorte: sem isso duas medicoes diferentes caem no
    MESMO arquivo e a segunda le o acervo da primeira. Aconteceu comigo em 04/09 ao comparar
    original x anonimizado — os dois deram 823 maos porque eu estava lendo o banco acumulado
    das 6 importacoes anteriores, e nao o recorte que pensava estar medindo.

    `zerar` apaga antes de importar: reimportar por cima nao e idempotente.
    """
    caminho = os.path.join(tempfile.gettempdir(), '%s.db' % nome)
    if zerar and os.path.exists(caminho):
        os.remove(caminho)
    os.environ['LEAKLAB_DB'] = caminho
    os.environ.pop('DATABASE_URL', None)   # senao cairia no Postgres de producao
    return caminho


def importar(pasta: str, usuario: str) -> None:
    import database.schema as sch
    import database.repositories as repo
    sch.init_db()

    uid = None
    try:
        u = repo.get_user_by_username(usuario)
        uid = u['id'] if u else None
    except Exception:
        pass
    if not uid:
        uid = repo.create_user(usuario, '%s@fixture.local' % usuario, 'fixture1234', 'player')
        print('usuario de teste criado: %s (id %s)' % (usuario, uid))

    from database.auth import generate_token
    from api.app import app
    token = generate_token(uid, 'player')
    cliente = app.test_client()

    arquivos = sorted(glob.glob(os.path.join(pasta, '*.txt')))
    if not arquivos:
        print('nenhum .txt em %s' % pasta)
        return
    ok = err = 0
    for i, arq in enumerate(arquivos, 1):
        with open(arq, 'r', encoding='utf-8', errors='ignore') as fh:
            bruto = fh.read()
        r = cliente.post('/analyze?explain=false', json={'content': bruto},
                         headers={'Authorization': 'Bearer %s' % token})
        if r.status_code == 200:
            ok += 1
        else:
            err += 1
            print('  FALHOU %s: HTTP %s %s' % (
                os.path.basename(arq), r.status_code, r.get_data(as_text=True)[:120]))
        print('  [%d/%d] %s' % (i, len(arquivos), os.path.basename(arq)))
    print('\nimportados: %d ok, %d falhas' % (ok, err))


def comparar(usuario: str, alvo_path: str | None) -> int:
    import database.schema as sch  # noqa: F401  (garante init)
    import database.repositories as repo
    u = repo.get_user_by_username(usuario)
    if not u:
        print('usuario %s nao existe no banco de teste. Rode com --importar primeiro.' % usuario)
        return 2

    # last_n=0 = historico genuino. Sem isso o default (50) volta a comparar recortes
    # diferentes, que foi exatamente o mal-entendido que originou este script.
    s = repo.get_player_stats(u['id'], days=3650, last_n=0)

    alvo = {}
    if alvo_path and os.path.exists(alvo_path):
        with open(alvo_path, encoding='utf-8') as fh:
            alvo = json.load(fh)

    print()
    print('%-14s %12s %12s %10s' % ('stat', 'GrindLab', 'PokerTracker', 'delta'))
    print('-' * 52)
    fora = 0
    for chave, rotulo, campo in ROTULOS:
        nosso = s.get(campo)
        deles = alvo.get(chave)
        if nosso is None:
            print('%-14s %12s %12s %10s' % (rotulo, 'None', deles if deles is not None else '-', 'SEM DADO'))
            fora += 1
            continue
        if deles is None:
            print('%-14s %12s %12s %10s' % (rotulo, nosso, '-', 'sem alvo'))
            continue
        delta = float(nosso) - float(deles)
        if chave == 'hands':
            limite = float(deles) * TOLERANCIA_MAOS_PCT / 100.0
        else:
            limite = TOLERANCIA_PP
        marca = 'ok' if abs(delta) <= limite else 'FORA'
        if marca == 'FORA':
            fora += 1
        print('%-14s %12s %12s %+10.2f  %s' % (rotulo, nosso, deles, delta, marca))

    print()
    if not alvo:
        print('SEM GABARITO: rode com --alvo apontando o JSON do PT4 para o MESMO recorte.')
        return 0
    if fora:
        print('%d stat(s) FORA da tolerancia. Nao declare que bate.' % fora)
    else:
        print('TODOS dentro da tolerancia (%.1fpp; maos %.0f%%).' % (TOLERANCIA_PP, TOLERANCIA_MAOS_PCT))
    return 1 if fora else 0


def principal():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pasta', required=True, help='pasta com os .txt de hand history')
    ap.add_argument('--usuario', default='fixture_pt4')
    ap.add_argument('--alvo', help='JSON com os numeros do PT4 para o MESMO recorte')
    ap.add_argument('--importar', action='store_true', help='importa antes de comparar (zera o banco)')
    ap.add_argument('--db', default='grindlab_pt4_compare', help='nome do banco de teste')
    args = ap.parse_args()

    caminho = _banco_descartavel(args.db, zerar=args.importar)
    print('banco de teste: %s' % caminho)

    if args.importar:
        importar(args.pasta, args.usuario)
    raise SystemExit(comparar(args.usuario, args.alvo))


if __name__ == '__main__':
    principal()
