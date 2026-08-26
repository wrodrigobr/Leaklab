# -*- coding: utf-8 -*-
"""Re-grada as decisoes PREFLOP do acervo NO LUGAR, sem apagar nada.

    python scripts/regrade_preflop_no_lugar.py --dry-run
    python scripts/regrade_preflop_no_lugar.py --apply

── Por que nao usar o reprocesso normal ───────────────────────────────────────────────────

O reprocesso de torneio e DELETE + INSERT. As tabelas que referenciam `decisions(id)` tem
`ON DELETE CASCADE`, entao ele leva junto o que estava pendurado -- foi assim que **71 anotacoes
de coach sumiram em producao**, caladas ([[project_cascade_apagava_anotacoes]]). Para uma mudanca
que so mexe no VEREDITO preflop, apagar a linha e desproporcional.

── Por que nao usar `_regrade_tournament` ─────────────────────────────────────────────────

Ele existe, e UPDATE no lugar e a estrutura dele e boa -- mas escreve **4 colunas**
(`label`, `best_action`, `gto_label`, `gto_action`). A invariante de v0.168 e que **quem muda o
veredito carrega recomendacao e score junto** ([[project_fechamento_v0_168]]): deixar `score` e
`note` descrevendo o veredito ANTERIOR e a contradicao que a familia
[[project_contradicoes_veredito_x_grade]] fechou. Este script escreve a tupla inteira do veredito.

── A seguranca contra escrita errada ──────────────────────────────────────────────────────

Copiada de `_regrade_tournament`, porque a razao dela e real: casar por `(hand_id, acao)` e
ambiguo em mao com duas decisoes preflop da mesma acao (hero enfrenta CO e depois SB). Entao o
casamento e por ORDEM dentro da mao, e so vale quando a lista fresca e a gravada tem o MESMO
tamanho E as acoes alinham posicao a posicao. Qualquer desalinhamento **pula a mao inteira** --
melhor nao regradar do que gravar o veredito de uma decisao em cima de outra.
"""
import argparse
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                                      # noqa: E402
from leaklab.parser import parse_hand_history                             # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand               # noqa: E402
from leaklab.decision_engine_v11 import evaluate_decision                 # noqa: E402
# A MESMA funcao que o INSERT usa para gravar o score. Reimplementar a regra aqui era o defeito:
# a primeira versao deste script lia `evaluation.score` (chave que nao existe) e devolvia None em
# 7.107 de 7.107 -- teria ZERADO o score do acervo inteiro. Numero absurdo e sinal.
from database.repositories import _align_score_to_label                   # noqa: E402

_COLUNAS = ('label', 'best_action', 'score', 'note', 'gto_label', 'gto_action',
            'verdict_source', 'verdict_has_cost')


def _fresco(r):
    """A tupla de veredito que o motor DE HOJE produz para esta decisao."""
    ev = r.get('evaluation') or {}
    g = r.get('gto') or {}
    return {
        'label': ev.get('label') or None,
        'best_action': r.get('bestAction') or None,
        'score': _align_score_to_label(ev.get('label', ''), ev.get('mistakeScore', 0),
                                       (r.get('gto') or {}).get('ev_loss_bb')),
        # `note` e prosa, e o texto gravado no upload nem sempre e reproduzido por
        # `evaluate_decision` (o /replay enriquece na LEITURA). Entao ela so e reescrita quando o
        # motor produz uma: apagar a explicacao de 384 decisoes seria dano que o bug nao causava.
        'note': r.get('note') or None,
        'gto_label': g.get('gto_label') or None,
        'gto_action': g.get('gto_action') or None,
        'verdict_source': r.get('verdictSource') or None,
        # BOOLEAN no Postgres: `1 if ... else 0` quebra TODO upload com a suite verde
        # ([[project_procedencia_do_veredito]]). Tem que ser bool de verdade.
        'verdict_has_cost': bool(r.get('verdictHasCost')),
    }


def _difere(c, fresco, gravado):
    a, b = fresco[c], gravado.get(c)
    if c == 'note' and not a:
        return False                    # nota vazia nao substitui nota escrita
    if c == 'score':
        if a is None and b is None:
            return False
        return a is None or b is None or abs(float(a) - float(b)) > 1e-6
    if c == 'verdict_has_cost':
        return bool(a) != bool(b)
    return (a or None) != (b or None)


