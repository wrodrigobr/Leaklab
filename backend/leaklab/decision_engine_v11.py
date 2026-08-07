from __future__ import annotations
from typing import Dict, Any
import logging as _logging
import os

from leaklab.verdict import icm_zone_softens_fold

_gto_log = _logging.getLogger('leaklab.gto')

_GTO_VALID_POSITIONS = {'UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}
_VALID_CARD_RANKS    = set('AKQJT98765432')
_VALID_CARD_SUITS    = set('shdc')


def _log_gto_miss(scope: str, street: str, position: str, reason: str) -> None:
    _gto_log.debug('GTO %s miss — street=%s pos=%s reason=%s', scope, street, position, reason)


def _validate_decision_input(inp: dict) -> list:
    """
    Valida campos numéricos e enumerados antes do GTO lookup.
    Retorna lista de warning strings (não bloqueia avaliação).
    """
    warnings = []
    spot    = inp.get('spot') or {}
    street  = (inp.get('street') or '').strip()
    pos     = (spot.get('position') or '').upper().strip()

    stack = spot.get('effectiveStackBb')
    if stack is not None:
        try:
            s = float(stack)
            if not (0 < s < 10_000) or s != s:
                warnings.append(f'stack_bb inválido: {stack!r}')
        except (TypeError, ValueError):
            warnings.append(f'stack_bb não numérico: {stack!r}')

    facing = spot.get('facingSize')
    if facing is not None:
        try:
            f = float(facing)
            if f < 0 or f != f:
                warnings.append(f'facing_size negativo/NaN: {facing!r}')
        except (TypeError, ValueError):
            warnings.append(f'facing_size não numérico: {facing!r}')

    if pos and pos not in _GTO_VALID_POSITIONS:
        warnings.append(f'position desconhecida: {pos!r}')

    if street and street != 'preflop':
        board = spot.get('board') or []
        if isinstance(board, list):
            for card in board:
                if not isinstance(card, str) or len(card) != 2:
                    warnings.append(f'card inválida no board: {card!r}')
                    break
                if card[0].upper() not in _VALID_CARD_RANKS or card[1].lower() not in _VALID_CARD_SUITS:
                    warnings.append(f'card inválida: {card!r}')
                    break

    return warnings


# ── GTO helpers ───────────────────────────────────────────────────────────────

def _norm_gto_action(a: str) -> str:
    """Normaliza ação para comparação: shove/jam/allin → 'allin'."""
    a = (a or '').lower()
    if a in ('shove', 'jam', 'allin', 'all-in', 'all in'):
        return 'allin'
    return a


def _action_family(a: str) -> str:
    """Colapsa um label de ação (inclusive parametrizado: bet_50pct, raise_103pct)
    para a família canônica {fold,check,call,bet,raise,allin}."""
    from leaklab.gto_utils import normalize_gto_action
    fam = normalize_gto_action(a or '')
    return 'allin' if fam == 'jam' else fam


def _match_strategy_entries(player_action: str, strategy: list) -> list:
    """Entradas da estratégia que correspondem à ação jogada, por FAMÍLIA de ação.

    Um shove (allin) é um raise/bet no maior sizing — quando a árvore não tem
    ação allin explícita, casa com as ações 'raise' (facing bet) ou, na falta,
    'bet'. Sem isso, shove vs árvore com raise_103pct dava freq 0 → gto_critical
    mesmo quando o hand-view dizia raise 100% (bug do full house no river).
    """
    played = _action_family(player_action)
    fams = [(s, _action_family(s.get('action', ''))) for s in strategy]
    exact = [s for s, f in fams if f == played]
    if played != 'allin':
        return exact
    # Um shove É a versão max-size de uma agressão. O "acerto da AÇÃO" é a frequência de
    # AGREDIR (raise facing bet / bet leading); o tamanho (allin vs sized) é questão de
    # SIZING, não de ação errada. Então casa com allin explícito + a família raise/bet —
    # mesmo quando há entrada allin com freq ~0 (antes só casava a allin@0% → gto_critical
    # indevido; mão 118: trinca dando lead/jam por valor era marcada Desvio Crítico).
    agg = list(exact)
    for fam in ('raise', 'bet'):
        agg += [s for s, f in fams if f == fam]
    return agg


def _gto_action_matches(player_action: str, gto_action: str) -> bool:
    """Verifica se a ação do jogador corresponde à ação GTO primária."""
    p = _norm_gto_action(player_action)
    g = _norm_gto_action(gto_action)
    if p == g:
        return True
    aggressive = {'bet', 'raise', 'shove', 'jam', 'allin'}
    if g.startswith('bet') or g.startswith('raise'):
        return p in aggressive
    return p.startswith(g) or g.startswith(p)


def _gto_classify_from_strategy(player_action: str, strategy: list) -> tuple:
    """
    Classifica usando frequência real + EV diff da ação jogada.

    Frequência isolada penaliza estratégias mistas legítimas (ex: call 15% com
    ev_diff = 0.02bb não é desvio crítico). A combinação freq + ev_diff evita
    isso: só sobe a severidade quando o custo de EV é significativo.

    Retorna (gto_label, played_freq).
    """
    matched = _match_strategy_entries(player_action, strategy)
    played_freq = max((float(s.get('frequency') or 0.0) for s in matched), default=0.0)
    # EV da ação jogada: melhor EV entre as entradas casadas — INCLUSIVE freq 0.
    # O matcher antigo só registrava EV quando freq > 0; uma ação com freq 0.0 e
    # ev_diff pequeno (ex.: check 0% mas -0.25bb) caía em ev_diff=None →
    # gto_critical indevido (bug dos labels inconsistentes do torneio 388).
    _evs = [float(s['ev_bb']) for s in matched if s.get('ev_bb') is not None]
    played_ev: float | None = max(_evs) if _evs else None

    # EV diff vs top action (positivo = jogador perdeu EV)
    ev_diff: float | None = None
    if strategy and played_ev is not None:
        top_ev = strategy[0].get('ev_bb')
        if top_ev is not None:
            ev_diff = float(top_ev) - played_ev

    # Tier 1: GTO joga isso a maioria do tempo → correto
    if played_freq >= 0.60:
        return 'gto_correct', played_freq

    # Tier 2: parte significativa do range GTO → misto por definição
    if played_freq >= 0.25:
        return 'gto_mixed', played_freq

    # Tier 3: 10-25% — decide pelo custo de EV
    if played_freq >= 0.10:
        # EV diff < 0.15bb: dentro do ruído de estratégia mista
        if ev_diff is None or ev_diff < 0.15:
            return 'gto_mixed', played_freq
        return 'gto_minor_deviation', played_freq

    # Tier 4: < 10% — frequência baixa, severidade pelo custo real
    # Se a ação aparece no mix GTO (>=3%), evita 'gto_critical' sem evidência de EV alto:
    # 7% de bet num check-heavy spot ainda é parte do range; não merece "Desvio Crítico".
    if ev_diff is not None:
        if ev_diff < 0.30:
            return 'gto_minor_deviation', played_freq
        # Custo de EV alto E freq baixa
        return 'gto_critical', played_freq
    # Sem ev_diff: usa freq como proxy. Frequência >=3% = ação faz parte do range GTO.
    if played_freq >= 0.03:
        return 'gto_minor_deviation', played_freq
    return 'gto_critical', played_freq


def _gto_classify(player_action: str, gto_action: str, gto_freq: float, hero_equity: float | None) -> str:
    """
    Classificação simplificada (fallback quando strategy_json não disponível).
    Usa apenas top action + frequência estimada da alternativa.
    """
    if _gto_action_matches(player_action, gto_action):
        return 'gto_correct'

    alt_freq = 1.0 - gto_freq

    if alt_freq >= 0.40:
        return 'gto_mixed'
    if alt_freq >= 0.15:
        if hero_equity is not None and hero_equity >= 0.60:
            return 'gto_mixed'
        return 'gto_minor_deviation'
    return 'gto_critical'


def _gto_label_cap(label: str, gto_label: str) -> str:
    """
    Reconcilia label heuristico com sinal do solver:
      - gto_correct/gto_mixed: acao validada pelo GTO -> cap em 'marginal'
        (nunca pode ser small/clear mistake)
      - gto_minor_deviation: solver classifica como desvio leve -> cap em
        'small_mistake' (impede clear_mistake quando proprio solver diz
        que e leve)
      - gto_critical: solver diz erro grave -> floor em 'small_mistake'
        (impede engine de dar pass como 'standard'/'marginal' quando
        solver classifica como critico)
    """
    if gto_label in ('gto_correct', 'gto_mixed'):
        if label in ('small_mistake', 'clear_mistake'):
            return 'marginal'
    elif gto_label == 'gto_minor_deviation':
        if label == 'clear_mistake':
            return 'small_mistake'
    elif gto_label == 'gto_critical':
        if label in ('standard', 'marginal'):
            return 'small_mistake'
    return label


def _enrich_preflop_gto(input_data: Dict[str, Any]) -> dict:
    """Range GTO preflop — lookup por posição, stack e cenário. Silencioso em caso de erro."""
    if input_data.get('street') != 'preflop':
        return {'available': False}

    spot       = input_data.get('spot', {})
    ctx        = input_data.get('context', {})
    hero_cards = input_data.get('hero_cards', [])
    if not hero_cards:
        return {'available': False}

    try:
        from leaklab.gto_utils import hand_to_type
        # Porta ÚNICA de estratégia preflop (mesma do trainer/academy). Consome `raw` = dict cru do
        # analyze_preflop (dialeto de armazenamento), então o resto do engine segue sem mudança.
        # Ver [[project_strategy_provider_single_source]].
        from leaklab.strategy_provider import preflop_strategy
        h_type = hand_to_type(hero_cards)
        if not h_type:
            return {'available': False}
        return preflop_strategy(
            position       = spot.get('position', ''),
            hero_hand_type = h_type,
            stack_bb       = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20),
            action_taken   = input_data.get('player_action', ''),
            # `facingSize` vem em FICHAS e as vezes vem VAZIO; `facingToBb` e o valor que o
            # pipeline calcula e no qual o resto do produto confia. A consulta roteia por
            # `facing_size`, entao com ele em 0 a cobertura SOME mesmo havendo no GTO — medido:
            # BB vs SB a 8,6bb responde `jam` com facing preenchido e `indisponivel` sem ele.
            # Foi o que fez a mao 2790343346 ficar "sem cobertura" tendo o numero certo ao lado.
            facing_size    = float(spot.get('facingSize') or spot.get('facingToBb') or 0),
            vs_position    = spot.get('villainPosition', ''),
            is_3bet_pot    = bool(input_data.get('is_3bet', False)),
            n_players      = spot.get('nPlayers'),
            facing_raises      = int(spot.get('preflopRaisesFaced') or 0),
            hero_was_aggressor = bool(spot.get('heroWasAggressor', False)),
            is_pko             = bool(ctx.get('isPko')),
            facing_to_bb       = float(spot.get('facingToBb') or 0),
            facing_allin       = bool(spot.get('facingAllin', False)),
        )['raw']
    except Exception as exc:
        _log_gto_miss('preflop', input_data.get('street'), spot.get('position'), str(exc)[:120])
        return {'available': False}


