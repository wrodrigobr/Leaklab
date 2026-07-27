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
import sys, os, tempfile, sqlite3, json, hashlib

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
_GOLDEN_SOLVED_PATH = os.path.join(os.path.dirname(__file__), 'fixtures',
                                   'replay_reconciliation_golden_solved.json')


# ── Solver sintético: cobre a camada 2, que o golden "sem solver" não alcança ──────────────────
#
# O buraco: sem nó postflop, `lookup_gto` não devolve estratégia, `_recon_strat` fica vazio e a
# camada 2 (`card_verdict.reconcile_verdict`) NUNCA roda. Ou seja, a única camada já extraída e
# pura era justamente a menos protegida pela rede — e é sobre ela que o Stage 3 mexe.
#
# Rodar o solver de verdade no teste está fora de questão (processo externo, lento, e o resultado
# muda quando o solver muda — golden não pode depender disso). A saída é um solver SINTÉTICO:
# determinístico, em memória, derivado do próprio `spot_hash`. Ele não pretende estar certo sobre
# poker; pretende ser SEMPRE O MESMO, que é o que um characterization test precisa.
#
# Duas escolhas deliberadas:
#   · o menu segue o contexto (enfrentando aposta → fold/call/raise; sem aposta → check/bet), senão
#     `gto_spot_mismatch` dispararia e pularia as camadas 2-4 — o oposto do objetivo;
#   · a estratégia DA MÃO é uma rotação da estratégia do RANGE, então o topo da mão difere do topo
#     do range. É exatamente o caso que motivou `card_verdict` ("o range folda 63%, mas A2s levanta
#     93%"). Se as duas fossem iguais, a regra de prioridade passaria despercebida num refactor.
class _SyntheticSolver:
    _NO_BET  = [[('check', 0.92), ('bet_75pct', 0.08)],
                [('check', 0.54), ('bet_75pct', 0.46)],
                [('bet_75pct', 0.88), ('check', 0.12)]]
    _FACING  = [[('call', 0.90), ('fold', 0.10)],
                [('call', 0.52), ('fold', 0.30), ('raise_2.5x', 0.18)],
                [('fold', 0.86), ('call', 0.14)]]

    def __init__(self):
        self.spots = {}          # spot_hash → entradas que o produziram
        self._real_hash = None

    # A memorização acontece no próprio `compute_spot_hash`: assim o teste nunca recalcula um hash
    # por conta própria (duplicar essa regra seria criar a segunda fonte de verdade que o Stage 3
    # existe para eliminar). Só respondemos hashes que o código de produção realmente pediu.
    def _hash(self, street, position, board, hero_hand, hero_stack_bb,
              facing_size_bb=0.0, pot_type=''):
        h = self._real_hash(street, position, board, hero_hand, hero_stack_bb,
                            facing_size_bb, pot_type)
        if street.lower() != 'preflop' and hero_hand:
            self.spots.setdefault(h, {
                'street': street.lower(), 'position': position.upper(),
                'board': list(board or []), 'hero_hand': list(hero_hand),
                'stack_bb': hero_stack_bb, 'facing': float(facing_size_bb or 0),
            })
        return h

    def _template(self, spot_hash, facing):
        pool = self._FACING if facing > 0 else self._NO_BET
        i = int(hashlib.sha1(spot_hash.encode()).hexdigest()[:8], 16) % len(pool)
        return pool[i]

    def get_gto_node(self, spot_hash):
        spot = self.spots.get(spot_hash)
        if not spot:
            return None      # hash genérico (sem mão) fica sem nó → o exato é que vence
        tmpl = self._template(spot_hash, spot['facing'])
        return {
            'spot_hash': spot_hash, 'tree_hash': 'tree_' + spot_hash,
            'street': spot['street'], 'position': spot['position'],
            'board': json.dumps(spot['board']), 'hero_hand': ''.join(spot['hero_hand']),
            'stack_bucket': '', 'gto_action': tmpl[0][0], 'gto_freq': tmpl[0][1],
            'ev_diff': 0.0, 'exploitability_pct': 2.0, 'iterations': 500,
            'source': 'solver_cli', 'is_aggregate': 0,
            'strategy_json': json.dumps({a: {'frequency': f, 'combos': 100} for a, f in tmpl}),
        }

    def get_tree_strategy(self, tree_hash):
        spot = self.spots.get((tree_hash or '')[5:])   # 'tree_' + spot_hash
        if not spot:
            return None
        tmpl  = self._template(tree_hash[5:], spot['facing'])
        freqs = [f for _, f in tmpl]
        return {
            'board':   spot['board'],
            'actions': [a for a, _ in tmpl],
            # rotação: o topo DA MÃO ≠ topo do RANGE (ver comentário do bloco)
            'hand_table': [{
                'hand':  ''.join(spot['hero_hand']),
                'freqs': freqs[-1:] + freqs[:-1],
                'evs':   [round(1.5 - 0.6 * i, 2) for i in range(len(tmpl))],
                'weight': 1.0,
            }],
        }

    def install(self):
        from leaklab import gto_utils
        from database import repositories as repo
        self._real_hash = gto_utils.compute_spot_hash
        self._saved = (gto_utils.compute_spot_hash, repo.get_gto_node, repo.get_tree_strategy)
        gto_utils.compute_spot_hash = self._hash
        repo.get_gto_node      = self.get_gto_node
        repo.get_tree_strategy = self.get_tree_strategy

    def uninstall(self):
        from leaklab import gto_utils
        from database import repositories as repo
        gto_utils.compute_spot_hash, repo.get_gto_node, repo.get_tree_strategy = self._saved


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
                # QUAL camada decidiu. Sem isto o golden protege o resultado mas não o caminho:
                # um refactor podia trocar quem decide e passar verde porque as duas camadas
                # concordavam nas mãos deste fixture. Última posição de propósito, para que
                # acrescentá-la fosse verificável como "só apendou coluna".
                t.get('verdict_layer'),
            ])
    return fp


