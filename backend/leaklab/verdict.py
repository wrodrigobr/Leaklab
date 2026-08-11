"""
verdict.py — fonte ÚNICA do veredito de DISPLAY em 3 níveis: Correto / Aceitável / Erro.

A plataforma mantém INTERNAMENTE 4 níveis de SEVERIDADE (`label`: standard / marginal /
small_mistake / clear_mistake) + a FREQUÊNCIA (`gto_label`) — necessários para ELO, ranking
de leaks, study plan e análises cognitivas. Mas o que o USUÁRIO vê colapsa em 3, dirigido
pela SEVERIDADE (custo de EV), encerrando a dualidade frequência×severidade (raiz dos bugs
card≠badge e do "Desvio Crítico" num desvio barato). A frequência vira CONTEXTO (barras de
estratégia), não veredito.

Mapa:  standard → Correto · marginal → Aceitável · small/clear_mistake → Erro.
"""

# Os 3 níveis canônicos de display.
CORRECT    = 'correct'
ACCEPTABLE = 'acceptable'
ERROR      = 'error'

# Severidade (label) → nível de display. Ausente/desconhecido → None (sem veredito).
_SEVERITY_TO_LEVEL = {
    'standard':      CORRECT,
    'marginal':      ACCEPTABLE,
    'small_mistake': ERROR,
    'clear_mistake': ERROR,
}


def verdict3(label):
    """Severidade (`label`) → nível de display de 3 níveis. None quando não há label
    classificável (ex.: spot sem cobertura)."""
    return _SEVERITY_TO_LEVEL.get((label or '').strip().lower())


def is_error(label) -> bool:
    """Atalho: a jogada é um ERRO no display de 3 níveis? (mesma régua da aderência)."""
    return verdict3(label) == ERROR


# Ações que INVESTEM fichas (continuar), em contraste com fold. Cobre variantes de all-in.
_ICM_CONTINUE_ACTIONS = frozenset({'call', 'raise', 'bet', 'allin', 'jam', 'shove'})


def icm_zone_softens_fold(icm_pressure, active_players, played_action, best_action) -> bool:
    """Gate zona-ICM (SÓ folds): o grading é ChipEV e não modela ICM. Sob ICM real,
    tight-is-right — foldar uma mão que o ChipEV manda CONTINUAR (call/raise/shove) não
    é erro, é uma APROXIMAÇÃO (o modelo não enxerga o risk premium). Este gate diz quando
    NÃO marcar esse aperto como "Erro".

    Escopo deliberadamente estreito (decisão de produto):
    - Só quando o hero FOLDOU. NUNCA abranda call/shove loose (aí o ChipEV segue mandando;
      um call -$EV sob ICM é ainda pior, não queremos aprová-lo).
    - Só em zona-ICM: `icm_pressure == 'high'` E mesa curta (`active_players <= 6`). A mesa
      curta aproxima "fundo no torneio" sem depender do tamanho do field (que o HH não traz).
      Um short stack full-ring no early/mid NÃO é zona-ICM: lá acumular +cEV importa, e um
      aperto ali é leak de verdade que deve continuar sendo marcado.
    """
    if (icm_pressure or '').strip().lower() != 'high':
        return False
    try:
        if active_players is not None and int(active_players) > 6:
            return False
    except (TypeError, ValueError):
        pass
    if (played_action or '').strip().lower() != 'fold':
        return False
    return (best_action or '').strip().lower() in _ICM_CONTINUE_ACTIONS


# ── Piso por DIREÇÃO ───────────────────────────────────────────────────────────────────────────
#
# Ações em que o hero PÕE fichas por iniciativa própria.
_ACOES_AGRESSIVAS = {'raise', 'bet', 'jam', 'shove', 'allin', 'all-in', '3bet', '4bet', 'reraise'}

# Rótulos de frequência em que a agressão pode ser CO-ÓTIMA. Num nó misto onde o solver
# raisa 45% e folda 55%, raisar não é erro de direção — é o outro lado do mix.
_MIX_LEGITIMO = ('gto_mixed', 'gto_correct')

_SEV = {'standard': 0, 'marginal': 1, 'small_mistake': 2, 'clear_mistake': 3, 'critical': 4}


def is_verdict_error_signal(gto_action, action_taken, played_freq=None, in_range=None) -> bool:
    """Sinal CANÔNICO de erro de DIREÇÃO. True ⇒ a mão nunca pode ser 'correta'/'aceitável',
    independente de ev_loss baixo.

    Captura: o GTO folda a mão (fora do range de continuação) mas o hero AGREDIU; ou a ação
    tomada tem frequência GTO ~0 / está fora do range.

    NÃO olha `gto_label` — é só o sinal. Quem decide se ele vira piso é `piso_por_direcao`.
    """
    ga = (gto_action or '').lower().strip()
    at = (action_taken or '').lower().strip()
    if at not in _ACOES_AGRESSIVAS:
        return False
    if ga == 'fold':                                     # GTO descarta a mão; hero agrediu
        return True
    if played_freq is not None and played_freq < 0.05:   # ação com freq ~0 (fora do mix)
        return True
    if in_range is False:                                # fora do range (agressão preflop)
        return True
    return False


def piso_por_direcao(label, gto_label, gto_action, action_taken,
                     played_freq=None, in_range=None) -> str:
    """Aplica o piso de erro por direção, RESPEITANDO o mix legítimo. Fonte única da regra.

    ── Por que isto virou função ──────────────────────────────────────────────────────────────
    A regra vivia em dois lugares. O reconcile (`_reconcile_label`) excluía `gto_correct` e
    `gto_mixed`; o motor tinha a MESMA regra escrita à mão, sem a exclusão, e com um comentário
    dizendo "espelha o is_verdict_error_signal do reconcile" — que não espelhava.

    O resultado medido em produção em 11/08: 12 decisões com o selo `GTO Correto` e o veredito
    `small_mistake` no mesmo card, todas com score exatamente 0,19 (o piso da banda de
    small_mistake). Eram nós MISTOS: o solver raisava entre 30% e 49% do tempo, o hero raisou, e
    o produto chamou de erro. Um relabel completo levaria isso de 12 para 19.

    Comentário não é evidência (CLAUDE.md, item 8) e regra em N lugares vira função (item 5).
    """
    if gto_label in _MIX_LEGITIMO:
        return label
    if not is_verdict_error_signal(gto_action, action_taken, played_freq, in_range):
        return label
    return label if _SEV.get(label, 0) >= _SEV['small_mistake'] else 'small_mistake'
