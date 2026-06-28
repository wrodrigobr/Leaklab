"""
diag_coach_flow.py — diagnóstico PONTA A PONTA do fluxo coach→aluno→pagamento→comissão, em dados de
TESTE (criados e APAGADOS no final). Prova que a experiência do coach não trava ANTES de convidar um
parceiro real (ex.: o Bruno).

NÃO usa contas reais. Cria 1 coach + 1 aluno temporários (emails __diag__), roda a cadeia inteira,
verifica cada elo, e limpa tudo no finally. Idempotente: limpa restos de execuções anteriores no início.

Rodar no server da API (prod), dentro do container:
    docker compose exec -T web python scripts/diag_coach_flow.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database import repositories as R

COACH_EMAIL   = '__diag_coach__@grindlab.local'
STUDENT_EMAIL = '__diag_student__@grindlab.local'
RATE_BPS = 3000      # 30% (mesmo override de parceiro)
PAY_CENTS = 9900     # R$99 (uma mensalidade Pro)

_results = []


def check(label, ok, detail=''):
    _results.append((bool(ok), label))
    print(f"  {'OK ' if ok else 'XX '} {label}" + (f"   [{detail}]" if detail else ''))


def _cleanup():
    """Apaga os usuários de teste + tudo que depende deles (comissões, convites, perfil, vínculos)."""
    conn = get_conn()
    try:
        ids = {}
        for em in (COACH_EMAIL, STUDENT_EMAIL):
            u = conn.execute(R._adapt("SELECT id FROM users WHERE email=?"), (em,)).fetchone()
            if u:
                ids[em] = u['id']
        for uid in ids.values():
            for sql in (
                "DELETE FROM coach_commissions WHERE coach_id=? OR student_id=?",
                "DELETE FROM coach_invites WHERE coach_id=? OR used_by=?",
                "DELETE FROM coach_profiles WHERE user_id=?",
            ):
                try:
                    conn.execute(R._adapt(sql), (uid,) * sql.count('?'))
                except Exception:
                    pass
            try:
                conn.execute(R._adapt("UPDATE users SET coach_id=NULL WHERE coach_id=?"), (uid,))
            except Exception:
                pass
        for em in (STUDENT_EMAIL, COACH_EMAIL):   # aluno antes do coach (FK coach_id)
            if em in ids:
                try:
                    conn.execute(R._adapt("DELETE FROM users WHERE id=?"), (ids[em],))
                except Exception:
                    pass
        conn.commit()
    finally:
        conn.close()


def _set_plan_pro(uid):
    conn = get_conn()
    try:
        conn.execute(R._adapt("UPDATE users SET plan='pro' WHERE id=?"), (uid,))
        conn.commit()
    finally:
        conn.close()


def _coach_ledger(coach_id):
    rows = [c for c in R.get_coaches_commission_status() if int(c['id']) == int(coach_id)]
    if not rows:
        return 0
    r = rows[0]
    return int(r.get('payable_cents') or 0) + int(r.get('held_cents') or 0)


def main():
    print("=== DIAGNÓSTICO coach->aluno->pagamento->comissão (dados de teste, apagados no fim) ===")
    _cleanup()   # remove restos de execução anterior
    try:
        # 1. coach + perfil + override 30%
        coach_id = R.create_user('__diag_coach__', COACH_EMAIL, 'x12345678', role='coach')
        R.upsert_coach_profile(coach_id, display_name='Diag Coach', max_students=50)
        R.set_coach_commission_rate(coach_id, RATE_BPS)
        check('1. coach criado + override', bool(coach_id), f'coach_id={coach_id} rate={RATE_BPS // 100}%')

        # 2. coach gera convite single-use
        inv = R.create_coach_invite(coach_id)
        code = (inv or {}).get('code')
        check('2. convite gerado', bool(code), f'code={code}')

        # 3. aluno criado resgata o convite (vínculo entra PENDENTE)
        student_id = R.create_user('__diag_student__', STUDENT_EMAIL, 'x12345678', role='player')
        red = R.redeem_coach_invite(student_id, code or '')
        check('3. aluno resgata convite (pendente)', bool(red.get('ok') and red.get('pending')),
              str(red.get('error') or 'pending'))

        # 4. coach aprova o vínculo
        appr = R.approve_link_request(coach_id, student_id)
        check('4. coach aprova vínculo', bool(appr))

        # 5. aluno vira Pro e aparece ATIVO no painel do coach
        _set_plan_pro(student_id)
        fin = R.get_coach_finance_summary(coach_id)
        check('5. aluno ativo no painel do coach', fin['active_students'] == 1,
              f"ativos={fin['active_students']} rate_bps={fin.get('rate_bps')}")

        # 6. pagamento do aluno credita comissão 30% no ledger
        R.accrue_coach_commission(student_id, 'diag-pay-ref-1', PAY_CENTS)
        accrued = _coach_ledger(coach_id)
        expected = round(PAY_CENTS * RATE_BPS / 10000)   # 2970 = R$29,70
        check('6. comissão 30% creditada', accrued == expected,
              f"creditado=R${accrued / 100:.2f} esperado=R${expected / 100:.2f}")

        # 7. cockpit do coach mostra "a receber"
        fin2 = R.get_coach_finance_summary(coach_id)
        check('7. cockpit mostra a receber', fin2['amount_cents'] == expected,
              f"a_receber=R${fin2['amount_cents'] / 100:.2f}")

        # 8. idempotência: mesmo pagamento não cobra em dobro
        R.accrue_coach_commission(student_id, 'diag-pay-ref-1', PAY_CENTS)
        check('8. idempotente (sem dupla cobrança)', _coach_ledger(coach_id) == expected,
              f"após repetir: R${_coach_ledger(coach_id) / 100:.2f}")
    except Exception as e:
        import traceback
        check('EXCEÇÃO na cadeia', False, str(e))
        traceback.print_exc()
    finally:
        _cleanup()
        print("  (dados de teste removidos)")

    ok = sum(1 for r in _results if r[0])
    tot = len(_results)
    print(f"\n=== {ok}/{tot} elos OK ===")
    if ok < tot:
        print("FALHAS:", [lbl for good, lbl in _results if not good])
        print(">> Resolver antes de convidar um coach real (a 1ª impressão dele depende disso).")
    else:
        print(">> Fluxo coach->aluno->comissão íntegro. Pode convidar o coach com segurança.")


if __name__ == '__main__':
    main()
