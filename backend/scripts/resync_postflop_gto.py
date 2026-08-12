"""
resync_postflop_gto.py -- Reconcilia decisions POSTFLOP (label, best_action,
gto_label, gto_action) com o recompute FRESCO do engine.

Contexto: o gto postflop em `decisions` foi gravado contra a tabela `gto_nodes`
ANTES da limpeza desta sessão (delete de nodes corrompidos, recuperação via
bet_bucket, fix do normalize_cards no insert + no compute_spot_hash). Como o
produto serve o gto_label/gto_action ARMAZENADO, decisões antigas ficaram stale:
verditos sem node de respaldo (vanished), verditos recuperáveis não exibidos
(appeared) e labels divergentes (incl. falsos gto_critical super-penalizando).

Pós-limpeza, o lookup on-demand (evaluate_decision) é AUTORITATIVO. Este script
regrava os 4 campos JUNTOS (do mesmo recompute) — nunca só o label, evitando
inconsistência label↔gto (label_gto_conflict). Diferente do sync_label_bestaction
(que preserva gto de propósito), aqui o objetivo é justamente sincronizar o gto.

Por padrão só postflop (`gto_nodes`). Com `--street preflop` reconcilia o
preflop range-backed (`analyze_preflop`) — útil após mudanças nas tabelas de
range / nos params de cenário (ex.: fix de squeeze adicionou `facing_raises`/
`hero_was_aggressor`, que deixaram phantoms `gto_correct` em spots non-RFI/limp
agora corretamente `unavailable`). `--street all` faz os dois. Em todos os casos
o `evaluate_decision` é a fonte autoritativa.

Matching por `(hand_id, street, action_taken)`, que **não é chave única** — o hero age duas vezes
na mesma street sempre que paga e depois enfrenta um raise. Isso era PULADO ("multi-decision
ambíguo"); desde 05/08 é pareado POSICIONALMENTE, com as duas fontes em ordem cronológica
(`ORDER BY id` no banco, ordem das ações no pipeline). Só continua pulado quando as CONTAGENS
divergem entre os dois lados, aí a correspondência não está provada. Ver `_pares_por_ordem`.

Uso:
    python scripts/resync_postflop_gto.py                       # dry-run (postflop)
    python scripts/resync_postflop_gto.py --apply
    python scripts/resync_postflop_gto.py --street preflop --apply
    python scripts/resync_postflop_gto.py --street all --apply
"""
import sys, os, argparse
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db, USE_POSTGRES
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def _pares_por_ordem(srows, frows):
    """Pares (linha_do_banco, recalculo) da MESMA chave `(hand_id, street, ação)`.

    Essa chave NÃO é única: o hero age duas vezes na mesma street sempre que paga um open e
    depois enfrenta um 3-bet, ou aposta e depois enfrenta um raise. Antes, chave com mais de uma
    decisão era PULADA inteira — o resync simplesmente não alcançava essas decisões, e o relatório
    dizia só "pulados (ambíguo)", sem distinguir "concordam" de "divergem".

    Pareia POSICIONALMENTE: as duas fontes são cronológicas (o SELECT ordena por `id`, que é a
    ordem de gravação; o pipeline devolve na ordem das ações). Mesma regra do
    `leaklab.pareamento_decisoes`, que resolveu isto no `/replay`.

    **Contagem diferente entre os lados devolve VAZIO.** Aí a correspondência não está provada
    (torneio analisado por versão anterior do parser, decisão a mais ou a menos), e gravar no
    palpite escreveria o solve na decisão errada — foi assim que 90 vereditos errados foram parar
    na tela uma vez. Perder cobertura é honesto; trocar veredito não é.
    """
    if not srows or len(srows) != len(frows):
        return []
    return list(zip(srows, frows))


def _norm(v):
    """'' e None são equivalentes (sem cobertura)."""
    return v if v else None


def _avaliacao_fresca(r):
    """Dict fresco da avaliacao — FONTE UNICA dos dois passos (gancho automatico e CLI).

    Eram dois builders copiados; em 12/08 o conserto dos campos-viajantes editou um e o
    comparador lia o outro — 2.500 de 2.500 linhas "com drift" porque `played` nao existia
    no dict. Regra dos N lugares: quem precisar deste formato chama ESTA funcao."""
    g = r.get("gto") or {}
    return {
        "label":      (r.get("evaluation") or {}).get("label") or None,
        "best":       r.get("bestAction") or None,
        "gto_label":  _norm(g.get("gto_label")),
        "gto_action": _norm(g.get("gto_action")),
        # Os campos que DESCREVEM a avaliacao viajam juntos, ou a linha vira quimera:
        # em 12/08 o resync gravou label+gto_label novos e deixou played_freq/ev VELHOS —
        # a linha 321149 saiu `gto_correct + small_mistake` com ev=0.0 no banco, quando a
        # avaliacao real tinha ev=1.61 (o caso RC-B legitimo). A varredura pegou em
        # minutos (SELO 0 -> 1). Mesma familia do reanalyze_all_labels de 11/08.
        "played":     g.get("played_freq") if g.get("available") else None,
        "top":        g.get("gto_freq") if g.get("available") else None,
        "ev":         g.get("ev_loss_bb") if g.get("available") else None,
        "ev_src":     g.get("ev_loss_source") if g.get("available") else None,
        "tem_gto":    bool(g.get("available")),
    }


