"""Validação EXAUSTIVA do veredito do Ghost Table.

Para CADA spot elegível a drill, roda CADA uma das 6 ações pela FONTE ÚNICA do veredito
(api.app.grade_drill_action) e checa invariantes de coerência. Reporta toda violação.
Não altera dados. Uso: python scripts/validate_drill_verdicts.py [--limit N] [--user U]
"""
import os, sys
os.environ.pop('DATABASE_URL', None)   # força SQLite local
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import get_decision_for_drill
from api.app import grade_drill_action, _norm_drill

ACTIONS = ['fold', 'check', 'call', 'bet', 'raise', 'jam']
VALID_TIERS = {'correct', 'deviation', 'error', 'uncovered'}

limit = None
for i, a in enumerate(sys.argv):
    if a == '--limit':
        limit = int(sys.argv[i + 1])

conn = get_conn()
q = ("SELECT d.id AS id, t.user_id AS user_id FROM decisions d "
     "JOIN tournaments t ON d.tournament_id = t.id "
     "WHERE d.gto_label IN ('gto_minor_deviation','gto_critical') "
     "AND d.gto_action IS NOT NULL AND d.gto_action != '' ORDER BY d.id")
spots = conn.execute(q).fetchall()
if limit:
    spots = spots[:limit]

viol = []          # (decision_id, action, descrição)
tiers = {}         # contagem por tier (todas as ações)
sources = {}       # contagem por validation_source (por spot)
n_spots = 0

for s in spots:
    row = get_decision_for_drill(s['user_id'], s['id'])
    if not row:
        continue
    n_spots += 1
    g = {a: grade_drill_action(row, a) for a in ACTIONS}
    g0 = g['fold']
    src = g0['validation_source']
    sources[src] = sources.get(src, 0) + 1
    best = g0['best_action']
    off = g0['gto_off_tree'] or g0['gto_multiway']
    freqs = g0['gto_freqs']
    street = (row.get('street') or '').lower()
    facing = float(row.get('facing_bet') or 0)

    for a in ACTIONS:
        t = g[a]['gto_tier']
        tiers[t] = tiers.get(t, 0) + 1
        if t not in VALID_TIERS:
            viol.append((s['id'], a, f"tier inválido: {t}"))

    # I1: best_action é uma das 6 ações
    if best not in ACTIONS:
        viol.append((s['id'], best, f"best_action fora das 6 ações: {best!r}"))

    if off:
        # I2: off-tree/multiway → TODA ação é uncovered (nunca grada a mão contra a range/HU)
        for a in ACTIONS:
            if g[a]['gto_tier'] != 'uncovered':
                viol.append((s['id'], a, f"off-tree/multiway mas tier={g[a]['gto_tier']} (esperado uncovered)"))
    else:
        # I3: jogar o best_action NÃO pode dar 'error' (a recomendação não pode ser erro)
        if best in ACTIONS and g[best]['gto_tier'] == 'error':
            viol.append((s['id'], best, f"best_action={best} gradeado ERROR (contradição recomenda↔veredito)"))
        # I4: a ação de MAIOR frequência GTO tem que ser 'correct'
        if freqs:
            topf = max(freqs, key=freqs.get)
            topn = _norm_drill(topf)
            if topn in ACTIONS and g[topn]['gto_tier'] != 'correct':
                viol.append((s['id'], topn, f"ação modal ({topn} {freqs[topf]:.0%}) tier={g[topn]['gto_tier']} (esperado correct)"))
        # I5: 'correct' só se top_match/equiv OU freq>=30% (princípio da indiferença)
        for a in ACTIONS:
            gv = g[a]
            if (gv['gto_tier'] == 'correct' and not gv['top_match'] and not gv['call_jam_equiv']
                    and gv['player_freq'] < 0.30):
                viol.append((s['id'], a, f"tier=correct mas freq={gv['player_freq']:.0%}<30% e não top/equiv"))

    # I6: coerência mesa↔opções — POSTFLOP com facing_bet=0 não pode ter best_action='fold'
    # (check é grátis). Preflop NÃO se aplica: foldar preflop é sempre válido (sem check grátis,
    # exceto BB), e facing_bet preflop costuma vir None.
    if street != 'preflop' and facing == 0 and best == 'fold':
        viol.append((s['id'], 'fold', "POSTFLOP facing_bet=0 mas best_action=fold (check é grátis — incoerência)"))

print(f"\n{'='*70}\nVALIDAÇÃO EXAUSTIVA — {n_spots} spots × {len(ACTIONS)} ações = {n_spots*len(ACTIONS)} vereditos\n{'='*70}")
print(f"\nCobertura (por spot): " + " · ".join(f"{k}={v}" for k, v in sorted(sources.items(), key=lambda x: -x[1])))
print(f"Vereditos (por ação): " + " · ".join(f"{k}={v}" for k, v in sorted(tiers.items(), key=lambda x: -x[1])))
print(f"\n{'VIOLAÇÕES: ' + str(len(viol)) if viol else '✅ ZERO violações — todos os vereditos coerentes'}")
for dec_id, act, desc in viol[:60]:
    print(f"  [dec {dec_id}] ação={act}: {desc}")
if len(viol) > 60:
    print(f"  ... +{len(viol)-60} (use o retorno pra ver todas)")
conn.close()
sys.exit(1 if viol else 0)
