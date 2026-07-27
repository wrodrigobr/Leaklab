"""
Detector de drift de confiança — o alerta que aparecia sempre.

A regra original marcava toda sessão 30% acima da MÉDIA da própria janela. Medido no banco de
dev: um jogador perfeitamente uniforme tinha 2 de 17 sessões marcadas, porque a média é puxada
pelas próprias sessões ruins e elas continuam acima dela. Alerta que aparece sempre treina o
jogador a ignorar alertas — e aí o dia em que ele importa também passa batido.

O que estes testes protegem é o silêncio: o detector tem que ficar CALADO quando não há nada a
dizer, e falar quando há.
"""
import sys, os, traceback, tempfile, sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo

TEST_DB = tempfile.mktemp(suffix='.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()

from database.repositories import (  # noqa: E402
    get_confidence_drift, DRIFT_MIN_DECISIONS, DRIFT_MIN_SESSIONS, DRIFT_MIN_ABS,
)


def _sessoes(scores_e_n):
    """Monta o histórico do usuário 800: lista de (avg_score_alvo, n_decisões)."""
    conn = _conn()
    try:
        conn.execute('DELETE FROM decisions')
        conn.execute('DELETE FROM tournaments')
        conn.execute('DELETE FROM users')
        conn.execute("INSERT INTO users (id, username, email, password_hash, role) "
                     "VALUES (800, 'drift', 'd@x.com', 'x', 'player')")
        for i, (score, n) in enumerate(scores_e_n):
            tid = 8000 + i
            conn.execute(
                "INSERT INTO tournaments (id, user_id, tournament_id, hero, site, played_at, "
                "imported_at) VALUES (?, 800, ?, 'h', 'PokerStars', '2026-07-01', "
                "datetime('now'))", (tid, f'T{i}'))
            for j in range(n):
                conn.execute(
                    "INSERT INTO decisions (tournament_id, hand_id, street, action_taken, "
                    "best_action, label, score) VALUES (?, ?, 'preflop', 'call', 'call', "
                    "'standard', ?)", (tid, f'H{i}-{j}', score))
        conn.commit()
    finally:
        conn.close()


N = DRIFT_MIN_DECISIONS  # amostra suficiente por sessão


def test_jogador_uniforme_nao_dispara():
    """O caso do relato: variação normal não é tilt. Sob a regra antiga isto disparava."""
    _sessoes([(0.050, N), (0.055, N), (0.060, N), (0.052, N), (0.058, N), (0.061, N)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is False, d
    print("OK  test_jogador_uniforme_nao_dispara")


def test_sessao_claramente_pior_dispara():
    """O detector não pode ficar mudo: sessão ao DOBRO da mediana é o que ele existe pra achar."""
    _sessoes([(0.050, N), (0.055, N), (0.060, N), (0.052, N), (0.058, N), (0.130, N)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is True, d
    assert d['affected_sessions'] == 1, d
    print("OK  test_sessao_claramente_pior_dispara")


def test_piso_absoluto_mata_o_ruido_de_escala():
    """30% acima de quase nada é quase nada. Todos os scores minúsculos: relativo passa,
    absoluto não — e o alerta cala."""
    _sessoes([(0.002, N), (0.002, N), (0.003, N), (0.002, N), (0.002, N), (0.010, N)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is False, d
    print("OK  test_piso_absoluto_mata_o_ruido_de_escala")


def test_sessao_curta_nao_conta():
    """Média de poucas mãos não é média. A sessão ruim tem amostra abaixo do mínimo."""
    _sessoes([(0.050, N), (0.055, N), (0.060, N), (0.052, N), (0.058, N),
              (0.200, DRIFT_MIN_DECISIONS - 1)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is False, d
    print("OK  test_sessao_curta_nao_conta")


def test_poucas_sessoes_nao_tem_baseline():
    """Sem janela mínima não há do que tirar baseline: calar é mais honesto que chutar."""
    _sessoes([(0.050, N), (0.200, N)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is False, d
    print("OK  test_poucas_sessoes_nao_tem_baseline")


def test_metade_da_janela_marcada_nao_e_tilt():
    """Se quase tudo é 'anômalo', o anômalo é o baseline. 'Possível tilt ou fadiga' não
    descreve um jogador simplesmente irregular."""
    _sessoes([(0.050, N), (0.052, N), (0.055, N),
              (0.200, N), (0.210, N), (0.220, N)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is False, d
    print("OK  test_metade_da_janela_marcada_nao_e_tilt")


def test_mediana_e_nao_media():
    """A mediana ignora os outliers; a média é puxada por eles. Com uma sessão MUITO ruim, a
    média subiria tanto que sessões medianas ficariam 'normais' — e a péssima, quase no
    limiar. Com mediana, a péssima é marcada e o resto fica de fora."""
    _sessoes([(0.050, N), (0.050, N), (0.050, N), (0.050, N), (0.050, N), (0.500, N)])
    d = get_confidence_drift(800, days=3650)
    assert d['drift_detected'] is True and d['affected_sessions'] == 1, d
    assert abs(d['baseline_score'] - 0.050) < 0.005, d['baseline_score']
    print("OK  test_mediana_e_nao_media")


def test_campos_do_contrato_seguem_presentes():
    """A marca d'água do dismiss depende de `latest_flagged_id` existir SEMPRE."""
    _sessoes([(0.050, N), (0.055, N)])
    d = get_confidence_drift(800, days=3650)
    for k in ('drift_detected', 'affected_sessions', 'severity', 'sessions', 'latest_flagged_id'):
        assert k in d, k
    print("OK  test_campos_do_contrato_seguem_presentes")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
