"""Gate de ROBUSTEZ pra gradear multiway com garantia (#30, Fase 1 — shadow).

Não existe gabarito multiway (solver é HU-only), então NÃO dá pra provar que um
veredito multiway é GTO-correto. O que dá pra provar é que ele NUNCA pune jogada
defensável: o veredito tem que sobreviver ao CANTO ADVERSÁRIO das nossas premissas
(range de continuação do vilão no extremo + realization tax), com folga maior que o
ruído do Monte Carlo.

  SAFE_FOLD  (continuar = leak):  hero priced-out MESMO com o vilão na range mais
             LARGA/fraca (equity do hero no MÁXIMO) e tax=0.  → recommended='fold'
  SAFE_VALUE (bet/raise claro):   hero é valor claro MESMO com o vilão na range mais
             APERTADA/forte (equity do hero no MÍNIMO).        → recommended='bet'
  resto (inclui todo CALL marginal): 'informative' — fica uncovered, como hoje.

Determinístico por (hero, board, n_opp). Read-only/puro (sem efeitos colaterais).
Fonte ÚNICA: o audit (scripts/audit_multiway_safety.py) e o backfill importam daqui.
"""
from __future__ import annotations
import math
import os
import random

try:
    import eval7
    _HAS_EVAL7 = True
except Exception:  # pragma: no cover
    _HAS_EVAL7 = False

from leaklab.draw_detector import detect_draws

STREET_N = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}

# Thresholds espelham o multiway_advisor de produto (mesma régua de "valor claro").
STRONG = 0.62
FOLD_MARGIN = 0.03
K_NOISE = 2.0   # folga exigida, em desvios-padrão do Monte Carlo

# Tiers de range de CONTINUAÇÃO do vilão → envelope da equity do hero.
#   loose = vilão continua larguíssimo → equity do hero no MÁXIMO (hostil ao fold)
#   tight = vilão continua só forte     → equity do hero no MÍNIMO (hostil ao valor)
_R_LOOSE = ("22+,A2s+,K2s+,Q2s+,J2s+,T4s+,95s+,84s+,73s+,63s+,52s+,42s+,32s,"
            "A2o+,K4o+,Q6o+,J7o+,T7o+,96o+,86o+,75o+,64o+,53o+,43o")
_R_TIGHT = "66+,A9s+,KTs+,QTs+,JTs,T9s,98s,AJo+,KQo"


def _cs(c) -> str:
    return str(c)


