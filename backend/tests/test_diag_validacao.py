"""
Prévia da validação — os vereditos certos, e nenhuma escrita.

A promessa central do `scripts/diag_validacao.py` é ser SOMENTE LEITURA. O caminho de produção
(`get_training_proof`) reabre o leak e move o baseline quando a regressão é comprovada — efeito
legítimo lá, armadilha numa consulta. Se a prévia mexesse no plano de estudo por ter sido
consultada, o jogador seria punido por perguntar.

O outro ponto: a sonda chama `validation.validate_leak`, a mesma função do produto. Uma query
própria criaria uma segunda definição de "melhorou" — a classe de bug que mais custou tempo aqui.
"""
import sys, os, tempfile, sqlite3, traceback, io, contextlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo

TEST_DB = tempfile.mktemp(suffix='_diagval.db')
CORTE   = '2026-07-01 00:00:00'


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()

import scripts.diag_validacao as sonda


def _setup():
    c = _conn()
    for t in ('decisions', 'tournaments', 'training_proof', 'training_skill_progress'):
        c.execute(f"DELETE FROM {t}")
    c.execute("DELETE FROM users WHERE id = 1")
    c.execute("INSERT INTO users (id,username,email,password_hash) VALUES (1,'rod','r@t.com','x')")
    c.execute("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,imported_at) "
              "VALUES (1,1,'ANTES','PS','H','2026-06-01 00:00:00')")
    c.execute("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,imported_at) "
              "VALUES (2,1,'DEPOIS','PS','H','2026-07-20 00:00:00')")

    def dec(tid, pos, vs, erros, n, tag):
        for i in range(n):
            c.execute(
                "INSERT INTO decisions (tournament_id,hand_id,street,action_taken,best_action,label,"
                "score,math_penalty,range_penalty,is_3bet,position,vs_position,"
                "preflop_raises_faced,gto_label) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, f'{tag}{i}', 'preflop', 'calls', 'calls', 'standard', 0.5, 0, 0, 0,
                 pos, vs, 1, 'gto_critical' if i < erros else 'gto_correct'))

    dec(1, 'BB',  'CO',  21, 30, 'A1'); dec(2, 'BB',  'CO',   6, 30, 'A2')   # melhora clara
    dec(1, 'SB',  'BTN', 12, 20, 'B1'); dec(2, 'SB',  'BTN',  2,  5, 'B2')   # depois curto
    dec(1, 'UTG', 'MP',   4, 20, 'C1'); dec(2, 'UTG', 'MP',  18, 24, 'C2')   # regressão
    for k in ('vs_rfi:BB:CO:30', 'vs_rfi:SB:BTN:30', 'vs_rfi:UTG:MP:30'):
        c.execute("INSERT INTO training_skill_progress (user_id,category_key) VALUES (?,?)", (1, k))
        c.execute("INSERT INTO training_proof (user_id,category_key,baseline_pct,baseline_n,baseline_at)"
                  " VALUES (?,?,?,?,?)", (1, k, 30.0, 20, CORTE))
    c.commit()
    c.close()


def _rodar():
    sys.argv = ['diag_validacao', '--user-id', '1']
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sonda.main()
    return buf.getvalue()


def _dump():
    """Estado completo do que a sonda poderia sujar."""
    c = _conn()
    try:
        return {
            'proof': [tuple(r) for r in c.execute(
                "SELECT user_id,category_key,baseline_pct,baseline_n,baseline_at FROM training_proof "
                "ORDER BY category_key")],
            'skills': [tuple(r) for r in c.execute(
                "SELECT user_id,category_key FROM training_skill_progress ORDER BY category_key")],
            'decisoes': [tuple(r) for r in c.execute(
                "SELECT id,gto_label FROM decisions ORDER BY id")],
        }
    finally:
        c.close()


def test_vereditos_batem_com_os_cenarios():
    _setup()
    out = _rodar()
    assert 'Melhorou no jogo' in out, out
    assert 'Regrediu no jogo' in out, out
    assert 'Ainda sem amostra' in out, out
    print("OK  test_vereditos_batem_com_os_cenarios")


def test_nao_grava_nada_nem_com_regressao():
    """O caso perigoso: há uma regressão comprovada no dado, que em produção REABRE o leak e move
    o baseline. A prévia não pode fazer isso — consultar não é jogar."""
    _setup()
    antes = _dump()
    out = _rodar()
    assert 'Regrediu no jogo' in out, 'o cenário de regressão não disparou; teste inócuo'
    assert _dump() == antes, 'a sonda alterou o banco — ela promete somente leitura'
    print("OK  test_nao_grava_nada_nem_com_regressao")


def test_nao_cria_baseline_para_categoria_sem_ele():
    """Criar baseline agora congelaria o 'antes' DEPOIS do treino — mediria a melhora contra ela
    mesma e nunca mais acusaria nada."""
    _setup()
    c = _conn()
    c.execute("INSERT INTO training_skill_progress (user_id,category_key) VALUES (1,'vs_rfi:CO:BTN:30')")
    c.commit(); c.close()
    n_antes = len(_dump()['proof'])
    out = _rodar()
    assert 'sem baseline' in out, out
    assert len(_dump()['proof']) == n_antes, 'a sonda criou baseline'
    print("OK  test_nao_cria_baseline_para_categoria_sem_ele")


def test_usa_a_funcao_de_veredito_do_produto():
    """Se alguém reescrever a regra dentro da sonda, ela deixa de refletir o que o jogador vê."""
    import ast
    fonte = open(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'diag_validacao.py'),
                 encoding='utf-8').read()
    arvore = ast.parse(fonte)
    importados = {a.name for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom)
                  for a in n.names}
    assert 'validate_leak' in importados, 'a sonda precisa usar a MESMA função de veredito'
    print("OK  test_usa_a_funcao_de_veredito_do_produto")


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
