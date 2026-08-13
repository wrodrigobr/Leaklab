"""
Veredito do Decision Card a partir das estratégias do solver — fonte PURA e testável
da reconciliação que o `/replay` faz ao vivo (antes inline em `api/app.py`, sem teste
direto; era a camada onde o bug A2s/mão 5 morava).

Invariante central: quando existe a estratégia da MÃO específica do hero
(`hand_strategy`), o veredito vem DELA, NUNCA da ação modal do range agregado
(`strategy`). O range descreve o CONJUNTO de mãos ("fold 63%" = % do range que
desiste); a mão decide a jogada do hero ("A2s raise 93%"). Num nó multiway aproximado
os dois divergem fortemente — julgar pelo range marcava "GTO recomenda Fold" numa mão
que o solver LEVANTA 93%.

Espelha a regra do frontend `cardLogic.verdictStrategy` + a reconciliação do app.
"""
from __future__ import annotations


def norm_action(a) -> str:
    """rstrip 's' + unifica all-in/allin/jam/shove → 'allin'. Mantém sizing
    (bet_75pct, raise_2.5bb) — o matching de prefixo cuida da equivalência base."""
    a = (a or '').strip().lower()
    if not a:
        return ''
    a = a[:-1] if a.endswith('s') else a
    return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a


def _matches(played_norm: str, act_norm: str) -> bool:
    if not played_norm or not act_norm:
        return False
    return (act_norm == played_norm
            or played_norm.startswith(act_norm)
            or act_norm.startswith(played_norm))


def label_for_freq(freq: float) -> str:
    """gto_label pela FREQUÊNCIA da ação na estratégia (mesma régua do app/frontend)."""
    if freq >= 0.60:
        return 'gto_correct'
    if freq >= 0.30:
        return 'gto_mixed'
    if freq >= 0.10:
        return 'gto_minor_deviation'
    return 'gto_critical'


# ── Precedência DECLARADA das camadas ─────────────────────────────────────────────────────────
#
# Antes disto a precedência era a ordem das instruções dentro de uma função de 1012 linhas: para
# responder "num spot multiway postflop, quem decide — o solver ou a severidade do engine?" era
# preciso ler 390 linhas de cima para baixo e simular. A resposta certa estava lá, e até
# comentada, mas expressa como layout de arquivo.
#
# Agora a ordem é um dado. Quem vem depois vence, e aplicar fora de ordem levanta erro em vez de
# passar silenciosamente — o que só pode acontecer por edição de código, nunca por dado.
LAYERS = (
    'stored',           # 1   label gravado na decisão (o que o import concluiu)
    'live',             # 2   estratégia viva do solver; a da MÃO manda sobre a do RANGE
    'preflop',          # 3   ranges estáticas — nó agregado engana no preflop
    'multiway_advice',  # 4a  advisor multiway com alta confiança
    'multiway_engine',  # 4b  advisor deferiu → severidade do engine, não frequência HU
    'multiway_safe',    # 4c  cauda segura: veredito que sobrevive ao canto adversário
)

# Só estes campos atravessam a cadeia. Filtrar é o que garante que uma camada não escreva por
# acidente um campo que ela não decide (as funções devolvem também dados de diagnóstico).
_CHAIN_FIELDS = ('is_error', 'reconciled_best', 'gto_label', 'gto_action', 'live_top_act')


class VerdictChain:
    """Acumula o veredito registrando QUEM decidiu.

    Vale tanto pelo que impede quanto pelo que guarda: `layer` responde, para cada card, qual
    camada teve a última palavra — pergunta que antes não tinha resposta sem depurar."""

    __slots__ = ('data', 'layer', 'trail')

    def __init__(self, **seed):
        self.data  = dict(seed)
        self.layer = None
        self.trail = []

    def apply(self, layer: str, verdict) -> 'VerdictChain':
        """Aplica uma camada por cima das anteriores. `verdict` None = a camada não opinou."""
        if layer not in LAYERS:
            raise ValueError(f"camada desconhecida: {layer!r} (esperado uma de {LAYERS})")
        if self.layer is not None and LAYERS.index(layer) <= LAYERS.index(self.layer):
            raise ValueError(
                f"camada {layer!r} aplicada depois de {self.layer!r} — fora da ordem declarada. "
                f"Se a precedência mudou de propósito, mude LAYERS, não a ordem das chamadas.")
        if verdict is None:
            return self          # não opinou: nem sobrescreve nem vira dona do veredito
        self.data.update({k: v for k, v in verdict.items() if k in _CHAIN_FIELDS})
        self.layer = layer
        self.trail.append(layer)
        return self

    def unpack(self):
        """Os 5 campos na ordem em que o /replay os usa."""
        d = self.data
        return (d.get('is_error'), d.get('reconciled_best'), d.get('gto_label'),
                d.get('gto_action'), d.get('live_top_act'))

    def __getitem__(self, k):
        return self.data.get(k)


