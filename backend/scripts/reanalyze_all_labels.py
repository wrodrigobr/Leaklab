"""
Re-analisa labels de TODAS as decisões (preflop + postflop) usando o pipeline completo.

Reusa o padrão de scripts/reanalyze_preflop_labels.py mas sem filtro de street,
para que o guard novo de apply_anti_rules (fold com eq >= po + 3pp) seja aplicado
às decisões postflop existentes no banco.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

import argparse
_ap = argparse.ArgumentParser(description="Re-analisa labels de todas as decisões.")
_ap.add_argument("--dry-run", action="store_true", help="só conta o que mudaria, NÃO grava")
_ap.add_argument("--only-heuristic", action="store_true",
                 help="re-grada SÓ decisões hoje heurísticas (gto_label vazio) — barato, p/ colher cobertura nova")
_args = _ap.parse_args()
DRY = _args.dry_run
ONLY_HEUR = _args.only_heuristic
if DRY:
    print("== DRY-RUN — nada será gravado ==")
if ONLY_HEUR:
    print("== ONLY-HEURISTIC — re-grada só decisões sem GTO ==")

conn = get_conn()
# DB dev tem o app.py vivo (WAL) — espera o lock em vez de falhar na hora.
if not getattr(conn, '_pg', False):   # PRAGMA é só SQLite; no Postgres aborta a transação
    try:
        conn.execute('PRAGMA busy_timeout=30000')
    except Exception:
        pass

tournaments = conn.execute(
    "SELECT id, tournament_id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
).fetchall()

print(f"Processando {len(tournaments)} torneios com raw_text...")
total_checked = 0
total_updated = 0
sem_cobertura_agora = 0   # linhas puladas por perder cobertura GTO na re-analise
gto_gained = 0   # heurística (gto_label vazio) → GTO (label real) — responde "quantos viram GTO"
affected_tournament_ids = set()

for row in tournaments:
    tid, t_ext_id = row['id'], row['tournament_id']

    raw_text = conn.execute(
        "SELECT raw_text FROM tournaments WHERE id = ?", (tid,)
    ).fetchone()
    if not raw_text or not raw_text['raw_text']:
        continue

    try:
        hands = parse_hand_history(raw_text['raw_text'])
    except Exception as e:
        print(f"  [SKIP] Erro parse tid={tid}: {e}")
        continue

    hand_updated = 0
    seen_decisions: set = set()  # (hand_id, street, position, action) — evita DIs duplicados

    for hand in hands:
        try:
            decision_inputs = build_decision_inputs_for_hand(hand)
        except Exception:
            continue

        for di in decision_inputs:
            street  = di.get('street')
            hand_id = di.get('hand_id', '')
            spot    = di.get('spot', {})
            act     = (spot.get('actionTaken') or di.get('player_action', '')).lower()
            pos     = (di.get('position') or spot.get('position') or '').upper()
            if not hand_id or not act or not street:
                continue

            dedup_key = (hand_id, street, pos, act)
            if dedup_key in seen_decisions:
                continue
            seen_decisions.add(dedup_key)

            db_row = conn.execute(
                """SELECT id, label, best_action, gto_label, gto_action,
                          ev_loss_bb, ev_loss_source, gto_played_freq, gto_top_freq
                     FROM decisions
                   WHERE hand_id = ? AND street = ? AND action_taken = ?
                   LIMIT 1""",
                (hand_id, street, act)
            ).fetchone()
            if not db_row:
                continue

            did        = db_row['id']
            old_played = db_row['gto_played_freq']
            old_top    = db_row['gto_top_freq']
            old_label = db_row['label']
            old_best  = db_row['best_action']
            old_gtolbl = db_row['gto_label']
            old_gtoact = db_row['gto_action']

            # --only-heuristic: pula decisões que já têm GTO (só colhe heurística→GTO,
            # evita jitter nas já-gradadas e é muito mais barato — usado pelo drain #29).
            if ONLY_HEUR and old_gtolbl not in (None, '', 'wizard_pending'):
                continue

            try:
                result    = evaluate_decision(di)
                new_label = (result.get('evaluation') or {}).get('label') or old_label
                new_best  = result.get('bestAction') or old_best
                gto_dict  = result.get('gto') or {}
                # As FREQUENCIAS andam com o gabarito. Elas nao estavam no UPDATE, entao ficavam
                # velhas ao lado de um `gto_label` novo — os dois campos passavam a descrever
                # avaliacoes diferentes. Medido em 11/08: o relabel limpou o gto_label de 44
                # linhas e a invariante FREQ continuou em 43, com o par impossivel
                # played=1.0 / top=0.0 intacto.
                new_played = gto_dict.get('played_freq')
                new_top    = gto_dict.get('gto_freq')

                # `spot_mismatch` entrou junto de `ungradeable_action` em 11/08: os dois
                # significam "este no NAO responde a esta pergunta", e nos dois o certo e LIMPAR
                # o gabarito velho, nao preserva-lo. Um no de check servido a quem enfrenta
                # aposta e resposta trocada, e resposta trocada e pior que ausente.
                if gto_dict.get('ungradeable_action') or gto_dict.get('spot_mismatch'):
                    # Ação fora da árvore solvada (ex.: shove em árvore sem branch de
                    # raise): o nó NÃO grade essa ação. Limpa os campos GTO antigos —
                    # mantê-los preservava o 'fold/gto_critical' podre gravado antes
                    # do fix (shove com a wheel no torneio 388).
                    new_gtolbl = None
                    new_gtoact = None
                    new_played = new_top = None
                else:
                    new_gtolbl = gto_dict.get('gto_label') if gto_dict.get('available') else old_gtolbl
                    new_gtoact = gto_dict.get('gto_action') if gto_dict.get('available') else old_gtoact
                    if not new_gtolbl: new_gtolbl = old_gtolbl
                    if not new_gtoact: new_gtoact = old_gtoact
                    if not gto_dict.get('available'):
                        new_played, new_top = old_played, old_top
                # Fase 3 / #24 postflop: a re-análise também sincroniza o EV loss —
                # sem isto, decisões antigas nunca ganham ev_loss_bb (só re-upload),
                # e o card "onde você sangra" fica só com o preflop do overlay.
                old_evloss = db_row['ev_loss_bb']
                old_evsrc  = db_row['ev_loss_source']
                new_evloss = gto_dict.get('ev_loss_bb')
                new_evsrc  = gto_dict.get('ev_loss_source')
                if new_evloss is None and not (gto_dict.get('ungradeable_action')
                                                or gto_dict.get('spot_mismatch')):
                    new_evloss, new_evsrc = old_evloss, old_evsrc

                # A avaliação NOVA perdeu a cobertura GTO que a gravada tinha? Então ela sabe
                # MENOS, e não pode sobrescrever o label.
                #
                # O fallback acima ("se não veio gto_label novo, mantém o velho") existe para não
                # apagar cobertura por falha transitória de lookup. Mas ele preserva o gto_label
                # ao lado de um `label` calculado SEM ele — e os dois campos deixam de descrever
                # a mesma avaliação. Medido no dry-run de 11/08: 6 decisões com o selo
                # `GTO Correto` gravado passariam a `small_mistake`, e a sonda mostrou
                # `gto_available=False` no motor nas 6. O card exibiria selo e acusação juntos.
                #
                # Pular é honesto: a linha fica como está, com o par (label, gto_label) coerente
                # entre si, e a próxima rodada com cobertura resolve. Sobrescrever seria trocar
                # uma resposta certa por uma menos informada — o tipo de conserto que faz dano
                # que o bug não fazia.
                # A recusa DELIBERADA nao conta como "perdeu cobertura": ela e o conserto.
                # Sem esta linha o guarda de ontem bloqueava o conserto de hoje — medido no
                # dry-run: "Mudariam: 0 | puladas s/ cobertura: 19", com as 43 linhas do par
                # impossivel intactas.
                _perdeu_cobertura = (not gto_dict.get('available')
                                     and old_gtolbl not in (None, '', 'wizard_pending')
                                     and not gto_dict.get('ungradeable_action')
                                     and not gto_dict.get('spot_mismatch'))
                if _perdeu_cobertura and new_label != old_label:
                    sem_cobertura_agora += 1
                    continue
            except Exception:
                continue

            total_checked += 1
            changed = (new_label != old_label or new_best != old_best or
                       new_gtolbl != old_gtolbl or new_gtoact != old_gtoact or
                       new_evloss != old_evloss or
                       new_played != old_played or new_top != old_top)
            if changed:
                if (old_gtolbl in (None, '', 'wizard_pending')
                        and new_gtolbl not in (None, '', 'wizard_pending')):
                    gto_gained += 1
                if not DRY:
                    conn.execute(
                        "UPDATE decisions SET label = ?, best_action = ?, gto_label = ?, "
                        "gto_action = ?, ev_loss_bb = ?, ev_loss_source = ?, "
                        "gto_played_freq = ?, gto_top_freq = ? WHERE id = ?",
                        (new_label, new_best, new_gtolbl, new_gtoact, new_evloss, new_evsrc,
                         new_played, new_top, did)
                    )
                hand_updated += 1
                total_updated += 1
                affected_tournament_ids.add(tid)
                # Em DRY-RUN imprime TUDO. O corte em 30 existe para não afogar o log de uma
                # execução real de milhares de linhas, mas no dry-run a lista É o produto: em
                # 11/08 ele reportou "Mudariam: 42" mostrando 30, e as 12 escondidas eram
                # exatamente o que faltava para decidir se aplicava. Diagnóstico que trunca
                # calado não fecha decisão.
                if DRY or total_updated <= 30 or total_updated % 50 == 0:
                    print(f"  tid={tid} hand={hand_id} {street}/{act}: "
                          f"{old_label}->{new_label} | gto {old_gtolbl}->{new_gtolbl}")

    if hand_updated and not DRY:
        conn.commit()

# Recalcular standard_pct nos torneios afetados
if affected_tournament_ids and not DRY:
    print(f"\nRecalculando standard_pct de {len(affected_tournament_ids)} torneios...")
    for tid in sorted(affected_tournament_ids):
        std_row = conn.execute(
            """SELECT
                 COUNT(CASE WHEN label = 'standard' THEN 1 END) * 100.0 / COUNT(*) AS std_pct,
                 AVG(score) AS avg_score
               FROM decisions WHERE tournament_id = ?""",
            (tid,)
        ).fetchone()
        if std_row:
            conn.execute(
                "UPDATE tournaments SET standard_pct = ?, avg_score = ? WHERE id = ?",
                (round(std_row['std_pct'], 2), round(std_row['avg_score'] or 0, 4), tid)
            )
    conn.commit()
    print("  standard_pct recalculado.")

conn.close()
print(f"\nConcluido. Verificadas: {total_checked} | "
      f"{'Mudariam' if DRY else 'Atualizadas'}: {total_updated} | "
      f"puladas s/ cobertura: {sem_cobertura_agora} | "
      f"heuristica->GTO: {gto_gained}")
if DRY:
    print("== DRY-RUN — nada foi gravado ==")
