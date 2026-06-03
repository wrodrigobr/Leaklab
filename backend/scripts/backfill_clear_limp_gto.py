"""
backfill_clear_limp_gto.py — Limpa o gto_label/gto_action/gto_freq ARMAZENADO das
decisões de POTE LIMPADO (coverage_reason='limped_pot').

Potes limpados estão FORA da cobertura GTO (árvore raise-first não cobre). Decisões
scoradas ANTES do feature de limp ganharam um gto_label (ex.: gto_critical/gto_correct)
que não deveria existir — polui gto-alignment, ELO e leak reports (e fazia o Decision
Card mostrar veredito stale contradizendo "vs Limp", já corrigido no front).

Re-avalia cada decisão preflop com facing_limp; onde coverage_reason='limped_pot' e há
gto_label armazenado, zera os 3 campos GTO. Idempotente. Dry-run por padrão (--apply
para gravar). Cross-backend via get_conn; busy_timeout p/ não brigar com o app.py vivo.
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type


def _is_limp(di) -> bool:
    sp = di.get('spot', {})
    r = analyze_preflop(
        position=sp.get('position', ''),
        hero_hand_type=hand_to_type(di.get('hero_cards') or []),
        stack_bb=float(sp.get('effectiveStackBb') or 20),
        action_taken=(di.get('player_action') or '').lower(),
        facing_size=float(sp.get('facingSize') or 0),
        vs_position=sp.get('villainPosition', ''),
        is_3bet_pot=bool(di.get('is_3bet')),
        n_players=sp.get('nPlayers'),
        facing_raises=int(sp.get('preflopRaisesFaced') or 0),
        hero_was_aggressor=bool(sp.get('heroWasAggressor')),
        facing_limp=bool(sp.get('facingLimp')),
    )
    return r.get('coverage_reason') == 'limped_pot'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Grava (default = dry-run)')
    args = ap.parse_args()

    c = get_conn()
    try:
        c.execute('PRAGMA busy_timeout = 15000')  # SQLite: espera o app.py liberar
    except Exception:
        pass

    tids = [dict(x)['id'] for x in c.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL").fetchall()]

    # (hand_id, action) das decisões de pote limpado
    limp_keys = set()
    for tid in tids:
        raw = c.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()[0]
        if not raw:
            continue
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for h in hands:
            try:
                dis = build_decision_inputs_for_hand(h)
            except Exception:
                continue
            for di in dis:
                if (di.get('street') or '').lower() != 'preflop':
                    continue
                if _is_limp(di):
                    limp_keys.add((str(h.hand_id), (di.get('player_action') or '').lower()))

    # decisões com gto_label armazenado nesses spots
    to_clear = []
    for hid, act in limp_keys:
        for row in c.execute(
                "SELECT id, gto_label FROM decisions "
                "WHERE hand_id=? AND lower(street)='preflop' AND lower(action_taken)=? "
                "AND gto_label IS NOT NULL AND gto_label != ''", (hid, act)).fetchall():
            to_clear.append(dict(row)['id'])

    print(f"potes limpados: {len(limp_keys)} | decisões com gto_label stale: {len(to_clear)}")
    if not to_clear:
        print("nada a limpar — idempotente OK")
        return

    if not args.apply:
        print("DRY-RUN (use --apply para gravar). IDs (até 20):", to_clear[:20])
        return

    ph = get_conn  # noop ref
    cur = c
    n = 0
    for did in to_clear:
        cur.execute("UPDATE decisions SET gto_label=NULL, gto_action=NULL WHERE id=?", (did,))
        n += 1
    c.commit()
    print(f"OK limpos {n} gto_label de potes limpados (gto_label/gto_action -> NULL)")


if __name__ == '__main__':
    main()
