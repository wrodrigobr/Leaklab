"""
Quota de upload de torneios (teto Free vem de PLAN_LIMITS) + correção do bug de re-import:
merge do MESMO torneio não consome quota nem é barrado; só torneio NOVO conta.
Reusa o setup/fixture do test_api_endpoints (DB SQLite isolado por client).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import test_api_endpoints as api          # mock flask_cors + helpers de client/auth
from database import repositories as repo

_FIX = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')


def _blocks():
    if not os.path.exists(_FIX):
        return None
    with open(_FIX, encoding='utf-8') as f:
        return [b for b in f.read().split('\n\n\n') if b.strip()]


def test_merge_not_counted_and_block_at_two():
    blocks = _blocks()
    if not blocks:
        print("OK  test_merge_not_counted_and_block_at_two | SKIP (fixture ausente)")
        return
    c = api._make_client()
    token = api._register_and_login(c, 'quota')
    h = api._auth_headers(token)
    uid = repo.get_user_by_email('testquota@api.com')['id']

    def imp(content):
        return c.post('/analyze', json={'content': content}, headers=h)
    def used():
        return repo.get_quota_status(uid)['tournaments_used']

    orig = '3910307458'
    j5  = '\n\n\n'.join(blocks[:5])
    j10 = '\n\n\n'.join(blocks[:10])   # mesmo T#, +5 mãos novas → merge

    # 1) torneio novo conta
    assert imp(j5).status_code == 200
    assert used() == 1, used()

    # 2) re-import do MESMO torneio (merge) NÃO conta de novo (o bug corrigido)
    assert imp(j10).status_code == 200
    assert used() == 1, f"merge não deveria incrementar, used={used()}"

    # 3) segundo torneio DISTINTO conta
    assert imp(j5.replace(orig, '9000000001')).status_code == 200
    assert used() == 2, used()

    # ── O teto vem da FONTE UNICA, nunca cravado (05/09) ────────────────────────────────
    # Este teste cravava `2` e ficou vermelho quando o corte Free subiu para 30 em 28/08
    # (decisao de negocio: "importar nao e custo, e aquisicao"). Como o arquivo estava FORA
    # da suite, ninguem viu — parecia bug de cota e era teste velho. Lendo de `PLAN_LIMITS`,
    # ele acompanha a decisao em vez de congelar o numero de ontem.
    teto = repo.PLAN_LIMITS['free']['tournaments']
    conn = repo.get_conn()
    conn.execute(repo._adapt("UPDATE users SET tournaments_this_month = ? WHERE id = ?"),
                 (teto - 1, uid))
    conn.commit(); conn.close()

    # 4) o torneio que ENCOSTA no teto passa
    assert imp(j5.replace(orig, '9000000002')).status_code == 200, "o ultimo do teto foi barrado"
    assert used() == teto, used()

    # 5) o SEGUINTE e barrado (402)
    r = imp(j5.replace(orig, '9000000003'))
    assert r.status_code == 402 and r.get_json().get('quota_exceeded'), (
        "teto %d nao barrou o torneio seguinte: HTTP %s" % (teto, r.status_code))

    # 6) mas re-import (merge) de um torneio EXISTENTE passa mesmo no teto
    j15 = '\n\n\n'.join(blocks[:15])   # T# original, +5 maos novas
    assert imp(j15).status_code == 200, "merge no teto nao deveria ser barrado"
    assert used() == teto, used()
    print("OK  test_merge_not_counted_and_block_at_two | teto=%d" % teto)


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
    raise SystemExit(1 if failed else 0)
