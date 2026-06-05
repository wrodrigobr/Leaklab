"""
Testa a captura de DRIFT (recompute fresco vs verdicto armazenado) do orchestrator:
funções puras _drift_against_stored / _norm_gto + _fetch_stored_decisions (DB).
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name

from leaklab.revalidation.orchestrator import (
    _drift_against_stored, _norm_gto, _fetch_stored_decisions, Scope,
)
from database.schema import init_db, get_conn
init_db()


def _engine(label='standard', best='fold', gto_available=True,
            gto_label='gto_correct', gto_action='fold'):
    gto = {'available': gto_available}
    if gto_available:
        gto.update({'gto_label': gto_label, 'gto_action': gto_action})
    return {'evaluation': {'label': label}, 'bestAction': best, 'gto': gto}


def _di(street='preflop', action='fold', vs=''):
    return {'street': street, 'player_action': action,
            'spot': {'villainPosition': vs}}


def _idx(stored, dups=None, vs=''):
    k = ('H1', 'preflop', 'fold', vs.lower())
    d = {k: stored} if stored is not None else {}
    d['__dups__'] = dups or set()
    return d


def test_no_drift_when_match():
    stored = {'label': 'standard', 'best_action': 'fold',
              'gto_label': 'gto_correct', 'gto_action': 'fold'}
    r = _drift_against_stored(_engine(), _di(), 'H1', _idx(stored))
    assert r['stored_found'] is True
    assert r['drift'] is False and r['drift_fields'] == []
    print("OK  test_no_drift_when_match")


def test_label_drift_detected():
    stored = {'label': 'small_mistake', 'best_action': 'call',
              'gto_label': 'gto_correct', 'gto_action': 'fold'}
    r = _drift_against_stored(_engine(label='standard', best='fold'), _di(), 'H1', _idx(stored))
    assert r['drift'] is True
    assert 'label' in r['drift_fields'] and 'best_action' in r['drift_fields']
    print("OK  test_label_drift_detected")


def test_vs_position_disambiguates():
    # Dois spots no mesmo (hand,street,action) — só vs_position separa. O fresco
    # vs=SB deve casar a linha SB (não a CO) → sem drift falso.
    co = {'label': 'small_mistake', 'best_action': 'fold',
          'gto_label': 'gto_critical', 'gto_action': 'fold'}
    sb = {'label': 'standard', 'best_action': 'call',
          'gto_label': None, 'gto_action': None}
    idx = {('H1', 'preflop', 'call', 'co'): co,
           ('H1', 'preflop', 'call', 'sb'): sb, '__dups__': set()}
    fresh = _engine(label='standard', best='call', gto_available=False)
    r = _drift_against_stored(fresh, _di(action='call', vs='SB'), 'H1', idx)
    assert r['stored_found'] is True
    assert r['stored_label'] == 'standard'   # casou a linha SB, não a CO
    assert r['drift'] is False and r['drift_fields'] == []
    print("OK  test_vs_position_disambiguates")


def test_stale_gto_uncovered_tagged():
    # Armazenado tinha gto_label; fresco perdeu cobertura (available=False).
    stored = {'label': 'standard', 'best_action': 'fold',
              'gto_label': 'gto_critical', 'gto_action': 'call'}
    r = _drift_against_stored(_engine(gto_available=False), _di(), 'H1', _idx(stored))
    assert r['drift'] is True
    assert 'gto_label' in r['drift_fields']
    assert 'gto_label:stale->NULL' in r['drift_fields']
    assert r['fresh_gto_label'] is None
    print("OK  test_stale_gto_uncovered_tagged")


def test_empty_gto_not_drift():
    # '' armazenado vs None fresco não deve gerar drift (normalização).
    stored = {'label': 'standard', 'best_action': 'fold', 'gto_label': '', 'gto_action': ''}
    r = _drift_against_stored(_engine(gto_available=False), _di(), 'H1', _idx(stored))
    assert 'gto_label' not in r['drift_fields']
    assert r['drift'] is False
    print("OK  test_empty_gto_not_drift")


def test_stored_not_found():
    r = _drift_against_stored(_engine(), _di(), 'H1', _idx(None))
    assert r['stored_found'] is False and r['drift'] is False
    print("OK  test_stored_not_found")


def test_ambiguous_flag():
    stored = {'label': 'standard', 'best_action': 'fold',
              'gto_label': 'gto_correct', 'gto_action': 'fold'}
    r = _drift_against_stored(_engine(), _di(), 'H1',
                              _idx(stored, dups={('H1', 'preflop', 'fold', '')}))
    assert r['stored_ambiguous'] is True
    print("OK  test_ambiguous_flag")


def test_norm_gto():
    assert _norm_gto('') is None and _norm_gto(None) is None
    assert _norm_gto('  gto_correct ') == 'gto_correct'
    print("OK  test_norm_gto")


def test_fetch_stored_indexes_and_dups():
    conn = get_conn()
    conn.execute("DELETE FROM decisions")
    conn.execute("DELETE FROM tournaments")
    conn.execute("DELETE FROM users")
    conn.execute("INSERT INTO users (username,email,password_hash) VALUES (?,?,?)",
                 ('du', 'du@t', 'x'))
    uid = dict(conn.execute("SELECT id FROM users WHERE username='du'").fetchone())['id']
    conn.execute("INSERT INTO tournaments (user_id,tournament_id,hero,raw_text,site) "
                 "VALUES (?,?,?,?,?)", (uid, 'TD', 'H', 'raw', 'pokerstars'))
    tid = dict(conn.execute("SELECT id FROM tournaments WHERE tournament_id='TD'").fetchone())['id']
    _dcols = "(tournament_id,hand_id,street,action_taken,vs_position,best_action,label,score)"
    # mesma chave 2x COM o mesmo vs_position → ambíguo de verdade
    for lbl in ('standard', 'small_mistake'):
        conn.execute(f"INSERT INTO decisions {_dcols} VALUES (?,?,?,?,?,?,?,?)",
                     (tid, 'HX', 'preflop', 'fold', 'CO', 'fold', lbl, 0.0))
    # mesma (hand,street,action) mas vs_position DIFERENTE → NÃO é ambíguo
    conn.execute(f"INSERT INTO decisions {_dcols} VALUES (?,?,?,?,?,?,?,?)",
                 (tid, 'HZ', 'preflop', 'call', 'CO', 'call', 'standard', 0.0))
    conn.execute(f"INSERT INTO decisions {_dcols} VALUES (?,?,?,?,?,?,?,?)",
                 (tid, 'HZ', 'preflop', 'call', 'SB', 'call', 'small_mistake', 0.0))
    conn.execute(f"INSERT INTO decisions {_dcols} VALUES (?,?,?,?,?,?,?,?)",
                 (tid, 'HY', 'flop', 'call', '', 'call', 'standard', 0.0))
    conn.commit(); conn.close()

    idx = _fetch_stored_decisions(Scope.for_tournament(tid))
    assert ('HX', 'preflop', 'fold', 'co') in idx
    assert idx[('HX', 'preflop', 'fold', 'co')]['label'] == 'standard'  # mantém o 1º
    assert ('HX', 'preflop', 'fold', 'co') in idx['__dups__']           # marcado ambíguo
    # HZ: 2 spots desambiguados por vs_position → AMBOS indexados, nenhum ambíguo
    assert idx[('HZ', 'preflop', 'call', 'co')]['label'] == 'standard'
    assert idx[('HZ', 'preflop', 'call', 'sb')]['label'] == 'small_mistake'
    assert ('HZ', 'preflop', 'call', 'co') not in idx['__dups__']
    assert ('HZ', 'preflop', 'call', 'sb') not in idx['__dups__']
    assert ('HY', 'flop', 'call', '') in idx
    print("OK  test_fetch_stored_indexes_and_dups")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    try: os.unlink(_TMPDB.name)
    except Exception: pass
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
