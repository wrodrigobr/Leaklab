"""Mapa dos spots POSTFLOP HU sem status GTO (read-only).

Classifica cada decisão postflop heads-up sem gto_label nas causas-raiz e gera um
relatório markdown em docs/postflop_hu_gto_gaps.md. Não muta nada.

Buckets:
  A) NÓ AGREGADO sem tabela hand-aware  → existe nó solved mas require_hand_aware
     o rejeita (sem gto_tree_strategies). Remediação: re-solve hand-aware.
  B) SOLVER FALHOU (queue=failed)        → no-solution genuíno ou erro a investigar.
  C) NUNCA ENFILEIRADO (órfão)           → sem nó e fora da fila. Enfileirar + solve.
"""
import sqlite3, json, re, os
from collections import Counter
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from leaklab.gto_utils import compute_spot_hash

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')
NB = {'flop': 3, 'turn': 4, 'river': 5}


def _cards(s):
    return re.findall(r'[2-9TJQKA][cdhs]', s or '')


def _depth_band(s):
    if s is None: return '??'
    if s <= 12: return '<=12bb'
    if s <= 24: return '13-24bb'
    if s <= 35: return '25-35bb'
    if s <= 45: return '36-45bb'
    if s <= 60: return '46-60bb'
    return '>60bb'


def classify():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    HU = "(COALESCE(n_active_opponents, num_players-1) = 1)"
    POST = "lower(street) IN ('flop','turn','river')"
    NOGTO = "(gto_label IS NULL OR gto_label='')"
    rows = c.execute(f"""SELECT id,tournament_id,hand_id,street,position,vs_position,board,hero_cards,
        stack_bb,facing_bet,is_3bet,action_taken,best_action,label
        FROM decisions WHERE {POST} AND {HU} AND {NOGTO} ORDER BY street,stack_bb""").fetchall()
    out = []
    for r in rows:
        board = json.loads(r['board']); hero = _cards(r['hero_cards'])
        b = board[:NB[r['street']]]
        try:
            h = compute_spot_hash(r['street'], r['position'].upper(), b, hero,
                                  r['stack_bb'], r['facing_bet'] or 0.0, '')
        except Exception:
            h = None
        node = c.execute('SELECT source FROM gto_nodes WHERE spot_hash=?', (h,)).fetchone() if h else None
        q = c.execute('SELECT status,tree_hash FROM gto_solver_queue WHERE spot_hash=?', (h,)).fetchone() if h else None
        tree = 0
        if q and q['tree_hash']:
            tree = c.execute('SELECT COUNT(*) FROM gto_tree_strategies WHERE tree_hash=?', (q['tree_hash'],)).fetchone()[0]
        if node and tree == 0:
            bucket = 'A_aggregate_no_handaware'
        elif q and q['status'] == 'failed':
            bucket = 'B_solver_failed'
        elif not node:
            bucket = 'C_never_queued'
        else:
            bucket = 'D_other'
        out.append({
            'id': r['id'], 'tid': r['tournament_id'], 'hand': r['hand_id'],
            'street': r['street'], 'pos': r['position'], 'vs': r['vs_position'],
            'facing': 'vs-bet' if (r['facing_bet'] or 0) > 0 else 'first-in',
            'pot': '3bet' if r['is_3bet'] else 'SRP',
            'depth': _depth_band(r['stack_bb']), 'stack_bb': r['stack_bb'],
            'played': r['action_taken'], 'best': r['best_action'],
            'node_src': node['source'] if node else None,
            'queue': q['status'] if q else None, 'bucket': bucket,
        })
    c.close()
    return out


