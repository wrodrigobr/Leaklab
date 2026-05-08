"""
test_gto_comparison.py — Compara recomendações do engine LeakLabs com dados GTO
para um torneio completo, por street.

Uso standalone:
    python tests/test_gto_comparison.py                      # torneio mais recente
    python tests/test_gto_comparison.py --tournament-id=42   # torneio específico
    python tests/test_gto_comparison.py --all                # todos os torneios (agregado)
    python tests/test_gto_comparison.py --user-id=1          # torneios do usuário 1

Uso como suite de testes (CI):
    python tests/test_gto_comparison.py                      # valida estrutura da infra
"""
from __future__ import annotations
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from collections import defaultdict
from database.schema import get_conn
from leaklab.gto_utils import compute_spot_hash

STREETS_ORDER = ['preflop', 'flop', 'turn', 'river']
LABEL_EMOJI = {
    'standard':      '✓',
    'marginal':      '△',
    'small_mistake': '✗',
    'clear_mistake': '✗✗',
}


# ── Data layer ────────────────────────────────────────────────────────────────

def fetch_tournament_decisions(tournament_db_id: int) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT d.id, d.hand_id, d.street, d.position, d.hero_cards, d.board,
                   d.action_taken, d.best_action, d.label, d.score,
                   d.stack_bb, d.m_ratio, d.icm_pressure, d.pot_size, d.facing_bet
            FROM decisions d
            WHERE d.tournament_id = ?
            ORDER BY d.id
        """, (tournament_db_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_tournament_info(tournament_db_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT id, tournament_id, tournament_name, hero, played_at,
                   decisions_count, standard_pct, user_id
            FROM tournaments WHERE id = ?
        """, (tournament_db_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_latest_tournament(user_id: int | None = None) -> dict | None:
    conn = get_conn()
    try:
        if user_id:
            row = conn.execute(
                "SELECT id FROM tournaments WHERE user_id = ? ORDER BY imported_at DESC LIMIT 1",
                (user_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM tournaments ORDER BY imported_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_all_tournament_ids(user_id: int | None = None) -> list[int]:
    conn = get_conn()
    try:
        if user_id:
            rows = conn.execute(
                "SELECT id FROM tournaments WHERE user_id = ? ORDER BY imported_at DESC",
                (user_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id FROM tournaments ORDER BY imported_at DESC"
            ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def lookup_gto(spot_hash: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT gto_action, gto_freq, ev_diff, source FROM gto_nodes WHERE spot_hash = ?",
            (spot_hash,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── Comparison engine ─────────────────────────────────────────────────────────

def compare_tournament(tournament_db_id: int) -> dict:
    """
    Compara todas as decisões de um torneio contra gto_nodes.
    Retorna dict com breakdown completo por street.
    """
    info  = fetch_tournament_info(tournament_db_id)
    decis = fetch_tournament_decisions(tournament_db_id)

    stats_total = {'decisions': 0, 'with_gto': 0, 'agreements': 0}
    by_street: dict[str, dict] = {s: {'decisions': 0, 'with_gto': 0, 'agreements': 0} for s in STREETS_ORDER}
    divergences: list[dict] = []
    missing_spots: dict[str, dict] = {}  # hash → spot info for bot

    for d in decis:
        stats_total['decisions'] += 1
        street   = (d.get('street') or '').lower()
        position = (d.get('position') or '').upper()
        hand_raw = d.get('hero_cards') or ''
        board_raw = d.get('board') or '[]'
        stack_bb = float(d.get('stack_bb') or 30.0)

        try:
            board = json.loads(board_raw) if isinstance(board_raw, str) else board_raw
        except Exception:
            board = []

        hero_hand = hand_raw.split() if isinstance(hand_raw, str) else []

        if street and position and hero_hand:
            spot_hash = compute_spot_hash(street, position, board, hero_hand, stack_bb)
        else:
            spot_hash = None

        if street in by_street:
            by_street[street]['decisions'] += 1

        gto = lookup_gto(spot_hash) if spot_hash else None

        if gto:
            stats_total['with_gto'] += 1
            if street in by_street:
                by_street[street]['with_gto'] += 1

            engine_action = (d.get('action_taken') or '').lower()
            gto_action    = (gto['gto_action'] or '').lower()
            agree = engine_action == gto_action

            if agree:
                stats_total['agreements'] += 1
                if street in by_street:
                    by_street[street]['agreements'] += 1
            else:
                divergences.append({
                    'decision_id':    d['id'],
                    'hand_id':        d.get('hand_id', '?'),
                    'street':         street,
                    'position':       position,
                    'hero_cards':     hand_raw,
                    'board':          board,
                    'stack_bb':       stack_bb,
                    'label':          d.get('label', '?'),
                    'score':          d.get('score', 0),
                    'engine_action':  d.get('action_taken', '?'),
                    'best_action':    d.get('best_action', '?'),
                    'gto_action':     gto['gto_action'],
                    'gto_freq':       gto['gto_freq'],
                    'ev_diff':        gto.get('ev_diff'),
                    'spot_hash':      spot_hash,
                })
        else:
            if spot_hash and spot_hash not in missing_spots:
                missing_spots[spot_hash] = {
                    'spot_hash': spot_hash,
                    'street':    street,
                    'position':  position,
                    'board':     board,
                    'hero_hand': hero_hand,
                    'stack_bb':  stack_bb,
                    'count':     1,
                }
            elif spot_hash:
                missing_spots[spot_hash]['count'] += 1

    return {
        'info':          info,
        'stats_total':   stats_total,
        'by_street':     by_street,
        'divergences':   sorted(divergences, key=lambda x: x['score'], reverse=True),
        'missing_spots': sorted(missing_spots.values(), key=lambda x: x['count'], reverse=True),
    }


# ── Report printer ────────────────────────────────────────────────────────────

def _pct(n: int, total: int) -> str:
    if total == 0: return '  -  '
    return f'{n/total*100:5.1f}%'


def print_report(result: dict, verbose: bool = True) -> None:
    info  = result['info'] or {}
    st    = result['stats_total']
    bs    = result['by_street']
    divs  = result['divergences']
    miss  = result['missing_spots']

    name = info.get('tournament_name') or info.get('tournament_id') or f"ID {info.get('id', '?')}"
    hero = info.get('hero', '?')
    std  = info.get('standard_pct')
    std_str = f'{std:.1f}%' if std is not None else '?'

    print()
    print('=' * 68)
    print(f'  GTO COMPARISON REPORT')
    print(f'  Torneio : {name}')
    print(f'  Hero    : {hero}  |  Standard%: {std_str}')
    print('=' * 68)

    total = st['decisions']
    with_gto = st['with_gto']
    agrees   = st['agreements']

    print()
    print('COBERTURA GTO')
    print(f'  Total de decisoes : {total}')
    print(f'  Com dados GTO     : {with_gto}  ({_pct(with_gto, total)})')
    print(f'  Sem dados GTO     : {total - with_gto}  ({_pct(total - with_gto, total)})  <- spots p/ o bot coletar')

    if with_gto > 0:
        print()
        print('CONCORDANCIA (decisoes com GTO)')
        print(f'  Engine == GTO : {agrees} / {with_gto}  ({_pct(agrees, with_gto)})')
        print(f'  Divergencias  : {with_gto - agrees} / {with_gto}  ({_pct(with_gto - agrees, with_gto)})')

    print()
    print('POR STREET')
    print(f'  {"Street":<9} | {"Decisoes":>8} | {"Cobertura GTO":>14} | {"Concordancia":>14}')
    print(f'  {"-"*9}-+-{"-"*8}-+-{"-"*14}-+-{"-"*14}')
    for s in STREETS_ORDER:
        sd = bs[s]
        d  = sd['decisions']
        g  = sd['with_gto']
        a  = sd['agreements']
        cov_str = f'{g:>4} ({_pct(g, d)})' if d > 0 else '   -'
        agr_str = f'{a:>4}/{g:<4} ({_pct(a, g)})' if g > 0 else '   -'
        print(f'  {s:<9} | {d:>8} | {cov_str:>14} | {agr_str:>14}')

    if divs and verbose:
        print()
        print(f'DIVERGENCIAS ({len(divs)} spots onde engine != GTO)')
        print(f'  {"Hand":<12} {"Street":<8} {"Pos":<5} {"Score":>6} {"Label":<14} {"Engine":<8} {"GTO":<8} {"Freq":>6} {"EV diff":>8}')
        print(f'  {"-"*12} {"-"*8} {"-"*5} {"-"*6} {"-"*14} {"-"*8} {"-"*8} {"-"*6} {"-"*8}')
        for d in divs[:30]:
            ev = f'{d["ev_diff"]:+.2f}' if d.get('ev_diff') is not None else '    -'
            label = LABEL_EMOJI.get(d['label'], '?') + ' ' + (d['label'] or '?')
            hand_id = str(d.get('hand_id', '?'))[:12]
            print(
                f'  {hand_id:<12} {d["street"]:<8} {d["position"]:<5} '
                f'{d["score"]:>6.3f} {label:<14} '
                f'{str(d["engine_action"]).upper():<8} {str(d["gto_action"]).upper():<8} '
                f'{d["gto_freq"]:>6.1%} {ev:>8}'
            )
        if len(divs) > 30:
            print(f'  ... e mais {len(divs)-30} divergencias')

    if miss:
        print()
        limit = 15 if verbose else 5
        print(f'TOP {limit} SPOTS FALTANTES (para o bot coletar)')
        print(f'  {"Hash":<18} {"Street":<8} {"Pos":<5} {"Stack bucket":<14} {"Ocorrencias":>11}')
        print(f'  {"-"*18} {"-"*8} {"-"*5} {"-"*14} {"-"*11}')
        from leaklab.gto_utils import stack_bucket as _sb
        for m in miss[:limit]:
            sb = _sb(float(m['stack_bb']))
            print(f'  {m["spot_hash"]:<18} {m["street"]:<8} {m["position"]:<5} {sb:<14} {m["count"]:>11}')

    print()


def print_aggregate_report(results: list[dict]) -> None:
    total_d  = sum(r['stats_total']['decisions'] for r in results)
    total_g  = sum(r['stats_total']['with_gto']  for r in results)
    total_a  = sum(r['stats_total']['agreements'] for r in results)
    total_t  = len(results)

    by_street_agg: dict[str, dict] = {s: {'decisions': 0, 'with_gto': 0, 'agreements': 0} for s in STREETS_ORDER}
    for r in results:
        for s in STREETS_ORDER:
            for k in ('decisions', 'with_gto', 'agreements'):
                by_street_agg[s][k] += r['by_street'][s][k]

    all_divs = [d for r in results for d in r['divergences']]

    print()
    print('=' * 68)
    print(f'  GTO COMPARISON REPORT — AGREGADO ({total_t} torneios)')
    print('=' * 68)
    print()
    print('TOTAIS')
    print(f'  Decisoes           : {total_d}')
    print(f'  Com dados GTO      : {total_g}  ({_pct(total_g, total_d)})')
    if total_g > 0:
        print(f'  Concordancia total : {total_a} / {total_g}  ({_pct(total_a, total_g)})')

    print()
    print('POR STREET')
    print(f'  {"Street":<9} | {"Decisoes":>8} | {"Cobertura":>10} | {"Concordancia":>14}')
    print(f'  {"-"*9}-+-{"-"*8}-+-{"-"*10}-+-{"-"*14}')
    for s in STREETS_ORDER:
        sd = by_street_agg[s]
        print(
            f'  {s:<9} | {sd["decisions"]:>8} | '
            f'{sd["with_gto"]:>4} ({_pct(sd["with_gto"], sd["decisions"])}) | '
            f'{sd["agreements"]:>4}/{sd["with_gto"]:<4} ({_pct(sd["agreements"], sd["with_gto"])})'
        )

    if all_divs:
        print()
        print(f'DISTRIBUICAO DE DIVERGENCIAS POR STREET')
        by_s: dict[str, int] = defaultdict(int)
        for d in all_divs:
            by_s[d['street']] += 1
        for s in STREETS_ORDER:
            n = by_s.get(s, 0)
            bar = '█' * min(n, 40)
            print(f'  {s:<9} {n:>4}  {bar}')
    print()


# ── Test functions (CI-compatible) ────────────────────────────────────────────

_TESTS_PASSED = 0
_TESTS_FAILED = 0


def _ok(msg: str) -> None:
    global _TESTS_PASSED
    _TESTS_PASSED += 1
    print(f'OK  {msg}')


def _fail(msg: str, detail: str = '') -> None:
    global _TESTS_FAILED
    _TESTS_FAILED += 1
    print(f'FAIL {msg}' + (f' | {detail}' if detail else ''))


def test_gto_utils_hash_determinism():
    """Hash idêntico para o mesmo spot com inputs em ordens diferentes."""
    h1 = compute_spot_hash('flop', 'BTN', ['Ah','Kd','2c'], ['As','Ks'], 25.0)
    h2 = compute_spot_hash('FLOP', 'btn', ['2c','Kd','Ah'], ['Ks','As'], 25.0)
    if h1 == h2 and len(h1) == 16:
        _ok(f'test_gto_utils_hash_determinism | hash={h1}')
    else:
        _fail('test_gto_utils_hash_determinism', f'h1={h1} h2={h2}')


def test_gto_utils_hash_varies():
    """Hashes diferentes para spots diferentes."""
    h1 = compute_spot_hash('flop', 'BTN', ['Ah','Kd','2c'], ['As','Ks'], 25.0)
    h2 = compute_spot_hash('turn', 'BTN', ['Ah','Kd','2c'], ['As','Ks'], 25.0)
    h3 = compute_spot_hash('flop', 'CO',  ['Ah','Kd','2c'], ['As','Ks'], 25.0)
    if h1 != h2 and h1 != h3 and h2 != h3:
        _ok('test_gto_utils_hash_varies')
    else:
        _fail('test_gto_utils_hash_varies', f'h1={h1} h2={h2} h3={h3}')


def test_gto_table_exists():
    """Tabela gto_nodes existe e é acessível."""
    conn = get_conn()
    try:
        row = conn.execute('SELECT COUNT(*) AS n FROM gto_nodes').fetchone()
        total = row['n']
        _ok(f'test_gto_table_exists | rows={total}')
    except Exception as e:
        _fail('test_gto_table_exists', str(e))
    finally:
        conn.close()


def test_gto_insert_and_lookup():
    """Insert de nó GTO e lookup pelo hash."""
    from database.repositories import insert_gto_nodes, get_gto_node, get_gto_stats
    try:
        spot = {
            'street': 'flop', 'position': 'BTN',
            'board': ['Ah','Kd','2c'], 'hero_hand': ['As','Ks'],
            'hero_stack_bb': 25.0, 'gto_action': 'raise',
            'gto_freq': 0.67, 'ev_diff': 1.2, 'source': 'test',
        }
        n = insert_gto_nodes([spot])
        assert n == 1
        h = compute_spot_hash('flop', 'BTN', ['Ah','Kd','2c'], ['As','Ks'], 25.0)
        node = get_gto_node(h)
        assert node is not None
        assert node['gto_action'] == 'raise'
        assert abs(node['gto_freq'] - 0.67) < 0.001
        assert abs((node['ev_diff'] or 0) - 1.2) < 0.001
        _ok(f'test_gto_insert_and_lookup | hash={h}')
    except Exception as e:
        _fail('test_gto_insert_and_lookup', str(e))


def test_gto_comparison_structure():
    """compare_tournament() retorna estrutura correta mesmo sem GTO data."""
    conn = get_conn()
    try:
        row = conn.execute('SELECT id FROM tournaments LIMIT 1').fetchone()
    finally:
        conn.close()

    if not row:
        _ok('test_gto_comparison_structure | sem torneios no DB, pulando')
        return

    try:
        result = compare_tournament(row[0])
        assert 'stats_total' in result
        assert 'by_street' in result
        assert 'divergences' in result
        assert 'missing_spots' in result
        assert 'decisions' in result['stats_total']
        for s in STREETS_ORDER:
            assert s in result['by_street']
        _ok(f'test_gto_comparison_structure | {result["stats_total"]["decisions"]} decisoes analisadas')
    except Exception as e:
        _fail('test_gto_comparison_structure', str(e))


def _ensure_test_user(conn) -> int:
    """Cria ou reutiliza um usuário de teste. Retorna o user_id."""
    row = conn.execute("SELECT id FROM users WHERE username = 'gto_test_user'").fetchone()
    if row:
        return row[0]
    conn.execute("""
        INSERT INTO users (username, email, password_hash, role)
        VALUES ('gto_test_user', 'gto_test@test.local', 'x', 'player')
    """)
    conn.commit()
    return conn.execute("SELECT id FROM users WHERE username = 'gto_test_user'").fetchone()[0]


def test_comparison_agreement_detection():
    """Cria decisão sintética com GTO node correspondente e verifica detecção de concordância."""
    from database.repositories import insert_gto_nodes
    conn = get_conn()
    try:
        u_id = _ensure_test_user(conn)
        conn.execute("""
            INSERT INTO tournaments (user_id, tournament_id, site, hero, played_at, hands_count, decisions_count)
            VALUES (?, 'test_gto_cmp', 'test', 'hero_gto', '2024-01-01', 1, 1)
        """, (u_id,))
        t_id = conn.execute(
            "SELECT id FROM tournaments WHERE tournament_id = 'test_gto_cmp'"
        ).fetchone()[0]
        conn.execute("""
            INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, board,
                                   action_taken, best_action, label, score, stack_bb)
            VALUES (?, 'HH111', 'flop', 'BTN', 'As Ks', '["Ah","Kd","2c"]', 'raise', 'raise', 'standard', 0.1, 25.0)
        """, (t_id,))
        conn.commit()

        insert_gto_nodes([{
            'street': 'flop', 'position': 'BTN',
            'board': ['Ah','Kd','2c'], 'hero_hand': ['As','Ks'],
            'hero_stack_bb': 25.0, 'gto_action': 'raise',
            'gto_freq': 0.72, 'ev_diff': 0.8, 'source': 'test',
        }])

        result = compare_tournament(t_id)
        assert result['stats_total']['with_gto'] == 1, 'deveria ter 1 decisao com GTO'
        assert result['stats_total']['agreements'] == 1, 'deveria ter 1 concordancia'
        assert len(result['divergences']) == 0, 'nao deveria ter divergencias'
        _ok('test_comparison_agreement_detection')
    except Exception as e:
        _fail('test_comparison_agreement_detection', str(e))
    finally:
        try:
            conn.execute("DELETE FROM decisions WHERE hand_id = 'HH111'")
            conn.execute("DELETE FROM tournaments WHERE tournament_id = 'test_gto_cmp'")
            conn.commit()
        except Exception:
            pass
        conn.close()


def test_comparison_divergence_detection():
    """Detecta divergência quando engine e GTO discordam."""
    from database.repositories import insert_gto_nodes
    conn = get_conn()
    try:
        u_id = _ensure_test_user(conn)
        conn.execute("""
            INSERT INTO tournaments (user_id, tournament_id, site, hero, played_at, hands_count, decisions_count)
            VALUES (?, 'test_gto_div', 'test', 'hero_gto', '2024-01-01', 1, 1)
        """, (u_id,))
        t_id = conn.execute(
            "SELECT id FROM tournaments WHERE tournament_id = 'test_gto_div'"
        ).fetchone()[0]
        conn.execute("""
            INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, board,
                                   action_taken, best_action, label, score, stack_bb)
            VALUES (?, 'HH222', 'turn', 'CO', 'Jh Th', '["9d","8c","2s","As"]', 'fold', 'call', 'clear_mistake', 0.7, 15.0)
        """, (t_id,))
        conn.commit()

        insert_gto_nodes([{
            'street': 'turn', 'position': 'CO',
            'board': ['9d','8c','2s','As'], 'hero_hand': ['Jh','Th'],
            'hero_stack_bb': 15.0, 'gto_action': 'call',
            'gto_freq': 0.88, 'ev_diff': 1.5, 'source': 'test',
        }])

        result = compare_tournament(t_id)
        assert result['stats_total']['with_gto'] == 1
        assert result['stats_total']['agreements'] == 0
        assert len(result['divergences']) == 1
        div = result['divergences'][0]
        assert div['engine_action'] == 'fold'
        assert div['gto_action'] == 'call'
        _ok('test_comparison_divergence_detection')
    except Exception as e:
        _fail('test_comparison_divergence_detection', str(e))
    finally:
        try:
            conn.execute("DELETE FROM decisions WHERE hand_id = 'HH222'")
            conn.execute("DELETE FROM tournaments WHERE tournament_id = 'test_gto_div'")
            conn.commit()
        except Exception:
            pass
        conn.close()


def _run_unit_tests():
    print('Rodando testes unitarios de GTO comparison...\n')
    test_gto_utils_hash_determinism()
    test_gto_utils_hash_varies()
    test_gto_table_exists()
    test_gto_insert_and_lookup()
    test_gto_comparison_structure()
    test_comparison_agreement_detection()
    test_comparison_divergence_detection()
    print(f'\n{"=" * 50}')
    print(f'Total: {_TESTS_PASSED + _TESTS_FAILED} | Passed: {_TESTS_PASSED} | Failed: {_TESTS_FAILED}')


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='GTO Comparison Report')
    parser.add_argument('--tournament-id', type=int, default=None,
                        help='ID interno do torneio no banco')
    parser.add_argument('--user-id', type=int, default=None,
                        help='Filtrar por user_id')
    parser.add_argument('--all', action='store_true',
                        help='Comparar todos os torneios (modo agregado)')
    parser.add_argument('--no-verbose', action='store_true',
                        help='Ocultar detalhes de divergencias')
    args = parser.parse_args()

    verbose = not args.no_verbose

    if args.all:
        ids = fetch_all_tournament_ids(user_id=args.user_id)
        if not ids:
            print('Nenhum torneio encontrado no banco.')
            return
        print(f'Analisando {len(ids)} torneio(s)...')
        results = []
        for tid in ids:
            r = compare_tournament(tid)
            print_report(r, verbose=False)
            results.append(r)
        print_aggregate_report(results)
    else:
        if args.tournament_id:
            tid = args.tournament_id
        else:
            row = fetch_latest_tournament(user_id=args.user_id)
            if not row:
                print('Nenhum torneio encontrado no banco.')
                return
            tid = row['id']
        result = compare_tournament(tid)
        print_report(result, verbose=verbose)


if __name__ == '__main__':
    # Se chamado sem argumentos CLI específicos em modo teste (CI),
    # executa testes unitários
    if len(sys.argv) == 1:
        _run_unit_tests()
    else:
        main()
