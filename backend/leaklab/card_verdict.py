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

import re


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


# ── A nota gravada contra o veredito de HOJE ──────────────────────────────────────────────
#
# A nota do card e TEXTO congelado no instante da analise. O resync do solver reescreve
# `best_action`, `gto_action`, `label` e `ev_loss_bb` horas depois e NAO reescreve o texto.
#
# Medido em producao em 14/09: 1.519 decisoes servindo uma ordem no texto e exibindo outra na
# linha, das quais 1.167 na forma pior -- o veredito ABSOLVE o jogador e o texto o acusa
# ("Flop: Fold" com chip verde de Correto, e a nota mandando dar CALL).
#
# O controle que sustenta a causa: a contradicao aparece em 39,7% das linhas cujo custo veio de
# `solver_hand` (reescritas depois) contra 0,1% das de `gw_har` (carta preflop, nunca reescrita).
# Se o defeito fosse do gerador de texto, as duas fontes empatariam. Nao empatam.
#
# Por que nao basta apagar a frase final: o corpo da nota tambem e escrito em funcao de `best`,
# em nove pontos de `decision_engine_v11` (2104, 2120, 2122, 2123, 2124, 2142, 2143, 2168, 2209).
# Tirar so a ultima sentenca deixa um paragrafo inteiro defendendo a acao velha.
#
# Duas formas, porque o produto escreve duas: o motor grava "Ação esperada: RAISE."
# (`decision_engine_v11:2218`) e `_enrich_note` regera "mas o esperado era RAISE." (`app.py`).
# Ate 15/09 a regua so lia a primeira, e a nota regerada passava sem ser julgada (VER-5).
_RE_ACAO_DECLARADA = re.compile(
    r'(?:A[cç][aã]o esperada:|o esperado era)\s*([A-Za-zÀ-ÿ\-]+)', re.IGNORECASE)


def acao_declarada_na_nota(note) -> str:
    """A acao que o TEXTO da nota manda fazer, normalizada. '' quando a nota nao declara nenhuma.

    A ausencia da frase NAO e sinal de nada: o motor so a acrescenta quando o label e erro
    (`decision_engine_v11:2218`); quando nao e, ele retorna antes (linha 2058) e a nota fica
    apenas com as sentencas de contexto. Essas sentencas sao condicionadas a jogada do HEROI e a
    forca da mao, nunca a `best` -- por isso nao envelhecem quando o veredito e reescrito.
    Conferido no acervo: as 1.200 notas sem a frase sao todas sentenca de contexto.
    """
    m = _RE_ACAO_DECLARADA.search(note or '')
    return norm_action(m.group(1)) if m else ''


def nota_contradiz_o_veredito(note, gto_action, best_action) -> bool:
    """A nota gravada manda fazer coisa diferente do que a linha recomenda HOJE.

    Compara contra `gto_action or best_action` porque e ISSO que a tela mostra ao lado da nota
    (`TournamentDetail.tsx:153`). Os dois divergem em 191 decisoes do acervo, e 17.430 nao tem
    `gto_action` -- julgar pelo outro campo faria a funcao avaliar uma recomendacao que o
    jogador nao ve.

    A equivalencia sai de `_matches`, a mesma que o resto do veredito usa, para que
    `bet` e `bet_75pct` nao contem como divergencia. Inventar uma segunda regra de equivalencia
    aqui seria criar o proximo bug dos N lugares.
    """
    declarada = acao_declarada_na_nota(note)
    if not declarada:
        return False
    recomendada = norm_action(gto_action) or norm_action(best_action)
    if not recomendada:
        return False
    return not _matches(declarada, recomendada)


# ── Multiway postflop: o solver nao modela esta mao ───────────────────────────────────────
#
# O solver e HEADS-UP: um `ip_range` contra um `oop_range`. Decisao postflop com 2+ oponentes
# ativos e resolvida como se os outros nao existissem.
#
# O caso que trouxe isto (mao 262009780504): flop de CINCO, aberto pelo UTG+1 com cold call do
# HJ. O solve modelou "HJ abre, BB paga" heads-up, deu ao HJ um range de ABERTURA (com AA/KK/AK,
# que ele 3-betaria em vez de pagar), e nesse mundo QJ tem 75,1% de equity contra os 53,1% que o
# proprio motor calculou. Dos 75% saiu `allin 61,2%` e uma acusacao de 37,67bb. O GTO Wizard, no
# no heads-up equivalente a 70bb, nao tem all-in no menu.
#
# Medido antes de fechar: 8.953 decisoes multiway com veredito de solver (32,4% do postflop),
# 728 acusando, 5.254,8bb cobrados. E no ranking de leaks, que ordena o PLANO DE ESTUDOS, o
# multiway era 32,7% da massa de EV perdido do pagante.
#
# `n_ativos` nulo conta como NAO multiway, de proposito: e legado/reimport, e essa e a mesma
# convencao do drill (`repositories` 2012) e do card (`app.py` 2707). Inverter aqui esconderia
# decisao heads-up antiga sem ter evidencia de que ela e multiway.
#
# O GEMEO EM SQL vive em `repositories._SQL_MULTIWAY_FORA`, porque `get_breakdown` agrega em
# GROUP BY e nao da para chamar Python de dentro do SQL. Sao duas expressoes da MESMA regra, e
# `test_multiway_fora_dos_agregados` prova que elas concordam caso a caso -- sem esse teste
# seriam duas regras que combinam de ser iguais.
def multiway_sem_cobertura(street, n_ativos) -> bool:
    """True quando a decisao e postflop com 2+ oponentes ativos, logo fora do que o solver mede.

    Nao diz que o jogador acertou nem que errou: diz que NAO SABEMOS. Quem consome isto tira a
    linha da medicao, em vez de contar como acerto -- contar como acerto e a mesma mentira na
    direcao oposta, e a casa ja tem o invariante de que celula sem dado nunca vira 0,0.
    """
    if str(street or '').strip().lower() == 'preflop':
        return False
    try:
        return int(n_ativos or 0) >= 2
    except (TypeError, ValueError):
        return False


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