def resync_tournament_postflop(tid, apply=True):
    """Re-anexa o gto (label/best/gto_label/gto_action) das decisões POSTFLOP de UM torneio,
    modo FILL-ONLY: só rotula uncovered que ganhou nó ('appeared'); nunca remove nem muda
    cobertura existente. É o re-attach usado pelo gancho automático quando a fila do torneio
    drena (corrige a cobertura artificialmente baixa pós-import). Retorna nº de decisões atualizadas.

    Self-contained (abre/fecha a própria conexão) pra ser chamável do worker do solver."""
    conn = get_conn()
    if not USE_POSTGRES:
        try:
            conn.execute("PRAGMA busy_timeout=10000")
        except Exception:
            pass
    try:
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()
        raw_text = dict(raw).get('raw_text') if raw else None
        if not raw_text:
            return 0
        try:
            hands = parse_hand_history(raw_text)
        except Exception:
            return 0

        fresh = defaultdict(list)
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                st = (di.get("street") or "").lower()
                if st == "preflop" or not st:          # só postflop
                    continue
                hid = di.get("hand_id", "")
                act = (di.get("player_action") or "").lower()
                if not hid or not act:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                fresh[(hid, st, act)].append(_avaliacao_fresca(r))

        stored = defaultdict(list)
        for r in conn.execute(
            "SELECT id, hand_id, street, action_taken, label, best_action, gto_label, gto_action "
            # ORDER BY id é PRÉ-REQUISITO do pareamento por ordem abaixo. Sem ele o Postgres não
            # garante ordem nenhuma, e parear duas listas cuja ordem não foi provada é como se
            # grava um solve no `decision_id` errado.
            "FROM decisions WHERE tournament_id=? AND lower(street)!='preflop' "
            "ORDER BY id", (tid,)).fetchall():
            d = dict(r)
            stored[(d['hand_id'], (d['street'] or '').lower(),
                    (d['action_taken'] or '').lower())].append(d)

        updated = 0
        for key, srows in stored.items():
            for s, f in _pares_por_ordem(srows, fresh.get(key, [])):
                # FILL-ONLY: só 'appeared' (era uncovered e ganhou nó). Nunca toca o que já tem gto.
                if _norm(s['gto_label']) or not f['gto_label']:
                    continue
                if apply:
                    conn.execute(
                        "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=?, "
                        "gto_played_freq=?, gto_top_freq=?, ev_loss_bb=?, ev_loss_source=? WHERE id=?",
                        (f['label'], f['best'], f['gto_label'], f['gto_action'],
                         f.get('played'), f.get('top'), f.get('ev'), f.get('ev_src'), s['id']))
                updated += 1
        if apply:
            conn.commit()
        return updated
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--street", choices=["preflop", "postflop", "all"],
                    default="postflop")
    # --fill-only: SÓ 'appeared' (era uncovered, agora tem nó). Nunca remove cobertura (vanished)
    # nem muda veredito de spot já coberto (label_drift). É o re-lookup seguro pro cron noturno.
    ap.add_argument("--fill-only", action="store_true",
                    help="só rotula uncovered que ganhou nó; não mexe no que já tem gto_label")
    ap.add_argument("--tid", type=int, default=None,
                    help="reconcilia SÓ este torneio (id interno) — rápido, por torneio")
    args = ap.parse_args()

    def _in_scope(st):
        if args.street == "all":
            return True
        if args.street == "preflop":
            return st == "preflop"
        return st != "preflop"

    init_db()
    conn = get_conn()
    if not USE_POSTGRES:                      # PRAGMA é SQLite-only; no Postgres aborta a transação
        try:
            conn.execute("PRAGMA busy_timeout=10000")
        except Exception:
            pass

    _tq = ("SELECT id FROM tournaments WHERE raw_text IS NOT NULL "
           "AND tournament_id NOT LIKE 'FAKE-%'")
    if args.tid:
        _tq += f" AND id = {int(args.tid)}"
    _tq += " ORDER BY id"
    tournaments = conn.execute(_tq).fetchall()

    changes = Counter()           # por campo
    kinds = Counter()             # vanished/appeared/label_drift/action_only
    updated = skipped = 0
    examples = []
    for trow in tournaments:
        tid = dict(trow)['id']
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()
        # acesso por CHAVE (Postgres usa RealDictCursor → row[0] dá KeyError; SQLite aceita ambos)
        raw_text = dict(raw).get('raw_text') if raw else None
        if not raw_text:
            continue
        try:
            hands = parse_hand_history(raw_text)
        except Exception:
            continue

        fresh = defaultdict(list)
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                st = (di.get("street") or "").lower()
                if not _in_scope(st):
                    continue
                hid = di.get("hand_id", "")
                act = (di.get("player_action") or "").lower()
                if not hid or not st or not act:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                fresh[(hid, st, act)].append(_avaliacao_fresca(r))

        if args.street == "all":
            street_clause = ""
        elif args.street == "preflop":
            street_clause = " AND lower(street)='preflop'"
        else:
            street_clause = " AND lower(street)!='preflop'"
        stored = defaultdict(list)
        for r in conn.execute(
            "SELECT id, hand_id, street, action_taken, label, best_action, "
            "gto_label, gto_action, gto_played_freq, gto_top_freq, ev_loss_bb, ev_loss_source "
            "FROM decisions "
            # ORDER BY id: pre-requisito do pareamento por ordem. Ver `_pares_por_ordem`.
            "WHERE tournament_id=?" + street_clause + " ORDER BY id", (tid,)).fetchall():
            d = dict(r)
            stored[(d['hand_id'], (d['street'] or '').lower(),
                    (d['action_taken'] or '').lower())].append(d)

        for key, srows in stored.items():
            pares = _pares_por_ordem(srows, fresh.get(key, []))
            if not pares:
                # So sobra aqui quem tem CONTAGEM diferente entre banco e recalculo. A chave com
                # duas decisoes de CADA lado agora e pareada por ordem, nao pulada inteira.
                skipped += len(srows)
                continue
            for s, f in pares:
                s_gl, s_ga = _norm(s['gto_label']), _norm(s['gto_action'])
                diffs = []
                if f['label'] != s['label']:      diffs.append('label')
                if f['best'] != s['best_action']: diffs.append('best_action')
                if f['gto_label'] != s_gl:        diffs.append('gto_label')
                if f['gto_action'] != s_ga:       diffs.append('gto_action')
                # Freq e EV tambem detectam mudanca — sem isto, uma linha cujos 4 campos ja
                # batem mas cujo freq/ev ficou de outra avaliacao (a quimera de 12/08) nunca
                # seria reescrita, e a proxima rodada nao a consertaria.
                def _f4(v):
                    try: return round(float(v), 4)
                    except (TypeError, ValueError): return None
                if _f4(f.get('played')) != _f4(s.get('gto_played_freq')): diffs.append('played_freq')
                if _f4(f.get('top')) != _f4(s.get('gto_top_freq')):       diffs.append('top_freq')
                if _f4(f.get('ev')) != _f4(s.get('ev_loss_bb')):          diffs.append('ev_loss')
                if not diffs:
                    continue
                # classifica a natureza da mudança de gto (conta TODOS pra o relatório, inclusive
                # os que o --fill-only vai pular — assim você vê quantos vanished/drift existem).
                is_appeared = (not s_gl) and bool(f['gto_label'])   # era uncovered, ganhou nó
                if s_gl and not f['gto_label']:        kinds['vanished'] += 1
                elif is_appeared:                      kinds['appeared'] += 1
                elif s_gl != f['gto_label']:           kinds['label_drift'] += 1
                elif 'gto_action' in diffs:            kinds['action_only'] += 1
                # --fill-only: só processa os 'appeared' (nunca remove/muda cobertura existente).
                if args.fill_only and not is_appeared:
                    continue
                updated += 1
                for d in diffs:
                    changes[d] += 1
                if len(examples) < 20:
                    examples.append(
                        f"  t{tid} {key[0]} {key[1]}/{key[2]} | "
                        f"label {s['label']}->{f['label']} | best {s['best_action']}->{f['best']} | "
                        f"gto {s_gl}/{s_ga}->{f['gto_label']}/{f['gto_action']}")
                if args.apply:
                    conn.execute(
                        "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=?, "
                        "gto_played_freq=?, gto_top_freq=?, ev_loss_bb=?, ev_loss_source=? "
                        "WHERE id=?",
                        (f['label'], f['best'], f['gto_label'], f['gto_action'],
                         f.get('played'), f.get('top'), f.get('ev'), f.get('ev_src'), s['id']))

    if args.apply:
        conn.commit()
    conn.close()
    print(f"\nReconciliados: {updated} | pulados (ambíguo): {skipped}")
    print("Por campo:", dict(changes))
    print("Natureza :", dict(kinds))
    if examples:
        print("Exemplos:\n" + "\n".join(examples))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == "__main__":
    main()
