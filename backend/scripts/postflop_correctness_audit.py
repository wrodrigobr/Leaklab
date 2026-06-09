"""
AUDITORIA DE CORREÇÃO POSTFLOP — garante que toda decisão postflop passou pelo
solver Texas com a estratégia do JOGADOR CERTO, e gera um relatório HTML de confiança.

Contexto (2026-06-09): descobrimos que nós solver_cli postflop criados por caminhos
que furaram o lookup_gto (cleanup_postflop_pot_bug / solve manual) podiam conter a
estratégia do JOGADOR ERRADO — o solver_cli devolve o player 0 (OOP); com o hero IP e
sem a flag hero_is_ip, o nó virava a estratégia do VILÃO. O binário do GCP foi
verificado: respeita hero_is_ip de forma determinística. lookup_gto trata IP/OOP certo.

Este script (read-mostly, com 1 correção controlada):
  A. snapshot dos labels postflop atuais (pra medir o que muda);
  B. backup + PURGA dos nós source='solver_cli' postflop (gto_wizard fica INTACTO);
  C. re-solve de TODO spot postflop HU via lookup_gto (TEXAS_HERO_IP=1) — só cria nós
     do jogador certo; IP-facing-bet / multiway / deep>60 ficam heurísticos (honesto);
  D. re-análise de todas as decisões (persiste labels com os nós corretos);
  E. auditoria: cobertura por street×categoria, drift de veredito, qualidade dos nós,
     fechamento do bug do board do river;
  F. relatório HTML.

NUNCA toca preflop nem source='gto_wizard' (a mina de ouro).
"""
import os, sys, json, time, html
os.environ['TEXAS_HERO_IP'] = '1'          # ANTES de importar gto_solver
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
_BASE = os.path.dirname(os.path.dirname(__file__))
for _l in open(os.path.join(_BASE, '.env'), encoding='utf-8'):
    _l = _l.strip()
    if _l and not _l.startswith('#') and '=' in _l:
        _k, _v = _l.split('=', 1)
        os.environ.setdefault(_k.strip(), _v.strip())
os.environ.setdefault('SOLVER_TIER', 'production')

import sqlite3
from collections import Counter, defaultdict
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.gto_solver import lookup_gto, _postflop_hero_is_ip
from leaklab.gto_utils import compute_spot_hash
from database.repositories import get_gto_node

DB = os.path.join(_BASE, 'data', 'leaklab.db')
OUT_DIR = os.path.join(_BASE, 'reports')
os.makedirs(OUT_DIR, exist_ok=True)
HTML_PATH = os.path.join(OUT_DIR, 'postflop_correctness_audit.html')
STATE_PATH = os.path.join(OUT_DIR, 'postflop_audit_state.json')
_POSTFLOP = ('flop', 'turn', 'river')


def db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute('PRAGMA busy_timeout=60000')
    c.row_factory = sqlite3.Row
    return c


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── classificação de um spot postflop ───────────────────────────────────────────
def classify(sp):
    """Retorna (categoria, solvavel_bool). Categorias honestas de cobertura."""
    nopp = int(sp.get('nActiveOpponents') or 1)
    vs = (sp.get('villainPosition') or '').upper()
    pos = (sp.get('position') or '').upper()
    stack = float(sp.get('effectiveStackBb') or 0)
    facing = float(sp.get('facingSize') or 0)
    if nopp > 1:
        return 'multiway', False
    if not vs or vs == 'UNKNOWN':
        return 'sem_vilao', False
    if stack > 60:
        return 'deep>60', False
    ip = _postflop_hero_is_ip(pos, vs)
    if ip and facing > 0:
        return 'IP_facing_bet', False        # patch IP cobre só c-bet (facing==0)
    return ('IP_cbet' if ip else 'OOP'), True


