"""Validação EXAUSTIVA da invariante do veredito.

INVARIANTE (exigida pelo dono): qualquer indício de erro ⇒ a mão NUNCA pode ser "Correta"/"Aceitável".
Sinal canônico (fonte única): is_verdict_error_signal — GTO folda a mão mas o hero AGREDIU.

Varre TODAS as decisões e reporta as que VIOLAM: sinal de erro presente, mas label não-erro
(standard/marginal). Exclui mix legítimo (gto_mixed/gto_correct). Não altera dados.
Uso: python scripts/validate_verdict_invariant.py [--prod]
"""
import os, sys
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
from database.repositories import is_verdict_error_signal

ERROR_LABELS = {'small_mistake', 'clear_mistake'}
conn = get_conn()
rows = conn.execute(
    "SELECT id, label, gto_label, gto_action, action_taken, street, position, hero_cards, stack_bb "
    "FROM decisions WHERE gto_action IS NOT NULL AND gto_action != '' "
    "AND action_taken IS NOT NULL AND action_taken != ''"
).fetchall()

viol = []
checked = 0
for r in rows:
    if not is_verdict_error_signal(r['gto_action'], r['action_taken']):
        continue
    if (r['gto_label'] or '') in ('gto_mixed', 'gto_correct'):
        continue   # mix legítimo: agressão pode ser co-ótima
    checked += 1
    if (r['label'] or '') not in ERROR_LABELS:
        viol.append(r)

print(f"\n{'='*70}\nINVARIANTE DO VEREDITO — {len(rows)} decisões varridas\n{'='*70}")
print(f"Com sinal de erro de direção (fora de mix): {checked}")
print(f"\n{'VIOLAÇÕES: ' + str(len(viol)) if viol else '✅ ZERO violações — nenhuma mão com indício de erro está como não-erro'}")
for r in viol[:50]:
    print(f"  [dec {r['id']}] {r['street']}/{r['position']} {r['hero_cards']} @ {r['stack_bb']}bb | "
          f"ação={r['action_taken']} gto={r['gto_action']} | label={r['label']} gto_label={r['gto_label']}")
if len(viol) > 50:
    print(f"  ... +{len(viol)-50}")
conn.close()
sys.exit(1 if viol else 0)
