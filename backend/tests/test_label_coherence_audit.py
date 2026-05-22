"""
Testes da auditoria scripts/audit_label_coherence.py.

Valida que cada uma das 4 categorias do relatorio detecta as condicoes
esperadas em fixtures controladas.
"""
import sys, os, tempfile, sqlite3, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

TEST_DB = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo


def _setup():
    sch.DB_PATH = TEST_DB
    repo.DB_PATH = TEST_DB

    def get_conn_test():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    sch.get_conn = get_conn_test
    repo.get_conn = get_conn_test
    sch.init_db()

    # Reimport audit module to pick up patched get_conn
    import importlib
    if 'audit_label_coherence' in sys.modules:
        importlib.reload(sys.modules['audit_label_coherence'])
    if 'database.schema' in sys.modules:
        # Garante que o modulo importado dentro de audit_label_coherence usa nosso get_conn
        pass


_setup()


def _clean():
    conn = sch.get_conn()
    conn.execute('DELETE FROM decisions')
    conn.execute('DELETE FROM tournaments')
    conn.execute('DELETE FROM users')
    try:
        conn.execute('DELETE FROM gto_nodes')
    except Exception:
        pass
    conn.commit()
    conn.close()


def _seed_user_tournament():
    uid = repo.create_user('audituser', 'audit@t.com', 'pwd')
    t_id = repo.save_tournament(uid, 'TAUDIT', 'phpro', {
        'total_hands': 4, 'total_decisions': 4, 'avg_mistake_score': 0.1,
        'label_pct': {'standard': 50.0},
    })
    return uid, t_id


def _insert_decision(t_id, label, gto_label, street='preflop', position='BTN',
                     action='fold', stack_bb=20.0, facing_bet=0.0,
                     hero_cards='[]', board='[]'):
    conn = sch.get_conn()
    conn.execute("""
        INSERT INTO decisions
          (tournament_id, hand_id, street, position, action_taken, best_action,
           label, gto_label, gto_action, score, stack_bb, facing_bet,
           hero_cards, board)
        VALUES (?, 'H1', ?, ?, ?, 'fold', ?, ?, 'fold', 0.05, ?, ?, ?, ?)
    """, (t_id, street, position, action, label, gto_label, stack_bb,
          facing_bet, hero_cards, board))
    conn.commit()
    conn.close()


# ── Audit A: reconciliacao pendente ──────────────────────────────────────────

def test_audit_reconciliation_detects_standard_to_critical():
    _clean()
    from audit_label_coherence import audit_reconciliation_pending
    uid, t_id = _seed_user_tournament()
    # label=standard mas gto=gto_critical -> deveria virar small_mistake
    _insert_decision(t_id, label='standard', gto_label='gto_critical')
    # Caso ja reconciliado: label=standard, gto=gto_correct -> NAO deve aparecer
    _insert_decision(t_id, label='standard', gto_label='gto_correct')

    conn = sch.get_conn()
    try:
        rep = audit_reconciliation_pending(conn)
    finally:
        conn.close()
    assert rep['total_with_both_labels'] == 2
    assert rep['pending_reconciliation'] == 1
    assert rep['affected_tournaments'] == 1
    assert rep['top_transitions'][0]['from_label'] == 'standard'
    assert rep['top_transitions'][0]['to_label'] == 'small_mistake'
    assert rep['top_transitions'][0]['gto_label'] == 'gto_critical'
    print('OK  test_audit_reconciliation_detects_standard_to_critical')


def test_audit_reconciliation_clear_mistake_to_standard():
    _clean()
    from audit_label_coherence import audit_reconciliation_pending
    uid, t_id = _seed_user_tournament()
    _insert_decision(t_id, label='clear_mistake', gto_label='gto_correct')

    conn = sch.get_conn()
    try:
        rep = audit_reconciliation_pending(conn)
    finally:
        conn.close()
    assert rep['pending_reconciliation'] == 1
    t = rep['top_transitions'][0]
    assert t['from_label'] == 'clear_mistake' and t['to_label'] == 'standard'
    print('OK  test_audit_reconciliation_clear_mistake_to_standard')


def test_audit_reconciliation_user_filter():
    _clean()
    from audit_label_coherence import audit_reconciliation_pending
    uid1, t1 = _seed_user_tournament()
    uid2 = repo.create_user('other', 'o@t.com', 'p')
    t2 = repo.save_tournament(uid2, 'T2', 'phpro', {
        'total_hands': 1, 'total_decisions': 1, 'avg_mistake_score': 0.05,
        'label_pct': {'standard': 100.0},
    })
    _insert_decision(t1, label='standard', gto_label='gto_critical')
    _insert_decision(t2, label='standard', gto_label='gto_critical')

    conn = sch.get_conn()
    try:
        only_uid1 = audit_reconciliation_pending(conn, user_id=uid1)
    finally:
        conn.close()
    assert only_uid1['pending_reconciliation'] == 1
    assert only_uid1['affected_tournaments'] == 1
    print('OK  test_audit_reconciliation_user_filter')


# ── Audit B: cobertura GTO ───────────────────────────────────────────────────

