"""Gamificação de treino (Fase 1) — domínio por categoria (eixo SEPARADO do ELO).

Valida a matemática do mastery (EMA × fator de volume), os tiers, o delta antes→depois
e a listagem. DB isolado (LEAKLAB_DB temp).
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
from database.repositories import (
    record_training_attempt, get_training_skills, _mastery_tier, get_all_achievements,
    evaluate_training_achievements, get_training_achievements, _TRAINING_ACHIEVEMENT_DEFS,
    record_daily_mission_progress, get_daily_missions, training_readiness,
    get_training_proof,
)
from leaklab.leak_trainer import build_curriculum
init_db()


def _mk_user():
    c = get_conn()
    c.execute("DELETE FROM decisions")        # FK: decisions→tournaments→users (limpar antes de users)
    c.execute("DELETE FROM tournaments")
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM training_skill_progress")
    c.execute("DELETE FROM training_achievements")
    c.execute("DELETE FROM training_daily")
    try: c.execute("DELETE FROM training_proof")
    except Exception: pass
    c.execute("INSERT INTO users (username,email,password_hash,plan) VALUES (?,?,?,?)",
              ('tg', 'tg@t', 'x', 'free'))
    uid = dict(c.execute("SELECT id FROM users WHERE username='tg'").fetchone())['id']
    c.commit(); c.close()
    return uid


def test_tier_boundaries():
    assert _mastery_tier(0) == 'bronze'
    assert _mastery_tier(39.9) == 'bronze'
    assert _mastery_tier(40) == 'silver'
    assert _mastery_tier(69.9) == 'silver'
    assert _mastery_tier(70) == 'gold'
    assert _mastery_tier(89.9) == 'gold'
    assert _mastery_tier(90) == 'diamond'
    print("OK  test_tier_boundaries")


def test_first_attempt_low_mastery_volume_gated():
    """1 acerto não vira Ouro: o fator de volume (1/20) segura — exige reps."""
    uid = _mk_user()
    r = record_training_attempt(uid, 'rfi:BB::50', True)
    assert r['attempts'] == 1 and r['correct'] == 1
    assert abs(r['mastery'] - 5.0) < 0.01, r          # ema=1 × 1/20 × 100
    assert r['tier'] == 'bronze'
    assert r['mastery_prev'] == 0.0 and r['mastery_delta'] == 5.0
    print("OK  test_first_attempt_low_mastery_volume_gated")


def test_sustained_correct_reaches_diamond():
    """20 acertos seguidos → volume satura (1.0) + ema=1 → mastery 100 → diamante."""
    uid = _mk_user()
    last = None
    for _ in range(20):
        last = record_training_attempt(uid, 'rfi:BB::50', True)
    assert last['attempts'] == 20
    assert abs(last['mastery'] - 100.0) < 0.01, last
    assert last['tier'] == 'diamond'
    print("OK  test_sustained_correct_reaches_diamond")


def test_wrong_attempt_lowers_mastery():
    uid = _mk_user()
    for _ in range(20):
        record_training_attempt(uid, 'rfi:BB::50', True)
    before = get_training_skills(uid)[0]['mastery']
    after = record_training_attempt(uid, 'rfi:BB::50', False)
    assert after['mastery'] < before, (before, after['mastery'])
    assert after['mastery_delta'] < 0
    print("OK  test_wrong_attempt_lowers_mastery")


def test_get_training_skills_lists_categories():
    uid = _mk_user()
    record_training_attempt(uid, 'rfi:BB::50', True)
    record_training_attempt(uid, 'pf:bb_defense', True)
    skills = get_training_skills(uid)
    keys = {s['category_key'] for s in skills}
    assert keys == {'rfi:BB::50', 'pf:bb_defense'}, skills
    assert all('tier' in s and 'mastery' in s for s in skills)
    print("OK  test_get_training_skills_lists_categories")


def test_isolation_by_category():
    """Acertar uma categoria não move o domínio de outra."""
    uid = _mk_user()
    record_training_attempt(uid, 'rfi:BB::50', True)
    r2 = record_training_attempt(uid, 'pf:bb_defense', True)
    assert r2['attempts'] == 1, r2   # categoria nova começa do zero
    print("OK  test_isolation_by_category")


def test_all_achievements_path_locked_then_unlocked():
    """Catálogo completo de conquistas: tudo travado no início; ao ganhar uma, vira unlocked."""
    uid = _mk_user()
    allac = get_all_achievements(uid)
    assert len(allac) > 0 and all(not a['unlocked'] for a in allac), "tudo travado no início"
    key = allac[0]['key']
    c = get_conn()
    c.execute("INSERT INTO achievements (user_id, achievement_key, earned_at) VALUES (?,?,datetime('now'))",
              (uid, key))
    c.commit(); c.close()
    allac2 = get_all_achievements(uid)
    unlocked = [a for a in allac2 if a['unlocked']]
    assert len(unlocked) == 1 and unlocked[0]['key'] == key, allac2
    assert len(allac2) == len(allac), "o catálogo não muda de tamanho, só o flag"
    print("OK  test_all_achievements_path_locked_then_unlocked")


def test_training_achievements_locked_then_award():
    """Conquistas de treino começam travadas; acertos/domínio destravam as certas."""
    uid = _mk_user()
    ach0 = get_training_achievements(uid)
    assert len(ach0) == len(_TRAINING_ACHIEVEMENT_DEFS) and all(not a['unlocked'] for a in ach0)
    # 1 acerto → 'train:first' (e nada de tier ainda, mastery=5)
    record_training_attempt(uid, 'rfi:BB::50', True)
    newly = evaluate_training_achievements(uid)
    assert 'train:first' in newly, newly
    assert 'train:silver' not in newly and 'train:gold' not in newly, newly
    # idempotente: avaliar de novo sem progресso não concede nada
    assert evaluate_training_achievements(uid) == []
    print("OK  test_training_achievements_locked_then_award")


def test_training_achievements_tier_and_volume():
    """20 acertos → diamante → destrava silver+gold+diamond; reps50 só com 50 tentativas."""
    uid = _mk_user()
    for _ in range(20):
        record_training_attempt(uid, 'rfi:BB::50', True)
    got = set(evaluate_training_achievements(uid))
    assert {'train:first', 'train:silver', 'train:gold', 'train:diamond'} <= got, got
    assert 'train:reps50' not in got, "20 < 50 tentativas"
    for _ in range(30):
        record_training_attempt(uid, 'rfi:BB::50', True)   # total 50
    assert 'train:reps50' in set(evaluate_training_achievements(uid))
    # catálogo reflete o estado
    unlocked = {a['key'] for a in get_training_achievements(uid) if a['unlocked']}
    assert 'train:diamond' in unlocked and 'train:reps50' in unlocked
    print("OK  test_training_achievements_tier_and_volume")


def test_daily_missions_progress_and_award():
    """Missões do dia: progresso derivado de spots/correct, auto-resgate, idempotência."""
    uid = _mk_user()
    m0 = get_daily_missions(uid)
    assert {m['key'] for m in m0} == {'m_lesson', 'm_correct', 'm_grind'}
    assert all(m['progress'] == 0 and not m['completed'] for m in m0)
    got = []
    for _ in range(10):                       # 10 spots corretos → m_lesson (10 spots)
        got += record_daily_mission_progress(uid, True)
    assert any(m['key'] == 'm_lesson' for m in got), got
    # idempotente: 11ª não re-concede m_lesson
    assert all(m['key'] != 'm_lesson' for m in record_daily_mission_progress(uid, True))
    got2 = []
    for _ in range(4):                        # correct chega a 15 → m_correct
        got2 += record_daily_mission_progress(uid, True)
    assert any(m['key'] == 'm_correct' for m in got2), got2
    dm = {m['key']: m for m in get_daily_missions(uid)}
    assert dm['m_lesson']['completed'] and dm['m_correct']['completed']
    assert not dm['m_grind']['completed']     # 16 < 30 spots
    print("OK  test_daily_missions_progress_and_award")


def _seed_leaks(uid, n_tourneys, n_leak_cats):
    """Cria n_tourneys torneios (imported_at=agora) e mete n_leak_cats categorias de leak RFI
    distintas (>=2 decisões cada, ev_loss crescente → ordena por custo). Controla o ESTÁGIO
    (nº de torneios) e o denominador (nº de leaks reais medidos)."""
    c = get_conn()
    c.execute("DELETE FROM decisions"); c.execute("DELETE FROM tournaments")
    c.execute("DELETE FROM training_skill_progress WHERE user_id=?", (uid,))
    positions = ['UTG', 'HJ', 'CO', 'BTN', 'SB']
    tids = []
    for i in range(n_tourneys):
        c.execute("INSERT INTO tournaments (user_id,tournament_id,hero,raw_text,site,imported_at) "
                  "VALUES (?,?,?,?,?,datetime('now'))", (uid, f'T{i}', 'H', 'raw', 'pokerstars'))
        tids.append(dict(c.execute("SELECT id FROM tournaments WHERE tournament_id=? AND user_id=?",
                                    (f'T{i}', uid)).fetchone())['id'])
    cols = ("(tournament_id,hand_id,street,action_taken,best_action,position,vs_position,"
            "is_3bet,preflop_raises_faced,ev_loss_bb,stack_bb,label,score)")
    hid = 0
    for ci in range(n_leak_cats):
        pos = positions[ci % len(positions)]
        for _ in range(2):                       # >=2 p/ passar no HAVING COUNT>=2
            hid += 1
            c.execute(f"INSERT INTO decisions {cols} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (tids[0], f'H{hid}', 'preflop', 'fold', 'raise', pos, '', 0, 0,
                       1.0 + ci, 50, 'clear_mistake', 0.8))
    c.commit(); c.close()


def _seed_proof_decisions(uid, tournament_id, imported_at, n_correct, n_wrong):
    """Cria 1 torneio (imported_at controlado) com decisões RFI de UTG (rfi:UTG::*), n_correct
    alinhadas (gto_correct) + n_wrong erradas (gto_critical), pra medir aderência da categoria."""
    c = get_conn()
    c.execute("INSERT INTO tournaments (user_id,tournament_id,hero,raw_text,site,imported_at) "
              "VALUES (?,?,?,?,?,?)", (uid, tournament_id, 'H', 'raw', 'pokerstars', imported_at))
    tid = dict(c.execute("SELECT id FROM tournaments WHERE tournament_id=? AND user_id=?",
                         (tournament_id, uid)).fetchone())['id']
    cols = ("(tournament_id,hand_id,street,action_taken,best_action,position,vs_position,is_3bet,"
            "preflop_raises_faced,score,label,gto_label)")
    hid = 0
    for lbl, cnt in (('gto_correct', n_correct), ('gto_critical', n_wrong)):
        for _ in range(cnt):
            hid += 1
            c.execute(f"INSERT INTO decisions {cols} VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (tid, f'{tournament_id}H{hid}', 'preflop', 'raise', 'raise', 'UTG', '', 0, 0,
                       0.0, 'standard', lbl))
    c.commit(); c.close()
    return tid


def test_training_proof_before_after():
    """Fase 4: aderência da categoria ANTES (baseline congelado) × DEPOIS (torneio importado após).
    Só conta torneio pós-baseline; snapshot = o último; delta é comparação honesta."""
    uid = _mk_user()
    key = 'rfi:UTG::100'
    c = get_conn()
    c.execute("INSERT INTO training_skill_progress (user_id,category_key,attempts,correct,mastery_ema,mastery) "
              "VALUES (?,?,?,?,?,?)", (uid, key, 5, 3, 0.6, 30.0))
    c.commit(); c.close()
    # ANTES: torneio antigo, aderência 25% (1 certo / 3 errados); baseline congelado depois dele
    _seed_proof_decisions(uid, 'BEFORE', '2020-01-01 00:00:00', n_correct=1, n_wrong=3)
    c = get_conn()
    c.execute("INSERT INTO training_proof (user_id,category_key,baseline_pct,baseline_n,baseline_at) "
              "VALUES (?,?,?,?,?)", (uid, key, 25.0, 4, '2020-06-01 00:00:00'))
    c.commit(); c.close()
    # sem torneio novo pós-baseline → ainda não prova
    assert get_training_proof(uid) == []
    # DEPOIS: torneio novo (pós-baseline), aderência 100% (12 certos)
    _seed_proof_decisions(uid, 'AFTER', '2020-12-01 00:00:00', n_correct=12, n_wrong=0)
    proof = get_training_proof(uid)
    assert len(proof) == 1, proof
    p = proof[0]
    assert p['category_key'] == key
    assert p['baseline_pct'] == 25.0 and p['baseline_n'] == 4
    assert p['after_pct'] == 100.0 and p['after_n'] == 12      # só o torneio AFTER
    assert p['delta'] == 75.0 and p['confident'] is True        # 12 >= _TRAIN_PROOF_MIN_N
    assert p['snapshot'] and p['snapshot']['tournament_id'] == 'AFTER' and p['snapshot']['pct'] == 100.0
    print("OK  test_training_proof_before_after")


def test_retention_factor_curve():
    """Decaimento: 1.0 na carência, ~0.5 uma meia-vida depois, piso no muito antigo, 1.0 se NULL."""
    from database.repositories import _retention_factor, _TRAIN_DECAY_FLOOR
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    fmt = lambda d: d.strftime('%Y-%m-%d %H:%M:%S')
    assert _retention_factor(fmt(now)) == 1.0
    assert _retention_factor(fmt(now - timedelta(days=3))) == 1.0          # dentro da carência (7d)
    f28 = _retention_factor(fmt(now - timedelta(days=28)))                 # 7 carência + 21 meia-vida
    assert abs(f28 - 0.5) < 0.05, f28
    assert _retention_factor('2000-01-01 00:00:00') == _TRAIN_DECAY_FLOOR  # muito antigo → piso
    assert _retention_factor(None) == 1.0
    print("OK  test_retention_factor_curve")


def test_mastery_decay_read_and_resume():
    """Domínio abandonado decai na LEITURA (tira do topo) e ao RETOMAR (1 rep não restaura tudo).
    Conquistas usam o pico (mastery_stored), não decaem."""
    uid = _mk_user()
    c = get_conn()
    c.execute("INSERT INTO training_skill_progress "
              "(user_id,category_key,attempts,correct,mastery_ema,mastery,last_practiced_at) "
              "VALUES (?,?,?,?,?,?,?)", (uid, 'rfi:UTG::100', 25, 25, 1.0, 100.0, '2020-01-01 00:00:00'))
    c.commit(); c.close()
    sk = {s['category_key']: s for s in get_training_skills(uid)}['rfi:UTG::100']
    assert sk['mastery_stored'] == 100.0                    # pico preservado (conquistas)
    assert sk['mastery'] <= 40.0 and sk['stale'] is True    # leitura decaída ao piso (0.4×100)
    assert sk['tier'] in ('silver', 'bronze')               # saiu do Diamante → gate re-trava
    r = record_training_attempt(uid, 'rfi:UTG::100', True)  # retoma: parte do decaído
    assert r['mastery_prev'] <= 40.0 and r['mastery'] < 100.0, r
    print("OK  test_mastery_decay_read_and_resume")


def test_readiness_untrained_leaks():
    """`untrained` = leaks reais do jogo que NUNCA foram treinados (sinal de "novos leaks, reinicie")."""
    uid = _mk_user()
    _seed_leaks(uid, n_tourneys=8, n_leak_cats=4)
    keys = [c['key'] for c in build_curriculum(uid) if int(c.get('n') or 0) > 0]
    assert len(keys) == 4
    for k in keys[:2]:                       # treina só 2 dos 4
        record_training_attempt(uid, k, True)
    r = training_readiness(uid)
    assert set(r['untrained']) == set(keys[2:]), r['untrained']   # os 2 não-treinados
    print("OK  test_readiness_untrained_leaks")


def test_readiness_beginner_stage():
    """Iniciante (poucos/nenhum torneio, sem leaks medidos): meta é JOGAR/importar, não Diamante."""
    uid = _mk_user()
    r = training_readiness(uid)
    assert r['stage'] == 'beginner' and r['ready'] is False
    assert r['target'] == 5 and r['total'] == 5 and r['done'] == 0
    assert r['target_tier'] is None and r['pending'] == []
    # 3 torneios (<5) mas com leaks → ainda iniciante (dado insuficiente)
    _seed_leaks(uid, n_tourneys=3, n_leak_cats=2)
    r2 = training_readiness(uid)
    assert r2['stage'] == 'beginner' and r2['done'] == 3, r2
    print("OK  test_readiness_beginner_stage")


def test_readiness_developing_top3_gold():
    """Em formação (5–14 torneios): só os TOP-3 leaks mais custosos, no Ouro."""
    uid = _mk_user()
    _seed_leaks(uid, n_tourneys=8, n_leak_cats=4)
    r = training_readiness(uid)
    assert r['stage'] == 'developing' and r['target_tier'] == 'gold'
    assert r['total'] == 3 and r['ready'] is False, r      # top-3, não os 4
    keys = [c['key'] for c in build_curriculum(uid) if int(c.get('n') or 0) > 0]
    for k in keys[:3]:                                     # domina os 3 principais no Ouro+
        for _ in range(20):
            record_training_attempt(uid, k, True)
    r2 = training_readiness(uid)
    assert r2['done'] == 3 and r2['ready'] is True, r2
    print("OK  test_readiness_developing_top3_gold")


def test_readiness_consolidated_all_diamond():
    """Consolidado (15+ torneios): TODOS os leaks reais no Diamante."""
    uid = _mk_user()
    _seed_leaks(uid, n_tourneys=15, n_leak_cats=3)
    r = training_readiness(uid)
    assert r['stage'] == 'consolidated' and r['target_tier'] == 'diamond'
    assert r['total'] == 3 and r['ready'] is False, r
    keys = [c['key'] for c in build_curriculum(uid) if int(c.get('n') or 0) > 0]
    for k in keys[:-1]:                                    # todas menos uma → ainda bloqueado
        for _ in range(20):
            record_training_attempt(uid, k, True)
    assert training_readiness(uid)['ready'] is False
    for _ in range(20):                                    # fecha a última
        record_training_attempt(uid, keys[-1], True)
    r2 = training_readiness(uid)
    assert r2['done'] == r2['total'] and r2['ready'] is True and r2['pending'] == [], r2
    print("OK  test_readiness_consolidated_all_diamond")


def test_daily_missions_timezone_aware():
    """Reset das missões à meia-noite LOCAL: record/get usam o dia no fuso do jogador. Um fuso
    vê o progresso; outro fuso (que está em outra data) vê zerado."""
    from database.repositories import _today_str
    assert _today_str(-840) != _today_str(840)          # -14h e +14h nunca no mesmo dia
    uid = _mk_user()
    record_daily_mission_progress(uid, True, -840)      # conta no "hoje" do fuso A
    ma = {m['key']: m for m in get_daily_missions(uid, -840)}
    mb = {m['key']: m for m in get_daily_missions(uid, 840)}   # fuso B = outra data
    assert ma['m_lesson']['progress'] == 1, ma
    assert mb['m_lesson']['progress'] == 0, mb            # não vaza entre dias/fusos
    print("OK  test_daily_missions_timezone_aware")


if __name__ == '__main__':
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
