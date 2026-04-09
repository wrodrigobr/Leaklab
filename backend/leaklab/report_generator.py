"""
report_generator.py — Sprint 3
Gera relatório HTML de auditoria a partir dos resultados do pipeline.
Sem dependências externas — HTML/CSS/JS puro gerado pelo Python.
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from typing import List, Dict
from .session_metrics import build_session_metrics
from .leak_correlator import correlate_leaks


LABEL_COLOR = {
    'standard':     '#22c55e',
    'marginal':     '#f59e0b',
    'small_mistake':'#f97316',
    'clear_mistake':'#ef4444',
}

LABEL_BG = {
    'standard':     '#f0fdf4',
    'marginal':     '#fffbeb',
    'small_mistake':'#fff7ed',
    'clear_mistake':'#fef2f2',
}

ICM_COLOR = {
    'low':    '#6b7280',
    'medium': '#f59e0b',
    'high':   '#ef4444',
}


def generate_report(results: List[dict],
                    hand_results: Dict[str, dict],
                    output_path: str,
                    hero: str = 'Hero',
                    tournament_id: str = '') -> str:
    metrics = build_session_metrics(results)
    leaks   = correlate_leaks(results)
    worst   = sorted(results,
                     key=lambda x: x['evaluation']['mistakeScore'],
                     reverse=True)[:20]

    html = _build_html(metrics, leaks, worst, results, hand_results, hero, tournament_id)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


# ── Seções HTML ───────────────────────────────────────────────────────────────

def _build_html(metrics, leaks, worst, results, hand_results, hero, tournament_id):
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    dist = metrics['label_distribution']
    pct  = metrics['label_pct']

    # Dados para o gráfico de barras (street breakdown)
    streets = ['preflop', 'flop', 'turn', 'river']
    street_data = metrics.get('by_street', {})

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GapHunter — Relatório de Auditoria</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}

  /* Header */
  .header {{ background: linear-gradient(135deg, #1e293b, #0f172a);
             border: 1px solid #334155; border-radius: 12px;
             padding: 28px 32px; margin-bottom: 24px; }}
  .header h1 {{ font-size: 1.8rem; font-weight: 700; color: #f8fafc;
                letter-spacing: -0.5px; }}
  .header .sub {{ color: #94a3b8; font-size: 0.9rem; margin-top: 4px; }}
  .header .meta {{ display: flex; gap: 24px; margin-top: 16px; flex-wrap: wrap; }}
  .meta-item {{ background: #1e293b; border: 1px solid #334155;
                border-radius: 8px; padding: 8px 14px; font-size: 0.85rem; }}
  .meta-item .val {{ font-weight: 700; color: #f8fafc; font-size: 1.1rem; }}

  /* Cards de métricas */
  .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr);
                   gap: 16px; margin-bottom: 24px; }}
  @media(max-width:800px) {{ .metrics-grid {{ grid-template-columns: repeat(2,1fr); }} }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155;
                  border-radius: 12px; padding: 20px; text-align: center; }}
  .metric-card .label {{ font-size: 0.8rem; color: #94a3b8; text-transform: uppercase;
                          letter-spacing: 0.05em; margin-bottom: 8px; }}
  .metric-card .value {{ font-size: 2rem; font-weight: 700; }}
  .metric-card .pct {{ font-size: 0.85rem; color: #94a3b8; margin-top: 2px; }}

  /* Seção */
  .section {{ background: #1e293b; border: 1px solid #334155;
              border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
  .section h2 {{ font-size: 1.1rem; font-weight: 600; color: #f8fafc;
                 margin-bottom: 20px; padding-bottom: 12px;
                 border-bottom: 1px solid #334155; }}

  /* Barra de progresso */
  .bar-wrap {{ margin-bottom: 14px; }}
  .bar-label {{ display: flex; justify-content: space-between;
                font-size: 0.85rem; margin-bottom: 5px; }}
  .bar-track {{ background: #0f172a; border-radius: 6px; height: 10px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 6px; transition: width 0.3s; }}

  /* Badge de label */
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px;
            font-size: 0.78rem; font-weight: 600; }}

  /* Tabela de erros */
  .error-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  .error-table th {{ text-align: left; padding: 10px 12px; color: #64748b;
                     font-weight: 600; font-size: 0.78rem; text-transform: uppercase;
                     border-bottom: 1px solid #334155; }}
  .error-table td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
  .error-table tr:hover td {{ background: #0f172a; }}

  /* Leak grid */
  .leak-grid {{ display: grid; grid-template-columns: repeat(3, 1fr);
                gap: 16px; }}
  @media(max-width:800px) {{ .leak-grid {{ grid-template-columns: 1fr; }} }}
  .leak-card {{ background: #0f172a; border: 1px solid #334155;
                border-radius: 8px; padding: 16px; }}
  .leak-card h3 {{ font-size: 0.85rem; color: #94a3b8; text-transform: uppercase;
                   letter-spacing: 0.05em; margin-bottom: 12px; }}
  .leak-row {{ display: flex; justify-content: space-between; align-items: center;
               padding: 6px 0; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }}
  .leak-row:last-child {{ border-bottom: none; }}
  .leak-key {{ color: #e2e8f0; font-weight: 500; }}
  .leak-val {{ color: #94a3b8; }}
  .heat {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%;
           margin-right: 6px; }}

  /* Street breakdown */
  .street-grid {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; }}
  @media(max-width:800px) {{ .street-grid {{ grid-template-columns: repeat(2,1fr); }} }}
  .street-card {{ background: #0f172a; border: 1px solid #334155;
                  border-radius: 8px; padding: 14px; }}
  .street-card h3 {{ font-size: 0.8rem; color: #94a3b8; text-transform: uppercase;
                     letter-spacing: 0.05em; margin-bottom: 10px; }}
  .street-stat {{ display: flex; justify-content: space-between;
                  font-size: 0.82rem; padding: 3px 0; }}

  /* MTT insight */
  .insight-box {{ background: #0f172a; border-left: 3px solid #3b82f6;
                  border-radius: 0 8px 8px 0; padding: 12px 16px;
                  font-size: 0.88rem; color: #cbd5e1; margin-bottom: 10px; }}

  /* Score pill */
  .score-pill {{ display: inline-block; padding: 2px 8px; border-radius: 20px;
                 font-size: 0.8rem; font-weight: 700;
                 background: #0f172a; border: 1px solid #334155; }}

  .icm-badge {{ display: inline-block; padding: 1px 8px; border-radius: 4px;
                font-size: 0.75rem; font-weight: 600; }}

  footer {{ text-align: center; color: #475569; font-size: 0.8rem;
            padding: 24px 0 8px; }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>🎯 GapHunter — Relatório de Auditoria</h1>
    <div class="sub">Análise de decisões MTT · Motor v1.1</div>
    <div class="meta">
      <div class="meta-item">Hero <div class="val">{hero}</div></div>
      <div class="meta-item">Torneio <div class="val">{tournament_id or 'N/A'}</div></div>
      <div class="meta-item">Gerado em <div class="val">{now}</div></div>
      <div class="meta-item">Mãos <div class="val">{metrics['total_hands']}</div></div>
      <div class="meta-item">Decisões <div class="val">{metrics['total_decisions']}</div></div>
      <div class="meta-item">Score médio <div class="val">{metrics['avg_mistake_score']:.4f}</div></div>
    </div>
  </div>

  <!-- Distribuição de labels -->
  <div class="metrics-grid">
    {_metric_card('Standard',      dist.get('standard',0),      pct.get('standard',0),      LABEL_COLOR['standard'])}
    {_metric_card('Marginal',      dist.get('marginal',0),      pct.get('marginal',0),      LABEL_COLOR['marginal'])}
    {_metric_card('Small Mistake', dist.get('small_mistake',0), pct.get('small_mistake',0), LABEL_COLOR['small_mistake'])}
    {_metric_card('Clear Mistake', dist.get('clear_mistake',0), pct.get('clear_mistake',0), LABEL_COLOR['clear_mistake'])}
  </div>

  <!-- Breakdown por street -->
  <div class="section">
    <h2>📊 Distribuição por Street</h2>
    <div class="street-grid">
      {_street_cards(street_data, streets)}
    </div>
  </div>

  <!-- Barra de distribuição -->
  <div class="section">
    <h2>📈 Qualidade das Decisões</h2>
    {_bar('Standard',      pct.get('standard',0),      LABEL_COLOR['standard'])}
    {_bar('Marginal',      pct.get('marginal',0),      LABEL_COLOR['marginal'])}
    {_bar('Small Mistake', pct.get('small_mistake',0), LABEL_COLOR['small_mistake'])}
    {_bar('Clear Mistake', pct.get('clear_mistake',0), LABEL_COLOR['clear_mistake'])}
    <div style="margin-top:16px; padding:12px; background:#0f172a; border-radius:8px; font-size:0.85rem; color:#94a3b8;">
      <b style="color:#f8fafc">Referência MTT saudável:</b>
      Standard 60–80% · Marginal 10–20% · Small Mistake 5–15% · Clear Mistake 2–8%
    </div>
  </div>

  <!-- Leaks -->
  <div class="section">
    <h2>🔍 Análise de Leaks</h2>
    <div class="leak-grid">
      {_leak_card('Por Ação',         leaks.get('by_action', {}), 8)}
      {_leak_card('Por Street',       leaks.get('by_street', {}), 8)}
      {_leak_card('Street × Ação',   leaks.get('by_street_action', {}), 8)}
    </div>
  </div>

  <!-- Top 20 erros -->
  <div class="section">
    <h2>⚠️ Top 20 Decisões Mais Críticas</h2>
    <table class="error-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Mão</th>
          <th>Street</th>
          <th>Cartas</th>
          <th>Tomou</th>
          <th>Esperado</th>
          <th>Label</th>
          <th>Score</th>
          <th>M</th>
          <th>ICM</th>
        </tr>
      </thead>
      <tbody>
        {_error_rows(worst)}
      </tbody>
    </table>
  </div>

  <!-- Insights MTT -->
  <div class="section">
    <h2>🏆 Insights de Contexto MTT</h2>
    {_mtt_insights(results)}
  </div>

</div>
<footer>GapHunter v1.1 · Análise determinística de poker MTT · {now}</footer>
</body>
</html>"""


