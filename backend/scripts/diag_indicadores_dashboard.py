#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Todo indicador do dashboard REAGE a mais amostra?

── A pergunta do usuario ──────────────────────────────────────────────────────────────────────────

"Tenho a percepcao de que, por mais que eu jogue torneios, nem todos os indicadores mudam."

É uma hipotese testavel, e o jeito de testar e chamar cada endpoint com amostra PEQUENA e com
amostra CHEIA e comparar. Indicador que devolve exatamente a mesma coisa nos dois nao esta
consumindo os torneios novos.

── Por que este script tem um CONTROLE, e por que ele e obrigatorio ────────────────────────────────

"Está tudo certo" e o resultado mais perigoso que um diagnostico pode dar, porque encerra a
investigacao. Em 28/07 quatro diagnosticos deste projeto imprimiram numeros confiantes e falsos, e
um deles reportou "zero perdidas" por um bug de parsing.

Entao o script roda dois CONTROLES antes de qualquer conclusao:

  · controle POSITIVO — um indicador que TEM que variar entre 3 e todos os torneios. Se ele nao
    variar, o arnes esta quebrado e o relatorio inteiro e lixo, entao o script aborta.
  · controle NEGATIVO — a MESMA chamada duas vezes. Se der diferente, ha nao-determinismo (cache,
    relogio, aleatoriedade) e "variou" deixa de significar "consumiu amostra".

Sem os dois, um relatorio de "tudo reage" seria indistinguivel de um arnes que sempre acusa
variacao, e um de "nada reage" seria indistinguivel de um arnes que nunca chama nada.

