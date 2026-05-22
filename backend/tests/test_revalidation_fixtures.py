"""
Smoke regressivo: trava o output esperado do varredor na fixture canônica.

Quando alguém alterar o engine ou o oracle e a contagem de divergências
mudar nessa fixture, o teste falha — força quem mexeu a justificar o
delta (atualiza o teto OU explica a regressão).

Para atacar uma categoria de divergência, ADICIONE fixtures novas com
spots representativos do problema (ex: "AKo facing 3bet @ 25bb").
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'revalidation_mini.txt')

# Teto atual — captura o estado conhecido em 2026-05-22 sobre a fixture mini.
# Subir esses números sem comentário no PR é regressão.
_BUDGETS = {
    'major_mismatch':  1,    # 1 spot conhecido (call vs raise CO facing 3bet)
    'minor_mismatch':  0,
    'no_oracle_data':  0,
    'engine_no_data':  0,
}


def _bootstrap():
    try:
        os.unlink(_TMPDB.name)
    except FileNotFoundError:
        pass
    from database.schema import init_db, get_conn
    init_db()
    with open(FIXTURE, 'r', encoding='utf-8') as f:
        raw = f.read()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ('reg_fixture', 'reg_fixture@x.com', 'x'),
        )
        uid = conn.execute(
            "SELECT id FROM users WHERE username = ?", ('reg_fixture',)
        ).fetchone()['id']
        conn.execute(
            "INSERT INTO tournaments (user_id, tournament_id, hero, raw_text, site) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, '999900001', 'HeroPlayer', raw, 'pokerstars'),
        )
        conn.commit()
    finally:
        conn.close()


def test_total_decisions_matches_fixture_shape():
    _bootstrap()
    from leaklab.revalidation.orchestrator import revalidate, Scope
    r = revalidate(scope=Scope.all(), persist=False)
    # 5 mãos na fixture, 11 decisões do hero (medido na implementação atual).
    assert r.total_hands == 5
    assert r.total_decisions == 11, (
        f"esperava 11 decisões, recebi {r.total_decisions} — "
        "shape da fixture mudou ou hand_state_builder está rotando spots."
    )
    print(f"OK  test_total_decisions_matches_fixture_shape (decisions={r.total_decisions})")


def test_major_mismatch_within_budget():
    _bootstrap()
    from leaklab.revalidation.orchestrator import revalidate, Scope
    r = revalidate(scope=Scope.all(), persist=False)
    n = r.category_counts.get('major_mismatch', 0)
    assert n <= _BUDGETS['major_mismatch'], (
        f"major_mismatch={n} > budget={_BUDGETS['major_mismatch']} — "
        "engine OU oracle introduziu divergência nova. Investigue o finding "
        "(rode `python -m scripts.revalidate --tournament-id <id> --output /tmp`) "
        "antes de atualizar o budget."
    )
    print(f"OK  test_major_mismatch_within_budget ({n}/{_BUDGETS['major_mismatch']})")


def test_minor_mismatch_within_budget():
    _bootstrap()
    from leaklab.revalidation.orchestrator import revalidate, Scope
    r = revalidate(scope=Scope.all(), persist=False)
    n = r.category_counts.get('minor_mismatch', 0)
    assert n <= _BUDGETS['minor_mismatch'], (
        f"minor_mismatch={n} > budget={_BUDGETS['minor_mismatch']}"
    )
    print(f"OK  test_minor_mismatch_within_budget ({n}/{_BUDGETS['minor_mismatch']})")


def test_engine_no_data_zero():
    _bootstrap()
    from leaklab.revalidation.orchestrator import revalidate, Scope
    r = revalidate(scope=Scope.all(), persist=False)
    n = r.category_counts.get('engine_no_data', 0)
    assert n == 0, f"engine_no_data={n} — engine retornou bestAction vazio (não deveria)"
    print("OK  test_engine_no_data_zero")


def test_aligned_majority():
    _bootstrap()
    from leaklab.revalidation.orchestrator import revalidate, Scope
    r = revalidate(scope=Scope.all(), persist=False)
    aligned = r.category_counts.get('aligned', 0)
    acceptable = r.category_counts.get('acceptable_alt', 0)
    healthy = aligned + acceptable
    pct = healthy / max(r.total_decisions, 1)
    assert pct >= 0.70, (
        f"aligned+acceptable_alt = {healthy}/{r.total_decisions} ({pct:.0%}) < 70% — "
        "saúde do engine caiu drasticamente na fixture mini"
    )
    print(f"OK  test_aligned_majority ({pct:.0%} healthy)")


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
