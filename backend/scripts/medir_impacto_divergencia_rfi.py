# -*- coding: utf-8 -*-
"""Quantas ACUSACOES do acervo caem numa celula onde a carta externa discorda da nossa.

    python scripts/medir_impacto_divergencia_rfi.py <arquivo.tsv>

`comparar_rfi_com_carta_externa.py` diz o quanto as duas cartas concordam (94,0%).
`divergencias_duras_rfi.py` isola as que sao de DECISAO e nao de modelo (75 celulas convictas).
Este mede a unica coisa que muda o produto: **quantas vezes o acervo real caiu exatamente nessas
celulas, e em quantas delas nos ACUSAMOS o jogador**.

Concordancia de 94% numa carta que quase nunca e consultada nas celulas divergentes vale mais que
99% numa que so e consultada la. O denominador tem que ser o uso, nao a grade.

CONTROLE (regra 1): o script conta primeiro quantas decisoes preflop de RFI existem no recorte e
quantas caem em celula COMPARAVEL. Se esse numero vier zero, o filtro esta errado e o "zero
divergencias" seria o falso alivio de sempre -- por isso ele falha alto em vez de imprimir 0.
"""
import os
import sys

sys.path.insert(0, '/app')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from comparar_rfi_com_carta_externa import (le_externa, le_nossa,      # noqa: E402
                                            classifica_externa)
from leaklab.preflop_gto_ranges import _load, _stack_bucket, _norm_pos  # noqa: E402
from leaklab.gto_utils import hand_to_type                             # noqa: E402
from database.schema import get_conn                                   # noqa: E402

_ACUSA = ('small_mistake', 'clear_mistake')
_MISTA = 0.85


def _freq(cel, mao):
    f = (cel.get('hand_freqs') or {}).get(mao)
    return max(f.values()) if isinstance(f, dict) and f else 1.0


def mapa_de_divergencias(caminho):
    """{(pos, bucket, mao): (nossa, dele, dura)} para as celulas sobrepostas."""
    ext = le_externa(caminho)
    ranges = _load()['ranges']
    out = {}
    for bucket in ranges:
        prof = int(bucket.replace('bb', ''))
        for pos, cel in (ranges[bucket].get('RFI') or {}).items():
            maos_ext = ext.get((pos, prof))
            if not maos_ext:
                continue
            nossa = le_nossa(bucket, pos)
            for mao, acao in maos_ext.items():
                dele = classifica_externa(acao)
                minha = nossa.get(mao)
                if minha is None:
                    continue
                dura = ({minha, dele} == {'fold', 'agride'} and _freq(cel, mao) >= _MISTA)
                out[(pos, bucket, mao)] = (minha, dele, dura)
    return out


def _cartas(bruto):
    if not bruto:
        return []
    if isinstance(bruto, str):
        s = bruto.strip()
        if ' ' in s:
            return s.split()
        return [s[i:i + 2] for i in range(0, len(s), 2)]
    return list(bruto)


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: medir_impacto_divergencia_rfi.py <arquivo.tsv>')
    mapa = mapa_de_divergencias(sys.argv[1])
    comparaveis = {k for k in mapa}
    divergentes = {k for k, v in mapa.items() if v[0] != v[1]}
    duras = {k for k, v in mapa.items() if v[2]}
    print('celulas comparaveis: %d | divergentes: %d | duras: %d'
          % (len(comparaveis), len(divergentes), len(duras)))

    conn = get_conn()
    linhas = [dict(r) for r in conn.execute("""
        SELECT d.hero_cards, d.position, d.label, d.action_taken, d.best_action,
               d.verdict_source, d.num_players,
               COALESCE(d.effective_stack_bb, d.stack_bb) AS stack
        FROM decisions d
        WHERE d.street = 'preflop'
          AND COALESCE(d.preflop_raises_faced, 0) = 0
          AND d.position IS NOT NULL
          AND COALESCE(d.effective_stack_bb, d.stack_bb) IS NOT NULL
    """)]
    conn.close()

    total = cobertas = em_divergencia = em_dura = acusadas_em_dura = 0
    acusadas_cobertas = 0
    exemplos = []
    for l in linhas:
        total += 1
        mao = hand_to_type(_cartas(l['hero_cards']))
        if not mao:
            continue
        # `_norm_pos` com o TAMANHO DA MESA é o que o motor faz antes de consultar a carta
        # (decision_engine_v11.py:260 passa `nPlayers`). Reconstruir isso à mão aqui já produziu
        # um falso positivo: `UTG` numa mesa de 5 é `HJ` na carta 9-max, e o único "conflito"
        # que a primeira medição achou vinha de olhar a célula errada.
        chave = (_norm_pos(l['position'], l.get('num_players')),
                 _stack_bucket(float(l['stack'])), mao)
        if chave not in comparaveis:
            continue
        cobertas += 1
        acusa = (l['label'] or '') in _ACUSA
        if acusa:
            acusadas_cobertas += 1
        if chave in divergentes:
            em_divergencia += 1
        if chave in duras:
            em_dura += 1
            if acusa:
                acusadas_em_dura += 1
                if len(exemplos) < 12:
                    nossa, dele, _ = mapa[chave]
                    exemplos.append('%-4s %-5s %-7s  nos: %-7s ele: %-7s  fez %-6s -> %s'
                                    % (mao, chave[0], chave[1], nossa, dele,
                                       l['action_taken'], l['label']))

    if not cobertas:
        sys.exit('CONTROLE FALHOU: zero decisoes caem em celula comparavel. O filtro esta errado '
                 '-- este zero seria falso alivio, nao boa noticia.')

    print('\ndecisoes preflop de pote nao aberto: %d' % total)
    print('  em celula comparavel (posicao+profundidade que as duas cartas cobrem): %d' % cobertas)
    print('    dessas, ACUSADAS por nos: %d (%.1f%%)'
          % (acusadas_cobertas, 100.0 * acusadas_cobertas / cobertas))
    print('  caem em celula ONDE AS CARTAS DIVERGEM: %d (%.1f%% das comparaveis)'
          % (em_divergencia, 100.0 * em_divergencia / cobertas))
    print('  caem em divergencia DURA (fold <-> agride, nos convictos): %d (%.2f%%)'
          % (em_dura, 100.0 * em_dura / cobertas))
    print('  ACUSACOES nossas em cima de divergencia dura: %d %s'
          % (acusadas_em_dura,
             '(%.2f%% de todas as acusacoes do recorte)'
             % (100.0 * acusadas_em_dura / acusadas_cobertas) if acusadas_cobertas else ''))
    if exemplos:
        print('\nas acusacoes que a carta dele nao sustentaria:')
        for e in exemplos:
            print('   ' + e)


if __name__ == '__main__':
    main()
