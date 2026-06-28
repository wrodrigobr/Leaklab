"""
seed_leaktrainer_3betpot.py — Fase 2: catálogo BB 3-BET POT (c-bet OOP). Cobre as mãos que o BB 3-beta
(99+, AK/AQ/AJ, AA/KK, bluffs Axo) — as que NÃO entram na defesa-de-call (elas 3-betam preflop).

Cenário: BTN abre, BB 3-beta, BTN paga → flop. BB é o 3-bettor, OOP (player 0 → SEM flag TEXAS_HERO_IP),
age primeiro → decide C-BET ou check (facing=0). pot_type='3bet' (ranges REAIS de 3-bet capturadas pros
dois: BB 3-bet + BTN call-vs-3bet). Pote ~18bb, stack remanescente ~31bb (SPR ~1.7, típico de 3-bet pot).

Mesma disciplina do seed de call: solve + VALIDA offline (lookup_gto live, require_hand_aware, lê
hand_strategy DA MÃO, exploitability<3%, estratégia bet/check sã). Reprovado/None = não servido.

Uso (no server da API, dentro do container; ~75s/spot):
    docker compose exec -T web python scripts/seed_leaktrainer_3betpot.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.gto_solver import lookup_gto

STACK = 31.0          # efetivo remanescente após o 3-bet (40bb start, BB 3-beta a ~9)
POT_BB = 18.0         # pote 3-bet (BB 9 + BTN 9)
MAX_EXPLOIT = 3.0
OPENER, THREEB = 'BTN', 'BB'   # BTN abriu e pagou; BB 3-betou (hero)

# (board, hero, rótulo). Mãos do RANGE DE 3-BET do BB (99+, AK/AQ/AJ, AA/KK, bluffs Axo).
CATALOG = [
    ('flop', ['Kd', '7c', '2s'], ['Ac', 'Ah'], 'overpair (AA)'),
    ('flop', ['Kd', '7c', '2s'], ['Ad', 'Kc'], 'top pair (AK)'),
    ('flop', ['Kd', '7c', '2s'], ['9h', '9d'], 'under pair (99)'),
    ('flop', ['Kd', '7c', '2s'], ['Ah', '5c'], 'air/bluff (A5o)'),
    ('flop', ['9h', '8h', '5c'], ['Ac', 'Ad'], 'overpair (AA)'),
    ('flop', ['9h', '8h', '5c'], ['Ah', 'Kd'], 'overs/air (AK)'),
    ('flop', ['Qd', '7s', '4h'], ['Ac', 'Kc'], 'overs (AK)'),
    ('flop', ['Qd', '7s', '4h'], ['Ad', 'Qc'], 'top pair (AQ)'),
    ('flop', ['Ad', '6c', '3s'], ['Ah', 'Kc'], 'top pair (AK)'),
    ('flop', ['Ad', '6c', '3s'], ['9h', '9d'], 'under pair (99)'),
    ('flop', ['Th', '8d', '3c'], ['Ac', 'Ad'], 'overpair (AA)'),
    ('flop', ['Th', '8d', '3c'], ['Ah', 'Jd'], 'overs + gutshot (AJ)'),
    ('flop', ['5d', '4s', '2h'], ['Ac', 'Ad'], 'overpair (AA)'),
    ('flop', ['5d', '4s', '2h'], ['Ah', 'Kd'], 'overs (AK)'),
]
_EXPECTED = {'bet', 'check', 'fold', 'call', 'raise'}


def _fmt_strategy(res):
    acts = (res.get('hand_strategy') or {}).get('actions') or {}
    parts = []
    for label, d in sorted(acts.items(), key=lambda x: -((x[1] or {}).get('frequency') or 0)):
        f = (d or {}).get('frequency') or 0
        pct = round(f * 100) if f <= 1.0 else round(f)
        parts.append(f"{label} {pct}%")
    return " · ".join(parts) if parts else "(sem hand_table)"


def _validate(res):
    if not res.get('found'):
        return False, f"sem solução ({res.get('source')})"
    hs = res.get('hand_strategy')
    if not hs or not hs.get('actions'):
        return False, "sem tabela por-mão (None — fora do range OU agregado)"
    expl = res.get('exploitability_pct')
    if expl is None:
        return False, "exploitability None"
    if expl > MAX_EXPLOIT:
        return False, f"exploitability {expl:.2f}% > {MAX_EXPLOIT}%"
    acts = {(k or '').split('_')[0] for k in hs['actions'].keys()}
    if not acts or not acts & _EXPECTED:
        return False, f"ações inesperadas: {acts}"
    return True, f"expl={expl:.2f}% best={hs.get('best_action')}"


def main():
    if not os.environ.get('GTO_SOLVER_URL'):
        print("AVISO: GTO_SOLVER_URL não setado — rode no server da API.")
    served, dropped = [], []
    for street, board, hero, label in CATALOG:
        tag = f"{''.join(c[0] for c in board)} {''.join(hero)} · {label}"
        try:
            res = lookup_gto(
                street=street, position='BB', board=board, hero_hand=hero,
                hero_stack_bb=STACK, vs_position='BTN',
                facing_size_bb=0.0, pot_bb=POT_BB,
                pot_type='3bet', opener=OPENER, threebettor=THREEB,
                require_hand_aware=True, allow_remote_solve=True, block_remote=True,
            )
        except Exception as e:
            dropped.append(('', tag, f"erro: {e}", ''))
            continue
        ok, why = _validate(res)
        (served if ok else dropped).append(((res.get('spot_hash') or '')[:12], tag, why, _fmt_strategy(res)))

    print(f"\n=== 3-BET POT BB (c-bet OOP, pote {POT_BB}bb, stack {STACK}bb) — {len(CATALOG)} spots ===")
    print(f"VALIDADOS ({len(served)}) — exploitability < {MAX_EXPLOIT}%:")
    for h, tag, why, strat in served:
        print(f"  ✓ {tag:<32} [{why}]\n        {strat}")
    print(f"REPROVADOS ({len(dropped)}):")
    for h, tag, why, strat in dropped:
        print(f"  ✗ {tag:<32} [{why}]" + (f"\n        {strat}" if strat else ""))
    print("\nValidados = mãos de 3-bet com c-bet/check coerente. Os None devem ser raros (mãos no 3-bet range).")


if __name__ == '__main__':
    main()
