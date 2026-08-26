# -*- coding: utf-8 -*-
"""Os nos de all-in que o re-solve anterior PULOU por mudanca de hash.

    python scripts/resolve_nos_allin_hash_recuperado.py --dry-run
    python scripts/resolve_nos_allin_hash_recuperado.py --apply

── Por que eles ficaram de fora ───────────────────────────────────────────────────────────

`resolve_nos_de_allin_com_pote_errado.py` remonta o payload com o pote certo e re-solva. Em 14 de
388 nos o `spot_hash` remontado saiu DIFERENTE do gravado -- e deletar o no antigo para gravar
noutro endereco deixaria a decisao sem cobertura e o solve novo orfao
([[project_board_hash_bug]]: jamais re-chavear no orfao). Por isso foram pulados, contados e
nomeados.

── O oraculo ──────────────────────────────────────────────────────────────────────────────

O hash NAO inclui o pote: `compute_spot_hash(street, position, board, hero, stack, facing,
pot_type_efetivo)`. Entao a diferenca vem do ultimo argumento -- o `pot_type` efetivo, que a
linha gravada nao guarda diretamente (so `is_3bet`, `preflop_raises_faced`, `hero_was_aggressor`).

Em vez de ADIVINHAR qual era, este script TESTA as combinacoes possiveis e aceita a que reproduz
o hash gravado. O hash antigo e o gabarito: se nenhuma combinacao bate, o no fica de fora --
melhor um no velho do que um orfao.
"""
import argparse
import itertools
import json
import sys

sys.path.insert(0, '/app')

from database.schema import get_conn                                   # noqa: E402
from database.repositories import enqueue_solver_spot                  # noqa: E402
from leaklab.parser import parse_hand_history                          # noqa: E402
from leaklab import hand_state_builder as hsb                          # noqa: E402
from leaklab.gto_solver import montar_payload_postflop, pote_implausivel  # noqa: E402

_POT_TYPES = ('', '3bet', 'srp')
_POSICOES = ('', 'UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')


def _prioridade(street):
    return {'flop': 3, 'turn': 2, 'river': 1}.get((street or '').lower(), 1)


def _descobre_argumentos(alvo_hash, street, pos, vs, board, hero, stack, facing, pote):
    """Combinacao (pot_type, opener, threebettor) que REPRODUZ o hash gravado, ou None.

    Busca em ordem de plausibilidade: sem pot_type, depois 3bet, e as posicoes que participam do
    spot antes das demais. O criterio de aceite e exato -- o hash bate ou nao bate.
    """
    candidatos_pos = [p for p in (('', pos, vs) + _POSICOES) if p is not None]
    vistos = set()
    ordenados = []
    for p in candidatos_pos:
        if p not in vistos:
            vistos.add(p)
            ordenados.append(p)
    for pt, op, tb in itertools.product(_POT_TYPES, ordenados, ordenados):
        montado = montar_payload_postflop(
            street=street, position=pos, vs_position=vs, board=board, hero_cards=hero,
            stack_bb=stack, facing_bb=facing, pot_bb=pote,
            pot_type=pt, opener=op, threebettor=tb)
        if montado and montado[0] == alvo_hash:
            return pt, op, tb, montado[1]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    conn = get_conn()
    alvos = [dict(r) for r in conn.execute("""
        SELECT DISTINCT d.tournament_id, d.hand_id, d.street, d.hero_cards, d.board,
               d.position, d.vs_position, d.facing_bet, d.level_bb, d.pot_size,
               COALESCE(d.effective_stack_bb, d.stack_bb) AS stack,
               d.n_active_opponents, n.spot_hash
        FROM gto_nodes n JOIN decisions d ON d.spot_hash = n.spot_hash
        WHERE n.gto_action IN ('allin','shove','jam') AND n.street <> 'preflop'
    """)]

    potes = {}
    for tid in {a['tournament_id'] for a in alvos}:
        row = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        if not row:
            continue
        try:
            maos = parse_hand_history(dict(row)['raw_text'])
        except Exception:                                              # noqa: BLE001
            continue
        for h in maos:
            acoes = getattr(h, 'actions', []) or []
            hero = getattr(h, 'hero', None)
            hid = str(getattr(h, 'hand_id', '') or '')
            for i, a in enumerate(acoes):
                if getattr(a, 'player', None) != hero:
                    continue
                st = (getattr(a, 'street', '') or 'preflop').lower()
                try:
                    p = hsb._pot_at_decision(h, acoes, i, st)
                except Exception:                                      # noqa: BLE001
                    p = None
                potes.setdefault((tid, hid, st), []).append(p)

    vistos = set()
    recuperados = perdidos = ja_ok = 0
    ex_ok, ex_perdido = [], []

    for a in alvos:
        h_antigo = a['spot_hash']
        if h_antigo in vistos:
            continue
        vistos.add(h_antigo)
        bb = float(a['level_bb'] or 0)
        fila = potes.get((a['tournament_id'], str(a['hand_id']), (a['street'] or '').lower()))
        if not fila or not bb or not fila[0]:
            continue
        pote = round(float(fila[0]) / bb, 2)
        stack = float(a['stack'] or 0)
        if pote_implausivel(pote, stack, a.get('n_active_opponents')):
            continue

        board = a['board']
        if isinstance(board, str):
            try:
                board = json.loads(board)
            except Exception:                                          # noqa: BLE001
                board = []
        hero = a['hero_cards']
        if isinstance(hero, str):
            hero = [hero[i:i + 2] for i in range(0, len(hero), 2)]
        facing = float(a['facing_bet'] or 0)
        pos, vs = a['position'] or '', a['vs_position'] or ''

        simples = montar_payload_postflop(
            street=a['street'], position=pos, vs_position=vs, board=board or [],
            hero_cards=hero or [], stack_bb=stack, facing_bb=facing, pot_bb=pote)
        if simples and simples[0] == h_antigo:
            ja_ok += 1          # o script anterior ja cobriu este
            continue

        achado = _descobre_argumentos(h_antigo, a['street'], pos, vs, board or [],
                                      hero or [], stack, facing, pote)
        if not achado:
            perdidos += 1
            if len(ex_perdido) < 6:
                ex_perdido.append('%s %-6s %s' % (a['hand_id'], a['street'], h_antigo[:12]))
            continue

        pt, op, tb, payload = achado
        recuperados += 1
        if len(ex_ok) < 6:
            ex_ok.append('%s %-6s %s  pot_type=%r opener=%r 3bettor=%r'
                         % (a['hand_id'], a['street'], h_antigo[:12], pt, op, tb))
        if args.apply:
            conn.execute('DELETE FROM gto_nodes WHERE spot_hash = ?', (h_antigo,))
            conn.commit()
            enqueue_solver_spot(h_antigo, payload, priority=_prioridade(a['street']))

    conn.close()
    print('nos de all-in postflop distintos: %d' % len(vistos))
    print('  ja cobertos pelo script anterior: %d' % ja_ok)
    print('  RECUPERADOS (hash reproduzido):   %d' % recuperados)
    print('  perdidos (nenhuma combinacao bate): %d' % perdidos)
    if ex_ok:
        print('\nrecuperados:')
        for e in ex_ok:
            print('   ' + e)
    if ex_perdido:
        print('\nperdidos (ficam com o no velho, nao viram orfao):')
        for e in ex_perdido:
            print('   ' + e)
    if not args.apply:
        print('\n[DRY-RUN] nada foi enfileirado')


if __name__ == '__main__':
    main()
