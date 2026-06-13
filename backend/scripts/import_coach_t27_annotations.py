"""
Importa os spots PUBLICADOS de docs/coach_review_t27_spots.json como ANOTAÇÕES DO COACH
(coach_hand_annotations) no torneio #27 — fonte única no replayer em vez do JSON.

- Só status != 'pendente' (os 13 pendentes ficam pro user fazer manual no replayer).
- h → hand_id = 100000000+h. Street inferida por palavra-chave (spot+coach+quote);
  decisão = a do hero naquela street (última se houver várias), fallback = última da mão.
- comment = quote literal (quando real) + veredito do coach. mode='complement' (comparação).
- coach_action parseado do veredito quando claro.

Dry-run por padrão; --apply grava. coach_id=6, student_id=13.
"""
import os, sys, json, re, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3

COACH_ID, STUDENT_ID, TID = 6, 13, 388
DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
SPOTS = os.path.join(os.path.dirname(__file__), '..', 'docs', 'coach_review_t27_spots.json')

ap = argparse.ArgumentParser(); ap.add_argument('--apply', action='store_true'); A = ap.parse_args()

conn = sqlite3.connect(DB, timeout=30); conn.row_factory = sqlite3.Row
conn.execute('PRAGMA busy_timeout=30000')
spots = [s for s in json.load(open(SPOTS, encoding='utf-8'))['spots'] if s.get('status') != 'pendente']


def infer_street(s):
    """Retorna (street, confianca_baixa). 'pós-flop' NÃO conta como flop."""
    txt = ' '.join([s.get('spot', ''), s.get('coach', ''), s.get('quote', '')]).lower()
    txt = txt.replace('pós-flop', ' ').replace('pos-flop', ' ').replace('pós flop', ' ').replace('postflop', ' ')
    board_n = len(re.findall(r'\b[2-9tjqka][shdc]\b', (s.get('ind', '') or '').lower()))
    # keywords explícitas por street (mais confiáveis)
    if re.search(r'\briver\b|bluff-?catch no river|shove (no )?river|donk de river|value.*river|blocking bet', txt):
        return 'river', False
    if re.search(r'\bturn\b|barrel no turn|raise no turn|fold no turn|double barrel', txt):
        return 'turn', False
    if re.search(r'\bflop\b|c-?bet|donk|check-?raise|shove no flop|monotone|multiway', txt):
        return 'flop', False
    if re.search(r'3-?bet|4-?bet|5-?bet|tribet|\bopen\b|\blimp\b|squeeze|iso-?raise|reshove|'
                 r'shove vs|jam vs|defesa de bb|flat vs open|fora do range|fold vs|call do 3|set-mine', txt):
        return 'preflop', False
    # sem keyword → profundidade do board no `ind` (0 preflop, 3 flop, 4 turn, 5 river)
    by_board = {0: 'preflop', 3: 'flop', 4: 'turn', 5: 'river'}.get(board_n, '')
    return by_board, True   # confiança baixa (inferido por board, sem keyword)


def parse_action(coach: str):
    c = (coach or '').upper()
    if c.startswith('FOLD') or 'NÃO RAISE' in c or 'NAO RAISE' in c or 'NÃO C-BET' in c or 'CHECK-FOLD' in c:
        return 'fold' if c.startswith('FOLD') else ('check' if 'CHECK' in c else 'call' if 'CALL' in c else None)
    if c.startswith(('JAM', 'SHOVE')) or 'SHOVE' in c.split('(')[0]:
        return 'all-in'
    if c.startswith(('3-BET', '3BET', '4-BET', '5-BET', 'RAISE', 'ISO', 'BET')):
        return 'raise' if 'BET' in c[:6] and '3-' in c[:3] or c.startswith(('3-', '4-', '5-', 'RAISE', 'ISO')) else 'bet'
    if c.startswith('CALL'):
        return 'call'
    if c.startswith('CHECK'):
        return 'check'
    return None


def pick_decision(hand_id, street, coach):
    rows = conn.execute(
        'SELECT id, street, action_taken FROM decisions WHERE tournament_id=? AND hand_id=? ORDER BY rowid',
        (TID, hand_id)).fetchall()
    if not rows:
        return None, None
    want = parse_action(coach)
    cand = [r for r in rows if r['street'] == street] if street else []
    if cand:
        # ação que bate o veredito do coach, senão a última da street
        m = [r for r in cand if want and r['action_taken'] == want]
        chosen = (m or cand)[-1]
        return chosen['id'], chosen
    return rows[-1]['id'], rows[-1]   # fallback: última decisão da mão


def make_comment(s):
    q = (s.get('quote') or '').strip().strip('“”"')
    coach = (s.get('coach') or '').strip()
    parts = []
    if q and not q.lower().startswith(('comentário do coach', 'comentario do coach')):
        parts.append(q)
    if coach:
        parts.append(coach)
    return ' — '.join(parts)


from database.repositories import upsert_annotation  # noqa: E402

# Decisões que JÁ têm anotação manual (qualquer coach) — NÃO sobrescrever (é a fonte de
# verdade do user feita no replayer; o import só preenche lacunas).
existing = {r[0] for r in conn.execute(
    'SELECT decision_id FROM coach_hand_annotations WHERE student_id=?', (STUDENT_ID,)).fetchall()}

applied = skipped = collided = 0
print(f"{'APLICANDO' if A.apply else 'DRY-RUN'} | {len(spots)} spots publicados\n")
low_conf_list = []
for s in spots:
    hand_id = str(100000000 + s['h'])
    street, low = infer_street(s)
    did, row = pick_decision(hand_id, street, s.get('coach', ''))
    comment = make_comment(s)
    if not did:
        skipped += 1
        print(f"  SKIP h={s['h']} {s['cards']} — sem decisão no banco")
        continue
    if did in existing:
        collided += 1
        print(f"  JÁ ANOTADO h={s['h']:<3} {s['cards']:<5} dec#{did} — preservando sua anotação manual")
        continue
    act = row['action_taken'] if row else '?'
    st  = row['street'] if row else '?'
    # baixa confiança: inferência por board OU street caiu em fallback (última da mão)
    flag = low or not street or (street and st != street)
    if flag:
        low_conf_list.append(s['h'])
    cact = parse_action(s.get('coach', ''))
    print(f"  h={s['h']:<3} {s['cards']:<5} -> dec#{did} {st}/{act} {'⚠️' if flag else '  '} "
          f"(inf={street or '—'}) act={cact or '—'}\n      {comment[:108]}")
    if A.apply:
        upsert_annotation(COACH_ID, STUDENT_ID, did, comment, mode='complement', coach_action=cact)
        applied += 1
print(f"\n⚠️  baixa confiança (revisar street no replayer): {low_conf_list}")
print(f"já anotados manualmente (preservados): {collided}")

conn.close()
to_write = len(spots) - skipped - collided
print(f"\n{'Gravadas' if A.apply else 'Seriam gravadas'}: {applied if A.apply else to_write} "
      f"| sem decisão: {skipped} | já manuais (preservados): {collided}")
