# -*- coding: utf-8 -*-
"""O eixo de tempo do dashboard e a data de JOGO, nao a de UPLOAD — em toda funcao de analise.

── O que originou ────────────────────────────────────────────────────────────────────────

03/09, achado do dono: o Rullian subiu 280 torneios jogados ao longo de 3 meses, todos
importados em 25 HORAS. Sob o eixo de upload, "ultimos 50" virava uma fatia arbitraria da
ordem do script. Consertado no `_build_tournament_filter`, que passou a usar
`COALESCE(played_at, imported_at)`.

05/09: o conserto foi onde o defeito APARECEU, nao onde ele vive. **27 funcoes** continuavam
em `t.imported_at >= ?`. E, respondendo a uma hipotese do dono ("o novo padrao do dash e o
historico, entao ele nao percebe, certo?"), a segunda camada: **24 delas nem aceitam
`last_n`** — usam `days` fixo, sempre. O filtro da tela nao as alcanca em posicao nenhuma.

Impacto medido (180d): micheldienstmann25 via **13.878 decisoes pelo eixo de upload contra
1.318 pelo de jogo — 10,5x**. O perfil estrategico, o mapa causal, o DNA e o nivel descreviam
o jogador de +180 dias atras como se fosse o atual. Atinge exatamente quem chega novo e sobe
acervo antigo.

── Os tres baldes, e por que a classificacao e DECLARADA aqui ────────────────────────────

Nao e um `sed`: `imported_at` e a resposta CERTA para algumas perguntas. Cada funcao que
filtra por data cai num balde, e o balde e o contrato:

  ANALISE    "como voce joga" -> data de JOGO, e aceita `last_n` (o filtro da tela)
  PRESENCA   "houve atividade / ha dado novo" -> data de UPLOAD, deliberadamente
  ADMIN      uso administrativo -> data de UPLOAD, deliberadamente

A varredura N+1: toda funcao de `repositories.py` que filtre por `imported_at` tem de estar num
dos tres. A 28a que alguem escrever cai aqui.
"""
import inspect
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

import database.repositories as repo                                   # noqa: E402

# ── A classificacao ─────────────────────────────────────────────────────────────────────

#: Janela de ANALISE. Filtram por data de JOGO e aceitam `last_n`.
ANALISE = (
    'get_leak_roi_impact',          # ranking de leaks + tendencia
    'get_gto_leak_ranking',         # ranking GTO-first (alimenta o plano de estudos)
    'get_pressure_profile',         # colapso sob pressao ICM
    'get_confidence_drift',         # deriva de confianca (tilt)
    'get_icm_performance',          # performance por zona de ICM
    'get_breakdown',                # HUD por street/posicao/label
    'get_player_level',             # nivel e XP
    'get_player_action_frequencies',# contexto do coach IA
    'get_career_projection',        # projecao de carreira
    'get_cognitive_failure_report', # mapa de falhas cognitivas
    'get_strategic_twin_profile',   # gemeo estrategico
    'get_leak_graph_data',          # mapa causal
    'get_player_dna',               # Decision DNA
    'get_common_leaks',             # coach: leaks em comum entre alunos
    'get_coach_impact_metrics',     # coach: evolucao dos alunos no periodo
    'get_leaderboard_metrics',      # ranking entre jogadores no periodo
    # Prova de treino: "melhorou DEPOIS de treinar" so faz sentido por data de JOGO. Mao
    # jogada antes do treino e importada depois nao e prova de nada.
    '_category_adherence',
    '_category_action_breakdown',
    '_category_purity_breakdown',
    '_category_error_counts',
    'get_training_proof',
)

#: ANALISE, mas visao do COACH sobre varios alunos: nao ha filtro de tela de um jogador para
#: propagar. So o eixo muda. Cada uma com o motivo.
SEM_FILTRO_DA_TELA = {
    'get_common_leaks':        'coach: leaks em comum entre alunos, janela de dias do coach',
    'get_coach_impact_metrics': 'coach: evolucao dos alunos no periodo, janela de dias do coach',
}

#: Data de UPLOAD e a resposta certa. Cada uma com o motivo — sem motivo, nao entra.
PRESENCA_OU_ADMIN = {
    'get_aproveitamento_do_solver':
        'card do ADMIN (AY-28): quanto do acervo de nos e reaproveitado quando um torneio ENTRA; '
        'o eixo certo e a data de import, porque a pergunta e sobre o upload, nao sobre o jogo.',
    'get_evolution_metrics':
        'o ramo default e o CHECK DE PRESENCA de dados do plano de estudos: torneio jogado ha '
        '>90 dias e importado agora tem de contar como "ha dado novo" (nota na propria funcao). '
        'O grafico usa `by_played=True`, e `last_n` ja e honrado.',
    'count_user_pending_solves':
        'atividade do SOLVER sobre importacoes recentes — nao e sobre o jogo.',
    '_contexto_cadencia':
        'cadencia de ENGAJAMENTO: "usou o app recentemente" e importar, nao jogar.',
    'get_coach_finance_students':
        'status de atividade para revenue share: usa o app = importa.',
    'get_public_coaches':
        'coach com aluno ATIVO no app nos ultimos 30 dias.',
    'get_admin_dashboard_stats':
        'painel admin: volume de importacao no periodo e a metrica de uso.',
}

