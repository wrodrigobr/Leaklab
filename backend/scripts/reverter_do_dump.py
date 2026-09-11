# -*- coding: utf-8 -*-
"""Desfaz um reparo do `resync_postflop_gto.py --dump`, linha por linha, a partir do arquivo.

Por que existe: o reparo das divergencias reescreve 7 campos em milhares de decisoes de gente
pagante. O dump guarda o ANTES de cada linha; sem uma ferramenta que o use, "da para reverter"
seria promessa, nao capacidade. Escrita em massa sem volta pronta nao se faz.

**A guarda que decide se isto e seguro:** so reverte a linha cujo estado ATUAL e exatamente o
`para` do dump. Se o valor de hoje nao e o que o reparo gravou, alguem mais escreveu ali (novo
solve, reconcile, reanalise do admin), e gravar o `de` por cima apagaria uma escrita mais nova —
o conserto causando dano que o bug nao causava. Essas linhas saem no relatorio como
`mudou_depois`, e a decisao volta a ser humana.

Uso:
    python scripts/reverter_do_dump.py ARQUIVO.jsonl                 # dry-run
    python scripts/reverter_do_dump.py ARQUIVO.jsonl --user 40       # so um usuario
    python scripts/reverter_do_dump.py ARQUIVO.jsonl --user 40 --apply
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt                                      # noqa: E402

#: Os 7 campos que o reparo reescreve, na ordem (coluna no banco, chave no dump).
CAMPOS = (
    ('label', 'label'),
    ('best_action', 'best'),
    ('gto_label', 'gto_label'),
    ('gto_action', 'gto_action'),
    ('gto_played_freq', 'played'),
    ('gto_top_freq', 'top'),
    ('ev_loss_bb', 'ev'),
    ('ev_loss_source', 'ev_src'),
)


def _n(v):
    """'' e None sao a MESMA ausencia, e numero em texto e o mesmo numero.

    O dump sai com `default=str`, entao Decimal do Postgres viaja como '1.4' e a comparacao
    ingenua com 1.4 diria que a linha mudou quando ela esta intacta — e uma revisao inteira
    cairia em `mudou_depois` sem nada ter acontecido.
    """
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    s = str(v)
    try:
        return round(float(s), 4)
    except ValueError:
        return s


def estado_igual(atual: dict, esperado: dict) -> bool:
    """A linha de hoje e exatamente o que o reparo gravou?

    Comparacao pelos 8 campos que o reparo escreve. Qualquer diferenca significa escrita de
    terceiro depois do reparo, e a reversao nao pode passar por cima dela.
    """
    for col, chave in CAMPOS:
        if _n(atual.get(col)) != _n(esperado.get(chave)):
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arquivo')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--user', type=int, default=None, help='reverte so as linhas deste usuario')
    ap.add_argument('--tid', type=int, default=None, help='reverte so as linhas deste torneio')
    args = ap.parse_args()

    linhas = []
    for l in io.open(args.arquivo, encoding='utf-8'):
        if not l.strip():
            continue
        x = json.loads(l)
        if args.user is not None and x.get('user_id') != args.user:
            continue
        if args.tid is not None and x.get('tid') != args.tid:
            continue
        linhas.append(x)
    print('linhas no recorte: %d' % len(linhas))
    if not linhas:
        return

    conn = get_conn()
    por_id = {x['id']: x for x in linhas}
    achadas = {}
    ids = list(por_id)
    LOTE = 500
    for i in range(0, len(ids), LOTE):
        pedaco = ids[i:i + LOTE]
        # `?` + `_adapt`: o mesmo caminho de placeholder do resto do projeto, para o script
        # rodar igual no Postgres de producao e no SQLite de teste.
        marcas = ','.join(['?'] * len(pedaco))
        for r in conn.execute(_adapt(
                "SELECT id, label, best_action, gto_label, gto_action, gto_played_freq, "
                "gto_top_freq, ev_loss_bb, ev_loss_source FROM decisions WHERE id IN (%s)"
                % marcas), tuple(pedaco)).fetchall():
            d = dict(r)
            achadas[d['id']] = d

    revertidas = intactas = mudou_depois = sumiu = 0
    exemplos = []
    for did, x in por_id.items():
        atual = achadas.get(did)
        if atual is None:
            sumiu += 1
            continue
        if estado_igual(atual, x['de']):
            intactas += 1                     # ja esta no estado antigo: nada a fazer
            continue
        if not estado_igual(atual, x['para']):
            mudou_depois += 1
            if len(exemplos) < 10:
                exemplos.append('  id %s: hoje label=%s gto=%s, o reparo gravou label=%s gto=%s'
                                % (did, atual['label'], atual['gto_label'],
                                   x['para']['label'], x['para']['gto_label']))
            continue
        if args.apply:
            # O `score` viaja JUNTO quando a linha o carrega (as do `reconcile`, que o
            # re-deriva do label). Devolver o rotulo antigo com a nota nova produziria a
            # linha-quimera de 12/08: veredito de uma avaliacao e numero de outra.
            if 'score' in (x['de'] or {}):
                conn.execute(_adapt(
                    "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=?, "
                    "gto_played_freq=?, gto_top_freq=?, ev_loss_bb=?, ev_loss_source=?, score=? "
                    "WHERE id=?"),
                    (x['de']['label'], x['de']['best'], x['de']['gto_label'],
                     x['de']['gto_action'], x['de']['played'], x['de']['top'], x['de']['ev'],
                     x['de']['ev_src'], x['de']['score'], did))
            else:
                conn.execute(_adapt(
                    "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=?, "
                    "gto_played_freq=?, gto_top_freq=?, ev_loss_bb=?, ev_loss_source=? "
                    "WHERE id=?"),
                    (x['de']['label'], x['de']['best'], x['de']['gto_label'],
                     x['de']['gto_action'], x['de']['played'], x['de']['top'], x['de']['ev'],
                     x['de']['ev_src'], did))
        revertidas += 1
    if args.apply:
        conn.commit()
    conn.close()

    print('revertidas      : %d' % revertidas)
    print('ja no estado antigo: %d' % intactas)
    print('MUDOU DEPOIS    : %d  (nao tocadas: alguem escreveu ali depois do reparo)' % mudou_depois)
    print('nao existem mais: %d' % sumiu)
    if exemplos:
        print('\n'.join(exemplos))
    print('\n%s' % ('APLICADO' if args.apply else 'DRY-RUN (use --apply)'))


if __name__ == '__main__':
    main()
