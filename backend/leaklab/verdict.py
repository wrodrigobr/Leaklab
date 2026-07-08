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
