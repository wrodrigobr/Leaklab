"""
Relatório Coach × GrindLab — Torneio #27, a partir das ANOTAÇÕES DO COACH no replayer
(fonte única). Lê coach_hand_annotations + os verdictos atuais do engine (decisions) e
gera docs/coach_review_t27.html com TODAS as mãos: match / divergência / sustenta nossa
decisão + pontos de calibragem (onde o sistema diverge sistematicamente do coach).

Roda depois de reanalyze_all_labels (verdictos atuais).
"""
import os, sys, re, html
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3

TID = 388
DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
OUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'coach_review_t27.html')

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row

def norm(a):
    if not a: return ''
    a = a.lower().rstrip('s')
    return {'allin': 'allin', 'all-in': 'allin', 'jam': 'allin', 'shove': 'allin',
            'bet': 'bet', 'raise': 'raise', 'call': 'call', 'fold': 'fold', 'check': 'check'}.get(a, a)

# Aprovação / crítica do coach pela LINGUAGEM (mais robusto que extrair a ação — quando o
# coach critica, o texto menciona a ação do HERO, não a recomendada).
_APPROVE = re.compile(r'perfeit|jogou (muito )?bem|muito bem|bem jogad|aprov|(?<!n[ãa]o )gost(o|ei|a )|'
                      r'\bcerto\b|correto|\blegal\b|[óo]tim|justo|excelente|t[áa] bom|t[áa] correto|'
                      r'tranquil|sem erro|trivial|un[âa]nime|\bboa\b|\bbom\b|sem cr[íi]tica|'
                      r'beleza|passou|\bok\b|importante isso|paci[êe]ncia', re.I)
# "ideal" sai: "o ideal seria [outra ação]" é CRÍTICA, não aprovação.
_CRIT = re.compile(r'deveria|recomendo|n[ãa]o gosto|larga(r|ria)?|pode largar|errad|for[çc]ad|'
                   r'desnecess|estranh|confus|sem sentido|pecou|abusiv|demais|problema|n[ãa]o aconselho|'
                   r'n[ãa]o recomend|cortou|caro\b|evita|\bruim|prefiro|preferia|tomaria|tem que|alto demais|'
                   r'baixo demais|n[ãa]o (faz sentido|me parece)|spew|vil[ãa]o|perde', re.I)

SYS_MISTAKE_LABELS = {'small_mistake', 'clear_mistake'}
SYS_MISTAKE_GTO = {'gto_minor_deviation', 'gto_critical'}

# ação ENDOSSADA pelo coach extraída do texto (slang BR) — None se não dá pra inferir
def _parse_rec(t):
    t = (t or '').lower()
    if re.search(r'\b(jam|shove|all-?in|dar(ia)? (o |a )?win|manda(r)? win|all in)\b', t): return 'allin'
    if re.search(r'\b(3-?bet|tribet|re-?raise|reraise|iso-?raise|4-?bet|forbet|5-?bet)\b', t): return 'raise'
    if re.search(r'\b(fold|larga(r|ria)?|largo|foldar(ia|am|ado)?|joga(r)? fora)\b', t): return 'fold'
    if re.search(r'\b(aposta(r|ndo)?|c-?bet|barrel|lead|donk|value|\bbet\b|blocking bet|apostei)\b', t): return 'bet'
    if re.search(r'\b(check-?call|check-?fold|dar mesa|da mesa|pot control|\bcheck\b|controlou)\b', t): return 'check'
    if re.search(r'\b(call|pagar|paga|pago|acompanha)\b', t): return 'call'
    return None

# crítica FORTE: o coach desaprova mesmo quando a ação mencionada bate a do hero
# (ex.: "pagou demais", "não gosto", "deveria ter...", "desnecessária")
_STRONG_CRIT = re.compile(r'demais|n[ãa]o gosto|deveria|errad|desnecess|estranh|confus|sem sentido|'
                          r'pecou|caro\b|problema|n[ãa]o aconselho|n[ãa]o recomend|spew|cortou|abusiv|'
                          r'alto demais|baixo demais|prefiro|preferia|tomaria|n[ãa]o (faz sentido|me parece)', re.I)

