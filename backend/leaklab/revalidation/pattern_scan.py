"""
pattern_scan.py -- Scanner DETERMINÍSTICO de padrões suspeitos sobre as decisões
JÁ ARMAZENADAS (read-only, sem chamar o engine). Complementa o oracle/differ
(que recomputam) com checagens SQL baratas de integridade/coerência.

Cada check vira um `PatternFinding(key, title, count, sample_ids, severity,
remediation)`. Severidades: critical > high > medium > low > caveat.

Uso: `scan_patterns(scope) -> list[PatternFinding]` — `scope` é qualquer objeto
com `.user_id` e `.tournament_db_id` (None = todos), igual ao orchestrator.Scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from database.schema import get_conn

_SAMPLE = 20  # ids de amostra por padrão


@dataclass
class PatternFinding:
    key: str
    title: str
    count: int
    severity: str            # critical|high|medium|low|caveat
    remediation: str
    sample_ids: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'key': self.key, 'title': self.title, 'count': self.count,
            'severity': self.severity, 'remediation': self.remediation,
            'sample_ids': list(self.sample_ids),
        }


# Cada check: (key, title, severity, remediation, WHERE-extra sobre `d`).
# A condição assume FROM decisions d JOIN tournaments t ON t.id=d.tournament_id.
_CHECKS = [
    ("faces_3bet_leftover", "Squeeze/3-bet enfrentado a frio ainda com gto_label",
     "high", "fix_preflop_3bet_misclass.py --apply",
     "d.street='preflop' AND COALESCE(d.preflop_raises_faced,0) >= 2 "
     "AND COALESCE(d.is_3bet,0) = 0 AND d.gto_label IS NOT NULL AND d.gto_label != ''"),

    ("vs_position_null_facing", "gto_label setado mas vs_position desconhecido (facing>0)",
     "medium", "preencher vs_position + resync_preflop_all.py",
     "d.street='preflop' AND (d.vs_position IS NULL OR d.vs_position='' OR d.vs_position='unknown') "
     "AND d.gto_label IS NOT NULL AND d.gto_label != '' AND COALESCE(d.facing_bet,0) > 0"),

    ("label_gto_conflict", "label diz erro mas gto_label diz correto",
     "high", "reanalyze_all_labels.py --apply (reconciliacao _gto_label_cap)",
     "d.label IN ('small_mistake','clear_mistake') "
     "AND d.gto_label IN ('gto_correct','gto_mixed')"),

    ("gto_label_no_action", "gto_label setado sem gto_action",
     "medium", "resync_gto_actions.py / resync_preflop_all.py",
     "d.gto_label IS NOT NULL AND d.gto_label != '' "
     "AND (d.gto_action IS NULL OR d.gto_action='')"),

    ("impossible_raise", "best_action raise/jam enfrentando all-in (raise impossivel)",
     "critical", "reanalyze_all_labels.py --apply (guard facing all-in)",
     "d.best_action IN ('raise','jam') AND COALESCE(d.stack_bb,0) > 0 "
     "AND COALESCE(d.facing_bet,0) >= 0.95 * COALESCE(d.stack_bb,0)"),

    ("postflop_raise_no_bet", "raise postflop sem aposta anterior (deveria ser bet)",
     "high", "reanalyze_all_labels.py --apply (guard raise->bet)",
     "d.street != 'preflop' AND d.best_action='raise' AND COALESCE(d.facing_bet,0)=0"),

    ("multiway_highequity", "equity alta em pote multiway (>2 jogadores) sem ajuste",
     "medium", "reavaliar postflop (build_math_snapshot multiway)",
     "d.street != 'preflop' AND COALESCE(d.num_players,0) > 2 "
     "AND COALESCE(d.estimated_equity,0) > 0.55"),

    ("gto_critical_fold", "fold marcado como gto_critical (fold disciplinado virou critico)",
     "high", "fix_preflop_3bet_misclass.py --apply (overlap squeeze)",
     "d.gto_label='gto_critical' AND d.action_taken='fold'"),

    ("missing_hero_cards", "decisao sem hero_cards",
     "medium", "re-parsear via reanalyze_all_labels.py",
     "d.hero_cards IS NULL OR d.hero_cards=''"),

    ("postflop_mistake_no_gto", "erro postflop sem respaldo GTO (so heuristico)",
     "low", "fila do solver / aceitar NULL honesto",
     "d.street != 'preflop' AND d.label IN ('small_mistake','clear_mistake') "
     "AND (d.gto_label IS NULL OR d.gto_label='')"),
]


def _scope_where(scope) -> tuple[str, tuple]:
    uid = getattr(scope, 'user_id', None)
    tdb = getattr(scope, 'tournament_db_id', None)
    if tdb is not None:
        return "d.tournament_id = ?", (tdb,)
    if uid is not None:
        return "t.user_id = ?", (uid,)
    return "1=1", ()


def scan_patterns(scope) -> list[PatternFinding]:
    base_where, base_params = _scope_where(scope)
    conn = get_conn()
    out: list[PatternFinding] = []
    try:
        for key, title, severity, remediation, cond in _CHECKS:
            where = f"({base_where}) AND ({cond})"
            try:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM decisions d "
                    "JOIN tournaments t ON t.id = d.tournament_id "
                    f"WHERE {where}", base_params).fetchone()[0]
                ids = []
                if cnt:
                    rows = conn.execute(
                        "SELECT d.id FROM decisions d "
                        "JOIN tournaments t ON t.id = d.tournament_id "
                        f"WHERE {where} ORDER BY d.id LIMIT {_SAMPLE}",
                        base_params).fetchall()
                    ids = [int(dict(r)['id']) for r in rows]
            except Exception as e:
                # Coluna ausente / SQL não suportado → reporta como cobertura indisponível
                out.append(PatternFinding(key, title + " [check indisponivel]", -1,
                                          severity, f"{remediation} | erro: {str(e)[:60]}"))
                continue
            out.append(PatternFinding(key, title, int(cnt or 0), severity, remediation, ids))

        # Duplicate decisions (GROUP BY) — quebra o match LIMIT-1
        try:
            dup_rows = conn.execute(
                "SELECT d.hand_id, d.street FROM decisions d "
                "JOIN tournaments t ON t.id = d.tournament_id "
                f"WHERE {base_where} GROUP BY d.hand_id, d.street HAVING COUNT(*) > 1 "
                f"LIMIT {_SAMPLE}", base_params).fetchall()
            dup_cnt = conn.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM decisions d "
                "JOIN tournaments t ON t.id = d.tournament_id "
                f"WHERE {base_where} GROUP BY d.hand_id, d.street HAVING COUNT(*) > 1) x",
                base_params).fetchone()[0]
            samples = [f"{dict(r)['hand_id']}/{dict(r)['street']}" for r in dup_rows]
            out.append(PatternFinding(
                "duplicate_decisions", "Decisoes duplicadas (mesmo hand_id+street)",
                int(dup_cnt or 0), "high",
                "GAP: sem ferramenta de dedup — quebra o match LIMIT 1", samples))
        except Exception as e:
            out.append(PatternFinding("duplicate_decisions",
                                      "Decisoes duplicadas [check indisponivel]", -1,
                                      "high", f"erro: {str(e)[:60]}"))

        # PKO com ranges Classic — CAVEAT (aproximacao documentada, nao divergencia)
        try:
            pko_cnt = conn.execute(
                "SELECT COUNT(*) FROM decisions d "
                "JOIN tournaments t ON t.id = d.tournament_id "
                f"WHERE ({base_where}) AND COALESCE(t.is_pko,0)=1", base_params).fetchone()[0]
        except Exception:
            pko_cnt = 0
        out.append(PatternFinding(
            "pko_classic_ranges", "PKO avaliado com ranges Classic (aproximacao)",
            int(pko_cnt or 0), "caveat",
            "nenhuma — aproximacao documentada (ICM/-2pp); PKO nativo depende de upgrade GW"))
    finally:
        conn.close()
    return out
