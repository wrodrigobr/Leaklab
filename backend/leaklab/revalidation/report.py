"""
report.py -- Formata RevalidationResult em Markdown + JSON para auditoria humana.

Gera dois arquivos por run em output_dir/:
  revalidation_run_<run_id>.json   -- payload completo (findings + counts)
  revalidation_run_<run_id>.md     -- relatório legível
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Optional

from leaklab.revalidation.orchestrator import RevalidationResult


_CATEGORY_ORDER = [
    'major_mismatch',
    'minor_mismatch',
    'no_oracle_data',
    'engine_no_data',
    'acceptable_alt',
    'aligned',
]


def write_outputs(result: RevalidationResult, output_dir: str) -> dict:
    """Escreve report.md + report.json. Retorna paths."""
    os.makedirs(output_dir, exist_ok=True)
    suffix = result.run_id if result.run_id is not None else 'unsaved'
    json_path = os.path.join(output_dir, f'revalidation_run_{suffix}.json')
    md_path   = os.path.join(output_dir, f'revalidation_run_{suffix}.md')

    meta = result.to_dict()
    meta['drift_summary'] = _drift_summary(result.findings)
    payload = {
        'meta':     meta,
        'findings': result.findings,
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(render_markdown(result))
    return {'json': json_path, 'markdown': md_path}


def render_markdown(result: RevalidationResult) -> str:
    """Sumário executivo + breakdowns + top findings por severidade."""
    lines: list[str] = []
    counts = result.category_counts
    total = result.total_decisions or 0

    lines.append(f"# Revalidação -- run #{result.run_id} ({result.scope})")
    lines.append('')
    lines.append(f"- Torneios varridos: **{result.total_tournaments}**")
    lines.append(f"- Mãos processadas: **{result.total_hands}**")
    lines.append(f"- Decisões avaliadas: **{result.total_decisions}**")
    lines.append(f"- Tempo: **{result.elapsed_sec:.1f}s**")
    if result.llm_judge_used:
        lines.append('- LLM judge: **ativo**')
    if result.errors:
        lines.append(f"- Erros: **{len(result.errors)}** (ver JSON)")
    lines.append('')

    lines.append('## Distribuição por categoria')
    lines.append('')
    lines.append('| Categoria | Total | % |')
    lines.append('|---|---:|---:|')
    for cat in _CATEGORY_ORDER:
        n = counts.get(cat, 0)
        pct = (n / total * 100.0) if total else 0.0
        lines.append(f"| `{cat}` | {n} | {pct:.1f}% |")
    lines.append('')

    by_street = _aggregate_by(result.findings, 'street')
    by_position = _aggregate_by(result.findings, 'position')
    by_tournament = _aggregate_by(result.findings, 'tournament_db_id')

    lines.append('## Por street')
    lines.append('')
    lines.append(_render_breakdown_table(by_street, ['major_mismatch', 'minor_mismatch']))
    lines.append('')

    lines.append('## Por posição')
    lines.append('')
    lines.append(_render_breakdown_table(by_position, ['major_mismatch', 'minor_mismatch']))
    lines.append('')

    lines.append('## Top 10 torneios com mais major_mismatch')
    lines.append('')
    sorted_tids = sorted(
        by_tournament.items(),
        key=lambda kv: kv[1].get('major_mismatch', 0),
        reverse=True,
    )[:10]
    if sorted_tids:
        lines.append('| Torneio (db id) | major | minor | no_data | total |')
        lines.append('|---|---:|---:|---:|---:|')
        for tid, c in sorted_tids:
            tot = sum(c.values())
            lines.append(
                f"| `{tid}` | {c.get('major_mismatch', 0)} | "
                f"{c.get('minor_mismatch', 0)} | {c.get('no_oracle_data', 0)} | {tot} |"
            )
    else:
        lines.append('_sem torneios analisados_')
    lines.append('')

    lines.append('## Top 50 findings por severidade')
    lines.append('')
    top = sorted(result.findings, key=lambda r: r.get('severity_score') or 0.0, reverse=True)[:50]
    if top:
        for i, r in enumerate(top, 1):
            tid = r.get('tournament_db_id', '?')
            hid = r.get('hand_id', '?')
            lines.append(
                f"### {i}. [{r.get('category')}] severity={r.get('severity_score', 0):.3f}"
                f" -- tid={tid} hand={hid} {r.get('street')}/{r.get('position')}"
            )
            lines.append(
                f"- tomou=`{r.get('action_taken')}` engine=`{r.get('engine_best')}`"
                f" oracle=`{r.get('oracle_action')}` gto=`{r.get('gto_action')}`"
            )
            if r.get('opp_cost_bb') is not None:
                lines.append(f"- opp_cost: **{r['opp_cost_bb']:+.2f}bb**")
            src = r.get('oracle_source') or '?'
            conf = r.get('oracle_confidence') or '?'
            lines.append(f"- oracle: `{src}` (confidence={conf})")
            reasons = r.get('reasons') or []
            if reasons:
                lines.append('- razões: ' + '; '.join(str(x) for x in reasons))
            if r.get('llm_verdict'):
                lines.append(f"- llm: **{r['llm_verdict']}** -- {r.get('llm_reasoning', '')[:200]}")
            lines.append('')
    else:
        lines.append('_sem findings_')
    lines.append('')

    # Sugestões: spots sem cobertura GTO agrupados (priorizar para enqueue de solver)
    no_data = [r for r in result.findings if r.get('category') == 'no_oracle_data']
    if no_data:
        by_spot = Counter((r.get('street'), r.get('position')) for r in no_data)
        lines.append('## Spots sem cobertura GTO (top 20)')
        lines.append('')
        lines.append('| Street | Posição | Ocorrências |')
        lines.append('|---|---|---:|')
        for (street, pos), n in by_spot.most_common(20):
            lines.append(f"| {street} | {pos} | {n} |")
        lines.append('')

    # Seções novas: drift vs armazenado, padrões suspeitos, plano de correção.
    lines.extend(_render_drift_section(result))
    lines.extend(_render_pattern_section(result))
    lines.extend(_render_correction_plan(result))

    return '\n'.join(lines)


# -- Helpers ------------------------------------------------------------------

def _aggregate_by(findings: list[dict], key: str) -> dict:
    out: dict = defaultdict(lambda: defaultdict(int))
    for r in findings:
        k = r.get(key) if r.get(key) is not None else '?'
        out[k][r.get('category')] += 1
    return {k: dict(v) for k, v in out.items()}


def _render_breakdown_table(agg: dict, categories: list[str]) -> str:
    if not agg:
        return '_sem dados_'
    header = '| key | ' + ' | '.join(categories) + ' | total |'
    sep    = '|---|' + ''.join('---:|' for _ in categories) + '---:|'
    rows = [header, sep]
    for key, c in sorted(agg.items(), key=lambda kv: sum(kv[1].values()), reverse=True):
        parts = [str(c.get(cat, 0)) for cat in categories]
        rows.append(f"| {key} | " + ' | '.join(parts) + f" | {sum(c.values())} |")
    return '\n'.join(rows)


# -- Seção A: Drift vs verdicto armazenado ------------------------------------

def _drift_summary(findings: list[dict]) -> dict:
    matched = [f for f in findings if f.get('stored_found')]
    drifted = [f for f in matched if f.get('drift')]
    by_field: Counter = Counter()
    for f in drifted:
        for fld in (f.get('drift_fields') or []):
            by_field[fld] += 1
    return {
        'stored_found':   len(matched),
        'not_found':      sum(1 for f in findings if not f.get('stored_found')),
        'ambiguous':      sum(1 for f in findings if f.get('stored_ambiguous')),
        'drifted':        len(drifted),
        'by_field':       dict(by_field),
    }


def _render_drift_section(result: RevalidationResult) -> list[str]:
    s = _drift_summary(result.findings)
    lines = ['## Drift vs verdicto armazenado', '']
    lines.append(f"- Decisões casadas com o banco: **{s['stored_found']}** "
                 f"(não encontradas: {s['not_found']}, ambíguas: {s['ambiguous']})")
    lines.append(f"- **Com divergência (drift): {s['drifted']}** — o recompute fresco "
                 f"difere do que está armazenado (o que produção serviria).")
    if s['by_field']:
        lines.append('')
        lines.append('| Campo divergente | Ocorrências |')
        lines.append('|---|---:|')
        for fld, n in sorted(s['by_field'].items(), key=lambda kv: kv[1], reverse=True):
            tag = ' ⚠️ stale (reanalyze NÃO corrige)' if fld == 'gto_label:stale->NULL' else ''
            lines.append(f"| `{fld}`{tag} | {n} |")
    drifted = [f for f in result.findings if f.get('drift')]
    if drifted:
        lines.append('')
        lines.append('### Top 30 drifts por severidade')
        lines.append('')
        top = sorted(drifted, key=lambda r: r.get('severity_score') or 0.0, reverse=True)[:30]
        for r in top:
            chgs = []
            for fld in (r.get('drift_fields') or []):
                if fld == 'gto_label:stale->NULL':
                    continue
                chgs.append(f"{fld}: `{r.get('stored_' + _stored_key(fld))}`→`{r.get('fresh_' + _fresh_key(fld))}`")
            stale = ' [gto stale→NULL]' if 'gto_label:stale->NULL' in (r.get('drift_fields') or []) else ''
            lines.append(
                f"- tid={r.get('tournament_db_id')} hand={r.get('hand_id')} "
                f"{r.get('street')}/{r.get('position')} — " + '; '.join(chgs) + stale)
    lines.append('')
    return lines


def _stored_key(fld: str) -> str:
    return {'best_action': 'best', 'gto_label': 'gto_label',
            'gto_action': 'gto_action', 'label': 'label'}.get(fld, fld)


def _fresh_key(fld: str) -> str:
    return {'best_action': 'best', 'gto_label': 'gto_label',
            'gto_action': 'gto_action', 'label': 'label'}.get(fld, fld)


# -- Seção B: Padrões suspeitos -----------------------------------------------

_SEV_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'caveat': 4}


def _render_pattern_section(result: RevalidationResult) -> list[str]:
    pf = result.pattern_findings or []
    lines = ['## Padrões suspeitos (scan determinístico)', '']
    if not pf:
        lines.append('_scanner não executado_')
        lines.append('')
        return lines
    lines.append('| Padrão | Severidade | Count | Amostra (ids) | Remediação |')
    lines.append('|---|---|---:|---|---|')
    for p in sorted(pf, key=lambda x: (_SEV_ORDER.get(x.get('severity'), 9), -(x.get('count') or 0))):
        sample = ', '.join(str(x) for x in (p.get('sample_ids') or [])[:8])
        lines.append(f"| `{p.get('key')}` — {p.get('title')} | {p.get('severity')} "
                     f"| {p.get('count')} | {sample} | {p.get('remediation')} |")
    lines.append('')
    return lines


# -- Seção C: Plano de correção -----------------------------------------------

_CORRECTION_PLAN = [
    ('major_mismatch', 'revisão manual → reanalyze_all_labels.py --apply'),
    ('minor_mismatch', 'aceitar; reanalyze_all_labels.py se sistemático'),
    ('no_oracle_data', 'fila do solver / aceitar NULL honesto (não é bug)'),
    ('internal_inconsistency', 'reanalyze_all_labels.py --apply'),
    ('drift:label / best_action', 'reanalyze_all_labels.py --apply'),
    ('drift:gto_label / gto_action (coberto)', 'resync_preflop_all.py + resync_gto_actions.py'),
    ('drift:gto_label:stale->NULL', '⚠️ GAP — fix_preflop_3bet_misclass.py (squeeze) cobre só parte; '
                                    'falta passada genérica "recompute → NULL quando sem cobertura"'),
    ('faces_3bet_leftover / gto_critical_fold', 'fix_preflop_3bet_misclass.py --apply'),
    ('impossible_raise / postflop_raise_no_bet', 'reanalyze_all_labels.py --apply (guards já existem)'),
    ('label_gto_conflict', 'reanalyze_all_labels.py --apply (_gto_label_cap)'),
    ('gto_label_no_action', 'resync_gto_actions.py / resync_preflop_all.py'),
    ('vs_position_null_facing', 'preencher vs_position + resync_preflop_all.py'),
    ('multiway_highequity', 'reavaliar postflop (build_math_snapshot)'),
    ('missing_hero_cards', 're-parsear via reanalyze_all_labels.py'),
    ('postflop_mistake_no_gto', 'fila do solver / aceitar NULL'),
    ('duplicate_decisions', '⚠️ GAP — não há ferramenta de dedup; quebra o match LIMIT 1'),
    ('pko_classic_ranges', 'nenhuma — caveat (PKO nativo depende de upgrade GW)'),
]


def _render_correction_plan(result: RevalidationResult) -> list[str]:
    lines = ['## Plano de correção (por categoria)', '']
    lines.append('> Read-only: nada foi aplicado. Cada divergência/padrão mapeia para a '
                 'ferramenta de remediação. **2 gaps** sinalizados (⚠️).')
    lines.append('')
    lines.append('| Categoria / Padrão | Remediação |')
    lines.append('|---|---|')
    for cat, rem in _CORRECTION_PLAN:
        lines.append(f"| `{cat}` | {rem} |")
    lines.append('')
    return lines