Uso:
    python scripts/diag_indicadores_dashboard.py --user 3
    python scripts/diag_indicadores_dashboard.py --user 3 --verboso
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def _norm(obj):
    """Remove o que muda sozinho entre duas chamadas (carimbos, ids de request)."""
    VOLATEIS = {'generated_at', 'updated_at', 'timestamp', 'request_id', 'now', 'server_time'}
    if isinstance(obj, dict):
        return {k: _norm(v) for k, v in sorted(obj.items()) if k not in VOLATEIS}
    if isinstance(obj, list):
        return [_norm(x) for x in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def _assinatura(payload):
    return json.dumps(_norm(payload), sort_keys=True, ensure_ascii=False)


# (rotulo, caminho, param_pequeno, param_cheio)
#
# `last_n` = ultimos N torneios; `days` = janela. Endpoint sem nenhum dos dois entra com None e o
# script o marca como NAO PARAMETRIZAVEL em vez de fingir que testou.
ENDPOINTS = [
    ('player-stats',        '/metrics/player-stats',      'last_n=3&days=3650',   'days=3650'),
    ('evolucao',            '/player/evolution',          None,                   None),
    ('gto-quality',         '/player/gto-quality',        'last_n=3',             ''),
    ('gto-alignment',       '/player/gto-alignment',      'last_n=3',             ''),
    ('gto-position',        '/player/gto-position',       'last_n=3',             ''),
    ('leak-finder',         '/player/leak-finder',        'last_n=3',             ''),
    ('leak-roi',            '/player/leak-roi',           'last_n=3&days=3650',   'days=3650'),
    ('results-vs-gto',      '/player/results-vs-gto',     'last_n=3',             ''),
    ('confidence-drift',    '/player/confidence-drift',   'days=7',               'days=3650'),
    ('pressure-profile',    '/player/pressure-profile',   'days=7',               'days=3650'),
    ('cognitive-failures',  '/player/cognitive-failures', 'days=7',               'days=3650'),
    ('leak-graph',          '/player/leak-graph',         'days=7',               'days=3650'),
    ('strategic-twin',      '/player/strategic-twin',     'days=7',               'days=3650'),
    ('dna',                 '/player/dna',                'days=7',               'days=3650'),
    ('career',              '/player/career',             None,                   None),
    ('session-context',     '/player/session-context',    None,                   None),
    ('ev-summary',          '/player/ev-summary',         None,                   None),
    ('pending-gto-count',   '/player/pending-gto-count',  None,                   None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', type=int, required=True)
    ap.add_argument('--verboso', action='store_true')
    args = ap.parse_args()

    from api.app import app
    from database.auth import generate_token
    from database.schema import get_conn

    conn = get_conn()
    try:
        n_t = conn.execute('SELECT COUNT(*) AS n FROM tournaments WHERE user_id = %s'
                           if os.environ.get('DATABASE_URL') else
                           'SELECT COUNT(*) AS n FROM tournaments WHERE user_id = ?',
                           (args.user,)).fetchone()['n']
        n_d = conn.execute(('SELECT COUNT(*) AS n FROM decisions d JOIN tournaments t '
                            'ON t.id = d.tournament_id WHERE t.user_id = %s')
                           if os.environ.get('DATABASE_URL') else
                           ('SELECT COUNT(*) AS n FROM decisions d JOIN tournaments t '
                            'ON t.id = d.tournament_id WHERE t.user_id = ?'),
                           (args.user,)).fetchone()['n']
    finally:
        conn.close()

    print(f'user {args.user}: {n_t} torneios, {n_d} decisoes\n')
    if n_t < 4:
        print('AVISO: com menos de 4 torneios, "amostra pequena" e "cheia" quase coincidem — o '
              'resultado nao distingue indicador congelado de indicador sem o que variar.\n')

    tok = generate_token(args.user, 'player')
    cli = app.test_client()
    hdr = {'Authorization': 'Bearer ' + tok}

    def chamar(caminho, query):
        url = caminho + (('?' + query) if query else '')
        r = cli.get(url, headers=hdr)
        if r.status_code != 200:
            return None, r.status_code
        try:
            return json.loads(r.data.decode('utf-8')), 200
        except Exception:
            return None, -1

    # ── CONTROLES ─────────────────────────────────────────────────────────────────────────────
    print('CONTROLES (o relatorio abaixo so vale se os dois passarem)')

    p_peq, st1 = chamar('/metrics/player-stats', 'last_n=3&days=3650')
    p_cheio, st2 = chamar('/metrics/player-stats', 'days=3650')
    if st1 != 200 or st2 != 200:
        print(f'  ABORTADO: player-stats devolveu {st1}/{st2}, nao 200.')
        return 1
    positivo = _assinatura(p_peq) != _assinatura(p_cheio)
    print(f'  positivo (player-stats 3 x todos difere): {"OK" if positivo else "FALHOU"}')

    p_a, _ = chamar('/metrics/player-stats', 'days=3650')
    p_b, _ = chamar('/metrics/player-stats', 'days=3650')
    negativo = _assinatura(p_a) == _assinatura(p_b)
    print(f'  negativo (mesma chamada 2x e identica): {"OK" if negativo else "FALHOU"}')

    if not positivo or not negativo:
        print('\nARNES QUEBRADO — nao interprete o relatorio abaixo. '
              'Sem o controle positivo, "nada reage" pode ser o script nao chamando nada; '
              'sem o negativo, "reage" pode ser ruido.')
        return 1
    print()

    # ── RELATORIO ─────────────────────────────────────────────────────────────────────────────
    reage, congelado, sem_param, erro = [], [], [], []
    for rotulo, caminho, q_peq, q_cheio in ENDPOINTS:
        if q_peq is None:
            d, st = chamar(caminho, '')
            (sem_param if st == 200 else erro).append((rotulo, st))
            continue
        a, sa = chamar(caminho, q_peq)
        b, sb = chamar(caminho, q_cheio)
        if sa != 200 or sb != 200:
            erro.append((rotulo, f'{sa}/{sb}'))
            continue
        (reage if _assinatura(a) != _assinatura(b) else congelado).append(rotulo)
        if args.verboso and _assinatura(a) == _assinatura(b):
            print(f'    [{rotulo}] identico: {_assinatura(a)[:220]}')

    # ── O TESTE QUE RESPONDE A PERGUNTA DE VERDADE ────────────────────────────────────────────
    #
    # "3 torneios x todos" prova que o indicador olha ALGUMA amostra. Nao prova que ele continua
    # se mexendo quando voce joga MAIS UM — um indicador com teto interno (ORDER BY id DESC
    # LIMIT 120, por exemplo) passaria naquele teste e ficaria parado neste. Foi exatamente esse
    # vies que me fez reportar "85% do EV e recuperavel" quando o numero real era 37%.
    print(f'
{"="*66}
O ULTIMO TORNEIO MUDA O INDICADOR? ({n_t} x {n_t - 1} torneios)
{"="*66}')
    mexe, parado = [], []
    for rotulo, caminho, q_peq, q_cheio in ENDPOINTS:
        if q_peq is None or 'last_n' not in q_peq:
            continue
        base = 'days=3650&' if 'days' in (q_cheio or '') or 'days' in q_peq else ''
        a2, s2a = chamar(caminho, f'{base}last_n={n_t}')
        b2, s2b = chamar(caminho, f'{base}last_n={n_t - 1}')
        if s2a != 200 or s2b != 200:
            continue
        (mexe if _assinatura(a2) != _assinatura(b2) else parado).append(rotulo)
    print(f'  muda ao tirar o ultimo torneio ({len(mexe)}): ' + (', '.join(mexe) or '-'))
    print(f'  NAO muda ({len(parado)}): ' + (', '.join(parado) or '-'))
    if parado:
        print('  ^ investigar: teto interno, cache, ou o torneio mais novo nao tem decisao do tipo')
    print()

    print(f'REAGE a mais amostra ({len(reage)}):')
    for r in reage:
        print(f'    {r}')
    print(f'\nIDENTICO com 3 torneios e com todos ({len(congelado)}):')
    for r in congelado:
        print(f'    {r}   <-- investigar')
    if sem_param:
        print(f'\nNAO PARAMETRIZAVEL, nao testado aqui ({len(sem_param)}):')
        for r, _ in sem_param:
            print(f'    {r}')
    if erro:
        print(f'\nERRO na chamada ({len(erro)}):')
        for r, st in erro:
            print(f'    {r}: HTTP {st}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