_LABEL_SEV = {'standard': 0, 'marginal': 1, 'small_mistake': 2, 'clear_mistake': 3}
_SEV_LABEL = {0: 'standard', 1: 'marginal', 2: 'small_mistake', 3: 'clear_mistake'}


# Tema 1: limiar de EV abaixo do qual um 'leak'/'major_leak' preflop é desvio de
# baixo custo, não erro grave. O postflop já escala severidade por EV (ver
# _gto_classify_from_strategy, tiers 0.15/0.30bb); o preflop nunca recebeu isso.
# 0.12bb separa limpo os casos validados pelo coach (75o 0.04 / A2o 0.023 /
# A4o 0.006 → desvio leve) do 3-bet de par baixo que o próprio coach critica
# (22 a 0.281bb → permanece small_mistake).
_PREFLOP_EV_MINOR_BB = 0.12


def _preflop_gto_label_adjust(label: str, quality: str, ev_loss_bb: float | None = None) -> str:
    """
    Ajusta label preflop pelo range GTO.

    correct    → sempre 'standard'  (ação confirmada pelo GTO)
    acceptable → cap em 'marginal'  (subótimo mas defensável)
    leak       → floor em 'small_mistake' (não capeia clear_mistake)
    major_leak → floor em 'small_mistake' (não capeia clear_mistake)

    Tema 1 (recalibração coach #27): quando o EV perdido medido é < _PREFLOP_EV_MINOR_BB,
    o 'leak'/'major_leak' é tratado como desvio LEVE — cap em 'marginal' em vez de
    floor em 'small_mistake'. Sem isso, um 3-bet light que custa 0.006bb levava o
    mesmo selo de um erro de vários bb.
    """
    cur = _LABEL_SEV.get(label, 1)
    if quality == 'correct':
        return 'standard'
    # Desvio mínimo (ação mista válida, ex.: vs_3bet/4bet rebaixado) — cap em 'marginal'.
    if quality in ('acceptable', 'gto_minor_deviation', 'minor_mistake'):
        return _SEV_LABEL[min(cur, _LABEL_SEV['marginal'])]
    if quality in ('leak', 'major_leak'):
        # RC-A: 'major_leak' = ação FORA do range (freq GTO ~0%). EV baixo aqui NÃO é "defensável"
        # (custa pouco JUSTAMENTE porque não devia estar no pote) — nunca rebaixa por EV. Só 'leak'
        # (low-freq dentro de um mix, freq>0) mantém o softening EV-minor.
        if quality == 'leak' and ev_loss_bb is not None and ev_loss_bb < _PREFLOP_EV_MINOR_BB:
            return _SEV_LABEL[min(cur, _LABEL_SEV['marginal'])]
        return _SEV_LABEL[max(cur, _LABEL_SEV['small_mistake'])]
    return label


# Teto de severidade pelo EV (recalibração coach #27): um erro só é GRAVE se custar EV
# real. Uma ação de baixa frequência GTO (gto_critical) que custa quase nada é spot
# misto/marginal, não erro grave — o coach aprova justamente esses. Capeia (nunca eleva):
#   EV < 0.30bb → no máximo 'marginal'   (custo ínfimo)
#   EV < 1.50bb → no máximo 'small_mistake' (custo real mas pequeno)
#   EV >= 1.50bb → mantém (erro grave de verdade — ex.: fold de TT a 4.4bb fica clear)
# NÃO toca o gto_label (frequência é fato do solver); só a severidade do veredito.
_EV_CEIL_MARGINAL_BB = 0.30
_EV_CEIL_SMALL_BB    = 1.50
_LABEL_MAX_SCORE = {'standard': 0.08, 'marginal': 0.18, 'small_mistake': 0.35, 'clear_mistake': 1.0}


_EV_RELIABLE_SOURCES = ('gw_har', 'solver_hand', 'gto_tree', 'hand_aware')

# Teto de calibração: acima disto o EV em bb não é confiável como QUANTIDADE.
#
# Medido em produção (2026-07-27), EV postflop `solver_hand` por profundidade:
#     <20bb  n=30  média 1,56  máx 17,5
#     20-40  n=54  média 2,07  máx 28,2
#     40-60  n=18  média 1,76  máx 14,8
#     60-100 n=15  média 0,39  máx  1,2     ← a faixa MAIS comportada; o cap funciona aqui
#     100+   n= 3  média 30,4  máx 90,3     ← três decisões produzindo toda a distorção
#
# A causa: acima de 100bb o lookup usa 100bb como profundidade efetiva. A AÇÃO transfere (é o que
# a aproximação promete e o que está documentado), mas o EV volta na escala do solve de 100bb
# enquanto o stack real é outro. Ninguém prometeu que o número em bb transferia — e ele não.
#
# O sintoma que denunciou: "-90,3bb num FOLD" no relatório de evolução. Foldar não pode custar
# 90bb; o que você abre mão é limitado pelo pote. E não era só cosmético: `_ev_severity_ceiling`
# usa esse número como PISO de severidade, então um fold defensável virava erro no card do
# jogador — a guarda de lá ("nunca em nó aproximado") não pega este caso, porque a fonte
# `solver_hand` É confiável; o que não é confiável é a PROFUNDIDADE.
_EV_TRUST_MAX_BB = 100.0


# Implied odds no teto de plausibilidade: quanto do que sobra atrás pode entrar no pote depois.
# 2x é generoso de propósito — o teto existe para pegar número IMPOSSÍVEL, não para discutir com
# o solver sobre spots apertados. Se ele passa nem desta régua, não está descrevendo este spot.
_IMPLIED_ODDS_MULT = 2.0
_FOLD_ACTIONS = ('fold', 'folds')


def ev_loss_fold_ceiling(equity, pot_bb, facing_bb, stack_bb):
    """Teto do que FOLDAR pode custar, pela aritmética de pot odds do próprio engine.

    Existe porque `ev_loss_bb` do solver vem na escala do POTE COM QUE O NÓ FOI SOLVADO, e
    `compute_spot_hash` NÃO inclui o tamanho do pote — só street, posição, board, mão, bucket de
    stack, facing e tipo de pote. Um nó solvado num pote de 5bb pode ser servido a um spot com
    pote de 31,8bb, e o número volta numa escala que não é a daquele spot. O pote solvado não é
    gravado em lugar nenhum, então não há como reescalar; o que dá é conferir.

    Medido em produção (2026-07-27), com a equity que o PRÓPRIO engine gravou:

        equity 33,0% · precisa 46,6% → foldar está CERTO → o engine marcou −28,2bb e gto_critical
        equity 30,8% · precisa 37,5% → foldar está CERTO → o engine marcou  −5,1bb

    Duas contradições de direção em dez decisões. Nas demais o valor gravado ia de 2x a 8x a
    aritmética — e em duas era METADE dela. Não erra para um lado só, o que descarta escala fixa.

    Devolve None quando falta dado para a conta (aí não há do que discordar, e o EV passa)."""
    try:
        if equity is None or pot_bb is None or facing_bb is None:
            return None
        eq, pot, facing = float(equity), float(pot_bb), float(facing_bb)
        stack = float(stack_bb) if stack_bb is not None else facing
        if pot < 0 or facing < 0:
            return None
        call = min(facing, stack) if stack > 0 else facing
        atras = max(0.0, stack - call)
        ganho_max = pot + call + _IMPLIED_ODDS_MULT * atras
        return max(0.0, eq * ganho_max - call)
    except (TypeError, ValueError):
        return None


# Acima disto a estratégia é PURA: a decisão é automática e acertá-la não mede habilidade.
# 0,90 e não 1,00 porque o solver raramente crava 100% — uma frequência de 0,97 com 3% de blefe
# ainda é "todo mundo folda essa mão".
PURE_STRATEGY_MIN_FREQ = 0.90


def strategy_purity(result: dict) -> tuple:
    """(freq da ação JOGADA, freq da ação MODAL) da decisão — ou (None, None) sem cobertura.

    A segunda é o que importa e é o que não existia: `gto_label` só diz a faixa de frequência do
    que o jogador fez, então um fold `gto_correct` pode ser 100% (decisão automática) ou 65%
    (decisão de verdade). Sem separar as duas, a taxa de erro de RFI dilui — ~84% das decisões são
    folds óbvios, e um "0% de erro" pode conviver com um limp que erra 3 de 3.

    Fonte única: preflop lê o mapa de frequências da MÃO (`hand_freq`, do StrategyProvider) e
    postflop lê o que `_enrich_gto` já calculou. Recalcular em outro lugar criaria a segunda
    definição de "frequência" que este projeto já pagou caro para não ter."""
    gto = result.get('gto') or {}
    if gto.get('available'):
        played = gto.get('played_freq')
        top = gto.get('gto_freq')
        if played is not None or top is not None:
            return (float(played) if played is not None else None,
                    float(top) if top is not None else None)

    pf = result.get('preflop_gto') or {}
    hf = pf.get('hand_freq') if pf.get('available') else None
    if isinstance(hf, dict) and hf:
        try:
            from leaklab.strategy_provider import normalize_action, normalize_freq_map
            mapa = normalize_freq_map(hf)
            agida = normalize_action(result.get('actionTaken') or result.get('action_taken') or '')
            return (float(mapa.get(agida, 0.0)), float(max(mapa.values())))
        except Exception:
            return (None, None)
    return (None, None)


def ev_loss_trustworthy(ev_loss_bb, stack_bb, ev_loss_source, *,
                        action=None, equity=None, pot_bb=None, facing_bb=None) -> bool:
    """O EV em bb pode ser usado como quantidade (ranking, soma, severidade)?

    O veredito e a ação do nó continuam valendo quando isto devolve False — o que se descarta é o
    NÚMERO, não a recomendação. Fonte única desta regra: quem for somar, ranquear ou pesar EV
    precisa passar por aqui, senão volta a existir duas noções de 'EV confiável' no código.

    Três razões para desconfiar, todas medidas em produção:
      · fonte não declarada / não confiável;
      · profundidade acima do teto de calibração (ver `_EV_TRUST_MAX_BB`);
      · o número contradiz a própria aritmética do engine num FOLD (ver `ev_loss_fold_ceiling`).

    O teto de fold só se aplica a fold porque ali a conta é fechada: você abre mão do pote e não
    investe nada. Para call/raise o EV depende do resto da árvore e não há aritmética simples com
    a qual comparar — desconfiar dessas por heurística seria trocar um erro por outro."""
    if ev_loss_bb is None:
        return False
    if (ev_loss_source or '') not in _EV_RELIABLE_SOURCES:
        return False
    try:
        ev = float(ev_loss_bb)
        if stack_bb is not None and float(stack_bb) > _EV_TRUST_MAX_BB:
            return False
    except (TypeError, ValueError):
        return False
    if (action or '').strip().lower() in _FOLD_ACTIONS:
        teto = ev_loss_fold_ceiling(equity, pot_bb, facing_bb, stack_bb)
        if teto is not None and ev > teto:
            return False
    return True


