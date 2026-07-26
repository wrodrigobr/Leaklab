"""
strategy_provider.py — Fonte ÚNICA de verdade para "qual é a jogada certa neste spot".

## Por que este módulo existe

A auditoria de 2026-07-25 encontrou um bug estrutural: componentes diferentes respondiam
"quais ações existem" e "qual é a estratégia GTO" por caminhos INDEPENDENTES que divergiam.
Caso concreto: no Leak Trainer, spot "RFI de SB, A8s, 75bb", o gabarito mostrava raise 54% /
call 46%, mas os BOTÕES oferecidos eram só FOLD e RAISE — porque uma TABELA ESTÁTICA
(`leak_trainer._OPTIONS`) montava o menu de ações SEM consultar a estratégia. A ação call/limp
(46% da estratégia, creditável no grading) não existia como opção.

Este módulo NÃO recalcula estratégia. Ele DELEGA às fontes já existentes (preflop:
`preflop_gto_ranges.analyze_preflop`; postflop: nós pré-solvados via `gto_solver.lookup_gto`),
NORMALIZA a resposta num formato único e — o ponto central — GARANTE o invariante:

    INVARIANTE  menu_de_ações ⊇ { ação : freq_GTO(ação) ≥ MIN_STRATEGY_FREQ }

Ou seja: toda ação que o corretor creditaria como certa TEM que ser oferecível ao jogador.
Foi exatamente a violação desse invariante que gerou o bug do A8s.

## Regra de projeto (ver memória do projeto)

Qualquer nova superfície que precise VERIFICAR ou OFERECER uma decisão (trainer, drill, academy,
daily challenge, replay, coach) DEVE consumir este provider. Nunca montar o menu de ações por
conta própria a partir de constantes/cenário — o menu deriva SEMPRE da estratégia.
"""
from __future__ import annotations

from leaklab.preflop_gto_ranges import analyze_preflop
# Normalizador de ARMAZENAMENTO/solver (fonte única de baixo nível): {fold,check,call,bet,raise,jam},
# colapsa sizes (bet_50pct→bet, raise_119pct→raise) e mapeia limp→call, allin/shove→jam.
from leaklab.gto_utils import normalize_gto_action

# Ação com frequência GTO ≥ isto é creditável como acerto (espelha leak_trainer.MIN_FREQ) →
# portanto DEVE ser oferecível. Fonte única do limiar de "linha co-ótima".
MIN_STRATEGY_FREQ = 0.10

# Ordem canônica de exibição de um menu de ações (o front rende nessa ordem).
CANONICAL_ACTION_ORDER = ('fold', 'check', 'call', 'raise', 'allin')

# Menu game-tree quando o herói enfrenta uma aposta postflop (fold/call/raise cobre a árvore;
# o solver colapsa os sizes de aposta na família 'raise'). Fonte única — não redefinir inline.
POSTFLOP_FACING_BET_MENU = ('fold', 'call', 'raise')


# ── Bridge de vocabulário (dois dialetos coexistem no código) ───────────────────────────────────
# ARMAZENAMENTO/solver (gto_nodes, decision_engine, /replay, gto_utils): usa 'jam' e distingue
#   'bet' de 'raise'. É o dialeto de baixo nível (VALID_GTO_ACTIONS).
# EXIBIÇÃO/trainer (este provider, frontend FREQ_LABEL): usa 'allin' e colapsa 'bet'→'raise'.
# Toda travessia entre os dois DEVE passar por estas duas funções — nunca reescrever inline.

def to_storage_action(action: str) -> str:
    """Dialeto de ARMAZENAMENTO/solver: {fold,check,call,bet,raise,jam}. Ex.: 'allin'→'jam'."""
    return normalize_gto_action(action)


def to_display_action(action: str) -> str:
    """Dialeto de EXIBIÇÃO/trainer: 'jam'→'allin', 'bet'→'raise' (o front só rotula fold/call/raise/allin)."""
    s = normalize_gto_action(action)
    if s == 'jam':
        return 'allin'
    if s == 'bet':
        return 'raise'
    return s


def normalize_action(a: str) -> str:
    """Normaliza um rótulo de ação para o dialeto de EXIBIÇÃO. Idempotente. Único normalizador
    de exibição do provider — construído sobre o normalizador de armazenamento (gto_utils)."""
    return to_display_action(a)


def normalize_freq_map(freq: dict | None) -> dict:
    """Normaliza um mapa {ação: freq} para chaves canônicas, somando famílias colididas (jam+allin)."""
    out: dict = {}
    for k, v in (freq or {}).items():
        if v is None:
            continue
        key = normalize_action(k)
        out[key] = out.get(key, 0.0) + float(v)
    return {k: round(v, 4) for k, v in out.items()}


def _order(actions) -> list[str]:
    """Ordena um conjunto de ações pela ordem canônica; ações fora da lista vão ao fim (estável)."""
    seen = list(dict.fromkeys(actions))
    ranked = [a for a in CANONICAL_ACTION_ORDER if a in seen]
    extra = [a for a in seen if a not in CANONICAL_ACTION_ORDER]
    return ranked + extra