# Um call que ja poe TODAS as fichas nao deixa nada atras. Abaixo disto o hero nao consegue nem
# postar um blind: 0,05bb nao e "fichas restantes", e a coluna `facing_to_call_bb` vem arredondada
# em 2 casas contra um `effective_stack_bb` de 7 (1,46 contra 1,4566667).
_SOBRA_IRRELEVANTE_BB = 0.05

_COMMIT = ('jam', 'shove', 'allin', 'all-in', 'raise')


def call_e_commit_total(facing_to_call_bb, effective_stack_bb) -> bool:
    """Pagar ja custa o stack inteiro: nao existe `jam` que seja outra decisao."""
    try:
        custo = float(facing_to_call_bb)
        stack = float(effective_stack_bb)
    except (TypeError, ValueError):
        return False
    # Sem um dos dois numeros NAO afirmamos nada. Chutar aqui apagaria veredito legitimo — a
    # mesma armadilha do estimador de equity, em que a ausencia de dado virava o caso que convem.
    return stack > 0 and custo >= stack - _SOBRA_IRRELEVANTE_BB


def colapsa_commit_para_call(spot: dict, played_action) -> bool:
    """A IRMA de `colapsa_shove_para_call`, na direcao oposta — e a que faltava.

    La o hero deu shove e o excesso voltava, entao o shove ERA o call. Aqui o hero PAGOU e o call
    ja levou tudo, entao o `jam` da carta E o call: o vilao apostou mais do que o hero tem, raise
    nao existe no spot, e as duas palavras movem exatamente as mesmas fichas.

    Caso que originou (27/08, invariante MUDO 0 -> 1, decisao 325499 em producao): AJo no BTN com
    1,4566bb efetivos enfrentando um raise de 2,0bb de UTG. A carta manda jam; o hero pagou
    all-in. A carta classificou `leak` pela PALAVRA e gravou `gto_critical`, enquanto o veredito
    final saiu `standard`. A tela entregou "Correto" com "recomendado: jam" e "-0,141bb" do lado.

    Uma direcao so: colapsar nunca cria acusacao. `fold` fica de fora — recomendar fold contra um
    commit e critica legitima, e o leak ali seria entrar na mao, nao a palavra usada."""
    if str(played_action or '').lower().strip().rstrip('s') != 'call':
        return False
    return call_e_commit_total((spot or {}).get('facingToCallBb'),
                               (spot or {}).get('effectiveStackBb'))


def carta_colapsada_por_commit_total(quality, recomendadas, spot, acao_jogada):
    """Aplica o colapso na leitura da carta preflop: `(quality, recomendadas, custo_ok)`.

    Funcao PURA de proposito. A 1a versao era um `if` dentro do motor, e os guardas de fiacao dele
    passaram verde com a condicao trocada por `False` — o vies de ancorar no EFEITO em vez de na
    CONDICAO, que ja me custou quatro guardas cegos em 25/08. Aqui o comportamento e testavel sem
    montar uma decisao inteira.

    `custo_ok` False significa: nao ha diferenca de EV a cobrar, porque as duas acoes movem as
    mesmas fichas."""
    if not colapsa_commit_para_call(spot, acao_jogada):
        return quality, recomendadas, True
    if quality in ('correct', 'unknown'):
        return quality, recomendadas, True
    if str((list(recomendadas or []) or [''])[0]).lower() not in _COMMIT:
        return quality, recomendadas, True
    return 'correct', ['call'], False


