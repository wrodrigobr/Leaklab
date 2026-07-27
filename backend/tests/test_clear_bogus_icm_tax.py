"""
Limpeza do `icm_tax_pct` gravado quando a mesa não era o torneio.

O script apaga dado, então merece teste. O que ele desfaz: até 2026-07-27 o ICM real era calculado
sempre que a mesa tinha 2..9 assentos — em MTT 9-max, toda mão. A equity de premiação saía como se
os stacks visíveis fossem o torneio inteiro, e o número é lido pelo detector de cegueira ICM. Sem
limpar, o jogador segue sendo acusado de erro de ICM com base em algo que nunca descreveu a mesa.

O critério tem uma escolha embutida que este teste trava: torneio SEM `field_size` também é limpo.
Sem prova de que a mesa era o torneio, não afirmamos — e um resumo enviado depois repõe o valor
via `backfill_icm_tax.py`.
"""
import sys, os, tempfile, sqlite3, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo

TEST_DB = tempfile.mktemp(suffix='_bogus_icm.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()

import scripts.clear_bogus_icm_tax as script

# (id, nome externo, field_size)
_TORNEIOS = [(1, 'MTT500', 500), (2, 'SNG9', 9), (3, 'SEM_TS', None)]


def _setup():
    c = _conn()
    c.execute("DELETE FROM decisions")
    c.execute("DELETE FROM tournaments")
    c.execute("DELETE FROM users WHERE id = 1")
    c.execute("INSERT INTO users (id,username,email,password_hash) VALUES (1,'u','u@t.com','x')")
    for tid, ext, fs in _TORNEIOS:
        c.execute("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,field_size) "
                  "VALUES (?,?,?,?,?,?)", (tid, 1, ext, 'PS', 'Hero', fs))
        for i in range(3):
            c.execute(
                "INSERT INTO decisions (tournament_id,hand_id,street,action_taken,best_action,"
                "label,score,math_penalty,range_penalty,is_3bet,icm_tax_pct) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tid, f'H{tid}{i}', 'preflop', 'calls', 'calls', 'standard', 0.5, 0, 0, 0, 4.2))
    c.commit()
    c.close()


def _com_icm():
    c = _conn()
    try:
        return {r['tournament_id']: r['n'] for r in c.execute(
            "SELECT t.tournament_id, SUM(CASE WHEN d.icm_tax_pct IS NOT NULL THEN 1 ELSE 0 END) AS n "
            "FROM decisions d JOIN tournaments t ON t.id = d.tournament_id "
            "GROUP BY t.tournament_id")}
    finally:
        c.close()


def _roda(*argv):
    sys.argv = ['clear_bogus_icm_tax', *argv]
    script.main()


def test_dry_run_nao_altera_nada():
    """Padrão é relatar, não apagar. Script destrutivo que age sem pedir é acidente esperando."""
    _setup()
    antes = _com_icm()
    _roda()
    assert _com_icm() == antes, 'dry-run alterou o banco'
    print("OK  test_dry_run_nao_altera_nada")


def test_apply_limpa_mtt_e_preserva_mesa_unica():
    _setup()
    _roda('--apply')
    depois = _com_icm()
    assert depois['MTT500'] == 0, 'MTT de 500 inscritos manteve ICM'
    assert depois['SNG9'] == 3, 'torneio de mesa única perdeu o ICM — ali o dado é válido'
    print("OK  test_apply_limpa_mtt_e_preserva_mesa_unica")


def test_sem_field_size_tambem_e_limpo():
    """A escolha conservadora, explícita: sem prova de mesa única, não afirmamos. O resumo pode
    chegar depois e o backfill repõe."""
    _setup()
    _roda('--apply')
    assert _com_icm()['SEM_TS'] == 0
    print("OK  test_sem_field_size_tambem_e_limpo")


def test_idempotente():
    """Rodar duas vezes não pode quebrar nem mexer no que sobrou."""
    _setup()
    _roda('--apply')
    primeiro = _com_icm()
    _roda('--apply')
    assert _com_icm() == primeiro
    print("OK  test_idempotente")


def test_criterio_bate_com_o_gate_do_engine():
    """O script e o `build_mtt_context` precisam concordar sobre o que é mesa única — senão a
    limpeza apaga o que a análise vai regravar, para sempre."""
    from leaklab.mtt_context import _ICM_MAX_PLAYERS
    assert str(_ICM_MAX_PLAYERS) in script._MANTER, script._MANTER
    print("OK  test_criterio_bate_com_o_gate_do_engine")


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
