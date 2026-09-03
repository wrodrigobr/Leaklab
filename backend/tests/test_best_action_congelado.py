# -*- coding: utf-8 -*-
"""test_best_action_congelado.py — best_action fica STALE quando o nó GTO era parcial no
momento da carga (03/09, achado pela varredura de invariantes AUTO).

O bug: no ramo "nó parcial" de `evaluate_decision`, `best_action` só é sobrescrito quando
`gto_label == 'gto_critical'` — pra `gto_minor_deviation`/`gto_mixed` ele fica congelado no
palpite heurístico de ANTES do solve completo existir. Nada além disso toca `best_action`
depois do save inicial (`reconcile_tournament_labels` só reescreve `label`/`score`). Resultado
medido em produção: 20 decisões do Rullian com `label` de erro E `best_action == action_taken`
— o card mostra "✗ Erro" ao lado de "o ideal era exatamente isso que você fez".

A coluna `gto_action` (sinal bruto, separada de `best_action`) SEMPRE reflete o nó atual —
nunca fica stale. O conserto realinha `best_action` a ela, mas SÓ na contradição exata:
label com severidade de erro (>= small_mistake) E best_action==action_taken E gto_action
diferente. Cinco casos, cinco garantias — a maioria prova que o conserto NÃO mexe onde não
deve (regra 7: o conserto não pode criar dano que o bug não causava).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_best_action_congelado_test.db'
if os.path.exists('_best_action_congelado_test.db'):
    os.remove('_best_action_congelado_test.db')

import database.schema as schema
schema.init_db()

from database.repositories import _adapt, get_conn, reconcile_tournament_labels

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


conn = get_conn()
conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (1,'u','u@e.st','h')"))
conn.execute(_adapt(
    "INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, hero) "
    "VALUES (1, 1, 'T1', 'Torneio 1', 'Hero')"))


def _dec(did, label, gto_label, action_taken, best_action, gto_action):
    conn.execute(_adapt("""
        INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board,
            action_taken, best_action, gto_action, label, gto_label, score, position,
            vs_position, stack_bb, pot_size, facing_bet, estimated_equity, ev_loss_source,
            num_players)
        VALUES (?, 1, ?, 'river', 'AsKs', '["3c","Qd","Ts","Jh","6s"]',
            ?, ?, ?, ?, ?, 0.5, 'BB', 'BTN', 23.7, 5.4, 0.0, 0.97, 'gw_har', 9)
    """), (did, f'H{did}', action_taken, best_action, gto_action, label, gto_label))


# 1) A CONTRADIÇÃO REAL — exatamente o padrão medido em produção. Deve ser corrigida.
_dec(1, 'clear_mistake', 'gto_minor_deviation', 'bet', 'bet', 'check')

# 2) CONTROLE: best_action JÁ é diferente da jogada (sem contradição) — nada a fazer, e o
#    conserto NÃO pode mexer aqui (senão estaria reescrevendo um veredito que já era correto).
_dec(2, 'clear_mistake', 'gto_minor_deviation', 'bet', 'check', 'check')

# 3) CONTROLE: severidade abaixo do limiar (marginal) — fora do escopo do achado, não tocar.
_dec(3, 'marginal', 'gto_minor_deviation', 'bet', 'bet', 'check')

# 4) CONTROLE: gto_action ausente — sem sinal confiável pra realinhar, não tocar.
_dec(4, 'small_mistake', 'gto_minor_deviation', 'call', 'call', None)

# 5) CONTROLE: as três concordam de verdade (sem contradição nenhuma) — não tocar.
_dec(5, 'clear_mistake', 'gto_minor_deviation', 'bet', 'bet', 'bet')

conn.commit()
conn.close()

n = reconcile_tournament_labels(1)
check(n >= 1, f"reconcile reportou pelo menos 1 mudança de best_action, veio {n}")

conn = get_conn()
rows = {r['id']: dict(r) for r in conn.execute(
    "SELECT id, action_taken, best_action, gto_action, label FROM decisions").fetchall()}
conn.close()

check(rows[1]['best_action'] == 'check',
      f"caso 1 (contradição real): best_action devia virar 'check', veio {rows[1]['best_action']}")
check(rows[2]['best_action'] == 'check',
      f"caso 2 (já divergia): best_action não devia mudar, veio {rows[2]['best_action']}")
check(rows[3]['best_action'] == 'bet',
      f"caso 3 (severidade marginal, fora de escopo): best_action não devia mudar, veio {rows[3]['best_action']}")
check(rows[4]['best_action'] == 'call',
      f"caso 4 (sem gto_action): best_action não devia mudar, veio {rows[4]['best_action']}")
check(rows[5]['best_action'] == 'bet',
      f"caso 5 (sem contradição, todos concordam): best_action não devia mudar, veio {rows[5]['best_action']}")

if os.path.exists('_best_action_congelado_test.db'):
    try:
        os.remove('_best_action_congelado_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