def _igual(fresco, gravado):
    return not any(_difere(c, fresco, gravado) for c in _COLUNAS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limite-exemplos', type=int, default=25)
    # A regra de severidade sem custo NAO e preflop: 38 dos 47 `clear_mistake` sem custo medidos
    # em 26/08 estao no flop, turn e river. O filtro nasceu preflop porque a carta rasa era
    # preflop; deixa-lo assim teria consertado 9 de 47 e chamado de pronto.
    ap.add_argument('--streets', default='preflop',
                    help="'preflop' (padrao) ou 'todas'")
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        sys.exit('escolha --dry-run ou --apply')

    _so_preflop = (args.streets or 'preflop').lower() != 'todas'

    conn = get_conn()
    torneios = [dict(r)['id'] for r in
                conn.execute('SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id')]

    cont = Counter()
    exemplos = []
    amostra = {}
    perdeu_carta = []
    for tid in torneios:
        row = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        if not row:
            continue
        try:
            maos = parse_hand_history(dict(row)['raw_text'])
        except Exception:                                                 # noqa: BLE001
            cont['torneio_ilegivel'] += 1
            continue

        frescas = {}
        for h in maos:
            try:
                entradas = build_decision_inputs_for_hand(h)
            except Exception:                                             # noqa: BLE001
                continue
            for di in entradas:
                if _so_preflop and (di.get('street') or '').lower() != 'preflop':
                    continue
                hid, act = di.get('hand_id', ''), (di.get('player_action') or '').lower()
                if not hid or not act:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:                                         # noqa: BLE001
                    continue
                d = _fresco(r)
                d['act'] = act
                frescas.setdefault(hid, []).append(d)

        gravadas = {}
        for r in conn.execute(
                "SELECT id, hand_id, action_taken, street, %s, "
                "COALESCE(effective_stack_bb, stack_bb) AS stack "
                "FROM decisions WHERE tournament_id=? %s ORDER BY id"
                % (', '.join(_COLUNAS),
                   "AND lower(street)='preflop'" if _so_preflop else ''), (tid,)).fetchall():
            d = dict(r)
            gravadas.setdefault(d['hand_id'], []).append(d)

        for hid, linhas in gravadas.items():
            novas = frescas.get(hid, [])
            if len(novas) != len(linhas):
                cont['mao_pulada_tamanho'] += 1
                continue
            if any((g['action_taken'] or '').lower() != f['act'] for g, f in zip(linhas, novas)):
                cont['mao_pulada_desalinhada'] += 1
                continue
            for g, f in zip(linhas, novas):
                cont['conferidas'] += 1
                if _igual(f, g):
                    continue
                cont['mudam'] += 1
                # QUAL coluna difere: sem isso, "7.107 de 7.107 mudam" nao distingue
                # "o motor mudou tudo" de "o comparador esta errado numa coluna so"
                for _c in _COLUNAS:
                    if _difere(_c, f, g):
                        cont['col_' + _c] += 1
                        if cont['col_' + _c] <= 2:
                            amostra.setdefault(_c, []).append(
                                '#%s gravado=%r fresco=%r' % (g['id'], g.get(_c), f[_c]))
                # perder procedencia e REGRESSAO: nomeia cada uma, com stack, em vez de contar
                if _c == 'verdict_source' and g.get('verdict_source') == 'carta'                         and f['verdict_source'] != 'carta':
                    perdeu_carta.append('#%-7s %6.1fbb  carta -> %-6s  label %s -> %s'
                                        % (g['id'], float(g['stack'] or 0),
                                           f['verdict_source'], g['label'], f['label']))
                if (g.get('label') in ('small_mistake', 'clear_mistake')) != \
                   (f['label'] in ('small_mistake', 'clear_mistake')):
                    cont['acusacao_entra' if f['label'] in ('small_mistake', 'clear_mistake')
                         else 'acusacao_sai'] += 1
                if len(exemplos) < args.limite_exemplos:
                    exemplos.append('#%-7s %5.1fbb  %-13s -> %-13s | best %-6s -> %-6s'
                                    % (g['id'], float(g['stack'] or 0), g['label'], f['label'],
                                       g['best_action'], f['best_action']))
                if args.apply:
                    conn.execute(
                        'UPDATE decisions SET %s WHERE id=?'
                        % ', '.join('%s=?' % c for c in _COLUNAS),
                        tuple((g.get(c) if c == 'note' and not f[c] else f[c])
                              for c in _COLUNAS) + (g['id'],))
        if args.apply:
            conn.commit()

    conn.close()
    print('torneios: %d' % len(torneios))
    print('decisoes conferidas (%s): %d' % (args.streets, cont['conferidas']))
    print('  MUDAM: %d' % cont['mudam'])
    print('    acusacoes que ENTRAM: %d' % cont['acusacao_entra'])
    print('    acusacoes que SAEM:   %d' % cont['acusacao_sai'])
    print('  maos puladas por tamanho diferente:  %d' % cont['mao_pulada_tamanho'])
    print('  maos puladas por acao desalinhada:   %d' % cont['mao_pulada_desalinhada'])
    if cont['torneio_ilegivel']:
        print('  torneios ilegiveis: %d' % cont['torneio_ilegivel'])
    print('')
    print('colunas que diferem (de %d que mudam):' % cont['mudam'])
    for c in _COLUNAS:
        if cont['col_' + c]:
            print('  %-18s %6d' % (c, cont['col_' + c]))
            for a in amostra.get(c, [])[:2]:
                print('      ' + a[:170])
    if exemplos:
        print('\nexemplos:')
        for e in exemplos:
            print('   ' + e)
    if not args.apply:
        print('\n[DRY-RUN] nada foi gravado')


if __name__ == '__main__':
    main()
