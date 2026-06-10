"""
HUD Fase 1 — computa e persiste os perfis de comportamento de oponente de cada
torneio, e imprime um resumo pra validar a mecânica e as amostras.

Uso:
    python -m scripts.compute_opponent_profiles            # dry-run (só imprime)
    python -m scripts.compute_opponent_profiles --apply    # persiste em opponent_profiles
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from database.schema import get_conn
from database.repositories import upsert_opponent_profile
from leaklab.parser import parse_hand_history
from leaklab.opponent_stats import build_profiles

# Nomes que sugerem dados ANONIMIZADOS (posição como nome) — stats não-significativos.
_POS_LABELS = {'SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'MP', 'MP1', 'MP2'}


def _pct(x):
    return f"{round(x*100)}%" if isinstance(x, (int, float)) else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='persiste em opponent_profiles')
    args = ap.parse_args()

    conn = get_conn()
    rows = conn.execute("SELECT id, raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()
    conn.close()
    print(f"Torneios com raw_text: {len(rows)}")

    tot_players = tot_persisted = 0
    anonymized_tourneys = 0

    for r in rows:
        tid = r['id'] if hasattr(r, 'keys') else r[0]
        raw = r['raw_text'] if hasattr(r, 'keys') else r[1]
        try:
            hands = list(parse_hand_history(raw))
        except Exception as e:
            print(f"  [tid={tid}] erro parse: {e}")
            continue
        profiles = build_profiles(hands)
        # exclui o hero da contagem de "oponentes"
        hero = next((h.hero for h in hands if h.hero), None)
        opp = {p: s for p, s in profiles.items() if p != hero}

        # detecção de anonimização: maioria dos nomes são rótulos de posição
        names = set(opp.keys())
        anon = names and len(names & _POS_LABELS) >= max(1, int(len(names) * 0.6))
        if anon:
            anonymized_tourneys += 1

        # ranking por amostra
        ranked = sorted(opp.items(), key=lambda kv: -kv[1]['hands'])
        tot_players += len(ranked)
        print(f"\n=== torneio {tid} — {len(hands)} mãos, {len(ranked)} oponentes"
              f"{'  ⚠ ANONIMIZADO (posição como nome — stats não significativos)' if anon else ''} ===")
        for p, s in ranked[:8]:
            print(f"  {p:<10} mãos={s['hands']:<4} {s['archetype']:<15} conf={s['confidence']:<12}"
                  f" VPIP={_pct(s['vpip_pct'])} PFR={_pct(s['pfr_pct'])}"
                  f" cbet={_pct(s['cbet_pct'])} fcb={_pct(s['foldcbet_pct'])}"
                  f" AF={s['af'] if s['af'] is not None else '—'} WTSD={_pct(s['wtsd_pct'])}")
        # persiste TODOS os perfis do torneio (não só o top-8 impresso)
        if args.apply:
            for p, s in ranked:
                upsert_opponent_profile(tid, p, s)
                tot_persisted += 1

    print(f"\n{'='*60}")
    print(f"Total: {tot_players} perfis de oponente | persistidos: {tot_persisted}"
          f" | torneios anonimizados: {anonymized_tourneys}/{len(rows)}")
    if anonymized_tourneys:
        print("NOTA: torneios anonimizados (posição como nome) validam só a MECÂNICA do motor —"
              " a significância real exige dados com screen name estável (PokerStars / GG não-anônimo).")


if __name__ == '__main__':
    main()
