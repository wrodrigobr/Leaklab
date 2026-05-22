"""
audit_label_coherence.py — Auditoria de coerência entre `label` (heurístico) e
`gto_label` (GTO). Diagnóstico read-only do item #2 do backlog.

Reporta 4 categorias:
  A) Reconciliação pendente — decisions onde _reconcile_label(label, gto_label) != label
  B) Cobertura GTO — % de decisions com gto_label populado, por street/posição
  C) Live vs stored — decisions cujo gto_label recalculado pela strategy_json do nó
     atual diverge do gto_label armazenado (resync pendente)
  D) Confiança dos KPIs do torneio — tournaments cujo standard_pct deriva de
     decisions com baixa cobertura GTO

Uso:
    python scripts/audit_label_coherence.py                 # relatório completo
    python scripts/audit_label_coherence.py --user-id 1     # apenas um usuário
    python scripts/audit_label_coherence.py --json          # saída JSON (para o endpoint)
    python scripts/audit_label_coherence.py --samples 10    # mais amostras
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import defaultdict
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from database.schema import get_conn
from database.repositories import _reconcile_label


# ── Thresholds (alinhados com app.py:3461 e effectiveGtoLabel do frontend) ───
def _derive_gto_label(freq: float) -> str:
    if freq >= 0.60: return 'gto_correct'
    if freq >= 0.30: return 'gto_mixed'
    if freq >= 0.10: return 'gto_minor_deviation'
    return 'gto_critical'


def _norm_action(a: str) -> str:
    a = (a or '').lower().rstrip('s')
    return {'raise': 'bet', 'all-in': 'allin', 'jam': 'allin'}.get(a, a)


# ── Audit A: Reconciliação pendente ──────────────────────────────────────────
def audit_reconciliation_pending(conn, user_id: int | None = None) -> dict:
    where_user = "AND t.user_id = ?" if user_id else ""
    params: tuple = (user_id,) if user_id else ()
    rows = conn.execute(f"""
        SELECT d.id, d.tournament_id, d.street, d.position, d.label, d.gto_label,
               d.action_taken, t.tournament_id AS site_tid, t.user_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE d.gto_label IS NOT NULL AND d.gto_label != ''
          AND d.label IS NOT NULL AND d.label != ''
          {where_user}
    """, params).fetchall()

    diverging = []
    by_transition: dict = defaultdict(int)
    affected_tournaments: set = set()
    for r in rows:
        reconciled = _reconcile_label(r['label'], r['gto_label'])
        if reconciled != r['label']:
            diverging.append(dict(r) | {'reconciled_label': reconciled})
            by_transition[(r['label'], reconciled, r['gto_label'])] += 1
            affected_tournaments.add(r['tournament_id'])

    return {
        'total_with_both_labels': len(rows),
        'pending_reconciliation': len(diverging),
        'pct_pending': round(len(diverging) * 100.0 / len(rows), 2) if rows else 0.0,
        'affected_tournaments': len(affected_tournaments),
        'top_transitions': [
            {'from_label': k[0], 'to_label': k[1], 'gto_label': k[2], 'count': v}
            for k, v in sorted(by_transition.items(), key=lambda x: -x[1])[:10]
        ],
        'samples': diverging[:20],
    }


# ── Audit B: Cobertura GTO ───────────────────────────────────────────────────
def audit_gto_coverage(conn, user_id: int | None = None) -> dict:
    where_user = "AND t.user_id = ?" if user_id else ""
    params: tuple = (user_id,) if user_id else ()

    def _coverage(group_col: str) -> list:
        rows = conn.execute(f"""
            SELECT d.{group_col} AS grp,
                   COUNT(*) AS total,
                   SUM(CASE WHEN d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS with_gto
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.{group_col} IS NOT NULL {where_user}
            GROUP BY d.{group_col}
        """, params).fetchall()
        out = []
        for r in rows:
            tot, wg = r['total'], r['with_gto']
            out.append({
                'group': r['grp'], 'total': tot, 'with_gto': wg,
                'coverage_pct': round(wg * 100.0 / tot, 1) if tot else 0.0,
            })
        return sorted(out, key=lambda x: -x['total'])

    overall = conn.execute(f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS with_gto
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE 1=1 {where_user}
    """, params).fetchone()

    tot = overall['total'] or 0
    wg = overall['with_gto'] or 0
    return {
        'total': tot,
        'with_gto': wg,
        'coverage_pct': round(wg * 100.0 / tot, 1) if tot else 0.0,
        'by_street': _coverage('street'),
        'by_position': _coverage('position'),
    }


