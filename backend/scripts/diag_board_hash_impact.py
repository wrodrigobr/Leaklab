"""
diag_board_hash_impact.py — quanto o bug do board custou, decisão por decisão.

Roda no HOST de prod (com DATABASE_URL apontando pro Neon). SOMENTE LEITURA, não altera nada:

    python scripts/diag_board_hash_impact.py                    # base inteira
    python scripts/diag_board_hash_impact.py rodrigo@email.com  # um usuário

── O que está sendo medido ───────────────────────────────────────────────────────────────────

Entre 12/05 e 28/07, um spot de flop era ENFILEIRADO com as cinco cartas do river (o board
completo da mão, que o banco guarda em toda decisão) e PROCURADO com as três da street. Chaves
diferentes: o solver resolvia, gravava, e o lookup nunca achava.

A medida certa não é contar nós órfãos, é contar DECISÕES. Para cada decisão postflop sem
cobertura, o script calcula o hash das duas formas:

    CERTO  = board cortado na street   (o que o lookup procura hoje)
    ERRADO = board completo da mão     (o que o enfileiramento gravava)

E classifica:

    · nó no ERRADO e nada no CERTO  → PERDIDA PELO BUG. O trabalho existe e está inalcançável.
    · nada nos dois                 → nunca foi resolvida (outra causa: multiway, deep, rejeitada)
    · nó no CERTO                   → coberta, não deveria estar nesta lista

Só o primeiro grupo é dano deste bug. Sem essa separação, o número viraria "toda decisão sem
cobertura", que inclui o que o solver legitimamente não resolve, e superestimaria o estrago.

── Por que NÃO existe um `--fix` aqui ────────────────────────────────────────────────────────

A tentação óbvia é re-chavear os nós órfãos: a estratégia já está calculada, só o identificador
está errado. **Não faça isso.** O payload mandado ao solver levava `street: flop` com cinco
cartas na mesa, então não se sabe o que ele resolveu: pode ter montado a árvore do RIVER e
rotulado como flop. Re-chavear colaria uma estratégia de river numa decisão de flop, e aí sim o
produto passaria a dar conselho ERRADO — que é exatamente o que este bug, no seu formato atual,
nunca fez (ele some com a resposta, não a troca).

O conserto seguro é re-enfileirar com a chave certa e deixar o solver refazer. Custa tempo de
CPU e não custa confiança.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _fetchall, _adapt, get_gto_node
from leaklab.gto_utils import compute_spot_hash, board_for_street, normalize_cards

_STREETS = ('flop', 'turn', 'river')


def _board(bruto):
    """Board vem como JSON (`["Qd","Th","7h"]`) na coluna `decisions.board`."""
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


def _mao(bruto):
    """A mão do herói vai DIRETO para `normalize_cards`, sem passar por `split()` antes.

    Isto já quebrou uma vez, na primeira versão deste arquivo: `hero_cards` é gravado colado
    (`'5h5d'`), então `split()` devolvia UM token de quatro caracteres, `normalize_cards` não tinha
    o que consertar, e o hash saía errado nas DUAS variantes. Resultado: o diagnóstico classificava
    tudo como "nunca resolvida" e imprimia zero perdidas — um zero falsamente tranquilizador, que é
    o pior resultado possível para uma ferramenta de medição. `normalize_cards` já aceita a string
    crua e trata as três formas que existem na base; deixe ela fazer o trabalho.
    """
    return normalize_cards(bruto)


def _acha_no(street, pos, board, mao, stack, facing):
    """Mesma ordem de variantes do lookup: exata, genérica, e sem facing quando não há aposta."""
    for _mao, _f in ((mao, facing), ([], facing), ([], 0.0)):
        if _f != facing and facing != 0:
            continue
        try:
            n = get_gto_node(compute_spot_hash(street, pos, board, _mao, stack, _f))
        except Exception:
            n = None
        if n:
            return True
    return False


def main():
    email = sys.argv[1] if len(sys.argv) > 1 else None
    conn = get_conn()
    try:
        filtro, params = '', []
        if email:
            u = _fetchall(conn, _adapt("SELECT id FROM users WHERE email = ?"), (email,))
            if not u:
                print(f'usuário {email} não encontrado'); return
            filtro = ' AND t.user_id = ? '
            params = [u[0]['id']]
            print(f'== usuário {email} ==')
        else:
            print('== base inteira ==')

        rows = _fetchall(conn, _adapt(f"""
            SELECT d.id AS id, d.street AS street, d.position AS position, d.board AS board,
                   d.hero_cards AS hero_cards, d.stack_bb AS stack_bb, d.facing_bet AS facing,
                   d.n_active_opponents AS opp, t.imported_at AS importado
            FROM decisions d JOIN tournaments t ON t.id = d.tournament_id
            WHERE lower(d.street) IN ('flop','turn','river')
              AND (d.gto_label IS NULL OR d.gto_label = '')
              AND (d.n_active_opponents IS NULL OR d.n_active_opponents < 2)
              AND d.position IS NOT NULL AND d.stack_bb IS NOT NULL
              {filtro}
        """), tuple(params))

        print(f'decisões postflop HU sem cobertura: {len(rows)}\n')

        perdidas, nunca, cobertas, ilegiveis = [], 0, 0, 0
        por_street = {}
        for r in rows:
            street = (r['street'] or '').lower()
            completo = _board(r['board'])
            if not completo:
                ilegiveis += 1
                continue
            cortado = board_for_street(completo, street)
            mao = _mao(r['hero_cards'])
            stack = float(r['stack_bb'] or 30)
            facing = float(r['facing'] or 0)
            pos = (r['position'] or '').upper()

            tem_certo = _acha_no(street, pos, cortado, mao, stack, facing)
            if tem_certo:
                cobertas += 1
                continue
            # Só faz sentido perguntar pelo hash ERRADO quando ele DIFERE do certo (flop e turn).
            if len(cortado) != len(completo) and _acha_no(street, pos, completo, mao, stack, facing):
                perdidas.append(r)
                por_street[street] = por_street.get(street, 0) + 1
            else:
                nunca += 1

        total = len(rows)
        print('CLASSIFICAÇÃO')
        print(f'  perdidas pelo bug do board .. {len(perdidas):6d}   (o solve EXISTE, com a chave errada)')
        print(f'  nunca resolvidas ............ {nunca:6d}   (multiway, deep, árvore rejeitada, etc.)')
        print(f'  já cobertas ................. {cobertas:6d}   (não deveriam estar na lista)')
        print(f'  board ilegível .............. {ilegiveis:6d}')
        if total:
            print(f'\n  o bug responde por {len(perdidas) * 100.0 / total:.1f}% das decisões sem cobertura')

        if por_street:
            print('\nPOR STREET (só as perdidas pelo bug)')
            for s in ('flop', 'turn', 'river'):
                if por_street.get(s):
                    print(f'  {s:6s} {por_street[s]:6d}')
            print('  (river NÃO deveria aparecer: lá o board completo E o cortado são os mesmos 5.)')

        if perdidas:
            datas = sorted(str(r['importado'])[:10] for r in perdidas if r['importado'])
            print(f'\nJANELA: primeira {datas[0]} · última {datas[-1]}')
            print('(a correção do lookup entrou em 12/05 — importações anteriores não deveriam aparecer)')
            print('\nAMOSTRA')
            for r in perdidas[:5]:
                print(f"  dec {r['id']}  {r['street']:5s} {r['position']:5s} "
                      f"stack={float(r['stack_bb'] or 0):.1f} facing={float(r['facing'] or 0):.1f}")

        print('\nSOMENTE LEITURA: nada foi alterado. O conserto seguro é RE-ENFILEIRAR com a chave')
        print('certa, nunca re-chavear o nó existente — ver o cabeçalho deste arquivo.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
