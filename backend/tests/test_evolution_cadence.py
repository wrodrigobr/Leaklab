"""
Cadência do relatório de evolução — a unidade é AMOSTRA, não calendário.

Relatório por calendário treina o jogador a ignorar relatório: quem jogou 3 torneios no mês recebe
um documento dizendo "sem amostra" em tudo, e depois de duas dessas ele para de abrir. Por isso a
decisão de gerar é por gatilho, em ordem de força:

  1. MUDOU UM VEREDITO — um leak virou provado, ou reabriu. É o único momento em que o relatório
     tem algo a dizer que o jogador não sabia.
  2. VOLUME NOVO — decisões suficientes para os intervalos de confiança se moverem de verdade.
  3. PISO MENSAL — mantém o hábito quando houve atividade, mesmo sem novidade.

Com teto semanal em todos. `decidir_cadencia_relatorio` é PURA de propósito: é ela que decide
mandar (ou não) uma notificação, e essa decisão precisa ser testável sem banco, sem relógio e sem
worker rodando.
"""
import sys, os, json, tempfile, sqlite3, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo
from database.repositories import (
    decidir_cadencia_relatorio as decidir,
    _REPORT_MIN_DECISOES, _REPORT_TETO_DIAS, _REPORT_PISO_DIAS,
)

