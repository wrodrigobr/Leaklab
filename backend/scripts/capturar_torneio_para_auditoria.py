# -*- coding: utf-8 -*-
"""Captura TUDO que a tela mostra de um torneio, para auditoria por jogador humano/agente.

    python scripts/capturar_torneio_para_auditoria.py 72 > /tmp/torneio72.jsonl

── Por que via HTTP, e nao lendo o banco ──────────────────────────────────────────────────

A pergunta da auditoria e "o que o produto DIZ ao jogador esta certo?". Ler o banco
responderia outra: "o que esta gravado". Entre os dois existem o motor de veredito, o
`StrategyProvider`, o card e a grade -- que e justamente onde os defeitos deste projeto
moraram (o card que contradizia o veredito, o replay que trocava veredito entre decisoes,
a grade 9-max que nao declarava a premissa).

Entao aqui se BATE nos mesmos endpoints que o navegador bate:

    /history/tournament/<id>      a lista e o veredito de cada mao
    /replay/<torneio>/<mao>       o replay passo a passo, com o card de decisao
    /preflop-ranges               a matriz, nas condicoes exatas de cada decisao preflop

── Sobre o token ──────────────────────────────────────────────────────────────────────────

O script emite um JWT para o proprio dono do torneio usando `auth.generate_token`, dentro do
container. Nenhuma senha e pedida, lida ou impressa, e o token nunca sai no stdout.
"""
import json
import os
import sys

sys.path.insert(0, '/app')

from database.schema import get_conn                      # noqa: E402
from database import auth                                 # noqa: E402


def _serie(v):
    """Rows do wrapper viram dict; datas viram texto."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def main():
    tid = int(sys.argv[1])
    conn = get_conn()
    dono = conn.execute(
        'SELECT t.user_id, t.tournament_id, u.email FROM tournaments t '
        'JOIN users u ON u.id = t.user_id WHERE t.id = ?', (tid,)).fetchone()
    if not dono:
        sys.exit('torneio %s nao existe' % tid)
    dono = dict(dono)

    token = auth.generate_token(dono['user_id'], 'player')
    cabecalho = {'Authorization': 'Bearer %s' % token}

    import urllib.parse
import urllib.request

    def pega(caminho):
        req = urllib.request.Request('http://127.0.0.1:5000' + caminho, headers=cabecalho)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))

    # O endpoint busca pelo tournament_id DO SITE (string), nao pelo id interno: passar o id
    # interno devolve 404 mesmo com o torneio aparecendo na lista.
    detalhe = pega('/history/tournament/%s' % dono['tournament_id'])
    maos = detalhe.get('decisions') or []
    print(json.dumps({'tipo': 'torneio', 'id': tid,
                      'tournament_id': dono['tournament_id'],
                      'n_maos': len(maos), 'detalhe': detalhe}, ensure_ascii=False))

    # ── replay de CADA mão, e a matriz nas condições de cada decisão preflop ───────────────
    vistos_range = {}
    for m in maos:
        hid = m.get('hand_id')
        if hid is None:
            continue
        try:
            replay = pega('/replay/%s/%s' % (dono['tournament_id'], hid))
        except Exception as e:                       # noqa: BLE001
            print(json.dumps({'tipo': 'erro_replay', 'hand_id': hid, 'erro': str(e)},
                             ensure_ascii=False))
            continue
        print(json.dumps({'tipo': 'replay', 'hand_id': hid, 'lista': m, 'replay': replay},
                         ensure_ascii=False))

        for passo in replay.get('steps', []):
            gto = passo.get('preflop_gto') or {}
            pos = gto.get('position') or passo.get('hero_position')
            stack = gto.get('stack_bb') or passo.get('hero_stack_bb')
            if not pos or stack is None:
                continue
            chave = '%s|%s' % (pos, round(float(stack)))
            if chave in vistos_range:
                continue
            try:
                vistos_range[chave] = pega(
                    '/preflop-ranges?%s'      # urlencode: '+' cru vira ESPACO na query
                    % urllib.parse.urlencode({'position': pos, 'stack_bb': stack}))
            except Exception as e:                   # noqa: BLE001
                vistos_range[chave] = {'erro': str(e)}

    for chave, grade in vistos_range.items():
        pos, stack = chave.split('|')
        print(json.dumps({'tipo': 'matriz', 'position': pos, 'stack_bb': stack,
                          'grade': grade}, ensure_ascii=False))


if __name__ == '__main__':
    main()
