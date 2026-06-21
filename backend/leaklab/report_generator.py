"""
report_generator.py — Sprint P (FEAT-04)
Premium HTML/PDF report generator.
- build_html_report(t, decisions, phases, hero)  → HTML string (for API)
- generate_pdf_bytes(html)                        → PDF bytes via WeasyPrint
- generate_report(...)                            → legacy file-based HTML (kept for backward compat)
"""
from __future__ import annotations
import html as _h
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict

from .session_metrics import build_session_metrics
from .leak_correlator import correlate_leaks

# ── Palette (light / print-friendly) ──────────────────────────────────────────
_BG     = '#ffffff'   # page background
_SURF   = '#ffffff'   # card surface
_SURF2  = '#f1f5f9'   # subtle fill
_BORD   = '#e2e8f0'   # gray borders
_TEXT   = '#0A0E1A'   # dark slate (brand)
_MUTED  = '#64748b'   # muted gray
_TEAL   = '#2DD4BF'   # GrindLab brand accent
_TEAL_D = '#0f766e'   # darker teal (text on white)
_GREEN  = '#059669'
_YELLOW = '#d97706'
_ORANGE = '#ea580c'
_RED    = '#dc2626'
_BLUE   = '#2563eb'

_LABEL_COLOR = {
    'standard':      _GREEN,
    'marginal':      _YELLOW,
    'small_mistake': _ORANGE,
    'clear_mistake': _RED,
}
_LABEL_NAME = {
    'standard':      'Standard',
    'marginal':      'Marginal',
    'small_mistake': 'Small Mistake',
    'clear_mistake': 'Clear Mistake',
}
_ICM_COLOR = {'low': _MUTED, 'medium': _YELLOW, 'high': _RED}

# ── Legacy exports (backward compat) ─────────────────────────────────────────
LABEL_COLOR = _LABEL_COLOR
LABEL_BG    = {
    'standard':      '#052e16',
    'marginal':      '#422006',
    'small_mistake': '#431407',
    'clear_mistake': '#450a0a',
}
ICM_COLOR = {'low': '#6b7280', 'medium': '#f59e0b', 'high': '#ef4444'}


# ── Premium public API ────────────────────────────────────────────────────────

def build_html_report(
    t: dict,
    decisions: List[dict],
    phases: List[dict],
    hero: str = 'Hero',
) -> str:
    """Returns a premium HTML string ready for WeasyPrint or inline download."""
    ctx = _build_ctx(t, decisions, phases)
    return _render(t, decisions, phases, ctx, hero)


def generate_pdf_bytes(html: str) -> bytes:
    """Converts HTML to PDF bytes. Raises ImportError if weasyprint is not installed."""
    from weasyprint import HTML  # type: ignore
    return HTML(string=html, base_url=None).write_pdf()


# ── Context builder ───────────────────────────────────────────────────────────

_MISTAKE_LABELS = ('small_mistake', 'clear_mistake')


def _build_ctx(t: dict, decisions: list, phases: list) -> dict:
    if not decisions:
        return {'empty': True, 'total': 0, 'label_counts': {}, 'label_pct': {},
                'top_leaks': [], 'icm': {}, 'worst': [],
                'streets': [], 'positions': [], 'gto': None,
                'ev_total': 0.0, 'ev_worst': [], 'recos': []}

    label_counts = Counter(d.get('label', 'standard') for d in decisions)
    total = len(decisions)
    label_pct = {k: v / total * 100 for k, v in label_counts.items()}

    spot_scores: dict = defaultdict(list)
    for d in decisions:
        key = '{}/{}'.format(d.get('street', '?'), d.get('best_action', '?'))
        spot_scores[key].append(d.get('score', 0) or 0)
    top_leaks = sorted(
        [(k, sum(v) / len(v), len(v)) for k, v in spot_scores.items() if len(v) >= 2],
        key=lambda x: x[1], reverse=True
    )[:8]

    icm_groups: dict = defaultdict(list)
    for d in decisions:
        icm = d.get('icm_pressure') or 'low'
        icm_groups[icm].append(d.get('score', 0) or 0)
    icm = {
        lvl: {
            'n': len(s),
            'avg': sum(s) / len(s),
            'mistakes': sum(1 for x in s if x > 0.18),
        }
        for lvl, s in icm_groups.items()
    }

    worst = sorted(decisions, key=lambda x: x.get('score', 0) or 0, reverse=True)[:10]

    # ── Per-street breakdown ──────────────────────────────────────────────────
    _street_order = ['preflop', 'flop', 'turn', 'river']
    street_groups: dict = defaultdict(list)
    for d in decisions:
        st = (d.get('street') or '?').lower()
        street_groups[st].append(d)
    streets = []
    for st in _street_order:
        ds = street_groups.get(st)
        if not ds:
            continue
        n = len(ds)
        mistakes = sum(1 for d in ds if d.get('label') in _MISTAKE_LABELS)
        std = sum(1 for d in ds if d.get('label') == 'standard')
        evs = [d.get('ev_loss_bb') for d in ds if d.get('ev_loss_bb') is not None]
        streets.append({
            'street': st,
            'n': n,
            'avg': sum((d.get('score') or 0) for d in ds) / n,
            'accuracy': std / n * 100,
            'mistake_rate': mistakes / n * 100,
            'ev_loss': sum(abs(e) for e in evs) if evs else None,
        })

    # ── Position breakdown ────────────────────────────────────────────────────
    pos_groups: dict = defaultdict(list)
    for d in decisions:
        pos = d.get('position')
        if pos:
            pos_groups[str(pos)].append(d)
    positions = []
    for pos, ds in pos_groups.items():
        n = len(ds)
        std = sum(1 for d in ds if d.get('label') == 'standard')
        mistakes = sum(1 for d in ds if d.get('label') in _MISTAKE_LABELS)
        positions.append({
            'position': pos,
            'n': n,
            'avg': sum((d.get('score') or 0) for d in ds) / n,
            'accuracy': std / n * 100,
            'mistakes': mistakes,
        })
    positions.sort(key=lambda p: (-p['avg'], -p['n']))

    # ── GTO deviation split ───────────────────────────────────────────────────
    gto_buckets = {'correct': 0, 'minor': 0, 'critical': 0}
    gto_seen = 0
    for d in decisions:
        gl = d.get('gto_label')
        if not gl:
            continue
        gto_seen += 1
        if gl in ('gto_correct', 'gto_mixed'):
            gto_buckets['correct'] += 1
        elif gl == 'gto_minor_deviation':
            gto_buckets['minor'] += 1
        elif gl == 'gto_critical':
            gto_buckets['critical'] += 1
        else:
            gto_seen -= 1  # unknown label, ignore
    gto = {'seen': gto_seen, **gto_buckets} if gto_seen else None

    # ── EV-loss aggregation ───────────────────────────────────────────────────
    ev_vals = [d for d in decisions if d.get('ev_loss_bb') is not None]
    ev_total = sum(abs(d.get('ev_loss_bb') or 0) for d in ev_vals)
    ev_worst = sorted(ev_vals, key=lambda d: abs(d.get('ev_loss_bb') or 0),
                      reverse=True)[:8]

    # ── Study recommendations (derived heuristics) ────────────────────────────
    recos = _build_recos(streets, positions, top_leaks, label_pct, gto, icm)

    return {
        'empty': False, 'total': total,
        'label_counts': dict(label_counts),
        'label_pct': dict(label_pct),
        'top_leaks': top_leaks, 'icm': icm, 'worst': worst,
        'streets': streets, 'positions': positions, 'gto': gto,
        'ev_total': ev_total, 'ev_worst': ev_worst, 'recos': recos,
    }