# ── Camada 1: label ARMAZENADO no banco ───────────────────────────────────────────────────────
#
# As 4 camadas de reconciliação do /replay rodam em sequência e cada uma sobrescreve a anterior
# por atribuição simples. Elas continuam nessa ordem — o que muda aqui é que a DECISÃO de cada
# uma virou função pura e nomeada, em vez de um bloco solto no meio de uma função de 1000 linhas.
#
# Nota sobre normalização: estas funções NÃO normalizam nada. Recebem valores já normalizados
# pelo chamador, de propósito. O `/replay` usa um `_norm` local que difere do `norm_action` daqui
# (não faz lower/strip e usa `rstrip('s')`, que come todos os "s" finais); trocar um pelo outro
# seria mudança de comportamento disfarçada de refactor. Unificar é trabalho à parte, com um
# teste de equivalência sobre o vocabulário real de ações antes.

_FACING_BET = {'call', 'calls'}
_NO_BET     = {'check', 'checks', 'bet', 'bets'}

# O engine chama de erro três severidades; o ramo multiway abaixo só considera duas. A diferença
# é real e está preservada — não é descuido.
_ENGINE_ERROR_LABELS    = ('clear_mistake', 'small_mistake', 'marginal')
_MW_ENGINE_ERROR_LABELS = ('small_mistake', 'clear_mistake')


_ACOES_DE_COMMIT = ('shove', 'jam', 'allin', 'all-in', 'raise')


def colapsa_shove_para_call(spot: dict, played_action) -> bool:
    """Shove sobre all-in cujo excesso ninguem pode pagar E o call: mesmo pote, mesmo custo,
    mesmo resultado. FONTE UNICA da condicao — o motor (decision_engine) e a camada viva do
    /replay usam ESTA funcao. Em 12/08 a regra existia so no motor: o refill deu no vivo ao
    spot, a camada 2 do replay ligou e re-acusou "Shove vs Call" num spot em que o hero cobria
    todos — a MESMA acusacao que o conserto de 11/08 tinha matado, uma porta acima."""
    return (bool((spot or {}).get('shoveEquivaleCall'))
            and (str(played_action or '')).lower() in _ACOES_DE_COMMIT)


def spot_mismatch(gto_action_norm: str, engine_best_norm: str) -> bool:
    """O nó GTO responde a um spot INCOMPATÍVEL com o que o hero enfrenta.

    "check" não é ação possível para quem enfrenta uma aposta, e "call" não é para quem não
    enfrenta nenhuma. Quando isso acontece o nó é de outro spot, e a recomendação dele precisa
    ser ignorada inteira — não corrigida."""
    if not (gto_action_norm and engine_best_norm):
        return False
    return ((engine_best_norm in _FACING_BET and gto_action_norm in _NO_BET)
            or (engine_best_norm in _NO_BET and gto_action_norm in _FACING_BET))


def verdict_from_stored(gto_label, gto_action, engine_best, decision_label,
                        played_norm, mismatch: bool) -> dict:
    """Camada 1 — veredito a partir do que está GRAVADO na decisão.

    `decision_label` é None quando não há decisão do engine para a ação (aí nada é erro).
    Com spot incompatível ou sem dado GTO, o engine decide sozinho."""
    engine_says_error = decision_label in _ENGINE_ERROR_LABELS
    if mismatch:
        return {'is_error': engine_says_error, 'reconciled_best': engine_best}
    if gto_label in ('gto_correct', 'gto_mixed'):
        # o solver confirma a jogada como válida — o alarme do engine era falso
        return {'is_error': False, 'reconciled_best': played_norm}
    if gto_label in ('gto_minor_deviation', 'gto_critical') and gto_action:
        return {'is_error': True, 'reconciled_best': gto_action}
    return {'is_error': engine_says_error, 'reconciled_best': engine_best}


