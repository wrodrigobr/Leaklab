"""
revalidation — Varredura sistemática de mãos × recomendações.

Contraponto ao replayer manual: para cada decisão do herói em cada torneio,
roda o engine atual, consulta as fontes GTO direto, e pede o veredicto de um
oráculo independente (que NÃO passa por decision_engine_v11). Classifica a
divergência por severidade e produz relatório agregado para guiar correções.

Módulos:
  oracle       — escolha de ação independente do engine (GTO + heurística determinística)
  differ       — classifica divergência engine vs oracle
  orchestrator — varre torneios, persiste findings, gera relatórios
  report       — formatadores Markdown/JSON do orchestrator
  llm_judge    — tiebreaker opcional via Claude Haiku (gated por flag)
"""

from .oracle import OracleDecision, decide

__all__ = ['OracleDecision', 'decide']
