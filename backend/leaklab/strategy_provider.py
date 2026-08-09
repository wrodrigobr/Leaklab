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


# Profundidade a partir da qual o SHOVE entra no menu SEMPRE, independentemente da estratégia
# da mão. Ver `preflop_base_menu` — é uma correção de vazamento, não uma preferência.
SHOVE_MENU_MAX_BB = 20.0


def preflop_base_menu(scenario: str, position: str, stack_bb: float | None = None) -> list[str]:
    """Ações legais do spot preflop pela ÁRVORE (independentes da mão do herói).

    RFI: fold/raise para todas as posições, MAIS call (complete/limp) quando o herói abre do SB —
    o SB é a única posição que pode completar no RFI (a BB nunca faz RFI: se todos foldam até a BB,
    ela ganha sem abrir). Essa é a razão-raiz do bug: a tabela estática antiga dava sempre
    ['fold','raise'] no RFI, engolindo o limp do SB. Mesmo aqui, o `menu_with_strategy` faz a
    rede de segurança: qualquer ação creditável da mão entra no menu ainda que a base erre.
    vs_rfi / vs_3bet / squeeze / demais: defensor pode fold/call/raise.

    SHOVE em stack curto (≤20bb): entra SEMPRE, mesmo com frequência GTO zero. Três razões, e a
    primeira é de correção, não de gosto:
      1. ANTI-TELL. Se o botão só aparecesse quando o shove é bom, o MENU ENTREGARIA A RESPOSTA.
         Medido em BB vs SB @14bb: das mãos em que o botão aparecia, o shove era 27-100%; nas
         que não aparecia, 0%. O jogador aprende a ler o menu em vez de ler o spot.
      2. REALISMO. Na mesa o shove está sempre disponível abaixo de ~20bb; um menu que o remove
         treina um conjunto de decisões que não existe.
      3. DIAGNÓSTICO. "Shovar por sobrevivência" é um leak real de MTT — e sem a ação no menu o
         trainer não consegue nem detectá-lo, porque o jogador não tem como expressá-lo.
    Acima de 20bb o shove não entra: ali ele não é decisão de verdade e só polui o menu.
    """
    scn = (scenario or '').lower()
    if scn == 'rfi':
        base = ['fold', 'raise']
        if (position or '').upper() == 'SB':
            base.insert(1, 'call')
    else:
        base = ['fold', 'call', 'raise']
    if stack_bb is not None and float(stack_bb) <= SHOVE_MENU_MAX_BB:
        base.append('allin')
    return base


_NAIPES = ('h', 'd', 'c', 's')
_RANKS = '23456789TJQKA'


