"""
test_replay_reconciliation_golden.py — REDE DE SEGURANÇA (characterization) do veredito do /replay.

Motivação (Stage 2 da unificação do StrategyProvider): o /replay reconcilia o veredito por 4 camadas
(stored-label → card_verdict → override preflop → multiway), PERSISTE no DB num GET e NÃO tinha teste.
Antes de mexer nessa reconciliação (Stage 3), este teste CONGELA a saída atual: importa um torneio real
(N mãos de torneio_ingles.txt) e tira um "fingerprint" dos campos DISCRETOS de veredito de cada ação do
hero, por todas as ruas. Qualquer mudança não-intencional na reconciliação quebra o golden.

Determinismo: PYTHONHASHSEED=0 (re-exec) fixa o seed do Monte Carlo multiway (hash-based). Sem solver
configurado, o postflop cai em pending/multiway-heurístico — determinístico. Campos capturados são
strings/bools discretos (NÃO os floats de EV do Monte Carlo), pra não ficar frágil por ruído numérico.

Regenerar após uma mudança INTENCIONAL de veredito:  GOLDEN_UPDATE=1 python tests/test_replay_reconciliation_golden.py
"""
import sys, os, tempfile, sqlite3, json

# Determinismo do seed multiway (hash de strings) — precisa valer ANTES de importar o app.
if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from database import schema, repositories

_N_HANDS     = 30
_GOLDEN_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'replay_reconciliation_golden.json')


def _setup_db():
    db = tempfile.mktemp(suffix='_golden.db')
    def gc():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    schema.get_conn = gc
    repositories.get_conn = gc
    import database.schema as sch
    sch.get_conn = gc
    schema.init_db()
    return gc


def _fingerprint(client, headers, tid, hand_ids):
    """Fingerprint dos campos DISCRETOS de veredito de cada ação do hero, por rua. Ordem estável."""
    fp = []
    for hid in hand_ids:
        r = client.get(f'/replay/{tid}/{hid}', headers=headers)
        if r.status_code != 200:
            fp.append([hid, '__status__', r.status_code])
            continue
        data = r.get_json()
        for t in data.get('timeline', []):
            if not t.get('is_hero'):
                continue
            pg = t.get('preflop_gto') or {}
            # Campos AMPLIADOS (pré-requisito do Stage 3): a rede antiga capturava o veredito
            # final, mas não os sinais que as 4 camadas de reconciliação usam pra chegar nele.
            # Sem eles, um refactor podia trocar o CAMINHO (ex.: passar a ler a estratégia do
            # range agregado em vez da mão) e o golden continuar verde porque o resultado
            # coincidia nas mãos deste fixture. Continua tudo DISCRETO — nada de float de EV.
            fp.append([
                hid, t.get('street'), t.get('action'),
                t.get('best_action'), t.get('gto_action'), t.get('gto_label'),
                bool(t.get('is_error')), t.get('gto_coverage'),
                pg.get('scenario'), pg.get('action_quality'),
                (pg.get('recommended_actions') or [None])[0],
                # sinais de ENTRADA da reconciliação
                bool(t.get('gto_spot_mismatch')), bool(pg.get('available')),
                pg.get('coverage_reason'), pg.get('in_range'), pg.get('hand_type'),
                pg.get('stack_bucket'),
                t.get('equity_source'),
                bool(t.get('multiway_advice')),
                # quais ações o solver creditou (ordem estável), não as frequências
                sorted(a.get("action", "") for a in (t.get("gto_strategy") or [])),   # lista: tupla não sobrevive ao round-trip do JSON
            ])
    return fp


def _build_current_fingerprint():
    _setup_db()
    from api.app import app
    app.config['TESTING'] = True
    client = app.test_client()
    client.post('/auth/register', json={'username': 'gold', 'email': 'gold@t.com', 'password': 'pass1234'})
    tok = client.post('/auth/login', json={'email': 'gold@t.com', 'password': 'pass1234'}).get_json()['token']
    H = {'Authorization': f'Bearer {tok}'}

    fixture = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')
    content = open(fixture, encoding='utf-8').read()
    hh = '\n\n\n'.join(content.split('\n\n\n')[:_N_HANDS])
    r = client.post('/analyze', json={'content': hh}, headers=H)
    assert r.status_code == 200, f'/analyze falhou: {r.status_code}'

    conn = schema.get_conn()
    tid = conn.execute("SELECT id FROM tournaments ORDER BY id DESC LIMIT 1").fetchone()['id']
    hand_ids = [row['hand_id'] for row in conn.execute(
        "SELECT DISTINCT hand_id FROM decisions WHERE tournament_id=? ORDER BY hand_id", (tid,)).fetchall()]
    conn.close()
    assert hand_ids, 'nenhuma decisão importada'
    return _fingerprint(client, H, tid, hand_ids)


def test_replay_reconciliation_golden():
    """O veredito do /replay para um torneio real bate com o golden congelado (rede de segurança do
    Stage 3). Se você MUDOU a reconciliação de propósito: rode com GOLDEN_UPDATE=1 e revise o diff."""
    current = _build_current_fingerprint()

    if os.environ.get('GOLDEN_UPDATE') or not os.path.exists(_GOLDEN_PATH):
        os.makedirs(os.path.dirname(_GOLDEN_PATH), exist_ok=True)
        with open(_GOLDEN_PATH, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=1)
        print(f"OK  test_replay_reconciliation_golden (GERADO golden com {len(current)} rows) — "
              f"revise e commite {os.path.basename(_GOLDEN_PATH)}")
        return

    with open(_GOLDEN_PATH, encoding='utf-8') as f:
        golden = json.load(f)

    if current != golden:
        # diff legível das primeiras divergências
        diffs = []
        for i, (c, g) in enumerate(zip(current, golden)):
            if c != g:
                diffs.append(f"  row {i}: golden={g}\n           atual ={c}")
        if len(current) != len(golden):
            diffs.append(f"  contagem: golden={len(golden)} atual={len(current)}")
        raise AssertionError(
            "veredito do /replay divergiu do golden (reconciliação mudou). Se foi INTENCIONAL, "
            "regenere com GOLDEN_UPDATE=1.\n" + "\n".join(diffs[:20]))

    print(f"OK  test_replay_reconciliation_golden ({len(current)} rows do veredito congeladas)")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
