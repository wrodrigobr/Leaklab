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
