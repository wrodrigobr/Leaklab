"""Sweep dos nós postflop DEGENERADOS (bug do pot em fichas → all-in fake, exploit≈0.01,
ev_bb absurdo). É o `fix_hand_spots` EM ESCALA: itera TODAS as mãos, e pra cada spot postflop
cujo nó tem a assinatura degenerada, deleta e re-solva com o pot CORRETO (potBb da DECISÃO —
o nó sozinho guarda o pot errado). Dedup por spot_hash, idempotente e resumível (pula nó já
bom). NUNCA purga em massa: só toca hash degenerado que uma decisão real cobre.

Por que decision-driven: o pot correto (BB) não está no nó (o hash não inclui pot; o valor
gravado é o errado). Só a decisão, via build_decision_inputs_for_hand, recompõe o potBb certo.
Nós degenerados ÓRFÃOS (sem decisão que os cubra) não afetam nenhuma tela → deixados como estão.

Uso:
    python -m scripts.sweep_degenerate_postflop                 # dry-run (conta recuperáveis vs órfãos)
    python -m scripts.sweep_degenerate_postflop --apply         # TUDO + resync no fim (exige GTO_SOLVER_URL)
    python -m scripts.sweep_degenerate_postflop --apply --limit 20   # lote de N nós (roda em partes)
    python -m scripts.sweep_degenerate_postflop --apply --timeout 300  # spot pesado > default 240s
    python -m scripts.sweep_degenerate_postflop --apply --no-resync    # sem colar os labels

O `--apply` já roda o `resync_postflop_gto --apply` no fim: re-solvar conserta o NÓ, mas as
decisões seguem com o gto_label antigo até colarem de novo — como passo separado, era esquecido.

Cada nó leva de dezenas de segundos a alguns minutos (solve remoto). Com muitos nós isso passa
de uma hora, então rode DESTACADO pra uma queda de SSH não matar no meio (é resumível, mas você
perde o progresso do lote em curso):

    docker compose exec -d web python -m scripts.sweep_degenerate_postflop --apply
    docker compose logs -f web        # acompanhar
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import compute_spot_hash
from leaklab.gto_solver import (_call_remote_solver, _remote_url, _remote_key,
                                _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE, _solver_params_for_stack)
from database.repositories import insert_gto_nodes, get_gto_node, GTO_EXPLOITABILITY_THRESHOLD

_POSTFLOP = ('flop', 'turn', 'river')
_DEGEN_EXPLOIT = 0.02   # assinatura: full solve postflop legítimo fica ~0.5-1.8%; ≤0.02 = fake do bug


def _arg(f, default=None):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv and sys.argv.index(f) + 1 < len(sys.argv) else default


def _resolve_spot(conn, st, pos, vs_pos, board, hero, stack, pot_bb, facing, shash, timeout=240):
    """Deleta o nó degenerado (só este hash) e re-solva com o pot CORRETO. Retorna
    (ok, msg). Se o solve falhar, o nó fica sem cobertura — mas ele já era rejeitado
    pelo engine (degenerado), então não há regressão funcional."""
    conn.execute("DELETE FROM gto_nodes WHERE spot_hash = ?", (shash,))
    conn.commit()
    _p = _solver_params_for_stack(stack)
    payload = {
        'street': st, 'board': board, 'position': pos, 'hero_hand': hero,
        'hero_stack_bb': stack, 'facing_size_bb': facing,
        'oop_range': _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
        'ip_range': _DEFAULT_RANGES.get(pos, _DEFAULT_RANGE_WIDE),
        'pot_bb': pot_bb,
        'effective_stack_bb': _p['effective_stack_bb'],
        'max_iterations': _p['max_iterations'],
        'target_exploitability_pct': _p['target_exploitability_pct'],
        '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero,
                  'hero_stack_bb': stack, 'facing_size_bb': facing, 'street': st, 'board': board},
    }
    try:
        res = _call_remote_solver(payload, timeout=timeout)
    except Exception as e:
        return False, f"solve ERRO: {e}"
    if not res:
        return False, "solve vazio"
    exploit = res.get('exploitability') or res.get('exploitability_pct')
    if exploit is None or float(exploit) > GTO_EXPLOITABILITY_THRESHOLD:
        return False, f"rejeitado: exploit={exploit}"
    node = {
        'spot_hash': shash, 'street': st, 'position': pos, 'board': board,
        'hero_hand': hero, 'hero_stack_bb': stack, 'facing_size_bb': facing,
        'gto_action': res['primary_action'], 'gto_freq': res['primary_freq'],
        'ev_diff': res.get('ev'), 'exploitability_pct': float(exploit),
        'iterations': res.get('iterations'), 'strategy_detail': res.get('strategy_detail'),
        'source': 'solver_cli',
    }
    if insert_gto_nodes([node]):
        return True, f"OK exploit={exploit} action={res['primary_action']} freq={res.get('primary_freq')}"
    return False, "insert rejeitado"


def main():
    apply = '--apply' in sys.argv
    limit = int(_arg('--limit', 0) or 0)
    timeout = int(_arg('--timeout', 240) or 240)   # solver single-thread chega a ~172s em spots pesados

    conn = get_conn()

    # Conjunto de hashes degenerados (assinatura do bug do pot).
    degen = {dict(r)['spot_hash'] for r in conn.execute(
        "SELECT spot_hash FROM gto_nodes WHERE source='solver_cli' AND exploitability_pct <= ?",
        (_DEGEN_EXPLOIT,)).fetchall()}
    print(f"nós degenerados no banco (exploit<={_DEGEN_EXPLOIT}): {len(degen)}")
    if not degen:
        print("nada a fazer."); return

    if apply and not (_remote_url() and _remote_key()):
        print("⛔ GTO_SOLVER_URL/API_KEY ausentes — solve é remoto. Abortado."); return

    # Varre TODAS as mãos, casa cada spot postflop ao seu hash + pot CORRETO (da decisão).
    # Dedup por hash: um hash coberto por várias mãos é resolvido uma vez só.
    recoverable = {}   # hash -> params de re-solve (primeira decisão que o cobre)
    trows = conn.execute("SELECT id, raw_text FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()
    for tr in trows:
        t = dict(tr)
        try:
            hands = parse_hand_history(t['raw_text'])
        except Exception:
            continue
        for h in hands:
            try:
                dis = build_decision_inputs_for_hand(h)
            except Exception:
                continue
            for d in dis:
                st = (d.get('street') or '').lower()
                if st not in _POSTFLOP:
                    continue
                sp = d.get('spot', {}) or {}
                pos = (sp.get('position') or '').upper()
                vs_pos = (sp.get('villainPosition') or '').upper()
                board = sp.get('board', [])
                hero = d.get('hero_cards', [])
                if not pos or not board or not hero:
                    continue
                stack = float(sp.get('effectiveStackBb') or 20.0)
                pot_bb = float(sp.get('potBb') or 0.0)
                facing = float(sp.get('facingToBb') or 0.0)
                shash = compute_spot_hash(st, pos, board, hero, stack, facing)
                if shash in degen and shash not in recoverable:
                    recoverable[shash] = dict(st=st, pos=pos, vs_pos=vs_pos, board=board,
                                              hero=hero, stack=stack, pot_bb=pot_bb, facing=facing)

    orphans = len(degen) - len(recoverable)
    print(f"cobertos por decisão (recuperáveis): {len(recoverable)} | órfãos (deixados como estão): {orphans}\n")

    if not apply:
        for i, (hsh, p) in enumerate(list(recoverable.items())[:30], 1):
            print(f"  {i:>3}. {hsh[:10]} {p['st']} {p['pos']} {p['board']} pot={p['pot_bb']:.2f} facing={p['facing']:.2f}")
        if len(recoverable) > 30:
            print(f"  ... (+{len(recoverable)-30})")
        print("\n[dry-run] rode com --apply pra deletar+re-solvar. Use --limit N pra lotes.")
        return

    solved = failed = skipped = 0
    items = list(recoverable.items())
    import time as _time
    _t0 = _time.time()
    for i, (hsh, p) in enumerate(items, 1):
        if limit and solved >= limit:
            print(f"\n[limit {limit} atingido — pare/continue depois; é resumível]"); break
        # Resumível: se o nó já foi consertado (exploit acima do degenerado), pula.
        cur = get_gto_node(hsh)
        if cur and float(dict(cur).get('exploitability_pct') or 0) > _DEGEN_EXPLOIT:
            skipped += 1; continue
        ok, msg = _resolve_spot(conn, p['st'], p['pos'], p['vs_pos'], p['board'],
                                p['hero'], p['stack'], p['pot_bb'], p['facing'], hsh, timeout=timeout)
        tag = 'OK ' if ok else 'FALHA'
        # ETA pela média corrida: o solve remoto varia MUITO por spot (dezenas de segundos a
        # minutos), então é a única estimativa honesta. Sem ela não dá pra saber se isso sai em
        # 10 minutos ou em 3 horas — e a decisão de deixar rodando destacado depende disso.
        _feitos = solved + failed + 1
        _resta = (len(items) - i) * ((_time.time() - _t0) / max(1, _feitos)) / 60
        print(f"[{i}/{len(items)}] {hsh[:10]} {p['st']} {p['pos']} pot={p['pot_bb']:.2f} "
              f"-> {tag} {msg}  (~{_resta:.0f} min restantes)")
        if ok:
            solved += 1
        else:
            failed += 1

    print(f"\nFIM: {solved} re-solvados, {failed} falhos, {skipped} já bons (pulados).")

    # O resync é o passo que faz a correção CHEGAR NA TELA: re-solvar conserta o nó, mas as
    # decisões seguem com o gto_label antigo até colarem de novo. Como passo separado ele era
    # esquecido — e aí o sweep "não funcionou". Agora encadeia sozinho quando algo mudou.
    if solved and '--no-resync' not in sys.argv:
        print("\n→ colando os labels nas decisões (resync_postflop_gto --apply)...")
        import subprocess
        _script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resync_postflop_gto.py')
        subprocess.run([sys.executable, _script, '--apply'], check=False)
    elif solved:
        print("\n[--no-resync] rode `python -m scripts.resync_postflop_gto --apply` pra colar "
              "os labels, senão as telas seguem com o veredito velho.")


if __name__ == '__main__':
    main()
