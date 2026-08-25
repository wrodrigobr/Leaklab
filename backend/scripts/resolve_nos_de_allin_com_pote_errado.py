# -*- coding: utf-8 -*-
"""Re-solva os nos postflop que recomendam ALL-IN por causa do pote errado no payload.

    python scripts/resolve_nos_de_allin_com_pote_errado.py --dry-run
    python scripts/resolve_nos_de_allin_com_pote_errado.py --apply [--limite N]

── O que se descobriu (25/08) ─────────────────────────────────────────────────────────────

Tres juizes de poker apontaram que o card recomendava all-in de ate 22x o pote. A causa NAO era
no de profundidade errada (o bucket bate em 242 de 242), nem no mal convergido (a exploitability
dos suspeitos e melhor que a dos normais), nem arvore degenerada (o formato `check/allin` aparece
igual nos dois grupos).

Era o POTE no payload do solve. Provado no solver de producao, mesmo spot (`9hJd` em `5h 7s 7c`,
61bb), trocando so o pote:

    pot_bb 0.5  ->  HTTP 500: "spot requer 7.2GB, excede o limite de 6GB"
    pot_bb 3.0  ->  59s, exploitability 2,5%, **check 67,6% / bet_50pct 32,4%**

Pote de 0,5bb num FLOP e impossivel -- depois do preflop o pote tem no minimo os blinds. Vinha do
`pot_size`, a reconstrucao de 1,2% de acerto. `spot.potBb` so passou a apontar para o pote real
em 24/08, entao estes nos sao legado anterior.

── Por que o DELETE antes do enqueue ──────────────────────────────────────────────────────

A blindagem do upsert ("nao piora a exploitability") bloquearia o solve novo, porque o no do pote
errado converge para ~0,01 **fraudulentamente perfeito** -- arvore pequena converge facil. Em
14/08 isso bloqueou 40 de 40 re-solves em silencio. No provadamente de outra escala nao merece
blindagem. O `spot_hash` NAO inclui o pote, entao o solve novo grava no MESMO endereco: sem
orfaos, que e a armadilha registrada em [[project_board_hash_bug]].

── Custo ──────────────────────────────────────────────────────────────────────────────────

59s por no, medidos. Solver com 8 vCPU e 2 solves simultaneos: ~3,2h para os 388 nos usados.
"""
import argparse
import json
import sys

sys.path.insert(0, '/app')

from database.schema import get_conn                                   # noqa: E402
from leaklab.parser import parse_hand_history                          # noqa: E402
from leaklab import hand_state_builder as hsb                          # noqa: E402
from leaklab.gto_solver import (montar_payload_postflop,               # noqa: E402
                                pote_implausivel)
from database.repositories import enqueue_solver_spot                  # noqa: E402


def _prioridade(street):
    return {'flop': 3, 'turn': 2, 'river': 1}.get((street or '').lower(), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limite', type=int, default=0, help='0 = sem limite')
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

    # pote RECONSTRUIDO por (torneio, mao, street) — 99,6% contra o SUMMARY
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
    enfileirados = sem_pote = recusados = ja_bom = hash_mudou = 0
    exemplos = []
    ex_hash = []

    for a in alvos:
        h_antigo = a['spot_hash']
        if h_antigo in vistos:
            continue
        bb = float(a['level_bb'] or 0)
        fila = potes.get((a['tournament_id'], str(a['hand_id']), (a['street'] or '').lower()))
        pote_novo = None
        if fila and bb and fila[0]:
            pote_novo = round(float(fila[0]) / bb, 2)
        pote_velho = float(a['pot_size'] or 0)
        if not pote_novo:
            sem_pote += 1
            continue
        # Se o pote gravado JA era o certo, o no nao foi vitima deste defeito.
        if abs(pote_novo - pote_velho) < 0.05:
            ja_bom += 1
            continue

        stack = float(a['stack'] or 0)
        if pote_implausivel(pote_novo, stack, a.get('n_active_opponents')):
            recusados += 1
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

        montado = montar_payload_postflop(
            street=a['street'], position=a['position'] or '',
            vs_position=a['vs_position'] or '', board=board or [], hero_cards=hero or [],
            stack_bb=stack, facing_bb=float(a['facing_bet'] or 0), pot_bb=pote_novo)
        if not montado:
            recusados += 1
            continue
        h_novo, payload = montado
        vistos.add(h_antigo)
        if h_novo != h_antigo:
            # HASH DIFERENTE = endereco diferente. Deletar o no antigo e gravar noutro lugar
            # deixaria a decisao SEM cobertura e o solve novo orfao -- a armadilha registrada em
            # [[project_board_hash_bug]] ("jamais re-chavear no orfao"). O hash nao inclui o
            # pote, entao a diferenca vem de outro argumento (tipicamente `pot_type`, que esta
            # linha nao consegue reconstruir). Estes ficam de fora, contados e nomeados.
            hash_mudou += 1
            if len(ex_hash) < 5:
                ex_hash.append('%s %-6s  %s -> %s' % (a['hand_id'], a['street'],
                                                      h_antigo[:12], h_novo[:12]))
            continue

        if len(exemplos) < 5:
            exemplos.append('%s %-6s pote %.1f -> %.1f bb   hash %s%s'
                            % (a['hand_id'], a['street'], pote_velho, pote_novo,
                               h_antigo[:12], '' if h_novo == h_antigo else ' (HASH MUDOU!)'))

        if args.apply:
            # DELETE antes do enqueue: sem isso a blindagem do upsert bloqueia o solve novo,
            # porque o no do pote errado converge "perfeito" (arvore pequena). 40 de 40
            # bloqueados em silencio em 14/08.
            conn.execute('DELETE FROM gto_nodes WHERE spot_hash = ?', (h_antigo,))
            conn.commit()
            enqueue_solver_spot(h_novo, payload, priority=_prioridade(a['street']))
        enfileirados += 1
        if args.limite and enfileirados >= args.limite:
            break

    conn.close()
    print('nos de all-in postflop com uso: %d' % len(alvos))
    print('  A RE-SOLVAR (pote gravado != pote real): %d' % enfileirados)
    print('  ja tinham o pote certo:                  %d' % ja_bom)
    print('  sem pote reconstruivel:                  %d' % sem_pote)
    print('  recusados pelo gate:                     %d' % recusados)
    print('  PULADOS por mudanca de hash (evita orfao): %d' % hash_mudou)
    if ex_hash:
        print('    exemplos de hash mudado:')
        for e in ex_hash:
            print('      ' + e)
    if exemplos:
        print('\nexemplos:')
        for e in exemplos:
            print('   ' + e)
    print('\ncusto estimado: %.1f h (59s por no, 2 solves simultaneos)'
          % (enfileirados * 59 / 2 / 3600))
    if not args.apply:
        print('\n[DRY-RUN] nada foi enfileirado')


if __name__ == '__main__':
    main()
