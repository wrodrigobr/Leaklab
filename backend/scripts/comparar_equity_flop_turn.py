# -*- coding: utf-8 -*-
"""Compara o veredito de flop/turn COM e SEM a equity contra a range de continuacao.

    python scripts/comparar_equity_flop_turn.py --limite 300
    python scripts/comparar_equity_flop_turn.py            # acervo inteiro (lento)

── Por que existe (28/08) ──────────────────────────────────────────────────────────────────

A frente "atacar a equity de flop/turn" ficou parada porque a medicao de 27/08 mostrou acusacoes
ENTRANDO, e a regra 7 do CLAUDE.md diz para perguntar se o conserto causa dano que o bug nao
causava. A resposta so pode vir de olhar as maos que mudam, uma a uma -- e a medicao daquele dia
foi ad-hoc e nao virou script, entao nao deu para repetir depois que o board pareado foi
consertado. Este arquivo existe para isso nao acontecer de novo.

── Como ele mede ───────────────────────────────────────────────────────────────────────────

Rodando o MOTOR, duas vezes, com `LEAKLAB_EQUITY_FLOP_TURN` desligada e ligada. Nao reimplementa a
regra de veredito em lugar nenhum: este projeto ja teve seis medicoes erradas num dia por
reconstruir a regra dentro do medidor, e uma auditoria inteira em que o `/replay` rodava uma
SEGUNDA politica por cima da do motor.

Ele nao escreve nada. E somente-leitura por construcao: nao existe `--apply`.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from database.schema import get_conn                                      # noqa: E402
from leaklab.decision_engine_v11 import evaluate_decision                 # noqa: E402
from leaklab.parser import parse_hand_history                            # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand              # noqa: E402

_ACUSA = ('small_mistake', 'clear_mistake')

# ── Onde as coisas REALMENTE moram ──────────────────────────────────────────────────────────
#
# A 1a versao deste script leu `r['math']['estimated_hand_equity']` e `r['label']`. Nenhum dos
# dois existe: o resultado do motor tem `evaluation.label`, e a equity vive na ENTRADA, em
# `di['math']['estimatedHandEquity']` (camelCase). Comparando None com None, o script imprimiu
# **"sem_troca" em 40 de 40 e "nenhum veredito muda"** -- um zero tranquilizador, que e o pior
# resultado possivel numa ferramenta de medicao porque encerra a investigacao.
#
# E tem uma consequencia de desenho: a equity e calculada pelo PIPELINE, nao pelo motor. Entao a
# chave precisa estar ligada quando as entradas sao CONSTRUIDAS, e nao quando sao avaliadas.

def _equity_da_entrada(di):
    m = di.get('math') or {}
    return m.get('estimatedHandEquity'), m.get('equitySource')


def _label(r):
    return ((r or {}).get('evaluation') or {}).get('label')


def _rec(r):
    return ((r or {}).get('bestAction') or (r or {}).get('recommended_actions') or [None])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=0,
                    help='no maximo N decisoes de flop/turn (0 = todas)')
    ap.add_argument('--exemplos', type=int, default=40)
    args = ap.parse_args()

    conn = get_conn()
    torneios = [dict(r)['id'] for r in
                conn.execute('SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id')]
    print('torneios com historico: %d' % len(torneios))

    cont = Counter()
    mudam = []
    vistos = 0

    for tid in torneios:
        if args.limite and vistos >= args.limite:
            break
        row = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        if not row:
            continue
        try:
            maos = parse_hand_history(dict(row)['raw_text'])
        except Exception:                                                 # noqa: BLE001
            cont['torneio_ilegivel'] += 1
            continue

        for h in maos:
            if args.limite and vistos >= args.limite:
                break
            # Constroi DUAS vezes: a equity nasce no pipeline, entao a chave tem de estar ligada
            # aqui e nao na avaliacao.
            try:
                os.environ.pop('LEAKLAB_EQUITY_FLOP_TURN', None)
                entradas_a = build_decision_inputs_for_hand(h)
                os.environ['LEAKLAB_EQUITY_FLOP_TURN'] = '1'
                entradas_d = build_decision_inputs_for_hand(h)
            except Exception:                                             # noqa: BLE001
                continue
            finally:
                os.environ.pop('LEAKLAB_EQUITY_FLOP_TURN', None)
            if len(entradas_a) != len(entradas_d):
                cont['entradas_desalinhadas'] += 1
                continue

            for da, dd in zip(entradas_a, entradas_d):
                if (da.get('street') or '').lower() not in ('flop', 'turn'):
                    continue
                if args.limite and vistos >= args.limite:
                    break
                vistos += 1
                ea, fa = _equity_da_entrada(da)
                ed, fd = _equity_da_entrada(dd)
                if ed is None or ea is None or abs((ed or 0) - (ea or 0)) < 1e-9:
                    cont['sem_troca'] += 1
                    continue
                cont['com_troca'] += 1
                try:
                    la, ld = _label(evaluate_decision(da)), _label(evaluate_decision(dd))
                except Exception:                                         # noqa: BLE001
                    cont['erro_no_motor'] += 1
                    continue
                if la == ld:
                    cont['veredito_igual'] += 1
                    continue
                a_acusa, d_acusa = la in _ACUSA, ld in _ACUSA
                if d_acusa and not a_acusa:
                    cont['ENTRA_acusacao'] += 1
                elif a_acusa and not d_acusa:
                    cont['SAI_acusacao'] += 1
                else:
                    cont['muda_de_faixa'] += 1
                mudam.append({
                    'tid': tid, 'hand': da.get('hand_id'), 'street': da.get('street'),
                    'mao': ''.join(da.get('hero_cards') or []),
                    'board': (da.get('spot') or {}).get('board'),
                    'acao': da.get('player_action'),
                    'eq': (ea, ed), 'label': (la, ld),
                })

    print()
    print('decisoes de flop/turn examinadas: %d' % vistos)
    for k in ('sem_troca', 'com_troca', 'veredito_igual', 'ENTRA_acusacao', 'SAI_acusacao',
              'muda_de_faixa', 'erro_no_motor', 'torneio_ilegivel'):
        if cont[k]:
            print('  %-18s %6d' % (k, cont[k]))

    # CONTROLE DE DETECCAO. Sem ele, um medidor quebrado imprime "nada muda" com a mesma cara
    # de um resultado tranquilizador -- que foi exatamente o que a 1a versao fez.
    if cont['com_troca'] == 0:
        print('\nPARE: a equity NAO mudou em nenhuma das %d decisoes. Antes de concluir que a '
              'troca e inocua, confira se a chave LEAKLAB_EQUITY_FLOP_TURN esta sendo lida no '
              'pipeline -- um medidor que le a chave errada imprime este mesmo zero.' % vistos)
        return

    if not mudam:
        print('\n%d decisoes tiveram a equity trocada e NENHUMA mudou de veredito.'
              % cont['com_troca'])
        return

    print('\n%d vereditos mudam. Os %d primeiros:' % (len(mudam), min(args.exemplos, len(mudam))))
    print('%-10s %-6s %-6s %-14s %-16s %s'
          % ('mao', 'street', 'acao', 'board', 'equity', 'veredito'))
    for m in mudam[:args.exemplos]:
        ea, ed = m['eq']
        print('%-10s %-6s %-6s %-14s %.3f -> %.3f   %-13s -> %s'
              % (m['mao'], m['street'], m['acao'], ' '.join(m['board'] or [])[:14],
                 ea, ed, m['label'][0], m['label'][1]))


if __name__ == '__main__':
    main()
