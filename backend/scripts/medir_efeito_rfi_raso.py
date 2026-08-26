# -*- coding: utf-8 -*-
"""O que muda no acervo quando a faixa 2,5-7,5bb passa a ter carta da PROPRIA profundidade.

    python scripts/medir_efeito_rfi_raso.py <linhas_da_faixa.json>

O arquivo de entrada e um dump das decisoes preflop do acervo com stack em [2,5, 7,5), tirado do
banco de producao.

── Por que ABLACAO e nao reimplementacao ──────────────────────────────────────────────────

Reconstruir os argumentos exatos que o motor passou para `analyze_preflop` a partir de uma linha
do banco e adivinhacao, e adivinhacao ja contaminou seis medicoes minhas nesta base
([[reference_medir_observando_nao_reconstruindo]]). Entao a medicao aqui NAO tenta reproduzir o
veredito gravado: ela roda `analyze_preflop` DUAS vezes com **exatamente os mesmos argumentos**,
trocando so a existencia da faixa rasa (`_BALDES_RASOS` cheia e vazia). A diferenca entre
as duas rodadas e valida mesmo que a reconstrucao dos argumentos seja imperfeita, porque o erro
de reconstrucao e o MESMO nos dois lados e se cancela.

O que a medicao NAO responde: se o veredito novo esta certo. Ela responde o que mudou, e quanto.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import preflop_gto_ranges as R                            # noqa: E402
from leaklab.gto_utils import hand_to_type                             # noqa: E402

_RASOS = ('3bb', '4bb', '5bb', '6bb', '7bb')


def _cartas(bruto):
    if not bruto:
        return []
    s = str(bruto).strip()
    return s.split() if ' ' in s else [s[i:i + 2] for i in range(0, len(s), 2)]


def _analisa(linha):
    """A carta responde o que para esta linha? Mesmos argumentos nos dois lados da ablacao."""
    mao = hand_to_type(_cartas(linha['hero_cards']))
    if not mao:
        return None
    try:
        r = R.analyze_preflop(
            hero_hand_type=mao,
            position=linha['position'] or '',
            stack_bb=float(linha['stack']),
            action_taken=(linha['action_taken'] or '').lower(),
            n_players=linha.get('num_players'),
            facing_raises=int(linha.get('rf') or 0),
            # `vs_position` e `hero_was_aggressor` decidem em QUAL cenario a linha cai (RFI,
            # vs_RFI, vs_3bet). Sem eles a primeira medicao jogou 5 linhas de pote ja aberto no
            # ramo de RFI e produziu "acusacao nova" que descrevia um spot inexistente.
            vs_position=('' if str(linha.get('vs_position') or '').lower() in ('', 'unknown')
                         else linha['vs_position']),
            hero_was_aggressor=bool(linha.get('agr')),
            facing_to_bb=float(linha.get('facing_bet') or 0),
        )
    except Exception as e:                                             # noqa: BLE001
        return {'erro': type(e).__name__ + ': ' + str(e)[:60]}
    return {
        'available': bool(r.get('available')),
        # o balde GERAL nao muda mais (a faixa rasa so vale para RFI), entao quem
        # descreve a ablacao e `balde_rfi`
        'bucket': R.balde_rfi(float(linha['stack'])),
        'rec': ','.join(r.get('recommended_actions') or []),
        'in_range': r.get('in_range'),
        'quality': r.get('action_quality'),
    }


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: medir_efeito_rfi_raso.py <linhas.json>')
    with open(sys.argv[1], encoding='utf-8') as fh:
        linhas = json.load(fh)

    completo = list(R._BALDES_RASOS)
    if not completo:
        sys.exit('CONTROLE FALHOU: a faixa rasa nao existe, nao ha o que ablacionar')

    def roda(baldes):
        R._BALDES_RASOS[:] = baldes
        R._mapa_mesa_cache.clear()
        return [_analisa(l) for l in linhas]

    antes = roda([])          # como era antes da importacao: so a carta de 10bb fala
    depois = roda(completo)
    R._BALDES_RASOS[:] = completo

    # CONTROLE: a ablacao mexeu no balde de alguem? Se nao mexeu, a medicao esta cega.
    mudou = sum(1 for a, d in zip(antes, depois)
                if a and d and (a.get('rec') != d.get('rec')
                                or a.get('available') != d.get('available')
                                or a.get('quality') != d.get('quality')))
    if not mudou:
        sys.exit('CONTROLE FALHOU: nenhuma linha mudou entre as duas rodadas -- a ablacao nao '
                 'esta ablacionando nada e o resultado seria um zero vazio')
    print('linhas: %d | mudaram na ablacao: %d' % (len(linhas), mudou))

    def cen(l):
        return 'RFI' if int(l.get('rf') or 0) == 0 else ('vs_RFI' if int(l['rf']) == 1 else 'vs_3bet+')

    print('\n%-10s %7s %10s %10s %12s %12s'
          % ('cenario', 'linhas', 'carta ANTES', 'carta DEPOIS', 'ganharam', 'perderam'))
    for c in ('RFI', 'vs_RFI', 'vs_3bet+'):
        idx = [i for i, l in enumerate(linhas) if cen(l) == c]
        a = sum(1 for i in idx if antes[i] and antes[i].get('available'))
        d = sum(1 for i in idx if depois[i] and depois[i].get('available'))
        ganhou = sum(1 for i in idx if depois[i] and depois[i].get('available')
                     and not (antes[i] or {}).get('available'))
        perdeu = sum(1 for i in idx if antes[i] and antes[i].get('available')
                     and not (depois[i] or {}).get('available'))
        print('%-10s %7d %10d %10d %12d %12d' % (c, len(idx), a, d, ganhou, perdeu))

    # onde a carta fala nos DOIS lados, a recomendacao mudou?
    virou = []
    for i, l in enumerate(linhas):
        a, d = antes[i], depois[i]
        if not (a and d and a.get('available') and d.get('available')):
            continue
        if a.get('rec') != d.get('rec') or a.get('in_range') != d.get('in_range'):
            virou.append((l, a, d))
    print('\ncom carta nos DOIS lados e recomendacao DIFERENTE: %d' % len(virou))
    for l, a, d in virou[:15]:
        print('   %-4s %-5s %5.1fbb  %s -> %s   | fez %-6s | era %s'
              % (hand_to_type(_cartas(l['hero_cards'])), l['position'], float(l['stack']),
                 '%s:%s' % (a['bucket'], a['rec']), '%s:%s' % (d['bucket'], d['rec']),
                 l['action_taken'], l['label']))

    # a qualidade da acao do hero mudou de lado? (e o que vira/deixa de virar acusacao)
    piorou = melhorou = 0
    _RUIM = ('leak', 'major_leak')
    for i, l in enumerate(linhas):
        a, d = antes[i], depois[i]
        if not (a and d):
            continue
        qa, qd = a.get('quality'), d.get('quality')
        if qa == qd:
            continue
        if qd in _RUIM and qa not in _RUIM:
            piorou += 1
        elif qa in _RUIM and qd not in _RUIM:
            melhorou += 1
    print('\nqualidade da acao do hero:')
    print('  deixou de ser leak (acusacao some): %d' % melhorou)
    print('  passou a ser leak (acusacao nova):  %d' % piorou)


if __name__ == '__main__':
    main()
