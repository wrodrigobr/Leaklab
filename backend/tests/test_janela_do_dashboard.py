# -*- coding: utf-8 -*-
"""test_janela_do_dashboard.py — filtro de período do "Hoje" (03/09, achado do dono).

Trava: sem janela, o headline e a "sangria por street" somavam a conta INTEIRA desde
sempre — um jogador que melhorou ao longo dos meses carregava o passado ruim pra sempre no
número, escondendo a evolução real. `get_ev_summary(window_tournaments=N)` corta para os N
torneios mais recentes; `None` é histórico, e nunca é o default silencioso (rota valida a
chave da query string). Conta pequena (< N) não sente a mudança — a janela vira a conta
inteira mesmo.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_janela_dash_test.db'
if os.path.exists('_janela_dash_test.db'):
    os.remove('_janela_dash_test.db')

import database.schema as schema
schema.init_db()

from database.repositories import _adapt, get_conn, get_ev_summary, EV_WINDOW_OPTIONS

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
    """Torneio i (1..n) com UMA decisão de ev_loss_bb = i. tournaments.id cresce junto —
    'ORDER BY id DESC' pega os de MAIOR id como 'mais recentes', então o corte de janela
    exclui os i MENORES primeiro. Soma conhecida: sum(1..n) = n*(n+1)/2."""
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (?,?,?,?)"),
                (uid, f'janela{uid}', f'j{uid}@e.st', 'h'))
    for i in range(1, n_torneios + 1):
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, tournament_name, hero) "
            "VALUES (?,?,?,?)"), (uid, f'T{i}', f'Torneio {i}', 'Hero'))
        tid = conn.execute(_adapt(
            "SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
            (uid, f'T{i}')).fetchone()['id']
        # 'call' (não fold): o teto de fold é fechado (equity×pote) e ficaria bem menor que 45;
        # aqui só precisa caber no teto FÍSICO (pot_bb + 2×stack_bb) — folgado de propósito
        # (110bb) pra até i=45 passar sem esbarrar em nada que não seja a janela sendo testada.
        conn.execute(_adapt("""
            INSERT INTO decisions (tournament_id, hand_id, street, hero_cards, board,
                action_taken, best_action, label, score, position, vs_position, stack_bb,
                pot_size, facing_bet, estimated_equity, ev_loss_source, ev_loss_bb, num_players)
            VALUES (?, 'H', 'preflop', 'AsKs', '[]', 'call', 'raise', 'small_mistake', 0.3,
                'BTN', 'CO', 50.0, 10.0, 2.0, 0.40, 'gw_har', ?, 9)
        """), (tid, float(i)))
    conn.commit()
    conn.close()


# ── conta GRANDE (45 torneios): janela de 40 corta os 5 mais antigos ─────────────────────────
_semear(101, 45)
soma_45 = 45 * 46 // 2          # 1035 — histórico
soma_40_mais_recentes = soma_45 - (1 + 2 + 3 + 4 + 5)   # 1020 — exclui T1..T5

r_hist = get_ev_summary(101, window_tournaments=None)
r_janela = get_ev_summary(101, window_tournaments=40)
r_default = get_ev_summary(101)   # default deve ser IGUAL a window_tournaments=40

check(r_hist['total_loss_bb'] == soma_45, f"histórico soma tudo: esperado {soma_45}, veio {r_hist['total_loss_bb']}")
check(r_janela['total_loss_bb'] == soma_40_mais_recentes,
      f"janela=40 exclui os 5 mais antigos: esperado {soma_40_mais_recentes}, veio {r_janela['total_loss_bb']}")
check(r_default['total_loss_bb'] == r_janela['total_loss_bb'], "default (sem args) == window_tournaments=40")
check(r_janela['window_tournaments'] == 40, "resposta ECOA a janela aplicada (front usa pra rotular)")
check(r_hist['window_tournaments'] is None, "histórico ecoa None")

# a sangria por street tem a MESMA propriedade — é a mesma lista filtrada (regra 5)
check(sum(x['loss_bb'] for x in r_janela['by_street']) == soma_40_mais_recentes,
      "sangria por street soma igual ao total, mesma janela")
check(sum(x['loss_bb'] for x in r_hist['by_street']) == soma_45,
      "sangria por street no histórico soma tudo")

# ── conta PEQUENA (8 torneios): janela de 40 não corta nada — mesmo resultado ────────────────
_semear(102, 8)
soma_8 = 8 * 9 // 2
r_peq_janela = get_ev_summary(102, window_tournaments=40)
r_peq_hist = get_ev_summary(102, window_tournaments=None)
check(r_peq_janela['total_loss_bb'] == soma_8 == r_peq_hist['total_loss_bb'],
      f"conta pequena: janela e histórico batem (esperado {soma_8})")

# ── mapa de opções da rota (o que a query string aceita) ─────────────────────────────────────
check(EV_WINDOW_OPTIONS == {'10': 10, '40': 40, 'all': None}, f"opções da rota: {EV_WINDOW_OPTIONS}")

if os.path.exists('_janela_dash_test.db'):
    try:
        os.remove('_janela_dash_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