def _combos(board, range_str, tight_filter, dead):
    """Combos da range que CONTINUAM no board, fora das cartas mortas.
      tight_filter=False: continua com par+ OU draw (igual ao multiway_advisor).
      tight_filter=True : só two-pair+ OU draw forte (flush/oesd) — vilão apertado."""
    bset = set(board)
    bcards = [eval7.Card(c) for c in board]
    out = []
    for hand, _w in eval7.HandRange(range_str).hands:
        c1, c2 = hand
        s1, s2 = _cs(c1), _cs(c2)
        if s1 in bset or s2 in bset or s1 in dead or s2 in dead:
            continue
        ht = eval7.handtype(eval7.evaluate([c1, c2] + bcards))
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
    board até o river. Espelha multiway_advisor._equity_vs_field. (eq, trials)."""
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


def _norm_board(board, street):
    """Fatia o board pela street (DB guarda board completo de propósito)."""
    n = STREET_N.get((street or '').lower(), len(board or []))
    return list((board or [])[:n])


def classify_safe(hero_cards, board, n_opponents, pot_bb, to_call_bb,
                  street='flop', n_sims=8000, seed=None):
    """Classifica um spot multiway na cauda segura ou não.

    Retorna dict:
      bucket      : 'safe_fold' | 'safe_value' | 'informative' | 'n/a'
      recommended : 'fold' | 'bet' | None   (ação garantida quando na cauda segura)
      eq_hi/eq_lo : envelope de equity (vilão larguíssimo / apertadíssimo)
      required_eq : pot odds (None quando não enfrenta aposta)
    bucket != safe_* ⇒ NÃO gradear (fica informativo/uncovered).
    """
    out = {'bucket': 'n/a', 'recommended': None, 'eq_hi': None,
           'eq_lo': None, 'required_eq': None}
    if not _HAS_EVAL7:
        return out
    hero = (hero_cards or '').replace(' ', '')
    if len(hero) != 4:
        return out
    b = _norm_board(board, street)
    if len(b) < 3:
        return out
    n_opp = int(n_opponents or 0)
    if n_opp < 2:
        return out  # HU tem o solver; só 2+ vilões é genuinamente multiway

    if seed is None:
        seed = (hash((hero, tuple(b), n_opp)) & 0x7FFFFFFF)
    facing = float(to_call_bb or 0) > 0
    pot = float(pot_bb or 0)
    call = float(to_call_bb or 0)
    required = (call / (pot + call)) if (facing and (pot + call) > 0) else None
    out['required_eq'] = round(required, 4) if required is not None else None

    # canto hostil ao FOLD: vilão larguíssimo (equity do hero no MÁXIMO) + tax=0
    eq_hi, t_hi = _equity(hero, b, n_opp, _combos(b, _R_LOOSE, False, set()),
                          n_sims, seed)
    # canto hostil ao VALOR: vilão apertadíssimo (equity do hero no MÍNIMO)
    eq_lo, t_lo = _equity(hero, b, n_opp, _combos(b, _R_TIGHT, True, set()),
                          n_sims, seed + 1)
    if eq_hi is None or eq_lo is None:
        return out
    out['eq_hi'] = round(eq_hi, 4)
    out['eq_lo'] = round(eq_lo, 4)

    # SAFE_FOLD: priced-out mesmo no melhor caso pra continuar.
    if facing and required is not None and \
            eq_hi + K_NOISE * _noise(eq_hi, t_hi) < required - FOLD_MARGIN:
        out['bucket'] = 'safe_fold'; out['recommended'] = 'fold'
        return out
    # SAFE_VALUE: valor claro mesmo no pior caso.
    if eq_lo - K_NOISE * _noise(eq_lo, t_lo) >= STRONG:
        out['bucket'] = 'safe_value'; out['recommended'] = 'bet'
        return out
    out['bucket'] = 'informative'
    return out


def grade_safe_tail_enabled() -> bool:
    """Fase 2: master switch. Lê o env em tempo de chamada (flip exige restart do
    container, igual TEXAS_HERO_IP; mas testes podem setar/limpar e ver o efeito)."""
    return os.environ.get('MULTIWAY_GRADE_SAFE_TAIL', '0') == '1'


def graded_safe_verdict(hero_cards, board, n_opponents, pot_bb, to_call_bb,
                        hero_action, street='flop', n_sims=6000):
    """Fase 2 — veredito GRADEADO da cauda segura, ou None.

    Devolve dict (bucket/recommended/is_leak/eq_hi/eq_lo/required_eq) SOMENTE quando:
      (a) a flag MULTIWAY_GRADE_SAFE_TAIL está on, E
      (b) o spot cai na cauda segura (safe_fold/safe_value).
    Senão None → o chamador mantém o comportamento informativo de hoje (uncovered/≈).
    `is_leak` = a ação do hero contraria o veredito garantido (continuar num safe_fold,
    passar num safe_value). Centraliza a checagem da flag p/ todas as superfícies."""
    if not grade_safe_tail_enabled():
        return None
    v = classify_safe(hero_cards, board, n_opponents, pot_bb, to_call_bb,
                      street=street, n_sims=n_sims)
    if v['bucket'] not in ('safe_fold', 'safe_value'):
        return None
    return {**v, 'is_leak': bool(is_safe_leak(v, hero_action))}


def is_safe_leak(verdict, hero_action):
    """Dado o veredito da cauda segura e a ação do hero, foi leak GARANTIDO?
    Só grada quando bucket é safe_*; None fora da cauda (defere ao informativo).
      safe_fold  → continuar (call/raise/bet/allin) é leak
      safe_value → passar (check/fold) é leak (não extrair valor claro)
    Retorna True (leak), False (ok) ou None (não-gradeável)."""
    if not verdict or verdict.get('bucket') not in ('safe_fold', 'safe_value'):
        return None
    h = (hero_action or '').strip().lower()
    h = h[:-1] if h.endswith('s') else h
    if h in ('all-in', 'allin', 'jam', 'shove'):
        h = 'allin'
    if verdict['bucket'] == 'safe_fold':
        return h in ('call', 'raise', 'bet', 'allin')
    return h in ('check', 'fold')   # safe_value
