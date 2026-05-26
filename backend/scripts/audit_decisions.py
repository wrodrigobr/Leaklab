"""
Fase 1 — Auditoria de decisões no banco.
Identifica anomalias sem modificar nenhum dado.

Uso:
    python scripts/audit_decisions.py
    python scripts/audit_decisions.py --samples 10   # mais exemplos por categoria
    python scripts/audit_decisions.py --csv           # salva relatorio em audit_report.csv
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.schema import get_conn
from leaklab.preflop_range_evaluator import _classify_range_zone, _recommended_action

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def pct(n, total):
    return f"{n/total*100:.1f}%" if total else "—"

def divider(char="-", width=70):
    print(char * width)

def header(title):
    divider("=")
    print(f"  {title}")
    divider("=")

def section(title):
    print()
    divider()
    print(f"  {title}")
    divider()

# -----------------------------------------------------------------------------
# Checks
# -----------------------------------------------------------------------------

def check_bb_fold_no_bet(conn, n_samples):
    """BB com facing_bet NULL/0 e best_action='fold' — bug confirmado (check é gratuito)."""
    rows = conn.execute("""
        SELECT id, hero_cards, stack_bb, score, label, action_taken, best_action,
               facing_bet, pot_size, position
        FROM decisions
        WHERE position IN ('BB')
          AND (facing_bet IS NULL OR facing_bet = 0)
          AND best_action = 'fold'
        ORDER BY score DESC
    """).fetchall()
    return rows

def check_sb_fold_no_bet(conn):
    """SB com facing_bet NULL/0 e best_action='fold'. SB pode foldar a blind (correto),
       mas vale revisar mãos fortes que foram marcadas como fold."""
    rows = conn.execute("""
        SELECT id, hero_cards, stack_bb, score, action_taken, best_action, facing_bet
        FROM decisions
        WHERE position = 'SB'
          AND (facing_bet IS NULL OR facing_bet = 0)
          AND best_action = 'fold'
        ORDER BY score DESC
    """).fetchall()
    return rows

def check_score_vs_action_mismatch(conn):
    """action_taken == best_action mas score alto (>0.35): scoring bug.
       Acao estava certa, mas o engine puniu com score alto de qualquer forma."""
    rows = conn.execute("""
        SELECT id, street, position, action_taken, best_action,
               ROUND(score,4) score, label, facing_bet, hero_cards
        FROM decisions
        WHERE action_taken = best_action AND score > 0.35
        ORDER BY score DESC
    """).fetchall()
    return rows

def check_wrong_action_low_score(conn):
    """action_taken != best_action mas score < 0.02 e label=standard.
       Engine diz que a acao foi errada mas nao penalizou — inconsistente."""
    rows = conn.execute("""
        SELECT id, street, position, action_taken, best_action,
               ROUND(score,4) score, label, facing_bet, hero_cards, stack_bb
        FROM decisions
        WHERE action_taken != best_action
          AND score < 0.02
          AND label = 'standard'
        ORDER BY street, position
    """).fetchall()
    return rows

def check_engine_regression(conn):
    """Re-evalua best_action com o engine atual e detecta divergencias.
       Identifica decisoes onde o engine atual discordaria do valor gravado."""
    rows = conn.execute("""
        SELECT id, street, position, hero_cards, action_taken, best_action,
               facing_bet, stack_bb, icm_pressure, score, label
        FROM decisions
        WHERE street = 'preflop'
        ORDER BY id
    """).fetchall()

    divergences = []
    for r in rows:
        cards    = r['hero_cards'] or ''
        pos      = r['position'] or ''
        facing   = float(r['facing_bet'] or 0)
        stored   = r['best_action'] or ''

        # BB especial: sem aposta = check sempre disponível
        if pos == 'BB' and facing == 0:
            reeval = 'check' if _classify_range_zone(cards) == 'outside_range' else 'raise'
        else:
            reeval = _recommended_action(cards, pos, facing_size=facing)

        if reeval != stored and stored != 'jam':  # jam é decisão de stack depth, não do range evaluator
            divergences.append({
                'id': r['id'], 'pos': pos, 'cards': cards,
                'stored': stored, 'reeval': reeval,
                'facing': facing, 'stack': r['stack_bb'],
                'action_taken': r['action_taken'], 'score': r['score'],
            })
    return divergences

def check_call_no_bet(conn):
    """action_taken='call' com facing_bet NULL — pipeline pode ter perdido o contexto."""
    rows = conn.execute("""
        SELECT id, street, position, hero_cards, action_taken, best_action,
               facing_bet, pot_size, stack_bb, score
        FROM decisions
        WHERE facing_bet IS NULL AND action_taken = 'call'
        ORDER BY street, position
    """).fetchall()
    return rows

def check_label_score_consistency(conn):
    """Verifica que label bate com o score.
       standard: score < 0.09 | marginal: 0.09-0.18 | small_mistake: 0.19-0.36 | clear_mistake: >0.36"""
    thresholds = {
        'standard':      (0.0,  0.09),
        'marginal':      (0.09, 0.19),
        'small_mistake': (0.19, 0.37),
        'clear_mistake': (0.37, 1.01),
    }
    mismatches = []
    rows = conn.execute("""
        SELECT id, street, position, label, ROUND(score,4) score, action_taken, best_action
        FROM decisions WHERE label IS NOT NULL
    """).fetchall()
    for r in rows:
        lo, hi = thresholds.get(r['label'], (0, 1))
        if not (lo <= r['score'] < hi):
            mismatches.append(dict(r))
    return mismatches

# -----------------------------------------------------------------------------
# Overview stats
# -----------------------------------------------------------------------------

def print_overview(conn):
    section("VISÃO GERAL DO BANCO")

    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    print(f"  Total de decisões: {total}")
    print()

    print("  Por street:")
    for r in conn.execute("SELECT street, COUNT(*) n FROM decisions GROUP BY street ORDER BY n DESC").fetchall():
        print(f"    {r[0]:10} {r[1]:5}  ({pct(r[1], total)})")

    print()
    print("  Por best_action:")
    for r in conn.execute("SELECT best_action, COUNT(*) n FROM decisions GROUP BY best_action ORDER BY n DESC").fetchall():
        print(f"    {r[0]:10} {r[1]:5}  ({pct(r[1], total)})")

    print()
    print("  Por label:")
    for r in conn.execute("SELECT label, COUNT(*) n FROM decisions GROUP BY label ORDER BY n DESC").fetchall():
        print(f"    {r[0]:20} {r[1]:5}  ({pct(r[1], total)})")

    print()
    print("  facing_bet:")
    null_c = conn.execute("SELECT COUNT(*) FROM decisions WHERE facing_bet IS NULL").fetchone()[0]
    pos_c  = conn.execute("SELECT COUNT(*) FROM decisions WHERE facing_bet > 0").fetchone()[0]
    zero_c = conn.execute("SELECT COUNT(*) FROM decisions WHERE facing_bet = 0").fetchone()[0]
    print(f"    NULL (sem aposta registrada): {null_c:5}  ({pct(null_c, total)})")
    print(f"    0 (aposta zero):              {zero_c:5}  ({pct(zero_c, total)})")
    print(f"    > 0 (aposta real):            {pos_c:5}  ({pct(pos_c, total)})")

# -----------------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=5, help='Exemplos por categoria')
    parser.add_argument('--csv', action='store_true', help='Salva relatorio em CSV')
    args = parser.parse_args()

    conn = get_conn()

    header("AUDITORIA DE DECISÕES — FASE 1")

    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    print_overview(conn)

    issues = []  # lista de (categoria, gravidade, count)

    # -- BUG 1: BB fold sem aposta ----------------------------------------------
    section("BUG 1 . BB fold sem aposta [CRITICO — fold impossivel no BB]")
    b1 = check_bb_fold_no_bet(conn, args.samples)
    print(f"  Afetados: {len(b1)} decisões  ({pct(len(b1), total)})")
    print(f"  Causa: facing_bet=NULL e position=BB e best_action='fold'.")
    print(f"  Impacto: Ghost Table e Sparring pedem fold quando check é gratuito.")
    print(f"  Fix: UPDATE best_action='check' onde (facing_bet IS NULL OR =0) AND position='BB'")
    print()
    print(f"  Amostras ({min(args.samples, len(b1))} de {len(b1)}):")
    for r in b1[:args.samples]:
        print(f"    id={r['id']:6}  {r['hero_cards']:5}  stack={r['stack_bb']:5.1f}bb  "
              f"action={r['action_taken']:6}  stored_best={r['best_action']:6}  "
              f"score={r['score']:.4f}  label={r['label']}")
    issues.append(("BB fold sem aposta", "CRITICO", len(b1)))

    # -- BUG 2: Score alto para acao correta --------------------------------------
    section("BUG 2 . Score alto (>0.35) para acao correta [SCORING BUG]")
    b2 = check_score_vs_action_mismatch(conn)
    print(f"  Afetados: {len(b2)} decisões  ({pct(len(b2), total)})")
    print(f"  Causa: action_taken == best_action mas score > 0.35.")
    print(f"  Impacto: Decisoes corretas aparecem como clear_mistake em alguns contextos.")
    print()
    for r in b2[:args.samples]:
        print(f"    id={r['id']:6}  {r['street']:7} {r['position']:6}  {r['hero_cards']:5}  "
              f"action={r['action_taken']:6}  score={r['score']:.4f}  label={r['label']}")
    issues.append(("Score alto para acao correta", "MEDIO", len(b2)))

    # -- BUG 3: Acao errada, score quase zero -------------------------------------
    section("BUG 3 . Acao errada mas score ~zero e label=standard [INCONSISTENCIA]")
    b3 = check_wrong_action_low_score(conn)
    print(f"  Afetados: {len(b3)} decisões  ({pct(len(b3), total)})")
    print(f"  Causa: action_taken != best_action mas score < 0.02 e label=standard.")
    print(f"  Impacto: Erros reais nao aparecem como erros nas análises.")
    print()
    for r in b3[:args.samples]:
        print(f"    id={r['id']:6}  {r['street']:7} {r['position']:6}  "
              f"action={r['action_taken']:6}  best={r['best_action']:6}  "
              f"score={r['score']:.4f}  facing={r['facing_bet']}")
    issues.append(("Acao errada score zero", "MEDIO", len(b3)))

    # -- BUG 4: Call sem facing_bet ------------------------------------------------
    section("BUG 4 . Call sem facing_bet registrado [PIPELINE / DADOS]")
    b4 = check_call_no_bet(conn)
    print(f"  Afetados: {len(b4)} decisões  ({pct(len(b4), total)})")
    print(f"  Causa: action_taken='call' mas facing_bet=NULL — pipeline nao capturou a aposta.")
    print(f"  Impacto: Contexto incompleto nas analises; getActionKeys mostra botoes errados.")
    print()
    for r in b4[:args.samples]:
        print(f"    id={r['id']:6}  {r['street']:7} {r['position']:6}  "
              f"action={r['action_taken']:6}  best={r['best_action']:6}  "
              f"facing={r['facing_bet']}  stack={r['stack_bb']:.1f}bb")
    issues.append(("Call sem facing_bet", "BAIXO", len(b4)))

    # -- Label vs Score consistency ------------------------------------------------
    section("CHECK . Consistencia label <-> score")
    b5 = check_label_score_consistency(conn)
    print(f"  Inconsistências encontradas: {len(b5)}")
    if b5:
        for r in b5[:args.samples]:
            print(f"    id={r['id']:6}  {r['street']:7} {r['position']:6}  "
                  f"label={r['label']:20}  score={r['score']:.4f}  "
                  f"action={r['action_taken']:6}  best={r['best_action']}")
    issues.append(("Label score inconsistente", "BAIXO", len(b5)))

    # -- Regressao: meu guard foi abrangente demais --------------------------------
    section("ATENCAO . Regressao no guard fold->check [CORRIGIR ANTES DA FASE 2]")
    print("  O guard adicionado em app.py e repositories.py muda fold->check para")
    print("  TODAS as posicoes quando facing_bet=NULL, incluindo UTG/HJ/CO/BTN.")
    print("  UTG com 82o preflop DEVE foldar (nao check). Check preflop nao existe")
    print("  para posicoes nao-BB. O guard precisa ser restrito a position='BB'.")
    print()

    # Quantas linhas nao-BB sao afetadas pelo guard incorreto:
    guard_affected = conn.execute("""
        SELECT COUNT(*) FROM decisions
        WHERE position NOT IN ('BB')
          AND (facing_bet IS NULL OR facing_bet = 0)
          AND best_action = 'fold'
    """).fetchone()[0]
    print(f"  Decisoes nao-BB afetadas pelo guard incorreto: {guard_affected}")
    print(f"  Dessas, o guard troca fold->check incorretamente em serve-time.")
    issues.append(("Guard fold->check muito abrangente", "CRITICO", guard_affected))

    # -- Engine re-evaluation divergences (preflop) -------------------------------
    section("ANALISE . Divergencias engine atual vs stored best_action [PREFLOP]")
    divs = check_engine_regression(conn)
    print(f"  Divergencias detectadas: {len(divs)}")
    if divs:
        # Agrupar por (stored, reeval)
        from collections import Counter
        pairs = Counter((d['stored'], d['reeval']) for d in divs)
        print("  Top divergencias (stored -> reeval):")
        for (s, r), cnt in pairs.most_common(10):
            print(f"    {s:8} -> {r:8}  {cnt:4} casos")
        print()
        print(f"  Amostras ({min(args.samples, len(divs))} de {len(divs)}):")
        for d in divs[:args.samples]:
            print(f"    id={d['id']:6}  {d['cards']:5}  {d['pos']:6}  "
                  f"stored={d['stored']:6}  reeval={d['reeval']:6}  "
                  f"facing={d['facing']:.1f}  stack={d['stack']:.1f}bb  "
                  f"action={d['action_taken']:6}  score={d['score']:.4f}")
    issues.append(("Divergencias engine preflop", "INFORMATIVO", len(divs)))

    # -- SB fold sem aposta (informativo) -----------------------------------------
    section("INFO . SB fold sem aposta [INFORMATIVO]")
    sb = check_sb_fold_no_bet(conn)
    print(f"  Total: {len(sb)} decisões")
    print(f"  SB pode foldar a blind legitimamente (nao e bug automatico).")
    print(f"  Verificar: ha maos fortes (AA, KK, AK) sendo recomendadas como fold?")
    strong = [r for r in sb if r['hero_cards'] and
              any(h in (r['hero_cards'] or '') for h in ['AA','KK','QQ','AK','AKs','AKo'])]
    print(f"  Maos fortes recomendadas como fold no SB: {len(strong)}")
    if strong:
        for r in strong[:3]:
            print(f"    {r['hero_cards']}  facing={r['facing_bet']}  best={r['best_action']}")
    issues.append(("SB fold sem aposta (informativo)", "INFORMATIVO", len(sb)))

    # -- Resumo final ---------------------------------------------------------------
    header("RESUMO — PRIORIDADE DE CORREÇÃO")
    print(f"  {'Categoria':<42} {'Gravidade':<12} {'Afetados':>8}")
    divider()
    for cat, grav, cnt in issues:
        mark = "[!!]" if grav == "CRITICO" else "[! ]" if grav == "MEDIO" else "[ ]" if grav == "BAIXO" else "[i]"
        print(f"  {mark} {cat:<40} {grav:<12} {cnt:>8}")
    divider()
    total_criticos = sum(c for _, g, c in issues if g == "CRITICO")
    total_medios   = sum(c for _, g, c in issues if g == "MEDIO")
    print(f"  Total criticos: {total_criticos}  |  Medios: {total_medios}")
    print()
    print("  PRÓXIMOS PASSOS (Fase 2):")
    print("  1. Restringir guard fold->check a position='BB' em app.py e repositories.py")
    print("  2. UPDATE decisions SET best_action='check' WHERE position='BB'")
    print("     AND (facing_bet IS NULL OR facing_bet=0) AND best_action='fold'")
    print("  3. Investigar Bug2 (score alto para acao correta) — possivel scoring bug")
    print("  4. Investigar Bug3 (acao errada score zero) — possivelmente alternativas validas")
    print()

    if args.csv:
        import csv
        out_path = os.path.join(os.path.dirname(__file__), 'audit_report.csv')
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['categoria', 'gravidade', 'afetados'])
            for cat, grav, cnt in issues:
                w.writerow([cat, grav, cnt])
        print(f"  CSV salvo em: {out_path}")

    conn.close()


if __name__ == '__main__':
    main()
