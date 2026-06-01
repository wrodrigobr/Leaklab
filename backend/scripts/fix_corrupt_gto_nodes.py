"""
fix_corrupt_gto_nodes.py -- Conserta os gto_nodes com hero_hand CORROMPIDO
(char-split ['4','A','d','d'] em vez de ['4d','Ad'], do bug de ingestão do
solver_cli) e RE-HASHEIA com o hand correto para o lookup voltar a achá-los.

Como recupera o facing (não armazenado): o spot_hash antigo foi computado com o
hand char-split + algum bet_bucket. Como há só 6 bet_buckets, faz brute-force —
recomputa o hash antigo (char-split) p/ cada bucket e casa com o spot_hash
armazenado → recupera o bucket → re-hasheia com o hand correto.

  - recuperável + novo hash livre → UPDATE (hero_hand corrigido + spot_hash novo)
  - novo hash colide com node existente → DELETE (é duplicata de um node correto)
  - não recuperável (nenhum bucket casa) → DELETE (malformado e inalcançável)

Uso:
    python scripts/fix_corrupt_gto_nodes.py            # dry-run
    python scripts/fix_corrupt_gto_nodes.py --apply
"""
import sys, os, argparse, json, hashlib, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db
from leaklab.gto_utils import normalize_cards

_BUCKETS = ["no_bet", "0-3bb", "3-8bb", "8-20bb", "20-40bb", "40bb+"]
_VALID = re.compile(r"^[2-9TJQKA][cdhs]$")


def _is_corrupt(hero_hand_json) -> bool:
    try:
        h = json.loads(hero_hand_json)
    except Exception:
        return True
    if h == []:
        return False
    return not (len(h) == 2 and all(_VALID.match(str(x)) for x in h))


def _hash(street, position, board, hand_list, stack_bucket_val, bet_b) -> str:
    canonical = {
        "street": (street or "").lower(), "position": (position or "").upper(),
        "board": sorted(board), "hand": sorted(hand_list),
        "stack_bucket": stack_bucket_val, "bet_bucket": bet_b,
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    init_db()
    conn = get_conn()
    try:
        conn.execute("PRAGMA busy_timeout=8000")
    except Exception:
        pass

    all_hashes = set(x[0] for x in conn.execute("SELECT spot_hash FROM gto_nodes").fetchall())
    nodes = [dict(r) for r in conn.execute(
        "SELECT id, spot_hash, street, position, board, hero_hand, stack_bucket FROM gto_nodes").fetchall()]
    corrupt = [n for n in nodes if _is_corrupt(n["hero_hand"])]
    print(f"gto_nodes total: {len(nodes)} | corrompidos: {len(corrupt)}")

    recovered = deleted_dup = deleted_unrec = 0
    examples = []
    for n in corrupt:
        try:
            board = json.loads(n["board"] or "[]")
            corrupt_hand = json.loads(n["hero_hand"])
        except Exception:
            corrupt_hand = []
            board = []
        corrected = normalize_cards(corrupt_hand)
        sb = n["stack_bucket"]
        # brute-force do bet_bucket que reproduz o spot_hash antigo (char-split)
        rec_bucket = None
        for b in _BUCKETS:
            if _hash(n["street"], n["position"], board, corrupt_hand, sb, b) == n["spot_hash"]:
                rec_bucket = b
                break
        if rec_bucket is None:
            deleted_unrec += 1
            if args.apply:
                conn.execute("DELETE FROM gto_nodes WHERE id=?", (n["id"],))
            continue
        new_hash = _hash(n["street"], n["position"], board, corrected, sb, rec_bucket)
        if new_hash != n["spot_hash"] and new_hash in all_hashes:
            deleted_dup += 1
            if args.apply:
                conn.execute("DELETE FROM gto_nodes WHERE id=?", (n["id"],))
            continue
        recovered += 1
        all_hashes.discard(n["spot_hash"]); all_hashes.add(new_hash)
        if len(examples) < 15:
            examples.append(f"  id{n['id']} {n['street']}/{n['position']} bucket={rec_bucket} | "
                            f"{corrupt_hand}->{corrected} | hash {n['spot_hash']}->{new_hash}")
        if args.apply:
            conn.execute("UPDATE gto_nodes SET hero_hand=?, spot_hash=? WHERE id=?",
                         (json.dumps(sorted(corrected)), new_hash, n["id"]))

    if args.apply:
        conn.commit()
    conn.close()
    print(f"\nRecuperados (re-hash): {recovered} | deletados dup: {deleted_dup} | "
          f"deletados não-recuperáveis: {deleted_unrec}")
    if examples:
        print("Exemplos:\n" + "\n".join(examples))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == "__main__":
    main()
