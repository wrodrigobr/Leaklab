"""Backfill SHADOW da coluna decisions.multiway_safe_verdict (#30, Fase 1).

Calcula o gate de robustez (leaklab/multiway_safety.classify_safe) pra cada decisão
multiway postflop e grava 'safe_fold'/'safe_value' na coluna — ou NULL fora da cauda
segura. É SHADOW: nada no produto lê essa coluna ainda (cobertura/ELO/veredito intactos).
Serve pra acumular dados e validar (validate_multiway_safety.py) antes de ligar (Fase 2).

Escreve SÓ a coluna multiway_safe_verdict; não toca label/gto/score. Idempotente.
Uso: python scripts/backfill_multiway_safety.py [--prod] [--sims N] [--limit N]
"""
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

from database.schema import get_conn, USE_POSTGRES
from leaklab.multiway_safety import classify_safe, _HAS_EVAL7

if not _HAS_EVAL7:
    sys.exit("ERRO: eval7 ausente (pip install eval7).")


def main():
    n_sims = 8000
    limit = None
    if '--sims' in sys.argv:
        n_sims = int(sys.argv[sys.argv.index('--sims') + 1])
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    conn = get_conn()   # dispara _run_migrations → garante a coluna
    # PRAGMA é SQLite-only; no Postgres é SQL inválido e ABORTA a transação
    # (o try/except engole o erro Python mas deixa a conexão envenenada →
    # InFailedSqlTransaction no próximo SELECT). Só no SQLite local.
    if not USE_POSTGRES:
        try:
            conn.execute('PRAGMA busy_timeout=30000')
        except Exception:
            pass

    rows = conn.execute(
        "SELECT id, hero_cards, board, pot_size, facing_bet, street, "
        "n_active_opponents, multiway_safe_verdict "
        "FROM decisions WHERE lower(street) IN ('flop','turn','river') "
        "AND n_active_opponents >= 2 "
        "AND hero_cards IS NOT NULL AND hero_cards != '' AND board IS NOT NULL "
        "ORDER BY id"
    ).fetchall()
    rows = [dict(r) for r in rows]
    if limit:
        rows = rows[:limit]
    print(f"Processando {len(rows)} decisões multiway postflop (sims={n_sims})...")

    checked = updated = 0
    dist = {'safe_fold': 0, 'safe_value': 0, None: 0}
    for i, r in enumerate(rows):
        try:
            board = json.loads(r['board']) if r['board'] else []
        except Exception:
            board = []
        v = classify_safe(r['hero_cards'], board, int(r['n_active_opponents'] or 0),
                          float(r['pot_size'] or 0),
                          float(r['facing_bet']) if r['facing_bet'] is not None else 0.0,
                          street=(r['street'] or '').lower(), n_sims=n_sims)
        # grava só a cauda gradeável; resto = NULL (não-gradeável, fica informativo)
        new_val = v['bucket'] if v['bucket'] in ('safe_fold', 'safe_value') else None
        dist[new_val] = dist.get(new_val, 0) + 1
        checked += 1
        if r['multiway_safe_verdict'] != new_val:
            conn.execute("UPDATE decisions SET multiway_safe_verdict = ? WHERE id = ?",
                         (new_val, r['id']))
            updated += 1
        if (i + 1) % 50 == 0:
            conn.commit()
    conn.commit()
    conn.close()

    src = 'PROD' if '--prod' in sys.argv else 'DEV'
    print(f"\n[{src}] Concluído. Verificadas: {checked} | Atualizadas: {updated}")
    print(f"  safe_fold:  {dist.get('safe_fold', 0)}")
    print(f"  safe_value: {dist.get('safe_value', 0)}")
    print(f"  (NULL / não-gradeável): {dist.get(None, 0)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
