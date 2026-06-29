"""Validação da invariante de SEGURANÇA do gate multiway (#30, Fase 1).

Varre as decisões com multiway_safe_verdict gravado (shadow) e CONFIRMA, recomputando
o gate, que cada veredito gradeado de fato sobrevive ao canto adversário:
  safe_fold  ⇒ eq_hi (vilão larguíssimo) + ruído  <  required − FOLD_MARGIN
  safe_value ⇒ eq_lo (vilão apertadíssimo) − ruído ≥ STRONG
Pega drift (lógica mudou e a coluna ficou velha) e corrupção. Read-only; não escreve.
Exit 1 se houver violação (gateável no CI). Uso:
  python scripts/validate_multiway_safety.py [--prod] [--sims N]
"""
import os, sys, json

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

from database.schema import get_conn
from leaklab.multiway_safety import classify_safe, _HAS_EVAL7

if not _HAS_EVAL7:
    print("SKIP: eval7 ausente"); sys.exit(0)


def main():
    n_sims = 8000
    if '--sims' in sys.argv:
        n_sims = int(sys.argv[sys.argv.index('--sims') + 1])

    conn = get_conn()
    rows = conn.execute(
        "SELECT id, hero_cards, board, pot_size, facing_bet, street, "
        "n_active_opponents, multiway_safe_verdict, action_taken "
        "FROM decisions "
        "WHERE multiway_safe_verdict IN ('safe_fold','safe_value')"
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]

    viol = []
    for r in rows:
        try:
            board = json.loads(r['board']) if r['board'] else []
        except Exception:
            board = []
        v = classify_safe(r['hero_cards'], board, int(r['n_active_opponents'] or 0),
                          float(r['pot_size'] or 0),
                          float(r['facing_bet']) if r['facing_bet'] is not None else 0.0,
                          street=(r['street'] or '').lower(), n_sims=n_sims)
        stored = r['multiway_safe_verdict']
        # (1) recomputo tem que CONTINUAR na mesma cauda (sem drift)
        if v['bucket'] != stored:
            viol.append((r['id'], f"drift: gravado={stored} recomputado={v['bucket']}"))
            continue
        # (2) invariante de segurança propriamente dita
        if stored == 'safe_fold':
            if not (v['required_eq'] and v['eq_hi'] is not None
                    and v['eq_hi'] < v['required_eq']):
                viol.append((r['id'], f"safe_fold sem priced-out: eq_hi={v['eq_hi']} req={v['required_eq']}"))
        elif stored == 'safe_value':
            if not (v['eq_lo'] is not None and v['eq_lo'] >= 0.60):
                viol.append((r['id'], f"safe_value fraco: eq_lo={v['eq_lo']}"))

    src = 'PROD' if '--prod' in sys.argv else 'DEV'
    print(f"\n{'='*68}\nVALIDAÇÃO GATE MULTIWAY — {src} ({len(rows)} vereditos gradeados)\n{'='*68}")
    if viol:
        print(f"VIOLAÇÕES: {len(viol)}")
        for did, msg in viol[:40]:
            print(f"  [dec {did}] {msg}")
        if len(viol) > 40:
            print(f"  ... +{len(viol)-40}")
    else:
        print("✅ ZERO violações — todo veredito gradeado sobrevive ao canto adversário")
    return 1 if viol else 0


if __name__ == '__main__':
    sys.exit(main())