# ── Componentes ───────────────────────────────────────────────────────────────

def _metric_card(label, count, pct, color):
    return f"""<div class="metric-card">
      <div class="label">{label}</div>
      <div class="value" style="color:{color}">{count}</div>
      <div class="pct">{pct:.1f}%</div>
    </div>"""


def _bar(label, pct, color):
    return f"""<div class="bar-wrap">
      <div class="bar-label">
        <span>{label}</span>
        <span style="color:{color};font-weight:600">{pct:.1f}%</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width:{min(pct,100):.1f}%;background:{color}"></div>
      </div>
    </div>"""


def _street_cards(street_data, streets):
    cards = []
    for street in streets:
        d = street_data.get(street, {})
        if not d:
            continue
        total = sum(d.values())
        def _row(lbl, cnt, tot):
            c = LABEL_COLOR.get(lbl, '#94a3b8')
            return (f'<div class="street-stat">'
                    f'<span style="color:{c}">{lbl}</span>'
                    f'<span>{cnt} ({cnt/tot*100:.0f}%)</span></div>')
        rows = ''.join(_row(lbl, cnt, total)
                       for lbl, cnt in sorted(d.items(), key=lambda x: x[1], reverse=True))
        cards.append(f"""<div class="street-card">
          <h3>{street}</h3>
          <div style="font-size:0.78rem;color:#64748b;margin-bottom:8px">{total} decisões</div>
          {rows}
        </div>""")
    return '\n'.join(cards)


