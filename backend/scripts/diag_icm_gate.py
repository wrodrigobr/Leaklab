"""Diagnóstico (read-only) do gate zona-ICM: lista mãos candidatas a disparar o gate
— hero FOLDA, o ChipEV manda CONTINUAR (best_action call/raise/shove) e o torneio está
em pressão de ICM alta. Serve pra abrir direto no Replayer e conferir o selo
"≈ Aproximação chipEV" (o gate real também exige mesa curta active<=6, aplicado ao vivo).

Uso:
  python scripts/diag_icm_gate.py [--prod] [--limit N]

Read-only; não escreve nada. Ver leaklab/verdict.py::icm_zone_softens_fold.
"""
from __future__ import annotations
import os, sys

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

from database.schema import get_conn
from leaklab.verdict import _ICM_CONTINUE_ACTIONS

limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 40


def main():
    conn = get_conn()
    # Candidatos: fold do hero + ChipEV manda continuar + zona-ICM alta. O filtro de mesa
    # curta (active<=6) o gate aplica AO VIVO; aqui deixamos passar pra mostrar ambos os
    # ramos (full-ring high-pressure segue "Erro"; mesa curta vira "≈ Aproximação").
    placeholders = ','.join('?' for _ in _ICM_CONTINUE_ACTIONS)
    rows = conn.execute(
        f"""
        SELECT t.tournament_id AS code, d.hand_id, d.street, d.position,
               d.action_taken, d.best_action, d.icm_pressure, d.n_active_opponents,
               d.label
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE lower(d.action_taken) = 'fold'
          AND lower(COALESCE(d.best_action,'')) IN ({placeholders})
          AND lower(COALESCE(d.icm_pressure,'')) = 'high'
        ORDER BY d.id DESC
        """,
        tuple(a for a in _ICM_CONTINUE_ACTIONS),
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows][:limit]

    print("=" * 78)
    print(f"DIAG GATE ZONA-ICM — candidatos (fold + best=continuar + icm=high): {len(rows)}")
    print("=" * 78)
    if not rows:
        print("Nenhum candidato no banco. (Precisa de torneios com folds em pressão ICM alta.)")
        return
    # nopp = n_active_opponents (oponentes na MÃO). O gate filtra por active_players
    # (assentos na MESA, <=6), que vem do contexto MTT ao vivo — não é esta coluna.
    print(f"{'torneio':>13}  {'mão':>13}  {'street':<6} {'pos':<4} "
          f"{'best':<6} {'icm':<5} {'nopp':<4} {'label':<13}  link")
    for r in rows:
        code, hid = r['code'], r['hand_id']
        link = f"/replayer?t={code}&h={hid}"
        print(f"{str(code):>13}  {str(hid):>13}  {(r['street'] or ''):<6} "
              f"{(r['position'] or ''):<4} {(r['best_action'] or ''):<6} "
              f"{(r['icm_pressure'] or ''):<5} {r['n_active_opponents'] if r['n_active_opponents'] is not None else '?':<4} "
              f"{(r['label'] or ''):<13}  {link}")
    print("-" * 78)
    print("Abra no Replayer: mesa curta (active<=6) → selo '≈ Aproximação chipEV';")
    print("full-ring (active>6) na mesma pressão → segue '✗ Erro' (leak real preservado).")


if __name__ == '__main__':
    main()
