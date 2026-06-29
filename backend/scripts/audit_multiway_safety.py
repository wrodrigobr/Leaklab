"""Spike de MEDIÇÃO (não muda produto): qual fatia das decisões multiway postflop
cai na "cauda provavelmente-segura" — onde o veredito é estável o bastante pra ser
GRADEADO (contar na cobertura/ELO/study) sem risco de punir jogada defensável.

A lógica do gate vive em leaklab/multiway_safety.classify_safe (fonte única). Aqui
só varremos as decisões reais e bucketizamos. Read-only; não escreve nada. Uso:
  python scripts/audit_multiway_safety.py [--prod] [--sims N] [--limit N]
"""
from __future__ import annotations
import os, sys, json

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

from leaklab.multiway_safety import classify_safe, is_safe_leak, _HAS_EVAL7
from leaklab.multiway_advisor import advise_multiway
from leaklab.hand_state_builder import _is_in_position
from database.schema import get_conn

if not _HAS_EVAL7:
    sys.exit("ERRO: eval7 ausente (pip install eval7).")

STREET_N = {'flop': 3, 'turn': 4, 'river': 5}


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

    buckets = {'safe_fold': 0, 'safe_value': 0, 'informative': 0, 'n/a': 0}
    base_clear = 0
    flips_to_error = 0

    for r in rows:
        try:
            full_board = json.loads(r['board']) if r['board'] else []
        except Exception:
            full_board = []
        st = (r['street'] or '').lower()
        pot = float(r['pot_size'] or 0)
        facing = float(r['facing_bet']) if r['facing_bet'] is not None else 0.0
        n_opp = int(r['n_active_opponents'] or 0)

        v = classify_safe(r['hero_cards'], full_board, n_opp, pot, facing,
                          street=st, n_sims=n_sims)
        buckets[v['bucket']] = buckets.get(v['bucket'], 0) + 1

        # comparação: o advisor de produto acha "clear"? (board já fatiado lá dentro)
        board = full_board[:STREET_N.get(st, 5)]
        if len(board) >= 3:
            ip = _is_in_position(r['position'] or '')
            base = advise_multiway(r['hero_cards'], board, pot, facing, n_opp,
                                   is_in_position=ip, street=st, n_sims=4000)
            if base and base.get('is_clear'):
                base_clear += 1

        if is_safe_leak(v, r['action_taken']):
            flips_to_error += 1

    n = len(rows)
    pct = lambda k: (100.0 * buckets[k] / n) if n else 0.0
    safe = buckets['safe_fold'] + buckets['safe_value']
    src = 'PROD' if '--prod' in sys.argv else 'DEV'
    print('=' * 68)
    print(f'AUDIT MULTIWAY — cauda segura pra gradear ({src}, sims={n_sims})')
    print('=' * 68)
    print(f'decisões multiway postflop:        {n}')
    print(f'  advisor is_clear (hoje):         {base_clear} ({100.0*base_clear/n if n else 0:.1f}%)')
    print('-' * 68)
    print(f'  SAFE_FOLD  (continuar = leak):   {buckets["safe_fold"]:4d} ({pct("safe_fold"):.1f}%)')
    print(f'  SAFE_VALUE (bet/raise claro):    {buckets["safe_value"]:4d} ({pct("safe_value"):.1f}%)')
    print(f'  → CAUDA SEGURA (gradeável):      {safe:4d} ({pct("safe_fold")+pct("safe_value"):.1f}%)')
    print(f'  informativo (fica uncovered):    {buckets["informative"]:4d} ({pct("informative"):.1f}%)')
    print(f'  n/a (sem eval/board curto):      {buckets["n/a"]:4d} ({pct("n/a"):.1f}%)')
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
