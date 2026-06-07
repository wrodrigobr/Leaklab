"""Reprocessa torneios construídos no Hand Builder. Dois fixes nas mãos do builder:
  (1) NOMES dos jogadores no raw_text → POSIÇÃO real da mão (hero → "Hero"), derivada
      de assento+button. Corrige rótulos stale (ex.: "UTG+1" no assento que é BTN).
  (2) 'calls X' → incremento correto (o gerador antigo gravava o TOTAL; ex.: open 200
      + 'calls 857' somava 1057 em vez de igualar a 857 → vira 'calls 657').
Ambos recalculam da estrutura → idempotentes. Mesma lógica do engine/`/replay`.

SÓ toca mãos claramente do builder (todos os nomes em {posições} ∪ {P1..P9, Hero}) —
uploads reais (nicks de gente) são ignorados. As DECISÕES não mudam (já guardam a
posição certa); só o raw_text (que o Replayer re-parseia) e o campo `hero`.

Uso:
    python -m scripts.fix_builder_tournament_names                 # dry-run, todos
    python -m scripts.fix_builder_tournament_names --tournament 999999
    python -m scripts.fix_builder_tournament_names --apply         # grava
"""
import sys, os, re, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from database.schema import get_conn

_POS = {'SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'MP1', 'MP2', 'MP3', 'LJ', 'HJ', 'CO', 'BTN'}
_BUILDER_NAMES = _POS | {f'P{i}' for i in range(1, 11)} | {'Hero'}

_SEAT_RE = re.compile(r'^Seat (\d+): (.+?) \((\d+) in chips', re.M)
_BTN_RE  = re.compile(r'Seat #(\d+) is the button')
_HERO_RE = re.compile(r'Dealt to (.+?) \[')


def _positions_for(seat_nums, button):
    """Posição por assento — clockwise a partir do SB (assento depois do button)."""
    n = len(seat_nums)
    btn_idx = seat_nums.index(button) if button in seat_nums else 0
    ordered = [seat_nums[(btn_idx + 1 + k) % n] for k in range(n)]  # [SB, BB, ..., BTN]
    pn = {0: 'SB', 1: 'BB', n - 1: 'BTN'}
    if n >= 4: pn[n - 2] = 'CO'
    if n >= 6: pn[n - 3] = 'HJ'
    seq = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'MP2', 'MP3']
    si = 0
    for k in range(2, n):
        if k not in pn:
            pn[k] = seq[si] if si < len(seq) else f'P{k}'
            si += 1
    return {ordered[k]: pn[k] for k in range(n)}


def remap_hand(hand_text):
    """Devolve (novo_texto, changed, is_builder). Não muda se não for builder ou já limpo."""
    seats = {int(m.group(1)): m.group(2) for m in _SEAT_RE.finditer(hand_text)}
    if len(seats) < 2:
        return hand_text, False, False
    if not all(nm in _BUILDER_NAMES for nm in seats.values()):
        return hand_text, False, False   # upload real — ignora
    btn_m = _BTN_RE.search(hand_text)
    if not btn_m:
        return hand_text, False, True
    button = int(btn_m.group(1))
    hero_m = _HERO_RE.search(hand_text)
    hero_name = hero_m.group(1) if hero_m else None

    seat_pos = _positions_for(sorted(seats.keys()), button)
    name_map = {}  # old -> new (por assento)
    for s, old in seats.items():
        name_map[old] = 'Hero' if old == hero_name else seat_pos[s]

    if all(old == new for old, new in name_map.items()):
        return hand_text, False, True   # já está limpo

    # Substituição com placeholders (evita colisão old→new quando new = outro old).
    text = hand_text
    items = list(name_map.items())
    for i, (old, _new) in enumerate(items):
        text = re.sub(r'(?<![A-Za-z0-9+])' + re.escape(old) + r'(?![A-Za-z0-9+])',
                      f'\x00{i}\x00', text)
    for i, (_old, new) in enumerate(items):
        text = text.replace(f'\x00{i}\x00', new)
    return text, True, True


_CALL_RE  = re.compile(r'^(.+?): calls (\d+)')
_RAISE_RE = re.compile(r'^(.+?): raises \d+ to (\d+)')
_BET_RE   = re.compile(r'^(.+?): bets (\d+)')
_BLIND_RE = re.compile(r'^(.+?): posts (?:small|big) blind (\d+)')


