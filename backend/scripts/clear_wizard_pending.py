"""Limpa as marcas `gto_label='wizard_pending'` que ficaram órfãs no banco.

Contexto: `wizard_pending` marcava spots que o solver local não cobre, para caírem no fallback
do GTO Wizard. O GW foi DESCONTINUADO e só resolvia HU, então esses spots não têm para onde ir.
A função que criava as marcas já está aposentada (`_mark_failed_solver_jobs_as_wizard_pending`,
no-op), mas as linhas criadas antes disso continuaram no banco — e faziam o dashboard anunciar
"N spots ainda sendo validados pelo solver" para sempre, enquanto o painel do admin mostrava a
fila real vazia.

O estado honesto para esses spots é `gto_label = NULL` ("sem cobertura"), que é exatamente o que
o comentário do worker declara como correto. Isto aqui é uma reclassificação de rótulo, não uma
purga: nenhuma decisão é apagada, nenhum outro campo é tocado.

Uso (dentro de backend/):
    python -m scripts.clear_wizard_pending                 # dry-run: só relata
    python -m scripts.clear_wizard_pending --apply         # aplica
    cd ~/app && docker compose exec web python -m scripts.clear_wizard_pending --apply
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn


def main():
    aplicar = '--apply' in sys.argv
    conn = get_conn()
    try:
        from database import schema as _sch
        print(f"banco: {'PostgreSQL' if getattr(_sch, 'USE_POSTGRES', False) else _sch.SQLITE_PATH}\n")

        total = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE gto_label = 'wizard_pending'").fetchone()[0]
        if not total:
            print("Nada a fazer: nenhuma decisão com wizard_pending.")
            return

        por_user = conn.execute("""
            SELECT t.user_id, COUNT(*) AS n
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.gto_label = 'wizard_pending'
            GROUP BY t.user_id ORDER BY n DESC
        """).fetchall()
        print(f"{total} decisão(ões) marcadas como wizard_pending:")
        for r in por_user:
            print(f"   user {r[0]:>5} → {r[1]} spot(s) (era o número que o dashboard exibia)")

        if not aplicar:
            print("\nDRY-RUN. Nada foi alterado. Rode com --apply para reclassificar como "
                  "'sem cobertura' (gto_label = NULL).")
            return

        cur = conn.execute("UPDATE decisions SET gto_label = NULL WHERE gto_label = 'wizard_pending'")
        conn.commit()
        restante = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE gto_label = 'wizard_pending'").fetchone()[0]
        print(f"\n✔ {getattr(cur, 'rowcount', total)} reclassificadas para NULL (sem cobertura). "
              f"Restam {restante}.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
