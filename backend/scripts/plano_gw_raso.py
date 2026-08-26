# -*- coding: utf-8 -*-
"""Monta o plano de captura do GW para a faixa RASA de defesa (vs_RFI / vs_3bet, 2,5-7,5bb).

    python scripts/plano_gw_raso.py <decisoes_rasas.json> [--teto-nos N]

── Por que MEDIDO e nao chutado ───────────────────────────────────────────────────────────

O primeiro plano de ring (07/08) fixava 15/20/30/40bb para todos os pares por analogia com o HU.
Rodando o motor sobre as decisoes reais, as profundidades nao tinham nada a ver com o chute --
`SB x BTN` vive em 60-100bb. Cota gasta em carta que o motor RECUSA pela janela de 25%. Entao
aqui a entrada e o dado: os stacks que cada par realmente teve no acervo, e o plano e o conjunto
MINIMO de profundidades que cobre esses stacks dentro da janela.

── O que fica de fora, declarado ──────────────────────────────────────────────────────────

* Pares onde quem "abriu" age DEPOIS do hero (ex.: `BB abre` e o SB defende). Preflop isso nao
  existe -- hero ja tinha agido, entao so segue na mao por ter LIMPADO. Nao ha no na arvore
  raise-first para capturar, e capturar seria inventar.
* `UTG+2`: o GW gratuito so tem 8-max, e a mesa de 8 nao tem esse assento
  (`_ORDEM_RING[8]`). Mapear para o vizinho seria palpite, entao esses casos ficam sem carta.

── O custo e do usuario ───────────────────────────────────────────────────────────────────

Cota do GW e por conta e o limite diario chega perto de ~90 requisicoes. Por isso a saida e
ordenada por DECISOES COBERTAS por no: quem parar no meio para no melhor lugar possivel.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import (_norm_pos, _profundidade_compativel,   # noqa: E402
                                        _ORDEM_RING, _IDX_ACAO_PREFLOP)

_ORDEM8 = _ORDEM_RING[8]
_MENU = [3.125, 4.125, 5.125, 6.125, 7.125]      # candidatas; o coletor recusa a que nao existir


def _cobre(depth, stacks):
    return [s for s in stacks if _profundidade_compativel(depth, s)]


def _minimo_de_depths(stacks):
    """Conjunto guloso de profundidades que cobre todos os stacks dentro da janela de 25%."""
    faltam = list(stacks)
    escolhidas = []
    while faltam:
        melhor = max(_MENU, key=lambda d: len(_cobre(d, faltam)))
        pegos = _cobre(melhor, faltam)
        if not pegos:
            break                                   # stack fora do alcance do menu
        escolhidas.append(melhor)
        faltam = [s for s in faltam if s not in pegos]
    return sorted(set(escolhidas)), faltam


def _linha(abre, hero, intencao):
    """Linha de acao 8-max ate o hero, ou None se o par nao existe na arvore raise-first."""
    if abre not in _ORDEM8 or hero not in _ORDEM8:
        return None
    if _IDX_ACAO_PREFLOP.get(abre, 99) >= _IDX_ACAO_PREFLOP.get(hero, -1):
        return None                                 # o "abridor" age depois do hero: pote limpado
    i_abre, i_hero = _ORDEM8.index(abre), _ORDEM8.index(hero)
    linha = ['fold'] * i_hero
    linha[i_abre] = intencao
    return linha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('decisoes')
    ap.add_argument('--teto-nos', type=int, default=40)
    args = ap.parse_args()

    with open(args.decisoes, encoding='utf-8') as fh:
        linhas = json.load(fh)

    pares = {}
    for r in linhas:
        vs = str(r.get('vs_position') or '')
        if not vs or vs.lower() == 'unknown':
            continue
        hero = _norm_pos(r['position'], r.get('num_players'))
        abre = _norm_pos(vs, r.get('num_players'))
        chave = (abre, hero)
        pares.setdefault(chave, []).append(round(float(r['stack']), 2))

    blocos, fora, total_nos, cobertas = [], [], 0, 0
    for (abre, hero), stacks in sorted(pares.items(), key=lambda kv: -len(kv[1])):
        # a 3-7bb o open e JAM, nao min-raise: a range de open do SB a 5bb e 77% all-in
        linha = _linha(abre, hero, 'allin')
        if linha is None:
            motivo = ('assento inexistente no 8-max' if abre not in _ORDEM8 or hero not in _ORDEM8
                      else 'o "abridor" age depois do hero (pote limpado, sem no na arvore)')
            fora.append('%-6s -> %-6s  %3d decisoes  (%s)' % (abre, hero, len(stacks), motivo))
            continue
        depths, descobertos = _minimo_de_depths(stacks)
        if descobertos:
            fora.append('%-6s -> %-6s  %3d stacks fora do alcance do menu' % (abre, hero, len(descobertos)))
        if not depths:
            continue
        if total_nos + len(depths) > args.teto_nos:
            fora.append('%-6s -> %-6s  %3d decisoes  (acima do teto de %d nos)'
                        % (abre, hero, len(stacks), args.teto_nos))
            continue
        total_nos += len(depths)
        cobertas += len(stacks) - len(descobertos)
        blocos.append({
            '_alvo': '%s defende o jam do %s — %d decisoes' % (hero, abre, len(stacks)),
            '_decisoes': len(stacks),
            'depths': depths,
            'linhas': [linha],
        })

    plano = {
        '_comentario': [
            'PLANO MEDIDO (26/08) para a faixa RASA de defesa: vs_RFI e vs_3bet entre 2,5 e 7,5bb.',
            'Entrada: as %d decisoes do acervo que hoje nao tem carta da propria profundidade.' % len(linhas),
            'As profundidades por par sao o conjunto MINIMO que cobre os stacks observados dentro',
            'da janela de 25% de `_profundidade_compativel` — capturar fora dela e cota gasta em',
            'carta que o motor recusa.',
            'A intencao e `allin` porque a 3-7bb o open E jam (a range do SB a 5bb e 77% all-in).',
            'Ordenado por decisoes cobertas: parar no meio para no melhor lugar possivel.',
        ],
        'gametype': 'MTTGeneral_8m',
        'saida': 'docs/ring_ranges_har.json',
        'blocos': blocos,
    }
    destino = os.path.join(os.path.dirname(__file__), '..', 'docs', 'gw_plano_raso.json')
    with open(destino, 'w', encoding='utf-8') as fh:
        json.dump(plano, fh, ensure_ascii=False, indent=2)

    print('pares distintos no acervo: %d' % len(pares))
    print('NO PLANO: %d blocos, %d nos, cobrindo %d das %d decisoes (%.0f%%)'
          % (len(blocos), total_nos, cobertas, len(linhas), 100.0 * cobertas / max(1, len(linhas))))
    print('\n%-38s %5s  %s' % ('alvo', 'nos', 'profundidades'))
    for b in blocos:
        print('%-38s %5d  %s' % (b['_alvo'][:38], len(b['depths']),
                                 ', '.join('%.3f' % d for d in b['depths'])))
    if fora:
        print('\nFICARAM DE FORA (declarado, nao esquecido):')
        for f in fora:
            print('   ' + f)
    print('\nescrito em docs/gw_plano_raso.json')


if __name__ == '__main__':
    main()