def _ev_severity_ceiling(label: str, ev_loss_bb: float | None, ev_loss_source: str | None = None) -> str:
    if ev_loss_bb is None:
        return label
    cur = _LABEL_SEV.get(label, 1)
    if ev_loss_bb < _EV_CEIL_MARGINAL_BB:
        cur = min(cur, _LABEL_SEV['marginal'])          # custo ínfimo → teto 'marginal'
    elif ev_loss_bb < _EV_CEIL_SMALL_BB:
        cur = min(cur, _LABEL_SEV['small_mistake'])     # custo real pequeno → teto 'small_mistake'
    # RC-B: PISO por EV alto (simétrico ao teto, que só rebaixava). Foldar mão que o GTO paga com
    # -EV grande é erro real mesmo com gto_mixed/gto_correct. Só com fonte de EV confiável
    # (hand-aware), nunca em nó agregado/aproximado (evita falso positivo).
    if (ev_loss_source or '') in _EV_RELIABLE_SOURCES and ev_loss_bb >= _EV_CEIL_SMALL_BB:
        cur = max(cur, _LABEL_SEV['small_mistake'])
    return _SEV_LABEL[cur]


def _enrich_gto(input_data: Dict[str, Any]) -> dict:
    """
    Lookup GTO postflop usando o mesmo hash que lookup_gto() — mesmos nós do banco.
    Tenta 3 variantes (exact → sem hand → sem facing) para maximizar cobertura.
    Usa strategy_json completo quando disponível para classificação precisa por frequência.
    """
    street = input_data.get('street', '')
    if street not in ('flop', 'turn', 'river'):
        return {'available': False}

    spot          = input_data.get('spot', {})
    board         = spot.get('board', [])
    position      = spot.get('position', '')
    hero_hand     = input_data.get('hero_cards', [])
    stack_bb      = float(spot.get('effectiveStackBb') or 20.0)
    # facingToBb (BB) — NÃO facingSize (fichas): o hash do nó usa o facing em BB. Usar fichas
    # dava bet_bucket errado → nenhum spot com aposta casava o nó (gto_label perdido).
    facing_bb     = float(spot.get('facingToBb') or 0.0)
    player_action = input_data.get('player_action', '')
    equity        = input_data.get('math', {}).get('estimatedHandEquity')

    if not board or not position:
        return {'available': False}

    try:
        import json as _json
        from leaklab.gto_utils import compute_spot_hash
        from leaklab.gto_solver import _effective_pot_type
        from database.repositories import get_gto_node

        # Fase 2: pot_type efetivo — prefere o nó de pote 3-bet (ranges corretas) e cai no
        # nó SRP (aproximação/legado) se o 3-bet ainda não foi solvado. '' = hash legado.
        _eff_pot = _effective_pot_type(spot.get('potType', ''), spot.get('preflopOpener', ''),
                                       spot.get('preflop3bettor', ''), stack_bb)

        def _variants(pt):
            hs = [compute_spot_hash(street, position, board, hero_hand, stack_bb, facing_bb, pt),
                  compute_spot_hash(street, position, board, [],        stack_bb, facing_bb, pt)]
            if facing_bb == 0.0:
                hs.append(compute_spot_hash(street, position, board, [], stack_bb, 0.0, pt))
            return hs

        # Mesmas variantes de hash que lookup_gto() usa (3-bet primeiro, SRP como fallback)
        hashes = (_variants('3bet') if _eff_pot == '3bet' else []) + _variants('')

        # Nós do solver Texas (source='solver_cli') REATIVADOS no postflop, COM TRAVA de
        # depth: o solve agora roda no stack REAL (cap 60bb), não mais capado a 20bb. Só
        # confia em solver_cli quando o spot é ≤60bb (acima seria aproximação do cap → cai
        # no GW/heurístico). O guard de SPR abaixo ainda rejeita jams indevidos de qualquer
        # fonte. GTO Wizard segue preferido quando existir (precisão maior).
        # Opção B: o solve do Texas roda capado em 60bb (limite de RAM). Antes só servíamos
        # ≤60bb; agora servimos como APROXIMAÇÃO até _APPROX_MAX_BB, marcando depth_capped
        # (o frontend mostra selo "aproximação"). O guard de SPR/allin abaixo ainda rejeita
        # shove fundo — então só servimos a aproximação onde ela é razoável (check/bet/call/etc).
        _SOLVE_CAP_BB  = 60.0
        _APPROX_MAX_BB = 200.0
        def _ok(n):
            if not n:
                return False
            if n.get('source') == 'solver_cli':
                return stack_bb <= _APPROX_MAX_BB
            return True

        # Prioridade 1: nó GW com strategy_json (dados completos)
        node = None
        for h in hashes:
            n = get_gto_node(h)
            if _ok(n) and n.get('strategy_json'):
                node = n
                break

        # Prioridade 2: nó GW parcial (só top action)
        if not node:
            for h in hashes:
                n = get_gto_node(h)
                if _ok(n):
                    node = n
                    break

        # APROXIMAÇÃO DEEP: postflop FUNDO (>35bb) sem nó no stack real → nó capado a 30bb (mesmo
        # hash que scripts/enqueue_deep_approx.py: pot_type default). Coerente com o fallback do
        # lookup_gto (replay); faz a cobertura (gto_label) subir nos spots deep no reanalyze.
        if not node and street != 'preflop' and float(stack_bb) > 35.0:
            for _hh in (hero_hand, []):
                _na = get_gto_node(compute_spot_hash(street, position, board, _hh, 30.0, facing_bb))
                if _na and _na.get('strategy_json'):
                    node = _na
                    break
            if not node and facing_bb == 0.0:
                _na = get_gto_node(compute_spot_hash(street, position, board, [], 30.0, 0.0))
                if _na and _na.get('strategy_json'):
                    node = _na

        if not node:
            return {'available': False}

        top_action = node['gto_action']
        top_freq   = float(node.get('gto_freq') or 0.0)

        # Desserializar strategy_json completo
        strategy = []
        if node.get('strategy_json'):
            try:
                raw = _json.loads(node['strategy_json'])
                for k, v in raw.items():
                    if isinstance(v, dict):
                        freq  = float(v.get('frequency', 0.0))
                        ev_bb = v.get('ev_bb')
                        ev_bb = float(ev_bb) if ev_bb is not None else None
                    else:
                        freq, ev_bb = float(v), None
                    strategy.append({'action': k, 'frequency': freq, 'ev_bb': ev_bb})
                strategy.sort(key=lambda s: s['frequency'], reverse=True)
                if strategy:
                    top_action = strategy[0]['action']
                    top_freq   = strategy[0]['frequency']
            except Exception as exc:
                _log_gto_miss('postflop', street, position, f'strategy_json parse error: {exc!s:.80}')
                strategy = []

        # Guard: strategy com freq_sum ≈ 0 indica nó corrompido
        if strategy:
            freq_sum = sum(s['frequency'] for s in strategy)
            if freq_sum < 0.10:
                _log_gto_miss('postflop', street, position, f'strategy freq_sum={freq_sum:.3f} (corrompido)')
                strategy = []
                node = None

        # Guard: jam/allin de nó postflop é INVÁLIDO quando o SPR é alto (stack >> pote).
        # O solver postflop roda capped a stack curto (~20bb), onde jogar all-in no flop
        # pode ser top; servido pra um spot FUNDO (ex.: 150bb, SPR ~9) vira "shove de
        # 150bb", que nunca é GTO. Rejeita e cai no heurístico em vez de recomendar shove.
        if _norm_gto_action(top_action) == 'allin':
            pot_bb = float(spot.get('potBb') or 0.0)
            spr = (stack_bb / pot_bb) if pot_bb > 0 else 0.0
            if spr > 3.0:
                _log_gto_miss('postflop', street, position,
                              f'jam rejeitado: SPR={spr:.1f} (stack {stack_bb:.0f}bb / pote {pot_bb:.1f}bb)')
                return {'available': False}

        # ── Fase 3 (plano solver): veredito HAND-AWARE ────────────────────────
        # A classificação usava a frequência AGREGADA da range — mas num K72r a
        # range checa 60% enquanto AA aposta 90%. Quando a tabela por mão da
        # árvore existe (gto_tree_strategies, populada pelo binário novo), o
        # veredito usa a frequência/EV DA MÃO DO HERO. Gated por GTO_HAND_AWARE
        # (default ON — sem tabela cai no agregado, comportamento idêntico ao
        # legado; binário antigo nunca popula a tabela → no-op).
        hand_view = None
        ev_loss_bb = None
        if (node.get('tree_hash') and hero_hand
                and os.environ.get('GTO_HAND_AWARE', '1') == '1'):
            try:
                from leaklab.gto_solver import hand_view_for_spot
                hand_view = hand_view_for_spot(node['tree_hash'], board, hero_hand)
            except Exception:
                hand_view = None

        hand_strategy = None
        if hand_view and hand_view.get('actions'):
            hand_strategy = [
                {'action': a, 'frequency': v['frequency'], 'ev_bb': v['ev_bb'],
                 'ev_loss_bb': v['ev_loss_bb']}
                for a, v in hand_view['actions'].items()
            ]
            hand_strategy.sort(key=lambda s: s['frequency'], reverse=True)
            # EV loss da ação JOGADA (bb): melhor EV da mão − EV da ação escolhida.
            # Mesmo matcher por família da classificação (shove casa raise/bet).
            for s in _match_strategy_entries(player_action, hand_strategy):
                if ev_loss_bb is None or s['ev_loss_bb'] < ev_loss_bb:
                    ev_loss_bb = s['ev_loss_bb']

        # Veredito hand-aware TAMBÉM para a ação recomendada: quando a tabela por
        # mão existe, gto_action/gto_freq são da MÃO DO HERO — não do agregado da
        # range. Servir o agregado aqui dizia "GTO: fold" para um shove com a
        # wheel (a RANGE folda 65%, mas A2 especificamente dá call 100%) e gerava
        # pares incoerentes action_taken == gto_action com gto_label=gto_critical.
        if hand_strategy:
            from leaklab.gto_utils import normalize_gto_action
            top_action = normalize_gto_action(hand_strategy[0]['action'])
            top_freq   = hand_strategy[0]['frequency']

        # Guard: ação agressiva FORA da árvore solvada. Algumas árvores não têm
        # branch de raise (só fold/call) — um shove aí não é gradeável: freq 0 não
        # significa "GTO nunca faz", significa "a árvore nunca OFERECEU". Cai no
        # heurístico em vez de carimbar gto_critical (bug do shove com a wheel).
        _grade_strategy = hand_strategy or strategy
        if (_grade_strategy
                and _action_family(player_action) in ('bet', 'raise', 'allin')
                and not _match_strategy_entries(player_action, _grade_strategy)):
            _log_gto_miss('postflop', street, position,
                          f'ação {player_action!r} fora da árvore '
                          f'({[s["action"] for s in _grade_strategy]})')
            return {'available': False, 'ungradeable_action': True}

        # Classificação: mão específica (Fase 3) > frequência da range > top action
        if hand_strategy:
            gto_label, played_freq = _gto_classify_from_strategy(player_action, hand_strategy)
        elif strategy:
            gto_label, played_freq = _gto_classify_from_strategy(player_action, strategy)
            # ROOT FIX off-tree: postflop SEM hand_strategy = mão fora da cobertura hand-aware.
            # A classificação é da RANGE AGREGADA, não da mão. SÓ rebaixa quando a estratégia é
            # MISTA (top < 90%): aí o modal da range pode não valer p/ a mão específica (ex.: trinca
            # como 'fold' porque a range folda muito) → não acusa desvio/crítico. Numa ação ~pura
            # (top >= 90%, ex.: Call 100%) toda mão faz o mesmo, então um desvio É erro real e o
            # label crítico/desvio se mantém (não é off-tree).
            _top = max((float(s.get('frequency') or 0) for s in strategy), default=0.0)
            if _top < 0.90 and gto_label in ('gto_minor_deviation', 'gto_critical'):
                gto_label = 'gto_mixed'
        else:
            gto_label  = _gto_classify(player_action, top_action, top_freq, equity)
            played_freq = top_freq if _gto_action_matches(player_action, top_action) else (1.0 - top_freq)

        # Aproximação por profundidade: nó solver_cli (capado a 60bb) servido a um spot > 60bb.
        depth_capped = (node.get('source') == 'solver_cli') and stack_bb > _SOLVE_CAP_BB
        return {
            'available':    True,
            'gto_action':   top_action,
            'gto_freq':     top_freq,
            'played_freq':  played_freq,
            'strategy':     strategy,
            'exploitability': node.get('exploitability_pct'),
            'gto_label':    gto_label,
            'source':       node.get('source', 'postflop_db'),
            'depth_capped': depth_capped,
            'hand_aware':   bool(hand_strategy),
            'hand_strategy': hand_strategy,
            'ev_loss_bb':   ev_loss_bb,
            # proveniência do EV (#24 estendido ao postflop): 'solver_hand' = EV da
            # MÃO específica no nó CFR (gto_tree_strategies) — save_decisions persiste
            # na coluna decisions.ev_loss_source junto do ev_loss_bb.
            'ev_loss_source': ('solver_hand' if ev_loss_bb is not None else None),
        }

    except Exception as exc:
        _log_gto_miss('postflop', input_data.get('street', ''),
                      (input_data.get('spot') or {}).get('position', ''), str(exc)[:120])
        return {'available': False}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round4(value: float) -> float:
    return round(value, 4)


