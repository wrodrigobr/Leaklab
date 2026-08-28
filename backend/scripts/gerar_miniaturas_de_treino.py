# -*- coding: utf-8 -*-
"""Gera as miniaturas de range dos cards de treino.

Um caractere por celula da grade 13x13. Elas sao ILUSTRACAO: o formato da range diz o que o drill
e mais rapido do que qualquer frase. Nao sao ferramenta de consulta -- para isso existe /ranges,
com frequencia e combos.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from leaklab.preflop_gto_ranges import _load                              # noqa: E402

RANKS = 'AKQJT98765432'
# (nome, balde, secao, heroi, vilao). O vilao NAO e opcional em vs_RFI e vs_3bet: as duas secoes
# sao aninhadas por vilao (`vs_3bet[heroi][3bettor]`), e procurar o heroi no nivel errado devolve
# o no de outra pessoa. A 1a versao fez isso e o controle de celulas ativas pegou: 13 num spot
# onde a range de continuacao tem dezenas.
MINIATURAS = [
    ('abrir',    '20bb', 'RFI',     'CO',  None),
    ('defender', '20bb', 'vs_RFI',  'BB',  'BTN'),
    # BB como 3-bettor de proposito: contra BTN/SB o CO folda 93% e a miniatura sairia
    # quase vazia, parecendo 'sem dado'. Contra o BB ele continua com 53%, e a FORMA da
    # range e o que o card precisa mostrar.
    ('vs_3bet',  '30bb', 'vs_3bet', 'CO',  'BB'),
]
DESTINO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..',
    'frontend', 'src', 'data', 'miniaturasDeTreino.ts'))


def mao(i, j):
    a, b = RANKS[i], RANKS[j]
    return a + b if i == j else ((a + b + 's') if i < j else (b + a + 'o'))


def spot(ranges, balde, secao, heroi, vilao):
    """O no do (heroi, vilao) pedido. NAO adivinha: sem o no exato devolve vazio, e o controle de
    celulas ativas transforma isso em erro visivel em vez de miniatura errada."""
    sec = (ranges.get(balde) or {}).get(secao) or {}
    if vilao is None:                                   # RFI: sec[heroi] direto
        no = sec.get(heroi)
        return no if isinstance(no, dict) and 'hand_freqs' in no else {}
    if secao == 'vs_3bet':                              # vs_3bet[heroi][3bettor]
        return ((sec.get(heroi) or {}).get(vilao)) or {}
    for chave, dentro in sec.items():                   # vs_RFI[abridor][defensor]
        if chave.replace('_open', '') == vilao and isinstance(dentro, dict):
            return dentro.get(heroi) or {}
    return {}


def tira(sp):
    hf = sp.get('hand_freqs') or {}
    fora = []
    for i in range(13):
        for j in range(13):
            f = hf.get(mao(i, j)) or {}
            r = sum(v for k, v in f.items() if k.startswith('R') and k != 'RAI')
            a = float(f.get('RAI', 0.0))
            c = float(f.get('C', 0.0))
            if a > 0.5:
                fora.append('a')
            elif r > 0.5:
                fora.append('r')
            elif c > 0.5:
                fora.append('c')
            elif (r + a + c) > 0.05:
                fora.append('m')
            else:
                fora.append('f')
    return ''.join(fora)


def main():
    ranges = _load().get('ranges') or {}
    linhas, ok = [], True
    for nome, balde, secao, heroi, vilao in MINIATURAS:
        sp = spot(ranges, balde, secao, heroi, vilao)
        t = tira(sp)
        vivas = sum(1 for ch in t if ch != 'f')
        # O controle mudou: contar celulas contra um limiar fixo deu alarme falso num spot em que
        # o heroi folda 93% e a forma REAL e pequena. O que importa e se o no foi ENCONTRADO --
        # lookup errado devolve dict vazio, e ai a miniatura seria uma grade toda cinza com cara
        # de dado. Um limiar minimo fica so contra o vazio absoluto.
        if not sp.get('hand_freqs'):
            print('ERRO: no de %s nao encontrado (heroi/vilao errados?)' % nome)
            ok = False
        elif vivas < 5:
            print('ERRO: %s ficou com %d celulas -- nao ilustra nada' % (nome, vivas))
            ok = False
        linhas.append('  %s: %s,' % (nome, json.dumps(t)))
        print('  %-10s %s %s %s vs %s -> %d celulas ativas'
              % (nome, balde, secao, heroi, vilao or '-', vivas))

    cab = [
        '// GERADO por `backend/scripts/gerar_miniaturas_de_treino.py`. NAO editar a mao.',
        '//',
        '// Um caractere por celula da grade 13x13, na ordem de leitura:',
        '//   r = raise   c = call   a = all-in   m = misto   f = fold',
        '//',
        '// Servem de ILUSTRACAO nos cards de treino: o formato da range diz o que o drill e mais',
        '// rapido do que qualquer frase. Nao sao ferramenta de consulta -- para isso existe',
        '// /ranges, com frequencia, combos e os seletores.',
        'export const MINIATURAS_DE_TREINO: Record<string, string> = {',
    ]
    io.open(DESTINO, 'w', encoding='utf-8').write(
        '\n'.join(cab) + '\n' + '\n'.join(linhas) + '\n};\n')
    print('-> %s' % os.path.relpath(DESTINO))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