def _build_recos(streets, positions, top_leaks, label_pct, gto, icm) -> list:
    """Heuristic study recommendations derived strictly from computed data."""
    recos = []
    clr = label_pct.get('clear_mistake', 0)
    if clr >= 8:
        recos.append(
            f'Taxa de Clear Mistakes em {clr:.1f}% (referência saudável 2–8%). '
            f'Priorize revisar as decisões mais críticas listadas abaixo.')
    # worst street
    bad_streets = [s for s in streets if s['n'] >= 3]
    if bad_streets:
        worst_st = max(bad_streets, key=lambda s: s['mistake_rate'])
        if worst_st['mistake_rate'] >= 20:
            recos.append(
                f'Street com maior taxa de erro: {worst_st["street"]} '
                f'({worst_st["mistake_rate"]:.0f}% mistakes em {worst_st["n"]} decisões). '
                f'Concentre o estudo nesse momento da mão.')
    # worst position
    bad_pos = [p for p in positions if p['n'] >= 3]
    if bad_pos:
        wp = min(bad_pos, key=lambda p: p['accuracy'])
        if wp['accuracy'] < 60:
            recos.append(
                f'Posição mais fraca: {wp["position"]} '
                f'({wp["accuracy"]:.0f}% standard em {wp["n"]} decisões). '
                f'Reveja os ranges e linhas dessa posição.')
    # top leak
    if top_leaks:
        spot, score, n = top_leaks[0]
        nice = spot.replace('_', ' ').replace('/', ' / ')
        recos.append(
            f'Spot com maior score médio: "{nice}" '
            f'(score {score:.3f} em {n} ocorrências). É o vazamento mais recorrente.')
    # GTO critical
    if gto and gto.get('critical', 0) > 0 and gto.get('seen'):
        pct = gto['critical'] / gto['seen'] * 100
        recos.append(
            f'{gto["critical"]} desvios críticos de GTO ({pct:.0f}% das decisões avaliadas). '
            f'Estude as soluções do solver nesses spots.')
    # ICM high pressure
    hi = icm.get('high')
    if hi and hi['n'] >= 3 and hi['avg'] > 0.15:
        recos.append(
            f'Sob ICM alto o score médio sobe para {hi["avg"]:.3f} '
            f'({hi["n"]} decisões). Treine spots de bolha e mesa final.')
    return recos


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Chakra+Petch:wght@600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

@page { size: A4; margin: 1.4cm 1.2cm; }

