"""
sync_gto_labels_from_ranges.py — Preenche gto_label/gto_action para decisões
preflop sem veredicto de solver, usando a análise de ranges estáticos.

O solver (gto_nodes) tem prioridade absoluta; este script só atualiza
decisões que ainda não têm gto_label, preenchendo o gap com o range estático.

Uso:
    cd backend
    python scripts/sync_gto_labels_from_ranges.py          # dry-run (todas as decisões)
    python scripts/sync_gto_labels_from_ranges.py --save   # persiste no banco
    python scripts/sync_gto_labels_from_ranges.py --save --tid 145  # só um torneio

API pública:
    from scripts.sync_gto_labels_from_ranges import sync_tournament
    sync_tournament(tournament_id)  # chamado automaticamente após upload
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database.schema import get_conn
from database.repositories import reconcile_tournament_labels
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type


def parse_cards(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if " " in raw:
        return raw.split()
    return [raw[i:i+2] for i in range(0, len(raw), 2)] if len(raw) % 2 == 0 else []


def quality_to_label(quality: str) -> str:
    if quality in ("correct",):
        return "gto_correct"
    if quality in ("acceptable",):
        return "gto_mixed"
    if quality in ("gto_minor_deviation", "minor_mistake"):
        return "gto_minor_deviation"
    return "gto_critical"


def _detect_squeeze_context(row: dict, raw_text_by_tid: dict) -> tuple[str, str] | None:
    """Detecta se a decisão do hero é um SQUEEZE (raise sobre open + cold call).
    Parsea raw_text da hand pra identificar opener e cold caller positions.

    Retorna (opener_pos_8max, caller_pos_8max) se for squeeze, None caso contrário.
    """
    import re as _re
    raw = raw_text_by_tid.get(row.get('tournament_id'))
    if not raw or not row.get('hand_id') or not row.get('hero_name'):
        return None
    idx = raw.find(row['hand_id'])
    if idx < 0:
        return None
    end = raw.find('PokerStars Hand', idx + 50)
    block = raw[idx:end if end > 0 else idx + 5000]
    s = block.find('*** HOLE CARDS ***')
    if s < 0:
        return None
    e_flop = block.find('*** FLOP ***', s)
    e_sum  = block.find('*** SUMMARY ***', s)
    e = e_flop if e_flop > 0 else e_sum
    if e < 0:
        return None
    preflop = block[s:e]

    # Mapear seats → posições do PokerStars
    # Encontrar button seat
    m_btn = _re.search(r'Seat #(\d+) is the button', block)
    if not m_btn:
        return None
    btn_seat = int(m_btn.group(1))

    # Restringe parsing de seats ao HEADER (antes de '*** HOLE CARDS ***') para evitar
    # match no SUMMARY que duplica entradas e capta nomes com sufixos como 'showed [...]'
    header_end = block.find('*** HOLE CARDS ***')
    header_block = block[:header_end] if header_end > 0 else block
    seats_present = []
    seen_seats = set()
    for m in _re.finditer(r'Seat (\d+): ([^\(\n]+?) \(', header_block):
        seat_num = int(m.group(1))
        if seat_num in seen_seats:
            continue
        seen_seats.add(seat_num)
        seats_present.append((seat_num, m.group(2).strip()))
    if len(seats_present) < 3:
        return None

    # Ordem de ação preflop: começa do seat após BB (3 seats após BTN), no sentido horário
    # Em PokerStars 9-max: BTN, SB(BTN+1), BB(BTN+2), UTG(BTN+3), UTG+1(BTN+4), ...
    # Em 8-max ou menos, a numeração é a mesma — só pula seats vazios
    ordered_seats = sorted(seats_present, key=lambda x: x[0])
    seat_to_player = dict(ordered_seats)
    n_seats_max = max(s for s, _ in ordered_seats) + 1 if ordered_seats else 0

    # Determinar ordem de ação: começa após BB. Em N-max table, BB é o 2º seat após BTN.
    # Para 9-max: SB=BTN+1, BB=BTN+2, UTG=BTN+3, ..., last=BTN
    n_active = len(ordered_seats)
    # Construir lista circular de seats ocupados em ordem horária
    sorted_occupied = [s for s, _ in ordered_seats]
    btn_idx_in_list = next((i for i, s in enumerate(sorted_occupied) if s == btn_seat), None)
    if btn_idx_in_list is None:
        return None
    # Reorganizar ciclicamente a partir do button
    btn_first = sorted_occupied[btn_idx_in_list:] + sorted_occupied[:btn_idx_in_list]
    # btn_first[0] = BTN, btn_first[1] = SB, btn_first[2] = BB, btn_first[3] = UTG, etc.
    if len(btn_first) < 3:
        return None
    # Mapear seat → position name (8-max canonical: UTG, UTG+1, LJ, HJ, CO, BTN, SB, BB)
    # Para tables maiores, mantém o nome direto do PokerStars (UTG+2, UTG+3) se necessário
    POS_NAMES_BY_NPLAYERS = {
        2: ['BTN', 'BB'],
        3: ['BTN', 'SB', 'BB'],
        4: ['BTN', 'SB', 'BB', 'CO'],
        5: ['BTN', 'SB', 'BB', 'UTG', 'CO'],
        6: ['BTN', 'SB', 'BB', 'UTG', 'HJ', 'CO'],
        7: ['BTN', 'SB', 'BB', 'UTG', 'LJ', 'HJ', 'CO'],
        8: ['BTN', 'SB', 'BB', 'UTG', 'UTG+1', 'LJ', 'HJ', 'CO'],
        9: ['BTN', 'SB', 'BB', 'UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'MP'],  # MP entre UTG+1 e LJ varia
    }
    n = len(btn_first)
    if n not in POS_NAMES_BY_NPLAYERS:
        return None
    # Mapeamento: btn_first[i] → POS_NAMES_BY_NPLAYERS[n][i]
    # Atenção: para 8-max o padrão é BTN, SB, BB, UTG, UTG+1, LJ, HJ, CO (acim a do button)
    # Mas a ordem de ação preflop começa em UTG (índice 3) → BTN (índice 0) → SB (índice 1)
    # Vou usar mapeamento 8-max canônico independente do número real, para alinhar com GW
    POS_8MAX = {
        'BTN': 'BTN', 'SB': 'SB', 'BB': 'BB',
        'UTG': 'UTG', 'UTG+1': 'UTG+1', 'LJ': 'LJ', 'HJ': 'HJ', 'CO': 'CO', 'MP': 'LJ',
    }
    pos_names = POS_NAMES_BY_NPLAYERS.get(n, [])
    seat_to_pos = {s: POS_8MAX.get(p, p) for s, p in zip(btn_first, pos_names)}

    # Construir ordem de ação preflop (UTG primeiro, depois clockwise até BB)
    # Em N-handed: action_order = btn_first[3:] + btn_first[:3]
    if n < 4:
        # 3-handed: ação preflop é BTN -> SB -> BB. Não dá squeeze 3-handed (precisa 4+ p/ ter caller entre open e hero)
        return None
    action_order = btn_first[3:] + [btn_first[0], btn_first[1], btn_first[2]]
    action_order_pos = [seat_to_pos[s] for s in action_order]

    # Identificar ações dos villains antes do hero
    hero_name = row['hero_name']
    actions = []  # lista de (player_name, action_name, size_to)
    for line in preflop.splitlines():
        m = _re.match(r'^([^:\n]+?):\s+(folds|calls|raises|checks|bets)\s*(.*)$', line.strip())
        if not m:
            continue
        player, act, rest = m.group(1).strip(), m.group(2), m.group(3)
        if player == hero_name:
            break
        actions.append((player, act))

    # Achar opener e caller (em ordem)
    opener = None
    caller = None
    for player, act in actions:
        if act == 'raises' and opener is None:
            opener = player
        elif act == 'calls' and opener is not None and caller is None:
            caller = player
        elif act == 'raises' and opener is not None:
            # 3-bet de outro villain antes do hero → não é squeeze do hero (hero seria cold4bet)
            return None
    if opener is None or caller is None:
        return None

    # Mapear nomes → posições
    name_to_seat = {p: s for s, p in seat_to_player.items()}
    op_seat = name_to_seat.get(opener)
    cl_seat = name_to_seat.get(caller)
    if op_seat is None or cl_seat is None:
        return None
    op_pos = seat_to_pos.get(op_seat)
    cl_pos = seat_to_pos.get(cl_seat)
    if not op_pos or not cl_pos:
        return None
    return (op_pos, cl_pos)


def _build_vs3bet_context(rows: list[dict], conn) -> set[int]:
    """Identifica decisions que sao vs_3bet por contexto: hero ja deu raise
    antes na mesma hand_id, mesma street=preflop, e agora enfrenta facing_bet>0.

    O campo decisions.is_3bet vindo do pipeline so e True quando hero da 3-bet
    (action=raise), nao quando hero FOLDA/CALLA ao 3-bet. Por isso recomputamos.

    Retorna o set de decision ids que devem ser tratados como is_3bet_pot=True.
    """
    hand_ids = {r["hand_id"] for r in rows if r.get("hand_id") and r.get("street") == "preflop"}
    if not hand_ids:
        return set()
    # Para cada hand, busca todas as decisions preflop com seus ids/actions
    placeholders = ",".join("?" * len(hand_ids))
    raised_by_hand: dict[str, list[int]] = {}
    for hid, did, act in conn.execute(
        f"SELECT hand_id, id, action_taken FROM decisions "
        f"WHERE hand_id IN ({placeholders}) AND street='preflop' ORDER BY id ASC",
        list(hand_ids),
    ).fetchall():
        if (act or "").lower() in ("raise", "jam", "shove", "allin"):
            raised_by_hand.setdefault(hid, []).append(did)

    is_vs3bet: set[int] = set()
    for r in rows:
        if r.get("street") != "preflop":
            continue
        try:
            facing = float(r.get("facing_bet") or 0)
        except Exception:
            facing = 0.0
        if facing <= 0:
            continue
        prior_raises = raised_by_hand.get(r["hand_id"], [])
        if any(prev_id < r["id"] for prev_id in prior_raises):
            is_vs3bet.add(r["id"])
    return is_vs3bet


def _process_rows(rows: list[dict], conn, dry_run: bool = True, verbose: bool = True) -> int:
    """Process a list of decision rows, filling gto_label where missing. Returns count updated."""
    updates: list[tuple] = []
    skipped = 0
    vs3bet_ids = _build_vs3bet_context(rows, conn)

    # Cache de raw_text + hero por tournament_id (para detector squeeze)
    tids = {r.get('tournament_id') for r in rows if r.get('tournament_id')}
    raw_by_tid: dict[int, str] = {}
    hero_by_tid: dict[int, str] = {}
    if tids:
        ph = ",".join("?" * len(tids))
        for tid, hero, raw in conn.execute(
            f"SELECT id, hero, raw_text FROM tournaments WHERE id IN ({ph})",
            list(tids),
        ).fetchall():
            raw_by_tid[tid] = raw or ""
            hero_by_tid[tid] = hero or ""

    for r in rows:
        cards = parse_cards(r["hero_cards"])
        if len(cards) < 2:
            skipped += 1
            continue

        try:
            hand_type = hand_to_type(cards)
        except Exception:
            skipped += 1
            continue

        stack_bb  = float(r["stack_bb"] or 20)
        facing_bb = float(r["facing_bet"] or 0)
        pos       = r["position"] or ""
        vs_pos    = r["vs_position"] or ""
        # is_3bet_pot semantico: hero ja deu raise antes nesta hand
        # (corrige bug do pipeline que so marca True quando hero da 3-bet)
        is_3bet   = bool(r["is_3bet"]) or (r["id"] in vs3bet_ids)
        action    = (r["action_taken"] or "").lower()

        # BB free play: no facing bet, BB checks — always correct
        if pos.upper() == "BB" and facing_bb == 0 and action == "check":
            updates.append(("gto_correct", "check", r["id"]))
            continue

        # Squeeze detection: se hero é 3-bet pot, tenta detectar squeeze para passar caller_position
        caller_pos = ""
        squeeze_op_pos = ""
        if is_3bet and action in ("raise", "jam", "shove"):
            tid = r.get('tournament_id')
            row_for_detect = {
                'tournament_id': tid,
                'hand_id': r.get('hand_id'),
                'hero_name': hero_by_tid.get(tid, ''),
            }
            sq = _detect_squeeze_context(row_for_detect, raw_by_tid)
            if sq:
                squeeze_op_pos, caller_pos = sq

        try:
            result = analyze_preflop(
                position=pos,
                hero_hand_type=hand_type,
                stack_bb=stack_bb,
                action_taken=action,
                facing_size=facing_bb,
                vs_position=squeeze_op_pos or vs_pos,
                is_3bet_pot=is_3bet,
                caller_position=caller_pos,
            )
        except Exception:
            skipped += 1
            continue

        if not result.get("available"):
            skipped += 1
            continue

        quality    = result.get("action_quality", "")
        rec_acts   = result.get("recommended_actions") or []
        new_label  = quality_to_label(quality)
        new_action = rec_acts[0] if rec_acts else (r["best_action"] or "")

        updates.append((new_label, new_action, r["id"]))
        if verbose and new_label != "gto_correct":
            print(f"  id={r['id']:>7}  {pos:<6} {stack_bb:>6.1f}bb  "
                  f"hand={hand_type:<4}  played={action:<6}  "
                  f"quality={quality:<24}  label={new_label}")

    if verbose:
        print(f"\nCom range disponivel: {len(updates)}  |  Sem range (skipped): {skipped}")

    if not updates or dry_run:
        return 0

    for new_label, new_action, dec_id in updates:
        conn.execute(
            "UPDATE decisions SET gto_label=?, gto_action=? WHERE id=?",
            (new_label, new_action, dec_id)
        )
    conn.commit()
    return len(updates)


def sync_tournament(tournament_id: int) -> int:
    """
    Preenche gto_label/gto_action para decisões preflop sem veredicto no torneio indicado.
    Chamado automaticamente após cada upload como background thread.
    Retorna o número de decisões atualizadas.
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, hand_id, tournament_id, street, position, stack_bb, facing_bet, is_3bet,
                   action_taken, best_action, hero_cards, vs_position
            FROM decisions
            WHERE tournament_id = ?
              AND street = 'preflop'
              AND (gto_label IS NULL OR gto_label = '')
              AND hero_cards IS NOT NULL AND hero_cards != ''
        """, (tournament_id,)).fetchall()
        rows = [dict(r) for r in rows]

        if not rows:
            return 0

        n = _process_rows(rows, conn, dry_run=False, verbose=False)
        if n:
            reconcile_tournament_labels(tournament_id)
        return n
    except Exception:
        return 0
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--tid", type=int, default=None, help="Processar apenas este tournament_id")
    args = parser.parse_args()

    conn = get_conn()

    where = "WHERE street = 'preflop' AND (gto_label IS NULL OR gto_label = '') AND hero_cards IS NOT NULL AND hero_cards != ''"
    params: list = []
    if args.tid:
        where += " AND tournament_id = ?"
        params.append(args.tid)

    rows = conn.execute(
        f"SELECT id, hand_id, tournament_id, street, position, stack_bb, facing_bet, is_3bet, "
        f"action_taken, best_action, hero_cards, vs_position FROM decisions {where}",
        params
    ).fetchall()
    rows = [dict(r) for r in rows]
    print(f"Preflop sem gto_label: {len(rows)}")

    n = _process_rows(rows, conn, dry_run=not args.save, verbose=True)

    if not args.save:
        print("\n[DRY RUN] Use --save para persistir.")
        conn.close()
        return

    conn.close()
    if n:
        print(f"\n{n} decisoes preflop atualizadas com veredicto de range estatico.")
        # Reconciliar labels para torneios afetados
        conn2 = get_conn()
        tids = set(r['tournament_id'] for r in conn2.execute(
            "SELECT DISTINCT tournament_id FROM decisions WHERE street='preflop' AND gto_label IS NOT NULL"
        ).fetchall())
        conn2.close()
        for tid in tids:
            r2 = reconcile_tournament_labels(tid)
            if r2:
                print(f"  Torneio {tid}: {r2} labels reconciliados.")
        if tids:
            print(f"standard_pct recalculado para {len(tids)} torneios.")
    else:
        print("\nNenhuma atualizacao necessaria.")


if __name__ == "__main__":
    main()
