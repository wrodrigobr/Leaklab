"""
Regressão do escopo do /admin/reanalyze-preflop-labels: hand_id NÃO é único entre
torneios/usuários (dois jogadores importam o mesmo torneio = mesmo hand_id). O lookup
da decisão a re-labelar/reposicionar DEVE casar por (tournament_id, hand_id, action),
nunca só por (hand_id, action) — senão relabela/reposiciona a decisão de OUTRA conta.

Reproduz a colisão que inflava a auditoria de posição (21 casos vs 8 reais): dois
torneios com o MESMO hand_id e posições diferentes; o match tem que ser cirúrgico.
"""
import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _db():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE decisions (id INTEGER PRIMARY KEY, tournament_id INT, "
              "hand_id TEXT, street TEXT, action_taken TEXT, label TEXT, "
              "position TEXT, vs_position TEXT)")
    # Mesmo hand_id 'H1' em dois torneios distintos, com posições diferentes.
    c.executemany(
        "INSERT INTO decisions (tournament_id, hand_id, street, action_taken, label, position, vs_position) "
        "VALUES (?,?,?,?,?,?,?)",
        [(101, 'H1', 'preflop', 'raise', 'standard',      'BB',  'SB'),
         (202, 'H1', 'preflop', 'raise', 'small_mistake', 'UTG', 'unknown')])
    c.commit()
    return c


# A query EXATA do endpoint (com o escopo por tournament_id).
_SCOPED = ("SELECT id, label, position, vs_position FROM decisions "
           "WHERE tournament_id = ? AND hand_id = ? AND street = 'preflop' "
           "AND action_taken = ? LIMIT 1")
_UNSCOPED = ("SELECT id, label, position, vs_position FROM decisions "
             "WHERE hand_id = ? AND street = 'preflop' AND action_taken = ? LIMIT 1")


def test_scoped_lookup_hits_the_right_tournament():
    c = _db()
    r101 = c.execute(_SCOPED, (101, 'H1', 'raise')).fetchone()
    r202 = c.execute(_SCOPED, (202, 'H1', 'raise')).fetchone()
    assert r101['position'] == 'BB', r101['position']
    assert r202['position'] == 'UTG', r202['position']
    assert r101['id'] != r202['id']
    print("OK  test_scoped_lookup_hits_the_right_tournament")


def test_unscoped_lookup_would_collide():
    """Documenta o bug: sem o escopo, os dois torneios casam a MESMA linha (a 1a)."""
    c = _db()
    a = c.execute(_UNSCOPED, ('H1', 'raise')).fetchone()
    b = c.execute(_UNSCOPED, ('H1', 'raise')).fetchone()
    assert a['id'] == b['id']  # sempre a mesma → a decisão do outro torneio nunca é vista
    print("OK  test_unscoped_lookup_would_collide")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
