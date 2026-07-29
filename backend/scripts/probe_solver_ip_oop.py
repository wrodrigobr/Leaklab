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

O truque é dar aos dois jogadores ranges de TAMANHO diferente, num board seco:

    board = A♥ 7♦ 2♣
    OOP   = só AA      →  6 combinações
    IP    = só 32o     → 12 combinações

E o discriminador é `total_combos`, não a ação. A primeira versão deste teste lia "agressiva =
AA = OOP, passiva = 32o = IP", e isso NÃO funciona: com AA contra uma range que é só 32o, apostar
não extrai nada, porque o vilão nunca paga. Os dois jogadores passam, as duas respostas vêm
`check`, e a leitura não decide nada. Critério que colapsa nos dois lados não é critério.

`total_combos` não colapsa: ou o solver devolveu o dono das 6 combinações, ou o das 12. A mesma
pergunta é feita com `hero_is_ip` false e true, e o número diz de quem é cada resposta.

Não altera nada no banco: fala direto com o solver.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.gto_solver import _call_remote_solver, _remote_url, _TEXAS_HERO_IP

BOARD = ['Ah', '7d', '2c']
RANGE_MONSTRO = 'AA'      # trinca máxima neste board
RANGE_LIXO = '32o'        # nada, e sem projeto


def _spot(hero_is_ip):
    return {
        'street': 'flop',
        'board': BOARD,
        'oop_range': RANGE_MONSTRO,
        'ip_range': RANGE_LIXO,
        'pot_bb': 6.0,
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
        combos = r.get('total_combos')
        saidas[flag] = combos
        dono = ('OOP, o das AA' if combos == 6 else
                'IP, o das 32o' if combos == 12 else f'INDEFINIDO ({combos})')
        print(f'  total_combos   : {combos}   ->  a resposta é do {dono}')
        print(f'  EV             : {r.get("ev")}')
        print(f'  ação dominante : {acao} ({freq})  {obs}')
        print(f'  exploitability : {r.get("exploitability") or r.get("exploitability_pct")}')
        print(f'  ações          : {r.get("actions")}\n')

    print('=' * 68)
    a, b = saidas.get(False), saidas.get(True)
    if a is None or b is None:
        print('INCONCLUSIVO: o solver não respondeu nas duas chamadas.')
        return
    print(f'hero_is_ip=False -> {a} combos   |   hero_is_ip=True -> {b} combos\n')
    if a == b:
        print('A FLAG É IGNORADA: o solver devolveu o MESMO jogador nas duas chamadas.')
        print('  -> binário antigo. Manter TEXAS_HERO_IP desligada e NÃO enfileirar spot de')
        print('     herói-IP: o nó viria com a estratégia do vilão.')
    elif a == 6 and b == 12:
        print('A FLAG É HONRADA, e na direção CERTA.')
        print('  -> false devolveu o OOP (6 combos de AA) e true devolveu o IP (12 de 32o),')
        print('     exatamente como a aplicação assume. Dá para ligar TEXAS_HERO_IP.')
    else:
        print('A FLAG MUDA A RESPOSTA, mas NÃO na direção esperada.')
        print('  -> não ligue nada até entender. Esperado: false=6 (OOP/AA), true=12 (IP/32o).')
        print('     Flag que muda na direção errada é pior que flag ignorada: parece funcionar.')


if __name__ == '__main__':
    main()
