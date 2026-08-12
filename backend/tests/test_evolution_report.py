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
         "range_penalty,is_3bet,position,vs_position,stack_bb,ev_loss_bb,gto_label,icm_pressure,"
         "ev_loss_source")
_VALS = "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
_FONTE_OK = 'solver_hand'   # está em _EV_RELIABLE_SOURCES


def _dec(c, tid, hand, pos, stack, ev, icm='low', vs=None, src=_FONTE_OK):
    c.execute(f"INSERT INTO decisions ({_COLS}) VALUES {_VALS}",
              (tid, hand, 'preflop', 'calls', 'raises', 'standard', 0.5, 0, 0, 0,
               pos, vs, stack, ev, 'gto_critical' if ev > 0.2 else 'gto_correct', icm, src))


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


# ── 6 · EV confiável ──────────────────────────────────────────────────────────────────────────

def test_ev_acima_do_teto_de_calibracao_nao_entra():
    """O bug que originou, medido em produção: um FOLD com -90,3bb a 139bb efetivos.

    Foldar não pode custar 90bb — o que você abre mão é limitado pelo pote. Acima de 100bb o
    lookup usa 100bb como profundidade efetiva: a AÇÃO transfere (é o que a aproximação promete),
    mas o EV volta na escala do solve de 100bb. Três decisões assim dominavam o ranking inteiro e
    faziam a manchete anunciar uma melhora de 12bb/torneio que era só a metade antiga conter um
    número inventado."""
    _setup([
        (1, 'FUNDO',  'CO',  139.3, 90.3),
        (1, 'NORMAL', 'BTN',  25.0,  2.0),
    ])
    r = repo.get_evolution_report(1)
    ids = [s['hand_id'] for s in r['top_spots']]
    assert 'FUNDO' not in ids, ids
    assert ids == ['NORMAL'], ids
    assert all(c['position'] != 'CO' for c in r['matriz']), r['matriz']
    print("OK  test_ev_acima_do_teto_de_calibracao_nao_entra")


def test_fonte_desconhecida_nao_entra():
    """EV sem fonte declarada não é 'EV pequeno', é EV de origem desconhecida. Somá-lo é dar peso
    a um número que ninguém assinou."""
    _setup([
        (1, 'SEM_FONTE', 'CO',  30.0, 5.0, 'low', None, None),
        (1, 'HEURISTIC', 'BTN', 30.0, 5.0, 'low', None, 'heuristic'),
        (1, 'OK',        'SB',  30.0, 1.0),
    ])
    ids = [s['hand_id'] for s in repo.get_evolution_report(1)['top_spots']]
    assert ids == ['OK'], ids
    print("OK  test_fonte_desconhecida_nao_entra")


def test_no_limite_exato_ainda_conta():
    """100bb é o teto de calibração, não o começo do problema — a faixa 60-100 foi a mais
    comportada de todas na medição. Cortar em `<` em vez de `<=` jogaria fora dado bom."""
    _setup([(1, 'LIMITE', 'CO', 100.0, 3.0)])
    ids = [s['hand_id'] for s in repo.get_evolution_report(1)['top_spots']]
    assert ids == ['LIMITE'], ids
    print("OK  test_no_limite_exato_ainda_conta")


def test_fold_nao_pode_custar_mais_que_a_aritmetica_do_proprio_engine():
    """OS CASOS REAIS que expuseram o bug (produção, 2026-07-27).

    `ev_loss_bb` do solver vem na escala do POTE COM QUE O NÓ FOI SOLVADO, e `compute_spot_hash`
    não inclui o tamanho do pote. Um nó de pote pequeno servido a um pote grande devolve número
    de outra escala — às vezes 4x para cima, às vezes metade, às vezes com o sinal invertido.

    O que o teto pega é a contradição SEM SAÍDA: equity 33,0% contra 46,6% exigidos, **quase
    all-in** (sobram 5,9bb atrás), então não há street futura que justifique. Ainda assim o
    sistema cobrou 28,2bb e marcou gto_critical.

    O que ele NÃO pega, de propósito: o mesmo tipo de contradição onde ainda há stack atrás.
    Na primeira análise eu contei dois casos de direção invertida; recalculando com implied odds,
    só um sobrevive — no outro sobravam 19,3bb num flop, e 30,8% de equity com esse stack por trás
    é call defensável. Apertar o teto para pegá-lo apagaria leak real."""
    from leaklab.decision_engine_v11 import ev_loss_trustworthy as ok

    # quase all-in: 5,9bb atrás → sem implied odds → a aritmética é fechada
    assert ok(28.2, 33.7, 'solver_hand', action='fold',
              equity=0.330, pot_bb=31.8, facing_bb=27.8) is False
    # mesma equity baixa, mas 19,3bb atrás num flop → implied odds reais → passa
    assert ok(5.1, 29.1, 'solver_hand', action='fold',
              equity=0.308, pot_bb=16.3, facing_bb=9.8) is True
    print("OK  test_fold_nao_pode_custar_mais_que_a_aritmetica_do_proprio_engine")


