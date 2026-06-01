"""
Testa o scanner determinístico de padrões suspeitos (pattern_scan.scan_patterns).
Insere decisões controladas e valida count + sample_ids por padrão.
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

from leaklab.revalidation.pattern_scan import scan_patterns
from leaklab.revalidation.orchestrator import Scope
from database.schema import init_db, get_conn
init_db()  # cria o schema uma vez no tempfile (LEAKLAB_DB)

_DEFAULTS = dict(
    hand_id='H1', street='preflop', action_taken='fold', label='standard',
    best_action='fold', score=0.0, gto_label=None, gto_action=None, position='BB',
    stack_bb=30.0, facing_bet=0.0, is_3bet=0, preflop_raises_faced=0,
    vs_position='SB', num_players=9, estimated_equity=0.30, hero_cards='AcKc',
)
_HN = [0]


def _setup(is_pko=0):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM decisions")
        conn.execute("DELETE FROM tournaments")
        conn.execute("DELETE FROM users")
        conn.execute("INSERT INTO users (username,email,password_hash) VALUES (?,?,?)",
                     ('pu', 'pu@t', 'x'))
        uid = dict(conn.execute("SELECT id FROM users WHERE username='pu'").fetchone())['id']
        conn.execute("INSERT INTO tournaments (user_id,tournament_id,hero,raw_text,site,is_pko) "
                     "VALUES (?,?,?,?,?,?)", (uid, 'T1', 'H', 'raw', 'pokerstars', is_pko))
        tid = dict(conn.execute("SELECT id FROM tournaments WHERE tournament_id='T1'").fetchone())['id']
        conn.commit()
    finally:
        conn.close()
    _HN[0] = 0
    return uid, tid


def _ins(tid, **kw):
    cols = dict(_DEFAULTS)
    cols.update(kw)
    cols['tournament_id'] = tid
    if 'hand_id' not in kw:
        _HN[0] += 1
        cols['hand_id'] = f'H{_HN[0]}'
    conn = get_conn()
    try:
        keys = list(cols.keys()); ph = ','.join('?' * len(keys))
        conn.execute(f"INSERT INTO decisions ({','.join(keys)}) VALUES ({ph})",
                     tuple(cols[k] for k in keys))
        conn.commit()
    finally:
        conn.close()


def _by_key(scope):
    return {p.key: p for p in scan_patterns(scope)}


def test_faces_3bet_leftover_and_gto_critical_fold():
    _uid, tid = _setup()
    # squeeze enfrentado a frio ainda com gto_label + fold marcado critical
    _ins(tid, preflop_raises_faced=2, is_3bet=0, gto_label='gto_critical', gto_action='call',
         action_taken='fold')
    _ins(tid, preflop_raises_faced=0, gto_label='gto_correct', action_taken='call')  # negativo
    pf = _by_key(Scope.for_tournament(tid))
    assert pf['faces_3bet_leftover'].count == 1 and len(pf['faces_3bet_leftover'].sample_ids) == 1
    assert pf['gto_critical_fold'].count == 1
    print("OK  test_faces_3bet_leftover_and_gto_critical_fold")


def test_label_gto_conflict():
    _uid, tid = _setup()
    _ins(tid, label='small_mistake', gto_label='gto_correct')
    _ins(tid, label='clear_mistake', gto_label='gto_mixed')
    _ins(tid, label='standard', gto_label='gto_correct')  # negativo
    assert _by_key(Scope.for_tournament(tid))['label_gto_conflict'].count == 2
    print("OK  test_label_gto_conflict")


def test_impossible_raise_and_gto_label_no_action():
    _uid, tid = _setup()
    _ins(tid, best_action='raise', facing_bet=29.0, stack_bb=30.0)  # 29 >= 0.95*30=28.5
    _ins(tid, best_action='raise', facing_bet=5.0, stack_bb=30.0)   # negativo
    _ins(tid, gto_label='gto_correct', gto_action=None)             # sem action
    pf = _by_key(Scope.for_tournament(tid))
    assert pf['impossible_raise'].count == 1 and pf['impossible_raise'].severity == 'critical'
    assert pf['gto_label_no_action'].count >= 1
    print("OK  test_impossible_raise_and_gto_label_no_action")


def test_postflop_raise_no_bet_and_multiway():
    _uid, tid = _setup()
    _ins(tid, street='flop', best_action='raise', facing_bet=0.0)
    _ins(tid, street='turn', num_players=4, estimated_equity=0.70)
    pf = _by_key(Scope.for_tournament(tid))
    assert pf['postflop_raise_no_bet'].count == 1
    assert pf['multiway_highequity'].count == 1
    print("OK  test_postflop_raise_no_bet_and_multiway")


def test_missing_hero_cards_and_postflop_mistake_no_gto():
    _uid, tid = _setup()
    _ins(tid, hero_cards='')
    _ins(tid, street='river', label='clear_mistake', gto_label=None)
    pf = _by_key(Scope.for_tournament(tid))
    assert pf['missing_hero_cards'].count == 1
    assert pf['postflop_mistake_no_gto'].count == 1
    print("OK  test_missing_hero_cards_and_postflop_mistake_no_gto")


def test_duplicate_decisions():
    _uid, tid = _setup()
    _ins(tid, hand_id='DUP', street='preflop', action_taken='call', label='standard')
    _ins(tid, hand_id='DUP', street='preflop', action_taken='raise', label='standard')
    assert _by_key(Scope.for_tournament(tid))['duplicate_decisions'].count == 1
    print("OK  test_duplicate_decisions")


def test_pko_caveat():
    _uid, tid = _setup(is_pko=1)
    _ins(tid)
    _ins(tid)
    p = _by_key(Scope.for_tournament(tid))['pko_classic_ranges']
    assert p.severity == 'caveat' and p.count == 2
    print("OK  test_pko_caveat")


def test_scope_isolates_tournament():
    _uid, tid = _setup()
    _ins(tid, gto_label='gto_critical', action_taken='fold')
    # outro torneio sem o padrão
    conn = get_conn()
    conn.execute("INSERT INTO tournaments (user_id,tournament_id,hero,raw_text,site) "
                 "VALUES (?,?,?,?,?)", (_uid, 'T2', 'H', 'raw', 'pokerstars'))
    conn.commit(); conn.close()
    assert _by_key(Scope.for_tournament(tid))['gto_critical_fold'].count == 1
    print("OK  test_scope_isolates_tournament")


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