def coach_says_mistake(dec, ann):
    """True/False/None — o coach considera a jogada do hero um erro? None = comentário neutro.
    override_label > coach_action > ação ENDOSSADA no texto (vs a do hero) > sentimento.
    Chave: o coach mencionar a MESMA ação do hero é APROVAÇÃO ('larga' + hero foldou), a não
    ser que haja crítica forte ('pagou demais')."""
    if ann['coach_override_label']:
        return ann['coach_override_label'] in SYS_MISTAKE_LABELS
    hero = norm(dec['action_taken'])
    t = ann['comment'] or ''
    rec = norm(ann['coach_action']) if ann['coach_action'] else _parse_rec(t)
    strong = bool(_STRONG_CRIT.search(t))
    # parse SÓ pra detectar APROVAÇÃO (ação endossada == ação do hero, sem crítica forte).
    # NÃO uso rec!=hero do texto livre p/ afirmar erro (over-gera: descreve a linha). Pro
    # resto, sentimento. Guarda de NEGAÇÃO: "não [ação]" (ex.: "não vejo motivos pra foldar")
    # nega a aprovação dessa ação.
    _neg_kw = {'fold': r'fold|larga', 'call': r'call|pag', 'bet': r'aposta|bet|c-?bet',
               'check': r'check|mesa', 'raise': r'3-?bet|raise|tribet', 'allin': r'all|jam|shove|win'}
    _negated = rec and re.search(r'n[ãa]o\b[^.]{0,30}(' + _neg_kw.get(rec, rec) + ')', t, re.I)
    if rec and rec == hero and not strong and not _negated:
        return False
    ap, cr = len(_APPROVE.findall(t)), len(_CRIT.findall(t))
    if ap == 0 and cr == 0:
        return None
    return cr > ap

def classify(dec, ann):
    # "erro do sistema" = a SEVERIDADE do veredito (label) que o usuário vê — não o
    # gto_label (frequência do solver). Após a calibração por EV, um gto_critical de baixo
    # custo vira marginal/standard → deixa de ser "erro" aqui (coerente com o card).
    sys_mistake = dec['label'] in SYS_MISTAKE_LABELS
    cm = coach_says_mistake(dec, ann)
    rec = norm(ann['coach_action']) if ann['coach_action'] else None
    if cm is None:
        return 'comentario', rec, sys_mistake
    if sys_mistake and cm:        return 'match_erro', rec, sys_mistake
    if not sys_mistake and not cm: return 'match_ok', rec, sys_mistake
    if sys_mistake and not cm:    return 'diverge_rigido', rec, sys_mistake   # nós flagamos, coach aprova
    return 'diverge_perdido', rec, sys_mistake                               # coach flaga, nós aprovamos

# ── coleta ────────────────────────────────────────────────────────────────────────────
decs = c.execute('''SELECT id, hand_id, street, action_taken, hero_cards, position, label,
    gto_label, gto_action, best_action, ev_loss_bb, score
    FROM decisions WHERE tournament_id=? ORDER BY hand_id, rowid''', (TID,)).fetchall()
anns = {r['decision_id']: r for r in c.execute(
    '''SELECT a.* FROM coach_hand_annotations a JOIN decisions d ON d.id=a.decision_id
       WHERE d.tournament_id=?''', (TID,)).fetchall()}

by_hand = defaultdict(list)
for d in decs:
    by_hand[d['hand_id']].append(d)

rows = []   # (dec, ann, kind, rec, sys_mistake)
for d in decs:
    ann = anns.get(d['id'])
    if ann:
        kind, rec, sysm = classify(d, ann)
    else:
        kind, rec, sysm = 'sem_anotacao', None, (d['label'] in SYS_MISTAKE_LABELS)
    rows.append((d, ann, kind, rec, sysm))

cnt = Counter(r[2] for r in rows)
n_ann = sum(1 for r in rows if r[1])
n_compar = sum(1 for r in rows if r[2] in ('match_erro','match_ok','diverge_rigido','diverge_perdido'))
n_match = cnt['match_erro'] + cnt['match_ok']
align = round(100*n_match/n_compar, 1) if n_compar else 0
rigido = [r for r in rows if r[2]=='diverge_rigido']
perdido = [r for r in rows if r[2]=='diverge_perdido']

# ── HTML ──────────────────────────────────────────────────────────────────────────────
def esc(s): return html.escape(str(s or ''))
KIND_BADGE = {
    'match_ok':       ('MATCH · ok', '#2DD4BF', 'Coach e sistema aprovam a jogada.'),
    'match_erro':     ('MATCH · erro', '#38bdf8', 'Coach e sistema apontam o mesmo erro — o comentário SUSTENTA nossa decisão.'),
    'diverge_rigido': ('DIVERGE · rígido', '#f59e0b', 'Nós flagamos erro, o coach aprova → candidato a relaxar/calibrar.'),
    'diverge_perdido':('DIVERGE · perdido', '#ef4444', 'Coach aponta erro que nós NÃO pegamos → leak/exploit a incorporar.'),
    'comentario':     ('COMENTÁRIO', '#94a3b8', 'Nota do coach sem ação clara pra comparar.'),
    'sem_anotacao':   ('—', '#334155', 'Sem comentário do coach.'),
}
def badge(kind):
    lbl, col, _ = KIND_BADGE[kind]
    return f'<span style="background:{col}22;color:{col};border:1px solid {col}55;border-radius:6px;padding:2px 8px;font:600 11px/1.4 monospace;white-space:nowrap">{lbl}</span>'

