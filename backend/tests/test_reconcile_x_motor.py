# -*- coding: utf-8 -*-
"""
O veredito GRAVADO discordava do que o motor calcula.

── Como apareceu ──────────────────────────────────────────────────────────────────────────────────

Reprocessando o acervo local, o delta de veredito nao batia com nada que eu tinha medido no motor.
Isolando por etapa num torneio de 485 decisoes:

    apos save_decisions ......... divergencia motor x banco:  0 / 485
    apos reconcile SOZINHO ...... divergencia:               54 / 485

O banco tinha exatamente o veredito do motor, e o reconcile o reescrevia. As 54:

    marginal -> small_mistake   38   (TODAS gto_critical)   <- consertado aqui
    marginal -> standard         8
    standard -> marginal         5
    standard -> small_mistake    2
    small_mistake -> standard    1

── A causa das 38 ────────────────────────────────────────────────────────────────────────────────

`_reconcile_label` aplicava o piso cru de `gto_critical` (-> `small_mistake`) por cima de um
veredito que o motor ja tinha rebaixado para `marginal` pelo TETO DE EV: um `gto_critical` que
custa ~0bb e spot misto, nao erro grave.

O reconcile tinha como saber — `ev_loss_bb`, `ev_loss_source`, `estimated_equity`, `pot_size` e
`facing_bet` estao todos na propria linha. Simplesmente nao eram lidos.

O conserto NAO reimplementa a regra: chama `_ev_severity_ceiling` + `ev_loss_trustworthy` do
motor. Uma terceira copia de politica de veredito e o erro que este projeto ja pagou varias vezes.

── Atribuicao que eu errei no caminho ─────────────────────────────────────────────────────────────

Meu primeiro isolamento deu "o reconcile responde por 0" e apontou o `sync`. Era falso: o
`sync_tournament` CHAMA o reconcile por dentro quando atualiza alguma linha, entao quando eu o
chamava depois ele ja tinha rodado. Medir uma etapa que outra ja executou nao isola nada.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.repositories import _reconcile_label      # noqa: E402


def _rec(label, gto_label, **kw):
    kw.setdefault('street', 'preflop')
    kw.setdefault('stack_bb', 40.0)
    kw.setdefault('action_taken', 'raise')
    kw.setdefault('gto_action', 'raise')
    return _reconcile_label(label, gto_label, **kw)


def test_gto_critical_de_custo_ininfimo_nao_vira_erro():
    """O caso das 38. O motor ja rebaixou para `marginal` por EV; o piso nao pode desfazer."""
    r = _rec('marginal', 'gto_critical', ev_loss_bb=0.02, ev_loss_source='gto_tree')
    assert r == 'marginal', f'o teto de EV do motor foi ignorado, veio {r}'


def test_gto_critical_que_custa_CARO_continua_erro():
    """O teto so vale para custo baixo — erro caro segue erro, senao o conserto viraria anistia."""
    r = _rec('marginal', 'gto_critical', ev_loss_bb=6.0, ev_loss_source='gto_tree')
    assert r in ('small_mistake', 'clear_mistake'), r


def test_sem_EV_o_piso_continua_valendo():
    """Falha para o lado seguro: sem `ev_loss_bb` nao ha o que capear, e o comportamento
    antigo (piso) permanece. Ausencia de dado nao pode virar absolvicao."""
    assert _rec('marginal', 'gto_critical', ev_loss_bb=None) == 'small_mistake'


def test_o_teto_NUNCA_agrava():
    """`_ev_severity_ceiling` so abaixa. Um label ja grave nao pode subir por causa do EV."""
    for ev in (0.0, 0.05, 1.0, 50.0):
        r = _rec('clear_mistake', 'gto_critical', ev_loss_bb=ev, ev_loss_source='gto_tree')
        assert r in ('clear_mistake', 'small_mistake', 'marginal'), (ev, r)


def test_erro_de_DIRECAO_nao_e_capeado_por_EV():
    """Invariante que ja existia: GTO folda e o hero AGREDIU nunca vira nao-erro, custe o que
    custar. O ramo de direcao sai antes do teto, e tem que continuar saindo."""
    r = _rec('standard', 'gto_critical', gto_action='fold', action_taken='raise',
             ev_loss_bb=0.001, ev_loss_source='gto_tree')
    assert r == 'small_mistake', r


def test_o_reconcile_concorda_com_o_MOTOR_no_mesmo_gto_critical():
    """O guarda de verdade: as duas politicas tem que dar a mesma resposta para a mesma entrada.
    E o que falhava — o motor dizia `marginal` e o banco gravava `small_mistake`."""
    from leaklab.decision_engine_v11 import _preflop_gto_label_adjust, _ev_severity_ceiling
    for ev in (0.01, 0.05, 0.2, 1.0, 5.0):
        motor = _ev_severity_ceiling(
            _preflop_gto_label_adjust('standard', 'major_leak', ev), ev, 'gto_tree')
        banco = _rec('standard', 'gto_critical', ev_loss_bb=ev, ev_loss_source='gto_tree')
        assert motor == banco, f'ev={ev}: motor={motor} banco={banco}'


def test_o_SELECT_do_reconcile_le_os_campos_de_EV():
    """Guarda do CAMINHO, nao da funcao pura: os testes acima passam mesmo que o
    `reconcile_tournament_labels` pare de LER `ev_loss_bb` da linha e passe None.

    Isso nao e hipotese — na primeira rodada de verificacao, trocar a leitura por `None` no
    SELECT nao derrubou teste nenhum. Aqui a decisao vai para um banco de verdade e volta."""
    import tempfile, sqlite3
    import database.schema as sch
    import database.repositories as repo

    db = tempfile.mktemp(suffix='.db')
    _orig_schema, _orig_repo = sch.get_conn, repo.get_conn

    def _conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c
    sch.get_conn = _conn
    repo.get_conn = _conn
    try:
        sch.init_db()
        uid = repo.create_user('evuser', 'ev@t.com', 'pwd')
        tid = repo.save_tournament(uid, 'TEV', 'phpro', {'total_hands': 1, 'total_decisions': 1})
        c = _conn()
        c.execute("""INSERT INTO decisions
            (tournament_id, hand_id, street, position, action_taken, best_action, label,
             gto_label, gto_action, score, stack_bb, facing_bet, hero_cards, board,
             ev_loss_bb, ev_loss_source, estimated_equity, pot_size)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tid, 'H1', 'preflop', 'BTN', 'raise', 'raise', 'marginal',
             'gto_critical', 'raise', 0.15, 40.0, 2.0, 'AsKd', '[]',
             0.02, 'gto_tree', 0.55, 5.0))
        c.commit(); c.close()

        repo.reconcile_tournament_labels(tid)

        c = _conn()
        lab = c.execute("SELECT label FROM decisions WHERE tournament_id=?", (tid,)).fetchone()['label']
        c.close()
        assert lab == 'marginal', \
            f'o reconcile ignorou o EV da linha e agravou para {lab}'
    finally:
        sch.get_conn, repo.get_conn = _orig_schema, _orig_repo
        try:
            os.remove(db)
        except OSError:
            pass


