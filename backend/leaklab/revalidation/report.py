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

    payload = {
        'meta':     result.to_dict(),
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
