# -*- coding: utf-8 -*-
"""Aplica SO a regra de severidade sem custo ao acervo, sem reavaliar nada.

    python scripts/aplica_severidade_sem_custo.py --dry-run
    python scripts/aplica_severidade_sem_custo.py --apply

── Por que um script proprio, e nao o regrade ─────────────────────────────────────────────

`regrade_preflop_no_lugar.py --streets todas` re-roda o motor no acervo inteiro e mexe em **832
linhas**: 216 ganham `gto_label` que era NULL (nos de solver capturados hoje), 117 mudam de
`best_action`, 726 de score. Quase tudo isso e acerto de contas de mudancas anteriores ao pedido,
e nao esta medido nem validado.

O pedido foi outro: **resolver a severidade sem custo.** Essa regra e uma funcao PURA da linha ja
gravada -- `label` e `verdict_has_cost`. Nao precisa do parser, nao precisa do motor, nao precisa
de nó de solver. Entao ela e aplicada sozinha, e o que ela toca e nomeado antes de ser tocado.

Reavaliar o acervo inteiro pode ser certo, mas e OUTRA decisao, com outros numeros -- e mistura-la
aqui esconderia o efeito desta.

── O que muda ─────────────────────────────────────────────────────────────────────────────

Somente linhas com `label = 'clear_mistake'` e sem custo medido. Nelas:

  * `label` -> `small_mistake` (segue sendo acusacao: frequencia zero e evidencia);
  * `score` -> reposicionado na banda do label novo pelo MESMO `_align_score_to_label` do insert,
    sem regra propria -- o teto `hi` da banda de `small_mistake` (0,35) faz o trabalho.

Nada mais e tocado.
"""
import argparse
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                                      # noqa: E402
from database.repositories import _align_score_to_label                   # noqa: E402
from leaklab.verdict import severidade_sem_custo                          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    conn = get_conn()
    alvos = [dict(r) for r in conn.execute("""
        SELECT id, street, label, score, gto_label, ev_loss_bb, verdict_has_cost, verdict_source
        FROM decisions
        WHERE label = 'clear_mistake'
          AND COALESCE(verdict_has_cost, FALSE) = FALSE
        ORDER BY id
    """)]

    # CONTROLE: se o filtro nao achar nada, e defeito do filtro, nao boa noticia. O acervo tinha
    # 47 destes em 26/08, entao zero aqui significa que a consulta parou de enxergar.
    if not alvos:
        conn.close()
        sys.exit('CONTROLE FALHOU: zero linhas com clear_mistake sem custo. Em 26/08 havia 47 -- '
                 'ou a regra ja foi aplicada, ou o filtro quebrou. Confira antes de comemorar.')

    cont = Counter()
    exemplos = []
    for a in alvos:
        novo_label = severidade_sem_custo(a['label'], bool(a['verdict_has_cost']))
        if novo_label == a['label']:
            cont['inalterado'] += 1
            continue
        novo_score = _align_score_to_label(novo_label, a['score'], a['ev_loss_bb'])
        cont['muda'] += 1
        cont['street_' + (a['street'] or '?')] += 1
        cont['fonte_' + (a['verdict_source'] or '?')] += 1
        if len(exemplos) < 12:
            exemplos.append('#%-7s %-7s %-14s -> %-14s  score %.3f -> %.3f  (%s)'
                            % (a['id'], a['street'], a['label'], novo_label,
                               float(a['score'] or 0), novo_score, a['verdict_source']))
        if args.apply:
            conn.execute('UPDATE decisions SET label=?, score=? WHERE id=?',
                         (novo_label, novo_score, a['id']))
    if args.apply:
        conn.commit()
    conn.close()

    print('linhas com clear_mistake e sem custo medido: %d' % len(alvos))
    print('  MUDAM: %d   (inalteradas: %d)' % (cont['muda'], cont['inalterado']))
    print('  por street:     %s' % ', '.join('%s=%d' % (k[7:], v)
                                             for k, v in sorted(cont.items())
                                             if k.startswith('street_')))
    print('  por procedencia: %s' % ', '.join('%s=%d' % (k[6:], v)
                                              for k, v in sorted(cont.items())
                                              if k.startswith('fonte_')))
    if exemplos:
        print('\nexemplos:')
        for e in exemplos:
            print('   ' + e)
    if not args.apply:
        print('\n[DRY-RUN] nada foi gravado')


if __name__ == '__main__':
    main()
