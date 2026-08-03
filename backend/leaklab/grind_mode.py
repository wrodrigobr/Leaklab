"""
grind_mode.py — percorrer uma mão REAL inteira, decisão por decisão, heads-up.

Pedido do usuário depois de ver o Practice do GTO Wizard: em vez de um spot solto, a mão roda do
preflop ao river, uma decisão por vez, com veredito a cada uma e nota no fim.

## O que este modo é, e o que ele NÃO é

**É replay de mão real, não simulação.** O GTO Wizard reparte cartas novas a cada mão porque tem a
árvore inteira pré-computada; aqui só existe nó onde alguém mandou solvar. Então o jogador percorre
uma mão que ACONTECEU, contra o que o vilão de fato fez. Para a tese do produto isso é melhor, não
pior: a linha do vilão é humana, não um robô jogando GTO.

**Consequência que precisa estar clara na tela:** as cartas do vilão e o board já estão decididos.
O jogador não muda o rumo da mão — ele responde "o que o GTO faria aqui", e a mão segue o caminho
que seguiu. Vender isso como simulação seria mentir.

## Anonimização é requisito de ENTRADA

As mãos vêm do acervo de todos, não só das do próprio jogador. O que sai daqui tem **posição e
stack em BB, e nada mais**: sem nick, sem `tournament_id`, sem `hand_id`, sem data. O identificador
que viaja é um token opaco, e o servidor é quem sabe o que ele significa.

Isso é requisito de entrada, não acabamento de tela: uma vez servido, não dá para despublicar da
cabeça de quem viu. Resta um resíduo aceito — quem estava NAQUELA mesa pode reconhecer a mão pela
combinação de board, stacks e linha. Não dá para eliminar sem descaracterizar o exercício, e o que
essa pessoa reconhece é a própria mesa, não a identidade de quem subiu o arquivo.

## Por que heads-up

Sem multiway, toda street tem gabarito: o solver é HU-only. Multiway entraria como exercício sem
veredito, que é justamente o defeito que o Ghost Table levou o dia de hoje para tirar.

## Medido em produção (2026-08-02)

809 mãos com decisão postflop heads-up · 632 100% heads-up · 456 com veredito em todas as streets ·
**338 jogáveis de ponta a ponta**, das quais 218 com duas ou mais decisões postflop.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

from database.schema import get_conn
from database.repositories import _adapt

# Segredo do token da mão. Sem ele, o token seria adivinhável e alguém poderia enumerar o acervo
# inteiro pedindo mãos por id sequencial. Cai para uma constante em dev, onde não há o que proteger.
_SEGREDO = os.getenv('LEAKLAB_SECRET') or 'dev-grind'

# `vs_position` não vem vazio quando não há vilão: vem o LITERAL 'unknown'. Medido: 3.600 linhas
# de preflop com esse valor. Testar por string vazia não pega, e a tela escrevia "SB vs unknown"
# numa abertura onde ainda não existe adversário. Normaliza aqui, na leitura, para que nenhum
# consumidor precise saber do sentinela.
_SEM_VILAO = ('', 'unknown', 'none', 'null', '-')


def _vilao(v) -> str:
    s = str(v or '').strip()
    return '' if s.lower() in _SEM_VILAO else s


_ORDEM_STREET = {'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}
_TAMANHO_BOARD = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}

# Mesma faixa sadia do resto do projeto — ver `trainer_pool`.
EXPLOIT_MIN, EXPLOIT_MAX = 0.05, 3.0


def token_da_mao(tournament_id: int, hand_id: str) -> str:
    """Identificador OPACO da mão. Nada nele revela torneio, jogador ou data."""
    crua = f'{tournament_id}:{hand_id}:{_SEGREDO}'.encode('utf-8')
    return hashlib.blake2b(crua, digest_size=10).hexdigest()


def _carrega(v):
    """JSON quando é JSON, valor cru quando não é. `json.loads` direto explodia.

    `decisions.board` é JSON (`'["3h","2d","6d"]'`), mas `decisions.hero_cards` é gravado COLADO
    (`'JsTd'`). São duas colunas vizinhas com formatos diferentes, e é a mesma armadilha que já
    custou meses aqui: um diagnóstico fazia `split()` num `hero_cards` colado e todo hash saía
    errado, reportando "zero perdidas" com confiança.
    """
    if not isinstance(v, (str, bytes)):
        return v
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return v


def _cartas(v) -> list:
    """Duas cartas, venham como lista JSON ou coladas."""
    v = _carrega(v)
    if isinstance(v, list):
        return [str(c) for c in v]
    s = str(v or '').replace(' ', '')
    return [s[i:i + 2] for i in range(0, len(s), 2)] if len(s) >= 4 else []


def _sql_maos(min_decisoes: int) -> str:
    """Mãos 100% heads-up no postflop, com nó sadio e gradeável em TODAS as decisões postflop.

    O `NOT EXISTS` é o que garante o "TODAS": sem ele, bastaria uma decisão coberta para a mão
    entrar, e o jogador travaria no meio da mão sem veredito — que é pior do que não oferecê-la.
    """
    return f"""
        SELECT d.tournament_id, d.hand_id, COUNT(*) AS n
          FROM decisions d
          JOIN gto_nodes g            ON g.spot_hash = d.spot_hash
          JOIN gto_solver_queue q     ON q.spot_hash = g.spot_hash
          JOIN gto_tree_strategies s  ON s.tree_hash = q.tree_hash
         WHERE d.street IN ('flop','turn','river')
           AND d.n_active_opponents = 1
           AND g.exploitability_pct > {EXPLOIT_MIN}
           AND g.exploitability_pct <= {EXPLOIT_MAX}
           AND NOT EXISTS (
                 SELECT 1 FROM decisions x
                  WHERE x.tournament_id = d.tournament_id
                    AND x.hand_id       = d.hand_id
                    AND x.street IN ('flop','turn','river')
                    AND (x.n_active_opponents <> 1 OR x.spot_hash IS NULL))
         GROUP BY d.tournament_id, d.hand_id
        HAVING COUNT(*) >= {int(min_decisoes)}
    """


def maos_disponiveis(min_decisoes: int = 2) -> list[tuple]:
    """(tournament_id, hand_id, n_decisoes) das mãos jogáveis. Uso interno — nunca vai para o
    cliente, porque carrega identificador."""
    with get_conn() as conn:
        linhas = conn.execute(_adapt(_sql_maos(min_decisoes))).fetchall()
    return [(r['tournament_id'], r['hand_id'], int(r['n'] or 0)) for r in linhas]


def _acao_do_vilao(anterior: dict, atual: dict) -> Optional[dict]:
    """O que o vilão fez ENTRE duas decisões do herói, deduzido do pote e da aposta enfrentada.

    A linha do vilão não está gravada como evento; o que existe é o estado antes de cada decisão do
    herói. Deduzir é honesto aqui porque heads-up só tem um outro jogador: se o pote cresceu e há
    aposta na mesa, foi ele. É o mesmo raciocínio que o replayer já faz para desenhar a mesa.
    """
    if not anterior:
        return None
    facing = float(atual.get('facing_bet') or 0)
    mesma_street = anterior.get('street') == atual.get('street')
    if facing > 0:
        return {'tipo': 'aposta' if mesma_street else 'aposta', 'bb': round(facing, 2)}
    if not mesma_street:
        return {'tipo': 'check', 'bb': 0.0}
    return None


def montar_mao(tournament_id: int, hand_id: str) -> Optional[dict]:
    """A mão inteira, ANONIMIZADA, pronta para ser percorrida.

    Devolve os passos na ordem em que aconteceram. Cada passo traz o que a tela precisa desenhar e
    o `tree_hash` para o servidor corrigir — nunca a resposta.
    """
    with get_conn() as conn:
        linhas = conn.execute(_adapt("""
            SELECT d.id, d.street, d.hero_cards, d.board, d.position, d.vs_position,
                   d.stack_bb, d.pot_size, d.facing_bet, d.action_taken, d.spot_hash,
                   d.level_bb, q.tree_hash, q.spot_json
              FROM decisions d
              LEFT JOIN gto_solver_queue q ON q.spot_hash = d.spot_hash
             WHERE d.tournament_id = ? AND d.hand_id = ?
             ORDER BY d.id"""), (tournament_id, hand_id)).fetchall()
    if not linhas:
        return None

    linhas = [dict(r) for r in linhas]
    linhas.sort(key=lambda r: (_ORDEM_STREET.get((r['street'] or '').lower(), 9), r['id']))

    # O board vem COMPLETO em toda linha (5 cartas até no preflop). Mostrar assim entregaria as
    # cartas futuras — o jogador veria o river antes de decidir no flop. Corta por street.
    board_final = _carrega(linhas[-1].get('board')) or []
    if isinstance(board_final, str):
        board_final = _cartas(board_final)
    mao = _cartas(linhas[0].get('hero_cards'))
    if len(mao) != 2 or len(board_final) < 3:
        return None            # mão sem cartas ou sem board não vira exercício

    # O PREFLOP quase nunca guarda `vs_position` (vem 'unknown'), mas o postflop guarda — e num
    # pote heads-up quem estava no flop estava no preflop também. Herdar do primeiro passo que sabe
    # é dedução honesta, e sem ela a mesa fica sem ninguém: reportado com o herói no BB, onde a
    # regra "quem agiu antes foldou" apagava os oito outros assentos.
    vilao_da_mao = ''
    for r in linhas:
        v = _vilao(r.get('vs_position'))
        if v:
            vilao_da_mao = v
            break

    passos, anterior = [], None
    for r in linhas:
        street = (r['street'] or '').lower()
        n = _TAMANHO_BOARD.get(street, 0)
        facing = float(r['facing_bet'] or 0)
        passo = {
            'street':         street,
            'board':          list(board_final)[:n],
            'hero_hand':      mao,
            'position':       r['position'],
            'vs_position':    _vilao(r['vs_position']) or vilao_da_mao,
            'stack_bb':       round(float(r['stack_bb'] or 0), 1),
            'pot_bb':         round(float(r['pot_size'] or 0), 1),
            'facing_size_bb': round(facing, 2),
            'options':        (['fold', 'call', 'raise'] if facing > 0
                               else ['check', 'bet']) if street != 'preflop' else
                              (['fold', 'call', 'raise'] if facing > 0 else ['fold', 'raise']),
            'tree_hash':      r.get('tree_hash'),
            'vilao_antes':    _acao_do_vilao(anterior, r),
        }
        passos.append(passo)
        anterior = r

    return {
        'token':  token_da_mao(tournament_id, hand_id),
        'passos': passos,
        'total':  len(passos),
        # NADA de tournament_id, hand_id, nick, data ou nome de torneio. Ver docstring do módulo.
    }


def _mao_por_token(token: str) -> Optional[tuple]:
    """Token → (tournament_id, hand_id). Varre as mãos jogáveis e compara o token.

    Custa uma varredura, e é de propósito: guardar o mapa token→mão numa tabela seria um segundo
    lugar onde o identificador vive, e o ponto do token é justamente ele não existir em lugar
    nenhum além do cálculo. Com 336 mãos, a varredura é barata.
    """
    for tid, hid, _ in maos_disponiveis(min_decisoes=1):
        if token_da_mao(tid, hid) == token:
            return tid, hid
    return None


# Teto de mãos testadas por requisição. `_toda_gradeavel` faz uma leitura por passo, e sem teto
# uma degradação do acervo transformaria "próxima mão" numa varredura do banco inteiro.
_TETO_TENTATIVAS = 20


def _toda_gradeavel(mao: dict) -> bool:
    """TODOS os passos respondem a uma correção de verdade?

    O SQL garante que existe nó solvado, e isso NÃO é o mesmo que gradeável: medido, 30% dos passos
    postflop voltavam sem veredito porque a mão do herói não está na `hand_table` daquela árvore —
    uma tabela por árvore, do range de um jogador só. Numa mão inteira o estrago é pior que num
    spot solto: o jogador percorre metade da mão e trava no meio, sem entender por quê.

    Conferir aqui custa uma leitura por passo e uma vez por mão servida. Vale.
    """
    for passo in mao.get('passos') or []:
        try:
            if corrigir_passo(passo, (passo.get('options') or ['check'])[0]) is None:
                return False
        except Exception:
            return False
    return True


def proxima_mao(rng=None, evitar: Optional[set] = None,
                min_decisoes: int = 2) -> Optional[dict]:
    """Uma mão jogável, ainda não vista nesta sessão e gradeável do começo ao fim."""
    import random as _r
    rng = rng or _r
    evitar = evitar or set()
    disponiveis = [m for m in maos_disponiveis(min_decisoes)
                   if token_da_mao(m[0], m[1]) not in evitar]
    if not disponiveis:
        return None
    rng.shuffle(disponiveis)
    for tid, hid, _ in disponiveis[:_TETO_TENTATIVAS]:
        mao = montar_mao(tid, hid)
        if mao and mao['passos'] and _toda_gradeavel(mao):
            return mao
    return None


def corrigir_passo(passo: dict, acao: str) -> Optional[dict]:
    """Corrige UM passo da mão.

    Postflop lê o nó pré-solvado pelo `tree_hash` (mesma porta do `trainer_pool`); preflop usa o
    corretor canônico, que já é a fonte única do preflop. Devolve `None` quando não dá para gradear
    — e o chamador PULA em vez de inventar veredito, mesma regra do resto do treino.
    """
    street = (passo.get('street') or '').lower()
    if street == 'preflop':
        from leaklab.leak_trainer import grade_canonical_spot
        alvo = dict(passo)
        alvo.pop('board', None)                 # sem board = caminho preflop do corretor
        alvo['hand'] = ''.join(passo.get('hero_hand') or [])
        alvo['facing_size'] = passo.get('facing_size_bb') or 0
        try:
            return grade_canonical_spot(alvo, acao)
        except Exception:
            return None
    from leaklab.trainer_pool import corrigir as _corrige
    return _corrige(passo, acao)
