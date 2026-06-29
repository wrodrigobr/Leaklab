"""Spike de MEDIÇÃO (não muda produto): qual fatia das decisões multiway postflop
cai na "cauda provavelmente-segura" — onde o veredito é estável o bastante pra ser
GRADEADO (contar na cobertura/ELO/study) sem risco de punir jogada defensável.

Não existe gabarito multiway (solver é HU-only). Então "seguro" aqui = o veredito
SOBREVIVE ao canto adversário das nossas premissas (range do vilão e realization
tax), com folga maior que o ruído do Monte Carlo:

  SAFE_FOLD  (continuar = leak):  hero está priced-out MESMO assumindo o vilão na
             range mais LARGA/fraca (equity do hero no MÁXIMO) e tax=0.
  SAFE_VALUE (bet/raise claro):   hero é valor claro MESMO assumindo o vilão na
             range mais APERTADA/forte (equity do hero no MÍNIMO).
  Resto (inclui todo CALL marginal): fica INFORMATIVO (uncovered), como hoje.

Cruza com a ação real do hero pra estimar quantos VIRARIAM erro gradeado.
Mede só; não escreve nada. Uso:
  python scripts/audit_multiway_safety.py [--prod] [--sims N] [--limit N]
"""
from __future__ import annotations
import os, sys, json, math, random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if '--prod' in sys.argv:
    try:
        from dotenv import load_dotenv; load_dotenv()
    except ImportError:
        pass
    if not os.environ.get('DATABASE_URL'):
        sys.exit("ERRO: --prod requer DATABASE_URL.")
else:
    os.environ.pop('DATABASE_URL', None)

try:
    import eval7
except Exception:
    sys.exit("ERRO: eval7 ausente (pip install eval7).")

from leaklab.draw_detector import detect_draws
from leaklab.multiway_advisor import advise_multiway, norm_action
from leaklab.hand_state_builder import _is_in_position
from database.schema import get_conn

STREET_N = {'flop': 3, 'turn': 4, 'river': 5}

# Mesmos thresholds do advisor de produto (espelhados aqui só pra leitura).
STRONG = 0.62
FOLD_MARGIN = 0.03
K_NOISE = 2.0   # folga em desvios-padrão do Monte Carlo

# Três tiers de range de CONTINUAÇÃO do vilão → envelope da equity do hero.
#   loose  = vilão continua larguíssimo  → equity do hero no MÁXIMO (hostil ao fold)
#   tight  = vilão continua só forte      → equity do hero no MÍNIMO (hostil ao valor)
_R_LOOSE = ("22+,A2s+,K2s+,Q2s+,J2s+,T4s+,95s+,84s+,73s+,63s+,52s+,42s+,32s,"
            "A2o+,K4o+,Q6o+,J7o+,T7o+,96o+,86o+,75o+,64o+,53o+,43o")
_R_TIGHT = "66+,A9s+,KTs+,QTs+,JTs,T9s,98s,AJo+,KQo"


def _cs(c) -> str:
    return str(c)


def _combos(board, range_str, tight_filter, dead):
    """Combos da range que CONTINUAM no board, fora das cartas mortas.
      tight_filter=False: continua com par+ OU draw (igual ao produto).
      tight_filter=True : só two-pair+ OU draw forte (flush/oesd) — vilão apertado."""
    bset = set(board)
    bcards = [eval7.Card(c) for c in board]
    out = []
    for hand, _w in eval7.HandRange(range_str).hands:
        c1, c2 = hand
        s1, s2 = _cs(c1), _cs(c2)
        if s1 in bset or s2 in bset or s1 in dead or s2 in dead:
            continue
        score = eval7.evaluate([c1, c2] + bcards)
        ht = eval7.handtype(score)
        dp = detect_draws(s1 + s2, board)
        if tight_filter:
            made_ok = ht not in ('High Card', 'Pair')          # two-pair+
            draw_ok = dp.flush_draw or dp.oesd                  # draw forte
        else:
            made_ok = ht != 'High Card'                          # par+
            draw_ok = dp.flush_draw or dp.oesd or dp.gutshot
        if made_ok or draw_ok:
            out.append((c1, c2))
    return out


