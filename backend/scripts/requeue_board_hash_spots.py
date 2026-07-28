"""
requeue_board_hash_spots.py — re-enfileira, com a chave CERTA, os spots perdidos pelo bug do board.

    python scripts/requeue_board_hash_spots.py rodrigo@email.com          # SIMULA (padrão)
    python scripts/requeue_board_hash_spots.py rodrigo@email.com --exec   # enfileira de verdade
    python scripts/requeue_board_hash_spots.py --exec                     # base inteira

── Por que re-enfileirar, e não re-chavear ───────────────────────────────────────────────────

O atalho tentador é pegar o nó órfão e trocar o `spot_hash` para o valor correto: a estratégia já
está calculada, e re-solvar custa CPU. **Não faça isso.**

O payload que gerou aquele nó levava `street: flop` com as CINCO cartas do river. Não se sabe o
que o solver montou: pode ter construído a árvore do river e rotulado como flop. Re-chavear
colaria uma estratégia de river numa decisão de flop, e o produto passaria a dar conselho ERRADO.

Isso importa porque, no formato atual, este bug nunca deu conselho errado: ele SOME com a
resposta (a decisão fica "sem cobertura", que é honesto), não a troca. O conserto não pode ser o
que cria o dano que o bug não causou.

Re-solvar custa tempo de CPU. Re-chavear custa confiança. O preço não é comparável.

── O que este script faz ─────────────────────────────────────────────────────────────────────

Encontra as decisões que o `diag_board_hash_impact.py` classifica como perdidas, monta o payload
do solver com o board **cortado na street** e enfileira sob o hash correto. Deduplica por hash:
uma mesma chave costuma servir várias decisões, então o número de solves é bem menor que o de
decisões.

Enfileira com prioridade BAIXA de propósito: isto é dívida, não pedido de usuário esperando na
tela, e não deve passar na frente de quem acabou de subir um torneio.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _fetchall, _adapt, get_gto_node, enqueue_solver_spot
from leaklab.gto_utils import compute_spot_hash, board_for_street, normalize_cards, normalize_position

_PRIORIDADE_DIVIDA = 9   # maior = depois; upload de usuário usa prioridade menor


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


def _acha_no(street, pos, board, mao, stack, facing):
    for _mao, _f in ((mao, facing), ([], facing), ([], 0.0)):
        if _f != facing and facing != 0:
            continue
        try:
            if get_gto_node(compute_spot_hash(street, pos, board, _mao, stack, _f)):
                return True
        except Exception:
            pass
    return False


def main():
    args = [a for a in sys.argv[1:]]
    executar = '--exec' in args
    email = next((a for a in args if not a.startswith('--')), None)

    from leaklab.gto_solver import (_DEFAULT_RANGES, _DEFAULT_RANGE_WIDE,
                                    _solver_params_for_stack)

    conn = get_conn()
    try:
        filtro, params = '', []
        if email:
            u = _fetchall(conn, _adapt("SELECT id FROM users WHERE email = ?"), (email,))
            if not u:
                print(f'usuário {email} não encontrado'); return
            filtro, params = ' AND t.user_id = ? ', [u[0]['id']]

        rows = _fetchall(conn, _adapt(f"""
            SELECT d.id AS id, d.street AS street, d.position AS position,
                   d.vs_position AS vs_position, d.board AS board, d.hero_cards AS hero_cards,
                   d.stack_bb AS stack_bb, d.facing_bet AS facing, d.pot_size AS pot,
                   d.level_bb AS level_bb, d.tournament_id AS tid
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE lower(d.street) IN ('flop','turn')
              AND (d.gto_label IS NULL OR d.gto_label = '')
              AND (d.n_active_opponents IS NULL OR d.n_active_opponents < 2)
              AND d.position IS NOT NULL AND d.stack_bb IS NOT NULL
              {filtro}
        """), tuple(params))

        modo = 'EXECUTANDO' if executar else 'SIMULAÇÃO (use --exec para valer)'
        print(f'== {modo} == {len(rows)} decisões candidatas\n')

        por_hash = {}
        for r in rows:
            street = (r['street'] or '').lower()
            completo = _board(r['board'])
            cortado = board_for_street(completo, street)
            if not completo or len(cortado) == len(completo):
                continue                       # river ou board vazio: nada a corrigir aqui
            mao = normalize_cards(r['hero_cards'])
            stack = float(r['stack_bb'] or 30)
            facing = float(r['facing'] or 0)
            pos = normalize_position(r['position'] or '')

            # Já coberto na chave certa? Então não é caso deste conserto.
            if _acha_no(street, pos, cortado, mao, stack, facing):
                continue
            # O solve tem que existir na chave ERRADA — é o que define "perdida pelo bug".
            if not _acha_no(street, pos, completo, mao, stack, facing):
                continue
            # NÃO existe filtro por `is_simple_spot` aqui, e a primeira versão tinha.
            #
            # Aquela função responde "dá para resolver SINCRONAMENTE, em menos de 30s?" — a própria
            # docstring diz que `False` significa "enfileira imediatamente sem bloquear o request".
            # Ou seja: `False` é o pedido para vir PARA CÁ, não uma recusa. Usá-la como gate de
            # capacidade descartava 133 dos 238 spots em produção, justamente os mais pesados, que
            # são o motivo da fila existir. O caminho assíncrono tem 1800s de orçamento, não 30.
            #
            # Quem recusa o que é genuinamente impossível é o próprio solver, marcando o item como
            # `rejected`/`unsupported` na fila. Melhor ele decidir com a árvore na mão do que este
            # script decidir por heurística.

            h = compute_spot_hash(street, pos, cortado, mao, stack, facing)
            if h in por_hash:
                por_hash[h]['decisoes'] += 1
                continue

            vs_pos = normalize_position(r['vs_position'] or '')
            lvl = float(r['level_bb'] or 1) or 1
            pot_chips = float(r['pot'] or 0)
            pot_bb = round(pot_chips / lvl, 2) if pot_chips > 0 else (facing * 2 + 2 or 4.0)
            p = _solver_params_for_stack(stack)
            payload = json.dumps({
                'street': street, 'board': cortado, 'position': pos, 'hero_hand': mao,
                'hero_stack_bb': stack, 'facing_size_bb': facing,
                'oop_range': _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
                'ip_range':  _DEFAULT_RANGES.get(pos,    _DEFAULT_RANGE_WIDE),
                'pot_bb': pot_bb,
                'effective_stack_bb': p['effective_stack_bb'],
                'max_iterations': p['max_iterations'],
                'target_exploitability_pct': p['target_exploitability_pct'],
                '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': mao,
                          'hero_stack_bb': stack, 'facing_size_bb': facing,
                          'street': street, 'board': cortado},
            }, sort_keys=True)
            por_hash[h] = {'payload': payload, 'tid': r['tid'], 'decisoes': 1,
                           'street': street, 'pos': pos}

        n_dec = sum(v['decisoes'] for v in por_hash.values())
        print(f'spots ÚNICOS a re-solvar ....... {len(por_hash)}')
        print(f'decisões que eles destravam .... {n_dec}')
        if por_hash:
            m = max(v['decisoes'] for v in por_hash.values())
            print(f'melhor caso: um único spot destrava {m} decisões')

        if not executar:
            print('\nNada foi enfileirado. Rode com --exec para valer.')
            return

        n = 0
        for h, v in por_hash.items():
            try:
                if enqueue_solver_spot(h, v['payload'], priority=_PRIORIDADE_DIVIDA,
                                       tournament_id=v['tid']):
                    n += 1
            except Exception as exc:
                print(f'  falhou {h[:12]}: {exc}')
        print(f'\nenfileirados: {n} spots (prioridade {_PRIORIDADE_DIVIDA}, atrás dos uploads)')
        print('Acompanhe com: scripts/diag_board_hash_impact.py — o número de perdidas cai')
        print('conforme o solver drena a fila.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
