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
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt, reconcile_tournament_labels         # noqa: E402
from scripts.resync_postflop_gto import (resync_tournament_postflop,          # noqa: E402
                                         linha_do_dump, MODO_PRESERVA, MODO_TOTAL, MODO_FILL)

#: Os campos que o reconcile pode reescrever, junto com os do resync. `score` entra porque o
#: reconcile o re-deriva do label, e sem ele a volta devolveria o rotulo antigo com a nota nova.
_CAMPOS_RECONCILE = ('label', 'best_action', 'gto_label', 'gto_action', 'gto_played_freq',
                     'gto_top_freq', 'ev_loss_bb', 'ev_loss_source', 'score')


def _estado_do_torneio(tid: int) -> dict:
    """{id: linha} das decisoes que o reconcile pode reescrever (as que tem gto_label).

    Existe porque o `reconcile_tournament_labels` alcanca linhas que o resync NAO tocou, e sem
    este retrato elas ficariam fora do registro para desfazer. Medido em 10/09 na minha propria
    conta: o resync gravou 168 linhas e o reconcile mexeu em ~180 OUTRAS, que eu nao teria como
    reverter. Registro que cobre metade da escrita nao e registro.
    """
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(
            "SELECT id, hand_id, street, action_taken, %s FROM decisions "
            "WHERE tournament_id = ? AND gto_label IS NOT NULL AND gto_label <> ''"
            % ', '.join(_CAMPOS_RECONCILE)), (tid,)).fetchall()
        return {dict(r)['id']: dict(r) for r in rows}
    finally:
        conn.close()


def _grava_o_que_o_reconcile_mudou(dump, tid: int, antes: dict) -> int:
    """Compara o retrato com o estado de agora e grava as linhas que o reconcile mexeu.

    Usa `linha_do_dump`, a MESMA funcao do resync: o registro nao pode ter dois formatos, senao
    a ferramenta de reverter entende um e o outro nao.
    """
    depois = _estado_do_torneio(tid)
    n = 0
    for did, a in antes.items():
        d = depois.get(did)
        if not d:
            continue
        if all(a.get(c) == d.get(c) for c in _CAMPOS_RECONCILE):
            continue
        # o formato que `linha_do_dump` espera do lado "depois"
        f = {'label': d['label'], 'best': d['best_action'], 'gto_label': d['gto_label'],
             'gto_action': d['gto_action'], 'played': d['gto_played_freq'],
             'top': d['gto_top_freq'], 'ev': d['ev_loss_bb'], 'ev_src': d['ev_loss_source']}
        key = (a.get('hand_id'), a.get('street'), a.get('action_taken'))
        linha = linha_do_dump(a, f, 'reconcile', ['reconcile'], tid, None, key)
        # `score` nao esta nos 8 campos do resync, e o reconcile o re-deriva: viaja fora deles
        linha['de']['score'] = a.get('score')
        linha['para']['score'] = d.get('score')
        if dump is not None:
            dump.write(json.dumps(linha, default=str) + "\n")
        n += 1
    return n

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
    tocadas_pelo_reconcile = 0
    try:
        for tid in tids:
            n = resync_tournament_postflop(tid, apply=args.apply, modo=modo, dump=dump)
            gravadas += n
            if args.apply:
                # Retrato ANTES do reconcile: ele reescreve linhas que o resync nao tocou, e sem
                # isto elas ficariam fora do registro para desfazer (achado em 10/09: 168
                # gravadas pelo resync, ~180 OUTRAS mexidas pelo reconcile).
                antes = _estado_do_torneio(tid)
                # Na ordem do gancho: primeiro o gto, depois o realinhamento de label/score/best.
                try:
                    reconciliadas += int(reconcile_tournament_labels(tid) or 0)
                except Exception as e:                                  # noqa: BLE001
                    print('  ATENCAO: reconcile do torneio %s falhou: %s' % (tid, e))
                tocadas_pelo_reconcile += _grava_o_que_o_reconcile_mudou(dump, tid, antes)
            if n:
                print('  tid %-6s %4d decisoes' % (tid, n))
    finally:
        if dump is not None:
            dump.close()

    print()
    print('decisoes gravadas pelo resync : %d' % gravadas)
    if args.apply:
        print('linhas realinhadas pelo reconcile: %d (no registro: %d)'
              % (reconciliadas, tocadas_pelo_reconcile))
        print('registro para desfazer        : %s' % caminho)
        print('   reverter: python scripts/reverter_do_dump.py %s --apply' % caminho)
    print('\n%s' % ('APLICADO' if args.apply else 'DRY-RUN (use --apply)'))


if __name__ == '__main__':
    main()
