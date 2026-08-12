from __future__ import annotations
import re
from typing import List
from .models import HandState, ParsedHand
from .hand_state_builder import extract_decision_points, build_hand_state
from .spot_classifier import classify_spot
from .street_math_engine import build_math_snapshot
from .preflop_range_evaluator import evaluate_preflop_range
from .mtt_context import build_mtt_context, context_to_dict
from .postflop_range_evaluator import evaluate_postflop_range
from .draw_detector import adjust_equity_for_draws


def _parse_cards(raw) -> list:
    """Converte hero_cards para lista de strings de 2 chars: '7s4s' → ['7s','4s']."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        # já é lista — garante que cada item é 2 chars
        return [str(c).strip() for c in raw if str(c).strip()]
    s = str(raw).replace(' ', '')
    # Padrão: rank (A,K,Q,J,T,2-9) + suit (s,h,d,c)
    return re.findall(r'[2-9TJQKAakqjt][shdcSHDC]', s)


def build_decision_input(state: HandState, hand: 'ParsedHand | None' = None) -> dict:
    """Constrói o input do Decision Engine para um HandState."""
    spot      = classify_spot(state)

    # #27 range-aware: quando o hero DEFENDE contra um open, injeta a RFI range GTO real do
    # opener pra equity vs RANGE (não vs random).
    #
    # ── 07/08: estendido ao 3-bet, que era o buraco ────────────────────────────────────────────
    # A versão anterior parava no open simples, com a justificativa "3bet/4bet têm ranges mais
    # estreitas e ficam no vs-random". Justamente por serem mais estreitas é que o vs-random
    # mente mais ali: o coach pegou um AQo contra 4-bet all-in exibindo **64,4%** de equity, e o
    # card usou esse número — medido contra outra coisa — para abençoar o call. Contra a range
    # real de 3-bet o mesmo AQo fica em ~52%.
    #
    # A range de re-raise sai das MESMAS cartas que já usamos para gradear o villain. Quando não
    # há cobertura, `villain_reraise_range` devolve `{}` e tudo segue como antes: **equity contra
    # range errada é pior que contra aleatória**, porque parece precisa.
    if (state.street == 'preflop'
            and state.villain_position and state.villain_position != 'unknown'):
        try:
            _raises = int((state.metadata or {}).get('preflop_raises_faced') or 0)
            mtt = state.metadata.get('mtt_context', {}) or {}
            vr = None
            # ── 09/08: enfrentando ALL-IN, a range é a de JAM ──────────────────────────────────
            # Até aqui o all-in caía no vs-random de propósito: a carta `vs_RFI` modela um 3-bet
            # DE TAMANHO, e usar um nó pelo outro é precisão falsa. A saída nunca foi voltar ao
            # aleatório, era ler o nó certo — a coluna `allin_hands` do MESMO spot, que já estava
            # no arquivo. `villain_jam_range` devolve `{}` sem cobertura, e aí nada muda.
            _allin = bool((state.metadata or {}).get('facing_allin'))
            if _allin and _raises >= 1:
                from .preflop_gto_ranges import villain_jam_range
                vr = villain_jam_range(
                    state.villain_position,
                    state.position,
                    state.effective_stack_bb or 0.0,
                    state.metadata.get('n_players'),
                    _raises,
                    bool(mtt.get('isPko')),
                    opener_pos=(state.metadata or {}).get('preflop_opener') or '',
                    # **Obrigatório, não opcional.** `preflop_raises_faced` conta raises de
                    # VILÃO, então sem esta flag um 3-bet jam (hero abriu, 1 raise de vilão) é
                    # indistinguível de um open-jam, e um 4-bet jam de um 3-bet jam. Nos dois
                    # casos o erro serve uma range mais LARGA e absolve call ruim.
                    hero_was_aggressor=bool((state.metadata or {}).get('hero_was_aggressor')),
                )
            if not vr and _raises == 1:
                # Open-jam sem carta de jam cai na range de ABERTURA, que é o comportamento de
                # hoje e é conservador de propósito (mais larga que a de jam, logo a favor do
                # hero). O `villain_jam_range` só a substitui onde abrir É jamar.
                from .preflop_gto_ranges import villain_open_range
                vr = villain_open_range(
                    state.villain_position,
                    state.effective_stack_bb or 0.0,
                    state.metadata.get('n_players'),
                    bool(mtt.get('isPko')),
                )
            elif not vr and _raises >= 2 and state.position and not _allin:
                from .preflop_gto_ranges import villain_reraise_range
                vr = villain_reraise_range(
                    state.villain_position,
                    state.position,
                    state.effective_stack_bb or 0.0,
                    state.metadata.get('n_players'),
                    bool(mtt.get('isPko')),
                )
            if vr:
                state.metadata['villain_range'] = vr
        except Exception:
            pass

    math      = build_math_snapshot(state)

    # Injetar equity no metadata — ajustada por draws para postflop
    raw_equity = math.estimated_hand_equity
    if state.street != 'preflop' and raw_equity is not None:
        adjusted_eq, draw_profile = adjust_equity_for_draws(
            raw_equity,
            state.hero_cards or '',
            state.board or [],
            state.street,
        )
        state.metadata['estimated_equity']   = adjusted_eq
        state.metadata['raw_equity']         = raw_equity
        state.metadata['draw_profile']       = str(draw_profile)
        state.metadata['equity_adjustment']  = round(adjusted_eq - raw_equity, 4)
    else:
        state.metadata['estimated_equity'] = raw_equity
        state.metadata['raw_equity']       = raw_equity
        state.metadata['draw_profile']     = 'none'
        state.metadata['equity_adjustment']= 0.0

    # Usar evaluator correto por street
    if state.street == 'preflop':
        range_eval = evaluate_preflop_range(state, spot)
    else:
        range_eval = evaluate_postflop_range(state)

    hand_profile = {
        'handClass':             classify_hand_class(state.hero_cards),
        'showdownValueTier':     classify_showdown_tier(state.hero_cards),
        'drawTier':              classify_draw_tier(state.hero_cards, state.board),
        'blockerProfile':        [],
        'rawEquityEstimate':     math.estimated_hand_equity,
        'realizedEquityEstimate': math.estimated_hand_equity,
    }

    is_3bet = (
        state.street == 'preflop' and
        state.player_action in ('raise', 'shove', 'jam') and
        state.facing_size > 0
    )

    return {
        'hand_id':       state.hand_id,
        'street':        state.street,
        'player_action': state.player_action,
        'hero_cards':    _parse_cards(state.hero_cards),
        'is_3bet':       is_3bet,
        'spot': {
            'spotType':         spot.spot_type,
            'position':         state.position,
            'villainPosition':  state.villain_position,
            'villainName':      state.metadata.get('villain_name'),
            'isInPosition':     state.is_in_position,
            'isMultiway':       state.is_multiway,
            'effectiveStackBb': state.effective_stack_bb,
            'potSize':          state.pot_size,
            'potBb':            round(state.pot_size / (state.metadata.get('bb') or 1), 2),  # pote em bb (p/ SPR)
            'facingSize':       state.facing_size,
            'raiseSizeBb':      state.facing_size,
            'board':            state.board or [],
            'nPlayers':         state.metadata.get('n_players'),  # tamanho da mesa
            'nActiveOpponents': state.metadata.get('n_active_opponents', 1),  # opps vivos na street
            # Preflop: quem ainda NAO foldou, incluindo quem nao agiu. `nActiveOpponents`
            # so conta quem ja agiu, e no pote limpado isso perde o BB.
            'nCanSeeFlop':      state.metadata.get('n_can_see_flop'),
            'preflopRaisesFaced': state.metadata.get('preflop_raises_faced', 0),  # 3-bet/squeeze faced
            'heroWasAggressor':   state.metadata.get('hero_was_aggressor', False),
            # Iniciativa na ENTRADA da street (postflop): 'hero' | 'vilao' | None. Ver o
            # comentario no builder — e o sinal de LEITURA, nao entra no numero que acusa.
            'iniciativaDaStreet': state.metadata.get('iniciativa_da_street'),
            'facingAllin':        state.metadata.get('facing_allin', False),  # enfrenta all-in (call = a agressão)
            # ...e o excesso de um raise seria impagavel por todos → aumentar E o call.
            'shoveEquivaleCall':  state.metadata.get('shove_equivale_call', False),
            # Alguem vivo ja esta all-in: blefe nao tem fold equity contra ele.
            'hasAllinOpponent':   state.metadata.get('has_allin_opponent', False),
            'facingLimp':         state.metadata.get('facing_limp', False),  # pote limpado (fora de cobertura GTO)
            'callerPosition':     state.metadata.get('caller_position', ''),  # cold caller (pra rotear squeeze)
            'facingToBb':         state.metadata.get('facing_to_bb'),  # #23: open enfrentado em bb (raise-to total)
            # TAMANHO da aposta (facingToBb) x CUSTO de pagá-la (facingToCallBb). O primeiro
            # identifica o nó — uma aposta "to 12bb" é o mesmo nó independente de quem já pôs
            # quanto — e por isso segue mandando no spot_hash. O segundo é o que sai do bolso.
            'facingToCallBb':     state.metadata.get('facing_to_call_bb'),
            'heroRaiseToBb':      state.metadata.get('hero_raise_to_bb'),  # tamanho do PRÓPRIO raise do hero
            'potType':            state.metadata.get('pot_type', 'srp'),       # Fase 2: srp|3bet|4bet|limped
            'preflopOpener':      state.metadata.get('preflop_opener', ''),    # posição do opener
            'preflop3bettor':     state.metadata.get('preflop_3bettor', ''),   # posição do 3-bettor
        },
        'hand_profile': hand_profile,
        'math': {
            'potOddsEquity':            math.pot_odds_equity,
            'estimatedHandEquity':      state.metadata.get('estimated_equity',
                                            math.estimated_hand_equity),
            'rawEquity':                state.metadata.get('raw_equity',
                                            math.estimated_hand_equity),
            'drawProfile':              state.metadata.get('draw_profile', 'none'),
            'equityAdjustment':         state.metadata.get('equity_adjustment', 0.0),
            'impliedOddsFactor':        math.implied_odds_factor,
            'reverseImpliedOddsFactor': math.reverse_implied_odds_factor,
            'pressureScore':            math.pressure_score,
            # #27: 'vs_range' quando a equity foi calculada vs a RFI range real do
            # opener (vs_rfi); 'vs_random' caso contrário (proxy mão aleatória).
            'equitySource':             'vs_range' if state.metadata.get('villain_range') else 'vs_random',
        },
        'range_evaluation': {
            'recommendedPrimaryAction': range_eval.recommended_primary_action,
            'alternativeActions':       range_eval.alternative_actions,
            'rangeZone':                range_eval.range_zone,
            'confidence':               range_eval.confidence,
            'mixWeight':                range_eval.mix_weight,
        },
        'context': state.metadata.get('mtt_context', {
            'tournamentStage': 'unknown',
            'icmPressure':     'low',
            'bountyDynamic':   False,
            'readsAvailable':  False,
        }),
    }


def build_decision_inputs_for_hand(hand: ParsedHand, field_size: int | None = None,
                                   colocacoes: dict | None = None) -> List[dict]:
    """
    Retorna lista de decision inputs — um por cada decisão do hero na mão.
    Injeta contexto MTT real (M ratio, stage, ICM pressure) em cada decisão.

    `field_size` (inscritos, do resumo) habilita o ICM contínuo em torneio de mesa única;
    `colocacoes` ({nome: colocação final}, também do resumo) habilita em MESA FINAL DE MTT, que
    `field_size` nunca cobre. Sem nenhum dos dois, só o bucket heurístico — ver
    `leaklab.mesa_final`.
    """
    states = extract_decision_points(hand)

    # Calcular MTT context uma vez por mão e injetar em todos os estados
    try:
        mtt = build_mtt_context(hand, field_size=field_size, colocacoes=colocacoes)
        ctx = context_to_dict(mtt)
    except Exception:
        ctx = {'tournamentStage': 'unknown', 'icmPressure': 'low',
               'bountyDynamic': False, 'readsAvailable': False}

    for s in states:
        s.metadata['mtt_context'] = ctx

    return [build_decision_input(s) for s in states]


# ── Hand profile helpers ──────────────────────────────────────────────────────

def classify_hand_class(cards: str | None) -> str:
    if not cards or len(cards) < 4:
        return 'unknown'
    r1, s1, r2, s2 = cards[0], cards[1], cards[2], cards[3]
    if r1 == r2:
        return 'pair'
    if s1 == s2 and r1 in 'TJQKA' and r2 in 'TJQKA':
        return 'suited_broadway'
    if s1 != s2 and (r1 in 'TJQKA' or r2 in 'TJQKA'):
        return 'dominated_broadway'
    return 'unpaired'


def classify_showdown_tier(cards: str | None) -> str:
    if not cards or len(cards) < 4:
        return 'unknown'
    if cards[0] == cards[2]:
        return 'pair'
    if cards[0] in 'TJQKA' and cards[2] in 'TJQKA':
        return 'broadway'
    return 'weak'


def classify_draw_tier(cards: str | None, board: list) -> str:
    if not cards or len(cards) < 4:
        return 'none'
    if cards[1] == cards[3]:
        return 'backdoor_or_fd'
    return 'none'
