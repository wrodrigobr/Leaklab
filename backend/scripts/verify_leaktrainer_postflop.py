"""verify_leaktrainer_postflop.py — checagem READ-ONLY de prontidão do Leak Trainer Fase 2.

Para CADA spot do POSTFLOP_CATALOG, LÊ o nó pré-solvado (NUNCA solva: block_remote/
allow_remote_solve off, mesmo caminho do grade ao vivo) e reporta:
  - nó presente? (hand_strategy por-mão existe)
  - exploitability% (e se passa o gate de serviço)
  - estratégia da mão (fold/call/raise) + se o grade está coerente (mão feita nunca fold-dominante)

Objetivo: confirmar que prod tem TODOS os nós do catálogo, com expl baixa, ANTES de servir.
Se algum vier AUSENTE, é só (re)rodar seed_leaktrainer_postflop.py (esse solva). Nada é escrito.

Uso (no server da API; instantâneo, não chama o solver):
    python scripts/verify_leaktrainer_postflop.py [--prod]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if '--prod' in sys.argv:
    try:
        from dotenv import load_dotenv; load_dotenv()
    except ImportError:
        pass
    if not os.environ.get('DATABASE_URL'):
        sys.exit("ERRO: --prod requer DATABASE_URL.")
else:
    os.environ.pop('DATABASE_URL', None)

from leaklab.leak_trainer import (
    POSTFLOP_CATALOG, _BBDEF_PARAMS, _CATALOG_PARAMS, _cards_to_objs, grade_postflop_spot,
    _MAX_SERVE_EXPLOIT_PCT,
)
from leaklab.gto_solver import lookup_gto


def _spot(entry, p):
    return {
        'kind': 'postflop', 'street': p['street'], 'position': p['position'],
        'vs_position': p['vs_position'], 'stack_bb': p['stack_bb'],
        'facing_size_bb': p['facing_size_bb'], 'pot_bb': p['pot_bb'],
        'pot_type': p.get('pot_type', ''), 'opener': p.get('opener', ''),
        'threebettor': p.get('threebettor', ''),
        'board': entry['board'], 'hero_hand': entry['hand'],
        'hand': ''.join(entry['hand']),
    }


def _verifica_catalogo(nome, cat):
    """(present, missing, high_expl, rows). Varre pelo caminho do SERVIÇO (grade), com os
    parâmetros DO catálogo — verificar o bb_3bet_pot com os params da bb_defense checaria o
    hash errado e daria AUSENTE falso (ou pior, OK falso via nó SRP)."""
    p = _CATALOG_PARAMS.get(nome, _BBDEF_PARAMS)
    # Ação de sondagem legal para a FORMA do spot: enfrentando aposta → call; facing 0 → check.
    acao = 'call' if float(p.get('facing_size_bb') or 0) > 0 else 'check'
    present = missing = high_expl = 0
    rows = []
    for e in cat:
        s = _spot(e, p)
        res = lookup_gto(
            street=s['street'], position=s['position'], board=s['board'],
            hero_hand=s['hero_hand'], hero_stack_bb=s['stack_bb'],
            vs_position=s['vs_position'], facing_size_bb=s['facing_size_bb'],
            pot_bb=s['pot_bb'], bb_chips=1.0,
            pot_type=s['pot_type'], opener=s['opener'], threebettor=s['threebettor'],
            require_hand_aware=True, block_remote=False, allow_remote_solve=False,
        )
        hs = res.get('hand_strategy')
        expl = res.get('exploitability_pct')
        tag = f"{''.join(c[0] for c in e['board'])} {''.join(e['hand'])}"
        if not hs or not hs.get('actions'):
            missing += 1
            rows.append(('AUSENTE', tag, '', 'nó/hand_strategy não encontrado → reseed'))
            continue
        # grade via o MESMO caminho do serviço (já aplica o gate de expl)
        g = grade_postflop_spot(s, acao)
        if g is None:
            high_expl += 1
            rows.append(('GATED', tag, f"{expl:.2f}%" if expl is not None else "?",
                         f"expl > {_MAX_SERVE_EXPLOIT_PCT}% → não-gradeável (rede de segurança)"))
            continue
        present += 1
        strat = ' · '.join(f"{x['action']} {round(x['freq']*100)}%" for x in g.get('gto_strategy', []))
        # coerência: mão que o GTO quase nunca folda não pode ser gradeada como erro ao pagar
        fold_f = next((x['freq'] for x in g.get('gto_strategy', []) if x['action'] == 'fold'), 0.0)
        flag = '' if fold_f < 0.5 else ' ⚠ fold-dominante'
        rows.append(('OK', tag, f"{expl:.2f}%" if expl is not None else "?", strat + flag))
    return present, missing, high_expl, rows


def main():
    print(f"\n{'='*72}\nLEAK TRAINER FASE 2 — prontidão postflop ({'PROD' if '--prod' in sys.argv else 'DEV'})")
    print(f"gate de serviço: expl ≤ {_MAX_SERVE_EXPLOIT_PCT}%\n{'='*72}")
    tot_p = tot_m = tot_g = tot_n = 0
    for nome, cat in POSTFLOP_CATALOG.items():
        present, missing, high_expl, rows = _verifica_catalogo(nome, cat or [])
        tot_p += present; tot_m += missing; tot_g += high_expl; tot_n += len(cat or [])
        print(f"\n── catálogo {nome}: {len(cat or [])} spots ──")
        for status, tag, expl, info in rows:
            mark = {'OK': '✓', 'AUSENTE': '✗', 'GATED': '⚠'}.get(status, '?')
            print(f"  {mark} {status:8s} {tag:<14} {expl:>7} {info}")
    print('-' * 72)
    print(f"  servíveis: {tot_p}/{tot_n} | ausentes: {tot_m} | gated(expl alta): {tot_g}")
    if tot_m:
        print("  → AUSENTES: rode `python scripts/seed_leaktrainer_postflop.py` (+ --pote-3bet) e repita.")
    elif tot_g:
        print("  → algum nó acima do gate: reseed ou remova do POSTFLOP_CATALOG.")
    else:
        print("  ✅ TODOS os spots de TODOS os catálogos estão servíveis — pronto pra servir.")
    return 1 if (tot_m or tot_g) else 0


if __name__ == '__main__':
    sys.exit(main())
