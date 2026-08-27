# -*- coding: utf-8 -*-
"""Se a equity de flop/turn passar a ser contra a RANGE DE CONTINUACAO, o que muda no veredito?

    python scripts/medir_equity_vs_range_postflop.py --limite 40     # piloto
    python scripts/medir_equity_vs_range_postflop.py                 # acervo inteiro

Hoje 100% das decisoes de flop e turn usam equity contra mao ALEATORIA. Contra quem aposta, esse
numero e inflado por construcao -- e a direcao do erro nao e simetrica: equity inflada CONDENA
quem folda e ABSOLVE quem paga. Baixar a equity anda no sentido oposto nas duas.

Por isso a medicao conta os dois sentidos separados. O conserto analogo no RIVER (24/08) deixou
registrado o risco exato: contra `vs_random` puro ele CRIARIA acusacoes (4 vereditos mudam, 2
deles standard -> small_mistake); contra a range de continuacao mudou ZERO. Aqui a pergunta e a
mesma, e a resposta so vale medida.

CONTROLES, porque zero sem controle nao significa nada:
  * quantas equities de fato MUDARAM (se for zero, o medidor nao esta medindo)
  * a amplitude media da mudanca
  * quantas decisoes o calculo RECUSOU (sem board, sem cartas, sem combos)
"""
import argparse
import sys
from collections import Counter

sys.path.insert(0, '/app')

from database.schema import get_conn                                      # noqa: E402
from leaklab.parser import parse_hand_history                             # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand               # noqa: E402
from leaklab.decision_engine_v11 import evaluate_decision                 # noqa: E402
from leaklab.multiway_advisor import _equity_vs_field, semente_estavel    # noqa: E402

_ACUSA = ('small_mistake', 'clear_mistake')
N_SIMS = 3000


def _nova_equity(hero_cards, board):
    hs = ''.join(str(c) for c in (hero_cards or []))[:4].replace(' ', '')
    b = [str(c) for c in (board or []) if c]
    if len(hs) != 4 or len(b) not in (3, 4):
        return None
    try:
        return _equity_vs_field(hs, b, 1, N_SIMS, semente_estavel(hs, tuple(b), 1))
    except Exception:                                                     # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=0)
    args = ap.parse_args()

    conn = get_conn()
    tids = [dict(r)['id'] for r in conn.execute(
        'SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id')]

    c = Counter()
    mudancas = []
    entram = []
    deltas = []
    for tid in tids:
        row = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
        if not row:
            continue
        try:
            maos = parse_hand_history(dict(row)['raw_text'])
        except Exception:                                                 # noqa: BLE001
            continue
        for h in maos:
            try:
                entradas = build_decision_inputs_for_hand(h)
            except Exception:                                             # noqa: BLE001
                continue
            for di in entradas:
                if (di.get('street') or '').lower() not in ('flop', 'turn'):
                    continue
                mt = di.get('math') or {}
                if mt.get('equitySource') != 'vs_random':
                    c['ja era vs_range'] += 1
                    continue
                c['alvo (flop/turn vs_random)'] += 1
                if args.limite and c['alvo (flop/turn vs_random)'] > args.limite:
                    conn.close()
                    return _imprime(c, mudancas, deltas, entram)

                board = (di.get('spot') or {}).get('board') or di.get('board')
                hero = (di.get('hand_profile') or {}).get('cards') or di.get('hero_cards')
                nova = _nova_equity(hero, board)
                if nova is None:
                    c['  calculo RECUSOU'] += 1
                    continue
                velha = float(mt.get('estimatedHandEquity') or 0)
                if abs(nova - velha) < 1e-6:
                    c['  equity IDENTICA'] += 1
                else:
                    c['  equity mudou'] += 1
                    deltas.append(nova - velha)

                try:
                    r1 = evaluate_decision(di)
                except Exception:                                         # noqa: BLE001
                    c['  erro no motor (antes)'] += 1
                    continue
                _di = dict(di)
                _m = dict(mt)
                _m['estimatedHandEquity'] = nova
                _m['equitySource'] = 'vs_range'
                _di['math'] = _m
                try:
                    r2 = evaluate_decision(_di)
                except Exception:                                         # noqa: BLE001
                    c['  erro no motor (depois)'] += 1
                    continue

                l1 = (r1.get('evaluation') or {}).get('label')
                l2 = (r2.get('evaluation') or {}).get('label')
                if l1 == l2:
                    c['veredito IGUAL'] += 1
                    continue
                a1, a2 = l1 in _ACUSA, l2 in _ACUSA
                if a1 and not a2:
                    c['ACUSACAO SAI'] += 1
                elif a2 and not a1:
                    c['ACUSACAO ENTRA'] += 1
                else:
                    c['muda de grau (sem trocar de lado)'] += 1
                if a2 and not a1:
                    # As acusacoes que ENTRAM sao as unicas que podem causar dano que o bug nao
                    # causava (regra 7). Sao poucas: saem inteiras, para conferencia a mao.
                    sp = di.get('spot') or {}
                    mt2 = di.get('math') or {}
                    entram.append(
                        '%-5s %-6s %-9s board=%-17s fez %-5s | eq %.3f -> %.3f | preco %.3f | '
                        '%s -> %s'
                        % (di.get('street'), _mao(di), sp.get('position'),
                           ','.join(str(c) for c in (sp.get('board') or [])),
                           di.get('player_action'), velha, nova,
                           float(mt2.get('potOddsEquity') or 0), l1, l2))
                if len(mudancas) < 25:
                    mudancas.append('%-5s fez %-6s eq %.3f -> %.3f | %-14s -> %-14s'
                                    % (di.get('street'), di.get('player_action'),
                                       velha, nova, l1, l2))
    conn.close()
    return _imprime(c, mudancas, deltas, entram)


def _mao(di):
    hp = di.get('hand_profile') or {}
    return ''.join(str(x) for x in (hp.get('cards') or di.get('hero_cards') or []))[:5]


def _imprime(c, mudancas, deltas, entram=()):
    print('%-42s %s' % ('medida', 'n'))
    for k, v in c.most_common():
        print('%-42s %d' % (k[:42], v))
    print()
    if deltas:
        print('amplitude da mudanca de equity: media %+.3f | min %+.3f | max %+.3f'
              % (sum(deltas) / len(deltas), min(deltas), max(deltas)))
    if not c['  equity mudou']:
        print('CONTROLE FALHOU: nenhuma equity mudou -- o medidor nao esta medindo nada.')
    if entram:
        print('')
        print('AS QUE ENTRAM (as unicas que podem causar dano novo) -- %d:' % len(entram))
        for e in entram:
            print('   ' + e)
    if mudancas:
        print('\nvereditos que mudam:')
        for m in mudancas:
            print('   ' + m)
    return 0


if __name__ == '__main__':
    sys.exit(main())