def test_audit_coverage_computes_pct():
    _clean()
    from audit_label_coherence import audit_gto_coverage
    uid, t_id = _seed_user_tournament()
    _insert_decision(t_id, label='standard', gto_label='gto_correct', street='preflop')
    _insert_decision(t_id, label='standard', gto_label=None, street='preflop')
    _insert_decision(t_id, label='standard', gto_label='gto_correct', street='flop')

    conn = sch.get_conn()
    try:
        cov = audit_gto_coverage(conn)
    finally:
        conn.close()
    assert cov['total'] == 3
    assert cov['with_gto'] == 2
    assert abs(cov['coverage_pct'] - 66.7) < 0.1
    preflop = next(s for s in cov['by_street'] if s['group'] == 'preflop')
    assert preflop['total'] == 2 and preflop['with_gto'] == 1
    print('OK  test_audit_coverage_computes_pct')


# ── Audit C: live vs stored ──────────────────────────────────────────────────

def test_audit_live_vs_stored_detects_divergence():
    _clean()
    from audit_label_coherence import audit_live_vs_stored
    from leaklab.gto_utils import compute_spot_hash
    import json as _json

    uid, t_id = _seed_user_tournament()
    # Decision postflop com gto_label=gto_correct armazenado, mas strategy
    # do node atual diz que action_taken foi gto_critical (freq < 0.1)
    board = ['Ah', 'Kd', '7c']
    hero = ['Qs', 'Js']
    h = compute_spot_hash('flop', 'BTN', board, hero, 20.0, 0.0)
    h_generic = compute_spot_hash('flop', 'BTN', board, [], 20.0, 0.0)

    _insert_decision(
        t_id, label='standard', gto_label='gto_correct',
        street='flop', position='BTN', action='call',
        hero_cards=_json.dumps(hero), board=_json.dumps(board),
        stack_bb=20.0, facing_bet=0.0,
    )

    # Inserir gto_node com strategy onde 'call' tem freq 0.05 (gto_critical)
    conn = sch.get_conn()
    try:
        conn.execute("""
            INSERT INTO gto_nodes (spot_hash, street, position, board, hero_hand,
                                    stack_bucket, gto_action, gto_freq, strategy_json)
            VALUES (?, 'flop', 'BTN', ?, '[]', '20bb', 'bet', 0.9, ?)
        """, (h_generic, _json.dumps(board),
              _json.dumps({'bet': {'frequency': 0.9}, 'call': {'frequency': 0.05}})))
        conn.commit()
    finally:
        conn.close()

    conn = sch.get_conn()
    try:
        rep = audit_live_vs_stored(conn)
    finally:
        conn.close()
    assert rep['scanned'] == 1
    assert rep['no_matching_node'] == 0
    assert rep['diverging'] == 1
    s = rep['samples'][0]
    assert s['stored_gto_label'] == 'gto_correct'
    assert s['live_gto_label'] == 'gto_critical'
    print('OK  test_audit_live_vs_stored_detects_divergence')


# ── Audit D: tournament KPI backing ──────────────────────────────────────────

def test_audit_tournament_kpi_backing_flags_no_coverage():
    _clean()
    from audit_label_coherence import audit_tournament_kpi_backing
    uid, t_id = _seed_user_tournament()
    _insert_decision(t_id, label='standard', gto_label=None)
    _insert_decision(t_id, label='standard', gto_label=None)

    conn = sch.get_conn()
    try:
        rep = audit_tournament_kpi_backing(conn)
    finally:
        conn.close()
    assert rep['no_gto_backing'] == 1
    assert rep['low_gto_backing'] == 0
    print('OK  test_audit_tournament_kpi_backing_flags_no_coverage')


def test_audit_tournament_kpi_backing_flags_low_coverage():
    _clean()
    from audit_label_coherence import audit_tournament_kpi_backing
    uid, t_id = _seed_user_tournament()
    # 1 com GTO, 3 sem -> 25% cobertura
    _insert_decision(t_id, label='standard', gto_label='gto_correct')
    _insert_decision(t_id, label='standard', gto_label=None)
    _insert_decision(t_id, label='standard', gto_label=None)
    _insert_decision(t_id, label='standard', gto_label=None)

    conn = sch.get_conn()
    try:
        rep = audit_tournament_kpi_backing(conn)
    finally:
        conn.close()
    assert rep['no_gto_backing'] == 0
    assert rep['low_gto_backing'] == 1
    assert rep['samples_low_backing'][0]['gto_coverage_pct'] == 25.0
    print('OK  test_audit_tournament_kpi_backing_flags_low_coverage')


# ── Orquestrador run_audit ───────────────────────────────────────────────────

def test_run_audit_returns_all_sections():
    _clean()
    from audit_label_coherence import run_audit
    uid, t_id = _seed_user_tournament()
    _insert_decision(t_id, label='standard', gto_label='gto_critical')
    rep = run_audit()
    assert set(rep.keys()) >= {'reconciliation', 'coverage', 'live_vs_stored',
                                'tournament_kpi_backing', 'user_id'}
    assert rep['reconciliation']['pending_reconciliation'] == 1
    print('OK  test_run_audit_returns_all_sections')


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f'FAIL {name}: {e}')
            traceback.print_exc()
            failed += 1
    print(f"\n{'=' * 50}")
    print(f'Total: {passed + failed} | Passed: {passed} | Failed: {failed}')
    try:
        os.unlink(TEST_DB)
    except Exception:
        pass
