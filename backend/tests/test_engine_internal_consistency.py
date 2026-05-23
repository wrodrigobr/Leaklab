"""
Testes de consistência interna do engine.

O engine produz `label` (verdict para o aluno) e `bestAction` (ação recomendada).
Quando os dois discordam SIGNIFICATIVAMENTE da ação tomada pelo hero, o aluno
vê narrativas contraditórias: "✓ Correto" no header MAS "foldar seria erro
matemático" nos indicadores. Esse é um bug crítico de UX que corrói confiança.

Este teste percorre todas as decisões reais do banco e falha se alguma viola
o invariante: `label='standard'` ⇒ ação tomada coerente com best_action (mesma
família agressivo/passivo OU mesma ação exata).

Tolerâncias aplicadas:
- bet ≡ raise em preflop (bet=open, raise=continuation; engine pode emitir bet
  como sinônimo de raise em RFI)
- jam/allin/shove são sinônimos
- check ≡ call quando não há aposta a enfrentar
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.schema import get_conn


_AGGRESSIVE = {'bet', 'raise', 'jam', 'allin', 'shove'}
_PASSIVE    = {'fold', 'check', 'call'}


def _norm(a):
    a = (a or '').lower().rstrip('s')
    return {
        'raise': 'raise', 'bet': 'raise',  # preflop: bet ≡ raise
        'all-in': 'allin', 'jam': 'allin', 'shove': 'allin',
    }.get(a, a)


def _action_matches(taken, best, street):
    """Retorna True se a ação tomada é semanticamente equivalente à best_action."""
    if not taken or not best:
        return True  # sem dados pra comparar
    t = _norm(taken)
    b = _norm(best)
    # postflop: bet e raise são distintos (bet = primeira aposta)
    if street != 'preflop':
        # restaura distinção
        t = (taken or '').lower().rstrip('s')
        b = (best or '').lower().rstrip('s')
        if t in {'all-in', 'jam', 'shove'}: t = 'allin'
        if b in {'all-in', 'jam', 'shove'}: b = 'allin'
    if t == b:
        return True
    # check ≡ call quando não há facing (frontend mostra ambos como "passivo OK")
    if {t, b} == {'check', 'call'}:
        return True
    # allin ≡ raise/bet — apostas all-in são raises agressivos
    if {t, b}.issubset({'raise', 'bet', 'allin'}):
        return True
    return False


def test_label_standard_implies_action_coherent():
    """label='standard' deve implicar que hero tomou ação coerente com best_action.

    Caso contrário: aluno vê 'Correto' no Replayer + indicadores que dizem o oposto.
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, hand_id, street, position, action_taken, best_action,
                   label, gto_label, gto_action, score
            FROM decisions
            WHERE label = 'standard'
              AND action_taken IS NOT NULL
              AND best_action IS NOT NULL
        """).fetchall()
    finally:
        conn.close()

    violations = []
    for r in rows:
        d = dict(r)
        if _action_matches(d['action_taken'], d['best_action'], d['street']):
            continue
        # Tolerância: gto_label=gto_mixed sinaliza estratégia mista — hero pegou
        # uma alternativa válida do mix. Label='standard' aqui é legítimo mesmo
        # se diferente do best_action (top action do mix).
        if d.get('gto_label') == 'gto_mixed':
            continue
        violations.append(d)

    if violations:
        sample = violations[:10]
        msg = (
            f"\n{len(violations)} decisões com label='standard' mas action != best_action.\n"
            f"Cada uma mostra 'Correto' no Replayer mas indicadores math contradizem.\n"
            f"Amostra:\n"
        )
        for v in sample:
            msg += (
                f"  id={v['id']} street={v['street']} pos={v['position']} "
                f"action={v['action_taken']} best={v['best_action']} "
                f"score={v['score']} gto_label={v['gto_label']}\n"
            )
        raise AssertionError(msg)
    print(f"OK  test_label_standard_implies_action_coherent | {len(rows)} decisões verificadas, 0 violações")


def test_label_standard_implies_no_gto_critical():
    """label='standard' não pode coexistir com gto_label='gto_critical'.

    Se GTO diz crítico, o reconcile deveria ter promovido label para small_mistake.
    Inconsistência indica reconcile não rodou OU bug no _reconcile_label.
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, hand_id, street, position, action_taken, label, gto_label, gto_action
            FROM decisions
            WHERE label = 'standard'
              AND gto_label = 'gto_critical'
        """).fetchall()
    finally:
        conn.close()

    if rows:
        sample = [dict(r) for r in rows[:10]]
        msg = (
            f"\n{len(rows)} decisões com label='standard' MAS gto_label='gto_critical'.\n"
            f"_reconcile_label deveria promover para small_mistake mínimo.\n"
            f"Amostra:\n"
        )
        for v in sample:
            msg += (
                f"  id={v['id']} {v['street']}/{v['position']} "
                f"action={v['action_taken']} gto_action={v['gto_action']}\n"
            )
        raise AssertionError(msg)
    print(f"OK  test_label_standard_implies_no_gto_critical | 0 violações")


def test_best_action_not_empty_when_label_set():
    """Toda decisão com label definido precisa ter best_action — proteção contra
    UI mostrar 'Correto' sem ter algo concreto pra recomendar."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT id, hand_id, street, action_taken, label
            FROM decisions
            WHERE label IS NOT NULL AND label != ''
              AND (best_action IS NULL OR best_action = '')
        """).fetchall()
    finally:
        conn.close()

    if rows:
        sample = [dict(r) for r in rows[:5]]
        raise AssertionError(
            f"\n{len(rows)} decisões com label preenchido mas sem best_action. Amostra: {sample}"
        )
    print(f"OK  test_best_action_not_empty_when_label_set | 0 violações")


if __name__ == '__main__':
    import traceback
    tests = [
        test_label_standard_implies_action_coherent,
        test_label_standard_implies_no_gto_critical,
        test_best_action_not_empty_when_label_set,
    ]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'=' * 50}\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
