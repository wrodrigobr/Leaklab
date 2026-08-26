# -*- coding: utf-8 -*-
"""Das divergencias entre a nossa carta RFI e a externa, quais podem VIRAR ACUSACAO ERRADA.

    python scripts/divergencias_duras_rfi.py <arquivo.tsv>

`comparar_rfi_com_carta_externa.py` mede a concordancia inteira. Mas nem toda divergencia pesa
igual no produto:

  * agride <-> limp  e diferenca de MODELO. A carta dele oferece open-limp em varias posicoes; a
    nossa (GW MTT) so oferece no SB. Nenhuma das duas esta "errada" -- sao arvores diferentes. E
    inofensivo para nos: o hero que limpa fora do SB ja e tratado por
    [[project_limp_fora_dos_blinds]], que nao consulta a carta.
  * fold <-> agride e diferenca de DECISAO. Uma das duas cartas manda jogar a mao e a outra manda
    jogar fora. E so essa que pode virar acusacao errada na tela.

Este script isola a segunda familia e pergunta de cada caso: a NOSSA celula estava em cima do
muro? Mao com frequencia mista (55/45) que o outro classifica pro outro lado nao e defeito -- e o
arredondamento de dois solves. Mao nossa em 100% que ele folda em 100% e desacordo duro, e cada
uma dessas merece uma pergunta de poker.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from comparar_rfi_com_carta_externa import (le_externa, le_nossa,     # noqa: E402
                                            classifica_externa)
from leaklab.preflop_gto_ranges import _load                          # noqa: E402

_MISTA = 0.85          # abaixo disso a nossa celula nao estava convicta


def _freq_da_acao(cel, mao):
    """Frequencia da acao MAJORITARIA nossa para a mao (1.0 = convicto)."""
    f = (cel.get('hand_freqs') or {}).get(mao)
    if not isinstance(f, dict) or not f:
        return 1.0
    return max(f.values())


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: divergencias_duras_rfi.py <arquivo.tsv>')
    ext = le_externa(sys.argv[1])
    ranges = _load()['ranges']

    duras = []
    for bucket in sorted(ranges, key=lambda b: int(b.replace('bb', ''))):
        prof = int(bucket.replace('bb', ''))
        for pos, cel in (ranges[bucket].get('RFI') or {}).items():
            maos_ext = ext.get((pos, prof))
            if not maos_ext:
                continue
            nossa = le_nossa(bucket, pos)
            for mao, acao in maos_ext.items():
                dele = classifica_externa(acao)
                minha = nossa.get(mao)
                if minha is None or minha == dele:
                    continue
                if {minha, dele} != {'fold', 'agride'}:
                    continue            # divergencia de MODELO, nao de decisao
                duras.append((prof, pos, mao, minha, dele, _freq_da_acao(cel, mao)))

    convictas = [d for d in duras if d[5] >= _MISTA]
    mistas = [d for d in duras if d[5] < _MISTA]

    print('divergencias de DECISAO (fold <-> agride): %d' % len(duras))
    print('  nossa celula estava em cima do muro (freq < %.0f%%): %d  -- arredondamento, nao defeito'
          % (_MISTA * 100, len(mistas)))
    print('  nossa celula CONVICTA e ele discorda:              %d  <- as que merecem pergunta'
          % len(convictas))

    por_mao = {}
    for prof, pos, mao, minha, dele, f in convictas:
        por_mao.setdefault((mao, minha, dele), []).append('%s@%d' % (pos, prof))

    print('\nas convictas, agrupadas pela mao (nossa -> dele):')
    for (mao, minha, dele), onde in sorted(por_mao.items(), key=lambda kv: -len(kv[1])):
        print('  %-4s %-7s -> %-7s  %2d celula(s): %s'
              % (mao, minha, dele, len(onde), ', '.join(sorted(onde)[:10])))

    # concentracao por profundidade: divergencia espalhada e ruido, concentrada e sintoma
    print('\nconcentracao por profundidade:')
    por_prof = {}
    for prof, pos, mao, minha, dele, f in convictas:
        por_prof.setdefault(prof, []).append(mao)
    for prof in sorted(por_prof):
        print('  %3dbb: %2d' % (prof, len(por_prof[prof])))


if __name__ == '__main__':
    main()