def fix_call_increments(hand_text):
    """Corrige 'calls X' onde X era o TOTAL (bug do gerador) — deveria ser o INCREMENTO
    (o que falta pra igualar a aposta). Recalcula da ESTRUTURA das apostas (não do X
    atual), então é idempotente: mãos já corretas (X = incremento) não mudam."""
    committed, max_bet, changed, out = {}, 0, False, []
    for line in hand_text.split('\n'):
        if line.startswith('*** ') and ('FLOP' in line or 'TURN' in line or 'RIVER' in line):
            committed, max_bet = {}, 0
            out.append(line); continue
        mb = _BLIND_RE.match(line)
        mr = _RAISE_RE.match(line)
        mt = _BET_RE.match(line)
        mc = _CALL_RE.match(line)
        if mb:
            p, amt = mb.group(1), int(mb.group(2))
            committed[p] = committed.get(p, 0) + amt
            max_bet = max(max_bet, committed[p])
        elif mr:
            p, to = mr.group(1), int(mr.group(2))
            committed[p] = to; max_bet = max(max_bet, to)
        elif mt and not mc:
            p, amt = mt.group(1), int(mt.group(2))
            committed[p] = amt; max_bet = max(max_bet, amt)
        elif mc:
            p, y = mc.group(1), int(mc.group(2))
            correct = max(0, max_bet - committed.get(p, 0))
            committed[p] = max_bet
            if correct != y:
                line = f'{p}: calls {correct}' + line[mc.end():]
                changed = True
        out.append(line)
    return '\n'.join(out), changed


def process_raw(raw):
    """Remapeia nomes + corrige call increments das mãos builder. Devolve
    (novo_raw, n_changed, n_builder, n_total)."""
    parts = re.split(r'(?=PokerStars Hand #)', raw)
    out, n_changed, n_builder, n_total = [], 0, 0, 0
    for p in parts:
        if not p.strip() or not p.startswith('PokerStars Hand #'):
            out.append(p); continue
        n_total += 1
        new, changed_n, is_builder = remap_hand(p)
        if is_builder:
            n_builder += 1
            new, changed_c = fix_call_increments(new)
            if changed_n or changed_c: n_changed += 1
        out.append(new)
    return ''.join(out), n_changed, n_builder, n_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tournament', help='tournament_id específico (senão: todos)')
    ap.add_argument('--user', type=int, help='user_id específico')
    ap.add_argument('--apply', action='store_true', help='grava (senão dry-run)')
    args = ap.parse_args()

    conn = get_conn()
    q = "SELECT id, user_id, tournament_id, hero, raw_text FROM tournaments WHERE raw_text IS NOT NULL"
    cond, params = [], []
    if args.tournament: cond.append("tournament_id = ?"); params.append(args.tournament)
    if args.user:       cond.append("user_id = ?");       params.append(args.user)
    if cond: q += " AND " + " AND ".join(cond)
    rows = conn.execute(q, params).fetchall()

    print(f"{'APLICANDO' if args.apply else 'DRY-RUN'} — {len(rows)} torneio(s) com raw_text\n")
    touched = 0
    for r in rows:
        new_raw, n_ch, n_bld, n_tot = process_raw(r['raw_text'])
        if n_bld == 0:
            continue   # nenhum hand builder — provável upload real
        all_builder = (n_bld == n_tot)
        status = f"  tid={r['tournament_id']} user={r['user_id']} hero='{r['hero']}': {n_ch}/{n_bld} mãos builder remapeadas"
        if n_ch == 0:
            print(status + " (já limpo)")
            continue
        touched += 1
        new_hero = 'Hero' if all_builder else r['hero']
        print(status + (f" → hero='{new_hero}'" if new_hero != r['hero'] else ''))
        if args.apply:
            conn.execute("UPDATE tournaments SET raw_text = ?, hero = ? WHERE id = ?",
                         (new_raw, new_hero, r['id']))
    if args.apply and touched:
        conn.commit()
    conn.close()
    print(f"\n{'Gravado' if args.apply else 'Dry-run'}: {touched} torneio(s) alterado(s)."
          + ('' if args.apply else "  Rode com --apply pra gravar."))


if __name__ == '__main__':
    main()
