# -*- coding: utf-8 -*-
"""v5 — as 235 contradições da v4 são BUG do painel ou informação que a grade não tem?

Hipótese: a grade é a range GENÉRICA de 9-max; o veredito conhece a MESA REAL (num_players,
mesa final, botão morto). Numa mesa de 5, 'UTG' é outra posição efetiva — a grade responde
outra pergunta, que é exatamente a família reportada pelo usuário.

Ablação: segmenta por num_players. Se as contradições se concentram em mesas != 9, a causa é
essa; se aparecem igualmente em mesa cheia, o defeito é outro.
"""
import sys
from collections import Counter, defaultdict

sys.path.insert(0, '/app')
from database.schema import get_conn
from database.repositories import _adapt
from leaklab.gto_utils import hand_to_type
from leaklab.preflop_gto_ranges import _load, _stack_bucket, _norm_pos, _expand_range

_DATA = _load()
_cache = {}


def grade(pos, stack):
    ck = (pos, _stack_bucket(stack))
    if ck not in _cache:
        bk = _DATA.get('ranges', {}).get(_stack_bucket(stack), {})
        raw = (bk.get('RFI') or {}).get(_norm_pos(pos)) or {}
        _cache[ck] = (_expand_range(raw.get('raise_hands', '')) | _expand_range(raw.get('allin_hands', ''))
                      if ('raise_hands' in raw or 'open_pct' in raw) else _expand_range(raw.get('hands', '')))
    return _cache[ck]


with get_conn() as conn:
    rows = conn.execute(_adapt(
        "SELECT position, stack_bb, hero_cards, gto_action, num_players, "
        "COALESCE(n_active_opponents, -1) AS nao, gto_label FROM decisions "
        "WHERE street = 'preflop' AND COALESCE(facing_bet,0) = 0 AND gto_action IS NOT NULL "
        "AND hero_cards IS NOT NULL AND hero_cards != '' AND position != 'BB'")).fetchall()

tot = defaultdict(int)
contra = defaultdict(int)
por_np = Counter()
exemplos_mesa_cheia = []
for r in rows:
    hc = r['hero_cards']
    ht = hand_to_type([hc[i:i + 2] for i in range(0, len(hc), 2)])
    if not ht:
        continue
    pos, stack = r['position'], float(r['stack_bb'] or 30)
    g = grade(pos, stack)
    if not g:
        continue
    np_ = int(r['num_players'] or 0)
    tot[np_] += 1
    abre = (r['gto_action'] or '').lower() in ('raise', 'allin', 'shove', 'jam')
    if (ht in g) != abre:
        contra[np_] += 1
        por_np[np_] += 1
        if np_ >= 9 and len(exemplos_mesa_cheia) < 10:
            exemplos_mesa_cheia.append((pos, _stack_bucket(stack), ht, r['gto_action'],
                                        'grade_tem' if ht in g else 'grade_nao_tem', r['gto_label']))

print('=== ABLAÇÃO POR TAMANHO DE MESA (num_players) ===')
print(f'{"mesa":>6} {"decisões":>10} {"contradições":>13} {"taxa":>8}')
for np_ in sorted(tot):
    t, c = tot[np_], contra.get(np_, 0)
    print(f'{np_:>6} {t:>10} {c:>13} {100*c/t:>7.1f}%')

print(f'\nTOTAL: {sum(contra.values())} de {sum(tot.values())} '
      f'({100*sum(contra.values())/max(1,sum(tot.values())):.1f}%)')
print('\nExemplos em MESA CHEIA (9+) — se houver, a causa NÃO é mesa curta:')
for e in exemplos_mesa_cheia:
    print('  ', e)
