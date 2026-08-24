# -*- coding: utf-8 -*-
"""Captura a MATRIZ (/preflop-ranges) em cada condicao que o torneio realmente produziu.

    python3 scripts/capturar_matrizes.py /tmp/dossies.jsonl /tmp/matrizes.json

Os pares (posicao, profundidade) saem dos dossies, entao a grade capturada e exatamente a que
o jogador veria ao abrir o painel naquelas maos -- nao um conjunto que eu escolhi.
"""
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, '/app')
from database import auth                                  # noqa: E402


def main():
    entrada, saida = sys.argv[1], sys.argv[2]
    pares = {}
    with open(entrada, encoding='utf-8') as fh:
        for linha in fh:
            reg = json.loads(linha)
            if reg.get('tipo') != 'mao':
                continue
            for passo in reg['passos_do_hero']:
                m = passo.get('matriz_do_spot') or {}
                pos, stack = m.get('position'), m.get('stack_bb')
                if pos and stack is not None:
                    pares.setdefault((pos, round(float(stack))), 0)
                    pares[(pos, round(float(stack)))] += 1

    cab = {'Authorization': 'Bearer %s' % auth.generate_token(43, 'player')}
    out = {}
    for (pos, stack), n in sorted(pares.items(), key=lambda x: -x[1]):
        # `+` CRU em query string decodifica como ESPACO: 'UTG+1' chegava como 'UTG 1' e a
        # grade voltava VAZIA. Foi assim que a auditoria de 24/08 quase reportou 'UTG+1 e
        # UTG+2 sem carta' -- a carta tem as duas nos 9 buckets; o instrumento e que perdia.
        url = ('http://127.0.0.1:5000/preflop-ranges?%s'
               % urllib.parse.urlencode({'position': pos, 'stack_bb': stack}))
        try:
            req = urllib.request.Request(url, headers=cab)
            with urllib.request.urlopen(req, timeout=60) as r:
                out['%s|%s' % (pos, stack)] = {
                    'ocorrencias_no_torneio': n,
                    'grade': json.loads(r.read().decode('utf-8'))}
        except Exception as e:                              # noqa: BLE001
            out['%s|%s' % (pos, stack)] = {'ocorrencias_no_torneio': n, 'erro': str(e)}

    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False)
    erros = sum(1 for v in out.values() if 'erro' in v)
    print('pares (posicao, stack) no torneio: %d' % len(pares))
    print('matrizes capturadas: %d   com erro: %d' % (len(out) - erros, erros))


if __name__ == '__main__':
    main()
