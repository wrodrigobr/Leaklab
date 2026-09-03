# -*- coding: utf-8 -*-
"""test_janela_do_dashboard.py — filtro de período do dashboard, UNIFICADO (03/09).

Trava dupla:
1. Sem janela, o headline "Hoje" e a "sangria por street" somavam a conta INTEIRA desde
   sempre — um jogador que melhorou ao longo dos meses carregava o passado ruim pra sempre
   no número, escondendo a evolução real. `get_ev_summary(last_n=N)` corta para os N
   torneios mais recentes.
2. O filtro "Volume" que já regia os OUTROS 8 cards do dashboard (evolution, gto-quality...)
   tinha só DOIS modos em `_build_tournament_filter`: last_n=N (N torneios) e last_n=None
   (fallback SILENCIOSO de 90 dias) — o botão "Todos" mandava None, e ninguém em NENHUM dos
   ~14 lugares que usam essa função conseguia ver o histórico genuíno. `last_n=0` é o
   sentinela novo pra isso, e por fluir sozinho pelos chamadores (regra 5), este teste prova
   TANTO get_ev_summary QUANTO um consumidor independente (get_gto_quality_breakdown).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_janela_dash_test.db'
if os.path.exists('_janela_dash_test.db'):
    os.remove('_janela_dash_test.db')

import database.schema as schema
schema.init_db()

from datetime import datetime, timedelta
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
    """Torneio i (1..n) com UMA decisão de ev_loss_bb = i, importado i SEGUNDOS depois do
    anterior (imported_at explícito — o default do banco tem resolução de 1s, e inserir
    dezenas de linhas no mesmo laço pode empatar timestamp, deixando o corte de janela
    ambíguo). Soma conhecida: sum(1..n) = n*(n+1)/2. i MAIOR = importado DEPOIS = mais recente."""
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (?,?,?,?)"),
                (uid, f'janela{uid}', f'j{uid}@e.st', 'h'))
    base = datetime(2026, 1, 1)
    for i in range(1, n_torneios + 1):
        quando = (base + timedelta(seconds=i)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero, imported_at) "
            "VALUES (?,?,?,?,?)"), (uid, f'T{i}', f'Torneio {i}', 'Hero', quando))
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


# ── conta GRANDE (45 torneios): janela de 40 corta os 5 mais ANTIGOS (T1..T5) ────────────────
_semear(101, 45)
soma_45 = 45 * 46 // 2          # 1035 — histórico
soma_40_mais_recentes = soma_45 - (1 + 2 + 3 + 4 + 5)   # 1020 — exclui T1..T5

r_hist = get_ev_summary(101, last_n=0)
r_janela = get_ev_summary(101, last_n=40)
r_default = get_ev_summary(101)   # default deve ser 50 → conta de 45 inteira (não corta)

check(r_hist['total_loss_bb'] == soma_45, f"histórico (last_n=0) soma tudo: esperado {soma_45}, veio {r_hist['total_loss_bb']}")
check(r_janela['total_loss_bb'] == soma_40_mais_recentes,
      f"last_n=40 exclui os 5 mais antigos: esperado {soma_40_mais_recentes}, veio {r_janela['total_loss_bb']}")
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

# ── REGRA 5: o sentinela flui sozinho por OUTRO consumidor de _build_tournament_filter ───────
# get_gto_quality_breakdown nunca foi tocado nesta mudança — se last_n=0 também vira "tudo"
# aqui, a correção no helper compartilhado propagou de verdade, não só no card que a motivou.
q_hist = get_gto_quality_breakdown(101, last_n=0)
q_janela40 = get_gto_quality_breakdown(101, last_n=40)
check(q_hist['total_with_gto'] == 45, f"gto-quality (outro consumidor): last_n=0 vê os 45 torneios, veio {q_hist['total_with_gto']}")
check(q_janela40['total_with_gto'] == 40, f"gto-quality: last_n=40 vê só 40, veio {q_janela40['total_with_gto']}")

# ── o helper cru, isolado: last_n=0 nunca aplica o fallback de dias ──────────────────────────
tf0, tp0 = _build_tournament_filter(999, days=90, last_n=0)
check('imported_at' not in tf0 and 'LIMIT' not in tf0, f"last_n=0 não tem teto de dias nem de contagem: {tf0}")
check(tp0 == (999,), f"last_n=0 só filtra por user_id: {tp0}")

if os.path.exists('_janela_dash_test.db'):
    try:
        os.remove('_janela_dash_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