def _equity(hero_str, board, n_opp, combos, n_sims, seed):
    """Equity Monte Carlo do hero vs n_opp amostrados de `combos`, completando o
    board até o river. Espelha multiway_advisor._equity_vs_field. Retorna (eq, trials)."""
    if not combos or n_opp < 1:
        return None, 0
    rng = random.Random(seed)
    hero = [eval7.Card(hero_str[0:2]), eval7.Card(hero_str[2:4])]
    bcards = [eval7.Card(c) for c in board]
    dead = set(_cs(c) for c in hero + bcards)
    combos = [hc for hc in combos if _cs(hc[0]) not in dead and _cs(hc[1]) not in dead]
    if not combos:
        return None, 0
    full = eval7.Deck().cards
    need = 5 - len(bcards)
    win = tie = 0.0
    trials = 0
    for _ in range(n_sims):
        used = set(dead); opps = []; ok = True
        for _i in range(n_opp):
            pick = None
            for _try in range(40):
                cand = combos[rng.randrange(len(combos))]
                a, b = _cs(cand[0]), _cs(cand[1])
                if a not in used and b not in used:
                    pick = cand; used.add(a); used.add(b); break
            if pick is None:
                ok = False; break
            opps.append(pick)
        if not ok:
            continue
        avail = [c for c in full if _cs(c) not in used]
        run = rng.sample(avail, need) if need > 0 else []
        fb = bcards + run
        hs = eval7.evaluate(hero + fb)
        scores = [eval7.evaluate(list(o) + fb) for o in opps]
        best = max([hs] + scores)
        if hs == best:
            k = 1 + sum(1 for s in scores if s == best)
            win += 1 if k == 1 else 0
            tie += 0 if k == 1 else 1.0 / k
        trials += 1
    if trials == 0:
        return None, 0
    return (win + tie) / trials, trials


def _noise(eq, trials):
    if not trials:
        return 1.0
    return math.sqrt(max(eq * (1 - eq), 1e-6) / trials)


def classify(hero, board, n_opp, pot_bb, to_call_bb, seed, n_sims):
    """Retorna (bucket, detalhe). bucket ∈ {safe_fold, safe_value, informative, n/a}."""
    facing = (to_call_bb or 0) > 0
    required = (to_call_bb / (pot_bb + to_call_bb)) if (facing and (pot_bb + to_call_bb) > 0) else None
    dead = set()
    # canto hostil ao FOLD: vilão larguíssimo (equity do hero no MÁXIMO) + tax=0
    cl = _combos(board, _R_LOOSE, False, dead)
    eq_hi, t_hi = _equity(hero, board, n_opp, cl, n_sims, seed)
    # canto hostil ao VALOR: vilão apertadíssimo (equity do hero no MÍNIMO)
    ct = _combos(board, _R_TIGHT, True, dead)
    eq_lo, t_lo = _equity(hero, board, n_opp, ct, n_sims, seed + 1)
    if eq_hi is None or eq_lo is None:
        return 'n/a', {}
    nz_hi = _noise(eq_hi, t_hi); nz_lo = _noise(eq_lo, t_lo)

    # SAFE_FOLD: mesmo no melhor caso pra continuar (eq_hi + ruído, tax=0), priced-out.
    if facing and required is not None:
        if eq_hi + K_NOISE * nz_hi < required - FOLD_MARGIN:
            return 'safe_fold', {'eq_hi': eq_hi, 'req': required}
    # SAFE_VALUE: mesmo no pior caso (eq_lo − ruído) ainda é valor claro.
    if eq_lo - K_NOISE * nz_lo >= STRONG:
        # se enfrenta aposta, valor exige também estar acima das pot odds (trivial qdo eq_lo≥0.62)
        return 'safe_value', {'eq_lo': eq_lo}
    return 'informative', {'eq_hi': eq_hi, 'eq_lo': eq_lo, 'req': required}