def carta_nao_acusa_fold_vs_allin(quality, ev_loss, *, facing_allin, acao_jogada,
                                  equity, equity_exigida):
    """A carta ABSOLVE o fold contra all-in quando o preco nao fecha: `(quality, ev_loss)`.

    ── O caso do dono (16/09), torneio 30, mao 157832100251 ──────────────────────────────────

    K7s no SB, 3-bet ALL-IN de 33,9bb, fold. A carta de `vs_3bet` do balde de 30bb declara
    `raise_to_bb: 15.0`: ela modela um 3-bet DIMENSIONADO, que deixaria 15bb atras para jogar o
    flop. Com 15bb atras, seguir com K7s se defende (fold equity, board por vir). Contra um shove
    nao ha flop nenhum: e equity pura.

    Na MESMA decisao o motor mediu equity de 43,4% contra 44,4% exigidos pelo pote, ou seja o
    fold estava certo por um ponto percentual -- e a carta cobrou 1,21bb dele. As duas fontes do
    nosso proprio produto discordavam, e a que acusava estava usando um sizing que nao era o do
    spot.

    ── Por que ABSOLVER e nao recalcular ────────────────────────────────────────────────────

    A mesma doutrina que ja vale para a carta de mesa cheia do GW: "carta vizinha absolve, nao
    acusa". Aqui o sizing e o vizinho. Recalcular o EV com o sizing certo exigiria um no que nao
    temos; derrubar a acusacao quando o preco a contradiz e aditivo e nunca inventa erro novo,
    que e o lado seguro da regra 7.

    O `ev_loss` tambem vai a None, e nao so a qualidade: a lista "Leaks por custo" ranqueia por
    EV, entao deixar o custo de pe manteria a decisao na lista de leaks depois de o card
    absolver -- duas superficies discordando, que e o defeito que esta semana inteira consertou.

    Quando o preco FECHA (equity >= exigida), a acusacao fica: ali a carta e o pote concordam.
    """
    if not facing_allin:
        return quality, ev_loss
    if str(acao_jogada or '').strip().lower() != 'fold':
        return quality, ev_loss
    if equity is None or equity_exigida is None:
        return quality, ev_loss          # sem os dois numeros nao ha o que comparar
    try:
        if float(equity) >= float(equity_exigida):
            return quality, ev_loss      # o preco fecha: a carta e o pote concordam
    except (TypeError, ValueError):
        return quality, ev_loss
    if quality in ('correct', 'unknown'):
        return quality, ev_loss
    return 'correct', None


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


def limiar_de_ev_desprezivel() -> float:
    """O MESMO `_PREFLOP_EV_MINOR_BB` (0,12bb) do motor. Import tardio: o motor importa este
    módulo, e o limiar é dele."""
    try:
        from leaklab.decision_engine_v11 import _PREFLOP_EV_MINOR_BB
        return float(_PREFLOP_EV_MINOR_BB)
    except Exception:                                                     # pragma: no cover
        return 0.12


def leak_de_custo_infimo(quality, ev_loss_bb) -> bool:
    """`leak` (freq>0, dentro de um mix) cujo EV medido fica abaixo do limiar.

    RC-A: `major_leak` (freq~0, fora do range) NUNCA entra — custa pouco justamente porque a
    mão não devia estar no pote, e é erro de DIREÇÃO. Sem EV medido também não entra: custo não
    declarado não vira atenuante (a régua `ev_loss_trustworthy` decide pela fonte)."""
    if quality != 'leak' or ev_loss_bb is None:
        return False
    try:
        return float(ev_loss_bb) < limiar_de_ev_desprezivel()
    except (TypeError, ValueError):
        return False


def rebaixa_gto_label_por_custo(gto_label, quality, ev_loss_bb):
    """`gto_critical` de custo ínfimo vira `gto_minor_deviation` — a regra do motor, agora UMA.

    O motor já rebaixava (`_low_cost_leak`) e o card mapeava `leak` direto para `gto_critical`:
    a mesma decisão saía `gto_minor_deviation` na coluna (ELO, drill) e `gto_critical` no card,
    que então imprimia "desvio caro" ao lado de "Correto". Auditoria VER-6 (15/09)."""
    if gto_label == 'gto_critical' and leak_de_custo_infimo(quality, ev_loss_bb):
        return 'gto_minor_deviation'
    return gto_label


def verdict_from_preflop(pf_quality, pf_recommended, played_norm, ev_loss_bb=None) -> dict | None:
    """Camada 3 — veredito preflop pela qualidade da ação segundo as ranges.

    None = qualidade que não reconhecemos ('unknown'): a camada anterior permanece de pé.

    `ev_loss_bb` é o custo medido do spot (`preflop_gto['ev_loss_bb']`, o mesmo que o motor lê).
    Ausente, o veredito é o de antes: sem custo declarado nada é rebaixado."""
    hit = _PF_QUALITY.get(pf_quality)
    if not hit:
        return None
    is_error, label = hit
    return {
        'is_error':        is_error,
        'reconciled_best': pf_recommended if is_error else played_norm,
        'gto_label':       rebaixa_gto_label_por_custo(label, pf_quality, ev_loss_bb),
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
