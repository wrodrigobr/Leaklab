"""
orchestrator.py -- Varre torneios, compara engine vs oracle, persiste findings.

Não modifica nenhuma decisão existente: só lê tournaments.raw_text e grava
linhas novas em revalidation_runs / revalidation_findings.

Ponto de entrada:
    revalidate(scope=Scope.all(), with_llm_judge=False, llm_budget=50,
               persist=True, output_dir=None) -> RevalidationResult
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from database.schema import get_conn
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.revalidation.differ import DivergenceRecord, classify
from leaklab.revalidation.oracle import OracleDecision, decide

log = logging.getLogger(__name__)


# -- Tipos --------------------------------------------------------------------

@dataclass(frozen=True)
class Scope:
    """Filtro de torneios a varrer."""
    user_id: Optional[int] = None
    tournament_db_id: Optional[int] = None

    @classmethod
    def all(cls) -> 'Scope':
        return cls()

    @classmethod
    def for_user(cls, user_id: int) -> 'Scope':
        return cls(user_id=user_id)

    @classmethod
    def for_tournament(cls, tournament_db_id: int) -> 'Scope':
        return cls(tournament_db_id=tournament_db_id)

    def label(self) -> str:
        if self.tournament_db_id is not None:
            return f'tournament:{self.tournament_db_id}'
        if self.user_id is not None:
            return f'user:{self.user_id}'
        return 'all'


@dataclass
class RevalidationResult:
    run_id: Optional[int]
    scope: str
    total_tournaments: int
    total_hands: int
    total_decisions: int
    category_counts: dict[str, int]
    findings: list[dict] = field(default_factory=list)
    elapsed_sec: float = 0.0
    errors: list[dict] = field(default_factory=list)
    llm_judge_used: bool = False

    def to_dict(self) -> dict:
        return {
            'run_id':            self.run_id,
            'scope':             self.scope,
            'total_tournaments': self.total_tournaments,
            'total_hands':       self.total_hands,
            'total_decisions':   self.total_decisions,
            'category_counts':   dict(self.category_counts),
            'elapsed_sec':       round(self.elapsed_sec, 2),
            'errors':            list(self.errors),
            'llm_judge_used':    self.llm_judge_used,
        }


# -- Entrypoint principal -----------------------------------------------------

def revalidate(scope: Scope = Scope.all(),
               with_llm_judge: bool = False,
               llm_budget: int = 50,
               persist: bool = True,
               output_dir: Optional[str] = None,
               notes: Optional[str] = None) -> RevalidationResult:
    """
    Roda a varredura. Quando persist=True, grava em revalidation_runs/findings.
    Quando output_dir é dado, escreve report.md + report.json no diretório.
    """
    t0 = time.time()
    tournaments = _fetch_tournaments(scope)

    findings: list[dict] = []
    category_counts: dict[str, int] = defaultdict(int)
    total_hands = total_decisions = 0
    errors: list[dict] = []

    for trow in tournaments:
        tid = trow['id']
        raw = trow.get('raw_text')
        if not raw:
            continue
        try:
            hands = parse_hand_history(raw)
        except Exception as e:
            errors.append({'tournament_db_id': tid, 'error': f'parse: {e}'})
            continue

        for hand in hands:
            total_hands += 1
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception as e:
                errors.append({
                    'tournament_db_id': tid, 'hand_id': hand.hand_id,
                    'error': f'build_decision_inputs: {e}',
                })
                continue
            for idx, di in enumerate(dis):
                try:
                    rec = _process_decision(tid, hand.hand_id, idx, di)
                except Exception as e:
                    errors.append({
                        'tournament_db_id': tid, 'hand_id': hand.hand_id,
                        'decision_index': idx, 'error': f'evaluate: {e}',
                    })
                    continue
                findings.append(rec)
                category_counts[rec['category']] += 1
                total_decisions += 1

    # LLM judge opcional sobre os top-N findings disputados
    llm_used = False
    if with_llm_judge and llm_budget > 0 and findings:
        try:
            from leaklab.revalidation.llm_judge import judge_findings
            llm_used = judge_findings(findings, budget=llm_budget) > 0
        except Exception as e:
            log.warning('llm_judge failed: %s', e)
            errors.append({'stage': 'llm_judge', 'error': str(e)})

    run_id = None
    if persist:
        run_id = _persist_run(scope, category_counts, findings,
                              total_tournaments=len(tournaments),
                              total_hands=total_hands,
                              total_decisions=total_decisions,
                              llm_used=llm_used, notes=notes)

    result = RevalidationResult(
        run_id=run_id,
        scope=scope.label(),
        total_tournaments=len(tournaments),
        total_hands=total_hands,
        total_decisions=total_decisions,
        category_counts=dict(category_counts),
        findings=findings,
        elapsed_sec=time.time() - t0,
        errors=errors,
        llm_judge_used=llm_used,
    )

    if output_dir:
        from leaklab.revalidation import report as _report
        _report.write_outputs(result, output_dir)

    return result


# -- Processamento por decisão ------------------------------------------------

def _process_decision(tournament_db_id: int, hand_id: str, idx: int,
                      di: dict) -> dict:
    engine_result = evaluate_decision(di)
    oracle_rec    = decide(di)
    gto_info      = engine_result.get('gto') or {}

    div: DivergenceRecord = classify(
        engine_result=engine_result,
        oracle=oracle_rec,
        gto_info=gto_info,
        action_taken=di.get('player_action'),
        street=di.get('street'),
    )

    spot = di.get('spot') or {}
    return {
        'tournament_db_id': tournament_db_id,
        'hand_id':          hand_id,
        'decision_index':   idx,
        'street':           di.get('street'),
        'position':         spot.get('position'),
        'action_taken':     di.get('player_action'),
        'engine_best':      div.engine_best,
        'oracle_action':    div.oracle_action,
        'gto_action':       div.gto_action,
        'category':         div.category,
        'severity_score':   div.severity_score,
        'opp_cost_bb':      div.opp_cost_bb,
        'oracle_source':    div.oracle_source,
        'oracle_confidence': div.oracle_confidence,
        'reasons':          div.reasons,
        'oracle':           oracle_rec.to_dict(),
    }


# -- Fetch de torneios --------------------------------------------------------

def _fetch_tournaments(scope: Scope) -> list[dict]:
    conn = get_conn()
    try:
        params: tuple = ()
        where = "raw_text IS NOT NULL"
        if scope.tournament_db_id is not None:
            where += " AND id = ?"
            params = (scope.tournament_db_id,)
        elif scope.user_id is not None:
            where += " AND user_id = ?"
            params = (scope.user_id,)
        sql = f"SELECT id, user_id, hero, raw_text, site FROM tournaments WHERE {where} ORDER BY id"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# -- Persistência -------------------------------------------------------------

def _persist_run(scope: Scope, category_counts: dict[str, int],
                 findings: list[dict], *,
                 total_tournaments: int, total_hands: int, total_decisions: int,
                 llm_used: bool, notes: Optional[str]) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO revalidation_runs "
            "(scope, total_tournaments, total_hands, total_decisions, "
            " category_counts_json, llm_judge_used, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (scope.label(), total_tournaments, total_hands, total_decisions,
             json.dumps(dict(category_counts), sort_keys=True),
             1 if llm_used else 0, notes),
        )
        run_id = _lastrowid(conn, cur, 'revalidation_runs')
        if findings:
            rows = []
            for f in findings:
                rows.append((
                    run_id,
                    f.get('tournament_db_id'),
                    f.get('hand_id'),
                    f.get('decision_index'),
                    f.get('street'),
                    f.get('position'),
                    f.get('action_taken'),
                    f.get('engine_best'),
                    f.get('gto_action'),
                    f.get('oracle_action'),
                    f.get('category'),
                    f.get('severity_score'),
                    f.get('opp_cost_bb'),
                    f.get('oracle_source'),
                    f.get('oracle_confidence'),
                    json.dumps(f.get('reasons') or [], sort_keys=True),
                    f.get('llm_verdict'),
                    f.get('llm_reasoning'),
                ))
            conn.executemany(
                "INSERT INTO revalidation_findings "
                "(run_id, tournament_db_id, hand_id, decision_index, street, "
                " position, action_taken, engine_best, gto_action, oracle_action, "
                " category, severity_score, opp_cost_bb, oracle_source, "
                " oracle_confidence, reasons_json, llm_verdict, llm_reasoning) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        conn.commit()
        return int(run_id)
    finally:
        conn.close()


def _lastrowid(conn, cur, table: str) -> int:
    """Funciona em SQLite (lastrowid no cursor) e PG (SELECT max via id)."""
    val = getattr(cur, 'lastrowid', None)
    if val:
        return int(val)
    # Fallback Postgres
    row = conn.execute(f"SELECT MAX(id) AS mx FROM {table}").fetchone()
    if row:
        return int(dict(row).get('mx') or 0)
    return 0
