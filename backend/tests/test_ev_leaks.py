"""
Testa get_ev_leaks (#24 Fase 5 / início do #25): leaks ranqueados por EV perdido
(bb), por spot. DB isolado (LEAKLAB_DB temp) — roda como subprocesso próprio.
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

from database.schema import init_db, get_conn
from database.repositories import get_ev_leaks, get_consolidated_leak_report
init_db()


def _seed():
    c = get_conn()
    c.execute("DELETE FROM decisions"); c.execute("DELETE FROM tournaments"); c.execute("DELETE FROM users")
    c.execute("INSERT INTO users (username,email,password_hash) VALUES (?,?,?)", ('evu', 'evu@t', 'x'))
    uid = dict(c.execute("SELECT id FROM users WHERE username='evu'").fetchone())['id']
    c.execute("INSERT INTO tournaments (user_id,tournament_id,hero,raw_text,site) VALUES (?,?,?,?,?)",
              (uid, 'TEV', 'H', 'raw', 'pokerstars'))
    tid = dict(c.execute("SELECT id FROM tournaments WHERE tournament_id='TEV'").fetchone())['id']
    # `ev_loss_source` é obrigatório desde que o ranking passou a exigir EV confiável: o plano de
    # estudos é ordenado por este número, e antes disso ele somava qualquer coisa — inclusive o
    # fold de −90bb que o relatório de evolução expôs.
    cols = ("(tournament_id,hand_id,street,action_taken,best_action,position,label,score,"
            "ev_loss_bb,ev_loss_source,stack_bb)")
    rows = [
        (tid, 'H1', 'preflop', 'fold', 'call', 'BB', 'clear_mistake', 0.8, 2.5, 'gw_har', 30),
        (tid, 'H2', 'preflop', 'fold', 'call', 'BB', 'clear_mistake', 0.8, 1.5, 'gw_har', 30),
        (tid, 'H3', 'preflop', 'raise', 'fold', 'BTN', 'clear_mistake', 0.8, 0.5, 'gw_har', 30),
        (tid, 'H4', 'preflop', 'raise', 'raise', 'UTG', 'standard', 0.0, 0.0, 'gw_har', 30),  # correto: ignorado
        (tid, 'H5', 'flop', 'call', 'fold', 'CO', 'clear_mistake', 0.8, None, None, 30),      # postflop sem EV
    ]
    for r in rows:
        c.execute(f"INSERT INTO decisions {cols} VALUES (?,?,?,?,?,?,?,?,?,?,?)", r)
    c.commit(); c.close()
    return uid


def test_ranks_by_total_ev_loss():
    uid = _seed()
    r = get_ev_leaks(uid, days=3650)
    # 3 spots com ev_loss > 0.05 (H1+H2 agrupam em BB/call; H3 BTN/fold). H4/H5 fora.
    assert r['n_leaks'] == 3, r['n_leaks']
    assert abs(r['total_ev_loss_bb'] - 4.5) < 0.01
    top = r['leaks'][0]
    assert top['position'] == 'BB' and top['ideal_action'] == 'call'
    assert top['n'] == 2 and abs(top['total_ev_loss_bb'] - 4.0) < 0.01
    # ranqueado por total: BB (4.0) antes de BTN (0.5)
    assert r['leaks'][1]['position'] == 'BTN'
    print("OK  test_ranks_by_total_ev_loss")


def test_excludes_zero_and_null():
    uid = _seed()
    r = get_ev_leaks(uid, days=3650)
    # nenhum spot correto (H4 ev=0) nem postflop sem EV (H5 NULL) entra
    assert all(l['avg_ev_loss_bb'] > 0 for l in r['leaks'])
    assert not any(l['street'] == 'flop' for l in r['leaks'])
    print("OK  test_excludes_zero_and_null")


def test_consolidated_report_severity():
    # #25: relatório consolidado adiciona severidade + top_leak + has_ev
    uid = _seed()
    r = get_consolidated_leak_report(uid, days=3650)
    assert r['has_ev'] is True and r['n_leaks'] == 3
    top = r['top_leak']
    assert top['position'] == 'BB' and top['ideal_action'] == 'call'
    # BB/call = 4.0bb < 5 → medium; nenhum spot sintético >= 5 → sem 'high' aqui
    assert top['severity'] == 'medium'
    # threshold: total >= 5 = high. Reforça um spot grande:
    c = get_conn()
    tid = dict(c.execute("SELECT id FROM tournaments WHERE tournament_id='TEV'").fetchone())['id']
    c.execute("INSERT INTO decisions (tournament_id,hand_id,street,action_taken,best_action,position,"
              "label,score,ev_loss_bb,ev_loss_source,stack_bb) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (tid, 'H6', 'preflop', 'fold', 'jam', 'UTG', 'clear_mistake', 0.8, 6.0, 'gw_har', 30))
    c.commit(); c.close()
    r2 = get_consolidated_leak_report(uid, days=3650)
    assert r2['top_leak']['position'] == 'UTG' and r2['top_leak']['severity'] == 'high'
    print("OK  test_consolidated_report_severity")


def test_plano_nao_ranqueia_por_ev_nao_confiavel():
    """REGRESSÃO: o plano de estudos é ordenado por `get_ev_leaks`, e ela não filtrava nada.

    O fold de −90,3bb que o relatório de evolução expôs (EV na escala do pote SOLVADO, ver
    `ev_loss_trustworthy`) estava dentro deste ranking, definindo o que o jogador estudaria
    primeiro. Um plano ordenado por ficção é pior que nenhum plano: manda trabalhar no lugar
    errado com a autoridade de quem mediu."""
    uid = _seed()
    c = get_conn()
    tid = dict(c.execute("SELECT id FROM tournaments WHERE tournament_id='TEV'").fetchone())['id']
    cols = ("(tournament_id,hand_id,street,action_taken,best_action,position,label,score,"
            "ev_loss_bb,ev_loss_source,stack_bb,estimated_equity,pot_size,facing_bet,icm_pressure)")
    # 1) fundo demais: acima do teto de calibração, o EV volta noutra escala
    c.execute(f"INSERT INTO decisions {cols} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (tid, 'FUNDO', 'flop', 'fold', 'call', 'CO', 'clear_mistake', 0.9,
               90.3, 'solver_hand', 139.3, 0.40, 60.0, 20.0, 'low'))
    # 2) fold impossível pela aritmética do próprio engine (equity 33% × 46,6% exigidos, quase all-in)
    c.execute(f"INSERT INTO decisions {cols} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (tid, 'IMPLAUS', 'flop', 'fold', 'call', 'HJ', 'clear_mistake', 0.9,
               28.2, 'solver_hand', 33.7, 0.330, 31.8, 27.8, 'low'))
    # 3) zona de ICM: gabarito chipEV puro não vale ali
    c.execute(f"INSERT INTO decisions {cols} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (tid, 'ICM', 'preflop', 'fold', 'call', 'SB', 'clear_mistake', 0.9,
               50.0, 'gw_har', 20.0, None, None, None, 'high'))
    c.commit(); c.close()

    posicoes = [l['position'] for l in get_ev_leaks(uid, days=3650)['leaks']]
    for intruso in ('CO', 'HJ', 'SB'):
        assert intruso not in posicoes, f"{intruso} entrou no ranking com EV não confiável: {posicoes}"
    assert posicoes and posicoes[0] == 'BB', posicoes   # o leak REAL segue no topo
    print("OK  test_plano_nao_ranqueia_por_ev_nao_confiavel")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    try:
        os.unlink(_TMPDB.name)
    except Exception:
        pass
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
