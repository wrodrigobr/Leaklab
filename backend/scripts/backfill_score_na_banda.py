# -*- coding: utf-8 -*-
"""Alinha `decisions.score` a banda do proprio `label` nas linhas ANTIGAS.

    python scripts/backfill_score_na_banda.py --dry-run
    python scripts/backfill_score_na_banda.py --apply

Por que existe (24/08): 27 decisoes estavam gravadas com `label` de erro e `score` 0 ou nulo --
**27 de 27 com `gto_label = gto_critical`**, e 20 delas com `math_penalty`/`range_penalty` > 0
ao lado do score zerado. O `_gto_label_cap` promove o LABEL quando a carta reprova a jogada e
nao toca no SCORE, e o INSERT gravava `mistakeScore` cru.

O codigo ja foi consertado (`save_decisions` grava `_align_score_to_label(...)`), entao toda
decisao NOVA nasce coerente. Este script existe so para o acervo que ja estava gravado.

O que o numero move: `priority_score = COUNT(*) * AVG(d.score)` ordena os leaks do plano de
estudo. Com score 0, as decisoes que o SOLVER considera criticas eram justo as que puxavam a
media da familia para baixo. Medido antes de aplicar: 63 linhas tocadas, 1 usuario de 8 com
troca de ordem, topo do plano inalterado em todos.

NAO toca em `label`, `gto_label`, `ev_loss_bb` nem em nada que decida veredito: so move o score
para DENTRO da banda que o proprio label ja declara. Usa a mesma funcao do reconcile
(`_align_score_to_label`) -- e regra 5: uma politica, uma funcao.
"""
import argparse
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                                        # noqa: E402
from database.repositories import _align_score_to_label, _LABEL_SCORE_BAND  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    conn = get_conn()
    linhas = [dict(r) for r in conn.execute(
        'SELECT id, label, score, gto_label FROM decisions WHERE label IS NOT NULL').fetchall()]

    # ESCOPO: so acusacao com score ABAIXO do piso da banda -- o defeito medido (o cap promove
    # o label e deixa o score para tras). O dry-run de 24/08 mostrou que "alinhar tudo" tocaria
    # 404 linhas, das quais 189 `standard` e 152 `marginal` com score ACIMA do teto: rebaixa-las
    # mexeria na media de decisoes CORRETAS, um efeito que ninguem mediu e que o bug nao causava.
    # Elas viram achado separado, nao carona neste backfill.
    fora, acima = [], []
    for d in linhas:
        novo = _align_score_to_label(d['label'], d['score'])
        atual = float(d['score']) if d['score'] is not None else None
        if atual is not None and abs(novo - atual) <= 1e-9:
            continue
        if d['label'] in ('small_mistake', 'clear_mistake') and (atual is None or novo > atual):
            fora.append((d, atual, novo))
        else:
            acima.append((d, atual, novo))

    print('decisoes no acervo: %d' % len(linhas))
    print('NO ESCOPO (acusacao com score abaixo do piso): %d' % len(fora))
    print('FORA do escopo (score acima do teto, outra familia): %d' % len(acima))
    por_label = Counter(d['label'] for d, _, _ in fora)
    for lab, n in por_label.most_common():
        lo, hi = _LABEL_SCORE_BAND.get(lab, (0.0, 0.08))
        print('   %-14s %4d   (banda %.2f-%.2f)' % (lab, n, lo, hi))
    # o subconjunto que motivou tudo
    criticas = [t for t in fora if t[0]['label'] in ('small_mistake', 'clear_mistake')
                and (t[1] is None or t[1] == 0.0)]
    print('   dessas, acusacoes com score 0/NULL: %d   (com gto_critical: %d)'
          % (len(criticas),
             sum(1 for d, _, _ in criticas if d.get('gto_label') == 'gto_critical')))

    if fora:
        print('\nmaiores movimentos (score atual -> alinhado):')
        for d, a, n in sorted(fora, key=lambda t: -(t[2] - (t[1] or 0)))[:6]:
            print('   id=%-8s %-14s %s -> %.4f' % (d['id'], d['label'], a, n))

    if args.apply:
        for d, _, novo in fora:
            conn.execute('UPDATE decisions SET score=? WHERE id=?', (novo, d['id']))
        conn.commit()
        # conferencia explicita: operacao que pode falhar em silencio precisa de releitura
        # A 1a versao contava o acervo INTEIRO e imprimia "(esperado 0)". Na rodada real ela
        # mostrou 347 -- os que o script deliberadamente nao toca -- e por um instante isso
        # passou por falha. Conferencia tem que medir o que a operacao prometeu mexer.
        resto = 0
        for r in conn.execute('SELECT id, label, score FROM decisions WHERE label IS NOT NULL'):
            d = dict(r)
            a = float(d['score']) if d['score'] is not None else None
            nv = _align_score_to_label(d['label'], d['score'])
            if a is not None and abs(nv - a) <= 1e-9:
                continue
            if d['label'] in ('small_mistake', 'clear_mistake') and (a is None or nv > a):
                resto += 1
        print('\n[APLICADO] %d linhas escritas. Acusacoes ainda abaixo do piso: %d (esperado 0)'
              % (len(fora), resto))
        print('           fora do escopo, intocados de proposito: %d' % len(acima))
    else:
        print('\n[DRY-RUN] nada foi escrito')


if __name__ == '__main__':
    main()