decision_engine_config = {
    "labels": {"standardMax": 0.08, "marginalMax": 0.18, "smallMistakeMax": 0.36},
    "streetCaps": {"preflop": 0.04, "flop": 0.05, "turn": 0.06, "river": 0.06},
    "streetMultipliers": {"preflop": 0.95, "flop": 1.0, "turn": 1.08, "river": 1.12},
}


def calc_realization_adjustment(is_in_position: bool | None, reverse_implied_odds_factor: float | None, effective_stack_bb: float | None, range_zone: str, hand_class: str | None) -> float:
    adj = 0.0
    if is_in_position is False:
        adj += 0.01
    if (reverse_implied_odds_factor or 0) > 0.5:
        adj += 0.01
    if (effective_stack_bb or 0) > 40 and range_zone == "outside_range":
        adj += 0.01
    if hand_class and "dominated" in hand_class:
        adj += 0.01
    return clamp(adj, 0.0, 0.04)


def calc_pressure_adjustment(street: str, pressure_score: float | None, is_multiway: bool | None,
                              icm_pressure: str | None, is_pko: bool = False,
                              icm_tax_pct: float | None = None) -> float:
    adj = 0.0
    p = pressure_score or 0.0
    if 0.35 <= p < 0.65:
        adj += 0.01
    if p >= 0.65:
        adj += 0.02
    if is_multiway:
        adj += 0.01
    # ICM: na mesa final usamos o sinal CONTÍNUO (icm_tax do calculate_icm, ver
    # leaklab/icm.py) — |tax| = intensidade da distorção ICM. Quanto mais a equity
    # ICM se afasta da fração de fichas (big stack pagando risk premium OU short
    # stack com prêmio de sobrevivência), mais equity é exigida para arriscar a
    # pilha (calls finos viram erro maior, folds apertados são perdoados). Fora da
    # mesa final (icm_tax indisponível) caímos no bucket heurístico icm_pressure.
    if icm_tax_pct is not None:
        adj += clamp(abs(icm_tax_pct) / 100.0 * 0.06, 0.0, 0.02)
    elif icm_pressure == "high" and street in {"turn", "river"}:
        adj += 0.01
    # PKO: bounty reduz a equity necessária para stack-off — covering player
    # tem incentivo extra (matar villain = ganha bounty). Artigo GW indica
    # 5.9% adicional vs 14.2% classic. Aplicamos -0.02 (2pp) na adjusted
    # required equity. Apenas pré-final-table — perto da bolha o efeito atenua.
    if is_pko and icm_pressure != 'high':
        adj -= 0.02
    return clamp(adj, -0.03, 0.03)


def calc_adjusted_required_equity(street: str, pot_odds_equity: float | None, realization_adjustment: float, pressure_adjustment: float):
    if pot_odds_equity is None:
        return {"adjustedRequiredEquity": None, "streetCapApplied": decision_engine_config["streetCaps"][street], "totalAdjustment": 0.0}
    cap = decision_engine_config["streetCaps"][street]
    # PKO pode gerar pressure_adjustment negativo (bounty reduz equity necessária).
    # Permite total negativo (cap inferior: -cap).
    total = clamp(realization_adjustment + pressure_adjustment, -cap, cap)
    adjusted = max(0.05, round4(pot_odds_equity + total))  # piso 5% pra evitar absurdos
    return {"adjustedRequiredEquity": adjusted, "streetCapApplied": cap, "totalAdjustment": round4(total)}


def calc_base_action_gap(player_action: str, recommended_primary_action: str, alternative_actions: list[str] | None = None) -> float:
    alternatives = alternative_actions or []
    if player_action == recommended_primary_action:
        return 0.0
    if player_action in alternatives:
        return 0.08
    aggressive_mismatch = player_action in {"shove", "jam", "raise"} and recommended_primary_action == "fold"
    if aggressive_mismatch:
        return 0.35
    if player_action == "fold" and recommended_primary_action == "call":
        return 0.14
    if player_action == "call" and recommended_primary_action == "fold":
        return 0.22
    return 0.18


def calc_math_penalty(player_action: str, estimated_hand_equity: float | None, adjusted_required_equity: float | None) -> float:
    if estimated_hand_equity is None or adjusted_required_equity is None:
        return 0.0
    diff = round4(estimated_hand_equity - adjusted_required_equity)
    if player_action == "call":
        if diff >= 0: return 0.0
        if diff > -0.02: return 0.05
        if diff > -0.04: return 0.11
        if diff > -0.07: return 0.18
        return 0.28
    if player_action == "fold":
        if diff <= 0: return 0.0
        if diff < 0.02: return 0.04
        if diff < 0.04: return 0.09
        if diff < 0.07: return 0.15
        return 0.22
    return 0.0


def calc_range_penalty(range_zone: str, player_action: str, recommended_primary_action: str) -> float:
    if player_action == recommended_primary_action:
        return 0.0
    if range_zone == "borderline_range":
        return 0.03
    if range_zone == "core_range":
        return 0.08
    if range_zone == "outside_range":
        return 0.12
    return 0.0


def calc_context_penalty(street: str, is_multiway: bool | None, is_in_position: bool | None, icm_pressure: str | None, player_action: str, recommended_primary_action: str) -> float:
    penalty = 0.0
    if player_action != recommended_primary_action:
        if street == "turn": penalty += 0.02
        if street == "river": penalty += 0.04
    if is_multiway: penalty += 0.01
    if is_in_position is False and street != "preflop": penalty += 0.01
    if icm_pressure == "high": penalty += 0.01
    return penalty


def calc_tolerance_credit(range_zone: str, player_action: str, recommended_primary_action: str, alternative_actions: list[str] | None, estimated_hand_equity: float | None, adjusted_required_equity: float | None) -> float:
    credit = 0.0
    alternatives = alternative_actions or []
    if range_zone == "borderline_range":
        credit += 0.05
    if player_action in alternatives:
        credit += 0.04
    if estimated_hand_equity is not None and adjusted_required_equity is not None:
        diff = abs(estimated_hand_equity - adjusted_required_equity)
        if diff <= 0.02:
            credit += 0.03
        elif diff <= 0.03:
            credit += 0.015
    return credit


def classify_mistake_score(score: float) -> str:
    if score <= 0.08: return "standard"
    if score <= 0.18: return "marginal"
    if score <= 0.36: return "small_mistake"
    return "clear_mistake"


def apply_anti_rules(player_action: str, estimated_hand_equity: float | None, adjusted_required_equity: float | None, provisional_label: str, best_action: str | None = None) -> str:
    # Se o jogador fez exatamente a ação recomendada, não há anti-rule a aplicar
    if best_action is not None and _norm_gto_action(player_action) == _norm_gto_action(best_action):
        return provisional_label
    if estimated_hand_equity is None or adjusted_required_equity is None:
        return provisional_label
    diff = round4(estimated_hand_equity - adjusted_required_equity)
    if player_action == "fold":
        if 0 <= diff <= 0.03 and provisional_label == "clear_mistake":
            return "small_mistake"
        # Fold com equity >= required + 3pp é leak math claro. Sem essa regra,
        # label pode ficar 'standard' contradizendo o indicador "Call lucrativo".
        if diff >= 0.03 and provisional_label == "standard":
            return "small_mistake"
    if player_action == "call":
        if diff <= -0.07:
            return "clear_mistake"
        if diff <= -0.04 and provisional_label == "marginal":
            return "small_mistake"
    return provisional_label


