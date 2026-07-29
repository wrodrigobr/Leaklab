"""
purge_bad_range_nodes.py — apaga os nós que EU gerei hoje com as ranges trocadas, e devolve as
decisões afetadas ao estado honesto ("sem cobertura") até que sejam re-solvadas direito.

    python scripts/purge_bad_range_nodes.py            # SIMULA (padrão)
    python scripts/purge_bad_range_nodes.py --exec     # aplica

── O que aconteceu ───────────────────────────────────────────────────────────────────────────

Em 2026-07-28, `requeue_board_hash_spots.py` foi executado numa versão que ainda copiava as duas
linhas erradas do enfileiramento:

    oop_range = _DEFAULT_RANGES[vilão]     # range do vilão no lugar do OOP
    ip_range  = _DEFAULT_RANGES[herói]     # range do herói no lugar do IP

O solver devolve o player 0, que é o OOP. Então a estratégia gravada é "o que a range do VILÃO
faria sentada na cadeira do herói". E, diferente do bug original do board, estes nós ficaram com
a chave CERTA: o produto os encontra, serve, e a reconciliação já escreveu o veredito deles nas
decisões. Ou seja, conselho ERRADO no ar — o dano que o bug original nunca chegou a causar.

O conserto das ranges entrou depois (`resolve_solver_ranges`), então re-enfileirar agora produz
o nó certo. Falta remover o errado.

── Por que apagar, e não só re-solvar por cima ───────────────────────────────────────────────

`insert_gto_nodes` tem guarda que PRESERVA o nó melhor: um solve novo com exploitability pior
seria descartado, e o nó errado sobreviveria. Apagar primeiro é o que garante que o certo entre.

E as decisões têm o `gto_label` limpo junto, de propósito. Sem isso, o veredito errado fica na
tela até o re-solve terminar — e para sempre, se aquele spot falhar no solver. "Sem cobertura" é
honesto; veredito errado não é. A ordem certa é sempre retirar a afirmação primeiro.

── Como os nós são identificados ─────────────────────────────────────────────────────────────

Pela `priority = 9` na fila. Nada mais na base grava esse valor: a prioridade do produto usa 5 a
8, e o 9 foi outro engano meu na mesma execução. Ele acabou virando a marca exata do lote.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _fetchall, _adapt
from leaklab.gto_utils import compute_spot_hash, board_for_street, normalize_cards, normalize_position

_MARCA = 9   # a prioridade que só o lote errado usou


def _board(bruto):
    if not bruto:
        return []
    if isinstance(bruto, str):
        bruto = bruto.strip()
        if not bruto.startswith('['):
            return bruto.split()
        try:
            return json.loads(bruto)
        except Exception:
            return []
    return list(bruto)


def main():
    executar = '--exec' in sys.argv[1:]
    conn = get_conn()
    try:
        suspeitos = {r['spot_hash'] for r in _fetchall(conn, _adapt(
            "SELECT spot_hash FROM gto_solver_queue WHERE priority = ?"), (_MARCA,))}
        if not suspeitos:
            print(f'nenhum spot com prioridade {_MARCA} — nada a fazer.'); return

        existentes = {r['spot_hash'] for r in _fetchall(conn, _adapt(
            "SELECT spot_hash FROM gto_nodes"), ())}
        alvos = suspeitos & existentes
        print(f'spots do lote (prioridade {_MARCA}): {len(suspeitos)}')
        print(f'destes, com nó gravado ............: {len(alvos)}   <- os que serão apagados')

        if not alvos:
            print('nenhum nó gravado; nada a apagar.')
            return

        # Decisões cujo veredito veio (ou pode ter vindo) de um desses nós.
        decisoes = _fetchall(conn, _adapt("""
            SELECT id, street, position, board, hero_cards, stack_bb, facing_bet
            FROM decisions
            WHERE lower(street) IN ('flop','turn','river')
              AND gto_label IS NOT NULL AND gto_label <> ''
              AND position IS NOT NULL AND stack_bb IS NOT NULL
        """), ())
        afetadas = []
        for d in decisoes:
            street = (d['street'] or '').lower()
            b = board_for_street(_board(d['board']), street)
            if not b:
                continue
            mao = normalize_cards(d['hero_cards'])
            st = float(d['stack_bb'] or 30)
            fa = float(d['facing_bet'] or 0)
            pos = normalize_position(d['position'] or '')
            for _m, _f in ((mao, fa), ([], fa), ([], 0.0)):
                if _f != fa and fa != 0:
                    continue
                if compute_spot_hash(street, pos, b, _m, st, _f) in alvos:
                    afetadas.append(d['id'])
                    break

        print(f'decisões com veredito vindo deles .: {len(afetadas)}   <- voltam a "sem cobertura"')

        if not executar:
            print('\nSIMULAÇÃO. Rode com --exec para aplicar.')
            print('Depois de aplicar: rode requeue_board_hash_spots.py --exec (já corrigido)')
            print('para re-solvar com as ranges certas.')
            return

        # Limpa o VEREDITO primeiro: se algo falhar depois, o pior estado é "sem cobertura",
        # nunca "veredito errado ainda no ar".
        n_dec = 0
        for i in range(0, len(afetadas), 200):
            lote = afetadas[i:i + 200]
            marcas = ','.join(['?'] * len(lote))
            cur = conn.execute(_adapt(
                f"UPDATE decisions SET gto_label = NULL, gto_action = NULL "
                f"WHERE id IN ({marcas})"), tuple(lote))
            n_dec += (cur.rowcount or 0)
        conn.commit()
        print(f'\ndecisões limpas: {n_dec}')

        lista = list(alvos)
        n_no = 0
        for i in range(0, len(lista), 200):
            lote = lista[i:i + 200]
            marcas = ','.join(['?'] * len(lote))
            cur = conn.execute(_adapt(
                f"DELETE FROM gto_nodes WHERE spot_hash IN ({marcas})"), tuple(lote))
            n_no += (cur.rowcount or 0)
        conn.commit()
        print(f'nós apagados  : {n_no}')
        print('\nAgora rode: scripts/requeue_board_hash_spots.py --exec')
        print('(já corrigido: ranges pelos jogadores certos, hero_is_ip, prioridade 1)')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
