"""
trainer_pool.py — spots de treino postflop tirados do acervo de nós JÁ SOLVADOS.

Backlog #41. Hoje o Leak Trainer postflop serve de um catálogo estático: **uma** categoria
(`pf:bb_defense`), **31 spots**, todos com os mesmos parâmetros (BB vs BTN, 40bb, flop, c-bet de
1,65bb num pote de 5). O jogador esgota o repertório e passa a reconhecer o board.

Enquanto isso, `gto_nodes` cresce sozinho a cada torneio que alguém manda solvar. Medido em
produção (2026-08-02): 6.065 nós postflop, dos quais **5.762 sadios** e **5.147 gradeáveis com
frequência por mão** — 166 vezes o catálogo. Este módulo transforma esse acervo em exercício.

## O que a medição obrigou a mudar no desenho

**A distribuição da resposta é torta, e muito.** Entre os nós gradeáveis: check 2.894 (56%),
fold 1.014 (20%), call 810 (16%), bet 367 (7%), jam 50, raise 12. Servindo nó ao acaso, **quem
responder "check" sempre acerta 56%**, e "check ou fold" cobre 76%. Seria um quiz vencível sem ler
o board — exatamente a cicatriz registrada no CLAUDE.md, onde um teste com "a opção certa é sempre
a 1ª" congelou por meses um quiz que ninguém precisava entender para passar.

Por isso a seleção **sorteia a AÇÃO primeiro** e só então um nó que a tenha como resposta. A
distribuição servida é decidida aqui (`_MIX_ALVO`), não herdada do acervo. Nenhuma resposta
constante passa de ~30%.

## Filtros que são requisito, não preferência

- **exploitability entre 0,05% e 3%.** Acima de 3% o solve não convergiu. **Abaixo de 0,05% é
  suspeito**, não ótimo: é a assinatura do nó degenerado do bug do pot (exploit≈0.01 com all-in a
  100% e ev_bb nas milhares). Nó degenerado no treino ENSINA ERRADO, que é pior do que repetir.
- **estratégia por mão obrigatória.** Sem a `hand_table` só daria para comparar com a ação de topo,
  e o gradeamento perderia a tolerância de mistura — puniria o jogador numa mão de fronteira onde
  duas ações valem quase o mesmo.
- **board na ORDEM ORIGINAL.** `gto_nodes.board` vem ordenado; a ordem real está no `spot_json`.
  Num river, mostrar o board ordenado troca qual carta foi o turn e qual foi o river, e a mão que o
  jogador lê deixa de ser a mão que o solver resolveu.
"""
from __future__ import annotations

import json
import random
from typing import Optional

from database.schema import get_conn
from database.repositories import _adapt

# Faixa sadia de exploitability. O piso NÃO é zero de propósito — ver docstring.
EXPLOIT_MIN = 0.05
EXPLOIT_MAX = 3.0

# Distribuição que QUEREMOS servir, e não a que o acervo tem. Achatar é o ponto: com o mix do
# acervo, responder sempre "check" acertaria 56%. Aqui, nenhuma resposta constante passa de 30%.
_MIX_ALVO = [('check', 30), ('fold', 25), ('call', 25), ('bet', 20)]

_STREETS = ('flop', 'turn', 'river')

# Teto de candidatos testados por spot servido. Existe porque `_coerente` lê a árvore a cada
# tentativa: sem teto, um acervo que degradasse transformaria uma requisição de treino em varredura
# do banco inteiro, e o jogador veria a tela pendurada em vez de um erro.
_TETO_TENTATIVAS = 25


def _familia(label: str) -> str:
    """'bet_75pct' → 'bet', 'allin' → 'jam'. Mesma normalização do resto do trainer."""
    from leaklab.leak_trainer import _action_family
    return _action_family(label)


def _carrega(v):
    return json.loads(v) if isinstance(v, (str, bytes)) else v


