"""Re-analisa UM torneio a partir do raw_text já guardado: re-parseia (parser atual),
reconstrói as decisões e faz save_decisions (DELETE+insert → substitui), depois roda o
preflop sync + reconcile de labels. Usado depois do fix do parser (GG blind com milhar)
pra as decisões gravadas em FICHAS recomputarem em BB (stack_bb/potBb/hash corretos).

NÃO enfileira postflop (use `reenqueue_postflop_from_decisions --tid` depois, que casa o
hash do lookup) nem chama o solver. Sequência completa pós-fix:
    1) python -m scripts.reprocess_tournament --tid <T> --apply
    2) python -m scripts.reenqueue_postflop_from_decisions --tid <T>
    3) python -m scripts.drain_solver_queue           (resolve a fila)
    4) python -m scripts.resync_postflop_gto --apply   (cola os gto_label)

Uso:
    python -m scripts.reprocess_tournament --tid 293241904          # dry-run (conta)
    python -m scripts.reprocess_tournament --tid 293241904 --apply  # aplica
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn
from database.repositories import save_decisions, reconcile_tournament_labels
from leaklab.parser import parse_pokerstars_file_from_text, _extract_showdown_result
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def _arg(f):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv and sys.argv.index(f) + 1 < len(sys.argv) else None


def _showdown(raw_text, hero):
    """Igual ao _detect_showdown do app, sem importar o Flask."""
    res = _extract_showdown_result(raw_text, hero)
    if res is not None:
        return res
    if not re.search(r'\b' + re.escape(hero) + r'\s*:\s*shows?\b', raw_text):
        return None
    return 'won' if re.search(r'\b' + re.escape(hero) + r'\s+collected\b', raw_text) else 'lost'


def _build_results(hands, hero_default):
    results = []
    for hand in hands:
        hero = hand.hero or hero_default or 'Hero'
        sd = _showdown(hand.raw_text or '', hero)
        for di in build_decision_inputs_for_hand(hand):
            r = evaluate_decision(di)
            interp = r.get('interpretation', {})
            results.append({
                **r,
                'street':          di['street'],
                'context':         di['context'],
                'math':            di['math'],
                'spot':            di['spot'],
                'hero_cards':      hand.hero_cards,
                'board':           hand.board or [],
                'draw_profile':    di['math'].get('drawProfile', ''),
                'position':        di['spot'].get('position', ''),
                'num_players':     di['context'].get('activePlayers', 0),
                'level_sb':        di['context'].get('levelSb', 0),
                'level_bb':        di['context'].get('levelBb', 0),
                'level_num':       di['context'].get('levelNum', 0),
                'note':            interp.get('strategicExplanation', '') or interp.get('mathExplanation', ''),
                'is_3bet':         di.get('is_3bet', False),
                'showdown_result': sd,
            })
    return results


def main():
    tid = _arg('--tid')
    apply = '--apply' in sys.argv
    if not tid:
        print(__doc__); return

    conn = get_conn()
    row = conn.execute("SELECT id, raw_text, hero FROM tournaments WHERE tournament_id = ?", (tid,)).fetchone()
    if not row:
        print(f"torneio {tid} não encontrado"); return
    t = dict(row)
    if not t.get('raw_text'):
        print("sem raw_text"); return

    hands = parse_pokerstars_file_from_text(t['raw_text'])
    # Sanidade: nenhuma mão pode ficar sem bb (senão o bug do pot volta).
    no_bb = [h.hand_id for h in hands if not h.bb or h.bb <= 0]
    print(f"torneio {tid} (db id {t['id']}) | {len(hands)} mãos | sem bb: {len(no_bb)}")
    if no_bb:
        print(f"  ⚠️ {len(no_bb)} mãos AINDA sem bb — o parser não cobre este formato. Abortado.")
        print(f"     exemplos: {no_bb[:3]}")
        return

    results = _build_results(hands, t.get('hero'))
    print(f"decisões reconstruídas: {len(results)}")

    if not apply:
        # amostra de stacks pra provar que saíram em BB (não fichas)
        sample = [round(float((d.get('spot') or {}).get('effectiveStackBb') or 0), 1)
                  for d in results[:8]]
        print(f"stacks(bb) amostra: {sample}")
        print("\n[dry-run] rode com --apply pra gravar (save_decisions substitui as decisões).")
        return

    save_decisions(t['id'], results)
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        from sync_gto_labels_from_ranges import sync_tournament
        sync_tournament(t['id'])
    except Exception as e:
        print(f"  preflop sync falhou: {e}")
    try:
        n = reconcile_tournament_labels(t['id'])
        print(f"  reconcile: {n} labels")
    except Exception as e:
        print(f"  reconcile falhou: {e}")

    print(f"\nOK: {len(results)} decisões regravadas em BB. Agora rode, para este --tid:\n"
          f"  reenqueue_postflop_from_decisions --tid {tid}  ->  drain_solver_queue  ->  resync_postflop_gto --apply")


if __name__ == '__main__':
    main()