def test_only_ids_limita_a_re_derivacao_de_label():
    """Depois do `save_decisions` cada linha ja tem o veredito do MOTOR, calculado junto com
    aquele mesmo `gto_label`. Varrer ali nao reconcilia nada — so troca um veredito completo
    (que viu ICM, multiway, mao monstro, EV e ausencia de gabarito) por um derivado so do
    `gto_label`. `only_ids=[]` desliga a re-derivacao sem desligar o resto.

    Medido no acervo: a varredura escopada levou a divergencia motor x banco de 9,9% para
    6,4%, e os casos "mesmo gto_label, label diferente" de 97 para 10."""
    import tempfile, sqlite3
    import database.schema as sch
    import database.repositories as repo

    db = tempfile.mktemp(suffix='.db')
    _os, _or = sch.get_conn, repo.get_conn

    def _conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c
    sch.get_conn = _conn
    repo.get_conn = _conn
    try:
        sch.init_db()
        uid = repo.create_user('scopeuser', 'scope@t.com', 'pwd')
        tid = repo.save_tournament(uid, 'TSC', 'phpro', {'total_hands': 1, 'total_decisions': 2})
        c = _conn()
        # `standard` com `gto_critical`: a varredura completa PISA em small_mistake.
        for hid in ('H1', 'H2'):
            c.execute("""INSERT INTO decisions
                (tournament_id, hand_id, street, position, action_taken, best_action, label,
                 gto_label, gto_action, score, stack_bb, facing_bet, hero_cards, board)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tid, hid, 'preflop', 'BTN', 'raise', 'raise', 'standard',
                 'gto_critical', 'raise', 0.05, 40.0, 2.0, 'AsKd', '[]'))
        c.commit()
        ids = [r['id'] for r in c.execute("SELECT id FROM decisions WHERE tournament_id=? ORDER BY id", (tid,))]
        c.close()

        def _labels():
            c2 = _conn()
            r = [x['label'] for x in c2.execute(
                "SELECT label FROM decisions WHERE tournament_id=? ORDER BY id", (tid,))]
            c2.close()
            return r

        repo.reconcile_tournament_labels(tid, only_ids=[])
        assert _labels() == ['standard', 'standard'], \
            f'only_ids=[] nao pode re-derivar label nenhum, veio {_labels()}'

        repo.reconcile_tournament_labels(tid, only_ids=[ids[0]])
        assert _labels() == ['small_mistake', 'standard'], \
            f'only_ids devia agir SO na primeira, veio {_labels()}'

        repo.reconcile_tournament_labels(tid)          # None = varre tudo (drain/backfill)
        assert _labels() == ['small_mistake', 'small_mistake'], \
            f'sem only_ids a varredura completa precisa continuar valendo, veio {_labels()}'
    finally:
        sch.get_conn, repo.get_conn = _os, _or
        try:
            os.remove(db)
        except OSError:
            pass


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
