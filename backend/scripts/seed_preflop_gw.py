"""
seed_preflop_gw.py — Enumera e busca a árvore preflop do GTO Wizard via API
(gto_wizard_client.query_spot_raw), CAMINHANDO a árvore com os `code`s reais
que o GW devolve em cada nó (nunca chuta sizing).

Por que tree-walk: o GW só resolve spots com sizings discretos válidos (ex.: open
= R2, não R2.5). A cada nó, `action_solutions` traz os codes válidos (F, C, R2,
R6.5, RAI). Descemos anexando esses codes exatos → preflop_actions sempre válido.

Cada nó fetchado = a range (169 mãos) do jogador a agir ali. Gravamos TODOS os
nós alcançáveis (RFI, vs_RFI, vs_3bet, squeeze, faces_squeeze, 4bet…), podados
por frequência (ignora linhas ~0%) e por nº máximo de raises (evita 5bet wars).

Checkpoint: grava 1 JSON por nó em docs/gw_preflop_seed/<bucket>.jsonl (append).
Resume-safe: pula preflop_actions já presentes no arquivo. Fetcher com RETRIES
(timeouts do GW são intermitentes). A conversão pro formato do master + merge é
passo separado (estruturação local, rápida) — fetch é o caro/flaky.

Uso:
    python scripts/seed_preflop_gw.py --test                 # 1 stack (20bb), raso
    python scripts/seed_preflop_gw.py --stacks 20,30,50      # stacks específicos
    python scripts/seed_preflop_gw.py                        # todos os 9 buckets
    python scripts/seed_preflop_gw.py --max-raises 3 --min-freq 0.005
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
except Exception:
    pass
os.environ.setdefault("GTO_WIZARD_ENABLED", "true")

from leaklab import gto_wizard_client as gw  # noqa: E402

SEED_DIR = BACKEND / "docs" / "gw_preflop_seed"
NUM_PLAYERS = 9
DEGRADED_GAPS = 15   # rajada de gaps consecutivos = servidor degradou → para limpo
DEFAULT_STACKS = [10, 14, 17, 20, 30, 40, 50, 75, 100]  # mesmos buckets do master


def _bucket(depth_bb: int) -> str:
    return f"{depth_bb}bb"


def _classify_code(code: str) -> str:
    """Classe da ação pelo code cru do GW."""
    if not code:
        return "OTHER"
    if code == "F":
        return "FOLD"
    if code in ("C", "X"):  # call / check
        return "CALL"
    if code == "RAI":
        return "ALLIN"
    if code[0] in ("R", "B"):  # R2, R6.5, B... (raise/bet)
        return "RAISE"
    return "OTHER"


def _actions(resp: dict) -> list[tuple[str, str, float]]:
    """[(classe, code, freq)] — lê do `strategy` normalizado do cliente
    (query_spot_raw NÃO devolve action_solutions; devolve strategy)."""
    out = []
    for s in (resp.get("strategy") or []):
        code = s.get("code")
        out.append((_classify_code(code), code, float(s.get("frequency") or 0.0)))
    return out


def fetch_node(pf: str, depth_bb: int, retries: int = 2) -> dict | None:
    """query_spot_raw com poucos retries — com o subprocesso isolado, timeout é
    raro; a maioria dos gaps é no-solution genuíno (não adianta insistir muito)."""
    for attempt in range(retries):
        try:
            r = gw.query_spot_raw(
                preflop_actions=pf, num_players=NUM_PLAYERS, depth_bb=depth_bb,
                include_strategy=True, timeout=60, use_cache=True,
            )
        except Exception:
            r = None
        if r and r.get("found") and (r.get("hand_freqs") or r.get("hero_hand_freqs")):
            return r
        time.sleep(1.0)
    return None


def _node_record(pf: str, depth_bb: int, resp: dict) -> dict:
    return {
        "pf":            pf,
        "depth_bb":      depth_bb,
        "hero_position": resp.get("hero_position"),
        "spot":          resp.get("spot"),
        # hand_freqs já normalizado (fold/call/raise/allin) pelo cliente
        "hand_freqs":    resp.get("hand_freqs") or {},
        "raw_hand_freqs": resp.get("raw_hand_freqs") or {},
        "actions":       [{"type": t, "code": c, "freq": round(f, 4)}
                          for (t, c, f) in _actions(resp)],
    }


def _count_aggr(pf: str) -> int:
    """Nº de agressões (raise/all-in) já no preflop_actions."""
    if not pf:
        return 0
    return sum(1 for tok in pf.split("-") if tok and (tok == "RAI" or tok[0] in ("R", "B")))


def walk(depth_bb: int, max_raises: int, min_freq: float,
         done: dict, fh, stats: dict, limit: int = 0, max_calls: int = 2) -> None:
    """BFS na árvore preflop (FIFO → nós rasos/comuns primeiro). Começa no RFI
    (UTG, pf vazio) e desce pelas ações que continuam a mão, com os codes exatos
    do GW. `done` = cache pf→registro (resume: nós já buscados expandem instantâneo,
    só nós novos vão ao GW)."""
    from collections import deque
    expanded: set = set()
    queue = deque([""])
    while queue:
        if limit and stats["nodes"] >= limit:
            print(f"    limite de {limit} nós novos atingido — parando."); break
        pf = queue.popleft()
        if pf in expanded:
            continue
        expanded.add(pf)

        rec = done.get(pf)
        if rec is None:                      # nó novo → busca no GW
            resp = fetch_node(pf, depth_bb)
            if not resp:
                stats["failed"] += 1
                stats["consec_gaps"] = stats.get("consec_gaps", 0) + 1
                fh_log(stats, f"  [gap] depth={depth_bb} pf={pf!r}")
                # Detecção de degradação do servidor: gaps de no-solution genuíno
                # são esparsos (intercalados com sucessos); uma RAJADA longa de gaps
                # consecutivos = servidor degradou (precisa restart). Para limpo.
                if stats["consec_gaps"] >= DEGRADED_GAPS:
                    print(f"\n⚠️  DEGRADAÇÃO: {DEGRADED_GAPS} gaps consecutivos — servidor "
                          f"precisa de restart (sudo systemctl restart leaklab-solver). "
                          f"Parando (resume-safe).", flush=True)
                    stats["degraded"] = True
                    break
                continue
            rec = _node_record(pf, depth_bb, resp)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            done[pf] = rec
            stats["nodes"] += 1
            stats["consec_gaps"] = 0
            if stats["nodes"] % 25 == 0:
                print(f"    {depth_bb}bb: +{stats['nodes']} nós | fila={len(queue)} | gaps={stats['failed']}", flush=True)

        # Expande filhos a partir do registro (vale pra cache E pra fetch novo).
        toks = pf.split("-") if pf else []
        nr = _count_aggr(pf)
        nc = sum(1 for t in toks if t == "C")     # callers já na linha
        has_allin = "RAI" in toks
        for a in rec.get("actions", []):
            code = a.get("code"); typ = a.get("type"); freq = a.get("freq", 0.0)
            if not code or freq < min_freq:
                continue
            is_aggr = typ in ("RAISE", "ALLIN")
            if is_aggr and nr + 1 > max_raises:
                continue                      # corta 5bet+ wars
            if typ == "CALL":
                # Poda multiway: o GW MTTGeneralV2 não resolve potes multiway
                # profundos. Limita callers e não expande call DE all-in (vira
                # side-pot multiway = dead-end). Não perde os spots úteis
                # (squeeze/3bet com 1 caller); só corta os becos sem solução.
                if nc + 1 > max_calls:
                    continue
                if has_allin:
                    continue
            child = f"{pf}-{code}" if pf else code
            if child not in expanded:
                queue.append(child)


def fh_log(stats, msg):
    stats.setdefault("log", []).append(msg)
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="só 20bb, max-raises=2 (validação)")
    ap.add_argument("--stacks", default="", help="lista ex: 20,30,50 (default: todos)")
    ap.add_argument("--max-raises", type=int, default=4)
    ap.add_argument("--max-calls", type=int, default=2, help="cap de callers na linha (poda multiway)")
    ap.add_argument("--min-freq", type=float, default=0.005)
    ap.add_argument("--limit", type=int, default=0, help="cap de nós por stack (0=sem limite)")
    args = ap.parse_args()

    SEED_DIR.mkdir(parents=True, exist_ok=True)

    st = gw.get_status()
    print("GW status:", st)
    if not st.get("enabled"):
        print("ABORT: GTO_WIZARD_ENABLED off ou servidor inacessível."); return

    if args.test:
        stacks = [20]; max_raises = 2
    else:
        max_raises = args.max_raises
        stacks = ([int(x) for x in args.stacks.split(",") if x.strip()]
                  if args.stacks else DEFAULT_STACKS)

    print(f"Stacks: {stacks} | max_raises={max_raises} | min_freq={args.min_freq}")
    grand = {"nodes": 0, "failed": 0}
    for depth_bb in stacks:
        out_path = SEED_DIR / f"{_bucket(depth_bb)}.jsonl"
        # resume: carrega registros já gravados (pf -> record) como cache
        done: dict = {}
        if out_path.exists():
            with open(out_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        done[rec["pf"]] = rec
                    except Exception:
                        continue
        print(f"\n== {depth_bb}bb == (resume: {len(done)} nós já no cache)")
        stats = {"nodes": 0, "failed": 0}
        with open(out_path, "a", encoding="utf-8") as fh:
            walk(depth_bb, max_raises, args.min_freq, done, fh, stats,
                 limit=args.limit, max_calls=args.max_calls)
        print(f"  {depth_bb}bb done: +{stats['nodes']} nós novos, {stats['failed']} gaps "
              f"(total no arquivo: {len(done)})")
        grand["nodes"] += stats["nodes"]; grand["failed"] += stats["failed"]
        if stats.get("degraded"):
            grand["degraded"] = True
            print("\n>>> SEED PAUSADO por degradação do servidor. Reinicie o serviço no "
                  "GCP e re-rode o MESMO comando (resume continua de onde parou).")
            break

    tag = " (PAUSADO — degradação)" if grand.get("degraded") else ""
    print(f"\nTOTAL: {grand['nodes']} nós novos | {grand['failed']} gaps{tag}")
    print(f"Checkpoints em {SEED_DIR}/*.jsonl")
    print("Próximo: converter os JSONL pro formato do master + merge + sync.")


if __name__ == "__main__":
    main()
