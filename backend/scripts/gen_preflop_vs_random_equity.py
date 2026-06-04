"""Gera a tabela de equity preflop vs UMA mão aleatória (all-in até o river)
para as 169 mãos canônicas, via Monte Carlo com eval7. Saída: dict literal
Python pronto pra embutir em street_math_engine.py.

Uso: python -m scripts.gen_preflop_vs_random_equity [n_amostras]
"""
import sys, random
import eval7

random.seed(20260603)  # reprodutível

RANKS = '23456789TJQKA'
DECK = [eval7.Card(r + s) for r in RANKS for s in 'shdc']
_BY_STR = {str(c): c for c in DECK}

def canon_cards(hand: str):
    """'AKs' -> (As, Ks); 'AKo' -> (As, Kh); 'TT' -> (Ts, Th)."""
    r1, r2 = hand[0], hand[1]
    if r1 == r2:                      # par
        return _BY_STR[r1 + 's'], _BY_STR[r2 + 'h']
    if hand[2:] == 's':               # suited
        return _BY_STR[r1 + 's'], _BY_STR[r2 + 's']
    return _BY_STR[r1 + 's'], _BY_STR[r2 + 'h']  # offsuit

def all_hands():
    out = []
    for i, hi in enumerate(reversed(RANKS)):
        for j, lo in enumerate(reversed(RANKS)):
            ih, jl = 12 - i, 12 - j
            if ih == jl:
                out.append(hi + lo)            # par (i==j)
            elif ih > jl:
                out.append(hi + lo + 's')       # suited (acima da diagonal)
            else:
                out.append(lo + hi + 'o')       # offsuit
    return sorted(set(out))

def equity(hand: str, n: int) -> float:
    hero = list(canon_cards(hand))
    used = {str(c) for c in hero}
    deck = [c for c in DECK if str(c) not in used]
    ev = eval7.evaluate
    win = tie = 0
    for _ in range(n):
        s = random.sample(deck, 7)
        board = s[2:]
        hs = ev(hero + board)
        os = ev(s[:2] + board)
        if hs > os: win += 1
        elif hs == os: tie += 1
    return (win + tie / 2) / n

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    hands = all_hands()
    table = {}
    for k, h in enumerate(hands):
        table[h] = round(equity(h, n), 4)
        if k % 20 == 0:
            print(f"  {k}/{len(hands)} {h}={table[h]}", file=sys.stderr)
    # imprime dict literal ordenado por equity desc (legível)
    items = sorted(table.items(), key=lambda kv: -kv[1])
    print("PREFLOP_EQ_VS_RANDOM = {")
    line = "    "
    for h, v in items:
        tok = f"'{h}': {v}, "
        if len(line) + len(tok) > 96:
            print(line.rstrip()); line = "    "
        line += tok
    if line.strip():
        print(line.rstrip())
    print("}")
    print(f"# n_amostras={n}; 169 mãos; eval7 Monte Carlo", file=sys.stderr)

if __name__ == '__main__':
    main()
