"""
Precompute dos nós GTO de hero IP ENFRENTANDO APOSTA (postflop) — Fase 1 do fix.

Pré-requisitos: main.rs com navigate_to_ip_facing_bet deployado na VM + flags
TEXAS_HERO_IP=1 e TEXAS_HERO_IP_FACING=1. Varre os spots reais (hero IP, facing>0,
postflop) e SOLVA+GRAVA cada um (lookup_gto allow_remote_solve=True). Read-only no
/replay não solva, então sem isto o card continua heurístico.

facing: passa em BB (facingToBb) com bb_chips=1.0 — o hash usa o facing como vem
(BB, igual ao engine/replay) e _facing_solver_bb = facing/1 = BB (correto pro solver).

Resumível: faz um lookup read-only antes; se já tem nó, pula.
"""
import os, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env + flags
for line in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
os.environ['TEXAS_HERO_IP'] = '1'
os.environ['TEXAS_HERO_IP_FACING'] = '1'

import sqlite3
from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_solver import lookup_gto, _postflop_hero_is_ip

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
conn = sqlite3.connect(DB, timeout=30); conn.row_factory = sqlite3.Row
conn.execute('PRAGMA busy_timeout=30000')

trows = conn.execute("SELECT id, raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()

# 1. Coleta os spots únicos (hero IP, postflop, facing>0) — dedup por chave de spot.
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
            ftb = float(sp.get('facingToBb') or 0)
            pos = (sp.get('position') or '').upper()
            vs  = (sp.get('villainPosition') or '').upper()
            if ftb <= 0 or not vs or vs == 'UNKNOWN':
                continue
            if not _postflop_hero_is_ip(pos, vs):
                continue
            board = sp.get('board') or []
            nb = len([c for c in board if c])
            if nb != {'flop': 3, 'turn': 4, 'river': 5}.get(di['street'], -1):
                continue
            stack = float(sp.get('effectiveStackBb') or 0)
            if stack <= 0 or stack > 200:        # >200bb: heurístico (Opção B)
                continue
            key = (di['street'], pos, vs, tuple(board), tuple(di.get('hero_cards') or []),
                   round(stack), round(ftb, 1))
            if key not in spots:
                spots[key] = dict(street=di['street'], position=pos, board=board,
                                  hero_hand=di.get('hero_cards') or [], hero_stack_bb=stack,
                                  vs_position=vs, pot_bb=float(sp.get('potBb') or 0), facing=ftb)

print(f"Spots IP-facing-bet únicos: {len(spots)}")

# 2. Solva os que ainda não têm nó.
solved = skipped = failed = 0
t0 = time.time()
for i, (key, s) in enumerate(spots.items(), 1):
    common = dict(street=s['street'], position=s['position'], board=s['board'],
                  hero_hand=s['hero_hand'], hero_stack_bb=s['hero_stack_bb'],
                  vs_position=s['vs_position'], pot_bb=s['pot_bb'])
    # já coberto? (read-only)
    pre = lookup_gto(facing_size_bb=s['facing'], allow_remote_solve=False, block_remote=False, **common)
    if pre.get('found'):
        skipped += 1
        continue
    try:
        r = lookup_gto(facing_size_bb=s['facing'], bb_chips=1.0,
                       allow_remote_solve=True, block_remote=True, **common)
        if r.get('found') and r.get('strategy'):
            solved += 1
            print(f"  [{i}/{len(spots)}] OK  {s['street']} {s['position']}v{s['vs_position']} "
                  f"{''.join(s['hero_hand'])} vs {s['facing']:.1f}bb -> "
                  f"{[(x['action'], round(x['frequency'],2)) for x in r['strategy'][:4]]}")
        else:
            failed += 1
            print(f"  [{i}/{len(spots)}] FALHOU {s['street']} {s['position']}v{s['vs_position']} ({r.get('source')})")
    except Exception as e:
        failed += 1
        print(f"  [{i}/{len(spots)}] ERRO {e}")

conn.close()
print(f"\nConcluido em {time.time()-t0:.0f}s | solvados: {solved} | ja cobertos: {skipped} | falhas: {failed}")