def test_fold_caro_de_verdade_continua_valendo():
    """O contrapeso, e ele importa: um teto agressivo demais apagaria leak real.

    River, equity 72%, precisa 41,2% — pagar vale +27,5bb pela aritmética, e o solver gravou
    14,8bb. Subestimar é seguro; o teto não pode derrubar isto."""
    from leaklab.decision_engine_v11 import ev_loss_trustworthy as ok
    assert ok(14.8, 55.6, 'solver_hand', action='fold',
              equity=0.720, pot_bb=52.5, facing_bb=36.8) is True
    print("OK  test_fold_caro_de_verdade_continua_valendo")


def test_teto_so_vale_para_fold():
    """Em call/raise o EV depende do resto da árvore e não há aritmética simples com a qual
    comparar. Desconfiar dessas por heurística seria trocar um erro por outro."""
    from leaklab.decision_engine_v11 import ev_loss_trustworthy as ok
    assert ok(28.2, 33.7, 'solver_hand', action='call',
              equity=0.330, pot_bb=31.8, facing_bb=27.8) is True
    print("OK  test_teto_so_vale_para_fold")


def test_sem_equity_o_ev_passa():
    """Sem os números da conta não há do que discordar. Bloquear aqui jogaria fora todo o
    preflop, que não computa equity-vs-range e cujo EV é justamente o mais comportado
    (média 0,29bb, máximo 3,8bb em produção)."""
    from leaklab.decision_engine_v11 import ev_loss_trustworthy as ok
    assert ok(2.0, 30.0, 'gw_har', action='fold', equity=None, pot_bb=None, facing_bb=None) is True
    print("OK  test_sem_equity_o_ev_passa")


def test_fold_implausivel_sai_do_relatorio():
    """O efeito de ponta a ponta: o spot de -28,2bb some do ranking e da matriz."""
    _setup([
        (1, 'IMPLAUSIVEL', 'CO',  33.7, 28.2),
        (1, 'REAL',        'BTN', 30.0,  3.0),
    ])
    c = _conn()
    c.execute("UPDATE decisions SET action_taken='fold', estimated_equity=0.330, "
              "pot_size=31.8, facing_bet=27.8 WHERE hand_id='IMPLAUSIVEL'")
    c.execute("UPDATE decisions SET action_taken='call' WHERE hand_id='REAL'")
    c.commit(); c.close()
    r = repo.get_evolution_report(1)
    assert [s['hand_id'] for s in r['top_spots']] == ['REAL'], r['top_spots']
    assert all(x['position'] != 'CO' for x in r['matriz']), r['matriz']
    print("OK  test_fold_implausivel_sai_do_relatorio")


def test_regra_e_a_mesma_do_engine():
    """O relatório expressa em SQL a regra que o engine aplica em Python. Se as duas divergirem,
    o card e o relatório discordam sobre a mesma mão — e essa é a classe de bug que mais custou
    tempo neste projeto."""
    from leaklab.decision_engine_v11 import (
        ev_loss_trustworthy, _EV_TRUST_MAX_BB, _EV_RELIABLE_SOURCES)
    assert ev_loss_trustworthy(2.0, 30.0, 'solver_hand') is True
    assert ev_loss_trustworthy(90.3, 139.3, 'solver_hand') is False   # fundo demais
    assert ev_loss_trustworthy(2.0, 30.0, 'heuristic') is False       # fonte não confiável
    assert ev_loss_trustworthy(None, 30.0, 'solver_hand') is False
    assert ev_loss_trustworthy(2.0, _EV_TRUST_MAX_BB, 'solver_hand') is True
    assert _FONTE_OK in _EV_RELIABLE_SOURCES
    print("OK  test_regra_e_a_mesma_do_engine")


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
    raise SystemExit(1 if failed else 0)
