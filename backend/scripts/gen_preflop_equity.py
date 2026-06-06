"""Gera a matriz de equity preflop MÃO-vs-MÃO (all-in até o river) para as 169
mãos canônicas — 169×169 — via Monte Carlo com eval7, respeitando card removal
(rejeita combos bloqueados). Saída: leaklab/data/preflop_equity_169.json no
formato {hero: {villain: eq}}.

Usa simetria eq[v][h] = 1 - eq[h][v] (empates dividem) → calcula só o triângulo
superior + diagonal. Diagonal NÃO é 0.5 exata (card removal), então é computada.

Uso: python -m scripts.gen_preflop_equity [n_amostras_por_par]
"""
import sys, os, json, random
import eval7

random.seed(20260606)  # reprodutível
RANKS = '23456789TJQKA'
SUITS = 'shdc'
DECK = [eval7.Card(r + s) for r in RANKS for s in SUITS]
_STR = {c: str(c) for c in DECK}


def combos(hand: str):
    """Todos os combos concretos de 2 cartas de uma mão canônica ('AKs','AKo','TT')."""
    r1, r2 = hand[0], hand[1]
    out = []
    if r1 == r2:                       # par: C(4,2)=6
        for i in range(4):
            for j in range(i + 1, 4):
                out.append((eval7.Card(r1 + SUITS[i]), eval7.Card(r2 + SUITS[j])))
    elif hand[2:] == 's':              # suited: 4
        for s in SUITS:
            out.append((eval7.Card(r1 + s), eval7.Card(r2 + s)))
    else:                              # offsuit: 12
        for i in SUITS:
            for j in SUITS:
                if i != j:
                    out.append((eval7.Card(r1 + i), eval7.Card(r2 + j)))
    return out


def all_hands():
    out = []
    for i, hi in enumerate(reversed(RANKS)):
        for j, lo in enumerate(reversed(RANKS)):
            ih, jl = 12 - i, 12 - j
            if ih == jl:
                out.append(hi + lo)
            elif ih > jl:
                out.append(hi + lo + 's')
            else:
                out.append(lo + hi + 'o')
    return sorted(set(out))


def equity_pair(hc, vc, n: int) -> float:
    """Equity de hero (combos hc) vs villain (combos vc), Monte Carlo com card
    removal por rejeição. n = nº de amostras VÁLIDAS alvo."""
    ev = eval7.evaluate
    win = tie = valid = 0
    attempts = 0
    cap = n * 6
    while valid < n and attempts < cap:
        attempts += 1
        h = random.choice(hc)
        v = random.choice(vc)
        h0, h1 = _STR[h[0]], _STR[h[1]]
        v0, v1 = _STR[v[0]], _STR[v[1]]
        if v0 == h0 or v0 == h1 or v1 == h0 or v1 == h1:
            continue                   # combo bloqueado
        used = {h0, h1, v0, v1}
        board = []
        while len(board) < 5:
            c = random.choice(DECK)
            cs = _STR[c]
            if cs in used:
                continue
            used.add(cs); board.append(c)
        hr = ev([h[0], h[1]] + board)
        vr = ev([v[0], v[1]] + board)
        if hr > vr:
            win += 1
        elif hr == vr:
            tie += 1
        valid += 1
    return (win + tie / 2) / valid if valid else 0.5


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
    hands = all_hands()
    combo_cache = {h: combos(h) for h in hands}
    H = len(hands)
    eq = {h: {} for h in hands}
    total_pairs = H * (H + 1) // 2
    done = 0
    for a in range(H):
        ha = hands[a]
        hc = combo_cache[ha]
        for b in range(a, H):
            hb = hands[b]
            e = equity_pair(hc, combo_cache[hb], n)
            eq[ha][hb] = round(e, 4)
            if b != a:
                eq[hb][ha] = round(1 - e, 4)   # simetria (empates dividem)
            done += 1
        if a % 10 == 0:
            print(f"  {done}/{total_pairs} pares (linha {a}/{H} {ha})", file=sys.stderr)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'data')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'preflop_equity_169.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(eq, f, separators=(',', ':'), sort_keys=True)
    sz = os.path.getsize(out_path)
    print(f"OK {out_path} ({H}×{H}, n={n}/par, {sz//1024} KB)", file=sys.stderr)
    # smoke sanity
    print(f"# AA vs KK = {eq['AA']['KK']} (esperado ~0.82)", file=sys.stderr)
    print(f"# AKo vs 22 = {eq['AKo']['22']} (esperado ~0.50)", file=sys.stderr)
    print(f"# 72o vs AA = {eq['72o']['AA']} (esperado ~0.12)", file=sys.stderr)


if __name__ == '__main__':
    main()
