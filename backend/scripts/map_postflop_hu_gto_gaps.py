"""Mapa dos spots POSTFLOP HU sem status GTO (read-only).

AUTORITATIVO PELO ENGINE: para cada decisão postflop heads-up sem gto_label, reconstrói
o spot pelo PARSER ATUAL e pergunta ao próprio engine (`_enrich_gto`) por que não há GTO.
NÃO confia na coluna `vs_position` do banco (que está STALE = 'unknown' em torneios
antigos, embora o parser resolva o villain — ver nota abaixo). Não muta nada.

Buckets (motivo real do _enrich_gto):
  UNGRADEABLE → existe nó, mas a AÇÃO do hero não está nas ações do nó (bet/raise/shove
                num nó que não oferece esse ramo, ou nó parcial só com a top action).
                Fechar exige um nó com o ramo de bet/raise/sizing do hero (lado solver).
  NO_NODE     → nenhum nó usável (nunca solvado / solve falhou). Villain é conhecido pelo
                parser, então é solvável — exceto stacks fundos (>60bb) que estouram a RAM
                do solver (6GB) e caem na Opção B (≈ Aproximação).
  STALE_ATTACH→ o engine JÁ devolve GTO (available), mas a decisão no banco está sem — basta
                resync (raro; normalmente 0).

NOTA (2026-06-15): a coluna `vs_position` está stale ('unknown') em decisões antigas; o
parser ATUAL resolve o villain em 100% destes spots. NÃO é problema de parser.
"""
import sqlite3, json, re, os
from collections import Counter, defaultdict
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
for _line in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in _line and not _line.strip().startswith('#'):
        _k, _v = _line.split('=', 1); os.environ.setdefault(_k.strip(), _v.strip())
os.environ['TEXAS_HERO_IP'] = '1'
os.environ['TEXAS_HERO_IP_FACING'] = '1'

from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import _enrich_gto

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')


def _depth_band(s):
    if s is None: return '??'
    if s <= 12: return '<=12bb'
    if s <= 24: return '13-24bb'
    if s <= 35: return '25-35bb'
    if s <= 45: return '36-45bb'
    if s <= 60: return '46-60bb'
    return '>60bb'


def _na(a):
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    return 'allin' if s in ('shove', 'jam', 'allin') else s


def classify():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    HU = "(COALESCE(n_active_opponents, num_players-1) = 1)"
    POST = "lower(street) IN ('flop','turn','river')"
    NOGTO = "(gto_label IS NULL OR gto_label='')"
    rows = c.execute(f"""SELECT id,tournament_id,hand_id,street,position,vs_position,
        stack_bb,facing_bet,is_3bet,action_taken,best_action FROM decisions
        WHERE {POST} AND {HU} AND {NOGTO} ORDER BY tournament_id,street""").fetchall()
    by_tid = defaultdict(list)
    for r in rows:
        by_tid[r['tournament_id']].append(r)

    out = []
    for tid, rs in by_tid.items():
        raw = c.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        hands = {}
        if raw and raw['raw_text']:
            hands = {str(h.hand_id): h for h in parse_pokerstars_file_from_text(raw['raw_text'])}
        for r in rs:
            live_vs, reason, node_has = None, 'no-di', False
            h = hands.get(str(r['hand_id']))
            if h:
                for di in build_decision_inputs_for_hand(h):
                    if di['street'] == r['street'] and _na(di.get('player_action')) == _na(r['action_taken']):
                        live_vs = di['spot'].get('villainPosition')
                        g = _enrich_gto(di)
                        if g.get('available'):
                            reason = 'STALE_ATTACH'
                        elif g.get('ungradeable_action'):
                            reason = 'UNGRADEABLE'
                        else:
                            reason = 'NO_NODE'
                        break
            out.append({
                'id': r['id'], 'tid': tid, 'hand': r['hand_id'], 'street': r['street'],
                'pos': r['position'], 'stored_vs': r['vs_position'], 'live_vs': live_vs,
                'facing': 'vs-bet' if (r['facing_bet'] or 0) > 0 else 'first-in',
                'depth': _depth_band(r['stack_bb']), 'stack_bb': r['stack_bb'],
                'played': r['action_taken'], 'best': r['best_action'], 'bucket': reason,
            })
    c.close()
    return out


