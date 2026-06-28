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
# board (seco/molhado/pareado) × mão (top pair/par/draw/overs) p/ o trainer ter de onde escolher.
CATALOG = [
    ('flop', ['Kd', '7c', '2s'], ['Kh', 'Ts']),   # top pair kicker fraco, board seco
    ('flop', ['Kd', '7c', '2s'], ['7h', '6h']),   # par médio + bdfd
    ('flop', ['9h', '8h', '5c'], ['Th', '9c']),   # par + draw, board molhado
    ('flop', ['9h', '8h', '5c'], ['Ah', 'Jh']),   # overs + nut flush draw
    ('flop', ['Qd', '7s', '4h'], ['Js', 'Ts']),   # overs + gutshot, board seco
    ('flop', ['Qd', '7s', '4h'], ['As', '4d']),   # bottom pair top kicker
    ('flop', ['Ad', '6c', '3s'], ['7h', '7d']),   # under pair
    ('flop', ['5d', '5s', '2h'], ['Ac', 'Kd']),   # overs em board pareado
    ('flop', ['Js', 'Ts', '4c'], ['Qh', 'Jd']),   # top pair + gutshot, board conectado
    ('flop', ['8c', '5d', '2h'], ['Ah', 'Ks']),   # overs (air) em board seco baixo
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
    for street, board, hero in CATALOG:
        tag = ''.join(c[0] for c in board) + ' ' + ''.join(hero)
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
        print(f"  ✓ {tag:>14}  [{why}]\n        {strat}")
    print(f"REPROVADOS ({len(dropped)}):")
    for h, tag, why, strat in dropped:
        print(f"  ✗ {tag:>14}  [{why}]" + (f"\n        {strat}" if strat else ""))
    print("\nCROSS-CHECK: compare as frequências acima (board+mão BB defendendo vs BTN open, ~40bb) com o")
    print("GTO Wizard (mesmo spot). Se baterem na DIREÇÃO e ~freq, o pipeline está correto → ligo o branch.")


if __name__ == '__main__':
    main()