def main():
    n_sims = 8000
    limit = None
    if '--sims' in sys.argv:
        n_sims = int(sys.argv[sys.argv.index('--sims') + 1])
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    conn = get_conn()
    rows = conn.execute(
        "SELECT id, hero_cards, board, pot_size, facing_bet, position, street, "
        "action_taken, n_active_opponents "
        "FROM decisions WHERE lower(street) IN ('flop','turn','river') "
        "AND n_active_opponents >= 2 "
        "AND hero_cards IS NOT NULL AND hero_cards != '' AND board IS NOT NULL"
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    if limit:
        rows = rows[:limit]

    buckets = {'safe_fold': [], 'safe_value': [], 'informative': [], 'n/a': []}
    base_clear = 0
    flips_to_error = 0   # safe-tail onde a ação real do hero contraria o veredito seguro

    for r in rows:
        hero = (r['hero_cards'] or '').replace(' ', '')
        if len(hero) != 4:
            buckets['n/a'].append(r['id']); continue
        try:
            full_board = json.loads(r['board']) if r['board'] else []
        except Exception:
            full_board = []
        st = (r['street'] or '').lower()
        nb = STREET_N.get(st, 5)
        board = [c for c in full_board[:nb]]
        if len(board) < 3:
            buckets['n/a'].append(r['id']); continue
        n_opp = int(r['n_active_opponents'] or 0)
        pot = float(r['pot_size'] or 0)
        facing = float(r['facing_bet']) if r['facing_bet'] is not None else 0.0
        ip = _is_in_position(r['position'] or '')
        seed = (hash((hero, tuple(board), n_opp)) & 0x7FFFFFFF)

        # verdito-base do advisor de produto (pra comparar is_clear rate)
        base = advise_multiway(hero, board, pot, facing, n_opp, is_in_position=ip,
                               street=st, n_sims=4000)
        if base and base.get('is_clear'):
            base_clear += 1

        bucket, det = classify(hero, board, n_opp, pot, facing, seed, n_sims)
        buckets[bucket].append(r['id'])

        # cruza com a ação real: na cauda segura, o hero contrariou?
        act = norm_action(r['action_taken'])
        if bucket == 'safe_fold' and act in ('call', 'raise', 'bet', 'allin'):
            flips_to_error += 1
        elif bucket == 'safe_value' and act in ('check', 'fold'):
            flips_to_error += 1

    n = len(rows)
    pct = lambda k: (100.0 * len(buckets[k]) / n) if n else 0.0
    src = 'PROD' if '--prod' in sys.argv else 'DEV'
    print('=' * 68)
    print(f'AUDIT MULTIWAY — cauda segura pra gradear ({src}, sims={n_sims})')
    print('=' * 68)
    print(f'decisões multiway postflop:        {n}')
    print(f'  advisor is_clear (hoje):         {base_clear} ({100.0*base_clear/n if n else 0:.1f}%)')
    print('-' * 68)
    print(f'  SAFE_FOLD  (continuar = leak):   {len(buckets["safe_fold"]):4d} ({pct("safe_fold"):.1f}%)')
    print(f'  SAFE_VALUE (bet/raise claro):    {len(buckets["safe_value"]):4d} ({pct("safe_value"):.1f}%)')
    print(f'  → CAUDA SEGURA (gradeável):      {len(buckets["safe_fold"])+len(buckets["safe_value"]):4d} '
          f'({pct("safe_fold")+pct("safe_value"):.1f}%)')
    print(f'  informativo (fica uncovered):    {len(buckets["informative"]):4d} ({pct("informative"):.1f}%)')
    print(f'  n/a (sem eval/board curto):      {len(buckets["n/a"]):4d} ({pct("n/a"):.1f}%)')
    print('-' * 68)
    print(f'  na cauda segura, ação real do hero CONTRARIA o veredito: {flips_to_error}')
    print(f'    (≈ leaks multiway que passariam a ser flagrados com garantia)')
    print('=' * 68)
    print('Leitura: % CAUDA SEGURA = teto de ganho de cobertura SEM risco de')
    print('punir jogada defensável. O "informativo" é o meio ambíguo — sem gabarito,')
    print('NÃO gradear. Baixo % ⇒ #30 não compensa; alto % ⇒ vale, e já se sabe qual subset.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