def _leak_card(title, data, max_rows):
    if not data:
        return f'<div class="leak-card"><h3>{title}</h3><div style="color:#64748b">Sem dados</div></div>'

    sorted_items = sorted(data.items(), key=lambda x: x[1]['avg_weight'], reverse=True)[:max_rows]
    rows = []
    for key, v in sorted_items:
        if v['count'] < 2:
            continue
        aw = v['avg_weight']
        if aw >= 0.55:
            color = '#ef4444'
        elif aw >= 0.3:
            color = '#f97316'
        elif aw >= 0.15:
            color = '#f59e0b'
        else:
            color = '#22c55e'
        rows.append(
            f'<div class="leak-row">'
            f'<span class="leak-key"><span class="heat" style="background:{color}"></span>{key}</span>'
            f'<span class="leak-val">avg={aw:.3f} · n={v["count"]}</span>'
            f'</div>'
        )

    return f"""<div class="leak-card">
      <h3>{title}</h3>
      {''.join(rows) or '<div style="color:#64748b;font-size:0.85rem">Nenhum leak significativo</div>'}
    </div>"""


def _error_rows(worst):
    rows = []
    for i, r in enumerate(worst, 1):
        label  = r['evaluation']['label']
        score  = r['evaluation']['mistakeScore']
        ctx    = r.get('context', {})
        icm    = ctx.get('icmPressure', '?')
        m      = ctx.get('mRatio', '?')
        cards  = r.get('hero_cards', '?')
        hand_id = r.get('handId', r.get('hand_id_full', '?'))
        short_id = str(hand_id)[-7:]

        color  = LABEL_COLOR.get(label, '#94a3b8')
        bg     = LABEL_BG.get(label, '#1e293b')
        icm_c  = ICM_COLOR.get(icm, '#6b7280')

        rows.append(f"""<tr>
          <td style="color:#64748b">{i}</td>
          <td style="font-family:monospace;font-size:0.8rem">#{short_id}</td>
          <td>{r.get('street','?')}</td>
          <td style="font-family:monospace;color:#f8fafc">{cards}</td>
          <td style="color:#ef4444;font-weight:600">{r.get('actionTaken','?')}</td>
          <td style="color:#22c55e">{r.get('bestAction','?')}</td>
          <td><span class="badge" style="color:{color};background:{bg}">{label}</span></td>
          <td><span class="score-pill">{score:.3f}</span></td>
          <td style="color:#94a3b8">{m}</td>
          <td><span class="icm-badge" style="color:{icm_c};border:1px solid {icm_c}20;background:{icm_c}15">{icm}</span></td>
        </tr>""")
    return '\n'.join(rows)


