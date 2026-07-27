"""
Limpa `decisions.icm_tax_pct` gravado quando a mesa NÃO era o torneio.

Por que existe: até 2026-07-27 o ICM real era calculado sempre que a mesa tinha de 2 a 9
assentos — o que, num MTT 9-max, é toda mão. A equity de premiação era computada tratando os
stacks visíveis como o torneio inteiro, então com centenas de jogadores vivos o número é ficção.
O gate foi corrigido (exige `field_size` provando torneio de mesa única), mas as linhas já
gravadas continuam no banco.

Por que isso não é cosmético: `icm_tax_pct` é lido pelo **detector de cegueira ICM** do mapa de
falhas cognitivas. Deixar os valores antigos é seguir acusando o jogador de erro de ICM com base
num número que nunca descreveu a mesa dele.

Critério (o mesmo do gate novo): mantém só onde o torneio tem `field_size` conhecido e ≤ 9.
Sem `field_size` também limpa — é a escolha conservadora: sem prova, não afirmamos. Se o resumo
(arquivo TS) for enviado depois, `backfill_icm_tax.py` repõe o valor para os que se qualificarem.

Uso (dry-run por padrão — nada é alterado sem --apply):
    cd ~/app && docker compose exec web python -m scripts.clear_bogus_icm_tax
    cd ~/app && docker compose exec web python -m scripts.clear_bogus_icm_tax --apply
"""
import sys, os, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _adapt
from leaklab.mtt_context import _ICM_MAX_PLAYERS


def _v(row, key, idx=0):
    """Nome primeiro, posição como fallback: em PG a linha é dict (`row[0]` → KeyError: 0)."""
    try:
        return row[key]
    except Exception:
        return row[idx]


# "Manter" = torneio PROVADAMENTE de mesa única. Todo o resto perde o valor.
_MANTER = f"(t.field_size IS NOT NULL AND t.field_size BETWEEN 2 AND {_ICM_MAX_PLAYERS})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='executa (sem isto, só relata)')
    args = ap.parse_args()

    conn = get_conn()
    try:
        tot = _v(conn.execute(_adapt(
            "SELECT COUNT(*) AS n FROM decisions WHERE icm_tax_pct IS NOT NULL")).fetchone(), 'n')

        manter = _v(conn.execute(_adapt(f"""
            SELECT COUNT(*) AS n FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.icm_tax_pct IS NOT NULL AND {_MANTER}
        """)).fetchone(), 'n')

        print(f"decisões com icm_tax_pct gravado : {tot}")
        print(f"  mantidas (mesa única provada)  : {manter}")
        print(f"  a limpar (mesa ≠ torneio)      : {tot - manter}")

        if tot - manter == 0:
            print("\nNada a fazer.")
            return

        # Amostra, para conferir antes de aplicar. Só COUNT e colunas cruas de propósito:
        # ROUND(AVG(...)) exigiria cast diferente em PG e SQLite, e query que só quebra em
        # produção é como este projeto perdeu tardes.
        print("\namostra do que será limpo (por torneio):")
        for r in conn.execute(_adapt(f"""
            SELECT t.tournament_id AS tid, t.field_size AS fs, COUNT(*) AS n
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.icm_tax_pct IS NOT NULL AND NOT {_MANTER}
            GROUP BY t.tournament_id, t.field_size
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """)):
            fs = _v(r, 'fs', 1)
            print(f"  torneio {_v(r,'tid',0)}  inscritos={fs if fs is not None else 'desconhecido'}"
                  f"  decisões={_v(r,'n',2)}")

        if not args.apply:
            print("\n(dry-run — nada foi alterado. Rode com --apply para executar.)")
            return

        cur = conn.execute(_adapt(f"""
            UPDATE decisions SET icm_tax_pct = NULL
            WHERE icm_tax_pct IS NOT NULL
              AND tournament_id IN (
                  SELECT t.id FROM tournaments t WHERE NOT {_MANTER}
              )
        """))
        n = cur.rowcount or 0
        conn.commit()
        print(f"\n✔ limpas {n} decisões. O detector de cegueira ICM deixa de usá-las.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
