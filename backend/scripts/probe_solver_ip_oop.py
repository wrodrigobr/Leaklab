"""
probe_solver_ip_oop.py — o solver honra `hero_is_ip`, ou devolve sempre o player 0?

Roda no HOST de prod (precisa de GTO_SOLVER_URL e GTO_SOLVER_API_KEY):

    python scripts/probe_solver_ip_oop.py

── Por que este teste existe ─────────────────────────────────────────────────────────────────

Tudo o que se sabia sobre isto vinha de um COMENTÁRIO no código:

    "Default OFF: só vale DEPOIS que o main.rs com `hero_is_ip` for buildado/deployado na VM
     (senão o binário antigo ignora a flag e devolve o player 0 = OOP = jogador errado)."

Comentário não é evidência. Se o binário na VM já suporta a flag, o produto está deixando de
servir spots de herói-IP à toa. Se não suporta, qualquer nó de herói-IP que entre no banco vira
veredito do VILÃO na decisão do jogador, porque o resync automático casa por hash e não aplica
o portão que o lookup aplica.

── Como a resposta se denuncia sozinha ───────────────────────────────────────────────────────

Ranges opostas ao extremo num board seco, e o discriminador é o **EV**:

    board = A♥ 7♦ 2♣  ·  pote 6bb
    OOP   = só AA      → trinca máxima: leva o pote quase inteiro, EV perto de 6
    IP    = só 32o     → nada, e sem projeto: EV perto de 0

Duas tentativas anteriores de critério falharam, e as duas merecem ficar registradas:

  1. **Pela AÇÃO** ("agressiva = AA, passiva = 32o"). Não funciona: com AA contra uma range que
     é só 32o, apostar não extrai nada, porque o vilão nunca paga. Os dois jogadores passam, as
     duas respostas vêm `check`, e a leitura não decide nada. Critério que colapsa nos dois lados
     não é critério.
  2. **Por `total_combos`** (esperando 6 e 12, as combinações cruas). Voltou 27.0 e 19.69 —
     FRACIONÁRIO, porque é contagem ponderada por alcance e bloqueadores, não contagem crua.

O EV separa sem ambiguidade: em produção deu 5.94 contra 0.08, num pote de 6bb. Não existe
leitura intermediária entre "levou o pote" e "não levou nada".

Não altera nada no banco: fala direto com o solver.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.gto_solver import _call_remote_solver, _remote_url, _TEXAS_HERO_IP

BOARD = ['Ah', '7d', '2c']
RANGE_MONSTRO = 'AA'      # trinca máxima neste board
RANGE_LIXO = '32o'        # nada, e sem projeto
POT_BB = 6.0              # o EV do dono das AA tende ao pote; o das 32o, a zero


def _spot(hero_is_ip):
    return {
        'street': 'flop',
        'board': BOARD,
        'oop_range': RANGE_MONSTRO,
        'ip_range': RANGE_LIXO,
        'pot_bb': POT_BB,
        'facing_size_bb': 0.0,
        'hero_stack_bb': 20.0,
        'effective_stack_bb': 20.0,
        'max_iterations': 60,
        'target_exploitability_pct': 5.0,
        'time_budget_s': 60,
        'hero_is_ip': hero_is_ip,
    }


def _resumo(r):
    """(ação dominante, frequência) da estratégia devolvida."""
    if not r:
        return None, None, 'sem resposta'
    estr = r.get('strategy') or []
    if isinstance(estr, dict):
        estr = [{'action': k, 'frequency': v} for k, v in estr.items()]
    if not estr:
        act = r.get('primary_action')
        return act, r.get('primary_freq'), 'só primary_action'
    top = max(estr, key=lambda s: float(s.get('frequency') or 0))
    return top.get('action'), float(top.get('frequency') or 0), ''


def main():
    if not _remote_url():
        print('GTO_SOLVER_URL não configurada — rode no host de prod.'); return
    print(f'solver: {_remote_url()}')
    print(f'TEXAS_HERO_IP na app: {_TEXAS_HERO_IP}\n')
    print(f'board {" ".join(BOARD)}  ·  OOP={RANGE_MONSTRO} (trinca)  ·  IP={RANGE_LIXO} (nada)\n')

    saidas = {}
    for flag in (False, True):
        print(f'--- hero_is_ip = {flag} ---')
        r = _call_remote_solver(_spot(flag), timeout=300)
        if r is None:
            print('  solver não respondeu (veja o log para o motivo)\n')
            saidas[flag] = None
            continue
        acao, freq, obs = _resumo(r)
        ev = float(r.get('ev') or 0)
        saidas[flag] = ev
        # O EV é o discriminador. `total_combos` NÃO serve: voltou 27.0 e 19.69 em produção,
        # fracionário, porque é contagem ponderada por alcance e bloqueadores — não as 6 e 12
        # combinações cruas que eu esperava. Fica impresso só como contexto.
        dono = ('OOP, o das AA (leva o pote)' if ev > POT_BB * 0.6 else
                'IP, o das 32o (não leva nada)' if ev < POT_BB * 0.2 else
                f'INDEFINIDO: EV {ev} não é nem perto de {POT_BB} nem perto de 0')
        print(f'  EV             : {ev}   ->  a resposta é do {dono}')
        print(f'  total_combos   : {r.get("total_combos")}   (ponderado; só contexto)')
        print(f'  ação dominante : {acao} ({freq})  {obs}')
        print(f'  exploitability : {r.get("exploitability") or r.get("exploitability_pct")}')
        print(f'  ações          : {r.get("actions")}\n')

    print('=' * 68)
    a, b = saidas.get(False), saidas.get(True)
    if a is None or b is None:
        print('INCONCLUSIVO: o solver não respondeu nas duas chamadas.')
        return
    print(f'hero_is_ip=False -> EV {a}   |   hero_is_ip=True -> EV {b}   (pote {POT_BB})\n')
    if abs(a - b) < POT_BB * 0.2:
        print('A FLAG É IGNORADA: os dois EVs são praticamente iguais, então o solver devolveu')
        print('o MESMO jogador nas duas chamadas.')
        print('  -> binário antigo. Manter TEXAS_HERO_IP desligada e NÃO enfileirar spot de')
        print('     herói-IP: o nó viria com a estratégia do vilão.')
    elif a > POT_BB * 0.6 and b < POT_BB * 0.2:
        print('A FLAG É HONRADA, e na direção CERTA.')
        print('  -> false devolveu o dono das AA (EV ~ pote inteiro) = OOP, e true devolveu o')
        print('     dono das 32o (EV ~ 0) = IP. É exatamente o que a aplicação assume.')
        print('  -> DÁ para ligar TEXAS_HERO_IP. NÃO liga TEXAS_HERO_IP_FACING com base neste')
        print('     teste: aqui o facing é 0, e o caminho de IP enfrentando aposta é outro')
        print('     (navigate_to_ip_facing_bet), que este probe não exercitou.')
    else:
        print('A FLAG MUDA A RESPOSTA, mas NÃO na direção esperada.')
        print(f'  -> não ligue nada até entender. Esperado: false ~ {POT_BB} (OOP/AA), true ~ 0 (IP/32o).')
        print('     Flag que muda na direção errada é pior que flag ignorada: parece funcionar.')


if __name__ == '__main__':
    main()