def _sql_base() -> str:
    return f"""
        SELECT g.spot_hash, g.street, g.position, g.board, g.hero_hand, g.stack_bucket,
               g.gto_action, g.gto_freq, g.exploitability_pct,
               q.spot_json, q.tree_hash, s.actions
          FROM gto_nodes g
          JOIN gto_solver_queue q     ON q.spot_hash = g.spot_hash
          JOIN gto_tree_strategies s  ON s.tree_hash = q.tree_hash
         WHERE LOWER(g.street) IN ('flop','turn','river')
           AND g.exploitability_pct > {EXPLOIT_MIN}
           AND g.exploitability_pct <= {EXPLOIT_MAX}
           AND NOT (g.gto_freq >= 0.99 AND LOWER(g.gto_action) LIKE '%all%')
    """


def contar_acervo() -> dict:
    """Quantos nós servíveis existem, por família de ação. Existe para o diagnóstico PROVAR que
    mede: um acervo que devolve zero calado encerraria a investigação com uma resposta boa."""
    fora = {}
    with get_conn() as conn:
        linhas = conn.execute(_adapt(_sql_base())).fetchall()
    for r in linhas:
        fam = _familia(r['gto_action'] or '')
        fora[fam] = fora.get(fam, 0) + 1
    fora['_total'] = len(linhas)
    return fora


def _monta_spot(r: dict) -> Optional[dict]:
    """Nó → spot no MESMO formato que `generate_postflop_spot` devolve, para o front não
    distinguir a origem e o corretor não precisar de um segundo contrato."""
    from leaklab.leak_trainer import _cards_to_objs

    sj = _carrega(r['spot_json']) or {}
    meta = sj.get('_meta') or {}
    # ORDEM ORIGINAL do board (ver docstring). O de `gto_nodes` está ordenado e trocaria a carta
    # do river pela do turn.
    board = sj.get('board') or meta.get('board') or _carrega(r['board']) or []
    if not board:
        return None
    mao = sj.get('hero_hand') or meta.get('hero_hand') or _carrega(r['hero_hand'])
    if isinstance(mao, str):
        mao = [mao[i:i + 2] for i in range(0, len(mao), 2)]
    if not mao or len(mao) != 2:
        return None

    # O MENU depende de haver aposta na mesa, e o normalizador do trainer sozinho não sabe disso:
    # `_action_family` manda todo `bet_50pct` para 'raise', porque o catálogo antigo só tinha spots
    # ENFRENTANDO aposta. No acervo há nós com `facing_size_bb = 0`, e ali oferecer "raise" é pedir
    # ao jogador que aumente uma aposta que ninguém fez.
    enfrentando = float(sj.get('facing_size_bb') or 0) > 0
    acoes = _carrega(r['actions']) or []
    menu = []
    for a in acoes:
        f = _familia(a)
        if f == 'raise' and not enfrentando:
            f = 'bet'
        if f not in menu:
            menu.append(f)
    if len(menu) < 2:
        return None            # sem escolha real não é exercício

    street = (r['street'] or 'flop').lower()
    n_board = {'flop': 3, 'turn': 4, 'river': 5}.get(street, len(board))
    board = list(board)[:n_board]

    stack = float(sj.get('effective_stack_bb') or sj.get('hero_stack_bb') or 0) or None
    return {
        'kind':           'postflop',
        'origem':         'pool',          # rastro: separa do catálogo estático nas métricas
        'spot_hash':      r['spot_hash'],
        'tree_hash':      r['tree_hash'],
        'street':         street,
        'category':       f"pool:{street}",
        'position':       r['position'],
        'vs_position':    meta.get('vs_position') or '',
        'stack_bb':       stack,
        'facing_size_bb': float(sj.get('facing_size_bb') or 0),
        'pot_bb':         float(sj.get('pot_bb') or 0),
        'board':          board,
        'board_cards':    _cards_to_objs(board),
        'hand':           ''.join(mao),
        'hero_hand':      mao,
        'hero_cards':     _cards_to_objs(mao),
        'options':        menu,
        'xp_value':       30,
    }