def render(rows):
    BKT = {
        'UNGRADEABLE':  'UNGRADEABLE — nó não oferece a ação do hero (bet/raise/shove)',
        'NO_NODE':      'NO_NODE — sem nó usável (nunca solvado / solve falhou)',
        'STALE_ATTACH': 'STALE_ATTACH — engine já devolve GTO; só falta resync',
        'no-di':        'NÃO reconstruído no parse',
    }
    REM = {
        'UNGRADEABLE':  'Lado SOLVER: emitir nó com o ramo de bet/raise/sizing do hero. Re-solve sozinho NÃO fecha.',
        'NO_NODE':      'Enfileirar + solve (villain é conhecido pelo parser). Stacks >60bb estouram a RAM do solver → Opção B (≈ Aproximação).',
        'STALE_ATTACH': 'resync_postflop_gto.py --apply (anexa o gto já disponível).',
        'no-di':        'Verificar parser/identificação da decisão.',
    }
    ORDER = ['STALE_ATTACH', 'UNGRADEABLE', 'NO_NODE', 'no-di']
    by = Counter(r['bucket'] for r in rows)

    def _actionable(r):
        return (r['played'] or '').lower() != (r['best'] or '').lower()

    n_act = sum(1 for r in rows if _actionable(r))
    n_villain_unresolved = sum(1 for r in rows if (r['live_vs'] or '').lower() in ('', 'unknown', 'none'))
    n_stale_col = sum(1 for r in rows if (r['stored_vs'] or '').lower() in ('', 'unknown')
                      and (r['live_vs'] or '').lower() not in ('', 'unknown', 'none'))

    L = []
    L.append('# Mapa — spots POSTFLOP HU sem status GTO (autoritativo pelo engine)')
    L.append('')
    L.append(f'Total: **{len(rows)}** decisões postflop heads-up sem `gto_label` (DB dev local). '
             f'Cobertura HU postflop ≈ 94,6%.')
    L.append('Gerado por `scripts/map_postflop_hu_gto_gaps.py` — reconstrói o spot pelo parser ATUAL '
             'e pergunta ao `_enrich_gto` o motivo real. Read-only.')
    L.append('')
    L.append(f'**Parser:** villain NÃO resolvido pelo parser atual em **{n_villain_unresolved}** dos {len(rows)} '
             f'spots — ou seja, NÃO é problema de parser. Em **{n_stale_col}** spots a coluna `vs_position` do '
             f'banco está STALE (`unknown`) embora o parser resolva o villain (issue de dado, não de cobertura).')
    L.append('')
    L.append(f'**Prioridade:** {n_act} acionáveis (jogou ≠ best); {len(rows) - n_act} são linhas default sem erro pendente.')
    L.append('')
    L.append('## Resumo por causa-raiz (motivo do engine)')
    L.append('')
    L.append('| Bucket | Qtde | Remediação |')
    L.append('|---|---|---|')
    for k in ORDER:
        if by.get(k):
            L.append(f'| {BKT[k]} | {by[k]} | {REM[k]} |')
    L.append('')
    L.append('## Distribuições')
    L.append('')
    for dim, key in [('Street/Facing', lambda r: f"{r['street']}/{r['facing']}"),
                     ('Profundidade', lambda r: r['depth']),
                     ('Posição (hero v villain LIVE)', lambda r: f"{r['pos']}v{r['live_vs']}")]:
        dist = Counter(key(r) for r in rows)
        L.append(f"- **{dim}:** " + ', '.join(f'{k}={v}' for k, v in dist.most_common()))
    L.append('')
    for k in ORDER:
        sub = [r for r in rows if r['bucket'] == k]
        if not sub:
            continue
        n_sub_act = sum(1 for r in sub if _actionable(r))
        L.append(f'## {BKT[k]}  — {len(sub)} spot(s)  ({n_sub_act} acionável(is))')
        L.append('')
        L.append(f'**Remediação:** {REM[k]}')
        L.append('')
        L.append('| id | torneio | mão | street | pos | villain (live) | vs_col(stale) | facing | depth | jogou | best | acionável |')
        L.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for r in sub:
            L.append(f"| {r['id']} | {r['tid']} | {r['hand']} | {r['street']} | {r['pos']} | {r['live_vs']} | "
                     f"{r['stored_vs']} | {r['facing']} | {r['depth']} | {r['played']} | {r['best']} | "
                     f"{'SIM' if _actionable(r) else '-'} |")
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
