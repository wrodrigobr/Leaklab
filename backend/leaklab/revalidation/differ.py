"""
differ.py -- Classifica a divergência entre o veredicto do engine e o do oráculo.

Não inventa veredito próprio: apenas categoriza o par (engine_best, oracle.action)
considerando alternativas conhecidas, GTO label e opp_cost.

Categorias:
  aligned            -- engine_best == oracle.action (após normalização canônica)
  acceptable_alt     -- engine_best in alternativas do oráculo OU GTO classifica como mixed
  minor_mismatch     -- ações diferentes, baixo opp_cost (< 0.15bb) ou gto_minor_deviation
  major_mismatch     -- ações diferentes E (opp_cost >= 0.30bb OU gto_critical OU fold<->jam)
  no_oracle_data     -- oracle.confidence == 'unavailable' (engine pode estar certo, sem como verificar)
  engine_no_data     -- engine_best vazio (raro -- proteção)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from leaklab.decision_engine_v11 import _norm_gto_action
from leaklab.revalidation.oracle import OracleDecision


# Aggressive <-> passive pares que sempre são "major" quando trocados
_AGGRESSIVE = {'bet', 'raise', 'jam', 'allin', 'shove'}
_PASSIVE    = {'fold', 'check', 'call'}

# Tiers de severidade numérica (0..1) para ordenar findings no relatório.
_SEVERITY_BY_CATEGORY = {
    'aligned':         0.00,
    'acceptable_alt':  0.05,
    'no_oracle_data':  0.10,
    'engine_no_data':  0.20,
    'minor_mismatch':  0.40,
    'major_mismatch':  0.85,
}


@dataclass
class DivergenceRecord:
    category: str
    severity_score: float
    engine_best: Optional[str]
    oracle_action: Optional[str]
    gto_action: Optional[str]
    action_taken: Optional[str]
    opp_cost_bb: Optional[float]
    oracle_source: str
    oracle_confidence: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'category':          self.category,
            'severity_score':    round(self.severity_score, 4),
            'engine_best':       self.engine_best,
            'oracle_action':     self.oracle_action,
            'gto_action':        self.gto_action,
            'action_taken':      self.action_taken,
            'opp_cost_bb':       self.opp_cost_bb,
            'oracle_source':     self.oracle_source,
            'oracle_confidence': self.oracle_confidence,
            'reasons':           list(self.reasons),
        }


def classify(engine_result: dict,
             oracle: OracleDecision,
             gto_info: Optional[dict] = None,
             action_taken: Optional[str] = None) -> DivergenceRecord:
    """
    engine_result: dict produzido por evaluate_decision()
    oracle:        OracleDecision retornado por oracle.decide()
    gto_info:      dict opcional com {'gto_label': str, 'gto_action': str}
                   (engine_result['gto'] já carrega isso quando available)
    action_taken:  ação efetiva do jogador (para anotar no record)
    """
    engine_best  = (engine_result or {}).get('bestAction')
    debug        = (engine_result or {}).get('debug') or {}
    alts_engine  = [a for a in (debug.get('alternativeActions') or []) if a]
    gto_dict     = gto_info or (engine_result or {}).get('gto') or {}
    gto_action   = gto_dict.get('gto_action')
    gto_label    = gto_dict.get('gto_label')
    if action_taken is None:
        action_taken = (engine_result or {}).get('actionTaken')

    reasons: list[str] = []

    # 1) Engine sem ação -- proteção
    if not engine_best:
        return DivergenceRecord(
            category='engine_no_data',
            severity_score=_SEVERITY_BY_CATEGORY['engine_no_data'],
            engine_best=engine_best, oracle_action=oracle.action,
            gto_action=gto_action, action_taken=action_taken,
            opp_cost_bb=oracle.opp_cost_bb,
            oracle_source=oracle.source, oracle_confidence=oracle.confidence,
            reasons=['engine.bestAction vazio'],
        )

    # 2) Oracle sem dados -- engine pode estar certo, mas não há como verificar
    if oracle.confidence == 'unavailable' or oracle.action is None:
        reasons.append('oracle.confidence=unavailable')
        return DivergenceRecord(
            category='no_oracle_data',
            severity_score=_SEVERITY_BY_CATEGORY['no_oracle_data'],
            engine_best=engine_best, oracle_action=None,
            gto_action=gto_action, action_taken=action_taken,
            opp_cost_bb=None,
            oracle_source=oracle.source, oracle_confidence=oracle.confidence,
            reasons=reasons,
        )

    ne = _norm_gto_action(engine_best)
    no = _norm_gto_action(oracle.action)

    # 3) Engine == Oracle (mesma ação canônica)
    if ne == no:
        return DivergenceRecord(
            category='aligned',
            severity_score=_SEVERITY_BY_CATEGORY['aligned'],
            engine_best=engine_best, oracle_action=oracle.action,
            gto_action=gto_action, action_taken=action_taken,
            opp_cost_bb=oracle.opp_cost_bb,
            oracle_source=oracle.source, oracle_confidence=oracle.confidence,
            reasons=[f'norm({engine_best})=norm({oracle.action})={ne}'],
        )

    # Daqui pra baixo: ações diferentes.

    # 4) Alternativa aceitável: engine_best está nas alternativas do oráculo
    oracle_alts_norm = {_norm_gto_action(a) for a in (oracle.alternatives or [])}
    engine_alts_norm = {_norm_gto_action(a) for a in alts_engine}

    if ne in oracle_alts_norm:
        reasons.append(f'engine_best={engine_best} listado em oracle.alternatives')
        return DivergenceRecord(
            category='acceptable_alt',
            severity_score=_SEVERITY_BY_CATEGORY['acceptable_alt'],
            engine_best=engine_best, oracle_action=oracle.action,
            gto_action=gto_action, action_taken=action_taken,
            opp_cost_bb=oracle.opp_cost_bb,
            oracle_source=oracle.source, oracle_confidence=oracle.confidence,
            reasons=reasons,
        )

    # GTO declara mixed/correct -> tratamos como acceptable_alt mesmo sem o oracle listar
    if gto_label in ('gto_correct', 'gto_mixed'):
        reasons.append(f'gto_label={gto_label} sinaliza ação alternativa válida')
        return DivergenceRecord(
            category='acceptable_alt',
            severity_score=_SEVERITY_BY_CATEGORY['acceptable_alt'],
            engine_best=engine_best, oracle_action=oracle.action,
            gto_action=gto_action, action_taken=action_taken,
            opp_cost_bb=oracle.opp_cost_bb,
            oracle_source=oracle.source, oracle_confidence=oracle.confidence,
            reasons=reasons,
        )

    # 5) Decidir entre minor vs major
    #
    # Política:
    #   - gto_critical sempre promove a major (GTO é a verdade objetiva).
    #   - opp_cost >= 0.30bb sempre promove a major (custo direto em EV).
    #   - swap agressivo<->passivo promove a major SALVO quando:
    #       * gto_label=gto_minor_deviation (GTO já disse que é leve), OU
    #       * opp_cost_bb conhecido e < 0.15 (custo real é desprezível).
    is_major = False
    is_swap = _is_major_swap(ne, no)
    if is_swap:
        reasons.append(f'swap agressivo<->passivo: engine={ne} vs oracle={no}')
        is_major = True

    if gto_label == 'gto_minor_deviation':
        is_major = False
        reasons.append('gto_label=gto_minor_deviation cap em minor')
    if oracle.opp_cost_bb is not None and oracle.opp_cost_bb < 0.15:
        is_major = False
        reasons.append(f'opp_cost_bb={oracle.opp_cost_bb} < 0.15 cap em minor')

    if gto_label == 'gto_critical':
        is_major = True
        reasons.append('gto_label=gto_critical')
    if oracle.opp_cost_bb is not None and oracle.opp_cost_bb >= 0.30:
        is_major = True
        reasons.append(f'opp_cost_bb={oracle.opp_cost_bb} >= 0.30')

    if (not is_major
            and oracle.opp_cost_bb is None
            and oracle.confidence == 'low'):
        reasons.append('oracle.confidence=low + opp_cost desconhecido -> minor')

    if is_major:
        return DivergenceRecord(
            category='major_mismatch',
            severity_score=_severity_for_major(oracle.opp_cost_bb),
            engine_best=engine_best, oracle_action=oracle.action,
            gto_action=gto_action, action_taken=action_taken,
            opp_cost_bb=oracle.opp_cost_bb,
            oracle_source=oracle.source, oracle_confidence=oracle.confidence,
            reasons=reasons,
        )

    return DivergenceRecord(
        category='minor_mismatch',
        severity_score=_severity_for_minor(oracle.opp_cost_bb, gto_label),
        engine_best=engine_best, oracle_action=oracle.action,
        gto_action=gto_action, action_taken=action_taken,
        opp_cost_bb=oracle.opp_cost_bb,
        oracle_source=oracle.source, oracle_confidence=oracle.confidence,
        reasons=reasons or [f'engine={ne} oracle={no} sem severidade alta'],
    )


# -- Helpers -----------------------------------------------------------------

def _is_major_swap(ne: str, no: str) -> bool:
    """
    Major quando engine recomenda agressivo e oracle recomenda passivo (ou vice-versa).
    fold<->jam, fold<->raise, fold<->bet, check<->jam etc.
    """
    a_set = _AGGRESSIVE
    p_set = _PASSIVE
    if ne in p_set and no in a_set:
        return True
    if ne in a_set and no in p_set:
        return True
    return False


def _severity_for_major(opp_cost_bb: Optional[float]) -> float:
    base = _SEVERITY_BY_CATEGORY['major_mismatch']
    if opp_cost_bb is None:
        return base
    # Escala: 0.85 (sem opp) -> até 0.99 conforme opp_cost cresce
    return min(0.99, base + min(opp_cost_bb / 5.0, 0.14))


def _severity_for_minor(opp_cost_bb: Optional[float], gto_label: Optional[str]) -> float:
    base = _SEVERITY_BY_CATEGORY['minor_mismatch']
    bonus = 0.0
    if opp_cost_bb is not None:
        bonus += min(opp_cost_bb / 2.0, 0.20)
    if gto_label == 'gto_minor_deviation':
        bonus += 0.05
    return min(0.79, base + bonus)
