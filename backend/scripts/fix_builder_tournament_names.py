"""Reprocessa torneios construídos no Hand Builder: troca os NOMES dos jogadores no
raw_text pela POSIÇÃO real da mão (hero → "Hero"), derivada de assento+button (mesma
lógica do engine `_infer_position` e do `/replay`). Corrige mãos antigas onde o nome
era um rótulo posicional STALE (ex.: "UTG+1" no assento que é BTN), que o Replayer
exibia competindo com a posição.

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


def process_raw(raw):
    """Remapeia todas as mãos builder do raw_text. Devolve (novo_raw, n_changed, n_builder, n_total)."""
    parts = re.split(r'(?=PokerStars Hand #)', raw)
    out, n_changed, n_builder, n_total = [], 0, 0, 0
    for p in parts:
        if not p.strip():
            out.append(p); continue
        if not p.startswith('PokerStars Hand #'):
            out.append(p); continue
        n_total += 1
        new, changed, is_builder = remap_hand(p)
        if is_builder: n_builder += 1
        if changed: n_changed += 1
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
