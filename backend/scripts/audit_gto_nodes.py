#!/usr/bin/env python3
"""
Auditoria de qualidade dos nós GTO armazenados.

Uso:
    python scripts/audit_gto_nodes.py           # apenas relatorio
    python scripts/audit_gto_nodes.py --fix     # aplica correcoes seguras

Correções aplicadas com --fix:
    - Normaliza gto_action (shove/allin/all-in → jam)
    - Marca nós preflop sem hero_hand como is_aggregate=1
    - Remove nós com strategy_json corrompido (freq_sum < 0.10)
"""
import sys, json, argparse, logging
sys.path.insert(0, '.')

from database.schema import get_conn

logging.basicConfig(level=logging.INFO, format='%(levelname)s  %(message)s')
log = logging.getLogger('audit_gto')

_VALID_STREETS   = {'preflop', 'flop', 'turn', 'river'}
_VALID_POSITIONS = {'UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}
_VALID_ACTIONS   = {'fold', 'check', 'call', 'bet', 'raise', 'jam'}
_NORM_ACTION     = {
    'shove': 'jam', 'allin': 'jam', 'all-in': 'jam', 'all_in': 'jam', 'all in': 'jam',
}


def _freq_sum(strategy_json: str) -> float:
    try:
        data = json.loads(strategy_json) if strategy_json else {}
        total = 0.0
        for v in data.values():
            if isinstance(v, dict):
                total += float(v.get('frequency', 0) or 0)
            elif isinstance(v, (int, float)):
                total += float(v)
        return total
    except Exception:
        return 0.0


def run_audit(fix: bool = False) -> dict:
    conn = get_conn()
    results = {}

    # ── C1: nós preflop sem hero_hand sem is_aggregate ────────────────────────
    rows = conn.execute(
        "SELECT id, position, gto_action FROM gto_nodes "
        "WHERE street='preflop' AND (hero_hand IS NULL OR hero_hand='[]') "
        "AND (is_aggregate IS NULL OR is_aggregate=0)"
    ).fetchall()
    results['C1_preflop_aggregate_not_flagged'] = len(rows)
    if rows:
        log.warning('[C1] %d nós preflop agregados sem is_aggregate=1', len(rows))
        if fix:
            ids = [r[0] for r in rows]
            conn.execute(
                'UPDATE gto_nodes SET is_aggregate=1 WHERE id IN (%s)' % ','.join('?' * len(ids)),
                ids
            )
            log.info('[C1 FIX] %d nós marcados como is_aggregate=1', len(ids))

    # ── C2: strategy_json com freq_sum < 0.10 (corrompido) ────────────────────
    all_nodes = conn.execute(
        'SELECT id, street, position, gto_action, strategy_json FROM gto_nodes '
        'WHERE strategy_json IS NOT NULL'
    ).fetchall()
    corrupt_ids = []
    for row in all_nodes:
        fsum = _freq_sum(row[4])
        if fsum < 0.10:
            corrupt_ids.append(row[0])
            log.warning('[C2] nó id=%d %s/%s/%s freq_sum=%.3f (corrompido)',
                        row[0], row[1], row[2], row[3], fsum)
    results['C2_corrupt_strategy_json'] = len(corrupt_ids)
    if corrupt_ids and fix:
        conn.execute(
            'UPDATE gto_nodes SET strategy_json=NULL WHERE id IN (%s)' % ','.join('?' * len(corrupt_ids)),
            corrupt_ids
        )
        log.info('[C2 FIX] strategy_json removido de %d nós corrompidos', len(corrupt_ids))

    # ── C3: gto_action não normalizado ────────────────────────────────────────
    rows_c3 = conn.execute(
        "SELECT id, gto_action FROM gto_nodes "
        "WHERE gto_action IN ('shove','allin','all-in','all_in')"
    ).fetchall()
    results['C3_action_not_normalized'] = len(rows_c3)
    if rows_c3:
        log.warning('[C3] %d nós com gto_action não normalizado', len(rows_c3))
        if fix:
            for nid, act in rows_c3:
                new_act = _NORM_ACTION.get(act.lower(), act)
                conn.execute('UPDATE gto_nodes SET gto_action=? WHERE id=?', (new_act, nid))
            log.info('[C3 FIX] %d gto_action normalizados para jam', len(rows_c3))

    # ── C4: position desconhecida ─────────────────────────────────────────────
    all_pos = conn.execute('SELECT DISTINCT position FROM gto_nodes').fetchall()
    bad_pos = [r[0] for r in all_pos if r[0] not in _VALID_POSITIONS]
    c4_count = 0
    for p in bad_pos:
        cnt = conn.execute('SELECT COUNT(*) FROM gto_nodes WHERE position=?', (p,)).fetchone()[0]
        c4_count += cnt
        log.error('[C4] position desconhecida: %r (%d nós)', p, cnt)
    results['C4_invalid_position'] = c4_count

    # ── C5: street desconhecida ───────────────────────────────────────────────
    all_streets = conn.execute('SELECT DISTINCT street FROM gto_nodes').fetchall()
    bad_streets = [r[0] for r in all_streets if r[0] not in _VALID_STREETS]
    c5_count = 0
    for s in bad_streets:
        cnt = conn.execute('SELECT COUNT(*) FROM gto_nodes WHERE street=?', (s,)).fetchone()[0]
        c5_count += cnt
        log.error('[C5] street desconhecida: %r (%d nós)', s, cnt)
    results['C5_invalid_street'] = c5_count

    # ── C6: gto_freq fora de [0,1] ────────────────────────────────────────────
    cnt_c6 = conn.execute(
        'SELECT COUNT(*) FROM gto_nodes WHERE gto_freq < 0 OR gto_freq > 1.0'
    ).fetchone()[0]
    results['C6_freq_out_of_range'] = cnt_c6
    if cnt_c6:
        log.error('[C6] %d nós com gto_freq fora de [0,1]', cnt_c6)

    # ── C7: decisions com gto_label mas sem gto_action ────────────────────────
    try:
        cnt_c7 = conn.execute(
            'SELECT COUNT(*) FROM decisions WHERE gto_label IS NOT NULL AND gto_action IS NULL'
        ).fetchone()[0]
        results['C7_decisions_label_no_action'] = cnt_c7
        if cnt_c7:
            log.warning('[C7] %d decisions com gto_label sem gto_action', cnt_c7)
    except Exception:
        results['C7_decisions_label_no_action'] = 'N/A'

    # ── C8: decisions com gto_action inválido ─────────────────────────────────
    try:
        invalid_actions_sql = "gto_action NOT IN ('fold','check','call','bet','raise','jam','allin','shove','all-in','jam')"
        cnt_c8 = conn.execute(
            f'SELECT COUNT(*) FROM decisions WHERE {invalid_actions_sql} AND gto_action IS NOT NULL'
        ).fetchone()[0]
        results['C8_decisions_invalid_action'] = cnt_c8
        if cnt_c8:
            log.error('[C8] %d decisions com gto_action inválido', cnt_c8)
    except Exception:
        results['C8_decisions_invalid_action'] = 'N/A'

    # ── C9: nós preflop com fold como top action sem hero_hand (bug tipo KK) ──
    cnt_c9 = conn.execute(
        "SELECT COUNT(*) FROM gto_nodes WHERE street='preflop' AND gto_action='fold' "
        "AND (hero_hand IS NULL OR hero_hand='[]')"
    ).fetchone()[0]
    results['C9_preflop_fold_aggregate'] = cnt_c9
    if cnt_c9:
        log.warning('[C9] %d nós preflop agregados com gto_action=fold (potencial KK-bug)', cnt_c9)
        if fix:
            conn.execute(
                "UPDATE gto_nodes SET is_aggregate=1 WHERE street='preflop' AND gto_action='fold' "
                "AND (hero_hand IS NULL OR hero_hand='[]')"
            )
            log.info('[C9 FIX] nós C9 marcados como is_aggregate=1')

    if fix:
        conn.commit()

    conn.close()
    return results


def print_report(results: dict, fix: bool) -> None:
    print()
    print('=' * 60)
    print('RELATÓRIO DE AUDITORIA — GTO Nodes')
    print('Mode:', 'FIX (correções aplicadas)' if fix else 'READ-ONLY')
    print('=' * 60)
    labels = {
        'C1_preflop_aggregate_not_flagged': 'C1  Preflop agregados sem is_aggregate flag',
        'C2_corrupt_strategy_json':         'C2  strategy_json corrompidos (freq_sum < 0.10)',
        'C3_action_not_normalized':         'C3  gto_action não normalizado (shove/allin)',
        'C4_invalid_position':              'C4  position desconhecida',
        'C5_invalid_street':                'C5  street desconhecida',
        'C6_freq_out_of_range':             'C6  gto_freq fora de [0,1]',
        'C7_decisions_label_no_action':     'C7  decisions gto_label sem gto_action',
        'C8_decisions_invalid_action':      'C8  decisions gto_action inválido',
        'C9_preflop_fold_aggregate':        'C9  Preflop fold agregado (tipo KK-bug) [CRITICAL]',
    }
    any_issue = False
    for key, label in labels.items():
        val = results.get(key, 0)
        icon = '✓' if val == 0 or val == 'N/A' else '✗'
        if val not in (0, 'N/A'):
            any_issue = True
        print(f'  {icon}  {label}: {val}')

    print()
    if any_issue:
        print('⚠  Problemas encontrados. Execute com --fix para corrigir os itens C1, C2, C3, C9.')
    else:
        print('✓  Nenhum problema encontrado.')
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Auditoria de qualidade dos nós GTO')
    parser.add_argument('--fix', action='store_true', help='Aplicar correções automáticas')
    args = parser.parse_args()

    results = run_audit(fix=args.fix)
    print_report(results, fix=args.fix)

    has_critical = any(
        results.get(k, 0) not in (0, 'N/A')
        for k in ('C4_invalid_position', 'C5_invalid_street', 'C6_freq_out_of_range', 'C8_decisions_invalid_action')
    )
    sys.exit(1 if has_critical else 0)