def sys_cell(d):
    lab = d['label'] or '—'; gto = d['gto_label'] or '—'
    ev = f" · EV {d['ev_loss_bb']:.2f}bb" if d['ev_loss_bb'] not in (None,'') and float(d['ev_loss_bb'] or 0)!=0 else ''
    best = d['best_action'] or '—'
    act = esc(d['action_taken'])
    return f'<b>{act}</b> → veredito <b>{esc(lab)}</b> · GTO {esc(gto)} · sugere <b>{esc(best)}</b>{ev}'

parts = []
for hid in sorted(by_hand):
    hrows = [r for r in rows if r[0]['hand_id']==hid]
    # mostra só mãos com ALGUMA anotação ou erro do sistema (todas as mãos relevantes)
    if not any(r[1] for r in hrows) and not any(r[4] for r in hrows):
        continue
    d0 = hrows[0][0]
    hnum = int(hid) - 100000000
    cards = esc(d0['hero_cards']); pos = esc(d0['position'])
    decrows = ''
    for d, ann, kind, rec, sysm in hrows:
        if not ann and kind=='sem_anotacao' and not sysm:
            continue
        comment = esc(ann['comment']) if ann else '<i style="color:#475569">— sem comentário —</i>'
        recstr = f' <span style="color:#2DD4BF">[coach: {esc(rec)}]</span>' if rec else ''
        decrows += f'''<tr>
          <td style="padding:8px 10px;border-top:1px solid #1e293b;color:#cbd5e1;white-space:nowrap;font:600 12px monospace">{esc(d['street'])}</td>
          <td style="padding:8px 10px;border-top:1px solid #1e293b;color:#94a3b8;font-size:12.5px">{sys_cell(d)}</td>
          <td style="padding:8px 10px;border-top:1px solid #1e293b;color:#e2e8f0;font-size:13px">{comment}{recstr}</td>
          <td style="padding:8px 10px;border-top:1px solid #1e293b;text-align:right">{badge(kind)}</td>
        </tr>'''
    parts.append(f'''<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;margin:14px 0;overflow:hidden">
      <div style="padding:10px 14px;background:#111c30;border-bottom:1px solid #1e293b;display:flex;gap:12px;align-items:baseline">
        <span style="font:700 15px 'Chakra Petch',monospace;color:#2DD4BF">Mão #{hnum}</span>
        <span style="color:#e2e8f0;font:600 14px monospace">{cards}</span>
        <span style="color:#64748b;font-size:12px">{pos}</span>
      </div>
      <table style="width:100%;border-collapse:collapse">{decrows}</table>
    </div>''')

def cal_list(items, color):
    out = ''
    for d, ann, kind, rec, sysm in items:
        hnum = int(d['hand_id'])-100000000
        cards = esc(d['hero_cards']); st = esc(d['street']); act = esc(d['action_taken'])
        lab = esc(d['label']); gto = esc(d['gto_label']); cm = esc((ann['comment'] or '')[:120])
        out += (f'<li style="margin:6px 0;color:#cbd5e1;font-size:13px">'
                f'<b style="color:{color}">#{hnum} {cards}</b> {st}/{act}: sistema diz <b>{lab}</b>/{gto}, '
                f'coach recomenda <b>{esc(rec)}</b>. <span style="color:#94a3b8">{cm}</span></li>')
    return out or '<li style="color:#475569">(nenhum)</li>'

# padrões de calibragem (agrupa divergências por street + severidade)
rig_street = Counter(r[0]['street'] for r in rigido)
per_street = Counter(r[0]['street'] for r in perdido)
# rígidos que NÓS chamamos de erro GRAVE (severidade clear_mistake) mas o coach aprova.
# 'grave' = a SEVERIDADE (label), não o gto_label (frequência do solver, mantida intacta).
rig_grave = [r for r in rigido if r[0]['label']=='clear_mistake']
rig_pre = sum(1 for r in rigido if r[0]['street']=='preflop')
per_pre = sum(1 for r in perdido if r[0]['street']=='preflop')
sustenta = cnt['match_erro']   # coach confirma um erro que NÓS flagamos

