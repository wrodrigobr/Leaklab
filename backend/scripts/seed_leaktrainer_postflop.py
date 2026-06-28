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
MAX_EXPLOIT = 2.0     # % — acima disso o solve não convergiu o bastante p/ servir como verdade

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
    """Retorna (ok, motivo). Só serve spot com solve convergido + estratégia sã."""
    if not res.get('found'):
        return False, f"sem solução ({res.get('source')})"
    expl = res.get('exploitability_pct')
    if expl is None:
        return False, "exploitability None (sem garantia)"
    if expl > MAX_EXPLOIT:
        return False, f"exploitability {expl:.2f}% > {MAX_EXPLOIT}%"
    strat = res.get('strategy') or []
    acts = {(s.get('action') or '').split('_')[0] for s in strat}
    if not acts or not acts & _EXPECTED:
        return False, f"ações inesperadas: {acts}"
    # degenerada: 1 ação ~100% (ok se for fold de lixo, mas sinalizamos p/ revisão manual)
    top = max((s.get('frequency') or 0) for s in strat) if strat else 0
    degenerate = top >= 0.985 and len(strat) > 1
    return True, (f"expl={expl:.2f}% acts={sorted(acts)}" + (" [DEGENERADA — revisar]" if degenerate else ""))


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
            )
        except Exception as e:
            dropped.append(('', tag, f"erro: {e}"))
            continue
        ok, why = _validate(res)
        (served if ok else dropped).append(((res.get('spot_hash') or '')[:12], tag, why))

    print(f"\n=== PILOTO BB-DEFESA — {len(CATALOG)} spots ===")
    print(f"VALIDADOS ({len(served)}):")
    for h, tag, why in served:
        print(f"  ✓ {h}…  {tag:>14}  {why}")
    print(f"REPROVADOS ({len(dropped)}):")
    for h, tag, why in dropped:
        print(f"  ✗ {h}…  {tag:>14}  {why}")
    print("\nPróximo passo: cross-check MANUAL de 2-3 validados vs GTO Wizard antes de ligar o branch.")
    print("Os hashes validados são o que o trainer vai LER (mesmo facing em BB).")


if __name__ == '__main__':
    main()
