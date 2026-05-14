"""
Gera um script JavaScript para executar no console do browser do GTO Wizard.

O browser já tem todas as credenciais e assina os requests automaticamente.
O script faz todas as chamadas de API e retorna os resultados como JSON.

Uso:
    1. python generate_console_script.py
    2. Abra o GTO Wizard no browser
    3. F12 → Console → cole o script gerado
    4. Aguarde a execução (alguns segundos por spot)
    5. Copie o JSON exibido no console
    6. Salve em comparison_results_raw.json
    7. python analyze_results.py --input comparison_results_raw.json
"""
from __future__ import annotations
import os, sys, json, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

SCRIPTS_DIR = os.path.dirname(__file__)
GAMETYPE = "MTTGeneral_8m"

# Stack snapshots disponíveis no GTO Wizard MTT (8-max)
STACK_SNAPS = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]

# Preflop action sequences por posição do hero (assume HU no flop — cenário mais comum)
# Formato: hero_position → preflop_actions quando hero IP ou OOP
PREFLOP_BY_POSITION = {
    # Hero IP vs BB (hero abre, BB chama)
    "BTN": "F-F-F-F-R2-F-C",    # UTG/LJ/HJ/CO fold, BTN raise, SB fold, BB call
    "CO":  "F-F-F-R2-F-F-C",    # UTG/LJ/HJ fold, CO raise, BTN/SB fold, BB call
    "HJ":  "F-F-R2-F-F-F-C",    # UTG/LJ fold, HJ raise, CO/BTN/SB fold, BB call
    "LJ":  "F-R2-F-F-F-F-C",
    "UTG": "R2-F-F-F-F-F-C",    # UTG raise, todos fold até BB, BB call
    # Hero OOP — SB abre, BB chama; ou hero na BB, outro posição abriu
    "SB":  "F-F-F-F-F-R2-C",    # todos fold, SB raise, BB call
    "BB":  "F-F-F-F-R2-F-C",    # BTN raise, SB fold, BB call (caso mais comum p/ BB no flop)
    # Posições com alias
    "UTG+1": "F-R2-F-F-F-F-C",
    "UTG+2": "F-F-R2-F-F-F-C",
    "MP":    "F-F-R2-F-F-F-C",
    "EP":    "R2-F-F-F-F-F-C",
}


def nearest_stack(stack_bb: float) -> float:
    return min(STACK_SNAPS, key=lambda s: abs(s - stack_bb))


def _extract_flop_cards(board: str) -> str:
    """Pega apenas as 3 primeiras cartas do board (flop), em formato GTO Wizard."""
    cards = board.strip().split()
    flop = cards[:3]
    if len(flop) < 3:
        return ""
    # Normalizar: rank uppercase, suit lowercase, sem espaço
    result = []
    for c in flop:
        c = c.strip()
        if len(c) >= 2:
            result.append(c[0].upper() + c[1].lower())
    return "".join(result) if len(result) == 3 else ""


def build_spot_url_params(spot: dict) -> dict | None:
    """Converte um spot do nosso DB nos parâmetros de URL do GTO Wizard."""
    board_raw = spot.get("board", "").strip()
    if not board_raw:
        return None

    board = _extract_flop_cards(board_raw)
    if not board:
        return None

    position = str(spot.get("position", "")).upper().strip()
    preflop_actions = PREFLOP_BY_POSITION.get(position)
    if not preflop_actions:
        return None

    stack = nearest_stack(float(spot.get("stack_bucket", 20)))
    stacks = "-".join([str(stack)] * 8)

    # Flop actions: se havia aposta, reconstituir como "check → bet"
    facing_bb = float(spot.get("facing_bet", 0) or 0)
    pot_bb = float(spot.get("pot_size", 1) or 1)
    if facing_bb > 0:
        bet_bb = round(facing_bb, 1)
        flop_actions = f"X-B{bet_bb}"
    else:
        flop_actions = ""

    description = (
        f"{position} vs BB, {stack}bb, board {board}"
        + (f", bet {facing_bb:.1f}bb" if facing_bb > 0 else ", no bet")
    )

    return {
        "gametype": GAMETYPE,
        "depth": stack,
        "stacks": stacks,
        "preflop_actions": preflop_actions,
        "flop_actions": flop_actions,
        "turn_actions": "",
        "river_actions": "",
        "board": board,
        "meta": {
            "spot_id": spot["spot_id"],
            "position": position,
            "villain_position": spot.get("villain_position") or "BB",
            "our_best_action": spot.get("example_best_action"),
            "our_label": spot.get("our_label"),
            "occurrences": spot.get("occurrences", 1),
            "scenario": description,
            "preflop_assumed": True,  # sempre assumido (não temos vilão no DB)
        },
    }


