# -*- coding: utf-8 -*-
"""O mapa dos 1.300 sem `gto_label`, lido pelo CAMINHO REAL e pareado por ORDEM.

Duas versoes anteriores desta sonda erraram, e vale registrar as duas:

1. chamava `_enrich_preflop_gto` isolado -- e o enriquecimento isolado ve entradas que o motor
   nao usa. Dizia "64 ja cobertas" contra um regrade que dizia `MUDAM: 0`;
2. pareava a linha gravada com a fresca por `(mao, acao)` -- ambiguo quando a mesma mao tem duas
   decisoes preflop com a mesma acao (hero enfrenta o CO e depois o SB). Dizia "27 ja cobertas".

Agora: `evaluate_decision` (o caminho real) e casamento por ORDEM dentro da mao, com a mesma trava
de `_regrade_tournament` -- so vale quando as listas tem o mesmo tamanho E as acoes alinham
posicao a posicao. Desalinhou, a mao inteira e pulada e CONTADA como pulada, nao diluida.
"""
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                                      # noqa: E402
from leaklab.parser import parse_hand_history                             # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand               # noqa: E402
from leaklab.decision_engine_v11 import evaluate_decision                 # noqa: E402

conn = get_conn()
por_torneio, alvo_ids = {}, set()
for r in conn.execute("""
    SELECT id, tournament_id, hand_id, street, action_taken, label, gto_label
    FROM decisions ORDER BY id
"""):
    d = dict(r)
    por_torneio.setdefault(d['tournament_id'], {}).setdefault(str(d['hand_id']), []).append(d)
    if d['gto_label'] is None:
        alvo_ids.add(d['id'])

cont, acus = Counter(), Counter()
ACU = ('small_mistake', 'clear_mistake')

for tid, maos_gravadas in por_torneio.items():
    if not any(g['id'] in alvo_ids for lst in maos_gravadas.values() for g in lst):
        continue
    row = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
    if not row:
        continue
    try:
        maos = parse_hand_history(dict(row)['raw_text'])
    except Exception:                                                     # noqa: BLE001
        continue
    frescas_por_mao = {}
    for h in maos:
        try:
            for di in build_decision_inputs_for_hand(h):
                frescas_por_mao.setdefault(str(di.get('hand_id') or ''), []).append(di)
        except Exception:                                                 # noqa: BLE001
            continue

    for hid, gravadas in maos_gravadas.items():
        n_alvo = sum(1 for g in gravadas if g['id'] in alvo_ids)
        if not n_alvo:
            continue
        frescas = frescas_por_mao.get(hid, [])
        if len(frescas) != len(gravadas):
            cont['(mao pulada: tamanho diferente)'] += n_alvo
            continue
        if any((g['action_taken'] or '').lower() != (f.get('player_action') or '').lower()
               for g, f in zip(gravadas, frescas)):
            cont['(mao pulada: acao desalinhada)'] += n_alvo
            continue
        for g, di in zip(gravadas, frescas):
            if g['id'] not in alvo_ids:
                continue
            try:
                r = evaluate_decision(di)
            except Exception as e:                                        # noqa: BLE001
                cont['(erro %s)' % type(e).__name__] += 1
                continue
            street = (g['street'] or '').lower()
            if street == 'preflop':
                motivo = r.get('preflop_coverage_reason') or (
                    'COBERTO agora' if r.get('preflop_gto') else '(sem motivo declarado)')
            else:
                motivo = r.get('gto_coverage_reason') or (
                    'COBERTO agora' if (r.get('gto') or {}).get('available')
                    else '(sem motivo declarado)')
            chave = '%-8s %s' % (street, motivo)
            cont[chave] += 1
            if g['label'] in ACU:
                acus[chave] += 1
conn.close()

print('decisoes sem gto_label: %d' % sum(cont.values()))
print('\n%-56s %6s %10s' % ('street / motivo declarado', 'total', 'acusacoes'))
for k, v in cont.most_common():
    print('%-56s %6d %10d' % (k[:56], v, acus.get(k, 0)))
print('\nACUSACOES sem nenhuma cobertura GTO: %d' % sum(acus.values()))
