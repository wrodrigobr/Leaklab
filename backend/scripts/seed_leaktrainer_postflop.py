"""
seed_leaktrainer_postflop.py — Fase 2 (piloto BB-defesa): SOLVA + VALIDA um catálogo de spots postflop
hero-OOP pro Leak Trainer, pelo caminho PROVADO (lookup_gto live-solve) e com gate de validação.

Por que assim (e não enqueue cru):
  - lookup_gto no live-solve RE-DERIVA as ranges REAIS do GW (hero OOP = call-vs-RFI, vilão IP = RFI)
    e ARMAZENA o nó com exploitability. O enqueue cru usaria _DEFAULT_RANGES genéricas (doc 2.3).
  - hero OOP (BB) = player 0 → o solver devolve a estratégia do HERO sem precisar do flag TEXAS_HERO_IP.
  - facing em BB nos dois lados (o hash usa facing_size_bb cru, gto_solver.py:312); bb_chips=1 passa o
    gate de conversão sem mudar o hash. Assim o hash do solve == hash que o trainer vai LER.

GATE DE VALIDAÇÃO (não servimos lixo): só entra no catálogo o spot com
  - found=True e exploitability_pct < MAX_EXPLOIT (solve convergiu),
  - estratégia com as ações esperadas (fold/call/raise) e não-degenerada.
Os reprovados são LISTADOS (não servidos). Sem cross-check vs GTO Wizard automático aqui — fazer manual
numa amostra antes de ligar o branch postflop do trainer.

Uso (no SERVER DA API, que alcança o solver via GTO_SOLVER_URL; ~75s/spot, alguns minutos):
    python scripts/seed_leaktrainer_postflop.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.gto_solver import lookup_gto

STACK = 40.0
POT_BB = 5.0          # SRP: BTN open ~2.2 + BB call → ~5bb
CBET = 1.65           # c-bet ~33% do pote (em BB)
MAX_EXPLOIT = 3.0     # % — bar prático: o grading é por TIER (freq≥30%=correto), robusto a erro de
                      # poucos % na freq. 2-3% é "GTO prático" bom. A corretude REAL vem do cross-check
                      # vs GTO Wizard (a exploitability só prova convergência, não a resposta certa).

# BB defesa OOP vs BTN (hero=BB=player 0, sem flag). facing>0 = enfrenta c-bet. Variedade de
# board (seco/molhado/pareado) × mão (top pair/par/draw/air) p/ o trainer ter de onde escolher.
# (street, board, hero, rótulo) — o rótulo é só p/ leitura/coerência na saída.
# Mãos SEMPRE da CALL range do BB vs BTN (flats): conectores suited, pares baixos 22-44, ases fracos,
# broadways suited/offsuit que pagam. NÃO usar 55+/AK/AQ/AJ (3-betam → caem em hand_strategy None).
CATALOG = [
    # ── DRY: K72 rainbow ──
    ('flop', ['Kd', '7c', '2s'], ['Kh', 'Qc'], 'top pair bom kicker'),
    ('flop', ['Kd', '7c', '2s'], ['Kh', 'Ts'], 'top pair fraco'),
    ('flop', ['Kd', '7c', '2s'], ['7h', '6d'], 'par medio'),
    # ── DRY: A63 rainbow ──
    ('flop', ['Ad', '6c', '3s'], ['Kh', 'Qd'], 'overs (air)'),
    ('flop', ['Ad', '6c', '3s'], ['6h', '5d'], 'par medio + gutshot'),
    # ── DRY: Q74 rainbow ──
    ('flop', ['Qd', '7s', '4h'], ['Kh', 'Qc'], 'top pair'),
    ('flop', ['Qd', '7s', '4h'], ['Js', 'Td'], 'overs + gutshot'),
    ('flop', ['Qd', '7s', '4h'], ['Ac', '4d'], 'bottom pair + A'),
    # ── WET: 985 two-tone ──
    ('flop', ['9h', '8h', '5c'], ['Th', '9c'], 'par + draw'),
    ('flop', ['9h', '8h', '5c'], ['Jd', 'Tc'], 'OESD (JT)'),
    ('flop', ['9h', '8h', '5c'], ['7d', '6c'], 'straight feita (76)'),
    # ── WET: JT4 two-tone ──
    ('flop', ['Js', 'Ts', '4c'], ['Qh', 'Jd'], 'top pair + OESD'),
    ('flop', ['Js', 'Ts', '4c'], ['Kd', 'Qc'], 'OESD (KQ)'),
    # ── WET: T96 two-tone ──
    ('flop', ['Th', '9d', '6c'], ['Qs', 'Jd'], 'OESD (QJ)'),
    ('flop', ['Th', '9d', '6c'], ['Ah', 'Td'], 'top pair'),
    # ── PAIRED: KK4 ──
    ('flop', ['Kc', 'Kd', '4h'], ['Js', 'Td'], 'air + gutshot'),
    # ── EXPANSÃO ──
    # two-tone 9h7h2c (flush draw)
    ('flop', ['9h', '7h', '2c'], ['Th', '8h'], 'OESD + flush draw (T8s)'),
    ('flop', ['9h', '7h', '2c'], ['Ad', '9c'], 'top pair (A9o)'),
    # broadway KdQcJs (straights/draws)
    ('flop', ['Kd', 'Qc', 'Js'], ['Ah', 'Td'], 'straight nut (ATo)'),
    ('flop', ['Kd', 'Qc', 'Js'], ['Ts', '9s'], 'straight + bdfd (T9s)'),
    ('flop', ['Kd', 'Qc', 'Js'], ['9c', '8c'], 'gutshot (98s)'),
    # low connected 7d6s4h
    ('flop', ['7d', '6s', '4h'], ['8c', '7h'], 'par + OESD (87o)'),
    ('flop', ['7d', '6s', '4h'], ['Ac', '4d'], 'bottom pair + A (A4o)'),
    ('flop', ['7d', '6s', '4h'], ['Ts', '9d'], 'overs + gutshot (T9o)'),
    # paired 9s9d4c (trips/air)
    ('flop', ['9s', '9d', '4c'], ['Kh', '9c'], 'trips (K9o)'),
    ('flop', ['9s', '9d', '4c'], ['Ah', '5d'], 'ace high air (A5o)'),
    # ace two-tone AhTc5h
    ('flop', ['Ah', 'Tc', '5h'], ['Ad', '8c'], 'top pair (A8o)'),
    ('flop', ['Ah', 'Tc', '5h'], ['8h', '7h'], 'flush draw (87s)'),
    ('flop', ['Ah', 'Tc', '5h'], ['Jd', 'Td'], 'mid pair (JTo)'),
    # middle two-tone 9s7s4d
    ('flop', ['9s', '7s', '4d'], ['8h', '6h'], 'OESD (86s)'),
    ('flop', ['9s', '7s', '4d'], ['Kh', '9c'], 'top pair (K9o)'),
]

_EXPECTED = {'fold', 'call', 'raise', 'check', 'bet'}


def _validate(res):
    """Só serve spot com solve convergido + estratégia DA MÃO (hand_strategy), não o agregado da range."""
    if not res.get('found'):
        return False, f"sem solução ({res.get('source')})"
    hs = res.get('hand_strategy')
    if not hs or not hs.get('actions'):
        return False, "sem tabela por-mão (hand_strategy None — só agregado)"
    expl = res.get('exploitability_pct')
    if expl is None:
        return False, "exploitability None (sem garantia)"
    if expl > MAX_EXPLOIT:
        return False, f"exploitability {expl:.2f}% > {MAX_EXPLOIT}%"
    acts = {(k or '').split('_')[0] for k in hs['actions'].keys()}
    if not acts or not acts & _EXPECTED:
        return False, f"ações inesperadas: {acts}"
    return True, f"expl={expl:.2f}% best={hs.get('best_action')}"


def _fmt_strategy(res):
    """Estratégia DA MÃO (por-mão, não agregada): 'fold 3% · call 70% · raise 27%'."""
    acts = (res.get('hand_strategy') or {}).get('actions') or {}
    parts = []
    for label, d in sorted(acts.items(), key=lambda x: -((x[1] or {}).get('frequency') or 0)):
        f = (d or {}).get('frequency') or 0
        pct = round(f * 100) if f <= 1.0 else round(f)
        parts.append(f"{label} {pct}%")
    return " · ".join(parts) if parts else "(sem hand_table)"


def main():
    if not os.environ.get('GTO_SOLVER_URL'):
        print("AVISO: GTO_SOLVER_URL não setado — rode no server da API (onde alcança o solver).")
    served, dropped = [], []
    for street, board, hero, label in CATALOG:
        tag = f"{''.join(c[0] for c in board)} {''.join(hero)} · {label}"
        try:
            res = lookup_gto(
                street=street, position='BB', board=board, hero_hand=hero,
                hero_stack_bb=STACK, vs_position='BTN',
                facing_size_bb=CBET, pot_bb=POT_BB, bb_chips=1.0,
                allow_remote_solve=True, block_remote=True,   # live solve (GW-real ranges)
                require_hand_aware=True,                       # estratégia DA MÃO, não o agregado da range
            )
        except Exception as e:
            dropped.append(('', tag, f"erro: {e}", ''))
            continue
        ok, why = _validate(res)
        (served if ok else dropped).append(((res.get('spot_hash') or '')[:12], tag, why, _fmt_strategy(res)))

    print(f"\n=== PILOTO BB-DEFESA (BTN open ~{POT_BB}bb, c-bet {CBET}bb, {int(STACK)}bb) — {len(CATALOG)} spots ===")
    print(f"VALIDADOS ({len(served)}) — exploitability < {MAX_EXPLOIT}%:")
    for h, tag, why, strat in served:
        print(f"  ✓ {tag:<34} [{why}]\n        {strat}")
    print(f"REPROVADOS ({len(dropped)}):")
    for h, tag, why, strat in dropped:
        print(f"  ✗ {tag:<34} [{why}]" + (f"\n        {strat}" if strat else ""))
    print("\nCROSS-CHECK: compare as frequências acima (board+mão BB defendendo vs BTN open, ~40bb) com o")
    print("GTO Wizard (mesmo spot). Se baterem na DIREÇÃO e ~freq, o pipeline está correto → ligo o branch.")


if __name__ == '__main__':
    main()