def build_js_script(spots: list[dict], delay_ms: int = 600) -> str:
    """
    Gera script JavaScript com interceptor de token em duas fases:
    Fase 1 — intercepta o fetch do app para capturar o Bearer token
    Fase 2 — usa o token capturado para fazer nossas chamadas

    O usuário precisa navegar para qualquer spot no GTO Wizard durante a Fase 1.
    """
    params_list = []
    for spot in spots:
        p = build_spot_url_params(spot)
        if p:
            params_list.append(p)

    params_json = json.dumps(params_list, indent=2, ensure_ascii=False)

    js = f"""
// ============================================================
// GTO Wizard Spot Comparison — Console Script (v2 — token interceptor)
// Execute no console do browser em https://app.gtowizard.com
//
// INSTRUÇÕES:
//  1. Cole este script no console e pressione Enter
//  2. Aguarde: "[Phase 1] Aguardando token..."
//  3. Navegue para QUALQUER spot no GTO Wizard (clique em qualquer flop)
//  4. Quando aparecer "[Phase 1] Token capturado!", a comparação inicia automaticamente
//  5. Ao final, o JSON é copiado para o clipboard
// ============================================================

(async function runComparison() {{
  const BASE = 'https://api.gtowizard.com';
  const SPOTS = {params_json};
  const DELAY = {delay_ms};
  const TOKEN_TIMEOUT_MS = 90000;  // 90s para o usuário navegar

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ── Phase 1: Interceptar token ──────────────────────────────────────────────
  console.log('[Phase 1] Aguardando token... Navegue para qualquer spot no GTO Wizard.');
  console.log('[Phase 1] (clique em qualquer flop na seção Study ou Solutions)');

  let capturedToken = null;
  const _origFetch = window.fetch.bind(window);

  window.fetch = function(url, opts) {{
    const urlStr = typeof url === 'string' ? url : (url?.url || String(url));
    if (urlStr.includes('api.gtowizard.com')) {{
      const headers = opts?.headers || {{}};
      const auth = headers['Authorization'] || headers['authorization'] || '';
      if (auth.startsWith('Bearer ') && !capturedToken) {{
        capturedToken = auth.slice(7);
        console.log('[Phase 1] ✓ Token capturado! Iniciando comparação em 1s...');
      }}
    }}
    return _origFetch(url, opts);
  }};

  // Aguardar até ter o token
  let waited = 0;
  while (!capturedToken && waited < TOKEN_TIMEOUT_MS) {{
    await sleep(300);
    waited += 300;
  }}

  // Restaurar fetch original
  window.fetch = _origFetch;

  if (!capturedToken) {{
    console.error('[Phase 1] TIMEOUT — token não capturado em ' + (TOKEN_TIMEOUT_MS/1000) + 's.');
    console.error('Tente navegar para um spot no GTO Wizard ANTES de rodar o script.');
    return;
  }}

  // ── Phase 2: Executar comparação ────────────────────────────────────────────
  console.log(`[Phase 2] Comparando ${{SPOTS.length}} spots...`);

  function buildUrl(p) {{
    const q = new URLSearchParams({{
      gametype: p.gametype,
      depth: p.depth,
      stacks: p.stacks,
      preflop_actions: p.preflop_actions,
      flop_actions: p.flop_actions,
      turn_actions: p.turn_actions,
      river_actions: p.river_actions,
      board: p.board,
    }});
    return `${{BASE}}/v4/solutions/spot-solution/?${{q.toString()}}`;
  }}

  function parseStrategy(data) {{
    const actions = {{}};
    let topAction = null, topFreq = -1;
    for (const item of (data.action_solutions || [])) {{
      const type = (item.action?.type || '').toLowerCase();
      const freq = parseFloat(item.total_frequency || 0);
      const name = {{
        'check': 'check', 'call': 'call', 'fold': 'fold',
        'bet': 'bet', 'raise': 'bet', 'all_in': 'allin', 'allin': 'allin',
      }}[type] || type;
      actions[name] = (actions[name] || 0) + freq;
      if (freq > topFreq) {{ topFreq = freq; topAction = name; }}
    }}
    return {{ actions, topAction }};
  }}

  const authHeaders = {{
    'Authorization': `Bearer ${{capturedToken}}`,
    'Accept': 'application/json, text/plain, */*',
    'gwclientid': '790ab864-ed0c-4545-9e5a-97efe89672cd',
    'Origin': 'https://app.gtowizard.com',
    'Referer': 'https://app.gtowizard.com/',
  }};

  const results = [];

  for (let i = 0; i < SPOTS.length; i++) {{
    const p = SPOTS[i];
    const meta = p.meta;
    process.stdout?.write?.(`[${{i+1}}/${{SPOTS.length}}]`);
    console.log(`[${{i+1}}/${{SPOTS.length}}] ${{meta.position}} | ${{p.board}} | ${{p.depth}}bb | preflop: ${{p.preflop_actions}}`);

    let result = {{
      ...meta,
      board: p.board,
      stack: p.depth,
      preflop_actions: p.preflop_actions,
      flop_actions: p.flop_actions,
      gto_found: false,
      gto_strategy: {{}},
      gto_top_action: null,
      error: null,
    }};

    try {{
      const url = buildUrl(p);
      const r = await _origFetch(url, {{ headers: authHeaders }});
      if (r.status === 401) {{
        result.error = 'token_expired_401';
        console.warn('  ✗ 401 — token expirou durante a execução. Reinicie o script.');
        break;
      }} else if (r.status === 404) {{
        result.error = 'not_found_404';
        console.log('  ✗ 404 — spot não disponível no plano');
      }} else if (!r.ok) {{
        result.error = `http_${{r.status}}`;
        console.log(`  ✗ ${{r.status}}`);
      }} else {{
        const data = await r.json();
        const {{ actions, topAction }} = parseStrategy(data);
        result.gto_found = true;
        result.gto_strategy = actions;
        result.gto_top_action = topAction;
        const ourAction = (meta.our_best_action || '').toLowerCase();
        const gtoKey = {{ 'raise': 'bet', 'all-in': 'allin', 'jam': 'allin' }}[ourAction] || ourAction;
        const freq = actions[gtoKey] || 0;
        result.our_action_gto_freq = freq;
        result.verdict = freq >= 0.40 ? 'agreement' : freq >= 0.15 ? 'mixed' : 'divergence';
        const strat = Object.entries(actions).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${{k}} ${{(v*100).toFixed(0)}}%`).join(' | ');
        console.log(`  ✓ ${{result.verdict.toUpperCase().padEnd(12)}} our=${{ourAction}}(${{(freq*100).toFixed(0)}}%)  GTO: ${{strat}}`);
      }}
    }} catch(e) {{
      result.error = e.message;
      console.error(`  ERROR: ${{e.message}}`);
    }}

    results.push(result);
    if (i < SPOTS.length - 1) await sleep(DELAY);
  }}

  // ── Summary ─────────────────────────────────────────────────────────────────
  const found = results.filter(r => r.gto_found);
  const verdicts = {{}};
  results.forEach(r => {{ verdicts[r.verdict || r.error || 'skip'] = (verdicts[r.verdict || r.error || 'skip'] || 0) + 1; }});
  console.log('\\n' + '='.repeat(60));
  console.log(`RESULTADO: ${{found.length}}/${{results.length}} spots encontrados`);
  console.log('Verditos:', JSON.stringify(verdicts));
  console.log('='.repeat(60));

  const jsonOutput = JSON.stringify(results, null, 2);

  try {{
    await navigator.clipboard.writeText(jsonOutput);
    console.log('✓ JSON copiado para o clipboard! Cole em comparison_results_raw.json');
  }} catch(e) {{
    console.log('Clipboard indisponível — JSON abaixo:');
    console.log('GTW_RESULTS_START');
    console.log(jsonOutput);
    console.log('GTW_RESULTS_END');
  }}

  return results;
}})();
""".strip()

    return js


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spots", default=os.path.join(SCRIPTS_DIR, "unique_spots.jsonl"))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--street", default="flop")
    parser.add_argument("--delay", type=int, default=600, help="Delay between calls in ms")
    parser.add_argument("--output", default=os.path.join(SCRIPTS_DIR, "console_script.js"))
    args = parser.parse_args()

    if not os.path.exists(args.spots):
        print(f"ERROR: {args.spots} not found. Run spot_extractor.py first.")
        sys.exit(1)

    spots = []
    with open(args.spots, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if args.street and s.get("street") != args.street:
                continue
            spots.append(s)
            if args.limit and len(spots) >= args.limit:
                break

    # Filter to spots we can build URLs for
    valid_spots = [s for s in spots if build_spot_url_params(s) is not None]
    skipped = len(spots) - len(valid_spots)

    print(f"Spots loaded: {len(spots)} | valid scenarios: {len(valid_spots)} | skipped (unknown scenario): {skipped}")

    js = build_js_script(valid_spots, delay_ms=args.delay)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"Script written to {args.output}")
    print(f"Estimated time: ~{len(valid_spots) * args.delay / 1000:.0f}s ({len(valid_spots)} spots × {args.delay}ms)")
    print()
    print("Next steps:")
    print("  1. Abra https://app.gtowizard.com no browser (deve estar logado)")
    print("  2. F12 → Console")
    print("  3. Cole o conteúdo de console_script.js")
    print("  4. Aguarde a conclusão")
    print("  5. O JSON será copiado para o clipboard automaticamente")
    print("  6. Cole em comparison_results_raw.json")
    print("  7. python analyze_results.py --input comparison_results_raw.json")


if __name__ == "__main__":
    main()
