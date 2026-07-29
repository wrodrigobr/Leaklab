"""
diag_labels_pendentes.py — por que uma decisão continua sem veredito mesmo com o nó GTO no banco.

SOMENTE LEITURA. Roda no host de prod:

    python scripts/diag_labels_pendentes.py rodrigo@email.com

── A pergunta ────────────────────────────────────────────────────────────────────────────────

Depois do conserto do bug do board, 91 spots foram re-solvados e o `diag_board_hash_impact`
passou a contar 107 decisões na linha "já cobertas". Esse rótulo engana: aquela consulta só olha
decisões com `gto_label` NULO, então "já cobertas" quer dizer **o nó existe e o veredito nunca
foi escrito na decisão**. Para o jogador, elas seguem mudas.

Solvar e ROTULAR são passos diferentes. Este script mede o segundo.

── Seção 1: a reconciliação alcança essas decisões? ──────────────────────────────────────────

`_reconcile_drained_tournaments` re-anexa os labels quando a fila de um torneio drena. Ele exige,
POR TORNEIO: nenhum spot pending/running, pelo menos um done, e um solve mais novo que o último
carimbo. Se um torneio tem uma decisão órfã e NÃO satisfaz essas condições, a reconciliação nunca
vai chegar nela sozinha — e o script diz qual condição barra.

Atenção a um detalhe que engana: o gate é por TORNEIO, não por spot. Um único spot pendente em
qualquer canto do torneio segura o re-anexo de todas as outras decisões dele.

── Seção 2: o gate do `is_simple_spot` fecha pedido cedo demais? ─────────────────────────────

Em `_process_gto_hand_request`, um spot só conta como "enfileirado" se `is_simple_spot` devolver
True, sob o comentário de que ela responde "o solver vai resolver isto algum dia?". Ela não
responde isso: responde "dá para resolver SINCRONAMENTE, em menos de 30s?". Quando devolve False
o certo é justamente enfileirar.

Se a leitura errada tem efeito, o sintoma é: pedido com status 'done' cujas decisões seguem sem
label, e cujos spots `is_simple_spot` reprovaria. Esta seção conta exatamente isso. Se o número
for zero, a leitura errada é inofensiva na prática e não vale mexer.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _fetchall, _adapt
from leaklab.gto_utils import compute_spot_hash, board_for_street, normalize_cards, normalize_position


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


def _o_produto_serviria(street, pos, vs_pos, board, mao, stack, facing):
    """Pergunta ao `lookup_gto`, o MESMO caminho que serve o jogador. Read-only.

    ── Por que não reimplementar a busca aqui ────────────────────────────────────────────────

    A primeira versão deste script montava o hash por conta própria e perguntava direto à tabela
    `gto_nodes`. Ela contava 13 "órfãs" e concluía que algo estava travado — mas o resync rodou
    nos oito torneios e reconciliou ZERO, porque ele passa por `evaluate_decision` → `lookup_gto`,
    que aplica portões que a minha busca ignorava: `pot_type` dentro do hash, recusa de spot com
    o herói IP (o solver só devolve o player 0, que é o OOP) e facing não conversível.

    Ou seja, "existe linha na tabela" não é "o produto deveria estar servindo". Reimplementar a
    consulta produziu um número que parecia denúncia e era ruído — o mesmo erro que este projeto
    já pagou várias vezes, e desta vez cometido dentro da própria ferramenta de diagnóstico.
    """
    from leaklab.gto_solver import lookup_gto
    try:
        r = lookup_gto(street=street, position=pos, board=board, hero_hand=mao,
                       hero_stack_bb=stack, vs_position=vs_pos, facing_size_bb=facing,
                       block_remote=True, allow_remote_solve=False) or {}
    except Exception as exc:
        return False, f'erro: {str(exc)[:40]}'
    if r.get('gto_action') or r.get('strategy'):
        return True, 'serviria'
    return False, (r.get('reason') or r.get('source') or 'sem no servivel')


def main():
    email = next((a for a in sys.argv[1:] if not a.startswith('--')), None)
    from leaklab.gto_solver import is_simple_spot

    conn = get_conn()
    try:
        filtro, params = '', []
        if email:
            u = _fetchall(conn, _adapt("SELECT id FROM users WHERE email = ?"), (email,))
            if not u:
                print(f'usuário {email} não encontrado'); return
            filtro, params = ' AND t.user_id = ? ', [u[0]['id']]
            print(f'== {email} ==\n')

        rows = _fetchall(conn, _adapt(f"""
            SELECT d.id AS id, d.tournament_id AS tid, d.hand_id AS hand_id,
                   d.street AS street, d.position AS position, d.vs_position AS vs_position,
                   d.board AS board,
                   d.hero_cards AS hero_cards, d.stack_bb AS stack_bb, d.facing_bet AS facing
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE lower(d.street) IN ('flop','turn','river')
              AND (d.gto_label IS NULL OR d.gto_label = '')
              AND (d.n_active_opponents IS NULL OR d.n_active_opponents < 2)
              AND d.position IS NOT NULL AND d.stack_bb IS NOT NULL
              {filtro}
        """), tuple(params))

        orfas, por_torneio, reprovaria_gate = [], {}, 0
        motivos = {}
        for r in rows:
            street = (r['street'] or '').lower()
            completo = _board(r['board'])
            if not completo:
                continue
            cortado = board_for_street(completo, street)
            mao = normalize_cards(r['hero_cards'])
            stack = float(r['stack_bb'] or 30)
            facing = float(r['facing'] or 0)
            pos = normalize_position(r['position'] or '')
            vs = normalize_position(r.get('vs_position') or '')
            serve, motivo = _o_produto_serviria(street, pos, vs, cortado, mao, stack, facing)
            if not serve:
                # O produto NÃO serviria este spot nem com o nó no banco. Não é órfã: é recusa
                # deliberada (herói IP, facing não conversível, pot_type sem cobertura).
                motivos[motivo] = motivos.get(motivo, 0) + 1
                continue
            orfas.append(r)
            por_torneio[r['tid']] = por_torneio.get(r['tid'], 0) + 1
            if not is_simple_spot(street, cortado, stack, facing):
                reprovaria_gate += 1

        print('── SEÇÃO 1 · decisões que o PRODUTO serviria e que estão sem veredito ──')
        print(f'  órfãs de verdade: {len(orfas)}  em {len(por_torneio)} torneio(s)')
        if motivos:
            print('\n  recusadas pelo lookup (NÃO são órfãs, o produto declina de propósito):')
            for m, n in sorted(motivos.items(), key=lambda x: -x[1]):
                print(f'    {n:5d}  {m}')
        if not orfas:
            print('  nada pendente. A reconciliação está em dia.')
            return

        print('\n  por torneio, e o que barra a reconciliação:')
        print(f'  {"tid":>6} {"órfãs":>6} {"pend/run":>9} {"done":>6} {"reconc":>20} {"veredito":>28}')
        for tid, n in sorted(por_torneio.items(), key=lambda x: -x[1])[:15]:
            q = _fetchall(conn, _adapt("""
                SELECT SUM(CASE WHEN sq.status IN ('pending','running') THEN 1 ELSE 0 END) AS ativos,
                       SUM(CASE WHEN sq.status = 'done' THEN 1 ELSE 0 END) AS prontos,
                       MAX(sq.solved_at) AS ultimo
                FROM gto_tournament_queue gtq
                JOIN gto_solver_queue sq ON sq.spot_hash = gtq.spot_hash
                WHERE gtq.tournament_id = ?"""), (tid,))
            a = int((q[0]['ativos'] if q else 0) or 0)
            p = int((q[0]['prontos'] if q else 0) or 0)
            ultimo = (q[0]['ultimo'] if q else None)
            t = _fetchall(conn, _adapt("SELECT labels_reconciled_at AS rc FROM tournaments WHERE id = ?"), (tid,))
            rc = t[0]['rc'] if t else None

            if p == 0:
                por_que = 'sem spot resolvido'
            elif a > 0:
                por_que = f'{a} spot(s) ainda na fila'
            elif rc is not None and ultimo is not None and str(ultimo) <= str(rc):
                por_que = 'carimbo mais novo que o solve'
            else:
                por_que = 'ELEGÍVEL — deveria rodar'
            print(f'  {tid:>6} {n:>6} {a:>9} {p:>6} {str(rc)[:19]:>20} {por_que:>28}')

        print('\n── SEÇÃO 2 · o gate do is_simple_spot ──')
        print(f'  órfãs que o gate reprovaria: {reprovaria_gate} de {len(orfas)}')
        if reprovaria_gate == 0:
            print('  o gate NÃO explica nenhuma órfã. A leitura errada é inofensiva aqui.')
        else:
            print('  estas seriam contadas como "não enfileirável" e o pedido fecharia como done,')
            print('  deixando a decisão sem veredito mesmo com o nó pronto no banco.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
