"""medir_estimador_postflop.py — mede o erro do estimador heuristico de equity no postflop
contra um TETO computado.

READ-ONLY. Nao toca no banco. Le os hand histories passados na linha de comando (ou os que
estiverem em backend/*.txt e backend/data/*.txt):

    cd backend && python scripts/medir_estimador_postflop.py [arquivo.txt ...]

## O oraculo, e por que ele e rigoroso mesmo sendo unilateral

    equity vs a range PREFLOP do vilao  >=  equity real vs a range que ele APOSTA

Uma range de aposta e mais forte que a range preflop inteira, entao a equity do heroi contra
ela e MENOR. Logo, tudo que o estimador der ACIMA desse teto e supervalorizacao COMPROVADA --
sem precisar modelar range de aposta nenhuma, que seria a parte discutivel.

A range do vilao vem de `gto_solver._DEFAULT_RANGES`, a mesma definicao que o projeto ja usa
para solvar postflop (fonte unica). A equity sai do `eval7` por Monte Carlo, com o board real.

## O que esta medicao ja produziu

Rodada em 2026-08-04, 103 decisoes heads-up enfrentando aposta:

    street/categoria    n    estimador   teto     erro
    flop / air         49      35,3%    30,8%    + 4,5pp
    flop / value       19      66,2%    69,9%    - 3,7pp   (subvaloriza -- rede do Tema 2)
    turn / air         19      44,1%    32,0%    +12,1pp   <- CONSERTADO
    turn / value       16      65,8%    54,9%    +10,9pp   <- ABERTO

O `turn/air` era uma rua de potencial contada a mais: `_postflop_made_equity` era cego a street
e dava o mesmo numero no flop e no turn. Depois do conserto: +2,1pp, em linha com o flop.

O `turn/value` continua alto e NAO foi mexido. A explicacao provavel e estrutural (com 4 cartas
no board, mais da range do vilao conectou, entao mao feita vale relativamente menos), mas n=16
e o `flop/value` anda na direcao OPOSTA (-3,4pp) -- calibrar os dois exigiria mexer em duas
pontas com amostra pequena. Fica medido, nao chutado.
"""
import sys, os, glob
from collections import defaultdict

_here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
for _cand in (os.path.join(_here, '..'), _here, os.getcwd(), '/app/backend', '/app'):
    if os.path.isdir(os.path.join(_cand, 'leaklab')):
        sys.path.insert(0, os.path.abspath(_cand))
        BACKEND = os.path.abspath(_cand)
        break

from leaklab.parser import parse_hand_history                        # noqa: E402
from leaklab.hand_state_builder import extract_decision_points       # noqa: E402
from leaklab.pipeline import build_decision_input                    # noqa: E402
from leaklab.gto_solver import _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE  # noqa: E402
from leaklab.bet_intent import made_hand_category                    # noqa: E402

ITER = 8000


def equity_computada(hero_cards, board, vs_pos):
    """Equity do hero vs a range preflop do vilao, no board real. None se nao der para calcular."""
    try:
        import eval7
    except ImportError:
        return None
    try:
        h = [eval7.Card(hero_cards[i:i + 2]) for i in range(0, 4, 2)]
        b = [eval7.Card(c) for c in board]
        r = eval7.HandRange(_DEFAULT_RANGES.get((vs_pos or '').upper(), _DEFAULT_RANGE_WIDE))
        return eval7.py_hand_vs_range_monte_carlo(h, r, b, ITER)
    except Exception:
        return None


def main(argv):
    paths = argv[1:] or (glob.glob(os.path.join(BACKEND, '*.txt'))
                         + glob.glob(os.path.join(BACKEND, 'data', '*.txt')))
    por_cat = defaultdict(list)
    for p in paths:
        try:
            hands = parse_hand_history(open(p, encoding='utf-8', errors='ignore').read())
        except Exception as exc:
            print(f'  [pulado] {os.path.basename(p)}: {exc}')
            continue
        for hand in hands:
            if not hand.hero or not hand.bb or not hand.hero_cards:
                continue
            try:
                estados = extract_decision_points(hand)
            except Exception:
                continue
            for st in estados:
                if st.street not in ('flop', 'turn', 'river'):
                    continue
                if (st.metadata or {}).get('n_active_opponents') != 1:
                    continue          # multiway: o teto vs UMA range nao se aplica
                if not (st.metadata or {}).get('facing_to_call'):
                    continue          # so quem ENFRENTA aposta
                board = [c for c in (st.board or []) if c]
                if len(board) < 3:
                    continue
                try:
                    est = build_decision_input(st, hand)['math'].get('estimatedHandEquity')
                except Exception:
                    continue
                if est is None:
                    continue
                real = equity_computada(hand.hero_cards, board, st.villain_position)
                if real is None:
                    continue
                por_cat[(st.street, made_hand_category(hand.hero_cards, board) or '?')].append((est, real))

    if not por_cat:
        print('nenhuma decisao elegivel (heads-up, enfrentando aposta, com cartas e board).')
        return 1
    print(f'{"street/categoria":24s} {"n":>5s} {"estimador":>10s} {"teto":>10s} '
          f'{"erro":>9s} {"acima do teto":>15s}')
    tot = acima = 0
    for chave in sorted(por_cat):
        pares = por_cat[chave]
        n = len(pares)
        me = sum(e for e, _ in pares) / n
        mr = sum(r for _, r in pares) / n
        ac = sum(1 for e, r in pares if e > r + 0.02)
        tot += n
        acima += ac
        print(f'{chave[0] + "/" + chave[1]:24s} {n:5d} {me * 100:9.1f}% {mr * 100:9.1f}% '
              f'{(me - mr) * 100:+8.1f}pp {ac:7d} ({100 * ac / n:4.0f}%)')
    print(f'\ntotal: {tot} decisoes | estimador acima do teto em {acima} ({100 * acima / tot:.0f}%)')
    print('\nteto = equity vs a range PREFLOP do vilao. A equity real contra a range que ele')
    print('APOSTA e ainda MENOR, entao tudo acima do teto e supervalorizacao comprovada.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