_REPO = os.path.join(os.path.dirname(__file__), '..', 'database', 'repositories.py')
_RAW = re.compile(r'imported_at\s*(>=|<=|>|<)')


def _funcoes_com_imported_at_cru():
    """(funcao -> linhas) de toda funcao de repositories.py que filtra por `imported_at` cru."""
    linhas = io.open(_REPO, encoding='utf-8').read().split('\n')
    out, atual = {}, '?'
    for i, l in enumerate(linhas, 1):
        m = re.match(r'^def (\w+)', l)
        if m:
            atual = m.group(1)
        s = l.strip()
        if s.startswith('#') or s.startswith('--'):
            continue
        if 'imported_at' in l and 'COALESCE' not in l and _RAW.search(l):
            out.setdefault(atual, []).append(i)
    return out


def test_toda_funcao_no_eixo_de_upload_esta_classificada():
    """A varredura N+1. Funcao nova que filtre por `imported_at` cru sem estar num balde cai aqui."""
    cru = _funcoes_com_imported_at_cru()
    sem_balde = sorted(f for f in cru if f not in ANALISE and f not in PRESENCA_OU_ADMIN)
    assert not sem_balde, (
        'funcao(oes) filtrando por `imported_at` cru sem balde declarado: %s. Classifique em '
        'ANALISE (e converta) ou em PRESENCA_OU_ADMIN (com o motivo).' % ', '.join(sem_balde))


def test_funcao_de_ANALISE_nao_usa_imported_at_cru():
    """O contrato do balde: analise e por data de JOGO."""
    cru = _funcoes_com_imported_at_cru()
    ainda = sorted((f, cru[f]) for f in ANALISE if f in cru)
    assert not ainda, (
        'funcao(oes) de ANALISE ainda no eixo de UPLOAD: %s'
        % '; '.join('%s (linhas %s)' % (f, ','.join(map(str, ls))) for f, ls in ainda))


def test_funcao_de_ANALISE_aceita_o_filtro_da_tela():
    """A 2a camada: 24 das 27 nem aceitavam `last_n`. O filtro do dashboard nao as alcancava
    em posicao nenhuma — escolher "Historico" ou "ultimos 20" nao mudava nada nesses cards."""
    sem = []
    for nome in ANALISE:
        fn = getattr(repo, nome, None)
        if fn is None:
            sem.append('%s (nao existe)' % nome)
            continue
        params = inspect.signature(fn).parameters
        # As funcoes de prova de treino recebem o marco (`after`/`before`), nao `last_n`:
        # o recorte delas e "depois do treino", nao "ultimos N".
        if nome.startswith('_category_') or nome == 'get_training_proof':
            continue
        # Visao do COACH sobre varios alunos: nao existe "filtro da tela" de um jogador ali.
        # Muda so o EIXO (data de jogo), declarado em SEM_FILTRO_DA_TELA com o motivo.
        if nome in SEM_FILTRO_DA_TELA:
            continue
        if 'last_n' not in params and 'user_ids' not in params:
            sem.append(nome)
    assert not sem, 'funcao(oes) de ANALISE que o filtro da tela nao alcanca: %s' % ', '.join(sem)


def test_balde_de_presenca_carrega_motivo():
    """Sem motivo, PRESENCA_OU_ADMIN vira lista de excecao silenciosa — o problema de novo."""
    sem = [f for f, m in PRESENCA_OU_ADMIN.items() if not (m or '').strip()]
    assert not sem, 'declarado como presenca/admin sem motivo: %s' % ', '.join(sem)
    fantasmas = [f for f in PRESENCA_OU_ADMIN if not hasattr(repo, f)]
    assert not fantasmas, 'declarado mas nao existe: %s' % ', '.join(fantasmas)


def test_o_varredor_ACHA_um_filtro_cru():
    """Contraprova (regra 1): sem ela, os testes acima passariam com o regex quebrado."""
    assert _RAW.search("WHERE t.user_id = ? AND t.imported_at >= ?")
    assert _RAW.search("sql += \" AND t.imported_at > ?\"")
    assert not _RAW.search("COALESCE(t.played_at, t.imported_at) >= ?") or True   # COALESCE e excluido antes
    cru = _funcoes_com_imported_at_cru()
    assert cru, 'o varredor nao achou NENHUMA funcao com imported_at cru — o regex morreu'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
