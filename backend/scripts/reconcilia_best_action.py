#!/usr/bin/env python
"""Reconcilia `best_action` congelado — AUTO **e** GRAFIA, pela mesma raiz.

── O que originou (04/09/2026) ───────────────────────────────────────────────────────────

Quando o solver termina de resolver um spot, `gto_action` e `label` sao reconciliados e o
`best_action` ficava parado no valor anterior. O card entao mostra "voce fez X, o ideal era
X" (AUTO) ou "voce deu shove, o ideal era jam" (GRAFIA) — a mesma jogada com outra palavra.

A propria varredura declara que GRAFIA **sobrepoe** AUTO: "uma acusacao ortografica e, por
definicao, uma auto-acusacao". Sao a mesma familia vista por duas lentes.

── O buraco que este script fecha ────────────────────────────────────────────────────────

A remediacao de 04/09 de manha selecionava torneios com comparacao LITERAL:

    LOWER(TRIM(best_action)) = LOWER(TRIM(action_taken))

Isso acha `bet`/`bet` e **nao acha `shove`/`jam`**. O `reconcile_tournament_labels` em si
normaliza certo; foi a consulta de SELECAO que nao. Resultado: zerei AUTO (78 -> 0) e deixei
GRAFIA viva (0 -> 1), que e o mesmo defeito com outra grafia.

Aqui a selecao usa `_norm_gto_action`, a MESMA normalizacao que a invariante usa para medir.
Regra 5: a regra vive num lugar so.

Rodar com --aplicar para gravar; sem isso e dry-run.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from database.schema import get_conn                      # noqa: E402
from database.repositories import (                        # noqa: E402
    _fetchall, reconcile_tournament_labels,
)
# A normalizacao mora no MOTOR, e e a mesma que as invariantes AUTO e GRAFIA usam para medir.
# Reimplementar aqui seria a 2a definicao da mesma regra — o defeito que a regra 5 do
# CLAUDE.md existe para impedir, e que ja custou 5 ocorrencias medidas neste projeto.
from leaklab.decision_engine_v11 import _norm_gto_action    # noqa: E402

# O criterio e a UNIAO EXATA do que as duas invariantes acusam. Nada alem disso.
#
# O 1o dry-run deste script achou 259 linhas em vez de 68, porque eu tinha usado
# `label <> 'standard'` — que inclui `marginal`. As 191 linhas `marginal` a mais NAO sao
# violacao de invariante nenhuma, e o script ia reescreve-las em 6 usuarios alem do dono do
# caso. Conserto que mexe no que nao estava quebrado e o dano que a regra 7 do CLAUDE.md
# existe para impedir; o dry-run foi o que segurou.
#
#   AUTO   (leaklab/invariantes_acervo._acusa_o_que_recomenda):
#            label IN ('small_mistake','clear_mistake','critical')  AND  norm(best) == norm(acao)
#   GRAFIA (leaklab/invariantes_acervo._punido_pela_grafia):
#            label <> 'standard'  AND  best <> acao (LITERAL)  AND  norm(best) == norm(acao)
#
# GRAFIA sobrepoe AUTO: e a mesma familia, vista pela lente da grafia.
_LABELS_ACUSADORES = ('small_mistake', 'clear_mistake', 'critical')

SQL_CANDIDATAS = """
    SELECT d.id, d.tournament_id, d.action_taken, d.best_action, d.gto_action,
           d.label, d.score, t.user_id, u.username
      FROM decisions d
      JOIN tournaments t ON t.id = d.tournament_id
      JOIN users u ON u.id = t.user_id
     WHERE d.label <> 'standard'
       AND d.best_action IS NOT NULL
       AND d.action_taken IS NOT NULL
"""


def _afetadas(conn):
    """So o que AUTO ou GRAFIA acusam de verdade."""
    fora = []
    for r in _fetchall(conn, SQL_CANDIDATAS):
        if _norm_gto_action(r['best_action']) != _norm_gto_action(r['action_taken']):
            continue
        eh_auto = (r['label'] or '') in _LABELS_ACUSADORES
        eh_grafia = ((r['action_taken'] or '').strip().lower()
                     != (r['best_action'] or '').strip().lower())
        if eh_auto or eh_grafia:
            r['_lente'] = 'AUTO' if eh_auto else 'GRAFIA'
            fora.append(r)
    return fora


def principal():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--aplicar', action='store_true', help='grava (sem isso e dry-run)')
    args = ap.parse_args()

    conn = get_conn()
    antes = _afetadas(conn)
    print('ANTES: %d linhas com best_action == acao jogada (normalizado)' % len(antes))

    por_lente = {}
    for r in antes:
        por_lente[r['_lente']] = por_lente.get(r['_lente'], 0) + 1
    for lente, n in sorted(por_lente.items()):
        print('  lente %-7s %s' % (lente, n))

    por_user = {}
    for r in antes:
        por_user[r['username']] = por_user.get(r['username'], 0) + 1
    for u, n in sorted(por_user.items(), key=lambda x: -x[1]):
        print('    %-24s %s' % (u, n))

    for r in antes[:6]:
        print('    id=%-8s %-6s vs %-6s  gto=%-6s %s' % (
            r['id'], r['action_taken'], r['best_action'], r['gto_action'], r['label']))

    tids = sorted({r['tournament_id'] for r in antes})
    print('\ntorneios a reconciliar: %d' % len(tids))

    if not args.aplicar:
        print('\nDRY-RUN. Nada foi gravado. Rode com --aplicar.')
        conn.close()
        return 0

    print('\n=== aplicando ===')
    total = 0
    for tid in tids:
        try:
            total += reconcile_tournament_labels(tid) or 0
        except Exception as e:
            print('  ERRO no torneio %s: %s' % (tid, e))

    conn2 = get_conn()
    depois = _afetadas(conn2)
    conn2.close()
    print('  reconcile mexeu em %d linhas' % total)
    print('DEPOIS: %d  (antes %d)' % (len(depois), len(antes)))
    for r in depois[:5]:
        print('    RESTOU id=%-8s %-6s vs %-6s gto=%-6s %s' % (
            r['id'], r['action_taken'], r['best_action'], r['gto_action'], r['label']))
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(principal())
