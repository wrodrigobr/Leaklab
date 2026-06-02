"""
backfill_hero_won_hand.py — Preenche decisions.hero_won_hand para os torneios já
analisados (insight results×GTO #5: 'ganhei mas joguei errado'). hero_won = hero
COLETOU o pote na mão (com ou sem showdown). É per-mão: todas as decisões da mão
recebem o mesmo valor.

Uso: python scripts/backfill_hero_won_hand.py
"""
import sys, re
sys.path.insert(0, ".")
from database.schema import get_conn, init_db
from leaklab.parser import parse_hand_history


def _won(raw: str, hero: str):
    if not hero or not raw:
        return None
    return 1 if re.search(r"\b" + re.escape(hero) + r"\s+collected\b", raw) else 0


def main():
    init_db()  # aplica a migration hero_won_hand (idempotente)
    conn = get_conn()
    try:
        conn.execute("PRAGMA busy_timeout=10000")
    except Exception:
        pass
    tids = [dict(x)["id"] for x in conn.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL").fetchall()]
    updated = won = lost = none = 0
    for tid in tids:
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()[0]
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for h in hands:
            w = _won(h.raw_text or "", h.hero or "")
            n = conn.execute(
                "UPDATE decisions SET hero_won_hand=? WHERE tournament_id=? AND hand_id=?",
                (w, tid, h.hand_id)).rowcount
            updated += n
            if w == 1:   won += n
            elif w == 0: lost += n
            else:        none += n
    conn.commit()
    conn.close()
    print(f"backfill: {updated} decisões atualizadas | won={won} lost/fold={lost} indeterminado={none}")


if __name__ == "__main__":
    main()
