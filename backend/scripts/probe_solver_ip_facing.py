"""
probe_solver_ip_facing.py — o solver navega até o nó do herói IP ENFRENTANDO aposta?

Roda no HOST de prod (precisa de GTO_SOLVER_URL e GTO_SOLVER_API_KEY):

    python scripts/probe_solver_ip_facing.py

── A pergunta ────────────────────────────────────────────────────────────────────────────────

`TEXAS_HERO_IP` já foi provada e ligada: o solver honra a flag no nó de raiz (c-bet, sem aposta
enfrentada). Falta a outra metade, que tem gate próprio:

    _TEXAS_HERO_IP_FACING — "IP enfrentando aposta (root → OOP bet → IP age). Default OFF: só
    vale DEPOIS do deploy do main.rs com navigate_to_ip_facing_bet (senão o binário antigo
    aborta facing>0 IP)."

De novo, isso é um comentário, não evidência. E de novo o custo de acreditar nele sem medir é
alto nos dois sentidos: se o binário suporta, o produto está sem cobrir uma fatia grande de
postflop à toa; se não suporta e alguém liga a flag, o solver aborta ou devolve o nó errado.

── Como a resposta se denuncia sozinha ───────────────────────────────────────────────────────

O discriminador aqui NÃO é EV nem contagem: é o **conjunto de ações**, que é estrutural.

  · num nó de RAIZ (ninguém apostou), quem age pode `check` ou `bet`
  · num nó ENFRENTANDO APOSTA, quem age pode `fold`, `call` ou `raise`

Não há sobreposição. Se a resposta para `facing>0` vier com `check`/`bet`, o solver ignorou a
navegação e devolveu a raiz — o nó errado, com cara de certo.

São QUATRO chamadas, e as três primeiras são controle:

    1. OOP, facing 0  → raiz do OOP          (baseline)
    2. OOP, facing 3  → OOP enfrentando bet  (caminho que o produto JÁ usa hoje)
    3. IP,  facing 0  → raiz do IP           (provado em 2026-07-28)
    4. IP,  facing 3  → IP enfrentando bet   ← A PERGUNTA

Sem o controle 2, um fracasso no 4 seria ambíguo: poderia ser o `facing` inteiro que não
funciona, não a navegação do IP. Com ele, o teste isola a variável.

RANGES REALISTAS de propósito. A primeira versão deste probe usava AA contra 32o, e com ranges
extremas o ramo "OOP aposta" quase não existe em equilíbrio — o nó do IP enfrentando aposta
poderia ficar inalcançável por motivo de poker, não de binário, e o teste culparia o solver.

Não altera nada no banco: fala direto com o solver.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.gto_solver import (_call_remote_solver, _remote_url,
                                _TEXAS_HERO_IP, _TEXAS_HERO_IP_FACING)

BOARD = ['Ah', '7d', '2c']
POT_BB = 6.0
FACING_BB = 3.0
RANGE_OOP = '22+,A2s+,K9s+,QTs+,JTs,A9o+,KJo+'
RANGE_IP = '22+,A2s+,K5s+,Q8s+,J8s+,T8s+,98s,A7o+,K9o+,QTo+'

# Ações que só existem enfrentando aposta, e ações que só existem na raiz.
_DE_FACING = {'fold', 'call'}
_DE_RAIZ = {'check'}


def _spot(hero_is_ip, facing):
    return {
        'street': 'flop', 'board': BOARD,
        'oop_range': RANGE_OOP, 'ip_range': RANGE_IP,
        'pot_bb': POT_BB, 'facing_size_bb': facing,
        'hero_stack_bb': 20.0, 'effective_stack_bb': 20.0,
        'max_iterations': 80, 'target_exploitability_pct': 5.0,
        'time_budget_s': 90, 'hero_is_ip': hero_is_ip,
    }


def _classifica(acoes):
    """De que TIPO de nó é esta resposta, olhando só as ações disponíveis."""
    s = {str(a).lower().split('_')[0] for a in (acoes or [])}
    tem_facing = bool(s & _DE_FACING)
    tem_raiz = bool(s & _DE_RAIZ)
    if tem_facing and not tem_raiz:
        return 'ENFRENTANDO APOSTA'
    if tem_raiz and not tem_facing:
        return 'RAIZ (ninguém apostou)'
    if tem_facing and tem_raiz:
        return f'AMBÍGUO ({sorted(s)})'
    return f'DESCONHECIDO ({sorted(s)})'


def _roda(rotulo, hero_is_ip, facing):
    print(f'--- {rotulo} ---')
    r = _call_remote_solver(_spot(hero_is_ip, facing), timeout=300)
    if r is None:
        print('  solver NÃO respondeu (abortou ou erro; veja o log)\n')
        return None
    acoes = r.get('actions')
    tipo = _classifica(acoes)
    print(f'  ações        : {acoes}')
    print(f'  tipo de nó   : {tipo}')
    print(f'  facing_node  : {r.get("facing_node")}')
    print(f'  EV           : {r.get("ev")}   ·  exploitability: '
          f'{r.get("exploitability") or r.get("exploitability_pct")}\n')
    return tipo


def main():
    if not _remote_url():
        print('GTO_SOLVER_URL não configurada — rode no host de prod.'); return
    print(f'solver: {_remote_url()}')
    print(f'flags na app: TEXAS_HERO_IP={_TEXAS_HERO_IP} · '
          f'TEXAS_HERO_IP_FACING={_TEXAS_HERO_IP_FACING}\n')
    print(f'board {" ".join(BOARD)}  ·  pote {POT_BB}bb  ·  aposta enfrentada {FACING_BB}bb\n')

    t1 = _roda('1 · OOP, sem aposta enfrentada  (baseline)', False, 0.0)
    t2 = _roda('2 · OOP, enfrentando aposta     (controle: o produto já usa)', False, FACING_BB)
    t3 = _roda('3 · IP, sem aposta enfrentada   (provado em 28/07)', True, 0.0)
    t4 = _roda('4 · IP, ENFRENTANDO aposta      <- A PERGUNTA', True, FACING_BB)

    print('=' * 70)
    if t2 != 'ENFRENTANDO APOSTA':
        print('TESTE INVÁLIDO: nem o controle funcionou.')
        print(f'  O caso 2 (OOP enfrentando aposta), que o produto usa todo dia, voltou "{t2}".')
        print('  Antes de concluir qualquer coisa sobre o IP, entenda por que o controle falhou:')
        print('  pode ser o `facing` inteiro, e aí o problema é bem maior que esta flag.')
        return

    if t4 is None:
        print('NÃO LIGAR: o solver ABORTOU no caso 4.')
        print('  -> é exatamente o que o comentário do código previa para o binário antigo.')
        print('     Manter TEXAS_HERO_IP_FACING=0. "Sem cobertura" é o estado honesto.')
    elif t4 == 'ENFRENTANDO APOSTA':
        print('PODE LIGAR TEXAS_HERO_IP_FACING.')
        print('  -> o caso 4 voltou um nó de ENFRENTANDO APOSTA, ou seja, a navegação até o IP')
        print('     depois do bet do OOP existe no binário. O comentário está desatualizado.')
    elif t4 == 'RAIZ (ninguém apostou)':
        print('NÃO LIGAR: o caso 4 devolveu a RAIZ, não o nó de facing.')
        print('  -> o pior cenário possível: o solver responde 200, parece certo, e entrega o nó')
        print('     ERRADO. Ligar a flag colocaria a estratégia de quem não enfrentou aposta na')
        print('     decisão de quem enfrentou.')
    else:
        print(f'NÃO LIGAR: caso 4 voltou "{t4}", que não é nem raiz nem facing.')
        print('  -> resultado que não bate com nenhuma hipótese. Investigar antes de mexer.')


if __name__ == '__main__':
    main()