def evaluate_decision(input_data: Dict[str, Any]) -> Dict[str, Any]:
    street = input_data["street"]
    spot = input_data["spot"]
    hand_profile = input_data["hand_profile"]
    math = input_data["math"]
    range_eval = input_data["range_evaluation"]
    context = input_data.get("context", {})

    # BB check em pot não contestado: ação obrigatória/trivial, sem análise de erro
    if (street == 'preflop'
            and spot.get('position') == 'BB'
            and input_data.get('player_action', '').lower() == 'check'
            and float(spot.get('facingSize') or 0) == 0):
        return {
            "handId": input_data["hand_id"],
            "bestAction": "check",
            "actionTaken": "check",
            "evaluation": {"mistakeScore": 0.0, "label": "standard", "scoreBreakdown": {}},
            "thresholds": {},
            "interpretation": {"summary": "BB exerceu o free play — sem análise de range.", "details": []},
            "gto": {"available": False},
            "preflop_gto": None,
            "debug": {"rangeZone": None, "alternativeActions": [], "rawFlags": []},
        }

    # Shove sobre all-in cujo excesso NINGUEM pode pagar: as fichas a mais voltam, entao a
    # jogada É o call — mesmo pote, mesmo custo, mesmo resultado. Gradear "shove" contra "call"
    # aqui e cobrar uma distincao que nao existe: medido no acervo, 24 decisoes, 3 delas acusadas
    # de `small_mistake` RECOMENDANDO exatamente a jogada equivalente a que o jogador fez.
    #
    # Grada-se como CALL (o custo real e o do call), e a acao exibida segue sendo a de verdade —
    # o jogador deu shove e a tela tem que dizer isso. O `_acao_real` restaura no fim.
    #
    # Nao vale para `best_action='fold'`: ali a critica e legitima e continua de pe (o leak e
    # entrar na mao, nao o tamanho). Isso sai de graca — so mexemos quando o melhor E o call.
    _acao_real = input_data.get('player_action', '')
    _shove_e_call = (bool(spot.get('shoveEquivaleCall'))
                     and (_acao_real or '').lower() in ('shove', 'jam', 'allin', 'all-in', 'raise'))
    if _shove_e_call:
        input_data = {**input_data, 'player_action': 'call'}

    realization_adjustment = calc_realization_adjustment(
        spot.get("isInPosition"),
        math.get("reverseImpliedOddsFactor"),
        spot.get("effectiveStackBb"),
        range_eval.get("rangeZone"),
        hand_profile.get("handClass"),
    )
    pressure_adjustment = calc_pressure_adjustment(
        street,
        math.get("pressureScore"),
        spot.get("isMultiway"),
        context.get("icmPressure"),
        is_pko=bool(context.get("isPko")),
        icm_tax_pct=context.get("icmTaxPct"),
    )
    threshold_pack = calc_adjusted_required_equity(
        street,
        math.get("potOddsEquity"),
        realization_adjustment,
        pressure_adjustment,
    )
    base_action_gap = calc_base_action_gap(
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
        range_eval.get("alternativeActions") or [],
    )
    # Math penalty só se aplica quando a ação diverge da recomendada
    # Se o jogador fez exatamente o bestAction, não há penalidade matemática
    _best_action = range_eval.get("recommendedPrimaryAction")
    math_penalty = calc_math_penalty(
        input_data["player_action"],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
    ) if _norm_gto_action(input_data["player_action"]) != _norm_gto_action(_best_action or '') else 0.0
    range_penalty = calc_range_penalty(
        range_eval.get("rangeZone"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
    )
    context_penalty = calc_context_penalty(
        street,
        spot.get("isMultiway"),
        spot.get("isInPosition"),
        context.get("icmPressure"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
    )
    tolerance_credit = calc_tolerance_credit(
        range_eval.get("rangeZone"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
        range_eval.get("alternativeActions") or [],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
    )
    raw_score = clamp(base_action_gap + math_penalty + range_penalty + context_penalty - tolerance_credit, 0.0, 1.0)
    street_multiplier = decision_engine_config["streetMultipliers"][street]
    final_score = clamp(raw_score * street_multiplier, 0.0, 1.0)
    label = classify_mistake_score(final_score)
    label = apply_anti_rules(
        input_data["player_action"],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
        label,
        best_action=_best_action,
    )

    # GTO enrichment postflop — fonte primária quando strategy_json disponível
    gto = _enrich_gto(input_data)
    if gto.get('available'):
        if gto.get('strategy'):
            # Strategy completo: recomputar score e label a partir da frequência real
            played_freq  = gto.get('played_freq', 0.0)
            top_freq     = gto.get('gto_freq', 1.0)
            gto_lbl      = gto['gto_label']
            opp_cost     = max(0.0, top_freq - played_freq)
            _score_mult  = {
                'gto_correct':         0.10,
                'gto_mixed':           0.30,
                'gto_minor_deviation': 0.65,
                'gto_critical':        0.90,
            }
            final_score  = clamp(round4(opp_cost * _score_mult.get(gto_lbl, 0.5)), 0.0, 1.0)
            label        = classify_mistake_score(final_score)
            # Aplica cap mesmo no caminho com strategy completo. Score recalculado
            # pode ficar acima de 0.36 (clear_mistake) quando opp_cost e alto,
            # contradizendo o proprio rotulo do solver (gto_minor_deviation/mixed).
            label        = _gto_label_cap(label, gto_lbl)
            _best_action = gto['gto_action']
        else:
            # Nó parcial (sem strategy_json): capeia label e override bestAction
            # quando GTO crítico — não faz sentido recomendar call quando solver diz jam.
            label = _gto_label_cap(label, gto['gto_label'])
            if gto.get('gto_label') == 'gto_critical' and gto.get('gto_action'):
                _best_action = gto['gto_action']

    # Validar inputs antes do GTO enrichment (warnings apenas — não bloqueia)
    _input_warnings = _validate_decision_input(input_data)
    if _input_warnings:
        for _w in _input_warnings:
            _log_gto_miss('input_validation', street, input_data.get('spot', {}).get('position', ''), _w)

    # GTO enrichment preflop: range GTO por posição/stack — ajusta label e best_action
    preflop_gto = _enrich_preflop_gto(input_data)
    if preflop_gto.get('available'):
        quality   = preflop_gto.get('action_quality', 'unknown')
        _pf_evloss = preflop_gto.get('ev_loss_bb')
        # Tema 1: a severidade do label preflop agora considera o EV perdido medido.
        label   = _preflop_gto_label_adjust(label, quality, _pf_evloss)
        rec     = preflop_gto.get('recommended_actions', [])
        if rec:
            _best_action = rec[0]   # sobrescreve com ação GTO recomendada
        # Tema 1: 'leak'/'major_leak' de baixo custo (EV < limiar) é desvio LEVE — o
        # gto_label crítico é rebaixado e o score capeado em 'marginal'. Sem isto, um
        # 3-bet light de 0.006bb saía como gto_critical/clear_mistake (igual a um erro
        # de vários bb). 22 a 0.281bb fica acima do limiar e segue small_mistake.
        # RC-A: só 'leak' (freq>0, dentro de um mix) é low-cost defensável. 'major_leak' (freq~0,
        # fora do range) é erro de DIREÇÃO — nunca rebaixado por EV (mantém gto_critical, piso de label).
        _low_cost_leak = (quality == 'leak' and _pf_evloss is not None
                          and _pf_evloss < _PREFLOP_EV_MINOR_BB)
        # Consistência score/label: recalcular final_score para bater com novo label
        if quality == 'correct':
            final_score = min(final_score, 0.08)    # cap em 'standard'
        elif quality in ('acceptable', 'gto_minor_deviation', 'minor_mistake') or _low_cost_leak:
            final_score = min(final_score, 0.18)    # cap em 'marginal'
        # Persistir gto_label/gto_action preflop no DB (save_decisions lê result['gto'])
        if quality and quality != 'unknown':
            _QUALITY_TO_GTO_LABEL = {
                'correct':             'gto_correct',
                'acceptable':          'gto_mixed',
                'gto_minor_deviation': 'gto_minor_deviation',
                'minor_mistake':       'gto_minor_deviation',
                'leak':                'gto_critical',
                'major_leak':          'gto_critical',
            }
            _gto_lbl = _QUALITY_TO_GTO_LABEL.get(quality, 'gto_critical')
            # Tema 1: rebaixa o gto_label crítico quando o custo de EV é minúsculo.
            if _low_cost_leak and _gto_lbl == 'gto_critical':
                _gto_lbl = 'gto_minor_deviation'
            gto = {'available': True, 'gto_label': _gto_lbl, 'gto_action': rec[0] if rec else None,
                   # #24: bb perdidos vs melhor ação (vem do overlay de EV no analyze_preflop)
                   'ev_loss_bb':     _pf_evloss,
                   'ev_loss_source': preflop_gto.get('ev_loss_source')}

    # Guard: BB pode check grátis quando não há aposta — fold é impossível.
    # Outras posições (UTG/HJ/CO/BTN/SB) estão escolhendo não abrir — fold é correto.
    if float(spot.get('facingSize') or 0) == 0 and _best_action == 'fold' and spot.get('position') == 'BB':
        _best_action = 'check'

    # Guard: em POSTFLOP sem aposta anterior, "raise" não é ação válida — normalizar para "bet".
    # Preflop sempre tem BB facing, então "raise" continua válido em RFI preflop.
    if (input_data.get('street') != 'preflop'
        and float(spot.get('facingSize') or 0) == 0 and _best_action == 'raise'):
        _best_action = 'bet'

    # Guard: facing all-in que cobre o hero — raise é impossível. Cai pra call/fold
    # baseado em equity vs required. Cobre o bug onde engine sugeria 'raise' em
    # spots multi-all-in ou facing shove cobrindo o stack do hero.
    # IMPORTANTE: spot.facingSize está em FICHAS; effectiveStackBb em BB. Converter
    # o facing para bb via levelBb antes de comparar (sem isso o guard disparava
    # espúrio — ex.: facing 250 fichas tratado como 250bb — e rebaixava jam do GTO).
    # PREFERE `facingToBb`, que o pipeline ja calcula em BB. Recalcular a partir de fichas exige
    # `levelBb`, e quando ele falta o facing vira 0 e este guarda PULA EM SILENCIO — foi o que
    # aconteceu com a mao 2790343346: hero com 10,6bb enfrentando 37,5bb teve o call marcado como
    # erro com recomendacao de shove, sendo que o call DELE ja era o all-in. Mesma familia do bug
    # do no de replay, que usava facing_bet(=0) em vez de facingToBb.
    _facing_to_bb = spot.get('facingToBb')
    if _facing_to_bb is not None:
        _facing_bb = float(_facing_to_bb or 0)
    else:
        _facing_chips = float(spot.get('facingSize') or 0)
        _bb_chips = float(input_data.get('context', {}).get('levelBb') or 0)
        _facing_bb = (_facing_chips / _bb_chips) if _bb_chips > 0 else 0.0
    _hero_stack_bb = float(spot.get('effectiveStackBb') or input_data.get('context', {}).get('heroStackBb') or 0)
    # Dispara em DOIS casos, e o segundo foi o da mao reportada:
    #   · o melhor lance era raise/jam e ele e impossivel (o facing cobre o stack), ou
    #   · nao ha cobertura GTO nenhuma. Ai o unico "melhor lance" disponivel vem da heuristica, que
    #     no preflop nao computa equity-vs-range: ela recomendou FOLD com AK e 8,6bb contra 37,5bb.
    #     Sem base, o produto nao acusa — a mesma regra que vale no resto dele.
    _sem_gabarito = not preflop_gto.get('available')
    if ((_best_action in ('raise', 'jam') or _sem_gabarito)
            and _facing_bb > 0 and _hero_stack_bb > 0
            and _facing_bb >= _hero_stack_bb * 0.95):
        _eq  = math.get('estimatedHandEquity')
        _req = threshold_pack.get('adjustedRequiredEquity')
        _gto_rec = preflop_gto.get('recommended_actions', []) if preflop_gto.get('available') else []
        if 'jam' in _gto_rec or 'call' in _gto_rec:
            # O range GTO queria comprometer o stack (jam/call). Facing all-in que
            # cobre o hero, 'jam' é impossível mas colapsa em 'call' — mesma decisão
            # de commit. Sem isso o guard caía em fold por equity=None (preflop não
            # computa equity-vs-range), rebaixando calls triviais (AK/AJ vs shove).
            _best_action = 'call'
        elif _eq is not None and _req is not None:
            _best_action = 'call' if _eq >= _req else 'fold'
        else:
            # SEM GTO e SEM equity nao ha base para acusar. O ramo antigo caia em 'fold' aqui, e
            # com isso um call que JA E all-in virava erro por AUSENCIA DE DADO — o oposto da
            # regra que vale no resto do produto (sem gabarito nao e erro; a decisao sai da conta
            # em vez de virar acusacao).
            #
            # Reportado numa mao real: hero com 10,6bb enfrentando 37,5bb deu call e recebeu
            # `small_mistake` com recomendacao de shove, sendo que o call dele ERA o shove.
            _best_action = _norm_gto_action(input_data.get('player_action')) or 'call'
        # Reclassifica: score foi computado contra 'raise' invalido. Se player
        # matched o novo best_action, e standard. Caso contrario, mantem severidade.
        if _norm_gto_action(input_data["player_action"]) == _norm_gto_action(_best_action):
            label = 'standard'
            final_score = 0.0

    # Guard: mão MONSTRO (quads/boat/flush/straight/set) jogada agressivamente SEM
    # veredito do solver. O estimador heurístico de equity não enxerga mão feita
    # (a wheel A2 em 4-3-J-5 era avaliada como "OESD, 29%") e punia o shove por
    # valor como small/clear mistake. Bet/raise por valor com monstro é, no pior
    # caso, questão de sizing — cap em 'marginal'. Quando há veredito GTO, ele manda.
    if (street != 'preflop' and not gto.get('available')
            and _action_family(input_data["player_action"]) in ('bet', 'raise', 'allin')
            and label in ('small_mistake', 'clear_mistake')):
        from leaklab.bet_intent import is_monster_hand
        if is_monster_hand(input_data.get('hero_cards'), spot.get('board')):
            label = 'marginal'
            final_score = min(final_score, 0.18)

    # Tema 2 (recalibração coach #27) — REDE DE SEGURANÇA estreita: cap em
    # 'small_mistake' SÓ onde o estimador de equity heurístico é o input não-confiável
    # que carrega o veredito. NÃO é cap cego de "sem GTO" — uma violação de pot odds
    # limpa (call 41% com required subindo por ICM) é clear_mistake legítimo mesmo
    # sem solver, e math-clear não passa pelo estimador. Dois gatilhos documentados:
    #   (a) POSTFLOP com mão FEITA (par+): o estimador subvaloriza mão feita (wheel,
    #       full house, par de J em K-6-J marcado clear_mistake). is_monster_hand já
    #       cobre o monstro jogado agressivo acima; aqui pegamos call/fold com par+.
    #   (b) PREFLOP em pote de SQUEEZE/cold multi-raise (raisesFaced>=2) sem cobertura:
    #       a equity vs-random engana (ATs mostra 64% vs aleatória, folda vs squeeze) e
    #       o range evaluator recomendava raise → fold virava clear_mistake.
    # Sem solver pra confirmar, nesses dois casos o custo de um falso-grave supera o
    # de um falso-leve. NÃO é o fix real (a direção de best_action segue errada) — é o
    # teto que impede o veredito mais caro. Ver tarefa do estimador de equity.
    if label == 'clear_mistake' and not gto.get('available') and not preflop_gto.get('available'):
        _suspect_equity = False
        if street != 'preflop':
            from leaklab.bet_intent import made_hand_category
            _suspect_equity = made_hand_category(
                input_data.get('hero_cards'), spot.get('board')) in ('value', 'middle')
        elif int(spot.get('preflopRaisesFaced') or 0) >= 2:
            _suspect_equity = True
        if _suspect_equity:
            label = 'small_mistake'
            final_score = min(final_score, 0.35)

    # Teto de severidade por EV (final): rebaixa veredito grave de baixo custo (gto_critical
    # que custa ~0 = spot misto, não erro grave). gto_label fica intacto.
    _eff_ev = gto.get('ev_loss_bb') if gto.get('available') else None
    _label_pre_ceil = label
    # A FONTE só é passada adiante quando o EV serve como quantidade. É ela que liga o PISO de
    # severidade em `_ev_severity_ceiling` — e acima do teto de calibração o número é fantasia
    # (ver `_EV_TRUST_MAX_BB`), então um fold defensável virava erro. O teto para baixo continua
    # valendo: rebaixar veredito grave de custo ínfimo é seguro em qualquer profundidade.
    _ev_src = gto.get('ev_loss_source') if gto.get('available') else None
    _ev_ok = ev_loss_trustworthy(
        _eff_ev, _hero_stack_bb, _ev_src,
        action=input_data.get('player_action'),
        equity=math.get('estimatedHandEquity'),
        pot_bb=spot.get('potBb'),
        facing_bb=_facing_bb,
    )
    label = _ev_severity_ceiling(label, _eff_ev, _ev_src if _ev_ok else None)
    if label != _label_pre_ceil:
        final_score = min(final_score, _LABEL_MAX_SCORE[label])

    # INVARIANTE (piso TERMINAL): erro de DIREÇÃO — o GTO folda a mão (fora do range de continuação)
    # mas o hero AGREDIU — NUNCA é capeado por EV. O _ev_severity_ceiling acima rebaixava de volta a
    # 'marginal' quando o EV era ~0 (open fora do range custa pouco justamente por isso). Espelha o
    # is_verdict_error_signal do reconcile/display → consistência card↔lista↔engine.
    _played_act = _norm_gto_action(input_data.get('player_action', ''))
    if (_best_action == 'fold' and _played_act in ('raise', 'bet', 'allin', 'jam', 'shove')
            and _LABEL_SEV.get(label, 1) < _LABEL_SEV['small_mistake']):
        label = 'small_mistake'
        final_score = max(final_score, _LABEL_MAX_SCORE['marginal'] + 0.001)

    # Teto HEURÍSTICO p/ POTE LIMPADO: sem nó GTO E pote limpado (o hero iso-raisa/aposta/
    # shova sobre limps) a heurística recomenda PASSIVO (check/call/fold) e flaga a agressão
    # padrão como erro. Aí cap em 'marginal' — iso-raisar sobre limp não é erro grave; o card
    # já rotula "heurística". NÃO afeta erros heurísticos confiáveis por math (call ruim, fold
    # claro — não-agressivos) nem spots cobertos por GTO.
    # Preflop, hero agride SEM aposta enfrentada (iso sobre limp / SB-complete-raise / open
    # sem cobertura) e a heurística recomenda passivo → cap. (facingLimp não pega SB-complete,
    # que é call < 1bb; facingSize==0 cobre todos.) Postflop multiway fica de fora (lá a
    # heurística 'check multiway' costuma estar certa — ex.: c-bet 8-way).
    _aggr_act = _norm_gto_action(input_data.get('player_action', '')) in ('raise', 'bet', 'allin')
    if (not gto.get('available') and _LABEL_SEV.get(label, 1) > _LABEL_SEV['marginal']
            and street == 'preflop' and float(spot.get('facingSize') or 0) == 0 and _aggr_act
            and _best_action in ('check', 'call', 'fold')):
        label = 'marginal'
        final_score = min(final_score, _LABEL_MAX_SCORE['marginal'])

    # Gate zona-ICM (TERMINAL, só folds): o grading é ChipEV e não modela ICM. Sob ICM
    # real (pressure alto + mesa curta), foldar uma mão que o ChipEV manda CONTINUAR não
    # é "Erro" — é aproximação (tight-is-right). Rebaixa Erro→'marginal' e marca a flag
    # para o card exibir "≈ Aproximação chipEV". NÃO toca agressão (o invariante de direção
    # acima é ortogonal: lá o hero AGRIDE; aqui ele FOLDA). Ver leaklab/verdict.py.
    icm_zone_approx = False
    if label in ('small_mistake', 'clear_mistake') and icm_zone_softens_fold(
            context.get('icmPressure'), context.get('activePlayers'),
            input_data.get('player_action'), _best_action):
        label = 'marginal'
        final_score = min(final_score, _LABEL_MAX_SCORE['marginal'])
        icm_zone_approx = True

    # SEM GABARITO NÃO É ERRO — só para FOLD, e o "só" tem razão de ser.
    #
    # A regra já vale em outros pontos do motor ("sem gabarito não é erro; a decisão sai da
    # conta em vez de virar acusação"), mas não estava aplicada aqui. Medido no acervo: das
    # 196 decisões acusadas de erro, 44 (22,4%) não têm cobertura NENHUMA — nem solver, nem
    # range preflop. Sem gabarito, tudo que sobra é o estimador heurístico de equity.
    #
    # Por que só o fold, e não um cap cego de "sem GTO" (que este arquivo já rejeitou uma vez,
    # ver o Tema 2 acima): o estimador erra numa direção conhecida — ele SUPERVALORIZA quem não
    # tem nada (postflop sem gabarito, 21 das 32 acusações são de mão `air`). Equity inflada só
    # fabrica erro num sentido: acusar quem FOLDOU ("você tinha equity e desistiu"). No sentido
    # oposto ela é conservadora — um call julgado com equity inflada tende a ser ABSOLVIDO, não
    # condenado. É por isso que a "violação de pot odds limpa" que o Tema 2 defende continua
    # podendo condenar: ela condena quem PAGOU.
    #
    # Postflop exige mão `air`: com par+ o estimador está no regime em que ele SUBvaloriza (o
    # Tema 2 cobre esse lado), e ali um fold acusado pode ser acusação boa — foldar mão feita.
    # Sem essa condição, foldar o nuts no river viraria "aceitável".
    #
    # Cap em 'marginal', não 'standard': `marginal` é "subótimo mas defensável" e NÃO conta como
    # erro no veredito de 3 níveis. É exatamente "sair da conta" sem afirmar que estava perfeito.
    if (label in ('small_mistake', 'clear_mistake')
            and not gto.get('available') and not preflop_gto.get('available')
            and _norm_gto_action(input_data.get('player_action', '')) == 'fold'):
        _estimador_infla = True
        if street != 'preflop':
            from leaklab.bet_intent import made_hand_category
            # ATENÇÃO: `made_hand_category(None, None)` devolve 'air'. Sem cartas ou sem board
            # não dá para AFIRMAR que o hero não tem nada, e a regra inteira se apoia nisso —
            # aplicá-la aí seria ler ausência de dado como o caso que me convém. Sem os dois,
            # a decisão mantém o veredito que tinha.
            _cartas = input_data.get('hero_cards')
            _board  = spot.get('board')
            _estimador_infla = bool(_cartas) and bool(_board) and made_hand_category(
                _cartas, _board) not in ('value', 'middle')
        if _estimador_infla:
            label = 'marginal'
            final_score = min(final_score, _LABEL_MAX_SCORE['marginal'])

    # ── Defeito 1: o rotulo mais duro num spot de moeda ao alto ────────────────────────────
    # Achado na revisao cruzada com o coach (05/08). Em tres maos o produto cravou
    # `clear_mistake` num FOLD cuja propria conta dizia outra coisa:
    #
    #   95o em 7-T-6   equity 28,0%  exigido 36,7%   -> o fold estava CERTO
    #   A9o em 4-8-2   equity 34,0%  exigido 33,6%   -> empate (0,4pp)
    #   Q5s em 6-A-2   equity 24,0%  exigido 23,5%   -> empate (0,5pp)
    #
    # Duas regras, e a primeira e a que mais importa: **se a equity estimada NAO alcanca o
    # exigido, o fold e +EV pela nossa propria matematica**. Chamar isso de "erro claro" e o
    # produto se contradizendo dentro do mesmo card. E o argumento vale mesmo com nó de solver:
    # o estimador erra INFLANDO equity (ver o bloco de "sem gabarito nao e erro" acima), entao
    # quando ate a versao inflada diz que nao da preco, nao da preco.
    #
    # Cap em `marginal`, nao em `standard`: pode existir motivo de range para pagar que a conta
    # de pot odds nao ve. Marginal e "subotimo mas defensavel", que e exatamente o que se sabe.
    _EMPATE_PP = 0.02
    if label in ('small_mistake', 'clear_mistake') and _norm_gto_action(
            input_data.get('player_action', '')) == 'fold':
        # POT ODDS CRU, nao o `adjustedRequiredEquity`. A primeira versao deste guarda usou o
        # ajustado e nao disparou em nenhuma das tres maos do relatorio: ele ja vem descontado
        # por realizacao/pressao (0,25 onde o pot odds era 0,336) e por isso quase sempre fica
        # ABAIXO da equity. A pergunta aqui e aritmetica — "o call paga o preco oferecido?" — e
        # quem responde isso e o preco, nao o preco ajustado por modelo.
        _eq_f  = math.get('estimatedHandEquity')
        _req_f = math.get('potOddsEquity') or threshold_pack.get('adjustedRequiredEquity')
        if _eq_f is not None and _req_f is not None:
            if _eq_f < _req_f or abs(_eq_f - _req_f) <= _EMPATE_PP:
                label = 'marginal'
                final_score = min(final_score, _LABEL_MAX_SCORE['marginal'])

    # ── Defeito 5 (familia 3 da revisao de 07/08): o ESPELHO do G1, para o lado do call ────
    #
    # O G1 acima cobre uma direcao so: jogador FOLDOU e o preco nao pagava. O caso que o coach
    # apontou e o inverso — o jogador PAGOU, o preco fechava com folga, e o produto acusou. A nota
    # do proprio card dizia, em 72 decisoes do acervo: "O preco fechava (X% de equity contra Y%
    # exigidos), mas o fold vem da RANGE, nao do preco". Saber e dizer que o preco fecha e ainda
    # assim cravar `small_mistake` e severidade contra a propria evidencia.
    #
    # Tres cuidados, cada um por um erro ja pago:
    #   1. **usa o pot odds do MOTOR** (`potOddsEquity`), nunca `to_call/(pot+to_call)` de colunas
    #      do banco — foi assim que eu acusei o produto errado no relatorio de 06/08;
    #   2. **margem larga** (>= `_MARGEM_PRECO_FOLGADO`), porque a equity estimada erra INFLANDO:
    #      exigir folga grande faz o guarda sobreviver a essa inflacao;
    #   3. **nao dispara contra range estreita** (all-in com 2+ raises). Ali a equity vs mao
    #      aleatoria nao vale como argumento — e exatamente o que o G2 logo abaixo trata.
    #
    # Cap em `marginal`, nunca `standard`: pode haver motivo de RANGE para foldar que o preco nao
    # ve. O que se sabe e que nao ha base para chamar de erro — e `marginal` diz isso.
    _MARGEM_PRECO_FOLGADO = 0.15
    _PRECO_BARATO = 0.35
    if label in ('small_mistake', 'clear_mistake') and _norm_gto_action(
            input_data.get('player_action', '')) == 'call':
        _eq_c = math.get('estimatedHandEquity')
        _req_c = math.get('potOddsEquity')
        _range_estreita = (spot.get('facingAllin')
                           and int(spot.get('preflopRaisesFaced') or 0) >= 2
                           and math.get('equitySource') == 'vs_random')
        if (_eq_c is not None and _req_c is not None and not _range_estreita
                and _req_c < _PRECO_BARATO
                and (_eq_c - _req_c) >= _MARGEM_PRECO_FOLGADO):
            label = 'marginal'
            final_score = min(final_score, _LABEL_MAX_SCORE['marginal'])

    # ── Defeito 2: equity vs mao ALEATORIA nao vale como argumento contra range estreita ───
    # O caso do coach: AQo enfrentando 4-bet ALL-IN por 20bb. O card exibia 64,4% de equity e
    # rotulava o call de `standard`. Mas 64,4% e vs mao ALEATORIA — contra quem 4-beta 20bb, AQo
    # esta bem atras. O produto usou um numero medido contra outra coisa para abencoar a jogada.
    #
    # Sinal de range estreita, sem adivinhacao: enfrentar all-in COM dois ou mais raises antes.
    # Nao e "vilao agressivo" nem leitura — e a linha mais estreita que existe no preflop.
    #
    # A correcao NAO acusa: baixa de `standard` para `marginal`. A diferenca importa. Acusar
    # exigiria saber a range de verdade; o que sabemos e so que **nao temos base para chamar de
    # correto**, e `marginal` diz exatamente isso. Mesma logica de direcao do bloco "sem gabarito
    # nao e erro": equity inflada absolve quem paga, entao a correcao anda no sentido de tirar a
    # absolvicao, nunca no de criar culpa.
    if (street == 'preflop' and label == 'standard'
            # `equitySource` vive no bloco `math` do input, nao no `context` — a primeira
            # versao leu do lugar errado e o guarda nunca disparou, calado.
            and math.get('equitySource') == 'vs_random'
            and spot.get('facingAllin')
            and int(spot.get('preflopRaisesFaced') or 0) >= 2
            and _norm_gto_action(input_data.get('player_action', '')) == 'call'
            and not gto.get('available') and not preflop_gto.get('available')):
        label = 'marginal'
        final_score = max(final_score, _LABEL_MAX_SCORE['standard'] + 0.001)

    # ── Defeito 3: abaixo de ~10bb a arvore e jam-ou-fold ──────────────────────────────────
    # O coach apontou duas: ATo de UTG com 9,2bb recebeu `raise` (com `gto_correct`!) e A5s
    # heads-up com 16,4bb recebeu `call`. Nessa profundidade o open pequeno nao existe na arvore
    # da mesa — quem abre, abre comprometido. Recomendar `raise` ali descreve uma arvore mais
    # funda do que a que o jogador tinha.
    #
    # So converte a RECOMENDACAO (raise -> jam), nunca cria acusacao: quem ja tinha jogado a
    # agressao continua com o mesmo rotulo, e o cap abaixo impede que a troca vire erro novo.
    _PROF_JAM = 10.0
    if (street == 'preflop' and _best_action == 'raise'
            and 0 < float(_hero_stack_bb or 0) <= _PROF_JAM):
        _best_action = 'jam'
        if _action_family(input_data.get('player_action', '')) in ('raise', 'allin'):
            label = 'marginal' if label in ('small_mistake', 'clear_mistake') else label
            final_score = min(final_score, _LABEL_MAX_SCORE['marginal'])

    # ── Defeito 4: blefe em pote com jogador JA all-in ─────────────────────────────────────
    # A anotacao mais valiosa das 71: "nao blefe em potes que ja tem alguem de all-in". Contra
    # quem nao pode foldar nao existe fold equity — o blefe perde a metade da sua razao de ser, e
    # a outra metade (ganhar no showdown) e justamente onde a mao fraca perde. O produto rotulava
    # `standard` nesses bets.
    #
    # So mexe quando ha mao fraca DE VERDADE (`air`) e cartas+board conhecidos, pela mesma razao
    # do bloco de `made_hand_category` acima: sem os dois, ausencia de dado viraria acusacao.
    # Cap em `marginal`, jamais em erro — a jogada tem equity e pode ser correta por outros
    # motivos; o que ela nao pode e ser exibida como linha padrao.
    if (street != 'preflop' and spot.get('hasAllinOpponent')
            and _action_family(input_data.get('player_action', '')) in ('bet', 'raise')
            and label == 'standard'):
        from leaklab.bet_intent import made_hand_category
        _c_ai, _b_ai = input_data.get('hero_cards'), spot.get('board')
        if _c_ai and _b_ai and made_hand_category(_c_ai, _b_ai) == 'air':
            label = 'marginal'
            final_score = max(final_score, _LABEL_MAX_SCORE['standard'] + 0.001)

    # `_best_action` FINAL — o mesmo que o card exibe. A narrativa relia
    # `range_evaluation.recommendedPrimaryAction`, que e a opiniao da HEURISTICA antes das
    # sobrescritas do GTO (linhas ~1006/1012/1029/1064). Resultado medido: 263 de 657 cards
    # acusados diziam "Acao esperada: X" com X diferente do "melhor" do cabecalho — e num
    # deles o texto mandava fazer exatamente o que o jogador tinha feito, enquanto o acusava.
    interpretation = build_interpretation(input_data, label,
                                          threshold_pack["adjustedRequiredEquity"],
                                          best_action=_best_action)

    # Intenção da aposta/raise postflop (value / proteção / semi-blefe / blefe / "o meio").
    # Só preenche em aposta agressiva postflop; None caso contrário.
    from leaklab.bet_intent import classify_bet_intent, explain_recommendation, classify_3bet_intent
    bet_intent = classify_bet_intent(
        player_action=input_data.get("player_action"),
        street=street,
        hero_cards=input_data.get("hero_cards"),
        board=spot.get("board"),
        equity=math.get("estimatedHandEquity"),
        equity_adj=math.get("equityAdjustment"),
        stack_bb=spot.get("effectiveStackBb"),
        position=spot.get("position"),
        gto=gto,
    )

    # Intenção de um 3-BET preflop (valor / merge / light-blefe) — só em raise preflop
    # enfrentando exatamente 1 raise (o open). Ensina o PORQUÊ do 3-bet light.
    threebet_intent = None
    if (input_data.get('is_3bet') and street == 'preflop'
            and int(spot.get('preflopRaisesFaced') or 0) == 1):
        threebet_intent = classify_3bet_intent(
            hero_cards=input_data.get("hero_cards"),
            gto=gto,
        )

    # Racional da AÇÃO RECOMENDADA (por que check/bet/call/fold/raise) — sobretudo p/
    # spots heurísticos (sem GTO), onde não há barras de estratégia explicando.
    reco_rationale = explain_recommendation(
        best_action=_best_action,
        hero_cards=input_data.get("hero_cards"),
        board=spot.get("board"),
        equity=math.get("estimatedHandEquity"),
        equity_adj=math.get("equityAdjustment"),
        position=spot.get("position"),
        n_opponents=spot.get("nActiveOpponents"),
        facing_bb=math.get("facingToBb") or spot.get("facingSize"),
        required_equity=threshold_pack.get("adjustedRequiredEquity") or math.get("potOddsEquity"),
        street=street,
    )

    # Shove == call (excesso impagavel): a tela mostra a acao REAL, e quando o melhor e o call
    # ela passa a mostrar a acao do jogador — porque sao a MESMA jogada, e exibir "melhor: call"
    # ao lado de "voce deu shove" e uma correcao fantasma. Nao mexe no label: ele ja foi calculado
    # como call acima, que e o certo.
    if _shove_e_call:
        input_data = {**input_data, 'player_action': _acao_real}
        if (_best_action or '').lower() == 'call':
            _best_action = _acao_real

    return {
        "handId": input_data["hand_id"],
        "bestAction": _best_action,
        "actionTaken": input_data["player_action"],
        "evaluation": {
            "mistakeScore": round4(final_score),
            "label": label,
            "scoreBreakdown": {
                "baseActionGap": round4(base_action_gap),
                "mathPenalty": round4(math_penalty),
                "rangePenalty": round4(range_penalty),
                "contextPenalty": round4(context_penalty),
                "toleranceCredit": round4(tolerance_credit),
                "streetMultiplier": round4(street_multiplier),
            },
        },
        "thresholds": {
            "potOddsEquity": math.get("potOddsEquity"),
            "realizationAdjustment": round4(realization_adjustment),
            "pressureAdjustment": round4(pressure_adjustment),
            "adjustedRequiredEquity": threshold_pack["adjustedRequiredEquity"],
            "streetCapApplied": threshold_pack["streetCapApplied"],
        },
        "interpretation": interpretation,
        "gto": gto,
        "icm_zone_approx": icm_zone_approx,   # gate zona-ICM: fold ChipEV-reprovado defensável → "≈ Aproximação chipEV"
        "bet_intent": bet_intent,
        "threebet_intent": threebet_intent,
        "reco_rationale": reco_rationale,
        "preflop_gto": preflop_gto if preflop_gto.get('available') else None,
        "debug": {
            "rangeZone": range_eval.get("rangeZone"),
            "alternativeActions": range_eval.get("alternativeActions") or [],
            "rawFlags": [],
        },
    }


def build_interpretation(input_data: Dict[str, Any], label: str,
                        adjusted_required_equity: float | None,
                        best_action: str | None = None):
    summary_map = {
        "standard":      "Linha sólida para o spot.",
        "marginal":      "Ação defensável, mas existe alternativa levemente melhor.",
        "small_mistake": "Pequena perda estratégica, relevante no longo prazo.",
        "clear_mistake": "Erro claro com impacto relevante em EV.",
    }

    # ── Familia 4: o pote com jogador all-in precisa ser NOMEADO, mesmo sem erro ───────────────
    # A anotacao do coach era um CONCEITO ("nao blefe em potes que ja tem alguem de all-in"), e o
    # motor tratava o assunto so no veredito (guarda G4), nunca no texto. Medido em 470 decisoes
    # postflop reais: 50 tem all-in vivo no pote e o hero apostou em 3 — todas com **outro
    # oponente vivo**, e todas com mao de VALOR. Ou seja, o veredito ja estava certo nas tres, e
    # o que faltava era o card dizer o que muda ali.
    #
    # Correcao do meu proprio enunciado: nao e "sem fold equity". Quando o unico oponente esta
    # all-in nao existe aposta possivel (25 dos 50 casos). Havendo aposta, ha alguem vivo para
    # foldar — o que a presenca do all-in tira e o POTE PRINCIPAL, que vai a showdown de qualquer
    # jeito. A frase abaixo diz isso, e nao a versao simplificada.
    _spot_ai = input_data.get('spot') or {}
    _nota_allin = ''
    if (input_data.get('street', 'preflop') != 'preflop' and _spot_ai.get('hasAllinOpponent')
            and _action_family(input_data.get('player_action', '')) in ('bet', 'raise')):
        _nota_allin = ('Há um jogador all-in no pote: o pote principal vai a showdown de qualquer '
                       'forma, então esta aposta disputa apenas o pote lateral e precisa vencer '
                       'no showdown, não por fold.')

    if label not in ("small_mistake", "clear_mistake"):
        return {"summary": summary_map[label], "mathExplanation": "",
                "strategicExplanation": _nota_allin}

    action = input_data.get("player_action", "")
    street = input_data.get("street", "preflop")
    rng    = input_data.get("range_evaluation", {})
    # O best do CARD, nao o da heuristica. `best_action=None` so acontece em chamador antigo;
    # ai cai no de antes, que e o comportamento conhecido.
    best   = best_action if best_action else rng.get("recommendedPrimaryAction", "")
    zone   = rng.get("rangeZone", "")
    mt     = input_data.get("math", {})
    spot   = input_data.get("spot", {})
    ctx    = input_data.get("context", {})

    est      = mt.get("estimatedHandEquity")
    pot_odds = mt.get("potOddsEquity")
    draw     = (mt.get("drawProfile") or "none").lower()
    riods    = mt.get("reverseImpliedOddsFactor") or 0

    position = spot.get("position", "")
    facing   = spot.get("facingSize") or 0

    m_ratio  = ctx.get("mRatio")
    icm      = ctx.get("icmPressure", "low")

    _act = {"fold": "fold", "check": "check", "call": "call",
            "bet": "bet", "raise": "raise", "shove": "all-in", "jam": "all-in"}.get
    _str = {"preflop": "pré-flop", "flop": "flop",
            "turn": "turn", "river": "river"}.get

    action_pt = _act(action, action)
    best_pt   = _act(best, best)
    street_pt = _str(street, street)

    parts = []

    # ── Equity analysis ──────────────────────────────────────────────────────
    if est is not None:
        eq_pct = round(est * 100, 1)
        req_pct = (round(adjusted_required_equity * 100, 1)
                   if adjusted_required_equity is not None
                   else (round(pot_odds * 100, 1) if pot_odds is not None else None))

        if req_pct is not None:
            diff = round(eq_pct - req_pct, 1)
            if action == "call" and best == "fold":
                # A frase NÃO pode assumir a premissa do veredito. Este ramo escrevia "ficou
                # X pp abaixo" com abs(diff) fixo; quando a equity está ACIMA do exigido (o
                # caso de fold recomendado por RANGE, não por preço — ex.: cold-call de 3-bet
                # fora de posição), o texto afirmava o contrário do próprio número exibido no
                # card, que mostra "+19.9pp". Dizer que o preço não fecha quando ele fecha é
                # pior que não explicar: destrói a confiança no resto da análise.
                parts.append(
                    f"Equity de {eq_pct}% ficou {abs(diff)}pp abaixo dos {req_pct}% exigidos — "
                    f"sem valor para continuar no pot."
                    if diff < 0 else
                    f"O preço fechava ({eq_pct}% de equity contra {req_pct}% exigidos), mas o fold "
                    f"vem da RANGE, não do preço: nesta situação a mão fica dominada com "
                    f"frequência alta e fora de posição, e a equity bruta superestima o que "
                    f"você realiza no pot."
                )
            elif action == "fold" and best == "call":
                parts.append(f"Com equity de {eq_pct}% vs {req_pct}% exigidos pelo pot, o call tinha valor positivo (+{abs(diff)}pp).")
            elif action == "fold" and best in ("raise", "shove", "jam", "bet"):
                parts.append(f"Equity de {eq_pct}% suporta {best_pt.upper()} neste spot — foldar deixou valor na mesa.")
            elif action in ("raise", "bet", "shove", "jam") and best == "fold":
                parts.append(f"Equity de {eq_pct}% ficou {abs(diff)}pp abaixo dos {req_pct}% necessários — a agressão não tinha suporte matemático.")
            elif action in ("check", "call") and best in ("bet", "raise"):
                parts.append(f"Com equity de {eq_pct}%, {best_pt.upper()} extrai mais valor e protege melhor do que {action_pt.upper()}.")
            elif diff > 0:
                parts.append(f"Equity de {eq_pct}% supera os {req_pct}% exigidos (+{diff}pp) — linha mais agressiva era suportada.")
            else:
                parts.append(f"Equity de {eq_pct}% ficou {abs(diff)}pp abaixo dos {req_pct}% exigidos para o spot.")
        else:
            parts.append(f"Equity estimada da mão: {eq_pct}%.")

    # ── Draw context ─────────────────────────────────────────────────────────
    if draw not in ("none", "no_draw", ""):
        if "combo" in draw:
            parts.append("Draw combinado (flush + straight) adiciona equity implícita significativa ao cálculo.")
        elif "flush" in draw:
            parts.append("Projeto de flush adiciona ~9% de equity implícita não capturada pelos pot odds simples.")
        elif "straight" in draw:
            parts.append("Projeto de straight adiciona equity implícita — relevante para decisões de call/fold no turn.")
        elif "backdoor" in draw:
            parts.append("Draw backdoor contribui marginalmente com equity extra.")

    if riods > 0.3 and action in ("call", "check") and best == "fold":
        parts.append("Reverse implied odds elevados: quando atrás, o pot fica maior; quando frente, os oponentes param de pagar.")

    # ── MTT / Stack ──────────────────────────────────────────────────────────
    if m_ratio is not None:
        mr = round(m_ratio, 1)
        if mr < 6:
            parts.append(f"M-Ratio {mr}: jogo push/fold — sem espaço para linhas especulativas.")
        elif mr < 10:
            parts.append(f"M-Ratio {mr}: zona crítica de pressão — priorize spots com fold equity real.")
        elif mr < 15:
            parts.append(f"M-Ratio {mr}: pressão moderada — stack preservation pesa em spots marginais.")

    # ICM — na mesa final, leitura direcional pelo sinal contínuo (icm_tax);
    # fora dela, o bucket heurístico icm_pressure. Qualitativo (sem número "duro":
    # os payouts reais não vêm no HH, então a forma da pressão é confiável, o valor não).
    icm_tax = ctx.get("icmTaxPct")
    if icm_tax is not None:
        if icm_tax >= 5:        # equity ICM < fração de fichas → pilha grande
            parts.append("Mesa final: você tem das maiores pilhas — pelo ICM, suas fichas valem menos que a fração no prize pool (retornos decrescentes). Arriscar a stack exige mais equity do que o pot odds sugere; evite flips marginais e prefira pressionar os short stacks.")
        elif icm_tax <= -5:     # equity ICM > fração de fichas → pilha curta
            parts.append("Mesa final: pilha curta com prêmio de sobrevivência — pelo ICM sua equity supera a fração de fichas, então sobreviver tem valor real. Seja seletivo ao arriscar a eliminação.")
        else:
            parts.append("Mesa final: stacks equilibrados — a pressão ICM é leve, mas todo all-in carrega risco de eliminação.")
    elif icm == "high":
        parts.append("ICM elevado: risco de eliminação aumenta o threshold de call — sobrevivência tem valor real.")
    elif icm == "medium" and label == "clear_mistake":
        parts.append("ICM médio: equity de fichas subestima o risco de eliminação neste spot.")

    # ── Range zone / position ────────────────────────────────────────────────
    # `outside_range` fala da MAO, nao da linha — e por isso a frase so faz sentido quando o hero
    # ENTROU na mao com ela. Foldar nunca esta "fora do range defensavel": foldar e o default, e a
    # mao estar fora do range CONFIRMA o fold em vez de conde-lo. Eram 59 cards dizendo
    # "A linha FOLD esta fora do range defensavel" logo acima de um "Acao esperada" qualquer.
    if zone == "outside_range" and action != "fold":
        pos_txt = f"em {position}" if position else "nesta posição"
        parts.append(f"A linha {action_pt.upper()} está fora do range defensável {pos_txt} no {street_pt}.")
    elif zone == "borderline_range":
        parts.append("Spot de borda do range — pequena variação de stack ou ICM pode inverter a decisão correta.")

    # ── Facing bet context ───────────────────────────────────────────────────
    if facing and facing > 0 and action == "fold" and best in ("call", "raise"):
        parts.append(f"A aposta/raise que veio representava uma oferta matematicamente atraente para o pot odds da situação.")

    if not parts:
        parts.append(f"A linha {action_pt.upper()} ficou abaixo do esperado para o spot — {best_pt.upper()} era a ação correta.")

    if _nota_allin:
        parts.insert(0, _nota_allin)     # o contexto vem ANTES do veredito, nao como rodape

    parts.append(f"Ação esperada: {best_pt.upper()}.")

    return {
        "summary": summary_map[label],
        "mathExplanation": "",
        "strategicExplanation": " ".join(parts),
    }