# ── Camada 3: override preflop (ranges estáticos do StrategyProvider) ─────────────────────────
#
# Nós agregados dão recomendação enganosa no preflop (a ação modal do RANGE, não a da mão), então
# o preflop é decidido pelo `analyze_preflop` com a mão específica do hero, por cima das camadas
# 1 e 2. Qualidade desconhecida NÃO mexe no veredito — daí o None.
_PF_QUALITY = {
    'correct':             (False, 'gto_correct'),
    'acceptable':          (False, 'gto_mixed'),
    'gto_minor_deviation': (True,  'gto_minor_deviation'),
    'minor_mistake':       (True,  'gto_minor_deviation'),
    'leak':                (True,  'gto_critical'),
    'major_leak':          (True,  'gto_critical'),
}


def verdict_from_preflop(pf_quality, pf_recommended, played_norm) -> dict | None:
    """Camada 3 — veredito preflop pela qualidade da ação segundo as ranges.

    None = qualidade que não reconhecemos ('unknown'): a camada anterior permanece de pé."""
    hit = _PF_QUALITY.get(pf_quality)
    if not hit:
        return None
    is_error, label = hit
    return {
        'is_error':        is_error,
        'reconciled_best': pf_recommended if is_error else played_norm,
        'gto_label':       label,
    }


# ── Camada 4: multiway (o solver é heads-up; aqui ele não manda) ──────────────────────────────

def verdict_from_multiway_advice(advice_action, advice_action_norm, is_leak) -> dict:
    """Camada 4a — o advisor multiway opinou com alta confiança e tem prioridade sobre o nó HU.

    `gto_action`/`live_top_act` ficam com o valor CRU e só `reconciled_best` normalizado: é o
    comportamento atual e a diferença é visível na tela, não cosmética."""
    return {
        'is_error':        bool(is_leak),
        'reconciled_best': advice_action_norm,
        'gto_action':      advice_action,
        'live_top_act':    advice_action,
    }


def verdict_from_multiway_engine(decision_label, engine_best,
                                 reconciled_best, gto_action) -> dict:
    """Camada 4b — o advisor DEFERIU. O veredito vem da severidade do engine, não da frequência
    heads-up (que chamaria de crítico um spot que o coach aprova). Duas severidades, não três."""
    return {
        'is_error':        decision_label in _MW_ENGINE_ERROR_LABELS,
        'reconciled_best': engine_best or reconciled_best,
        'gto_action':      engine_best or gto_action,
    }


def verdict_from_multiway_safe(recommended, recommended_norm, is_leak) -> dict:
    """Camada 4c — cauda SEGURA: veredito que sobrevive ao canto adversário das premissas, então
    vale como erro/correto de verdade e substitui o informativo da 4a."""
    return {
        'is_error':        bool(is_leak),
        'reconciled_best': recommended_norm,
        'gto_action':      recommended,
        'live_top_act':    recommended,
        'safe_label':      'small_mistake' if is_leak else 'standard',
    }


def reconcile_verdict(strategy, hand_strategy, played_action, stored_gto_action=None):
    """
    strategy:          lista [{'action','frequency'}, ...] — RANGE agregado do nó (ou None)
    hand_strategy:     lista [{'action','frequency'}, ...] — MÃO específica do hero (ou None)
    played_action:     ação que o hero tomou
    stored_gto_action: gto_action do banco (fallback p/ recommended quando não há modal)

    Retorna None quando não há nenhuma estratégia. Senão, dict:
      source         : 'hand' (mão tem prioridade) | 'range'
      played_freq    : freq da ação jogada na estratégia escolhida
      live_top_act   : ação modal (a recomendada)
      top_freq       : freq da modal
      gto_label      : label por played_freq
      is_error       : played_freq < 0.30 (fora da estratégia mista)
      reconciled_best: ação jogada (normalizada) se não-erro; senão a modal
      gto_action     : live_top_act or stored_gto_action
    """
    src = hand_strategy if hand_strategy else strategy
    source = 'hand' if hand_strategy else 'range'
    if not src:
        return None

    played_norm = norm_action(played_action)
    played_freq = 0.0
    live_top_act = None
    top_freq = -1.0
    for item in src:
        act = item.get('action', '')
        f = float(item.get('frequency') or 0.0)
        if _matches(played_norm, norm_action(act)):
            played_freq = f
        if f > top_freq:
            top_freq = f
            live_top_act = act
    if live_top_act is None:
        return None

    is_error = played_freq < 0.30
    return {
        'source': source,
        'played_freq': played_freq,
        'live_top_act': live_top_act,
        'top_freq': max(top_freq, 0.0),
        'gto_label': label_for_freq(played_freq),
        'is_error': is_error,
        'reconciled_best': played_norm if not is_error else live_top_act,
        'gto_action': live_top_act or stored_gto_action,
    }
