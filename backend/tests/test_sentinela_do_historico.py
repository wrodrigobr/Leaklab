# -*- coding: utf-8 -*-
"""`last_n=0` significa HISTORICO GENUINO — em TODA funcao que aceita o parametro.

── O que originou (05/09) ────────────────────────────────────────────────────────────────

O dono pediu para o dashboard abrir em "Historico" por padrao, em vez de "ultimos 50". Antes
de trocar, medi como cada card se comporta com `last_n=0`:

    funcao                     last_n=None   last_n=50   last_n=0
    get_evolution_metrics      78            50          0        <-- VAZIO
    get_player_stats           3969          2041        3969
    get_gto_leak_ranking       10            10          10
    get_leak_roi_impact        10            10          10
    get_ev_leaks               10            10          10
    get_ev_summary             12            12          12

**Bug vivo, independente da troca de default:** quem escolhesse "Historico" hoje via o grafico
de evolucao do bankroll VAZIO, enquanto todos os outros cards traziam o acervo inteiro. A causa
e a regra 5 de novo — a janela de tempo tem duas implementacoes, `_build_tournament_filter` e a
consulta propria do `get_evolution_metrics`, e o sentinela `last_n=0` so foi ensinado a uma
delas. Como `0` nao e `None`, ele caia no ramo de volume e virava `LIMIT 0`.

── O contrato que este arquivo defende ──────────────────────────────────────────────────

**Historico nunca pode devolver MENOS que a janela padrao.** E uma invariante, nao um teste do
caso conhecido: qualquer funcao futura que aceite `last_n` e esqueca o sentinela cai aqui, sem
que ninguem precise lembrar de conferir. Testar so `get_evolution_metrics` congelaria o caso
que ja achamos e continuaria cego para o proximo.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                          # noqa: E402
import database.repositories as repo                                   # noqa: E402
from database.repositories import _adapt, _build_tournament_filter     # noqa: E402

#: Funcoes do dashboard que recebem o `last_n` do filtro "Volume". Cada uma devolve algo
#: MENSURAVEL (linhas, maos ou itens) para a invariante poder comparar os tres modos.
_MEDIDAS = (
    ('get_evolution_metrics', lambda uid, ln: len(repo.get_evolution_metrics(uid, 3650, last_n=ln))),
    ('get_player_stats',      lambda uid, ln: repo.get_player_stats(uid, 3650, last_n=ln)['total_hands']),
    ('get_gto_leak_ranking',  lambda uid, ln: len(repo.get_gto_leak_ranking(uid, 3650, last_n=ln))),
    ('get_leak_roi_impact',   lambda uid, ln: len(repo.get_leak_roi_impact(uid, 3650, last_n=ln))),
    ('get_ev_leaks',          lambda uid, ln: len(repo.get_ev_leaks(uid, 3650, last_n=ln) or {})),
    ('get_player_stats_by_position',
     lambda uid, ln: repo.get_player_stats_by_position(uid, 3650, last_n=ln)['total_hands']),
)

#: Torneios ANTIGOS de proposito: fora de qualquer janela de dias, dentro do historico. Se o
#: sentinela nao valer, eles somem — que e exatamente o sintoma que o dono veria.
_ANTIGOS = 6
_RECENTES = 4


def _semeia():
    init_db()
    conn = get_conn()
    for tabela in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % tabela)
    conn.commit()
    conn.close()

    uid = repo.create_user('hist', 'hist@t.local', 'senha12345', 'player')
    conn = get_conn()
    n = 0
    for i in range(_ANTIGOS + _RECENTES):
        antigo = i < _ANTIGOS
        data = '2024-01-%02d 12:00:00' % (i + 1) if antigo else '2026-09-0%d 12:00:00' % (i - _ANTIGOS + 1)
        conn.execute(_adapt(
            "INSERT INTO tournaments (id, user_id, tournament_id, site, hero, played_at, imported_at) "
            "VALUES (?, ?, ?, 'pokerstars', 'Hero', ?, ?)"),
            (i + 1, uid, 'T%d' % i, data, data))
        for _ in range(40):
            n += 1
            conn.execute(_adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, "
                "action_taken, best_action, score, label) "
                "VALUES (?, ?, 'preflop', 'BTN', ?, 'raise', 0.1, 'standard')"),
                (i + 1, 'H%d' % n, 'raise' if n % 2 else 'fold'))
    conn.commit()
    conn.close()
    return uid


def test_o_sentinela_esta_declarado_no_filtro_canonico():
    """A fonte da regra. Se ela mudar, o resto do arquivo esta medindo outra coisa."""
    where, params = _build_tournament_filter(1, days=90, last_n=0)
    assert '?' in where and len(params) >= 1
    # Historico nao pode carregar corte de data nem LIMIT.
    assert 'LIMIT' not in where.upper(), where
    assert 'imported_at >=' not in where and 'played_at' not in where, where


def test_historico_NUNCA_devolve_menos_que_a_janela_padrao():
    """A invariante, e a varredura N+1.

    `last_n=0` e o acervo INTEIRO; `last_n=None` e uma janela de dias. O historico nao pode
    ser menor. Funcao nova que aceite `last_n` e esqueca o sentinela cai aqui.
    """
    uid = _semeia()
    falhas = []
    for nome, medir in _MEDIDAS:
        try:
            janela = medir(uid, None)
            historico = medir(uid, 0)
        except Exception as e:                                  # noqa: BLE001
            falhas.append('%s: %s: %s' % (nome, type(e).__name__, e))
            continue
        if historico < janela:
            falhas.append('%s: historico=%s < janela=%s' % (nome, historico, janela))
    assert not falhas, 'sentinela `last_n=0` nao vale em: ' + '; '.join(falhas)


def test_historico_ENXERGA_os_torneios_antigos():
    """Contraprova (regra 1): sem ela o teste acima passaria com tudo devolvendo o mesmo
    numero por acidente. Aqui a semeadura tem torneios de 2024, fora de qualquer janela de
    dias — o historico TEM de conta-los, e a janela padrao NAO."""
    uid = _semeia()
    total = _ANTIGOS + _RECENTES
    assert len(repo.get_evolution_metrics(uid, 3650, last_n=0)) == total, 'historico perdeu torneio'
    # `days=30` deixa os de 2024 de fora: se nao deixasse, a comparacao acima nao provaria nada.
    janela_curta = len(repo.get_evolution_metrics(uid, 30, last_n=None))
    assert janela_curta < total, 'a janela curta nao exclui os antigos; o teste nao mede nada'


def test_volume_continua_cortando():
    """Contraprova do lado oposto: se `last_n=N` parasse de limitar, o sentinela teria sido
    'consertado' desligando o recurso inteiro."""
    uid = _semeia()
    assert len(repo.get_evolution_metrics(uid, 3650, last_n=3)) == 3


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
