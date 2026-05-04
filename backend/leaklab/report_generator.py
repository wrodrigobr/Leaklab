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

# ── Palette ───────────────────────────────────────────────────────────────────
_BG     = '#0a0f1e'
_SURF   = '#111827'
_SURF2  = '#162032'
_BORD   = '#1f2937'
_TEXT   = '#f9fafb'
_MUTED  = '#9ca3af'
_GREEN  = '#10b981'
_YELLOW = '#f59e0b'
_ORANGE = '#f97316'
_RED    = '#ef4444'
_BLUE   = '#60a5fa'

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

def _build_ctx(t: dict, decisions: list, phases: list) -> dict:
    if not decisions:
        return {'empty': True, 'total': 0, 'label_counts': {}, 'label_pct': {},
                'top_leaks': [], 'icm': {}, 'worst': []}

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
    )[:5]

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

    return {
        'empty': False, 'total': total,
        'label_counts': dict(label_counts),
        'label_pct': dict(label_pct),
        'top_leaks': top_leaks, 'icm': icm, 'worst': worst,
    }


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

@page { size: A4; margin: 1.4cm 1.2cm; }

body {
  background: #0a0f1e;
  color: #f9fafb;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 10pt;
  line-height: 1.6;
}

.mono { font-family: 'JetBrains Mono', 'Consolas', monospace; }

/* Cover */
.cover {
  background: linear-gradient(135deg, #0d1b2e 0%, #091525 55%, #0a0f1e 100%);
  border: 1px solid #1e3a5f;
  border-radius: 12px;
  padding: 36px 36px 32px;
  margin-bottom: 18px;
}
.cover-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
.brand { font-size: 10.5pt; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #60a5fa; }
.brand .g { color: #10b981; }
.cover-date { font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; color: #9ca3af; text-align: right; }
.cover-hero { font-size: 26pt; font-weight: 300; letter-spacing: -0.02em; color: #f9fafb; margin-bottom: 4px; }
.cover-sub { font-size: 9.5pt; color: #9ca3af; margin-bottom: 26px; }
.meta-row { display: flex; flex-wrap: wrap; gap: 10px; }
.mp {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 8px 14px;
}
.mp-k { font-size: 7pt; text-transform: uppercase; letter-spacing: 0.07em; color: #9ca3af; margin-bottom: 3px; }
.mp-v { font-family: 'JetBrains Mono', monospace; font-size: 14pt; font-weight: 700; color: #f9fafb; line-height: 1.1; }

/* Sections */
.sect {
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 14px;
  break-inside: avoid;
}
.sect-title {
  font-size: 7.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #9ca3af;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #1f2937;
}

/* KPI row */
.kpi-row { display: flex; gap: 10px; margin-bottom: 14px; }
.kc {
  flex: 1;
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 10px;
  padding: 16px 12px;
  text-align: center;
}
.kc-l { font-size: 7pt; text-transform: uppercase; letter-spacing: 0.07em; color: #9ca3af; margin-bottom: 8px; }
.kc-v { font-family: 'JetBrains Mono', monospace; font-size: 18pt; font-weight: 700; line-height: 1; }
.kc-s { font-size: 7.5pt; color: #9ca3af; margin-top: 4px; }

/* Bars */
.bar { margin-bottom: 9px; }
.bar-h { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 8.5pt; }
.bar-t { background: rgba(255,255,255,0.06); border-radius: 4px; height: 7px; overflow: hidden; }
.bar-f { height: 100%; border-radius: 4px; }

/* Table */
.dt { width: 100%; border-collapse: collapse; font-size: 8.5pt; }
.dt th {
  text-align: left; padding: 6px 9px;
  font-size: 7.5pt; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.07em;
  color: #9ca3af; border-bottom: 1px solid #1f2937;
}
.dt th.r { text-align: right; }
.dt td { padding: 8px 9px; border-bottom: 1px solid rgba(31,41,55,0.35); font-size: 8.5pt; }
.dt td.m { font-family: 'JetBrains Mono', monospace; }
.dt td.r { text-align: right; font-family: 'JetBrains Mono', monospace; }
.dt tr:last-child td { border-bottom: none; }
.dt tr:hover td { background: rgba(255,255,255,0.02); }

/* Leak list */
.lr { display: flex; align-items: center; gap: 9px; padding: 8px 0; border-bottom: 1px solid rgba(31,41,55,0.35); }
.lr:last-child { border-bottom: none; }
.lr-rk { font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; color: #9ca3af; width: 18px; flex-shrink: 0; }
.lr-nm { flex: 1; font-size: 8.5pt; }
.lr-bt { width: 75px; background: rgba(255,255,255,0.05); border-radius: 3px; height: 5px; flex-shrink: 0; }
.lr-bf { height: 100%; border-radius: 3px; }
.lr-sc { font-family: 'JetBrains Mono', monospace; font-size: 8.5pt; font-weight: 700; width: 42px; text-align: right; flex-shrink: 0; }
.lr-n { font-size: 7.5pt; color: #9ca3af; width: 26px; text-align: right; flex-shrink: 0; }

/* Badges */
.badge { display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 7.5pt; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

/* Footer */
footer { text-align: center; color: #6b7280; font-size: 7.5pt; padding: 16px 0 4px; font-family: 'JetBrains Mono', monospace; }
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

    body = '\n'.join([
        _cover(hero, name, played, site, buy_in, place, std, std_c, avg, avg_c, hands, profit, now),
        _kpi_row(std, std_c, avg, avg_c, clr_pct, clr_c, ctx),
        _quality_section(ctx),
        _phase_section(phases),
        _leaks_section(ctx['top_leaks']),
        _icm_section(ctx['icm']),
        _worst_section(ctx['worst']),
    ])

    return (
        '<!DOCTYPE html>\n'
        '<html lang="pt-BR">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        f'<title>PokerLeakLab — {_h.escape(name)}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        f'{body}\n'
        f'<footer>PokerLeakLab &nbsp;·&nbsp; Análise técnica de decisão MTT &nbsp;·&nbsp; {_h.escape(now)}</footer>\n'
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
        f'<div class="brand">Poker<span class="g">Leak</span>Lab</div>'
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
    ref = (f'<div style="margin-top:12px;padding:10px 12px;background:rgba(255,255,255,0.03);'
           f'border-radius:6px;font-size:8pt;color:{_MUTED}">'
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
        street  = d.get('street', '?')
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
<title>PokerLeakLab — Relatório de Auditoria</title>
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
    <h1>🎯 PokerLeakLab — Relatório de Auditoria</h1>
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
<footer>PokerLeakLab v2 · Análise determinística de poker MTT · {now}</footer>
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
