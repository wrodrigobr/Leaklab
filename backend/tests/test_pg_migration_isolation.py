"""
Tabela nova no Postgres tem que nascer isolada por SAVEPOINT.

── O deploy que originou este arquivo ────────────────────────────────────────────────────────

`range_card_srs` foi criada dentro de um `try/except Exception: pass`, copiando o formato dos
blocos vizinhos — que se descrevem, em comentário, como "bloco abort-proof próprio". O deploy
subiu verde, os containers ficaram healthy, e a tabela simplesmente NÃO EXISTIA em produção.

O `CREATE` era válido: rodado sozinho no container, funciona. O que acontece é que as migrações
rodam numa transação única e, no Postgres, um statement que aborta deixa a transação inteira em
estado 'aborted' — todo statement seguinte falha até o rollback. O `except` engole esse erro e a
migração vira no-op silencioso. O comentário dizia "abort-proof" e descrevia uma intenção, não um
mecanismo (regra 8 da definição de pronto: comentário não é evidência).

O mecanismo de verdade é `_pg_exec_isolated`, que envolve cada DDL num SAVEPOINT: a falha faz
rollback só daquele statement e a transação segue viva.

── O que este arquivo trava ──────────────────────────────────────────────────────────────────

Que o número de `CREATE TABLE` desprotegidos na trilha Postgres NÃO CRESÇA. É uma catraca, e não
uma proibição: as 31 tabelas antigas nasceram assim e reescrevê-las agora seria mexer, sem
necessidade, em toda a criação de schema de um banco em produção. Elas ficam nomeadas aqui, como
dívida declarada — o que a catraca impede é a próxima tabela repetir o erro.

O sintoma, quando acontece, é sempre o mesmo e é caro de diagnosticar: "funciona no dev, não
popula nada em produção".
"""
import io, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_SCHEMA = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.py')

# As que já existiam quando a catraca foi instalada (2026-07-29). NÃO adicionar nada aqui: tabela
# nova vai na lista isolada por SAVEPOINT, junto de `coach_commissions`.
_DIVIDA_CONHECIDA = {
    'achievements', 'coach_applications', 'coach_invites', 'coach_messages', 'coach_payments',
    'coach_plan_templates', 'coach_reviews', 'drill_sessions', 'expenses', 'gto_hand_requests',
    'gto_nodes', 'gto_preflop_ranges', 'gto_solver_queue', 'gto_tournament_queue',
    'gto_tree_strategies', 'gw_raw_cache', 'leaderboard_snapshots', 'notifications',
    'opponent_profiles', 'payments', 'player_elo_history', 'progression_attempts',
    'revalidation_findings', 'revalidation_llm_cache', 'revalidation_runs', 'session_goals',
    'support_tickets', 'training_achievements', 'training_daily', 'training_proof',
    'training_skill_progress',
}


def _secao_postgres() -> str:
    """O trecho de `_run_migrations` que roda quando USE_POSTGRES, sem a trilha SQLite."""
    s = io.open(_SCHEMA, encoding='utf-8').read()
    ini = s.index('def _run_migrations')
    # a trilha SQLite começa no `else:` do `if USE_POSTGRES:`
    fim = s.index('\n    else:', ini)
    return s[ini:fim]


def _tabelas_em_try_except(pg: str) -> set:
    """CREATE TABLE que NÃO está numa lista executada por `_pg_exec_isolated`."""
    fora = set()
    for m in re.finditer(r'CREATE TABLE IF NOT EXISTS (\w+)', pg):
        antes = pg[:m.start()]
        # a lista isolada é sempre `for sql in [ ... ]` seguido de _pg_exec_isolated
        ult_lista = antes.rfind('for sql in [')
        ult_try   = antes.rfind('\n        try:')
        if ult_try > ult_lista:
            fora.add(m.group(1))
    return fora


def test_nenhuma_tabela_NOVA_nasce_desprotegida():
    desprotegidas = _tabelas_em_try_except(_secao_postgres())
    novas = desprotegidas - _DIVIDA_CONHECIDA
    assert not novas, (
        f'tabela(s) criadas em try/except na trilha Postgres: {sorted(novas)}. '
        'Um try/except NÃO sobrevive a uma transação abortada: mova o CREATE para a lista '
        'executada por _pg_exec_isolated (SAVEPOINT), junto de coach_commissions.'
    )


def test_a_divida_declarada_nao_e_ficcao():
    """Se a lista de dívida ficasse obsoleta, a catraca passaria a permitir tabela nova pelo nome
    de uma antiga que já foi migrada. O teste tem que reprovar quando a lista mente."""
    desprotegidas = _tabelas_em_try_except(_secao_postgres())
    fantasmas = _DIVIDA_CONHECIDA - desprotegidas
    assert not fantasmas, (
        f'nomes na dívida que não existem mais desprotegidos: {sorted(fantasmas)}. '
        'Remova-os de _DIVIDA_CONHECIDA — dívida que já foi paga não pode continuar '
        'servindo de permissão para tabela nova.'
    )


def test_a_tabela_do_SRS_esta_isolada():
    """O caso concreto que originou o arquivo. `range_card_srs` tem que estar na lista com
    SAVEPOINT — foi ela que não existiu em produção depois de um deploy verde."""
    assert 'range_card_srs' not in _tabelas_em_try_except(_secao_postgres())
    s = io.open(_SCHEMA, encoding='utf-8').read()
    assert 'CREATE TABLE IF NOT EXISTS range_card_srs' in s


def test_o_mecanismo_de_isolamento_existe_e_usa_savepoint():
    """Sem SAVEPOINT, `_pg_exec_isolated` seria só outro try/except com nome melhor."""
    s = io.open(_SCHEMA, encoding='utf-8').read()
    corpo = s[s.index('def _pg_exec_isolated'):s.index('def _run_migrations')]
    assert 'SAVEPOINT' in corpo and 'ROLLBACK TO SAVEPOINT' in corpo


if __name__ == '__main__':
    falhas = 0
    testes = (test_nenhuma_tabela_NOVA_nasce_desprotegida,
              test_a_divida_declarada_nao_e_ficcao,
              test_a_tabela_do_SRS_esta_isolada,
              test_o_mecanismo_de_isolamento_existe_e_usa_savepoint)
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
