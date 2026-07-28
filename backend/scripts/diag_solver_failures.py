"""
diag_solver_failures.py — o que distingue os spots que o solver FALHOU dos que ele resolveu.

SOMENTE LEITURA:

    python scripts/diag_solver_failures.py            # base inteira
    python scripts/diag_solver_failures.py --prio 1   # só os de uma prioridade (ex.: a dívida)

── O que dá e o que NÃO dá para saber aqui ───────────────────────────────────────────────────

A fila NÃO guarda o motivo da falha: `gto_solver_queue` tem status e mais nada. Os três caminhos
que marcam `failed` são bem diferentes entre si e ficam indistinguíveis na tabela:

  1. o solver não devolveu nada (timeout, queda, remoto fora)  → SILENCIOSO
  2. resolveu mas não convergiu (exploitability > o teto)      → loga "exploitability=... MAX"
  3. exceção no meio                                           → loga "Solver error for"

Ou seja: quem responde "o quê" é o LOG do solver-consumer, e quem responde "em quais spots" é
este script, comparando o payload dos falhados com o dos resolvidos. Os dois juntos fecham a
pergunta; sozinho, nenhum fecha.

    docker compose logs --since 24h solver-consumer | grep -c "exploitability="
    docker compose logs --since 24h solver-consumer | grep -c "Solver error for"

── Por que comparar com os RESOLVIDOS, e não só descrever os falhados ────────────────────────

Descrever só o grupo que falhou responde "como eles são", não "o que os diferencia". Se 80% dos
falhados são de flop mas 80% de TODA a fila também é, flop não explica nada. A coluna que importa
é a taxa de falha DENTRO de cada faixa.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _fetchall, _adapt


def _faixa_stack(bb):
    if bb is None:
        return '?'
    for teto, rot in ((15, '0-15bb'), (25, '15-25bb'), (35, '25-35bb'), (60, '35-60bb')):
        if bb <= teto:
            return rot
    return '60bb+'


def _textura(board):
    naipes = [c[1].lower() for c in board if len(c) >= 2]
    valores = [c[0].upper() for c in board if c]
    if len(set(naipes)) == 1 and len(naipes) >= 3:
        return 'monotone'
    if len(valores) != len(set(valores)):
        return 'pareado'
    if len(set(naipes)) == len(naipes):
        return 'rainbow'
    return '2-tone'


def _tabela(titulo, chave_de, falhados, prontos):
    print(f'\n{titulo}')
    print(f"  {'faixa':<12} {'falhou':>7} {'resolveu':>9} {'total':>7} {'taxa de falha':>14}")
    chaves = set()
    cf, cp = {}, {}
    for grupo, acc in ((falhados, cf), (prontos, cp)):
        for s in grupo:
            k = chave_de(s)
            acc[k] = acc.get(k, 0) + 1
            chaves.add(k)
    for k in sorted(chaves, key=str):
        f, p = cf.get(k, 0), cp.get(k, 0)
        tot = f + p
        pct = f * 100.0 / tot if tot else 0
        alerta = '  <<<' if tot >= 10 and pct >= 70 else ''
        print(f'  {str(k):<12} {f:>7} {p:>9} {tot:>7} {pct:>13.1f}%{alerta}')


def main():
    prio = None
    if '--prio' in sys.argv:
        prio = int(sys.argv[sys.argv.index('--prio') + 1])

    conn = get_conn()
    try:
        cond, params = '', []
        if prio is not None:
            cond, params = ' AND priority = ? ', [prio]
            print(f'== só prioridade {prio} ==')

        rows = _fetchall(conn, _adapt(f"""
            SELECT status, spot_json FROM gto_solver_queue
            WHERE status IN ('failed','done') {cond}
        """), tuple(params))

        falhados, prontos, ilegiveis = [], [], 0
        for r in rows:
            try:
                s = json.loads(r['spot_json'])
            except Exception:
                ilegiveis += 1
                continue
            (falhados if r['status'] == 'failed' else prontos).append(s)

        tot = len(falhados) + len(prontos)
        if not tot:
            print('nada a analisar.'); return
        print(f'falhados: {len(falhados)}  ·  resolvidos: {len(prontos)}  ·  '
              f'taxa global de falha: {len(falhados) * 100.0 / tot:.1f}%')
        if ilegiveis:
            print(f'(payload ilegível ignorado: {ilegiveis})')

        _tabela('POR STREET', lambda s: (s.get('street') or '?'), falhados, prontos)
        _tabela('POR PROFUNDIDADE (stack do herói)',
                lambda s: _faixa_stack(s.get('hero_stack_bb')), falhados, prontos)
        _tabela('ENFRENTA APOSTA?',
                lambda s: 'sim' if float(s.get('facing_size_bb') or 0) > 0 else 'não',
                falhados, prontos)
        _tabela('TEXTURA DO BOARD',
                lambda s: _textura(s.get('board') or []), falhados, prontos)
        _tabela('STACK EFETIVO NO SOLVE (já capado)',
                lambda s: _faixa_stack(s.get('effective_stack_bb')), falhados, prontos)

        print('\nLeitura: a coluna que importa é a TAXA, não a contagem. "<<<" marca faixa com')
        print('pelo menos 10 casos e 70% ou mais de falha — é onde o problema mora.')
        print('\nPara saber o MOTIVO (o banco não guarda), cruze com o log do solver-consumer:')
        print('  grep -c "exploitability="   → não convergiu')
        print('  grep -c "Solver error for"  → exceção')
        print('  o resto do total é o caminho silencioso: timeout ou solver fora do ar.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