doc = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coach × GrindLab — Torneio #27</title>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#0A0E1A;color:#E3E8EC;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 18px 80px}}h1{{font-family:'Chakra Petch',monospace;color:#2DD4BF;font-size:26px;margin:0 0 4px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}}
.card{{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:14px}}.k{{font:700 26px 'Chakra Petch',monospace;color:#2DD4BF}}.kl{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
h2{{font-family:'Chakra Petch',monospace;color:#E3E8EC;font-size:18px;margin:30px 0 6px;border-bottom:1px solid #1e293b;padding-bottom:6px}}</style></head>
<body><div class="wrap">
<h1>Coach × GrindLab — Torneio #27</h1>
<p style="color:#94a3b8;margin:0 0 6px">Fonte: anotações do coach no replayer (fonte única) × verdictos atuais do engine. Comparação por mão.</p>
<div class="cards">
  <div class="card"><div class="k">{len(by_hand)}</div><div class="kl">mãos</div></div>
  <div class="card"><div class="k">{n_ann}</div><div class="kl">decisões comentadas</div></div>
  <div class="card"><div class="k" style="color:#2DD4BF">{align}%</div><div class="kl">alinhamento (match)</div></div>
  <div class="card"><div class="k" style="color:#38bdf8">{sustenta}</div><div class="kl">sustentam nossa decisão</div></div>
  <div class="card"><div class="k" style="color:#f59e0b">{cnt['diverge_rigido']}</div><div class="kl">diverge · rígidos</div></div>
  <div class="card"><div class="k" style="color:#ef4444">{cnt['diverge_perdido']}</div><div class="kl">diverge · perdidos</div></div>
</div>
<p style="color:#64748b;font-size:12.5px">De {n_compar} decisões comparáveis: <b style="color:#2DD4BF">{n_match} match</b> ({cnt['match_ok']} ambos aprovam + <b style="color:#38bdf8">{cnt['match_erro']} ambos apontam o mesmo erro = coach SUSTENTA nossa decisão</b>) · {cnt['diverge_rigido']+cnt['diverge_perdido']} divergências · {cnt['comentario']} comentários sem ação clara (mostrados, não comparados).</p>

<h2>Pontos de calibragem — como chegar mais perto do coach</h2>
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:12px 16px;margin:8px 0 16px">
<p style="color:#cbd5e1;font-size:13px;margin:4px 0"><b style="color:#f59e0b">1. Estamos severos demais em spots agressivos/curtos preflop + sizing.</b> Dos {len(rigido)} casos que flagamos e o coach aprova, <b style="color:#ef4444">{len(rig_grave)} foram chamados por nós de erro GRAVE</b> (clear_mistake/critical) — reshoves, folds vs 4-bet, 3-bets marginais que o coach considera linha padrão. Ação: rebaixar severidade desses spots (já em curso na recalibração por EV). {rig_pre} dos {len(rigido)} são preflop.</p>
<p style="color:#cbd5e1;font-size:13px;margin:4px 0"><b style="color:#ef4444">2. O coach joga mais tight/exploit que o GTO baseline.</b> Dos {len(perdido)} casos que ele aponta e nós aprovamos, {per_pre} são preflop (folda mãos marginais como A6s, set-mine, calls/folds por read). <b>Cuidado:</b> nem todos são bug nosso — muitos são preferência EXPLOITATIVA do coach (vs recreativo/nit) que o GTO não modela. Não tightem cego rumo a ele; revise caso a caso quais são leak real vs exploit.</p>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
<div>
  <h3 style="color:#f59e0b;font-size:15px">⚠️ Rígidos demais ({len(rigido)}) — nós flagamos, coach aprova</h3>
  <p style="color:#94a3b8;font-size:12.5px">RELAXAR. {len(rig_grave)} chamados de erro grave. Por street: {dict(rig_street)}</p>
  <ul style="padding-left:18px;margin:6px 0">{cal_list(rigido,'#f59e0b')}</ul>
</div>
<div>
  <h3 style="color:#ef4444;font-size:15px">🔴 Coach aponta, nós aprovamos ({len(perdido)})</h3>
  <p style="color:#94a3b8;font-size:12.5px">REVISAR (leak real vs exploit do coach). Por street: {dict(per_street)}</p>
  <ul style="padding-left:18px;margin:6px 0">{cal_list(perdido,'#ef4444')}</ul>
</div>
</div>

<h2>Todas as mãos</h2>
{''.join(parts)}
</div></body></html>'''

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(doc)
c.close()
print('HTML:', OUT)
print(f'mãos: {len(by_hand)} | comentadas: {n_ann} | alinhamento: {align}% '
      f'| match: {n_match} | rígidos: {cnt["diverge_rigido"]} | perdidos: {cnt["diverge_perdido"]} | comentário: {cnt["comentario"]}')