# ── Audit C: Live vs stored gto_label ────────────────────────────────────────
def audit_live_vs_stored(conn, user_id: int | None = None, limit_scan: int = 5000) -> dict:
    """
    Para cada decision com gto_label e ação tomada conhecida, recupera o gto_node
    correspondente (pelo spot_hash) e recomputa gto_label a partir do strategy_json
    + action_taken. Reporta divergências contra o gto_label armazenado.

    Custo: O(N) decisions * lookup gto_nodes. Limita scan para evitar travar relatório
    em bancos grandes.
    """
    from leaklab.gto_utils import compute_spot_hash as _csh

    where_user = "AND t.user_id = ?" if user_id else ""
    params: tuple = (user_id, limit_scan) if user_id else (limit_scan,)
    rows = conn.execute(f"""
        SELECT d.id, d.tournament_id, d.street, d.position, d.board, d.hero_cards,
               d.stack_bb, d.facing_bet, d.action_taken, d.gto_label
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE d.gto_label IS NOT NULL AND d.gto_label != ''
          AND d.action_taken IS NOT NULL
          {where_user}
        ORDER BY d.id DESC
        LIMIT ?
    """, params).fetchall()

    diverging = []
    no_node = 0
    for r in rows:
        try:
            board = json.loads(r['board'] or '[]') if r['board'] else []
            hand = json.loads(r['hero_cards'] or '[]') if r['hero_cards'] else []
            stack = float(r['stack_bb'] or 20.0)
            face = float(r['facing_bet'] or 0.0)
        except Exception:
            continue

        h_specific = _csh(r['street'], r['position'], board, hand, stack, face)
        h_generic = _csh(r['street'], r['position'], board, [], stack, face)

        node = conn.execute(
            "SELECT strategy_json, gto_action, gto_freq FROM gto_nodes WHERE spot_hash IN (?, ?) LIMIT 1",
            (h_specific, h_generic)
        ).fetchone()
        if not node:
            no_node += 1
            continue

        strategy: dict = {}
        if node['strategy_json']:
            try:
                raw = json.loads(node['strategy_json'])
                for k, v in raw.items():
                    strategy[k] = v['frequency'] if isinstance(v, dict) else float(v)
            except Exception:
                pass
        if not strategy and node['gto_action']:
            strategy[node['gto_action']] = float(node['gto_freq'] or 1.0)
        if not strategy:
            continue

        acted = _norm_action(r['action_taken'])
        freq = strategy.get(acted, 0.0)
        live = _derive_gto_label(freq)
        if live != r['gto_label']:
            diverging.append({
                'id': r['id'], 'tournament_id': r['tournament_id'],
                'street': r['street'], 'position': r['position'],
                'action_taken': r['action_taken'],
                'stored_gto_label': r['gto_label'],
                'live_gto_label': live,
                'live_freq': round(freq, 3),
            })

    return {
        'scanned': len(rows),
        'no_matching_node': no_node,
        'diverging': len(diverging),
        'pct_diverging': round(len(diverging) * 100.0 / len(rows), 2) if rows else 0.0,
        'samples': diverging[:20],
    }


# ── Audit D: Confiança dos KPIs do torneio ───────────────────────────────────
def audit_tournament_kpi_backing(conn, user_id: int | None = None) -> dict:
    where_user = "AND t.user_id = ?" if user_id else ""
    params: tuple = (user_id,) if user_id else ()
    rows = conn.execute(f"""
        SELECT t.id, t.tournament_id, t.tournament_name, t.user_id,
               t.standard_pct, t.decisions_count, t.imported_at,
               SUM(CASE WHEN d.gto_label IS NOT NULL AND d.gto_label != '' THEN 1 ELSE 0 END) AS with_gto,
               COUNT(d.id) AS total
        FROM tournaments t
        LEFT JOIN decisions d ON d.tournament_id = t.id
        WHERE 1=1 {where_user}
        GROUP BY t.id
    """, params).fetchall()

    low_backing = []  # cobertura < 50%
    no_backing = []   # cobertura == 0%
    for r in rows:
        tot = r['total'] or 0
        wg = r['with_gto'] or 0
        cov = (wg * 100.0 / tot) if tot else 0.0
        rec = {
            'id': r['id'], 'tournament_id': r['tournament_id'],
            'tournament_name': r['tournament_name'], 'user_id': r['user_id'],
            'standard_pct': r['standard_pct'], 'decisions': tot,
            'with_gto': wg, 'gto_coverage_pct': round(cov, 1),
            'imported_at': r['imported_at'],
        }
        if tot > 0 and cov == 0.0:
            no_backing.append(rec)
        elif tot > 0 and cov < 50.0:
            low_backing.append(rec)

    return {
        'total_tournaments': len(rows),
        'no_gto_backing': len(no_backing),
        'low_gto_backing': len(low_backing),
        'samples_no_backing': sorted(no_backing, key=lambda x: -(x['decisions'] or 0))[:10],
        'samples_low_backing': sorted(low_backing, key=lambda x: -(x['decisions'] or 0))[:10],
    }


