"""
Precompute dos nós GTO de pote 3-BET (Fase 2) — ranges corretas (3-bettor = vs_RFI.raise,
caller = vs_3bet.call) sob o hash 3bet-aware. Cobre c-bets + facing-bets, IP + OOP.

Pré-requisitos: flags TEXAS_HERO_IP=1 e TEXAS_HERO_IP_FACING=1 + binário IP-facing na VM.
Não faz pre-check read-only (o lookup_gto auto-pula nós 3bet já solvados e, com
allow_remote_solve=True, NÃO cai no fallback SRP — solva o nó 3bet de verdade).

facing em BB (facingToBb) + bb_chips=1.0 (igual Fase 1).
"""
import os, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for line in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
os.environ['TEXAS_HERO_IP'] = '1'
os.environ['TEXAS_HERO_IP_FACING'] = '1'

import sqlite3
from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_solver import lookup_gto

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
conn = sqlite3.connect(DB, timeout=30); conn.row_factory = sqlite3.Row
conn.execute('PRAGMA busy_timeout=30000')
trows = conn.execute("SELECT raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()

# Coleta spots postflop de POTE 3-BET (dedup).
spots = {}
for tr in trows:
    try:
        hands = parse_pokerstars_file_from_text(tr['raw_text'])
    except Exception:
        continue
    for h in hands:
        for di in build_decision_inputs_for_hand(h):
            if di['street'] == 'preflop':
                continue
            sp = di['spot']
            if (sp.get('potType') or '') != '3bet':
                continue
            vs = (sp.get('villainPosition') or '').upper()
            if not vs or vs == 'UNKNOWN':
                continue
            board = sp.get('board') or []
            nb = len([c for c in board if c])
            if nb != {'flop': 3, 'turn': 4, 'river': 5}.get(di['street'], -1):
                continue
            stack = float(sp.get('effectiveStackBb') or 0)
            if stack <= 0 or stack > 200:
                continue
            ftb = float(sp.get('facingToBb') or 0)
            key = (di['street'], (sp.get('position') or '').upper(), vs, tuple(board),
                   tuple(di.get('hero_cards') or []), round(stack), round(ftb, 1))
            if key not in spots:
                spots[key] = dict(street=di['street'], position=(sp.get('position') or '').upper(),
                                  board=board, hero_hand=di.get('hero_cards') or [], hero_stack_bb=stack,
                                  vs_position=vs, pot_bb=float(sp.get('potBb') or 0), facing=ftb,
                                  opener=sp.get('preflopOpener', ''), threebettor=sp.get('preflop3bettor', ''))

print(f"Spots postflop de pote 3-bet únicos: {len(spots)}")
solved = skipped = failed = 0
t0 = time.time()
for i, (key, s) in enumerate(spots.items(), 1):
    try:
        r = lookup_gto(street=s['street'], position=s['position'], board=s['board'],
                       hero_hand=s['hero_hand'], hero_stack_bb=s['hero_stack_bb'],
                       vs_position=s['vs_position'], pot_bb=s['pot_bb'],
                       facing_size_bb=s['facing'], bb_chips=1.0,
                       pot_type='3bet', opener=s['opener'], threebettor=s['threebettor'],
                       allow_remote_solve=True, block_remote=True)
        src = r.get('source')
        if r.get('found') and r.get('strategy'):
            if src == 'remote_solver':
                solved += 1
            else:
                skipped += 1   # nó 3bet já existia
            print(f"  [{i}/{len(spots)}] {src:14s} {s['street']} {s['position']}v{s['vs_position']} "
                  f"{''.join(s['hero_hand'])} f={s['facing']:.1f} -> "
                  f"{[(x['action'], round(x['frequency'],2)) for x in r['strategy'][:4]]}")
        else:
            failed += 1
            print(f"  [{i}/{len(spots)}] FALHOU ({src})")
    except Exception as e:
        failed += 1
        print(f"  [{i}/{len(spots)}] ERRO {e}")

conn.close()
print(f"\nConcluido em {time.time()-t0:.0f}s | solvados: {solved} | ja 3bet: {skipped} | falhas: {failed}")