TEST_DB = tempfile.mktemp(suffix='_cad.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()


def _ultimo(n_decisoes=0, verdicts=None, motivo='volume'):
    proof = [{'category_key': k, 'validacao': {'veredito': v}} for k, v in (verdicts or {}).items()]
    return {'motivo': motivo, 'n_decisoes': n_decisoes,
            'snapshot': json.dumps({'proof': proof})}


# ── Primeiro relatório ────────────────────────────────────────────────────────────────────────

def test_primeiro_exige_amostra():
    """Nascer dizendo "sem dados em tudo" queima a estreia — e a estreia é a única que todo
    jogador abre."""
    assert decidir(None, _REPORT_MIN_DECISOES - 1, {}, None, True) is None
    assert decidir(None, _REPORT_MIN_DECISOES, {}, None, True) == 'primeiro'
    print("OK  test_primeiro_exige_amostra")


# ── Gatilho 1: veredito ───────────────────────────────────────────────────────────────────────

def test_veredito_novo_dispara():
    """O gatilho mais forte: 'seu leak de BTN está provado' é a única coisa que o relatório sabe e
    o jogador não."""
    ultimo = _ultimo(n_decisoes=100, verdicts={'rfi:BTN': 'sem_mudanca'})
    assert decidir(ultimo, 110, {'rfi:BTN': 'melhorou'}, 10, True) == 'veredito_mudou'
    print("OK  test_veredito_novo_dispara")


def test_regressao_tambem_dispara():
    """Leak reaberto é a notícia mais urgente que o sistema pode dar. Esperar volume para contá-la
    seria deixar o jogador treinando o que ele já domina enquanto sangra noutro lugar."""
    ultimo = _ultimo(n_decisoes=100, verdicts={'rfi:SB': 'melhorou'})
    assert decidir(ultimo, 105, {'rfi:SB': 'piorou'}, 10, True) == 'veredito_mudou'
    print("OK  test_regressao_tambem_dispara")


def test_veredito_igual_nao_dispara():
    ultimo = _ultimo(n_decisoes=100, verdicts={'rfi:BTN': 'melhorou'})
    assert decidir(ultimo, 110, {'rfi:BTN': 'melhorou'}, 10, True) is None
    print("OK  test_veredito_igual_nao_dispara")


def test_sem_amostra_nao_e_noticia():
    """'Ainda sem amostra' não é veredito, é ausência dele. Disparar por isso geraria relatório a
    cada categoria nova treinada, sem nada a dizer."""
    ultimo = _ultimo(n_decisoes=100, verdicts={})
    assert decidir(ultimo, 110, {'rfi:CO': 'sem_amostra'}, 10, True) is None
    assert decidir(ultimo, 110, {'rfi:CO': 'sem_mudanca'}, 10, True) is None
    print("OK  test_sem_amostra_nao_e_noticia")


# ── Gatilho 2: volume ─────────────────────────────────────────────────────────────────────────

def test_volume_dispara_no_limiar():
    ultimo = _ultimo(n_decisoes=1000)
    assert decidir(ultimo, 1000 + _REPORT_MIN_DECISOES - 1, {}, 10, True) is None
    assert decidir(ultimo, 1000 + _REPORT_MIN_DECISOES, {}, 10, True) == 'volume'
    print("OK  test_volume_dispara_no_limiar")


def test_volume_e_incremental_nao_absoluto():
    """Compara com o que existia NO ÚLTIMO relatório. Se fosse absoluto, um veterano geraria
    relatório a cada varredura para sempre."""
    ultimo = _ultimo(n_decisoes=50_000)
    assert decidir(ultimo, 50_010, {}, 10, True) is None
    print("OK  test_volume_e_incremental_nao_absoluto")


# ── Teto e piso ───────────────────────────────────────────────────────────────────────────────

def test_teto_semanal_vence_qualquer_gatilho():
    """Inclusive o veredito. Quem joga muito mudaria veredito toda semana, e o relatório viraria
    spam — que é como um bom sinal vira ruído ignorado."""
    ultimo = _ultimo(n_decisoes=100, verdicts={'rfi:BTN': 'sem_mudanca'})
    assert decidir(ultimo, 100_000, {'rfi:BTN': 'melhorou'}, _REPORT_TETO_DIAS - 1, True) is None
    print("OK  test_teto_semanal_vence_qualquer_gatilho")


def test_piso_mensal_com_atividade():
    ultimo = _ultimo(n_decisoes=1000)
    assert decidir(ultimo, 1010, {}, _REPORT_PISO_DIAS + 1, True) == 'mensal'
    print("OK  test_piso_mensal_com_atividade")


def test_piso_mensal_nao_dispara_sem_atividade():
    """Quem parou de jogar não deve receber relatório mensal dizendo que nada mudou. Nada mudou
    porque ele não jogou, e o e-mail só lembra que ele abandonou."""
    ultimo = _ultimo(n_decisoes=1000)
    assert decidir(ultimo, 1000, {}, _REPORT_PISO_DIAS + 30, False) is None
    print("OK  test_piso_mensal_nao_dispara_sem_atividade")


# ── Persistência ──────────────────────────────────────────────────────────────────────────────

def test_snapshot_guarda_numeros_nao_html():
    """Guardar os NÚMEROS é o que permite o visual melhorar sem invalidar relatório antigo, e o
    que faz a comparação julho × agosto continuar válida."""
    c = _conn()
    c.execute("DELETE FROM evolution_reports")
    c.execute("DELETE FROM users WHERE id = 1")
    c.execute("INSERT INTO users (id,username,email,password_hash) VALUES (1,'u','u@t.com','x')")
    c.commit(); c.close()

    rid = repo.save_evolution_report(1, 'volume', {'resumo': {'bb_por_torneio': 2.47}}, 830)
    assert rid
    lido = repo.get_evolution_report_by_id(1, rid)
    assert json.loads(lido['snapshot'])['resumo']['bb_por_torneio'] == 2.47
    assert repo.get_last_evolution_report(1)['n_decisoes'] == 830
    assert len(repo.list_evolution_reports(1)) == 1
    assert 'snapshot' not in repo.list_evolution_reports(1)[0], 'a lista não carrega o snapshot'
    print("OK  test_snapshot_guarda_numeros_nao_html")


def test_relatorio_de_outro_usuario_nao_vaza():
    """Anti-IDOR: o user_id entra na cláusula, não é conferido depois."""
    c = _conn()
    c.execute("INSERT OR IGNORE INTO users (id,username,email,password_hash) "
              "VALUES (2,'v','v@t.com','x')")
    c.commit(); c.close()
    rid = repo.save_evolution_report(1, 'volume', {'x': 1}, 10)
    assert repo.get_evolution_report_by_id(2, rid) is None
    print("OK  test_relatorio_de_outro_usuario_nao_vaza")


def test_snapshot_corrompido_nao_derruba_a_decisao():
    """Um snapshot ilegível não pode travar a cadência para sempre — o pior caso é perder a
    comparação de vereditos daquele ciclo, não parar de gerar."""
    ultimo = {'motivo': 'volume', 'n_decisoes': 100, 'snapshot': '{quebrado'}
    assert decidir(ultimo, 100 + _REPORT_MIN_DECISOES, {}, 10, True) == 'volume'
    print("OK  test_snapshot_corrompido_nao_derruba_a_decisao")


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