def _normaliza_mao(mao):
    """Cartas concretas → hand type. `'AdQd'` → `'AQs'`, `'KhQc'` → `'KQo'`, `'5h5d'` → `'55'`.

    Já veio hand type? Devolve igual. **Formato irreconhecível devolve `None`**, e não uma
    tentativa de adivinhar: `analyze_preflop` responde `available=False` para `None`, e "não sei"
    é infinitamente melhor que "fold 100%" para uma mão que abre.

    Existe porque o analisador compara o texto da mão com a string do range. `'AdQd'` não está em
    `'...,AQo,AQs,...'`, então ele conclui "fora do range" e recomenda fold — com confiança, sem
    erro nenhum. O modo grind mostrou exatamente isso: fold para AQs de UTG+1 a 58bb.
    """
    if mao is None:
        return None
    m = str(mao).strip().replace(' ', '')
    if not m:
        return None
    # já é hand type: '77', 'AQs', 'AQo'
    if len(m) == 2 and m[0].upper() in _RANKS and m[1].upper() in _RANKS:
        return m[0].upper() + m[1].upper()
    if len(m) == 3 and m[2].lower() in ('s', 'o') and m[0].upper() in _RANKS and m[1].upper() in _RANKS:
        return m[0].upper() + m[1].upper() + m[2].lower()
    # cartas concretas: 'AdQd'
    if len(m) == 4 and m[1].lower() in _NAIPES and m[3].lower() in _NAIPES:
        r1, r2 = m[0].upper(), m[2].upper()
        if r1 not in _RANKS or r2 not in _RANKS:
            return None
        if r1 == r2:
            return r1 + r2
        if _RANKS.find(r1) < _RANKS.find(r2):
            r1, r2 = r2, r1                      # rank alto primeiro, como no hand type
        return f"{r1}{r2}{'s' if m[1].lower() == m[3].lower() else 'o'}"
    return None


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
    # A mão chega aqui como HAND TYPE ('AQs', '77', 'KQo'). Quando chega como CARTAS CONCRETAS
    # ('AdQd'), o analisador não reconhece, conclui "fora do range" e responde **fold 100% com
    # confiança** — não levanta erro nenhum. Foi assim que o modo grind mostrou "o GTO manda fold"
    # para AQs de UTG+1 a 58bb, que é uma abertura padrão. Resposta errada silenciosa é o pior
    # defeito possível num corretor, e o conserto mora AQUI porque esta é a porta única do preflop:
    # protegendo o chamador que errou hoje, protejo os que vierem.
    _bruta = hero_hand_type if hero_hand_type is not None else hand
    _mao = _normaliza_mao(_bruta)
    if _bruta and _mao is None:
        # Mão veio, e não dá para entender. Responder "não sei" é obrigatório: `analyze_preflop`
        # não valida o formato, então seguir daqui produziria "fora do range, fold 100%" para uma
        # string qualquer. Conferido: sem esta porta, `preflop_strategy(..., 'lixo')` voltava
        # `available=True`. Um corretor que responde com confiança sobre entrada que não entendeu
        # é pior que um que recusa.
        return {'available': False, 'scenario': '', 'hand_freq': {}, 'recommended': [],
                'available_actions': [], 'range_pct': None, 'raise_to_bb': None,
                'raw': {'available': False, 'motivo': 'mao_em_formato_desconhecido',
                        'hand_type': str(_bruta)[:16]}}
    res = analyze_preflop(
        position=position,
        hero_hand_type=_mao,
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
    base = preflop_base_menu(scenario or '', position, stack_bb)
    available_actions = menu_with_strategy(base, hand_freq)
    return {
        'available':         bool(res.get('available')),
        'scenario':          scenario,
        'hand_freq':         hand_freq,
        'recommended':       recommended,
        'available_actions': available_actions,
        'range_pct':         res.get('range_pct'),
        # TAMANHO GTO do raise em bb (do código 'R2.1'). None quando a linha não é raise
        # (ex.: BB vs SB a 14bb, onde as opções são call ou shove).
        'raise_to_bb':       res.get('raise_to_bb'),
        'raw':               res,
    }


def postflop_menu(freq_map: dict | None = None) -> list[str]:
    """Menu postflop (herói enfrenta aposta) com o invariante aplicado sobre o menu game-tree fixo."""
    return menu_with_strategy(POSTFLOP_FACING_BET_MENU, freq_map)


# ── Gate de PREMISSA de cenário ─────────────────────────────────────────────────────────────────
# Em spots onde o HERÓI JÁ ABRIU (vs_3bet e afins), a história do spot é "você abriu esta mão e
# levou 3-bet" — logo a mão treinável DEVE pertencer ao range de abertura da posição. Sem este
# gate, o gerador servia spots com premissa impossível (ex.: "UTG+1 abriu 84o", que o GTO abre
# 0%), induzindo o jogador ao erro. O bug: analyze_preflop devolve available=True pro vs_3bet de
# mão fora do open (rec=fold), então "cobertura" sozinha não filtra a premissa.
# Limiar 5%: mão que o GTO abre ao menos ~1 em 20 vezes é premissa plausível (mãos de fronteira
# que abrem 10-20% são ótimas didaticamente: "você abre às vezes — e agora vs 3-bet?"). Poeira de
# frequência (<5%) não conta.
MIN_PREMISE_OPEN_FREQ = 0.05


def hand_in_open_range(position: str, hand: str, stack_bb: float,
                       min_freq: float = MIN_PREMISE_OPEN_FREQ) -> bool:
    """A mão pertence ao range de ABERTURA (raise+allin) da posição neste stack? Usado como gate
    de premissa pelos geradores de spot vs_3bet (trainer/academy/daily). RFI indisponível → False
    (sem como validar a premissa, não serve o spot)."""
    res = analyze_preflop(position=position, hero_hand_type=hand, stack_bb=float(stack_bb),
                          action_taken='raise', facing_size=0.0, vs_position='')
    if not res.get('available'):
        return False
    hf = normalize_freq_map(res.get('hand_freq'))
    return (hf.get('raise', 0.0) + hf.get('allin', 0.0)) >= min_freq


# ── Fallbacks preflop honestos (sem cobertura de árvore) — fonte única p/ o /replay ──────────────
# Estes eram construídos INLINE no /replay em 2-3 cópias (incl. o hack
# `recommended_actions: ['call' if _q != 'leak' else 'fold']`). Centralizados aqui pra não divergir.
# Devolvem um dict no dialeto de ARMAZENAMENTO (recommended_actions com fold/call/raise), como o
# analyze_preflop. O CHAMADOR decide o GATILHO (ex.: facing ≥ 40% do stack) — estas só constroem.

def preflop_call_vs_shove_fallback(position: str, hero_hand_type: str, stack_bb: float,
                                   action_taken: str = 'call') -> dict | None:
    """Fallback call-vs-shove: sem dados vs_3bet/vs_shove na árvore, usa a pertinência ao range de
    ABERTURA (RFI) como proxy honesto — mão no open que paga um shove = correto; fora do open = leak.
    Devolve um dict raw-shaped OU None se não há cobertura RFI da posição."""
    rfi = analyze_preflop(position=position, hero_hand_type=hero_hand_type, stack_bb=float(stack_bb),
                          action_taken='raise', facing_size=0.0, vs_position='')
    if not rfi.get('available'):
        return None

    # ── A pergunta certa e "a mao ABRE?", nao "o RAISE esta certo?" ───────────────────────────
    # A versao anterior lia `action_quality` de uma consulta feita com `action_taken='raise'`. Em
    # stack curto o GTO abre as maos fortes com JAM, entao "raise" volta como leak — e o fallback
    # concluia "mao fora do range de abertura, folde ao shove" para uma mao que abre **100%**.
    #
    # Caso real (33 no SB heads-up, 15,2bb efetivos, pagando shove de 17,2 com 53,8% de equity
    # contra 43,8% de pot odds): o card acusava ERRO. O proprio retorno se contradizia —
    # `in_range=True` junto de `recommended_actions=['fold']`.
    #
    # Agora a forca vem da FREQUENCIA de nao-fold da mao: e a mesma pergunta que o range faz.
    freq = rfi.get('hand_freq') or {}
    _abre = sum(float(v or 0) for k, v in freq.items() if k != 'fold') if freq else None
    if _abre is None:
        rq = rfi.get('action_quality', 'unknown')
        q  = 'correct' if rq == 'correct' else ('acceptable' if rq == 'acceptable' else 'leak')
    else:
        q = 'correct' if _abre >= 0.80 else ('acceptable' if _abre >= 0.30 else 'leak')
    return {
        'available':           True,
        'scenario':            'vs_shove_fallback',
        'hand_type':           hero_hand_type,
        'stack_bucket':        rfi.get('stack_bucket', f'{int(stack_bb)}bb'),
        'stack_bb':            stack_bb,
        'position':            position,
        'vs_position':         '',
        'range_pct':           rfi.get('range_pct', 0),
        'range_hands':         rfi.get('range_hands', ''),
        'action_taken':        action_taken,
        'pro_notes':           rfi.get('pro_notes', []),
        'recommended_actions': ['call'] if q != 'leak' else ['fold'],
        'action_quality':      q,
        # `in_range` e `recommended_actions` NAO podem se contradizer: era exatamente esse par
        # ("no range" + "folde") que o card exibia lado a lado. Aqui os dois saem da MESMA conta.
        'in_range':            q != 'leak',
        'reasoning': (
            'Mão premium em range de abertura — call de shove correto.'  if q == 'correct'    else
            'Mão no limite do range — call de shove aceitável.'          if q == 'acceptable' else
            'Mão fora do range de abertura — fold vs shove recomendado.'
        ),
    }


def preflop_open_range_proxy(position: str, hero_hand_type: str, stack_bb: float,
                             action_taken: str) -> dict | None:
    """Proxy de range de ABERTURA p/ spots preflop SEM cobertura (ex.: vs limp multiway). Usa a
    pertinência ao RFI da PRÓPRIA ação nas 2 pontas CLARAS: FOLD de mão fora do open = trivialmente
    correto; RAISE (iso) de mão dentro do open = padrão. Devolve dict raw-shaped OU None (ambíguo)."""
    if action_taken not in ('fold', 'raise'):
        return None
    proxy = analyze_preflop(position=position, hero_hand_type=hero_hand_type, stack_bb=float(stack_bb),
                            action_taken=action_taken, facing_size=0.0, vs_position='')
    if not (proxy.get('available') and proxy.get('action_quality') in ('correct', 'acceptable')):
        return None
    return {
        **proxy,
        'action_taken':    action_taken,
        'open_range_proxy': True,
        'reasoning': (
            'Mão fora da range de abertura: fold é trivial em qualquer pote não-aberto.'
            if action_taken == 'fold' else
            'Mão na range de abertura: isolar o limp é o padrão (proxy da range de abertura).'
        ),
    }