def _mtt_insights(results):
    # Calcular métricas por ICM pressure
    icm_groups = {'low': [], 'medium': [], 'high': []}
    for r in results:
        icm = r.get('context', {}).get('icmPressure', 'low')
        icm_groups.get(icm, icm_groups['low']).append(r['evaluation']['mistakeScore'])

    insights = []
    for icm, scores in icm_groups.items():
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        errors = sum(1 for s in scores if s > 0.18)
        error_pct = errors / len(scores) * 100
        color = ICM_COLOR[icm]
        insights.append(
            f'<div class="insight-box">'
            f'<b style="color:{color}">ICM {icm.upper()}</b> — '
            f'{len(scores)} decisões · score médio {avg:.4f} · '
            f'{errors} erros ({error_pct:.1f}%)'
            f'</div>'
        )

    # Insight sobre M ratio crítico
    critical = [r for r in results
                if (r.get('context', {}).get('mRatio') or 99) <= 6
                and r['evaluation']['label'] in ('small_mistake', 'clear_mistake')]
    if critical:
        insights.append(
            f'<div class="insight-box">'
            f'<b style="color:#ef4444">Atenção — Stack Crítico (M ≤ 6)</b> — '
            f'{len(critical)} erros com stack crítico. '
            f'Spots com M baixo exigem foco em push/fold correto.'
            f'</div>'
        )

    return '\n'.join(insights) if insights else '<div style="color:#64748b">Sem dados suficientes.</div>'