def _build_current_fingerprint(solver=None):
    _setup_db()
    if solver:
        # instalado ANTES do /analyze de propósito: em produção o nó já existe no banco quando o
        # torneio é importado, e import e replay leem o mesmo nó. Instalar só no replay simularia
        # um estado que nunca acontece.
        solver.install()
    try:
        return _fingerprint_run()
    finally:
        if solver:
            solver.uninstall()


def _fingerprint_run():
    from api.app import app
    # `_REPLAY_CACHE` é de processo, TTL 5min, chaveado por (tournament_id, hand_id, user_id) — e as
    # três chaves se repetem entre execuções, porque cada uma começa num banco novo onde o torneio e
    # o usuário nascem com id 1. Sem limpar, a SEGUNDA execução no mesmo processo recebe a resposta
    # da primeira e o handler nem roda. Foi exatamente o que aconteceu: o golden "com solver" saiu
    # idêntico ao "sem solver" e teria passado para sempre, medindo nada.
    import api.app as _appmod
    _appmod._REPLAY_CACHE.clear()
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


def _assert_golden(current, path, nome):
    if os.environ.get('GOLDEN_UPDATE') or not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=1)
        print(f"OK  {nome} (GERADO golden com {len(current)} rows) — "
              f"revise e commite {os.path.basename(path)}")
        return

    with open(path, encoding='utf-8') as f:
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

    print(f"OK  {nome} ({len(current)} rows do veredito congeladas)")


def test_replay_reconciliation_golden():
    """O veredito do /replay para um torneio real bate com o golden congelado (rede de segurança do
    Stage 3). Se você MUDOU a reconciliação de propósito: rode com GOLDEN_UPDATE=1 e revise o diff."""
    _assert_golden(_build_current_fingerprint(), _GOLDEN_PATH,
                   'test_replay_reconciliation_golden')


def test_replay_reconciliation_golden_com_solver():
    """MESMA rede, agora com nós postflop presentes — o caminho que o golden sem solver não toca.

    Sem nó, `lookup_gto` volta vazio, `_recon_strat` fica None e a camada 2 (`card_verdict`) é
    pulada inteira. Com o solver sintético instalado, ela roda para todo spot postflop do hero: a
    estratégia viva sobrescreve o label armazenado, a estratégia da MÃO tem prioridade sobre a do
    RANGE, e onde o spot é multiway a camada 4 sobrescreve a 2. Essa ordem de precedência é o que
    o Stage 3 vai tornar explícita — e é o que este golden congela antes de a mudança começar."""
    current = _build_current_fingerprint(_SyntheticSolver())

    # PROVA DE VIDA, antes de comparar com o próprio golden. Um characterization test que não
    # exercita o caminho que diz exercitar passa para sempre sem medir nada — e foi o que
    # aconteceu na primeira versão deste teste (o cache de replay servia a resposta da execução
    # anterior). Se a presença dos nós não muda NADA na saída, a camada 2 não rodou: falhe alto,
    # em vez de congelar um golden vazio.
    with open(_GOLDEN_PATH, encoding='utf-8') as f:
        sem_solver = json.load(f)
    mudou = sum(1 for a, b in zip(sem_solver, current) if a != b)
    assert mudou >= 5, (
        f"o solver sintético não alterou o veredito ({mudou} linhas diferentes) — a camada 2 não "
        f"foi exercitada e este golden não protege nada. Verifique o cache de replay e os patches.")

    _assert_golden(current, _GOLDEN_SOLVED_PATH, 'test_replay_reconciliation_golden_com_solver')
    print(f"    (camada 2 exercitada: {mudou} linhas divergem do golden sem solver)")


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