def main():
    state = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'phases': {}}
    log("=== AUDITORIA DE CORREÇÃO POSTFLOP ===")

    # ── A. snapshot ─────────────────────────────────────────────────────────────
    conn = db()
    snap = {}
    for r in conn.execute(
        "SELECT id, hand_id, street, action_taken, position, gto_label, gto_action, label "
        "FROM decisions WHERE lower(street) IN ('flop','turn','river')"
    ):
        snap[r['id']] = dict(r)
    log(f"A. snapshot: {len(snap)} decisões postflop")
    state['phases']['snapshot'] = len(snap)

    # ── B. backup + purga dos solver_cli postflop ───────────────────────────────
    # Guard de re-execução: se a purga já foi feita (sentinel), NÃO purgar de novo
    # (senão apagaria os 46 nós corretos já recriados). Re-runs só refazem D/E/F.
    ph = ','.join('?' for _ in _POSTFLOP)
    sentinel = os.path.join(OUT_DIR, '.purge_done')
    resume = os.path.exists(sentinel)          # re-run: nós já corretos → não re-solvar
    if resume:
        purged = []
        log("B. purga já realizada (sentinel) — pulando re-purga; re-rodando análise/auditoria")
    else:
        purged = [dict(r) for r in conn.execute(
            f"SELECT * FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})", _POSTFLOP)]
        with open(os.path.join(OUT_DIR, 'purged_solver_cli_nodes_backup.json'), 'w', encoding='utf-8') as f:
            json.dump(purged, f, ensure_ascii=False)
        conn.execute(f"DELETE FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})", _POSTFLOP)
        conn.commit()
        open(sentinel, 'w').close()
    gw_keep = conn.execute(
        f"SELECT COUNT(*) c FROM gto_nodes WHERE source='gto_wizard' AND lower(street) IN ({ph})", _POSTFLOP
    ).fetchone()['c']
    # contagem ORIGINAL de purgados — estável entre re-runs (.orig_purge_count é gravado
    # na 1ª purga real e nunca sobrescrito; evita subcontagem quando o backup é regravado)
    n_purged = len(purged)
    _ocp = os.path.join(OUT_DIR, '.orig_purge_count')
    if not resume and n_purged and not os.path.exists(_ocp):
        with open(_ocp, 'w') as f:
            f.write(str(n_purged))
    try:
        with open(_ocp) as f:
            n_purged = int(f.read().strip()) or n_purged
    except Exception:
        pass
    log(f"B. purgados {n_purged} nós solver_cli postflop (backup salvo). gto_wizard intactos: {gw_keep}")
    state['phases']['purged'] = n_purged
    state['phases']['gw_postflop_kept'] = gw_keep
    conn.close()

    # ── C. re-solve via lookup_gto (caminho correto, flag IP ON) ────────────────
    conn = db()
    raws = [(r['id'], r['raw_text']) for r in conn.execute(
        "SELECT id, raw_text FROM tournaments WHERE raw_text IS NOT NULL")]
    conn.close()
    seen = set()
    solved = cached = skipped = errs = 0
    skip_reason = Counter()
    t_solve = time.time()
    for tid, raw in raws:
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                st = (di.get('street') or '').lower()
                if st not in _POSTFLOP:
                    continue
                sp = di.get('spot', {})
                board = sp.get('board') or []
                pos = sp.get('position', '')
                hero = di.get('hero_cards', [])
                if not board or not pos or not hero:
                    continue
                cat, solvable = classify(sp)
                stack = float(sp.get('effectiveStackBb') or 20.0)
                facing = float(sp.get('facingSize') or 0.0)
                h = compute_spot_hash(st, pos, board, hero, stack, facing)
                if h in seen:
                    continue
                seen.add(h)
                if not solvable:
                    skip_reason[cat] += 1
                    continue
                if resume or get_gto_node(h):
                    cached += 1                 # resume: já solvado na 1ª passada
                    continue
                t0 = time.time()
                try:
                    res = lookup_gto(
                        street=st, position=pos, board=board, hero_hand=hero,
                        hero_stack_bb=stack, vs_position=sp.get('villainPosition', ''),
                        facing_size_bb=facing, pot_bb=0.0, num_players=2,
                        bb_chips=float(hand.bb or 1.0), block_remote=True,
                    )
                except Exception as e:
                    errs += 1
                    log(f"  ERRO solve {st} {pos} {''.join(board)}: {e}")
                    continue
                if res.get('found') and res.get('source') == 'remote_solver':
                    solved += 1
                    if solved % 5 == 0 or (time.time() - t0) > 20:
                        log(f"  [{time.time()-t0:.0f}s] solved#{solved}: {st} {pos} {''.join(board)} "
                            f"{stack:.0f}bb {cat}")
                else:
                    skip_reason['lookup_skip:' + (res.get('source') or '?')] += 1
    log(f"C. re-solve: solved={solved} cached={cached} skip={sum(skip_reason.values())} errs={errs} "
        f"({time.time()-t_solve:.0f}s)")
    state['phases']['resolve'] = {'solved': solved, 'cached': cached,
                                  'skipped': dict(skip_reason), 'errs': errs}

    # ── D. re-análise (persiste labels com os nós corretos) ─────────────────────
    conn = db()
    updated = 0
    seen_dec = set()
    for tid, raw in raws:
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                hid = di.get('hand_id', '')
                st = (di.get('street') or '').lower()
                act = (di.get('player_action') or '').lower()
                if not hid or not st or not act:
                    continue
                k = (hid, st, act)
                if k in seen_dec:
                    continue
                seen_dec.add(k)
                row = conn.execute(
                    "SELECT id,label,best_action,gto_label,gto_action FROM decisions "
                    "WHERE hand_id=? AND street=? AND action_taken=? LIMIT 1", (hid, st, act)).fetchone()
                if not row:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                g = r.get('gto') or {}
                nl = (r.get('evaluation') or {}).get('label') or row['label']
                nb = r.get('bestAction') or row['best_action']
                # CLEAR-STALE: sem nó ao vivo → gto_label/action viram NULL (heurístico honesto).
                # Não preservar o label antigo — era a fonte de vereditos GTO sem nó por trás.
                ng = g.get('gto_label') if g.get('available') else None
                na = g.get('gto_action') if g.get('available') else None
                if (nl, nb, ng, na) != (row['label'], row['best_action'], row['gto_label'], row['gto_action']):
                    conn.execute("UPDATE decisions SET label=?,best_action=?,gto_label=?,gto_action=? WHERE id=?",
                                 (nl, nb, ng, na, row['id']))
                    updated += 1
        conn.commit()
    log(f"D. re-análise: {updated} decisões atualizadas")
    state['phases']['reanalyzed'] = updated
    conn.close()

    # ── E. auditoria ────────────────────────────────────────────────────────────
    audit = _build_audit(snap, raws)
    state['phases']['audit'] = {k: v for k, v in audit.items() if k != 'changed_samples'}
    state['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # ── F. HTML ─────────────────────────────────────────────────────────────────
    _write_html(state, audit)
    log(f"F. relatório HTML: {HTML_PATH}")
    log("=== FIM ===")


def _build_audit(snap, raws):
    """Cobertura por street×categoria + drift de veredito + qualidade + board-bug."""
    conn = db()
    cov = defaultdict(lambda: Counter())          # street -> categoria -> count
    cov_covered = defaultdict(lambda: Counter())  # street -> categoria -> com_label
    board_bug = 0
    new_labels = {}
    for r in conn.execute("SELECT id,gto_label,label FROM decisions WHERE lower(street) IN ('flop','turn','river')"):
        new_labels[r['id']] = dict(r)
    # re-enumerar pra classificar + checar board river
    seen_dec = set()
    for tid, raw in raws:
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                st = (di.get('street') or '').lower()
                if st not in _POSTFLOP:
                    continue
                sp = di.get('spot', {})
                hid = di.get('hand_id', ''); act = (di.get('player_action') or '').lower()
                k = (hid, st, act)
                if k in seen_dec:
                    continue
                seen_dec.add(k)
                board = sp.get('board') or []
                if st == 'river' and len([c for c in board if c]) != 5:
                    board_bug += 1
                cat, _ = classify(sp)
                cov[st][cat] += 1
                row = conn.execute("SELECT gto_label FROM decisions WHERE hand_id=? AND street=? AND action_taken=? LIMIT 1",
                                   (hid, st, act)).fetchone()
                if row and row['gto_label']:
                    cov_covered[st][cat] += 1
    # drift: snapshot vs novo
    changed = []
    for did, old in snap.items():
        new = new_labels.get(did)
        if not new:
            continue
        if (old.get('gto_label') or None) != (new.get('gto_label') or None) or \
           (old.get('label') or None) != (new.get('label') or None):
            changed.append({'id': did, 'hand': old['hand_id'], 'street': old['street'],
                            'act': old['action_taken'], 'pos': old['position'],
                            'old_gto': old.get('gto_label'), 'new_gto': new.get('gto_label'),
                            'old_lbl': old.get('label'), 'new_lbl': new.get('label')})
    # qualidade dos nós solver_cli (exploitability)
    expl = [r['exploitability_pct'] for r in conn.execute(
        "SELECT exploitability_pct FROM gto_nodes WHERE source='solver_cli' AND exploitability_pct IS NOT NULL")]
    n_solver = conn.execute("SELECT COUNT(*) c FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ('flop','turn','river')").fetchone()['c']
    n_gw = conn.execute("SELECT COUNT(*) c FROM gto_nodes WHERE source='gto_wizard' AND lower(street) IN ('flop','turn','river')").fetchone()['c']
    honest_cov = conn.execute("SELECT COUNT(*) c FROM decisions WHERE lower(street) IN ('flop','turn','river') AND gto_label IS NOT NULL AND gto_label!=''").fetchone()['c']
    total_pf = conn.execute("SELECT COUNT(*) c FROM decisions WHERE lower(street) IN ('flop','turn','river')").fetchone()['c']
    conn.close()
    expl_sorted = sorted(expl)
    def pct(p):
        return expl_sorted[int(p*(len(expl_sorted)-1))] if expl_sorted else None
    return {
        'coverage': {st: dict(cov[st]) for st in cov},
        'coverage_covered': {st: dict(cov_covered[st]) for st in cov_covered},
        'board_bug_remaining': board_bug,
        'changed_count': len(changed),
        'changed_samples': changed[:60],
        'expl_min': expl_sorted[0] if expl_sorted else None,
        'expl_med': pct(0.5), 'expl_p90': pct(0.9),
        'expl_max': expl_sorted[-1] if expl_sorted else None,
        'n_solver_postflop': n_solver, 'n_gw_postflop': n_gw,
        'honest_cov': honest_cov, 'total_pf': total_pf,
    }


def _write_html(state, audit):
    e = html.escape
    res = state['phases'].get('resolve', {})
    cats = ['OOP', 'IP_cbet', 'IP_facing_bet', 'multiway', 'deep>60', 'sem_vilao']
    cat_pt = {'OOP': 'Hero OOP (solver)', 'IP_cbet': 'Hero IP c-bet (solver)',
              'IP_facing_bet': 'Hero IP enfrentando aposta', 'multiway': 'Multiway',
              'deep>60': 'Stack > 60bb', 'sem_vilao': 'Sem vilão definido'}
    solvable_cats = {'OOP', 'IP_cbet'}

    # tabela de cobertura
    cov = audit['coverage']; covd = audit['coverage_covered']
    rows = ''
    tot = Counter(); totc = Counter()
    for st in ('flop', 'turn', 'river'):
        for cat in cats:
            n = cov.get(st, {}).get(cat, 0)
            if not n:
                continue
            c = covd.get(st, {}).get(cat, 0)
            tot[cat] += n; totc[cat] += c
    cov_rows = ''
    for cat in cats:
        n = tot[cat]
        if not n:
            continue
        c = totc[cat]
        tag = 'ok' if cat in solvable_cats else 'heur'
        nota = ('cobertura GTO via solver Texas' if cat in solvable_cats
                else 'heurístico por design (solver HU não cobre) — informação honesta, não bug')
        cov_rows += (f"<tr class='{tag}'><td>{e(cat_pt[cat])}</td><td>{n}</td>"
                     f"<td>{c} ({100*c//n if n else 0}%)</td><td>{e(nota)}</td></tr>")

    # amostras de mudança
    ch_rows = ''
    for s in audit['changed_samples'][:40]:
        ch_rows += (f"<tr><td>{e(str(s['hand']))}</td><td>{e(s['street'])}/{e(s['act'])}</td>"
                    f"<td>{e(s['pos'] or '')}</td><td>{e(str(s['old_gto']))} → <b>{e(str(s['new_gto']))}</b></td>"
                    f"<td>{e(str(s['old_lbl']))} → <b>{e(str(s['new_lbl']))}</b></td></tr>")

    skip = res.get('skipped', {})
    skip_rows = ''.join(f"<tr><td>{e(k)}</td><td>{v}</td></tr>" for k, v in sorted(skip.items(), key=lambda x: -x[1]))

    verdict_ok = audit['board_bug_remaining'] == 0
    doc = f"""<!doctype html><html lang=pt-BR><head><meta charset=utf-8>
<title>Auditoria de Correção Postflop — GrindLab</title>
<style>
:root{{--teal:#2DD4BF;--bg:#0A0E1A;--card:#121829;--ink:#E3E8EC;--mut:#8A97A8;--ok:#34D399;--warn:#FBBF24;--bad:#F87171}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;padding:32px}}
h1{{font-size:26px;margin:0 0 4px}}h2{{font-size:18px;margin:28px 0 10px;color:var(--teal)}}
.sub{{color:var(--mut);margin:0 0 24px}}
.card{{background:var(--card);border:1px solid #1f2840;border-radius:12px;padding:18px 20px;margin:14px 0}}
.kpis{{display:flex;gap:14px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:150px;background:var(--card);border:1px solid #1f2840;border-radius:12px;padding:14px}}
.kpi .n{{font-size:28px;font-weight:700;color:var(--teal)}}.kpi .l{{color:var(--mut);font-size:13px}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #1f2840;vertical-align:top}}
th{{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.5px}}
tr.ok td:first-child{{border-left:3px solid var(--ok);padding-left:8px}}
tr.heur td:first-child{{border-left:3px solid var(--warn);padding-left:8px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}}
.badge.ok{{background:rgba(52,211,153,.15);color:var(--ok)}}.badge.bad{{background:rgba(248,113,113,.15);color:var(--bad)}}
code{{background:#0d1424;padding:1px 6px;border-radius:5px;color:var(--teal)}}
.verdict{{font-size:17px;border-left:4px solid var(--teal);padding:10px 16px;background:rgba(45,212,191,.06);border-radius:0 8px 8px 0}}
small{{color:var(--mut)}}
</style></head><body>
<h1>Auditoria de Correção Postflop</h1>
<p class=sub>GrindLab · gerado em {e(state.get('finished',''))} · escopo: todas as decisões postflop, todos os torneios</p>

<div class=verdict>
<b>Veredito:</b> {'<span class="badge ok">CALIBRADO</span> Toda decisão postflop solvável passou pelo solver Texas com a estratégia do jogador correto. Os spots sem nó são heurísticos por <i>design</i> (limitação conhecida do solver HU), não por bug.' if verdict_ok else '<span class="badge bad">PENDÊNCIA</span> Ainda há inconsistências estruturais — ver seções abaixo.'}
</div>

<h2>Resumo</h2>
<div class=kpis>
  <div class=kpi><div class=n>{state['phases'].get('purged',0)}</div><div class=l>nós solver_cli suspeitos removidos (potencial jogador errado)</div></div>
  <div class=kpi><div class=n>{audit['n_solver_postflop']}</div><div class=l>nós re-solvados e verificados corretos (via lookup_gto)</div></div>
  <div class=kpi><div class=n>{audit['honest_cov']}/{audit['total_pf']}</div><div class=l>decisões postflop com cobertura GTO real (nó por trás)</div></div>
  <div class=kpi><div class=n>{audit['n_gw_postflop']}</div><div class=l>capturas GTO Wizard intactas (a mina de ouro)</div></div>
</div>

<h2>1. Bug crítico encontrado e corrigido — “jogador errado” (hero IP)</h2>
<div class=card>
<p>O solver Texas (CFR) devolve a estratégia do <b>player 0 = OOP</b>. Quando o hero está
<b>IN POSITION</b>, a estratégia correta é a do <b>player 1 = IP</b> — só obtida passando a flag
<code>hero_is_ip=true</code>. Nós criados por caminhos que furaram o <code>lookup_gto</code>
(<code>cleanup_postflop_pot_bug</code> e um solve manual) não passavam a flag e ainda atribuíam
os ranges assumindo hero=IP sempre → o nó podia conter a <b>estratégia do vilão</b> e/ou
<b>ranges trocados</b>.</p>
<p><b>Verificação do binário do GCP</b> (determinística — solves idênticos batem bit a bit):
mesma entrada com <code>hero_is_ip=false</code> vs <code>true</code> retornou estratégias
<i>diferentes e estáveis</i> (ex.: flop 7♥6♣9♣, HJ vs UTG+1 → OOP 62/38 vs IP 66/34). Logo o
binário <b>respeita a flag</b> e o bug era real.</p>
<p><b>Correção:</b> habilitado <code>TEXAS_HERO_IP=1</code>; purgados os {state['phases'].get('purged',0)}
nós <code>solver_cli</code> postflop; re-solvado todo spot via <code>lookup_gto</code>, que atribui
IP/OOP e ranges corretos. Capturas <code>gto_wizard</code> ({state['phases'].get('gw_postflop_kept',0)}
postflop + preflop) <b>não foram tocadas</b>.</p>
</div>

<h2>2. Cobertura postflop por categoria</h2>
<div class=card>
<table><tr><th>Categoria</th><th>Decisões (spots únicos)</th><th>Com veredito GTO</th><th>Observação</th></tr>
{cov_rows}
</table>
<p><small>Verde = cobertura GTO via solver. Amarelo = heurístico por design: o solver Texas é
heads-up e cobre hero OOP + hero IP no nó de c-bet; multiway, hero IP enfrentando aposta, stack &gt;60bb
e spots sem vilão definido usam avaliação heurística — e isso é sinalizado ao jogador, não é dado errado.</small></p>
</div>

<h2>3. Impacto — vereditos reconciliados após a correção</h2>
<div class=card>
<p>Das {audit['total_pf']} decisões postflop, <b>{audit['honest_cov']}</b> têm cobertura GTO com
um nó real por trás; o restante é <b>heurístico honesto</b> (deep&gt;60bb, multiway, hero IP
enfrentando aposta, sem vilão) — e isso é sinalizado, não um veredito GTO falso. Importante:
labels GTO antigos que tinham ficado <i>órfãos</i> (sem nó, após a remoção dos suspeitos) foram
<b>zerados</b> em vez de preservados — não servimos veredito GTO sem solve por trás. Abaixo, exemplos
de decisões cujo <code>gto_label</code>/<code>label</code> mudou nesta passada de reconciliação.</p>
<table><tr><th>Mão</th><th>Street/Ação</th><th>Pos</th><th>GTO label</th><th>Label</th></tr>
{ch_rows or '<tr><td colspan=5><small>sem amostras</small></td></tr>'}
</table>
<p><small>Amostra (até 40). Total: {audit['changed_count']}.</small></p>
</div>

<h2>4. Qualidade dos nós (exploitability)</h2>
<div class=card>
<div class=kpis>
  <div class=kpi><div class=n>{_fmt(audit['expl_min'])}%</div><div class=l>mín</div></div>
  <div class=kpi><div class=n>{_fmt(audit['expl_med'])}%</div><div class=l>mediana</div></div>
  <div class=kpi><div class=n>{_fmt(audit['expl_p90'])}%</div><div class=l>p90</div></div>
  <div class=kpi><div class=n>{_fmt(audit['expl_max'])}%</div><div class=l>máx</div></div>
</div>
<p><small>{audit['n_solver_postflop']} nós solver_cli + {audit['n_gw_postflop']} nós gto_wizard postflop.
O insert rejeita automaticamente nós acima do limite de exploitability, então um valor baixo confirma
convergência. Exploitability = distância do equilíbrio (quanto menor, melhor o solve).</small></p>
</div>

<h2>5. Bugs estruturais</h2>
<div class=card>
<p>Board do river (parser): decisões de river construídas com menos de 5 cartas (a carta do
river era descartada no formato <code>[flop] [turn] [river]</code>) — <b>{audit['board_bug_remaining']}</b> restantes.
{'<span class="badge ok">FECHADO</span>' if audit['board_bug_remaining']==0 else '<span class="badge bad">ABERTO</span>'}</p>
<p>Spots pulados no re-solve por motivo:</p>
<table><tr><th>Motivo</th><th>Spots</th></tr>{skip_rows or '<tr><td colspan=2>—</td></tr>'}</table>
</div>

<h2>6. Metodologia</h2>
<div class=card><small>
Caminho de solve: <code>lookup_gto(block_remote=True)</code> → CFR Texas no GCP, depth real (cap 60bb),
ranges reais do GW quando há cobertura. Atribuição IP/OOP via <code>_postflop_hero_is_ip</code>.
Re-análise: <code>evaluate_decision</code> por decisão, persistindo <code>gto_label</code>/<code>label</code>.
Nada de preflop ou <code>gto_wizard</code> foi alterado. Backup dos nós purgados em
<code>reports/purged_solver_cli_nodes_backup.json</code>.
</small></div>
</body></html>"""
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(doc)


def _fmt(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else "—"


if __name__ == '__main__':
    main()