def proximo_spot(rng: Optional[random.Random] = None, street: Optional[str] = None,
                 position: Optional[str] = None, evitar: Optional[set] = None) -> Optional[dict]:
    """Um spot do acervo, com a AÇÃO CERTA sorteada antes do nó.

    `evitar` recebe os `spot_hash` já servidos na sessão — o acervo é grande, mas sortear sem
    memória repete cedo por aniversário, e repetir foi a queixa que originou todo este trabalho.
    """
    rng = rng or random
    evitar = evitar or set()

    sql = _sql_base()
    params: list = []
    if street:
        sql += " AND LOWER(g.street) = ?"
        params.append(street.lower())
    if position:
        sql += " AND g.position = ?"
        params.append(position)

    with get_conn() as conn:
        linhas = conn.execute(_adapt(sql), tuple(params)).fetchall()
    if not linhas:
        return None

    por_familia: dict = {}
    for r in linhas:
        if r['spot_hash'] in evitar:
            continue
        por_familia.setdefault(_familia(r['gto_action'] or ''), []).append(r)
    if not por_familia:
        return None

    # sorteia a AÇÃO primeiro, entre as que o acervo realmente tem
    candidatas = [(fam, peso) for fam, peso in _MIX_ALVO if por_familia.get(fam)]
    if not candidatas:
        candidatas = [(fam, 1) for fam in por_familia]
    total = sum(p for _, p in candidatas)
    sorteio = rng.uniform(0, total)
    acc = 0.0
    alvo = candidatas[0][0]
    for fam, peso in candidatas:
        acc += peso
        if sorteio <= acc:
            alvo = fam
            break

    # Tenta a família sorteada primeiro e depois as outras. `_coerente` custa uma leitura por
    # candidato, e é ele que garante que nada chegue ao jogador sem veredito possível — nem com um
    # veredito que fale de ações fora do menu.
    ordem = [alvo] + [f for f in por_familia if f != alvo]
    tentativas = 0
    for fam in ordem:
        grupo = por_familia[fam][:]
        rng.shuffle(grupo)
        for r in grupo:
            if tentativas >= _TETO_TENTATIVAS:
                return None
            tentativas += 1
            spot = _monta_spot(dict(r))
            if spot and _coerente(spot):
                return spot
    return None


def estrategia_da_mao(tree_hash: str, hero_hand) -> Optional[dict]:
    """A linha da MÃO na `hand_table`, no formato que `grade_from_hand_strategy` já consome.

    Lê do banco na hora da correção, nunca do que voltou do cliente: o spot faz a viagem de ida e
    volta pelo navegador, e a resposta certa não pode depender do que voltou de lá.

    **Devolve `None` em 34% dos nós, e isso é estrutural.** Medido em produção: `gto_tree_strategies`
    tem UMA tabela por árvore (5.986 linhas, 5.986 `tree_hash` distintos), com a range de um jogador
    só. Quando o herói daquele nó é o outro, a mão dele não está lá — parente do
    [[project_postflop_hero_ip_bug]]. Não há segunda tabela para consultar; o nó simplesmente não é
    gradeável, e o lugar de descobrir isso é a SELEÇÃO, não a correção.

    **Por que não resolver via `lookup_gto`:** ele re-deriva o hash a partir dos parâmetros, e a
    reconstrução a partir do `spot_json` não reproduz o mesmo nó. No teste ele resolveu um nó
    DIFERENTE e devolveu um veredito incoerente com a tela: o menu oferecia check/bet e a correção
    respondia sobre fold/call/raise, marcando "errado, o certo era fold" com fold fora do menu.
    Veredito sobre outro nó é pior do que veredito nenhum.
    """
    if not tree_hash or not hero_hand:
        return None
    if isinstance(hero_hand, str):
        hero_hand = [hero_hand[i:i + 2] for i in range(0, len(hero_hand), 2)]
    alvos = {''.join(hero_hand), ''.join(reversed(hero_hand))}

    with get_conn() as conn:
        r = conn.execute(_adapt(
            "SELECT actions, hand_table FROM gto_tree_strategies WHERE tree_hash = ?"),
            (tree_hash,)).fetchone()
    if not r:
        return None
    acoes = _carrega(r['actions']) or []
    tabela = _carrega(r['hand_table']) or []
    linha = next((it for it in tabela if (it.get('hand') or '') in alvos), None)
    if not linha:
        return None                       # mão fora da tabela: nó de outro jogador
    freqs = linha.get('freqs') or []
    evs = linha.get('evs') or []
    if len(freqs) != len(acoes):
        return None                       # tabela e cabeçalho fora de sincronia: não arrisca
    acts = {}
    for i, rotulo in enumerate(acoes):
        acts[rotulo] = {'frequency': float(freqs[i] or 0),
                        'ev_bb': (float(evs[i]) if i < len(evs) and evs[i] is not None else None)}
    melhor = max(acts.items(), key=lambda kv: kv[1]['frequency'])[0] if acts else None
    return {'actions': acts, 'best_action': melhor}


