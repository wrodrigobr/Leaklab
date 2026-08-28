# -*- coding: utf-8 -*-
"""Regera o recorte da carta que a landing renderiza.

    python scripts/gerar_vitrine_range.py

A landing mostra o `RangeGrid` DE VERDADE em vez de um print, e o dado dele vem daqui. O recorte
e um literal em `frontend/src/data/vitrineRange.ts` porque a landing e PUBLICA: chamar
`/preflop-ranges` exigiria token.

Rode isto quando `test_vitrine_range_em_dia.py` acusar divergencia. O teste existe porque o
comentario do arquivo afirmava que ele "nao envelhece calado" e isso era falso -- nao havia
gerador nem conferencia. Agora ha os dois.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from leaklab.preflop_gto_ranges import _load                              # noqa: E402

BALDE, POSICAO, SECAO = '20bb', 'CO', 'RFI'
DESTINO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..',
    'frontend', 'src', 'data', 'vitrineRange.ts'))

CABECALHO = '''// GERADO por `backend/scripts/gerar_vitrine_range.py` a partir de `preflop_gto_ranges`
// (balde %s, posicao %s, secao %s).
// NAO editar a mao: `tests/test_vitrine_range_em_dia.py` compara este recorte com a carta e
// falha quando divergem.
//
// A landing renderiza o RangeGrid DE VERDADE com este recorte, em vez de uma imagem: o que o
// visitante ve e o componente do produto, com dado do produto. Um print raster envelheceria
// calado no dia em que a carta mudasse -- isto nao, porque o guarda acusa.
import type { RangeSet } from "./ranges";

'''


def main():
    spot = ((_load().get('ranges') or {}).get(BALDE) or {}).get(SECAO, {}).get(POSICAO) or {}
    hf = spot.get('hand_freqs') or {}
    if not hf:
        print('ERRO: %s/%s/%s nao tem hand_freqs na carta.' % (BALDE, SECAO, POSICAO))
        return 1

    freqs = {}
    for mao, f in hf.items():
        raise_ = sum(v for k, v in f.items() if k.startswith('R') and k != 'RAI')
        d = {'raise': round(raise_, 4), 'allin': round(float(f.get('RAI', 0.0)), 4),
             'call': round(float(f.get('C', 0.0)), 4), 'fold': round(float(f.get('F', 0.0)), 4)}
        freqs[mao] = {k: v for k, v in d.items() if v > 0}

    ativas = sorted(m for m, f in freqs.items()
                    if (f.get('raise', 0) + f.get('allin', 0) + f.get('call', 0)) > 0.001)

    ts = (CABECALHO % (BALDE, POSICAO, SECAO)
          + 'const FREQS = %s;\n\n' % json.dumps(freqs, ensure_ascii=False, sort_keys=True)
          + 'export const VITRINE_RANGE: RangeSet = {\n'
          + '  label: %s,\n' % json.dumps('Open %s (%s)' % (POSICAO, BALDE))
          + '  raise: new Set(%s),\n' % json.dumps(ativas)
          + '  frequencies: FREQS,\n};\n')
    io.open(DESTINO, 'w', encoding='utf-8').write(ts)
    print('gerado: %d maos com frequencia, %d ativas -> %s'
          % (len(freqs), len(ativas), os.path.relpath(DESTINO)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
