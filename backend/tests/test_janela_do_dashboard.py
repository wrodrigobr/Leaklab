# -*- coding: utf-8 -*-
"""test_janela_do_dashboard.py — filtro de período do dashboard, UNIFICADO e por DATA DE
JOGO (03/09).

Três travas:
1. Sem janela, o headline "Hoje" e a "sangria por street" somavam a conta INTEIRA desde
   sempre — um jogador que melhorou ao longo dos meses carregava o passado ruim pra sempre
   no número, escondendo a evolução real. `get_ev_summary(last_n=N)` corta para os N
   torneios mais recentes.
2. O filtro "Volume" que já regia os OUTROS 8 cards do dashboard (evolution, gto-quality...)
   tinha só DOIS modos em `_build_tournament_filter`: last_n=N (N torneios) e last_n=None
   (fallback SILENCIOSO de 90 dias) — o botão "Todos" mandava None, e ninguém em NENHUM dos
   ~14 lugares que usam essa função conseguia ver o histórico genuíno. `last_n=0` é o
   sentinela novo pra isso.
3. O eixo de "recente" era `imported_at` (data do UPLOAD), não `played_at` (data do JOGO) —
   quebra na cara com lote histórico: o Rullian importou 280 torneios jogados ao longo de 3+
   meses, todos com imported_at espremido em 25 horas. Este teste prova o pior caso: semeia
   `played_at` em ordem CORRETA e `imported_at` em ordem INVERTIDA de propósito — se o código
   regredisse pro eixo errado, o resultado sairia visivelmente TROCADO (não só impreciso),
   impossível de passar batido.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_janela_dash_test.db'
if os.path.exists('_janela_dash_test.db'):
    os.remove('_janela_dash_test.db')

import database.schema as schema
schema.init_db()

from datetime import date, datetime, timedelta
from database.repositories import (
    _adapt, get_conn, get_ev_summary, get_gto_quality_breakdown, _build_tournament_filter,
)

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


def _semear(uid: int, n_torneios: int):
    """Torneio i (1..n) com UMA decisão de ev_loss_bb = i.

    played_at = base + i DIAS   → i maior = jogado DEPOIS  = mais recente de VERDADE.
    imported_at = base − i SEG  → i maior = importado ANTES = "mais antigo" se o código
    (incorretamente) usasse esse eixo — as duas ordens são DELIBERADAMENTE opostas, pra
    qualquer regressão ao eixo errado estourar como resultado trocado, não só arredondado.
    Soma conhecida: sum(1..n) = n*(n+1)/2.
    """
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (?,?,?,?)"),
                (uid, f'janela{uid}', f'j{uid}@e.st', 'h'))
    base_jogo = date(2026, 1, 1)
    base_import = datetime(2026, 9, 3, 12, 0, 0)
    for i in range(1, n_torneios + 1):
        jogado = (base_jogo + timedelta(days=i)).isoformat()
        importado = (base_import - timedelta(seconds=i)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, "
            "played_at, imported_at) VALUES (?,?,?,?,?,?)"),
            (uid, f'T{i}', f'Torneio {i}', 'Hero', jogado, importado))
        tid = conn.execute(_adapt(
            "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
            (uid, f'T{i}')).fetchone()['id']
        # 'call' (não fold): o teto de fold é fechado (equity×pote) e ficaria bem menor que 45;
        # aqui só precisa caber no teto FÍSICO (pot_bb + 2×stack_bb) — folgado de propósito
        # (110bb) pra até i=45 passar sem esbarrar em nada que não seja a janela sendo testada.
        conn.execute(_adapt("""
            INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, board,
                action_taken, best_action, label, score, position, vs_position, stack_bb,
                pot_size, facing_bet, estimated_equity, ev_loss_source, ev_loss_bb, num_players,
                gto_label)
            VALUES (?, 'H', 'preflop', 'AsKs', '[]', 'call', 'raise', 'small_mistake', 0.3,
                'BTN', 'CO', 50.0, 10.0, 2.0, 0.40, 'gw_har', ?, 9, 'gto_correct')
        """), (tid, float(i)))
    conn.commit()
    conn.close()


# ── conta GRANDE (45 torneios): últimos 40 por PLAYED_AT excluem os 5 JOGADOS mais cedo ──────
# (T1..T5 — que são justamente os IMPORTADOS por ÚLTIMO, pela ordem invertida do _semear;
# se o código usasse imported_at por engano, excluiria T41..T45, o oposto)
_semear(101, 45)
soma_45 = 45 * 46 // 2          # 1035 — histórico
soma_40_mais_recentes = soma_45 - (1 + 2 + 3 + 4 + 5)   # 1020 — exclui T1..T5 (jogados 1º)

r_hist = get_ev_summary(101, last_n=0)
r_janela = get_ev_summary(101, last_n=40)
r_default = get_ev_summary(101)   # default deve ser 50 → conta de 45 inteira (não corta)

check(r_hist['total_loss_bb'] == soma_45, f"histórico (last_n=0) soma tudo: esperado {soma_45}, veio {r_hist['total_loss_bb']}")
check(r_janela['total_loss_bb'] == soma_40_mais_recentes,
      f"last_n=40 por DATA DE JOGO exclui os 5 jogados mais cedo: esperado {soma_40_mais_recentes}, veio {r_janela['total_loss_bb']} "
      "(se veio 300, o codigo regrediu pro eixo de IMPORTACAO)")
check(r_default['total_loss_bb'] == soma_45, "default (50, sem args) não corta 45 torneios")
check(r_janela['last_n'] == 40, "resposta ECOA a janela aplicada (front usa pra sincronizar o botão)")
check(r_hist['last_n'] == 0, "histórico ecoa 0, não None")

# a sangria por street tem a MESMA propriedade — é a mesma lista filtrada (regra 5)
check(sum(x['loss_bb'] for x in r_janela['by_street']) == soma_40_mais_recentes,
      "sangria por street soma igual ao total, mesma janela")
check(sum(x['loss_bb'] for x in r_hist['by_street']) == soma_45,
      "sangria por street no histórico soma tudo")

# ── conta PEQUENA (8 torneios): janela de 40 não corta nada — mesmo resultado ────────────────
_semear(102, 8)
soma_8 = 8 * 9 // 2
r_peq_janela = get_ev_summary(102, last_n=40)
r_peq_hist = get_ev_summary(102, last_n=0)
check(r_peq_janela['total_loss_bb'] == soma_8 == r_peq_hist['total_loss_bb'],
      f"conta pequena: janela e histórico batem (esperado {soma_8})")

# ── REGRA 5: o sentinela E o eixo por played_at fluem sozinhos por OUTRO consumidor ───────────
# get_gto_quality_breakdown nunca foi tocado nesta mudança — se last_n=0 e last_n=40 também
# batem certo aqui, a correção no helper compartilhado propagou de verdade.
q_hist = get_gto_quality_breakdown(101, last_n=0)
q_janela40 = get_gto_quality_breakdown(101, last_n=40)
check(q_hist['total_with_gto'] == 45, f"gto-quality (outro consumidor): last_n=0 vê os 45 torneios, veio {q_hist['total_with_gto']}")
check(q_janela40['total_with_gto'] == 40, f"gto-quality: last_n=40 vê só 40 (por played_at), veio {q_janela40['total_with_gto']}")

# ── o helper cru, isolado: last_n=0 nunca aplica o fallback de dias, e usa played_at ─────────
tf0, tp0 = _build_tournament_filter(999, days=90, last_n=0)
check('imported_at' not in tf0 and 'LIMIT' not in tf0, f"last_n=0 não tem teto de dias nem de contagem: {tf0}")
check(tp0 == (999,), f"last_n=0 só filtra por user_id: {tp0}")
tfN, _ = _build_tournament_filter(999, last_n=5)
# COALESCE(played_at, imported_at): JOGO tem prioridade, upload é só rede de seguranca pra
# played_at nulo (fixture antiga, torneio sem data extraida) — nao pode sumir do filtro.
check(tfN.index('played_at') < tfN.index('imported_at'), f"last_n=N prioriza JOGO sobre upload: {tfN}")
tfD, _ = _build_tournament_filter(999, days=30)
check(tfD.index('played_at') < tfD.index('imported_at'), f"o fallback de dias também prioriza JOGO: {tfD}")

# ── a rede de segurança de verdade: torneio SEM played_at não pode sumir do filtro ───────────
# Regressão real pega no caminho (test_portas_do_ev.py, fixture antiga sem played_at): sem o
# COALESCE, `played_at >= since` com NULL nunca é verdadeiro em SQL nenhum — o torneio evapora
# em SILÊNCIO de toda tela com janela (o próprio card que este arquivo testa, inclusive).
conn = get_conn()
conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (?,?,?,?)"),
            (103, 'semdata', 'sd@e.st', 'h'))
conn.execute(_adapt(
    "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, imported_at) "
    "VALUES (?,?,?,?,?)"), (103, 'T-sem-data', 'Sem played_at', 'Hero', '2026-01-01 00:00:00'))
tid_sd = conn.execute(_adapt(
    "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
    (103, 'T-sem-data')).fetchone()['id']
conn.execute(_adapt("""
    INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, board,
        action_taken, best_action, label, score, position, vs_position, stack_bb,
        pot_size, facing_bet, estimated_equity, ev_loss_source, ev_loss_bb, num_players)
    VALUES (?, 'H', 'preflop', 'AsKs', '[]', 'call', 'raise', 'small_mistake', 0.3,
        'BTN', 'CO', 50.0, 10.0, 2.0, 0.40, 'gw_har', 5.0, 9)
"""), (tid_sd,))
conn.commit()
conn.close()
r_sd_hist = get_ev_summary(103, last_n=0)
r_sd_dias = get_ev_summary(103)   # cai no fallback de dias (last_n=None internamente é so via helper direto; aqui last_n=50 default, torneio unico entra de qualquer forma)
check(r_sd_hist.get('has_data') is True and r_sd_hist['total_loss_bb'] == 5.0,
      f"torneio SEM played_at não some do histórico: {r_sd_hist}")
tf_sd, tp_sd = _build_tournament_filter(103, days=9999)   # fallback de dias, o caminho que quebrava
import sqlite3 as _sq
_c = _sq.connect(schema.SQLITE_PATH)
_c.row_factory = _sq.Row
_row = _c.execute(f"SELECT COUNT(*) n FROM tournaments t WHERE {tf_sd}", tp_sd).fetchone()
check(_row['n'] == 1, f"o fallback de dias (COALESCE) também não perde o torneio sem played_at: {_row['n']}")
_c.close()

if os.path.exists('_janela_dash_test.db'):
    try:
        os.remove('_janela_dash_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