def _rotula(res: dict, enfrentando: bool) -> dict:
    """Sem aposta na mesa, 'raise' vira 'bet' em TUDO que o jogador lê.

    O corretor agrega por família e a família de `bet_50pct` é 'raise'. Sem esta troca, um spot
    onde ninguém apostou volta dizendo "o certo era raise" enquanto a tela oferece "bet": a mesma
    ação com dois nomes, e o jogador conclui que escolheu errado.
    """
    if enfrentando:
        return res
    troca = lambda a: 'bet' if a == 'raise' else a
    res['best_action'] = troca(res.get('best_action') or '')
    res['new_action'] = troca(res.get('new_action') or '')
    res['recommended'] = [troca(a) for a in (res.get('recommended') or [])]
    res['gto_strategy'] = [{**d, 'action': troca(d.get('action'))}
                           for d in (res.get('gto_strategy') or [])]
    res['hand_freq'] = {troca(k): v for k, v in (res.get('hand_freq') or {}).items()}
    return res


def corrigir(spot: dict, action: str) -> Optional[dict]:
    """Corrige um spot do acervo. `None` quando o nó não é gradeável — o chamador PULA."""
    from leaklab.leak_trainer import grade_from_hand_strategy
    hs = estrategia_da_mao(spot.get('tree_hash'), spot.get('hero_hand') or spot.get('hand'))
    if not hs or not hs.get('actions'):
        return None
    res = grade_from_hand_strategy(hs, action)
    res['validation_source'] = 'gto_pool_postflop'
    return _rotula(res, float(spot.get('facing_size_bb') or 0) > 0)


def _coerente(spot: dict) -> bool:
    """O nó é gradeável, o menu faz sentido na mesa, e o veredito fala das MESMAS ações da tela.

    As três coisas, e não só a primeira:

    - **gradeável**: 34% dos nós têm a mão do herói fora da tabela;
    - **menu possível**: nó sem aposta na mesa não pode oferecer FOLD. Existe no acervo (a lista
      de ações da árvore nem sempre bate com o `facing_size_bb` gravado), e "fold" com ninguém
      tendo apostado é uma opção que não existe em poker nenhum;
    - **veredito dentro do menu**: um veredito que responde sobre ação fora do menu diz ao jogador
      que ele errou por não escolher algo que não estava na tela. Foi o que apareceu quando tentei
      gradear por `lookup_gto` e ele resolveu outro nó.
    """
    hs = estrategia_da_mao(spot.get('tree_hash'), spot.get('hero_hand'))
    if not hs or not hs.get('actions'):
        return False
    menu = set(spot.get('options') or [])
    enfrentando = float(spot.get('facing_size_bb') or 0) > 0
    if not enfrentando and 'fold' in menu:
        return False
    if enfrentando and 'check' in menu:
        return False                       # não se dá check com aposta na mesa
    familias = set()
    for rotulo, d in hs['actions'].items():
        if float((d or {}).get('frequency') or 0) <= 0.001:
            continue                       # ação que o GTO nunca joga não precisa estar no menu
        f = _familia(rotulo)
        familias.add('bet' if (f == 'raise' and not enfrentando) else f)
    return bool(familias) and familias <= menu