body {
  background: #ffffff;
  color: #0A0E1A;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 10pt;
  line-height: 1.6;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.mono { font-family: 'JetBrains Mono', 'Consolas', monospace; }
.wrap { max-width: 920px; margin: 0 auto; padding: 16px; }

/* Cover */
.cover {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-top: 4px solid #2DD4BF;
  border-radius: 12px;
  padding: 32px 34px 28px;
  margin-bottom: 18px;
}
.cover-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 26px; }
.brand { font-family: 'Chakra Petch', sans-serif; font-size: 13pt; font-weight: 700; letter-spacing: 0.02em; color: #0A0E1A; }
.brand .ai { color: #0f766e; }
.cover-date { font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; color: #64748b; text-align: right; }
.cover-hero { font-family: 'Chakra Petch', sans-serif; font-size: 26pt; font-weight: 700; letter-spacing: -0.01em; color: #0A0E1A; margin-bottom: 4px; }
.cover-sub { font-size: 9.5pt; color: #64748b; margin-bottom: 24px; }
.meta-row { display: flex; flex-wrap: wrap; gap: 10px; }
.mp {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 14px;
}
.mp-k { font-size: 7pt; text-transform: uppercase; letter-spacing: 0.07em; color: #64748b; margin-bottom: 3px; }
.mp-v { font-family: 'JetBrains Mono', monospace; font-size: 14pt; font-weight: 700; color: #0A0E1A; line-height: 1.1; }

/* Sections */
.sect {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 14px;
  break-inside: avoid;
}
.sect-title {
  font-family: 'Chakra Petch', sans-serif;
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #0A0E1A;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 2px solid #2DD4BF;
}
.sect-note { font-size: 8.5pt; color: #64748b; margin-bottom: 12px; line-height: 1.5; }

/* Executive summary */
.summary p { font-size: 9pt; color: #1f2937; margin-bottom: 8px; line-height: 1.6; }
.summary p:last-child { margin-bottom: 0; }
.summary b { color: #0A0E1A; }

/* Recommendations */
.reco { display: flex; gap: 10px; padding: 9px 0; border-bottom: 1px solid #eef2f6; font-size: 8.8pt; color: #1f2937; line-height: 1.5; }
.reco:last-child { border-bottom: none; }
.reco-n { font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #0f766e; flex-shrink: 0; }

/* KPI row */
.kpi-row { display: flex; gap: 10px; margin-bottom: 14px; }
.kc {
  flex: 1;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px 12px;
  text-align: center;
}
.kc-l { font-size: 7pt; text-transform: uppercase; letter-spacing: 0.07em; color: #64748b; margin-bottom: 8px; }
.kc-v { font-family: 'JetBrains Mono', monospace; font-size: 18pt; font-weight: 700; line-height: 1; }
.kc-s { font-size: 7.5pt; color: #64748b; margin-top: 4px; }

/* Bars */
.bar { margin-bottom: 9px; }
.bar-h { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 8.5pt; }
.bar-t { background: #eef2f6; border-radius: 4px; height: 7px; overflow: hidden; }
.bar-f { height: 100%; border-radius: 4px; }

/* Table */
.dt { width: 100%; border-collapse: collapse; font-size: 8.5pt; }
.dt th {
  text-align: left; padding: 6px 9px;
  font-size: 7.5pt; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.07em;
  color: #64748b; border-bottom: 2px solid #e2e8f0;
}
.dt th.r { text-align: right; }
.dt td { padding: 8px 9px; border-bottom: 1px solid #eef2f6; font-size: 8.5pt; color: #1f2937; }
.dt td.m { font-family: 'JetBrains Mono', monospace; }
.dt td.r { text-align: right; font-family: 'JetBrains Mono', monospace; }
.dt tr:last-child td { border-bottom: none; }

/* Leak list */
.lr { display: flex; align-items: center; gap: 9px; padding: 8px 0; border-bottom: 1px solid #eef2f6; }
.lr:last-child { border-bottom: none; }
.lr-rk { font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; color: #64748b; width: 18px; flex-shrink: 0; }
.lr-nm { flex: 1; font-size: 8.5pt; color: #1f2937; }
.lr-bt { width: 75px; background: #eef2f6; border-radius: 3px; height: 5px; flex-shrink: 0; }
.lr-bf { height: 100%; border-radius: 3px; }
.lr-sc { font-family: 'JetBrains Mono', monospace; font-size: 8.5pt; font-weight: 700; width: 42px; text-align: right; flex-shrink: 0; }
.lr-n { font-size: 7.5pt; color: #64748b; width: 26px; text-align: right; flex-shrink: 0; }

/* Badges */
.badge { display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 7.5pt; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

/* Footer */
footer { text-align: center; color: #94a3b8; font-size: 7.5pt; padding: 16px 0 4px; font-family: 'JetBrains Mono', monospace; }

/* Print */
@media print {
  body { background: #ffffff; }
  .wrap { max-width: none; padding: 0; }
  .sect, .cover, .kc, .kpi-row { break-inside: avoid; page-break-inside: avoid; }
  .dt tr { break-inside: avoid; }
  footer { color: #64748b; }
}
"""


# ── Renderer ──────────────────────────────────────────────────────────────────

def _render(t: dict, decisions: list, phases: list, ctx: dict, hero: str) -> str:
    now    = datetime.now().strftime('%d/%m/%Y %H:%M')
    std    = t.get('standard_pct') or 0
    avg    = t.get('avg_score') or 0
    hands  = t.get('hands_count') or ctx.get('total', 0)
    profit = t.get('profit')
    buy_in = t.get('buy_in')
    place  = t.get('place')
    site   = t.get('site', '')
    name   = t.get('tournament_name') or t.get('tournament_id', 'N/A')
    played = _fmt_date(t.get('played_at'))

    std_c   = _score_color_rev(std, 75, 60)     # higher better
    avg_c   = _score_color_fwd(avg, 0.08, 0.15) # lower better
    clr_pct = ctx['label_pct'].get('clear_mistake', 0)
    clr_c   = _score_color_rev(100 - clr_pct, 95, 85)

    body = '\n'.join(filter(None, [
        _cover(hero, name, played, site, buy_in, place, std, std_c, avg, avg_c, hands, profit, now),
        _summary_section(t, ctx, std, avg, clr_pct, hero),
        _kpi_row(std, std_c, avg, avg_c, clr_pct, clr_c, ctx),
        _quality_section(ctx),
        _gto_section(ctx.get('gto')),
        _street_section(ctx.get('streets')),
        _phase_section(phases),
        _position_section(ctx.get('positions')),
        _icm_section(ctx['icm']),
        _leaks_section(ctx['top_leaks']),
        _ev_section(ctx.get('ev_worst'), ctx.get('ev_total', 0)),
        _worst_section(ctx['worst']),
        _recos_section(ctx.get('recos')),
    ]))

    return (
        '<!DOCTYPE html>\n'
        '<html lang="pt-BR">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        f'<title>GrindLab — {_h.escape(name)}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="wrap">\n'
        f'{body}\n'
        f'<footer>GrindLab &nbsp;·&nbsp; grindlabpoker.com &nbsp;·&nbsp; Análise técnica de decisão MTT &nbsp;·&nbsp; {_h.escape(now)}</footer>\n'
        '</div>\n'
        '</body>\n'
        '</html>'
    )


# ── Section builders ──────────────────────────────────────────────────────────

def _cover(hero, name, played, site, buy_in, place, std, std_c, avg, avg_c, hands, profit, now):
    profit_str = (f'{"+" if (profit or 0) >= 0 else ""}${abs(profit):.0f}'
                  if profit is not None else '—')
    profit_c   = _GREEN if (profit or 0) >= 0 else _RED
    buyin_str  = f'${buy_in}' if buy_in is not None else '—'
    place_str  = f'#{place}' if place is not None else '—'
    sub = ' &nbsp;·&nbsp; '.join(filter(None, [_h.escape(site), played]))

    pills = [
        ('Standard %', f'{std:.1f}%', std_c),
        ('Avg Score',  f'{avg:.4f}',  avg_c),
        ('Mãos',       str(hands),    _TEXT),
        ('Buy-in',     buyin_str,     _TEXT),
        ('Posição',    place_str,     _TEXT),
        ('Resultado',  profit_str,    profit_c),
    ]
    pills_html = ''.join(
        f'<div class="mp"><div class="mp-k">{k}</div>'
        f'<div class="mp-v" style="color:{c}">{v}</div></div>'
        for k, v, c in pills
    )

    return (
        f'<div class="cover">'
        f'<div class="cover-top">'
        f'<div class="brand">Grind<span class="ai">Lab</span></div>'
        f'<div class="cover-date">Relatório Técnico<br>{_h.escape(now)}</div>'
        f'</div>'
        f'<div class="cover-hero">{_h.escape(hero)}</div>'
        f'<div class="cover-sub">{_h.escape(name)}&nbsp;&nbsp;·&nbsp;&nbsp;{sub}</div>'
        f'<div class="meta-row">{pills_html}</div>'
        f'</div>'
    )


def _kpi_row(std, std_c, avg, avg_c, clr_pct, clr_c, ctx):
    total = ctx.get('total', 0)
    cards = [
        ('Standard %',      f'{std:.1f}%',   std_c, 'Decisões dentro do padrão'),
        ('Avg Score',       f'{avg:.4f}',     avg_c, 'Score médio — menor = melhor'),
        ('Clear Mistakes %', f'{clr_pct:.1f}%', clr_c, 'Erros claros'),
        ('Decisões',        str(total),      _TEXT, 'Total analisadas'),
    ]
    items = ''.join(
        f'<div class="kc">'
        f'<div class="kc-l">{l}</div>'
        f'<div class="kc-v" style="color:{c}">{v}</div>'
        f'<div class="kc-s">{s}</div>'
        f'</div>'
        for l, v, c, s in cards
    )
    return f'<div class="kpi-row">{items}</div>'


def _summary_section(t: dict, ctx: dict, std, avg, clr_pct, hero) -> str:
    total = ctx.get('total', 0)
    if not total:
        return ''
    mistakes = (ctx['label_counts'].get('small_mistake', 0)
                + ctx['label_counts'].get('clear_mistake', 0))
    marginal = ctx['label_counts'].get('marginal', 0)

    if std >= 75:
        verdict = 'jogo sólido e consistente'
    elif std >= 60:
        verdict = 'jogo competente com pontos de ajuste claros'
    else:
        verdict = 'desempenho abaixo do esperado, com vazamentos relevantes'

    parts = [
        f'<b>{_h.escape(str(hero))}</b> tomou <b>{total}</b> decisões analisadas neste torneio, '
        f'das quais <b>{ctx["label_counts"].get("standard", 0)}</b> dentro do padrão '
        f'(<b>{std:.1f}%</b> Standard), <b>{marginal}</b> marginais e <b>{mistakes}</b> com erro '
        f'(small/clear). O score médio foi <b>{avg:.4f}</b> '
        f'(quanto menor, melhor), indicando {verdict}.'
    ]

    gto = ctx.get('gto')
    if gto and gto.get('seen'):
        acc = gto['correct'] / gto['seen'] * 100
        parts.append(
            f'Entre as <b>{gto["seen"]}</b> decisões avaliadas contra o GTO Solver, '
            f'<b>{acc:.0f}%</b> seguiram a solução, com <b>{gto["critical"]}</b> desvios críticos.')

    ev_total = ctx.get('ev_total', 0)
    if ev_total and ev_total > 0:
        parts.append(
            f'A perda de EV acumulada nas decisões medidas soma aproximadamente '
            f'<b>{ev_total:.1f} BB</b>.')

    body = ''.join(f'<p>{p}</p>' for p in parts)
    return (
        f'<div class="sect summary">'
        f'<div class="sect-title">Resumo Executivo</div>'
        f'{body}'
        f'</div>'
    )


def _gto_section(gto: dict | None) -> str:
    if not gto or not gto.get('seen'):
        return ''
    seen = gto['seen']
    rows_def = [
        ('correct',  'Correto (GTO)',   _GREEN),
        ('minor',    'Desvio Menor',    _YELLOW),
        ('critical', 'Desvio Crítico',  _RED),
    ]
    bars = ''
    for key, lbl, color in rows_def:
        cnt = gto.get(key, 0)
        pct = cnt / seen * 100 if seen else 0
        bars += (
            f'<div class="bar">'
            f'<div class="bar-h">'
            f'<span style="color:{color}">{lbl}</span>'
            f'<span class="mono" style="color:{color}">{pct:.1f}% &nbsp;'
            f'<span style="color:{_MUTED};font-weight:400">({cnt})</span></span>'
            f'</div>'
            f'<div class="bar-t"><div class="bar-f" style="width:{min(pct,100):.1f}%;background:{color}"></div></div>'
            f'</div>'
        )
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Aderência ao GTO Solver</div>'
        f'<div class="sect-note">{seen} decisões avaliadas contra a solução do solver.</div>'
        f'{bars}'
        f'</div>'
    )


def _street_section(streets: list | None) -> str:
    if not streets:
        return ''
    _names = {'preflop': 'Preflop', 'flop': 'Flop', 'turn': 'Turn', 'river': 'River'}
    has_ev = any(s.get('ev_loss') is not None for s in streets)
    rows = ''
    for s in streets:
        acc_c = _score_color_rev(s['accuracy'], 70, 55)
        avg_c = _score_color_fwd(s['avg'], 0.08, 0.15)
        ev_cell = ''
        if has_ev:
            ev = s.get('ev_loss')
            ev_cell = (f'<td class="r" style="color:{_MUTED}">{ev:.1f}</td>'
                       if ev is not None else '<td class="r" style="color:#cbd5e1">—</td>')
        rows += (
            f'<tr>'
            f'<td>{_names.get(s["street"], _h.escape(s["street"]))}</td>'
            f'<td class="r">{s["n"]}</td>'
            f'<td class="r" style="color:{acc_c}">{s["accuracy"]:.0f}%</td>'
            f'<td class="r" style="color:{avg_c}">{s["avg"]:.4f}</td>'
            f'<td class="r" style="color:{_score_color_rev(100-s["mistake_rate"],90,80)}">{s["mistake_rate"]:.0f}%</td>'
            f'{ev_cell}'
            f'</tr>'
        )
    ev_th = '<th class="r">EV Loss (BB)</th>' if has_ev else ''
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Desempenho por Street</div>'
        f'<table class="dt">'
        f'<thead><tr>'
        f'<th>Street</th><th class="r">Decisões</th><th class="r">Standard</th>'
        f'<th class="r">Avg Score</th><th class="r">Mistake %</th>{ev_th}'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


def _position_section(positions: list | None) -> str:
    if not positions:
        return ''
    rows = ''
    for p in positions:
        acc_c = _score_color_rev(p['accuracy'], 70, 55)
        avg_c = _score_color_fwd(p['avg'], 0.08, 0.15)
        rows += (
            f'<tr>'
            f'<td class="m">{_h.escape(p["position"])}</td>'
            f'<td class="r">{p["n"]}</td>'
            f'<td class="r" style="color:{acc_c}">{p["accuracy"]:.0f}%</td>'
            f'<td class="r" style="color:{avg_c}">{p["avg"]:.4f}</td>'
            f'<td class="r" style="color:{_MUTED}">{p["mistakes"]}</td>'
            f'</tr>'
        )
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Desempenho por Posição</div>'
        f'<table class="dt">'
        f'<thead><tr>'
        f'<th>Posição</th><th class="r">Decisões</th><th class="r">Standard</th>'
        f'<th class="r">Avg Score</th><th class="r">Erros</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


def _ev_section(ev_worst: list | None, ev_total: float) -> str:
    if not ev_worst:
        return ''
    rows = ''
    for i, d in enumerate(ev_worst, 1):
        ev      = abs(d.get('ev_loss_bb') or 0)
        street  = d.get('street') or '?'
        cards   = d.get('hero_cards', '?') or '?'
        action  = d.get('action_taken', '?') or '?'
        best    = d.get('best_action', '?') or d.get('gto_action', '?') or '?'
        hand_id = str(d.get('hand_id', d.get('id', '?')))[-7:]
        rows += (
            f'<tr>'
            f'<td class="m" style="color:{_MUTED}">{i}</td>'
            f'<td class="m" style="color:{_MUTED};font-size:7.5pt">#{_h.escape(hand_id)}</td>'
            f'<td>{_h.escape(street)}</td>'
            f'<td class="m">{_h.escape(cards)}</td>'
            f'<td style="color:{_RED};font-weight:600">{_h.escape(action)}</td>'
            f'<td style="color:{_GREEN}">{_h.escape(best)}</td>'
            f'<td class="r" style="color:{_RED};font-weight:700">{ev:.2f}</td>'
            f'</tr>'
        )
    note = (f'Perda de EV total medida: <b style="color:{_RED}">{ev_total:.1f} BB</b>.'
            if ev_total else '')
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Decisões Mais Caras (EV Loss)</div>'
        f'<div class="sect-note">{note}</div>'
        f'<table class="dt">'
        f'<thead><tr>'
        f'<th>#</th><th>Mão</th><th>Street</th><th>Cartas</th>'
        f'<th>Tomou</th><th>Esperado</th><th class="r">EV Loss (BB)</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


def _recos_section(recos: list | None) -> str:
    if not recos:
        return ''
    items = ''.join(
        f'<div class="reco"><span class="reco-n">{i:02d}</span><span>{_h.escape(r)}</span></div>'
        for i, r in enumerate(recos, 1)
    )
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Recomendações de Estudo</div>'
        f'{items}'
        f'</div>'
    )


def _quality_section(ctx: dict) -> str:
    label_order = ['standard', 'marginal', 'small_mistake', 'clear_mistake']
    bars = ''
    for lbl in label_order:
        pct   = ctx['label_pct'].get(lbl, 0)
        count = ctx['label_counts'].get(lbl, 0)
        color = _LABEL_COLOR.get(lbl, _MUTED)
        name  = _LABEL_NAME.get(lbl, lbl)
        bars += (
            f'<div class="bar">'
            f'<div class="bar-h">'
            f'<span style="color:{color}">{name}</span>'
            f'<span class="mono" style="color:{color}">{pct:.1f}% &nbsp;<span style="color:{_MUTED};font-weight:400">({count})</span></span>'
            f'</div>'
            f'<div class="bar-t">'
            f'<div class="bar-f" style="width:{min(pct,100):.1f}%;background:{color}"></div>'
            f'</div>'
            f'</div>'
        )
    ref = (f'<div style="margin-top:12px;padding:10px 12px;background:#f1f5f9;'
           f'border:1px solid #e2e8f0;border-radius:6px;font-size:8pt;color:{_MUTED}">'
           f'<span style="color:{_TEXT};font-weight:600">Referência MTT saudável:&nbsp;</span>'
           f'Standard 60–80% &nbsp;·&nbsp; Marginal 10–20% &nbsp;·&nbsp; '
           f'Small Mistake 5–15% &nbsp;·&nbsp; Clear Mistake 2–8%</div>')
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Qualidade de Decisão</div>'
        f'{bars}{ref}'
        f'</div>'
    )


def _phase_section(phases: list) -> str:
    if not phases:
        return ''
    phase_order = ['Deep Stack', 'Mid Stack', 'Short Stack', 'Push/Fold']
    phase_map   = {p['phase']: p for p in phases}
    rows = ''
    for ph_name in phase_order:
        p = phase_map.get(ph_name)
        if not p:
            continue
        avg   = p.get('avg_score', 0) or 0
        rate  = p.get('mistake_rate', 0) or 0
        n     = p.get('n', 0)
        rng   = p.get('range', '—')
        avg_c = _score_color_fwd(avg, 0.08, 0.15)
        rows += (
            f'<tr>'
            f'<td>{_h.escape(ph_name)}</td>'
            f'<td class="m" style="color:{_MUTED}">{_h.escape(rng)}</td>'
            f'<td class="r">{n}</td>'
            f'<td class="r" style="color:{avg_c}">{avg:.4f}</td>'
            f'<td class="r" style="color:{_score_color_rev(100-rate,90,80)}">{rate:.1f}%</td>'
            f'</tr>'
        )
    if not rows:
        return ''
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Phase Breakdown (M-Ratio)</div>'
        f'<table class="dt">'
        f'<thead><tr>'
        f'<th>Fase</th><th>M-Ratio</th>'
        f'<th class="r">Decisões</th><th class="r">Avg Score</th><th class="r">Mistake %</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


def _leaks_section(top_leaks: list) -> str:
    if not top_leaks:
        return ''
    max_score = max(s for _, s, _ in top_leaks) if top_leaks else 1
    rows = ''
    for i, (spot, score, n) in enumerate(top_leaks, 1):
        label = spot.replace('_', ' ').replace('/', ' / ')
        color = _score_color_fwd(score, 0.12, 0.25)
        bar_w = int(min(100, score / max(max_score, 0.01) * 100))
        rows += (
            f'<div class="lr">'
            f'<span class="lr-rk">{i:02d}</span>'
            f'<span class="lr-nm">{_h.escape(label)}</span>'
            f'<div class="lr-bt"><div class="lr-bf" style="width:{bar_w}%;background:{color}"></div></div>'
            f'<span class="lr-sc" style="color:{color}">{score:.3f}</span>'
            f'<span class="lr-n">{n}×</span>'
            f'</div>'
        )
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Top Leaks — Spots com Maior Score Médio</div>'
        f'{rows}'
        f'</div>'
    )


def _icm_section(icm: dict) -> str:
    if not icm:
        return ''
    order = ['low', 'medium', 'high']
    label = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}
    rows = ''
    for lvl in order:
        d = icm.get(lvl)
        if not d:
            continue
        avg_c    = _score_color_fwd(d['avg'], 0.08, 0.15)
        mist_pct = (d['mistakes'] / d['n'] * 100) if d['n'] else 0
        rows += (
            f'<tr>'
            f'<td><span class="badge" style="color:{_ICM_COLOR[lvl]};'
            f'background:{_ICM_COLOR[lvl]}18;border:1px solid {_ICM_COLOR[lvl]}30">'
            f'ICM {label[lvl]}</span></td>'
            f'<td class="r">{d["n"]}</td>'
            f'<td class="r" style="color:{avg_c}">{d["avg"]:.4f}</td>'
            f'<td class="r">{d["mistakes"]}</td>'
            f'<td class="r" style="color:{_score_color_rev(100-mist_pct,90,80)}">{mist_pct:.1f}%</td>'
            f'</tr>'
        )
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Performance por ICM Pressure</div>'
        f'<table class="dt">'
        f'<thead><tr>'
        f'<th>Nível</th><th class="r">Decisões</th>'
        f'<th class="r">Avg Score</th><th class="r">Erros</th><th class="r">Mistake %</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


def _worst_section(worst: list) -> str:
    if not worst:
        return ''
    rows = ''
    for i, d in enumerate(worst, 1):
        label   = d.get('label', 'standard')
        score   = d.get('score', 0) or 0
        street  = d.get('street') or '?'
        cards   = d.get('hero_cards', '?') or '?'
        action  = d.get('action_taken', '?') or '?'
        best    = d.get('best_action', '?') or '?'
        m_ratio = d.get('m_ratio')
        icm     = d.get('icm_pressure', 'low') or 'low'
        hand_id = str(d.get('hand_id', d.get('id', '?')))[-7:]

        lbl_c = _LABEL_COLOR.get(label, _MUTED)
        sc_c  = _score_color_fwd(score, 0.12, 0.25)
        icm_c = _ICM_COLOR.get(icm, _MUTED)

        rows += (
            f'<tr>'
            f'<td class="m" style="color:{_MUTED}">{i}</td>'
            f'<td class="m" style="color:{_MUTED};font-size:7.5pt">#{_h.escape(hand_id)}</td>'
            f'<td>{_h.escape(street)}</td>'
            f'<td class="m">{_h.escape(cards)}</td>'
            f'<td style="color:{_RED};font-weight:600">{_h.escape(action)}</td>'
            f'<td style="color:{_GREEN}">{_h.escape(best)}</td>'
            f'<td><span class="badge" style="color:{lbl_c};background:{lbl_c}18">'
            f'{_LABEL_NAME.get(label, label)}</span></td>'
            f'<td class="r" style="color:{sc_c}">{score:.3f}</td>'
            f'<td class="r" style="color:{_MUTED}">{m_ratio if m_ratio is not None else "—"}</td>'
            f'<td><span class="badge" style="color:{icm_c};background:{icm_c}18">{_h.escape(icm)}</span></td>'
            f'</tr>'
        )
    return (
        f'<div class="sect">'
        f'<div class="sect-title">Top 10 Decisões Mais Críticas</div>'
        f'<table class="dt">'
        f'<thead><tr>'
        f'<th>#</th><th>Mão</th><th>Street</th><th>Cartas</th>'
        f'<th>Tomou</th><th>Esperado</th><th>Label</th>'
        f'<th class="r">Score</th><th class="r">M</th><th>ICM</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )


# ── Color helpers ─────────────────────────────────────────────────────────────

def _score_color_fwd(v: float, good: float, warn: float) -> str:
    """Lower is better: v <= good → green, <= warn → yellow, else red."""
    if v <= good:
        return _GREEN
    if v <= warn:
        return _YELLOW
    return _RED


def _score_color_rev(v: float, good: float, warn: float) -> str:
    """Higher is better: v >= good → green, >= warn → yellow, else red."""
    if v >= good:
        return _GREEN
    if v >= warn:
        return _YELLOW
    return _RED


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return '—'
    try:
        return datetime.fromisoformat(iso[:19]).strftime('%d/%m/%Y')
    except Exception:
        return iso[:10]


# ── Legacy HTML builder (unchanged) ──────────────────────────────────────────

def generate_report(results: list, hand_results: dict,
                    output_path: str, hero: str = 'Hero',
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


def _build_html(metrics, leaks, worst, results, hand_results, hero, tournament_id):
    now  = datetime.now().strftime('%d/%m/%Y %H:%M')
    dist = metrics['label_distribution']
    pct  = metrics['label_pct']
    streets   = ['preflop', 'flop', 'turn', 'river']
    street_data = metrics.get('by_street', {})

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>LeakLabs.ai — Relatório de Auditoria</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
  .header {{ background: linear-gradient(135deg, #1e293b, #0f172a);
             border: 1px solid #334155; border-radius: 12px;
             padding: 28px 32px; margin-bottom: 24px; }}
  .header h1 {{ font-size: 1.8rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.5px; }}
  .header .sub {{ color: #94a3b8; font-size: 0.9rem; margin-top: 4px; }}
  .header .meta {{ display: flex; gap: 24px; margin-top: 16px; flex-wrap: wrap; }}
  .meta-item {{ background: #1e293b; border: 1px solid #334155;
                border-radius: 8px; padding: 8px 14px; font-size: 0.85rem; }}
  .meta-item .val {{ font-weight: 700; color: #f8fafc; font-size: 1.1rem; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr);
                   gap: 16px; margin-bottom: 24px; }}
  @media(max-width:800px) {{ .metrics-grid {{ grid-template-columns: repeat(2,1fr); }} }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155;
                  border-radius: 12px; padding: 20px; text-align: center; }}
  .metric-card .label {{ font-size: 0.8rem; color: #94a3b8; text-transform: uppercase;
                          letter-spacing: 0.05em; margin-bottom: 8px; }}
  .metric-card .value {{ font-size: 2rem; font-weight: 700; }}
  .metric-card .pct {{ font-size: 0.85rem; color: #94a3b8; margin-top: 2px; }}
  .section {{ background: #1e293b; border: 1px solid #334155;
              border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
  .section h2 {{ font-size: 1.1rem; font-weight: 600; color: #f8fafc;
                 margin-bottom: 20px; padding-bottom: 12px;
                 border-bottom: 1px solid #334155; }}
  .bar-wrap {{ margin-bottom: 14px; }}
  .bar-label {{ display: flex; justify-content: space-between;
                font-size: 0.85rem; margin-bottom: 5px; }}
  .bar-track {{ background: #0f172a; border-radius: 6px; height: 10px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 6px; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px;
            font-size: 0.78rem; font-weight: 600; }}
  .error-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  .error-table th {{ text-align: left; padding: 10px 12px; color: #64748b;
                     font-weight: 600; font-size: 0.78rem; text-transform: uppercase;
                     border-bottom: 1px solid #334155; }}
  .error-table td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
  .error-table tr:hover td {{ background: #0f172a; }}
  .leak-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
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
  .heat {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  .street-grid {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; }}
  @media(max-width:800px) {{ .street-grid {{ grid-template-columns: repeat(2,1fr); }} }}
  .street-card {{ background: #0f172a; border: 1px solid #334155;
                  border-radius: 8px; padding: 14px; }}
  .street-card h3 {{ font-size: 0.8rem; color: #94a3b8; text-transform: uppercase;
                     letter-spacing: 0.05em; margin-bottom: 10px; }}
  .street-stat {{ display: flex; justify-content: space-between; font-size: 0.82rem; padding: 3px 0; }}
  .insight-box {{ background: #0f172a; border-left: 3px solid #3b82f6;
                  border-radius: 0 8px 8px 0; padding: 12px 16px;
                  font-size: 0.88rem; color: #cbd5e1; margin-bottom: 10px; }}
  .score-pill {{ display: inline-block; padding: 2px 8px; border-radius: 20px;
                 font-size: 0.8rem; font-weight: 700;
                 background: #0f172a; border: 1px solid #334155; }}
  .icm-badge {{ display: inline-block; padding: 1px 8px; border-radius: 4px;
                font-size: 0.75rem; font-weight: 600; }}
  footer {{ text-align: center; color: #475569; font-size: 0.8rem; padding: 24px 0 8px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🎯 LeakLabs.ai — Relatório de Auditoria</h1>
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
  <div class="metrics-grid">
    {_metric_card('Standard',      dist.get('standard',0),      pct.get('standard',0),      LABEL_COLOR['standard'])}
    {_metric_card('Marginal',      dist.get('marginal',0),      pct.get('marginal',0),      LABEL_COLOR['marginal'])}
    {_metric_card('Small Mistake', dist.get('small_mistake',0), pct.get('small_mistake',0), LABEL_COLOR['small_mistake'])}
    {_metric_card('Clear Mistake', dist.get('clear_mistake',0), pct.get('clear_mistake',0), LABEL_COLOR['clear_mistake'])}
  </div>
  <div class="section">
    <h2>📊 Distribuição por Street</h2>
    <div class="street-grid">{_street_cards(street_data, streets)}</div>
  </div>
  <div class="section">
    <h2>📈 Qualidade das Decisões</h2>
    {_bar('Standard',      pct.get('standard',0),      LABEL_COLOR['standard'])}
    {_bar('Marginal',      pct.get('marginal',0),      LABEL_COLOR['marginal'])}
    {_bar('Small Mistake', pct.get('small_mistake',0), LABEL_COLOR['small_mistake'])}
    {_bar('Clear Mistake', pct.get('clear_mistake',0), LABEL_COLOR['clear_mistake'])}
    <div style="margin-top:16px;padding:12px;background:#0f172a;border-radius:8px;font-size:0.85rem;color:#94a3b8">
      <b style="color:#f8fafc">Referência MTT saudável:</b>
      Standard 60–80% · Marginal 10–20% · Small Mistake 5–15% · Clear Mistake 2–8%
    </div>
  </div>
  <div class="section">
    <h2>🔍 Análise de Leaks</h2>
    <div class="leak-grid">
      {_leak_card('Por Ação',       leaks.get('by_action', {}), 8)}
      {_leak_card('Por Street',     leaks.get('by_street', {}), 8)}
      {_leak_card('Street × Ação', leaks.get('by_street_action', {}), 8)}
    </div>
  </div>
  <div class="section">
    <h2>⚠️ Top 20 Decisões Mais Críticas</h2>
    <table class="error-table">
      <thead>
        <tr>
          <th>#</th><th>Mão</th><th>Street</th><th>Cartas</th>
          <th>Tomou</th><th>Esperado</th><th>Label</th><th>Score</th><th>M</th><th>ICM</th>
        </tr>
      </thead>
      <tbody>{_error_rows(worst)}</tbody>
    </table>
  </div>
  <div class="section">
    <h2>🏆 Insights de Contexto MTT</h2>
    {_mtt_insights(results)}
  </div>
</div>
<footer>LeakLabs.ai · Análise determinística de poker MTT · {now}</footer>
</body>
</html>"""


def _metric_card(label, count, pct, color):
    return (f'<div class="metric-card">'
            f'<div class="label">{label}</div>'
            f'<div class="value" style="color:{color}">{count}</div>'
            f'<div class="pct">{pct:.1f}%</div>'
            f'</div>')


def _bar(label, pct, color):
    return (f'<div class="bar-wrap">'
            f'<div class="bar-label">'
            f'<span>{label}</span>'
            f'<span style="color:{color};font-weight:600">{pct:.1f}%</span>'
            f'</div>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:{min(pct,100):.1f}%;background:{color}"></div>'
            f'</div>'
            f'</div>')


def _street_cards(street_data, streets):
    cards = []
    for street in streets:
        d = street_data.get(street, {})
        if not d:
            continue
        total = sum(d.values())
        rows = ''.join(
            f'<div class="street-stat">'
            f'<span style="color:{LABEL_COLOR.get(lbl, "#94a3b8")}">{lbl}</span>'
            f'<span>{cnt} ({cnt/total*100:.0f}%)</span></div>'
            for lbl, cnt in sorted(d.items(), key=lambda x: x[1], reverse=True)
        )
        cards.append(
            f'<div class="street-card">'
            f'<h3>{street}</h3>'
            f'<div style="font-size:0.78rem;color:#64748b;margin-bottom:8px">{total} decisões</div>'
            f'{rows}</div>'
        )
    return '\n'.join(cards)


def _leak_card(title, data, max_rows):
    if not data:
        return (f'<div class="leak-card"><h3>{title}</h3>'
                f'<div style="color:#64748b">Sem dados</div></div>')
    sorted_items = sorted(data.items(), key=lambda x: x[1]['avg_weight'], reverse=True)[:max_rows]
    rows = []
    for key, v in sorted_items:
        if v['count'] < 2:
            continue
        aw = v['avg_weight']
        color = '#ef4444' if aw >= 0.55 else '#f97316' if aw >= 0.3 else '#f59e0b' if aw >= 0.15 else '#22c55e'
        rows.append(
            f'<div class="leak-row">'
            f'<span class="leak-key"><span class="heat" style="background:{color}"></span>{key}</span>'
            f'<span class="leak-val">avg={aw:.3f} · n={v["count"]}</span>'
            f'</div>'
        )
    body = ''.join(rows) or '<div style="color:#64748b;font-size:0.85rem">Nenhum leak significativo</div>'
    return f'<div class="leak-card"><h3>{title}</h3>{body}</div>'


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
        rows.append(
            f'<tr>'
            f'<td style="color:#64748b">{i}</td>'
            f'<td style="font-family:monospace;font-size:0.8rem">#{short_id}</td>'
            f'<td>{r.get("street","?")}</td>'
            f'<td style="font-family:monospace;color:#f8fafc">{cards}</td>'
            f'<td style="color:#ef4444;font-weight:600">{r.get("actionTaken","?")}</td>'
            f'<td style="color:#22c55e">{r.get("bestAction","?")}</td>'
            f'<td><span class="badge" style="color:{color};background:{bg}">{label}</span></td>'
            f'<td><span class="score-pill">{score:.3f}</span></td>'
            f'<td style="color:#94a3b8">{m}</td>'
            f'<td><span class="icm-badge" style="color:{icm_c};border:1px solid {icm_c}20;background:{icm_c}15">{icm}</span></td>'
            f'</tr>'
        )
    return '\n'.join(rows)


def _mtt_insights(results):
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
    critical = [r for r in results
                if (r.get('context', {}).get('mRatio') or 99) <= 6
                and r['evaluation']['label'] in ('small_mistake', 'clear_mistake')]
    if critical:
        insights.append(
            f'<div class="insight-box">'
            f'<b style="color:#ef4444">Stack Crítico (M ≤ 6)</b> — '
            f'{len(critical)} erros com stack crítico. '
            f'Spots com M baixo exigem foco em push/fold correto.'
            f'</div>'
        )
    return '\n'.join(insights) if insights else '<div style="color:#64748b">Sem dados suficientes.</div>'
