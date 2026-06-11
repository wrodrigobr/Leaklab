"""
Campanha de precompute ISOMÓRFICA — item 2 do plano pós-solver
(specs/solver-improvement-plan.md). Roda na SUA máquina (precisa do DB dev +
VM do solver acessível).

A Fase 1 (tree_hash + isomorfismo) mudou a economia do precompute: cada solve
agora serve TODOS os spots da mesma classe de árvore (board isomorfo × qualquer
mão do hero). Este script varre as decisões reais, agrupa os spots postflop por
classe isomórfica e solva 1 representante por classe — ordenado por quantos
spots reais cada solve cobre (maior cobertura por CFR primeiro; empate: street
barata primeiro). O dedup do lookup_gto faz o resto: classes já solvadas viram
cópia instantânea ('tree_cache'), nós existentes são pulados.

Cada solve novo também grava a tabela POR MÃO (gto_tree_strategies) → veredito
hand-aware + ev_loss_bb para todos os spots da classe (Fase 3).

Uso:
  python scripts/precompute_tree_campaign.py --dry-run     # só lista as classes
  python scripts/precompute_tree_campaign.py               # solva tudo
  python scripts/precompute_tree_campaign.py --limit 50    # primeiras 50 classes

Resumível: rode de novo a qualquer momento — cobertos são pulados.
Ao final, rode scripts/reanalyze_all_labels.py para atualizar os labels.
"""
import os, sys, time, argparse
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
from leaklab.gto_solver import lookup_gto, _postflop_hero_is_ip, _effective_pot_type
from leaklab.gto_utils import canonical_board_key, stack_bucket, bet_bucket

ap = argparse.ArgumentParser()
ap.add_argument('--dry-run', action='store_true')
ap.add_argument('--limit', type=int, default=0)
args = ap.parse_args()

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
# read-only: este script só LÊ tournaments (as escritas do solve passam pelo
# repositories, com conexões próprias) — e ro evita lock contra o app.py vivo.
conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True, timeout=30)
conn.row_factory = sqlite3.Row
trows = conn.execute(
    "SELECT id, raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
).fetchall()
conn.close()

_STREET_N = {'flop': 3, 'turn': 4, 'river': 5}
_SJF      = {'river': 0, 'turn': 1, 'flop': 2}   # empate: street barata primeiro

# 1. Coleta + agrupa por CLASSE DE ÁRVORE isomórfica
classes: dict = {}   # key -> {'rep': spot_dict, 'count': n}
total_spots = 0
for tr in trows:
    try:
        hands = parse_pokerstars_file_from_text(tr['raw_text'])
    except Exception:
        continue
    for h in hands:
        for di in build_decision_inputs_for_hand(h):
            if di['street'] == 'preflop':
                continue
            sp    = di['spot']
            pos   = (sp.get('position') or '').upper()
            vs    = (sp.get('villainPosition') or '').upper()
            board = sp.get('board') or []
            stack = float(sp.get('effectiveStackBb') or 0)
            ftb   = float(sp.get('facingToBb') or 0)
            if not vs or vs == 'UNKNOWN':
                continue
            if len([c for c in board if c]) != _STREET_N.get(di['street'], -1):
                continue
            if stack <= 0 or stack > 200:
                continue
            total_spots += 1
            eff_pot = _effective_pot_type(sp.get('potType', ''), sp.get('preflopOpener', ''),
                                          sp.get('preflop3bettor', ''), stack)
            key = (di['street'], canonical_board_key(board), pos, vs,
                   stack_bucket(stack), bet_bucket(ftb), eff_pot,
                   round(float(sp.get('potBb') or 0), 1))
            c = classes.get(key)
            if c:
                c['count'] += 1
            else:
                classes[key] = {'count': 1, 'rep': dict(
                    street=di['street'], position=pos, board=board,
                    hero_hand=di.get('hero_cards') or [], hero_stack_bb=stack,
                    vs_position=vs, pot_bb=float(sp.get('potBb') or 0), facing=ftb,
                    pot_type=sp.get('potType', ''), opener=sp.get('preflopOpener', ''),
                    threebettor=sp.get('preflop3bettor', ''))}

ordered = sorted(classes.items(),
                 key=lambda kv: (-kv[1]['count'], _SJF.get(kv[0][0], 3)))
if args.limit:
    ordered = ordered[:args.limit]
print(f"Spots postflop reais: {total_spots} | classes isomórficas: {len(classes)} "
      f"({total_spots/max(1,len(classes)):.1f} spots/classe)")

if args.dry_run:
    for i, (key, c) in enumerate(ordered[:40], 1):
        print(f"  {i:3d}. x{c['count']:<3d} {key[0]:<5s} {key[2]}v{key[3]} "
              f"board={key[1]} stack={key[4]} facing={key[5]} pot_type={key[6] or 'srp'}")
    if len(ordered) > 40:
        print(f"  ... +{len(ordered)-40} classes")
    sys.exit(0)

# 2. Solva 1 representante por classe (dedup/cópia automáticos via tree_hash)
solved = copied = already = failed = 0
t0 = time.time()
for i, (key, c) in enumerate(ordered, 1):
    s = c['rep']
    common = dict(street=s['street'], position=s['position'], board=s['board'],
                  hero_hand=s['hero_hand'], hero_stack_bb=s['hero_stack_bb'],
                  vs_position=s['vs_position'], pot_bb=s['pot_bb'],
                  pot_type=s.get('pot_type', ''), opener=s.get('opener', ''),
                  threebettor=s.get('threebettor', ''))
    pre = lookup_gto(facing_size_bb=s['facing'], bb_chips=1.0,
                     allow_remote_solve=False, block_remote=False, **common)
    if pre.get('found'):
        already += 1
        continue
    try:
        r = lookup_gto(facing_size_bb=s['facing'], bb_chips=1.0,
                       allow_remote_solve=True, block_remote=True, **common)
        src = r.get('source')
        if r.get('found') and src == 'tree_cache':
            copied += 1
            print(f"  [{i}/{len(ordered)}] COPIA x{c['count']} {s['street']} "
                  f"{s['position']}v{s['vs_position']}")
        elif r.get('found') and r.get('strategy'):
            solved += 1
            print(f"  [{i}/{len(ordered)}] SOLVE x{c['count']} {s['street']} "
                  f"{s['position']}v{s['vs_position']} stack={s['hero_stack_bb']:.0f}bb -> "
                  f"{[(x['action'], round(x['frequency'],2)) for x in r['strategy'][:3]]}")
        else:
            failed += 1
            print(f"  [{i}/{len(ordered)}] SEM-COBERTURA {s['street']} "
                  f"{s['position']}v{s['vs_position']} ({src})")
    except Exception as e:
        failed += 1
        print(f"  [{i}/{len(ordered)}] ERRO {e}")

print(f"\nConcluído em {(time.time()-t0)/60:.1f}min | solves novos: {solved} | "
      f"cópias (dedup): {copied} | já cobertos: {already} | sem cobertura/falha: {failed}")
print("Agora rode: python scripts/reanalyze_all_labels.py")
