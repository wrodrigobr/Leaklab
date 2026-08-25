# -*- coding: utf-8 -*-
"""Quantas decisoes do acervo um CONSTRUTOR de veredito recusaria hoje?

    python scripts/medir_veredito_construivel.py

Nao grava nada. Responde a pergunta que o dono fez: "o que precisamos para garantir que o
veredito seja confiavel?" -- o primeiro passo e saber quanto do que ja esta gravado passaria
por um portao que recusa incoerencia na ESCRITA, em vez de um cron que a descobre depois.

As regras abaixo sao candidatas a pre-condicao de gravacao. Cada uma corresponde a um defeito
REAL medido em 24/08, nao a uma preferencia de estilo.

CONTROLE (regra 1 do CLAUDE.md): imprime, para cada regra, quantas decisoes ela AVALIA. Regra
com denominador zero nao esta olhando nada, e seu "0 violacoes" nao vale.
"""
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                            # noqa: E402

_BANDA = {'standard': (0.0, 0.08), 'marginal': (0.09, 0.18),
          'small_mistake': (0.19, 0.35), 'clear_mistake': (0.36, 1.0)}
_ACUSA = ('small_mistake', 'clear_mistake')
_CARTA_REPROVA = ('gto_critical', 'gto_minor_deviation')


def regras(d):
    """(violacoes, avaliadas) para UMA decisao. Cada item: (nome, violou?, avaliou?)."""
    lab = d.get('label')
    sc = d.get('score')
    ev = d.get('ev_loss_bb')
    gl = d.get('gto_label')
    st = (d.get('street') or '').lower()
    out = []

    # R1 score na banda do label
    if lab in _BANDA and sc is not None:
        lo, hi = _BANDA[lab]
        out.append(('R1 score fora da banda do label', not (lo - 1e-9 <= float(sc) <= hi + 1e-9), True))
    else:
        out.append(('R1 score fora da banda do label', False, False))

    # R2 PROCEDENCIA: toda decisao declara de onde veio o veredito
    tem_proc = bool(gl) or (ev is not None) or (d.get('ev_loss_source') or '')
    out.append(('R2 sem procedencia declarada', not tem_proc, True))

    # R3 acusacao com a carta reprovando precisa do CUSTO em bb
    if lab in _ACUSA and gl in _CARTA_REPROVA:
        out.append(('R3 acusacao GTO sem custo em bb', ev is None, True))
    else:
        out.append(('R3 acusacao GTO sem custo em bb', False, False))

    # R4 acusacao sem NENHUMA base (custo, carta ou desvio)
    if lab in _ACUSA:
        base = (ev is not None and float(ev or 0) > 0) or (gl in _CARTA_REPROVA) \
               or (sc is not None and float(sc or 0) > 0)
        out.append(('R4 acusacao sem base nenhuma', not base, True))
    else:
        out.append(('R4 acusacao sem base nenhuma', False, False))

    # R5 postflop tem pote >= 1bb (depois do preflop o pote tem, no minimo, os blinds)
    if st in ('flop', 'turn', 'river'):
        p = d.get('pot_at_decision_bb')
        if p is None:
            p = d.get('pot_size')
        out.append(('R5 postflop com pote < 1bb', p is None or float(p or 0) < 1.0, True))
    else:
        out.append(('R5 postflop com pote < 1bb', False, False))

    # R6 erro cuja "melhor jogada" e a que o jogador fez
    if lab in _ACUSA and d.get('best_action') and d.get('action_taken'):
        a = str(d['action_taken']).lower().rstrip('s')
        b = str(d['best_action']).lower().rstrip('s')
        out.append(('R6 erro com best_action == acao jogada', a == b, True))
    else:
        out.append(('R6 erro com best_action == acao jogada', False, False))

    # R7 backdoor no turn/river e impossivel (backdoor exige DUAS cartas por vir)
    dp = (d.get('draw_profile') or '').upper()
    if st in ('turn', 'river') and dp:
        out.append(('R7 backdoor no turn/river', 'BD' in dp, True))
    else:
        out.append(('R7 backdoor no turn/river', False, False))

    return out


def main():
    conn = get_conn()
    linhas = [dict(r) for r in conn.execute(
        'SELECT id, label, score, ev_loss_bb, ev_loss_source, gto_label, street, '
        '       action_taken, best_action, draw_profile, pot_size, pot_at_decision_bb '
        'FROM decisions').fetchall()]

    viol = Counter()
    aval = Counter()
    recusadas = 0
    for d in linhas:
        ruim = False
        for nome, v, a in regras(d):
            if a:
                aval[nome] += 1
            if v:
                viol[nome] += 1
                ruim = True
        recusadas += ruim

    print('decisoes no acervo: %d' % len(linhas))
    print('RECUSADAS pelo construtor: %d  (%.1f%%)'
          % (recusadas, 100.0 * recusadas / max(1, len(linhas))))
    print('PASSAM: %d  (%.1f%%)'
          % (len(linhas) - recusadas, 100.0 * (len(linhas) - recusadas) / max(1, len(linhas))))
    print('\npor regra (violacoes / avaliadas):')
    for nome in sorted(aval, key=lambda k: -viol[k]):
        n, a = viol[nome], aval[nome]
        marca = '  <- denominador ZERO: a regra nao esta olhando nada' if a == 0 else ''
        print('   %-38s %5d / %5d  (%.1f%%)%s'
              % (nome, n, a, 100.0 * n / max(1, a), marca))


if __name__ == '__main__':
    main()
