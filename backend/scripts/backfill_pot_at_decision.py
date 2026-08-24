# -*- coding: utf-8 -*-
"""Preenche `decisions.pot_at_decision_bb` nas linhas antigas.

    python scripts/backfill_pot_at_decision.py --dry-run
    python scripts/backfill_pot_at_decision.py --apply

Por que existe: a nota do card escrevia `pot {pot_size}bb` chamando de pote um numero que nao
e o pote da decisao -- "pot 1.0bb" onde havia 3,7bb, em 215 de 433 decisoes preflop do torneio
auditado (49,7%). O valor certo (`_pot_at_decision`, 99,6% contra o `Total pot` do SUMMARY) ja
era calculado; so nao era gravado.

NAO toca em `pot_size`, `label`, `score` nem em nada que decida veredito: as pot odds sempre
usaram o pote certo, e este backfill so preenche uma coluna nova de EXIBICAO. Rode com
`--dry-run` primeiro; ele mostra a distribuicao da diferenca antes de escrever.
"""
import argparse
import sys

sys.path.insert(0, '/app')

from database.schema import get_conn                            # noqa: E402
from leaklab.parser import parse_hand_history                   # noqa: E402
from leaklab import hand_state_builder as hsb                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    conn = get_conn()
    torneios = [dict(r) for r in conn.execute(
        'SELECT id, raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id').fetchall()]

    preenchidas = 0
    sem_par = 0
    iguais = 0
    difs = []

    for t in torneios:
        try:
            maos = parse_hand_history(t['raw_text'])
        except Exception:                                       # noqa: BLE001
            continue
        # o que esta no banco, na MESMA ordem do parser
        gravadas = {}
        for r in conn.execute(
                'SELECT id, hand_id, street, action_taken, pot_size, level_bb '
                'FROM decisions WHERE tournament_id=? ORDER BY id', (t['id'],)).fetchall():
            d = dict(r)
            chave = (str(d['hand_id']), (d['street'] or '').lower(),
                     (d['action_taken'] or '').lower())
            gravadas.setdefault(chave, []).append(d)

        for hand in maos:
            acoes = getattr(hand, 'actions', []) or []
            hero = getattr(hand, 'hero', None)
            hid = str(getattr(hand, 'hand_id', '') or '')
            for i, a in enumerate(acoes):
                if getattr(a, 'player', None) != hero:
                    continue
                street = (getattr(a, 'street', '') or 'preflop').lower()
                acao = (getattr(a, 'action', '') or '').lower()
                fila = gravadas.get((hid, street, acao))
                if not fila:
                    sem_par += 1
                    continue
                d = fila.pop(0)
                bb = float(d['level_bb'] or 0)
                if not bb:
                    sem_par += 1
                    continue
                try:
                    pote = hsb._pot_at_decision(hand, acoes, i, street)
                except Exception:                               # noqa: BLE001
                    sem_par += 1
                    continue
                if not pote:
                    sem_par += 1
                    continue
                valor = round(float(pote) / bb, 1)
                antigo = d['pot_size']
                if antigo is not None and abs(float(antigo) - valor) < 0.05:
                    iguais += 1
                else:
                    difs.append((float(antigo or 0), valor))
                if args.apply:
                    conn.execute('UPDATE decisions SET pot_at_decision_bb=? WHERE id=?',
                                 (valor, d['id']))
                preenchidas += 1
        if args.apply:
            conn.commit()

    print('torneios: %d' % len(torneios))
    print('decisoes com pote reconstruido: %d   sem par no banco: %d' % (preenchidas, sem_par))
    print('  onde pot_size JA batia: %d' % iguais)
    print('  onde DIFERE: %d' % len(difs))
    if difs:
        piores = sorted(difs, key=lambda x: -(x[1] - x[0]))[:5]
        print('  maiores diferencas (pot_size -> pote real, em bb):')
        for a, b in piores:
            print('    %.1f -> %.1f' % (a, b))
    if not args.apply:
        print('\n[DRY-RUN] nada foi escrito')


if __name__ == '__main__':
    main()