def menu_with_strategy(base_menu, freq_map: dict | None) -> list[str]:
    """O CORAÇÃO do provider — impõe o invariante.

    Une o menu game-tree (`base_menu`, as ações legais do spot independentes da mão) com TODA
    ação creditável da estratégia da mão (freq ≥ MIN_STRATEGY_FREQ). Assim o menu é, por
    construção, um superconjunto do que o corretor creditaria — o bug do A8s não pode recorrer.
    """
    menu = list(base_menu)
    for act, f in normalize_freq_map(freq_map).items():
        if f >= MIN_STRATEGY_FREQ and act not in menu:
            menu.append(act)
    return _order(menu)


def menu_covers_strategy(menu, freq_map: dict | None) -> list[str]:
    """Guard de invariante: devolve a lista de ações creditáveis que FALTAM no menu (vazia = OK).
    Usado nos testes de regressão e como defesa-em-profundidade. Se não-vazio, é o bug do A8s."""
    have = set(normalize_action(a) for a in (menu or []))
    missing = [a for a, f in normalize_freq_map(freq_map).items()
               if f >= MIN_STRATEGY_FREQ and a not in have]
    return _order(missing)


def preflop_base_menu(scenario: str, position: str) -> list[str]:
    """Ações legais do spot preflop pela ÁRVORE (independentes da mão do herói).

    RFI: fold/raise para todas as posições, MAIS call (complete/limp) quando o herói abre do SB —
    o SB é a única posição que pode completar no RFI (a BB nunca faz RFI: se todos foldam até a BB,
    ela ganha sem abrir). Essa é a razão-raiz do bug: a tabela estática antiga dava sempre
    ['fold','raise'] no RFI, engolindo o limp do SB. Mesmo aqui, o `menu_with_strategy` faz a
    rede de segurança: qualquer ação creditável da mão entra no menu ainda que a base erre.
    vs_rfi / vs_3bet / squeeze / demais: defensor pode fold/call/raise.
    """
    scn = (scenario or '').lower()
    if scn == 'rfi':
        base = ['fold', 'raise']
        if (position or '').upper() == 'SB':
            base.insert(1, 'call')
        return base
    return ['fold', 'call', 'raise']


def preflop_strategy(position: str, hand: str | None = None, stack_bb: float = 20.0, *,
                     hero_hand_type: str | None = None, action_taken: str = 'fold',
                     facing_size: float = 0.0, vs_position: str = '',
                     is_3bet_pot: bool = False, hero_was_aggressor: bool = False,
                     facing_raises: int = 0, caller_position: str = '',
                     n_players: int | None = None, facing_limp: bool = False,
                     is_pko: bool = False, facing_to_bb: float = 0.0,
                     facing_allin: bool = False) -> dict:
    """Resposta normalizada de estratégia preflop — a PORTA ÚNICA para preflop (trainer, academy,
    decision_engine/HH analyzer, /replay). Encaminha TODA a superfície de parâmetros do
    `analyze_preflop` (não recalcula nada). `hand`/`hero_hand_type` são sinônimos (ex.: 'A8s').

    Devolve:
      available          — a fonte cobre este spot?
      scenario           — rfi / vs_rfi / vs_3bet / …
      hand_freq          — {ação_canônica (dialeto exibição): freq} da MÃO do herói (mista)
      recommended        — ações recomendadas (dialeto exibição), ordem de freq desc da fonte
      available_actions  — MENU a oferecer (invariante garantido) — use SEMPRE isto p/ os botões
      range_pct          — % do range naquele nó (p/ display)
      raw                — o dict CRU de analyze_preflop (dialeto ARMAZENAMENTO: recommended_actions
                           com 'jam', action_quality, ev_loss_bb, pro_notes…). O engine/replay
                           consomem `raw` e seguem no dialeto de armazenamento sem mudança.
    """
    res = analyze_preflop(
        position=position,
        hero_hand_type=(hero_hand_type if hero_hand_type is not None else hand),
        stack_bb=float(stack_bb),
        action_taken=action_taken,
        facing_size=float(facing_size or 0.0),
        vs_position=vs_position or '',
        is_3bet_pot=bool(is_3bet_pot),
        caller_position=caller_position or '',
        n_players=n_players,
        facing_raises=int(facing_raises or 0),
        hero_was_aggressor=bool(hero_was_aggressor),
        facing_limp=bool(facing_limp),
        is_pko=bool(is_pko),
        facing_to_bb=float(facing_to_bb or 0.0),
        facing_allin=bool(facing_allin),
    )
    scenario = res.get('scenario')
    hand_freq = normalize_freq_map(res.get('hand_freq'))
    recommended = [normalize_action(a) for a in (res.get('recommended_actions') or [])]
    base = preflop_base_menu(scenario or '', position)
    available_actions = menu_with_strategy(base, hand_freq)
    return {
        'available':         bool(res.get('available')),
        'scenario':          scenario,
        'hand_freq':         hand_freq,
        'recommended':       recommended,
        'available_actions': available_actions,
        'range_pct':         res.get('range_pct'),
        'raw':               res,
    }


def postflop_menu(freq_map: dict | None = None) -> list[str]:
    """Menu postflop (herói enfrenta aposta) com o invariante aplicado sobre o menu game-tree fixo."""
    return menu_with_strategy(POSTFLOP_FACING_BET_MENU, freq_map)
