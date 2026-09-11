# -*- coding: utf-8 -*-
"""O reparo das divergencias, POR USUARIO, em uma passagem: resync + reconcile + registro.

Nasceu em 10/09, depois da medicao: 7.259 decisoes pos-flop com o veredito gravado divergindo do
que o motor produz hoje, das quais 1.390 com o ROTULO velho (a causa era o gancho fill-only, que
pulava exatamente o drift). O efeito na tela, no modo conservador: 768 acusacoes saem, 191
entram, 1.856 mudam de grau, com 637 absolvendo contra 60 agravando.

Por usuario, e nao na base toda de uma vez, porque cinco pessoas concentram tudo e duas delas
sao fundadores: o reparo entra em etapas, com conferencia entre elas.

Faz as DUAS coisas que o gancho automatico faz, na ordem dele:
  1. `resync_tournament_postflop(modo)` — realinha os 7 campos do gto com a avaliacao fresca
  2. `reconcile_tournament_labels(tid)` — realinha label, score e best_action de quem sobrou
     (sem isto, 62 decisoes em prod ficaram acusadas com `best_action` igual a jogada, o card
     dizendo "Erro" ao lado de "o ideal era exatamente isso" — o AY-26)

E grava o REGISTRO PARA DESFAZER (uma linha JSON por decisao gravada, com o antes) em
`--dump-dir`. Sem ele, `--apply` e recusado: escrita em massa sem volta pronta nao se faz. Para
reverter: `python scripts/reverter_do_dump.py <arquivo> --apply`.

Uso:
    python scripts/reparo_das_divergencias.py --user 40                    # dry-run
    python scripts/reparo_das_divergencias.py --user 40 --apply
    python scripts/reparo_das_divergencias.py --user 40 --apply --modo total
"""
import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt, reconcile_tournament_labels         # noqa: E402
from scripts.resync_postflop_gto import (resync_tournament_postflop,          # noqa: E402
                                         MODO_PRESERVA, MODO_TOTAL, MODO_FILL)

MODOS = {'preserva': MODO_PRESERVA, 'total': MODO_TOTAL, 'fill': MODO_FILL}


def torneios_do_usuario(user_id: int) -> list:
    """Torneios com decisao pos-flop e `raw_text` — os unicos que o resync alcanca.

    Sem `raw_text` nao ha o que reavaliar (o resync reparseia a mao), e o torneio sairia como
    "0 reconciliados" sem dizer por que. Aqui ele nem entra na lista, e a contagem do relatorio
    fala do que foi de fato olhado.
    """
    conn = get_conn()
    try:
        rows = conn.execute(_adapt("""
            SELECT DISTINCT t.id
            FROM tournaments t JOIN decisions d ON d.tournament_id = t.id
            WHERE t.user_id = ? AND t.raw_text IS NOT NULL
              AND lower(d.street) <> 'preflop'
            ORDER BY t.id
        """), (user_id,)).fetchall()
        return [dict(r)['id'] for r in rows]
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', type=int, required=True)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--modo', choices=sorted(MODOS), default='preserva')
    ap.add_argument('--dump-dir', default='/tmp/rollback',
                    help='onde gravar o registro para desfazer (um arquivo por usuario)')
    args = ap.parse_args()
    modo = MODOS[args.modo]

    tids = torneios_do_usuario(args.user)
    print('usuario %s | torneios com decisao pos-flop: %d | modo %s'
          % (args.user, len(tids), modo))
    if not tids:
        return

    caminho = None
    dump = None
    if args.apply:
        # O registro e PRE-REQUISITO do --apply, nao um extra. Se o diretorio nao der para
        # escrever, o reparo nao acontece: melhor nao consertar do que consertar sem volta.
        os.makedirs(args.dump_dir, exist_ok=True)
        caminho = os.path.join(args.dump_dir, 'u%s_%s.jsonl' % (args.user, args.modo))
        dump = io.open(caminho, 'w', encoding='utf-8', newline='\n')

    gravadas = 0
    reconciliadas = 0
    try:
        for tid in tids:
            n = resync_tournament_postflop(tid, apply=args.apply, modo=modo, dump=dump)
            gravadas += n
            if args.apply:
                # Na ordem do gancho: primeiro o gto, depois o realinhamento de label/score/best.
                try:
                    reconciliadas += int(reconcile_tournament_labels(tid) or 0)
                except Exception as e:                                  # noqa: BLE001
                    print('  ATENCAO: reconcile do torneio %s falhou: %s' % (tid, e))
            if n:
                print('  tid %-6s %4d decisoes' % (tid, n))
    finally:
        if dump is not None:
            dump.close()

    print()
    print('decisoes gravadas pelo resync : %d' % gravadas)
    if args.apply:
        print('linhas realinhadas pelo reconcile: %d' % reconciliadas)
        print('registro para desfazer        : %s' % caminho)
        print('   reverter: python scripts/reverter_do_dump.py %s --apply' % caminho)
    print('\n%s' % ('APLICADO' if args.apply else 'DRY-RUN (use --apply)'))


if __name__ == '__main__':
    main()
