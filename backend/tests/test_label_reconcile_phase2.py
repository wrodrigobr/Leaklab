"""
Testes da Fase 2 do backlog #2 — reconciliacao observavel e backfill.

Cobre:
 - coluna tournaments.labels_reconciled_at criada pela migration
 - reconcile_tournament_labels seta o timestamp (mesmo sem mudancas)
 - backfill_label_reconciliation: dry-run nao escreve, run normal escreve
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


_setup()


def _clean():
    conn = sch.get_conn()
    for tbl in ('decisions', 'tournaments', 'users'):
        conn.execute(f'DELETE FROM {tbl}')
    conn.commit()
    conn.close()


def _seed():
    uid = repo.create_user('p2user', 'p2@t.com', 'pwd')
    t_id = repo.save_tournament(uid, 'TP2', 'phpro', {
        'total_hands': 2, 'total_decisions': 2, 'avg_mistake_score': 0.1,
        'label_pct': {'standard': 50.0},
    })
    return uid, t_id


def _insert_decision(t_id, label, gto_label, action='fold'):
    conn = sch.get_conn()
    conn.execute("""
        INSERT INTO decisions
          (tournament_id, hand_id, street, position, action_taken, best_action,
           label, gto_label, gto_action, score, stack_bb, facing_bet,
           hero_cards, board)
        VALUES (?, 'H1', 'preflop', 'BTN', ?, 'fold', ?, ?, 'fold', 0.05, 20.0, 0.0, '[]', '[]')
    """, (t_id, action, label, gto_label))
    conn.commit()
    conn.close()


# ── Migration ───────────────────────────────────────────────────────────────

def test_labels_reconciled_at_column_exists():
    conn = sch.get_conn()
    cols = {r[1] for r in conn.execute('PRAGMA table_info(tournaments)').fetchall()}
    conn.close()
    assert 'labels_reconciled_at' in cols, f'coluna ausente, cols={cols}'
    print('OK  test_labels_reconciled_at_column_exists')


# ── reconcile_tournament_labels ─────────────────────────────────────────────

def test_reconcile_sets_timestamp_even_without_changes():
    _clean()
    uid, t_id = _seed()
    # Decision ja reconciliada
    _insert_decision(t_id, label='standard', gto_label='gto_correct')

    n = repo.reconcile_tournament_labels(t_id)
    assert n == 0, f'esperava 0 mudancas, recebi {n}'

    conn = sch.get_conn()
    row = conn.execute(
        "SELECT labels_reconciled_at FROM tournaments WHERE id=?", (t_id,)
    ).fetchone()
    conn.close()
    assert row['labels_reconciled_at'] is not None, 'timestamp nao foi setado'
    print(f'OK  test_reconcile_sets_timestamp_even_without_changes | ts={row["labels_reconciled_at"]}')


def test_reconcile_changes_and_stamps():
    _clean()
    uid, t_id = _seed()
    _insert_decision(t_id, label='standard', gto_label='gto_critical')

    n = repo.reconcile_tournament_labels(t_id)
    assert n == 1, f'esperava 1 mudanca, recebi {n}'

    conn = sch.get_conn()
    row = conn.execute(
        "SELECT label FROM decisions WHERE tournament_id=?", (t_id,)
    ).fetchone()
    assert row['label'] == 'small_mistake'
    conn.close()
    print('OK  test_reconcile_changes_and_stamps')


# ── Backfill (dry-run e execucao) ────────────────────────────────────────────

def test_backfill_dry_run_does_not_write():
    _clean()
    uid, t_id = _seed()
    _insert_decision(t_id, label='standard', gto_label='gto_critical')

    # Import direto do modulo
    import importlib
    if 'backfill_label_reconciliation' in sys.modules:
        importlib.reload(sys.modules['backfill_label_reconciliation'])
    bf = __import__('backfill_label_reconciliation')

    # Patch sys.argv para simular CLI
    orig_argv = sys.argv
    sys.argv = ['backfill', '--dry-run']
    try:
        bf.main()
    finally:
        sys.argv = orig_argv

    conn = sch.get_conn()
    row = conn.execute("SELECT label, gto_label FROM decisions WHERE tournament_id=?", (t_id,)).fetchone()
    ts = conn.execute("SELECT labels_reconciled_at FROM tournaments WHERE id=?", (t_id,)).fetchone()
    conn.close()
    assert row['label'] == 'standard', f'label foi mudado em dry-run: {row["label"]}'
    assert ts['labels_reconciled_at'] is None, 'timestamp foi setado em dry-run'
    print('OK  test_backfill_dry_run_does_not_write')


def test_backfill_normal_run_reconciles():
    _clean()
    uid, t_id = _seed()
    _insert_decision(t_id, label='standard', gto_label='gto_critical')

    import importlib
    if 'backfill_label_reconciliation' in sys.modules:
        importlib.reload(sys.modules['backfill_label_reconciliation'])
    bf = __import__('backfill_label_reconciliation')

    orig_argv = sys.argv
    sys.argv = ['backfill', '--no-sync']
    try:
        bf.main()
    finally:
        sys.argv = orig_argv

    conn = sch.get_conn()
    row = conn.execute("SELECT label FROM decisions WHERE tournament_id=?", (t_id,)).fetchone()
    ts = conn.execute("SELECT labels_reconciled_at FROM tournaments WHERE id=?", (t_id,)).fetchone()
    conn.close()
    assert row['label'] == 'small_mistake', f'esperava small_mistake, recebi {row["label"]}'
    assert ts['labels_reconciled_at'] is not None
    print('OK  test_backfill_normal_run_reconciles')


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
