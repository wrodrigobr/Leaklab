"""
Testa o orchestrator.revalidate end-to-end usando fixture mini + SQLite em memória.

Cobertura:
  - Re-parse de raw_text + sweep de todas as decisões
  - Persistência em revalidation_runs + revalidation_findings
  - Idempotência (mesmas counts em runs consecutivos)
  - Filtros de scope (tournament-specific)
  - Saída em arquivo (Markdown + JSON)
"""
import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Banco em tempfile (não :memory:) porque cada get_conn cria conexão nova.
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'revalidation_mini.txt')


def _reset_db():
    """Apaga o tempfile entre testes para começar limpo."""
    try:
        os.unlink(_TMPDB.name)
    except FileNotFoundError:
        pass


def _bootstrap_db_with_fixture():
    """Inicializa schema e injeta a fixture como um torneio com raw_text."""
    _reset_db()
    from database.schema import init_db, get_conn
    init_db()
    with open(FIXTURE, 'r', encoding='utf-8') as f:
        raw = f.read()
    conn = get_conn()
    try:
        # Cria usuário mínimo
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ('phpro_test', 'phpro_test@example.com', 'x'),
        )
        urow = conn.execute(
            "SELECT id FROM users WHERE username = ?", ('phpro_test',)
        ).fetchone()
        uid = dict(urow)['id']
        conn.execute(
            "INSERT INTO tournaments (user_id, tournament_id, hero, raw_text, site) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, '999900001', 'HeroPlayer', raw, 'pokerstars'),
        )
        trow = conn.execute(
            "SELECT id FROM tournaments WHERE tournament_id = ?", ('999900001',)
        ).fetchone()
        tid = dict(trow)['id']
        conn.commit()
        return uid, tid
    finally:
        conn.close()


# -- Testes ------------------------------------------------------------------

def test_sweep_all_completes_without_errors():
    uid, tid = _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    result = revalidate(scope=Scope.all(), persist=True)
    assert result.errors == [], f"sweep teve erros: {result.errors}"
    assert result.total_tournaments == 1
    assert result.total_hands == 5
    assert result.total_decisions >= 5, f"esperava >=5 decisões, recebi {result.total_decisions}"
    assert result.run_id is not None
    print(f"OK  test_sweep_all_completes_without_errors (decisions={result.total_decisions}, run_id={result.run_id})")


def test_sweep_categories_sum_to_total():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    result = revalidate(scope=Scope.all(), persist=True)
    total = sum(result.category_counts.values())
    assert total == result.total_decisions, (
        f"sum(counts)={total} != total_decisions={result.total_decisions}"
    )
    assert 'aligned' in result.category_counts or 'acceptable_alt' in result.category_counts
    print(f"OK  test_sweep_categories_sum_to_total (counts={result.category_counts})")


def test_sweep_is_idempotent():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    r1 = revalidate(scope=Scope.all(), persist=True)
    r2 = revalidate(scope=Scope.all(), persist=True)
    assert r1.category_counts == r2.category_counts, (
        f"counts diferem: {r1.category_counts} vs {r2.category_counts}"
    )
    assert r1.total_decisions == r2.total_decisions
    assert r1.run_id != r2.run_id  # cada run é uma nova linha
    print(f"OK  test_sweep_is_idempotent (counts={r1.category_counts})")


def test_scope_tournament_filters_correctly():
    uid, tid = _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    result = revalidate(scope=Scope.for_tournament(tid), persist=False)
    assert result.total_tournaments == 1
    assert result.total_decisions > 0

    # Torneio inexistente
    empty = revalidate(scope=Scope.for_tournament(99999), persist=False)
    assert empty.total_tournaments == 0
    assert empty.total_decisions == 0
    print(f"OK  test_scope_tournament_filters_correctly (decisions={result.total_decisions})")


