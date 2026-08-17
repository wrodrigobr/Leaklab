# -*- coding: utf-8 -*-
"""Valida o estimador de equity contra as cartas de vilao REVELADAS no SUMMARY.

── O que isto mede (e o que NAO mede) ─────────────────────────────────────────────────────────

`decisions.estimated_equity` e estimado vs mao ALEATORIA (postflop) ou vs range; a mao
revelada e a fatia da range que chegou ao SHOWDOWN — mais forte que a media por selecao.
Entao `est − real` positivo NA MEDIA e esperado por construcao, nao e "erro do estimador".
O que a medicao prova de verdade:

  1. QUANTO o vs-random absolve a mais, por street, com dado real — o fenomeno que o guarda
     #27 trata no preflop, agora quantificado no postflop;
  2. casos EXTREMOS (est alto com real ~0 na mesma street) que merecem inspecao um a um;
  3. calibracao no river, onde vs a mao revelada a equity real e quase-binaria.

Medicao pura: nada e escrito. Emparelhamento ESTRITO: so mao com exatamente UM revelador
alem do heroi E decisao com n_active_opponents == 1 — vs range de 2+ oponentes a comparacao
com UMA mao revelada nao significa nada. Denominador impresso em cada filtro
([[reference_medir_observando_nao_reconstruindo]]).

Equity real: enumeracao EXATA (eval7) dos runouts no board da street da decisao; preflop usa
a matriz 169x169 do proprio motor (leaklab/equity.py) — observar, nao reconstruir.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.schema import get_conn, init_db                       # noqa: E402
from leaklab.equity import equity_vs_hand                           # noqa: E402
from leaklab.equity_real import cartas as _cartas, equity_exata     # noqa: E402  (fonte unica)
from leaklab.gto_utils import hand_to_type                          # noqa: E402
from leaklab.parser import parse_hand_history                       # noqa: E402

_N_POR_STREET = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}


def _ancoras():
    """Prova que o medidor DETECTA antes de medir (regra 1): numeros conhecidos."""
    aa72 = equity_vs_hand('AA', '72o')
    assert aa72 and 0.83 <= aa72 <= 0.92, f'ancora preflop AA vs 72o: {aa72}'
    # AA vs KK num flop seco: ~0.91; nuts no river = 1.0; drawing dead = 0.0
    e = equity_exata(['As', 'Ad'], ['Kh', 'Ks'], ['2c', '7d', '9h'])
    assert e and 0.85 <= e <= 0.96, f'ancora flop AA vs KK: {e}'
    e = equity_exata(['As', 'Ad'], ['Kh', 'Ks'], ['Ac', 'Ah', '2d', '2s', '9h'])
    assert e == 1.0, f'ancora river nuts: {e}'
    e = equity_exata(['2c', '3d'], ['Ah', 'As'], ['Ac', 'Ad', '9h', '9s', 'Kh'])
    assert e == 0.0, f'ancora river dead: {e}'
    print(f'ancoras do medidor: OK (AA vs 72o = {aa72:.3f}; nuts 1.0; dead 0.0)\n')


def main() -> int:
    _ancoras()
    init_db()
    conn = get_conn()
    ts = conn.execute('SELECT id, hero, raw_text FROM tournaments').fetchall()
    print(f'torneios: {len(ts)}')

    n_maos = n_com_reveal = n_um_revelador = 0
    pares = []                                        # (tid, hand_id, hero_cards?, vilao_cards)
    reveladores = {}
    for t in ts:
        t = dict(t)
        try:
            hands = parse_hand_history(t['raw_text'])
        except Exception:
            continue
        for h in hands:
            n_maos += 1
            rev = {n: c for n, c in (getattr(h, 'reveals', None) or {}).items()
                   if n != (t['hero'] or '') and c}
            if not rev:
                continue
            n_com_reveal += 1
            if len(rev) != 1:
                continue                               # 2+ reveladores: pareamento ambiguo
            n_um_revelador += 1
            (nome, cartas), = rev.items()
            reveladores[(t['id'], str(h.hand_id))] = _cartas(cartas)
    print(f'maos parseadas: {n_maos} | com reveal de vilao: {n_com_reveal} '
          f'| com UM revelador (pareaveis): {n_um_revelador}')

    if not reveladores:
        print('nada a medir neste ambiente')
        return 1

    n_dec = n_hu = n_com_eq = n_medidas = 0
    descartes = {'cartas_malformadas': 0, 'street_desconhecida': 0,
                 'board_curto': 0, 'equity_none': 0, 'preflop_sem_matriz': 0}
    exemplo_board = None
    linhas = []
    for (tid, hid), vilao in reveladores.items():
        rows = conn.execute(
            'SELECT id, street, board, hero_cards, action_taken, estimated_equity, '
            '       n_active_opponents, label, ev_loss_bb '
            '  FROM decisions WHERE tournament_id = ? AND hand_id = ?', (tid, hid)).fetchall()
        for r in rows:
            d = dict(r)
            n_dec += 1
            if int(d.get('n_active_opponents') or 0) != 1:
                continue                               # estimativa vs 2+ ranges: nao compara
            n_hu += 1
            est = d.get('estimated_equity')
            if est is None:
                continue
            n_com_eq += 1
            hero = _cartas(d.get('hero_cards'))
            street = (d.get('street') or '').lower()
            n_board = _N_POR_STREET.get(street)
            if len(hero) != 2 or len(vilao) != 2:
                descartes['cartas_malformadas'] += 1
                continue
            if n_board is None:
                descartes['street_desconhecida'] += 1
                continue
            if street == 'preflop':
                real = equity_vs_hand(hand_to_type(hero) or '', hand_to_type(vilao) or '')
                if real is None:
                    descartes['preflop_sem_matriz'] += 1
                    continue
            else:
                board = _cartas(d.get('board'))[:n_board]
                if len(board) != n_board:
                    descartes['board_curto'] += 1
                    if exemplo_board is None:
                        exemplo_board = (street, repr(d.get('board')))
                    continue
                real = equity_exata(hero, vilao, board)
                if real is None:
                    descartes['equity_none'] += 1
                    continue
            n_medidas += 1
            linhas.append({'tid': tid, 'hand': hid, 'street': street,
                           'acao': d.get('action_taken'), 'est': float(est),
                           'real': float(real), 'gap': float(est) - float(real),
                           'label': d.get('label')})
    print(f'decisoes das maos pareaveis: {n_dec} | HU (n_active_opponents=1): {n_hu} '
          f'| com estimated_equity: {n_com_eq} | MEDIDAS: {n_medidas}')
    print(f'descartes: {descartes}'
          + (f' | exemplo de board descartado: {exemplo_board}' if exemplo_board else '') + '\n')

    if not linhas:
        print('populacao vazia apos filtros')
        return 1

    print('AVISO DE METODO: mao revelada e a fatia que chegou ao showdown (range mais forte '
          'que a media). gap medio POSITIVO e esperado por construcao — o numero util e o '
          'TAMANHO dele por street, e os extremos.\n')
    fmt = '%-8s %5s   est_medio %5.3f   real_medio %5.3f   gap_medio %+6.3f   gap_p90 %+6.3f'
    for st in ('preflop', 'flop', 'turn', 'river'):
        grupo = [x for x in linhas if x['street'] == st]
        if not grupo:
            continue
        gaps = sorted(x['gap'] for x in grupo)
        p90 = gaps[int(0.9 * (len(gaps) - 1))]
        print(fmt % (st, len(grupo), sum(x['est'] for x in grupo) / len(grupo),
                     sum(x['real'] for x in grupo) / len(grupo),
                     sum(gaps) / len(gaps), p90))
    print()
    for acao in ('call', 'fold', 'raise', 'bet', 'check', 'allin', 'shove'):
        grupo = [x for x in linhas if (x['acao'] or '').lower() == acao]
        if len(grupo) >= 5:
            print('acao %-6s n=%3d  gap_medio %+6.3f'
                  % (acao, len(grupo), sum(x['gap'] for x in grupo) / len(grupo)))
    print('\nEXTREMOS (|gap| maior — est alto com real baixo merece olhar um a um):')
    for x in sorted(linhas, key=lambda v: -abs(v['gap']))[:12]:
        print('  tid=%-4s hand=%-14s %-7s %-5s est %.2f real %.2f gap %+.2f label=%s'
              % (x['tid'], x['hand'], x['street'], x['acao'], x['est'], x['real'],
                 x['gap'], x['label']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