# ── Orquestrador ─────────────────────────────────────────────────────────────
def run_audit(user_id: int | None = None, scan_limit: int = 5000) -> dict:
    conn = get_conn()
    try:
        return {
            'user_id': user_id,
            'reconciliation': audit_reconciliation_pending(conn, user_id),
            'coverage': audit_gto_coverage(conn, user_id),
            'live_vs_stored': audit_live_vs_stored(conn, user_id, scan_limit),
            'tournament_kpi_backing': audit_tournament_kpi_backing(conn, user_id),
        }
    finally:
        conn.close()


# ── CLI pretty-print ─────────────────────────────────────────────────────────
def _print_report(report: dict, samples: int) -> None:
    def hdr(t: str) -> None:
        print('\n' + '=' * 72); print(f'  {t}'); print('=' * 72)
    def sec(t: str) -> None:
        print('\n' + '-' * 72); print(f'  {t}'); print('-' * 72)

    hdr('AUDITORIA DE COERÊNCIA label vs gto_label')
    if report['user_id']:
        print(f"  Filtro: user_id = {report['user_id']}")

    sec('A) RECONCILIAÇÃO PENDENTE')
    rec = report['reconciliation']
    print(f"  Decisions com ambos labels: {rec['total_with_both_labels']}")
    print(f"  Pendentes de reconciliação: {rec['pending_reconciliation']} ({rec['pct_pending']}%)")
    print(f"  Torneios afetados:          {rec['affected_tournaments']}")
    if rec['top_transitions']:
        print('\n  Top transicoes label_atual -> label_esperado (gto_label):')
        for t in rec['top_transitions']:
            print(f"    {t['from_label']:<15} -> {t['to_label']:<15}  ({t['gto_label']:<22}) {t['count']:>5} casos")

    sec('B) COBERTURA GTO')
    cov = report['coverage']
    print(f"  Total decisions: {cov['total']}  |  Com gto_label: {cov['with_gto']}  |  Cobertura: {cov['coverage_pct']}%")
    print('\n  Por street:')
    for r in cov['by_street']:
        print(f"    {(r['group'] or '?'):<10}  total={r['total']:>6}  with_gto={r['with_gto']:>6}  cov={r['coverage_pct']}%")
    print('\n  Por posição:')
    for r in cov['by_position']:
        print(f"    {(r['group'] or '?'):<10}  total={r['total']:>6}  with_gto={r['with_gto']:>6}  cov={r['coverage_pct']}%")

    sec('C) LIVE GTO_LABEL vs ARMAZENADO')
    lvs = report['live_vs_stored']
    print(f"  Escaneadas: {lvs['scanned']}")
    print(f"  Sem nó GTO correspondente: {lvs['no_matching_node']}")
    print(f"  Divergentes (resync pendente): {lvs['diverging']} ({lvs['pct_diverging']}%)")
    if lvs['samples']:
        print(f"\n  Amostras (até {samples}):")
        for s in lvs['samples'][:samples]:
            print(f"    id={s['id']:>7}  {s['street']:<7} {s['position']:<5}  action={s['action_taken']:<6}  "
                  f"stored={s['stored_gto_label']:<22}  live={s['live_gto_label']:<22}  freq={s['live_freq']}")

    sec('D) KPIs DE TORNEIO — CONFIANÇA')
    kpi = report['tournament_kpi_backing']
    print(f"  Total de torneios:        {kpi['total_tournaments']}")
    print(f"  Sem cobertura GTO (0%):   {kpi['no_gto_backing']}")
    print(f"  Cobertura < 50%:          {kpi['low_gto_backing']}")
    if kpi['samples_no_backing']:
        print('\n  Torneios sem cobertura (amostra):')
        for t in kpi['samples_no_backing'][:samples]:
            print(f"    tid={t['tournament_id']}  user={t['user_id']}  decisions={t['decisions']}  std={t['standard_pct']}%")
    if kpi['samples_low_backing']:
        print('\n  Torneios com cobertura < 50% (amostra):')
        for t in kpi['samples_low_backing'][:samples]:
            print(f"    tid={t['tournament_id']}  user={t['user_id']}  decisions={t['decisions']}  cov={t['gto_coverage_pct']}%  std={t['standard_pct']}%")

    hdr('FIM')


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--user-id', type=int, default=None)
    p.add_argument('--samples', type=int, default=8)
    p.add_argument('--scan-limit', type=int, default=5000)
    p.add_argument('--json', action='store_true')
    args = p.parse_args()

    report = run_audit(user_id=args.user_id, scan_limit=args.scan_limit)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report, args.samples)


if __name__ == '__main__':
    main()