def test_scope_user_filters_correctly():
    uid, _tid = _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    result = revalidate(scope=Scope.for_user(uid), persist=False)
    assert result.total_tournaments == 1
    assert result.total_decisions > 0

    other = revalidate(scope=Scope.for_user(99999), persist=False)
    assert other.total_tournaments == 0
    print(f"OK  test_scope_user_filters_correctly (decisions={result.total_decisions})")


def test_persistence_creates_run_and_findings_rows():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope
    from database.schema import get_conn

    r = revalidate(scope=Scope.all(), persist=True)
    conn = get_conn()
    try:
        run_row = conn.execute(
            "SELECT * FROM revalidation_runs WHERE id = ?", (r.run_id,)
        ).fetchone()
        assert run_row is not None
        run_d = dict(run_row)
        assert run_d['scope'] == 'all'
        assert run_d['total_decisions'] == r.total_decisions
        counts = json.loads(run_d['category_counts_json'])
        assert counts == r.category_counts

        rows = conn.execute(
            "SELECT category, COUNT(*) as n FROM revalidation_findings WHERE run_id = ? GROUP BY category",
            (r.run_id,),
        ).fetchall()
        per_cat = {dict(x)['category']: dict(x)['n'] for x in rows}
        assert per_cat == r.category_counts, (
            f"counts no DB ({per_cat}) ≠ counts no resultado ({r.category_counts})"
        )
    finally:
        conn.close()
    print(f"OK  test_persistence_creates_run_and_findings_rows (per_cat={per_cat})")


def test_no_persist_returns_run_id_none():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    r = revalidate(scope=Scope.all(), persist=False)
    assert r.run_id is None
    # Mas findings continuam no objeto resultado
    assert len(r.findings) == r.total_decisions
    print("OK  test_no_persist_returns_run_id_none")


def test_output_dir_writes_files():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    tmpdir = tempfile.mkdtemp(prefix='reval_test_')
    try:
        r = revalidate(scope=Scope.all(), persist=True, output_dir=tmpdir)
        files = sorted(os.listdir(tmpdir))
        assert any(f.endswith('.json') for f in files), f"sem JSON em {files}"
        assert any(f.endswith('.md') for f in files), f"sem MD em {files}"
        # Valida JSON
        json_path = next(f for f in files if f.endswith('.json'))
        with open(os.path.join(tmpdir, json_path)) as f:
            payload = json.load(f)
        assert payload['meta']['total_decisions'] == r.total_decisions
        assert len(payload['findings']) == r.total_decisions
        # Valida MD
        md_path = next(f for f in files if f.endswith('.md'))
        with open(os.path.join(tmpdir, md_path)) as f:
            md = f.read()
        assert '# Revalidação' in md
        assert 'Distribuição por categoria' in md
        print(f"OK  test_output_dir_writes_files ({files})")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_findings_have_required_fields():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    r = revalidate(scope=Scope.all(), persist=False)
    assert r.findings, "sem findings"
    for f in r.findings:
        for k in ('tournament_db_id', 'hand_id', 'decision_index', 'street',
                  'position', 'action_taken', 'engine_best', 'category',
                  'severity_score', 'oracle_source', 'oracle_confidence',
                  'reasons'):
            assert k in f, f"chave {k} faltando em finding"
        assert 0.0 <= f['severity_score'] <= 1.0
    print(f"OK  test_findings_have_required_fields ({len(r.findings)} findings)")


def test_severity_ordering_matches_categories():
    _bootstrap_db_with_fixture()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    r = revalidate(scope=Scope.all(), persist=False)
    # Categoria 'aligned' deve ter severity 0; major_mismatch > minor_mismatch
    by_cat = {}
    for f in r.findings:
        by_cat.setdefault(f['category'], []).append(f['severity_score'])
    if 'aligned' in by_cat:
        assert all(s == 0 for s in by_cat['aligned']), "aligned deve ter severity 0"
    if 'major_mismatch' in by_cat and 'minor_mismatch' in by_cat:
        assert min(by_cat['major_mismatch']) >= max(by_cat['minor_mismatch']), (
            "major deve ter severity >= minor"
        )
    print(f"OK  test_severity_ordering_matches_categories")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)