def render(rows):
    BKT = {
        'A_aggregate_no_handaware': 'A) Nó agregado SEM tabela hand-aware (require_hand_aware rejeita)',
        'B_solver_failed':          'B) Solver FALHOU (no-solution genuíno ou erro)',
        'C_never_queued':           'C) NUNCA enfileirado (órfão — sem nó, fora da fila)',
        'D_other':                  'D) Outro',
    }
    REM = {
        'A_aggregate_no_handaware': 'Re-solve hand-aware (gerar gto_tree_strategies) — mesma campanha de 2026-06-12.',
        'B_solver_failed':          'Investigar log do solver: confirmar no-solution do GW vs erro de servidor.',
        'C_never_queued':           'Enfileirar (requeue_orphaned_postflop --apply) + solve hand-aware; >60bb usa Opção B (≈ Aproximação).',
        'D_other':                  '—',
    }
    by = Counter(r['bucket'] for r in rows)

    def _actionable(r):
        # jogou ≠ best ⇒ o engine já aponta um possível erro que o GTO não está graduando.
        return (r['played'] or '').lower() != (r['best'] or '').lower()

    n_act = sum(1 for r in rows if _actionable(r))
    L = []
    L.append('# Mapa — spots POSTFLOP HU sem status GTO')
    L.append('')
    L.append(f'Total: **{len(rows)}** decisões postflop heads-up sem `gto_label` (DB dev local).')
    L.append('Gerado por `scripts/map_postflop_hu_gto_gaps.py` (read-only).')
    L.append('')
    L.append(f'**Prioridade:** {n_act} são "acionáveis" (jogou ≠ best — o engine já sinaliza um '
             f'possível erro que falta o GTO confirmar); os outros {len(rows) - n_act} são linhas '
             f'default (check/check etc.) sem erro pendente — cobertura por completude, baixa prioridade.')
    L.append('')
    L.append('## Resumo por causa-raiz')
    L.append('')
    L.append('| Bucket | Qtde | Remediação |')
    L.append('|---|---|---|')
    for k in ('A_aggregate_no_handaware', 'B_solver_failed', 'C_never_queued', 'D_other'):
        if by.get(k):
            L.append(f'| {BKT[k]} | {by[k]} | {REM[k]} |')
    L.append('')
    # distribuições
    L.append('## Distribuições (todos os spots)')
    L.append('')
    for dim, key in [('Street/Facing', lambda r: f"{r['street']}/{r['facing']}"),
                     ('Profundidade', lambda r: r['depth']),
                     ('Posição', lambda r: r['pos']),
                     ('Tipo de pote', lambda r: r['pot'])]:
        dist = Counter(key(r) for r in rows)
        L.append(f"- **{dim}:** " + ', '.join(f'{k}={v}' for k, v in dist.most_common()))
    L.append('')
    # detalhe por bucket
    for k in ('A_aggregate_no_handaware', 'B_solver_failed', 'C_never_queued', 'D_other'):
        sub = [r for r in rows if r['bucket'] == k]
        if not sub:
            continue
        L.append(f'## {BKT[k]}  — {len(sub)} spot(s)')
        L.append('')
        L.append(f'**Remediação:** {REM[k]}')
        L.append('')
        n_sub_act = sum(1 for r in sub if _actionable(r))
        L.append(f'_{n_sub_act} acionável(is) (jogou ≠ best) de {len(sub)}._')
        L.append('')
        L.append('| id | torneio | mão | street | pos | vs | facing | depth | jogou | best | acionável | fonte_nó | fila |')
        L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for r in sub:
            L.append(f"| {r['id']} | {r['tid']} | {r['hand']} | {r['street']} | {r['pos']} | {r['vs']} | "
                     f"{r['facing']} | {r['depth']} | {r['played']} | {r['best']} | {'SIM' if _actionable(r) else '-'} | "
                     f"{r['node_src'] or '-'} | {r['queue'] or '-'} |")
        L.append('')
    return '\n'.join(L)


if __name__ == '__main__':
    rows = classify()
    md = render(rows)
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'docs', 'postflop_hu_gto_gaps.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md + '\n')
    print(md)
    print(f'\n[escrito em {out_path}]')
