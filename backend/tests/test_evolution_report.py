"""
Relatório de evolução — ranqueia por CUSTO, valida por frequência.

A separação que estrutura o relatório inteiro: **bb perdidos** responde "no que eu mexo agora" e
**taxa de erro** responde "melhorei?". São perguntas diferentes e precisam de medidas diferentes.
Errar 29% de um spot que custa 0,08bb importa menos que errar 6% de um que custa 4bb — um
relatório ordenado por frequência manda o jogador para o lugar errado, com toda a confiança do
mundo. O relatório de validação que existia antes deste módulo cometia exatamente esse erro.

O que os testes travam, em ordem de importância:
  1. a zona de ICM fica FORA (o gabarito é chipEV puro; o EV medido ali não descreve a decisão);
  2. a cauda pesada aparece — em MTT três desastres pesam mais que duzentos erros pequenos, e
     média esconde justamente as mãos que decidiram os torneios;
  3. a matriz normaliza por 100 decisões, senão a célula mais escura é só a que você mais jogou;
  4. as faixas de stack são as MESMAS do solver, não um terceiro esquema.
"""
import sys, os, tempfile, sqlite3, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo

TEST_DB = tempfile.mktemp(suffix='_evrep.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()

_COLS = ("tournament_id,hand_id,street,action_taken,best_action,label,score,math_penalty,"
         "range_penalty,is_3bet,position,vs_position,stack_bb,ev_loss_bb,gto_label,icm_pressure")
_VALS = "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"


def _dec(c, tid, hand, pos, stack, ev, icm='low', vs=None):
    c.execute(f"INSERT INTO decisions ({_COLS}) VALUES {_VALS}",
              (tid, hand, 'preflop', 'calls', 'raises', 'standard', 0.5, 0, 0, 0,
               pos, vs, stack, ev, 'gto_critical' if ev > 0.2 else 'gto_correct', icm))


def _setup(linhas, n_torneios=4):
    c = _conn()
    for t in ('decisions', 'tournaments'):
        c.execute(f"DELETE FROM {t}")
    c.execute("DELETE FROM users WHERE id = 1")
    c.execute("INSERT INTO users (id,username,email,password_hash) VALUES (1,'u','u@t.com','x')")
    for t in range(1, n_torneios + 1):
        c.execute("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,imported_at) "
                  "VALUES (?,?,?,?,?,?)", (t, 1, f'T{t}', 'PS', 'H', f'2026-07-{t:02d} 10:00:00'))
    for l in linhas:
        _dec(c, *l)
    c.commit()
    c.close()


# ── 1 · ICM fora ──────────────────────────────────────────────────────────────────────────────

def test_zona_de_icm_fica_fora_do_ranking():
    """O maior EV do banco está sob ICM alto. Se ele aparecer, o relatório está mandando o jogador
    estudar um spot cujo gabarito não vale ali."""
    _setup([
        (1, 'NORMAL', 'BTN', 25, 3.0, 'low'),
        (1, 'ICM',    'BB',  12, 99.0, 'high'),
    ])
    r = repo.get_evolution_report(1)
    ids = [s['hand_id'] for s in r['top_spots']]
    assert 'ICM' not in ids, ids
    assert ids == ['NORMAL'], ids
    print("OK  test_zona_de_icm_fica_fora_do_ranking")


def test_icm_tambem_fora_da_matriz_e_do_total():
    _setup([
        (1, 'A', 'BTN', 25, 1.0, 'low'),
        (1, 'B', 'BTN', 25, 50.0, 'high'),
    ])
    r = repo.get_evolution_report(1)
    celula = next(c for c in r['matriz'] if c['position'] == 'BTN')
    assert celula['n'] == 1, celula
    assert r['resumo']['bb_por_torneio'] == 1.0, r['resumo']
    print("OK  test_icm_tambem_fora_da_matriz_e_do_total")


# ── 2 · cauda pesada ──────────────────────────────────────────────────────────────────────────

def test_o_desastre_aparece_no_topo():
    """Em MTT, três mãos decidem o torneio. A lista existe para mostrar exatamente essas."""
    linhas = [(1, f'PEQUENO{i}', 'CO', 30, 0.3) for i in range(60)]
    linhas.append((1, 'DESASTRE', 'BB', 18, 8.4, 'low', 'BTN'))
    _setup(linhas)
    top = repo.get_evolution_report(1)['top_spots']
    assert top[0]['hand_id'] == 'DESASTRE', top[0]
    assert top[0]['ev_loss_bb'] == 8.4
    assert top[0]['vs_position'] == 'BTN', 'o contexto do vilão precisa vir junto'
    print("OK  test_o_desastre_aparece_no_topo")


def test_spot_sem_perda_nao_entra():
    """EV zero não é 'spot barato', é acerto. Listá-lo encheria o top 5 de ruído."""
    _setup([(1, 'ZERO', 'CO', 30, 0.0), (1, 'CUSTOU', 'CO', 30, 1.2)])
    ids = [s['hand_id'] for s in repo.get_evolution_report(1)['top_spots']]
    assert ids == ['CUSTOU'], ids
    print("OK  test_spot_sem_perda_nao_entra")


# ── 3 · matriz normalizada ────────────────────────────────────────────────────────────────────

def test_matriz_normaliza_por_100_decisoes():
    """Sem normalizar, a célula mais escura seria só a que você mais jogou. Aqui BTN tem o DOBRO
    de decisões de SB e a MESMA perda total — o mapa precisa mostrar BTN como metade do problema."""
    _setup([(1, f'B{i}', 'BTN', 25, 1.0) for i in range(20)]
           + [(1, f'S{i}', 'SB', 25, 2.0) for i in range(10)])
    m = {c['position']: c for c in repo.get_evolution_report(1)['matriz']}
    assert m['BTN']['bb_100'] == 100.0, m['BTN']
    assert m['SB']['bb_100'] == 200.0, m['SB']
    print("OK  test_matriz_normaliza_por_100_decisoes")


def test_celula_sem_amostra_simplesmente_nao_existe():
    """Ausência precisa ser ausência. Uma célula 'zero' onde não houve mão diria ao jogador que
    ele joga perfeito ali — a mentira mais fácil de contar num mapa de calor."""
    _setup([(1, 'A', 'BTN', 25, 1.0)])
    m = repo.get_evolution_report(1)['matriz']
    assert len(m) == 1 and m[0]['position'] == 'BTN', m
    print("OK  test_celula_sem_amostra_simplesmente_nao_existe")


# ── 4 · buckets são os do solver ──────────────────────────────────────────────────────────────

def test_faixas_de_stack_sao_as_do_solver():
    """Já existem DOIS bucketings nesta base e um teste que documenta por que unificá-los seria
    bug. Um terceiro, só para o relatório, seria a mesma armadilha de novo."""
    from leaklab.gto_utils import STACK_BUCKETS, stack_bucket
    _setup([(1, 'CURTO', 'BTN', 8, 1.0), (1, 'MEDIO', 'BTN', 25, 1.0), (1, 'FUNDO', 'BTN', 80, 1.0)])
    buckets = {c['bucket'] for c in repo.get_evolution_report(1)['matriz']}
    assert buckets == {stack_bucket(8), stack_bucket(25), stack_bucket(80)}, buckets
    assert buckets <= {b[2] for b in STACK_BUCKETS}, 'rótulo fora do esquema do solver'
    print("OK  test_faixas_de_stack_sao_as_do_solver")


# ── 5 · tendência ─────────────────────────────────────────────────────────────────────────────

def test_tendencia_compara_metades_e_nao_um_corte_fixo():
    """Com poucos torneios, 'últimos 10 × anteriores' compara 10 com 2 e apresenta ruído de
    amostra como tendência. Meio a meio mantém os dois lados comparáveis."""
    linhas = ([(t, f'A{t}', 'CO', 30, 2.0) for t in (1, 2)]      # antigos: caros
              + [(t, f'B{t}', 'CO', 30, 0.5) for t in (3, 4)])    # recentes: baratos
    _setup(linhas)
    r = repo.get_evolution_report(1)['resumo']
    assert r['n_torneios'] == 4
    assert r['anterior'] == 2.0 and r['bb_por_torneio'] == 0.5, r
    assert r['delta'] == -1.5, r
    print("OK  test_tendencia_compara_metades_e_nao_um_corte_fixo")


def test_timeline_em_ordem_cronologica():
    """O gráfico lê da esquerda para a direita. A query ordena DESC para pegar os últimos N — se
    alguém esquecer de inverter, a curva de melhora vira curva de piora."""
    _setup([(t, f'H{t}', 'CO', 30, float(t)) for t in (1, 2, 3, 4)])
    tl = repo.get_evolution_report(1)['timeline']
    assert [x['ext'] for x in tl] == ['T1', 'T2', 'T3', 'T4'], tl
    assert [x['bb'] for x in tl] == [1.0, 2.0, 3.0, 4.0], tl
    print("OK  test_timeline_em_ordem_cronologica")


def test_sem_dado_nao_quebra():
    _setup([], n_torneios=0)
    r = repo.get_evolution_report(1)
    assert r['timeline'] == [] and r['top_spots'] == []
    assert r['resumo'].get('bb_por_torneio') is None
    print("OK  test_sem_dado_nao_quebra")


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
