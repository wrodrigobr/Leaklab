# -*- coding: utf-8 -*-
"""Preenche `decisions.verdict_source` e `verdict_has_cost` nas linhas ANTERIORES a migracao.

    python scripts/backfill_procedencia.py --dry-run
    python scripts/backfill_procedencia.py --apply

Por que existe: a procedencia passou a ser gravada em 24/08, entao toda decisao NOVA ja nasce
declarando de onde veio o veredito. As antigas ficam NULL, e a primeira escolha foi derivar na
LEITURA (o `/replay` faz isso). A medicao mostrou o custo dessa escolha: qualquer analise sobre
o BANCO -- inclusive a sonda que criou este trabalho -- continua vendo 1.503 decisoes mudas,
porque a derivacao so acontece na porta da API.

Campo novo, antes NULL: e aditivo e reversivel. NAO toca em `label`, `score`, `ev_loss_bb` nem
em nada que decida veredito -- so preenche a origem que o motor ja sabia e nao gravava.

A derivacao usa a MESMA funcao do motor (`leaklab.verdict.procedencia`). Reimplementar a regra
aqui seria a segunda porta, o defeito mais recorrente deste projeto.
"""
import argparse
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                            # noqa: E402
from leaklab import verdict as _verdict                         # noqa: E402


def deriva(d):
    """(verdict_source, verdict_has_cost) para uma linha gravada."""
    fonte = (d.get('ev_loss_source') or '').lower()
    tem_gabarito = bool(d.get('gto_label')) or d.get('ev_loss_bb') is not None
    src = _verdict.procedencia(
        {'available': tem_gabarito, 'ev_loss_source': fonte} if tem_gabarito else None,
        None,
        d.get('street'))
    custo = _verdict.tem_custo_medido(
        {'available': True, 'ev_loss_bb': d.get('ev_loss_bb'), 'ev_loss_source': fonte}, None)
    return src, custo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    conn = get_conn()
    linhas = [dict(r) for r in conn.execute(
        'SELECT id, street, gto_label, ev_loss_bb, ev_loss_source, verdict_source '
        'FROM decisions').fetchall()]

    ja_tem = [d for d in linhas if d.get('verdict_source')]
    alvo = [d for d in linhas if not d.get('verdict_source')]

    dist = Counter()
    for d in alvo:
        src, custo = deriva(d)
        dist['%s / custo=%s' % (src, custo)] += 1

    print('decisoes no acervo: %d' % len(linhas))
    print('  ja com procedencia gravada: %d' % len(ja_tem))
    print('  a preencher:                %d' % len(alvo))
    print('\ncomo ficariam:')
    for k, n in dist.most_common():
        print('   %-22s %5d  (%.1f%%)' % (k, n, 100.0 * n / max(1, len(alvo))))

    # CONTROLE: nenhuma pode sair vazia -- campo "as vezes preenchido" e pior que inexistente
    vazias = sum(1 for d in alvo if not deriva(d)[0])
    print('\nsairiam VAZIAS: %d  (tem que ser 0)' % vazias)
    if vazias:
        sys.exit('derivacao produziu procedencia vazia — nao aplicar')

    if args.apply:
        for d in alvo:
            src, custo = deriva(d)
            conn.execute('UPDATE decisions SET verdict_source=?, verdict_has_cost=? WHERE id=?',
                         # BOOLEANO: no PG a coluna e BOOLEAN e int estoura DatatypeMismatch
                         (src, bool(custo), d['id']))
        conn.commit()
        # conferencia explicita: releitura, no ESCOPO que a operacao prometeu mexer
        resto = sum(1 for r in conn.execute(
            'SELECT id FROM decisions WHERE verdict_source IS NULL'))
        print('\n[APLICADO] %d linhas escritas. Sem procedencia depois: %d (esperado 0)'
              % (len(alvo), resto))
    else:
        print('\n[DRY-RUN] nada foi escrito')


if __name__ == '__main__':
    main()
