"""medir_pote_reconstruido.py — mede o quanto o `pot_size` que o motor usa erra, e prova
que a reconstrucao por jogador acerta.

READ-ONLY. Nao toca no banco. Le os hand histories passados na linha de comando (ou os
que estiverem em backend/*.txt e backend/data/*.txt):

    cd backend && python scripts/medir_pote_reconstruido.py [arquivo.txt ...]

## Por que existe

`_pot_up_to` (leaklab/hand_state_builder.py) soma o `amount` cru de cada acao. Isso erra
duas vezes ao mesmo tempo:

  1. perde os blinds, que nao chegam como acao do parser;
  2. conta o INCREMENTO do raise ('raises 120 to 240' -> 120) em vez do total do jogador.

O numero resultante vai para `state.pot_size`, que e o denominador das pot odds em
`street_math_engine.build_math_snapshot`. Medido em 2026-08-04 sobre 1.682 maos locais:

    _pot_up_to (o que o motor usa hoje) .......   1,2% de acerto
    reconstrucao por jogador (aqui) ...........  99,6% de acerto

## O oraculo

A propria mao declara o pote final: a linha `Total pot X` do SUMMARY. Somamos o que cada
jogador pos em cada street, descontamos a aposta devolvida (`Uncalled bet (X) returned`
no PS/GG, `Jogador: RETURN X` no CoinPoker) e comparamos. E medicao contra o texto do
site, nao contra outra funcao nossa.

## O que NAO foi feito, e por que

Trocar o pote no motor esta pendente de proposito. A tolerancia do veredito foi calibrada
em cima da equity exigida inflada por este erro; so corrigir o pote produziu 13 acusacoes
NOVAS contra fold em 2.158 decisoes, e duas delas sao falsas — vem do estimador heuristico
de equity, que le o par do BOARD como par do hero (76o em Q-3-3 avaliado em 44%). O pote
certo nao cria esse defeito, ele o EXPOE. Consertar o pote exige recalibrar junto.
"""
import sys, os, glob, re

_here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
for _cand in (os.path.join(_here, '..'), _here, os.getcwd(), '/app/backend', '/app'):
    if os.path.isdir(os.path.join(_cand, 'leaklab')):
        sys.path.insert(0, os.path.abspath(_cand))
        BACKEND = os.path.abspath(_cand)
        break

from leaklab.parser import parse_hand_history                      # noqa: E402
from leaklab.models import ParsedHand, ParsedAction                # noqa: E402
from leaklab.hand_state_builder import _pot_up_to, _committed_on_street  # noqa: E402

TOTAL_RE = re.compile(r'Total pot\s+([\d.,]+)', re.IGNORECASE)
# PS/GG: "Uncalled bet (240) returned to X" | CoinPoker: "Hero: RETURN 38,370"
DEVOLVIDO_RE = re.compile(r'Uncalled bet \(?\s*([\d.,]+)\s*\)?\s*returned'
                          r'|^.+?:\s*RETURN\s+([\d.,]+)', re.IGNORECASE | re.MULTILINE)


def _num(s: str) -> float:
    return float(s.replace(',', ''))


def pot_at_decision(hand: ParsedHand, actions, upto_index: int, street: str) -> float:
    """Tudo que esta NO MEIO no ponto pedido: blinds, antes, e o que cada jogador tem na
    frente — a aposta enfrentada inclusive. Streets anteriores contam inteiras; a street
    corrente conta so ate `upto_index`."""
    ordem, vistas = [], set()
    for a in actions:
        if a.street not in vistas:
            vistas.add(a.street)
            ordem.append(a.street)
    if street not in ordem:
        ordem.append(street)

    jogadores = {s['name'] for s in (hand.seats or [])} or {a.player for a in actions}
    total = sum(float(v or 0) for v in (hand.antes or {}).values())
    for st in ordem:
        limite = upto_index if st == street else len(actions)
        total += sum(_committed_on_street(hand, actions, limite, st, p) for p in jogadores)
        if st == street:
            break
    return total


def main(argv):
    paths = argv[1:] or (glob.glob(os.path.join(BACKEND, '*.txt'))
                         + glob.glob(os.path.join(BACKEND, 'data', '*.txt')))
    ok_novo = ok_velho = n = 0
    piores = []
    for p in paths:
        try:
            hands = parse_hand_history(open(p, encoding='utf-8', errors='ignore').read())
        except Exception as exc:
            print(f'  [pulado] {os.path.basename(p)}: {exc}')
            continue
        for hand in hands:
            m = TOTAL_RE.search(hand.raw_text or '')
            if not m or not hand.actions:
                continue
            declarado = _num(m.group(1))
            devolvido = sum(_num(a or b) for a, b in DEVOLVIDO_RE.findall(hand.raw_text or ''))
            ultima = hand.actions[-1].street
            novo  = pot_at_decision(hand, hand.actions, len(hand.actions), ultima) - devolvido
            velho = _pot_up_to(hand.actions, len(hand.actions))
            n += 1
            tol = max(1.0, declarado * 0.005)
            ok_novo  += abs(novo  - declarado) <= tol
            ok_velho += abs(velho - declarado) <= tol
            if abs(novo - declarado) > tol:
                piores.append((hand.hand_id, declarado, novo, velho,
                               abs(novo - declarado) / max(declarado, 1)))

    if not n:
        print('nenhuma mao com "Total pot" no SUMMARY — sem oraculo, sem medicao.')
        return 1
    print(f'maos com "Total pot" no SUMMARY: {n}\n')
    print(f'{"reconstrucao":26s} {"bate":>7s} {"%":>8s}')
    print(f'{"_pot_up_to (motor hoje)":26s} {ok_velho:7d} {100.0 * ok_velho / n:7.1f}%')
    print(f'{"por jogador (proposta)":26s} {ok_novo:7d} {100.0 * ok_novo / n:7.1f}%')
    if piores:
        print(f'\ndivergencias da proposta ({len(piores)}), as 15 maiores:')
        for e in sorted(piores, key=lambda x: -x[4])[:15]:
            print(f'  mao {e[0]:16s} declarado={e[1]:12.2f} proposta={e[2]:12.2f} '
                  f'motor={e[3]:12.2f} ({100 * e[4]:.0f}%)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
