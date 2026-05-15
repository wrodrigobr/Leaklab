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
GAMETYPE = "MTTGeneral"  # 9-max MTT (MTTGeneral_8m requer plano superior)

# Stack snapshots disponíveis no GTO Wizard MTT
STACK_SNAPS = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]

# Preflop action sequences para MTTGeneral 9-max (8 acoes)
# Raise size 2.3bb confirmado via API — stacks="" (depth= e a referencia)
PREFLOP_BY_POSITION = {
    "BTN":   "F-F-F-F-F-R2.3-F-C",  # confirmado via API
    "CO":    "F-F-F-F-R2.3-F-F-C",
    "HJ":    "F-F-F-R2.3-F-F-F-C",
    "LJ":    "F-F-R2.3-F-F-F-F-C",
    "UTG+1": "F-R2.3-F-F-F-F-F-C",
    "UTG":   "R2.3-F-F-F-F-F-F-C",
    "SB":    "F-F-F-F-F-F-R2.3-C",
    "BB":    "F-F-F-F-F-R2.3-F-C",  # BTN abre, SB fold, BB call
    "UTG+2": "F-F-R2.3-F-F-F-F-C",  # alias LJ
    "MP":    "F-F-R2.3-F-F-F-F-C",  # alias LJ
    "EP":    "R2.3-F-F-F-F-F-F-C",  # alias UTG
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
    # GTO Wizard requer stacks fracionados (representam estado real com antes)
    stack_frac = stack + 0.125
    stacks = ""  # arvore MTTGeneral usa depth= como referencia

    # Flop actions: se havia aposta, reconstituir como "check → raise"
    # API usa R (raise) para bets, nao B (que da 422)
    facing_bb = float(spot.get("facing_bet", 0) or 0)
    if facing_bb > 0:
        bet_bb = round(facing_bb, 1)
        flop_actions = f"X-R{bet_bb}"
    else:
        flop_actions = ""

    description = (
        f"{position} vs BB, {stack}bb, board {board}"
        + (f", bet {facing_bb:.1f}bb" if facing_bb > 0 else ", no bet")
    )

    return {
        "gametype": GAMETYPE,
        "depth": stack_frac,
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


def build_js_script(spots: list[dict], delay_ms: int = 2500) -> str:
    """
    Gera script JavaScript que intercepta Response.prototype.json para capturar
    as respostas spot-solution que o próprio GTO Wizard app faz — sem precisar
    fazer requests diretos (que exigem DPoP assinado por chave não-exportável).

    Fluxo:
    1. Instala interceptor em Response.prototype.json (não pode ser pre-capturado)
    2. Tenta navegação programática via history.pushState + popstate para cada spot
    3. Se o app React responder, captura a resposta automaticamente
    4. Se não responder (SPA não detecta popstate), exibe URL para navegação manual
    5. Usuário chama window.finishComparison() quando quiser ver os resultados
    """
    params_list = []
    for spot in spots:
        p = build_spot_url_params(spot)
        if p:
            params_list.append(p)

    params_json = json.dumps(params_list, indent=2, ensure_ascii=False)

    js = f"""
// ============================================================
// GTO Wizard Spot Comparison — Console Script (v4 — Response interceptor)
// Execute no console do browser em https://app.gtowizard.com
//
// COMO FUNCIONA:
//  Intercepta Response.prototype.json para capturar as respostas spot-solution
//  que o app GTO Wizard faz — sem DPoP, sem token, sem requests diretos.
//
// INSTRUÇÕES:
//  1. Cole este script no console e pressione Enter
//  2. Aguarde a tentativa de navegação automática (2-3s por spot)
//  3. Se um spot nao carregar, navegue manualmente ate ele
//  4. Quando todos estiverem capturados: window.finishComparison()
//     (ou aguarde o timeout automatico de 3 min apos o ultimo spot)
// ============================================================

(async function runComparison() {{
  const SPOTS = {params_json};
  const NAV_WAIT_MS = {delay_ms};   // espera por resposta apos navegacao
  const MANUAL_TIMEOUT_MS = 180000; // 3 min para navegacao manual

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ── Interceptar Response.prototype.json ────────────────────────────────────
  // Prototype chain: nao pode ser pre-capturado pelo app. Captura qualquer
  // chamada .json() em qualquer Response de spot-solution, seja do app ou nossa.
  const capturedSolutions = new Map(); // spotKey → {{actions, topAction}}
  const _origRespJson = Response.prototype.json;

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

  function spotKey(board, preflop, flop, depth) {{
    return `${{board}}|${{preflop}}|${{flop}}|${{depth}}`;
  }}

  Response.prototype.json = function() {{
    const url = this.url || '';
    if (url.includes('/v4/solutions/spot-solution/')) {{
      return _origRespJson.call(this).then(data => {{
        try {{
          const p = new URL(url).searchParams;
          const key = spotKey(p.get('board'), p.get('preflop_actions'), p.get('flop_actions') || '', p.get('depth'));
          if (!capturedSolutions.has(key)) {{
            const {{actions, topAction}} = parseStrategy(data);
            capturedSolutions.set(key, {{actions, topAction}});
            const strat = Object.entries(actions).sort((a,b)=>b[1]-a[1])
              .map(([k,v])=>`${{k}} ${{(v*100).toFixed(0)}}%`).join(' | ');
            console.log(`[Captured ${{capturedSolutions.size}}/${{SPOTS.length}}] ${{p.get('board')}} ${{p.get('depth')}}bb — ${{strat}}`);
          }}
        }} catch(e) {{}}
        return data;
      }});
    }}
    return _origRespJson.call(this);
  }};

  // ── Funcao para finalizar e gerar resultados ────────────────────────────────
  let finishCalled = false;
  function doFinish() {{
    if (finishCalled) return;
    finishCalled = true;
    Response.prototype.json = _origRespJson;
    delete window.finishComparison;

    const results = [];
    for (const p of SPOTS) {{
      const key = spotKey(p.board, p.preflop_actions, p.flop_actions || '', String(p.depth));
      const sol = capturedSolutions.get(key);
      const meta = p.meta;
      const result = {{
        ...meta,
        board: p.board,
        stack: p.depth,
        preflop_actions: p.preflop_actions,
        flop_actions: p.flop_actions,
        gto_found: !!sol,
        gto_strategy: sol?.actions || {{}},
        gto_top_action: sol?.topAction || null,
        error: sol ? null : 'not_captured',
      }};
      if (sol) {{
        const ourAction = (meta.our_best_action || '').toLowerCase();
        const gtoKey = {{'raise': 'bet', 'all-in': 'allin', 'jam': 'allin'}}[ourAction] || ourAction;
        const freq = sol.actions[gtoKey] || 0;
        result.our_action_gto_freq = freq;
        result.verdict = freq >= 0.40 ? 'agreement' : freq >= 0.15 ? 'mixed' : 'divergence';
      }}
      results.push(result);
    }}

    const found = results.filter(r => r.gto_found);
    const verdicts = {{}};
    results.forEach(r => {{ verdicts[r.verdict || r.error || 'skip'] = (verdicts[r.verdict || r.error || 'skip'] || 0) + 1; }});
    console.log('\\n' + '='.repeat(60));
    console.log(`RESULTADO: ${{found.length}}/${{results.length}} spots capturados`);
    console.log('Verditos:', JSON.stringify(verdicts));
    console.log('='.repeat(60));

    const jsonOutput = JSON.stringify(results, null, 2);
    navigator.clipboard.writeText(jsonOutput).then(() => {{
      console.log('JSON copiado para o clipboard! Cole em comparison_results_raw.json');
    }}).catch(() => {{
      console.log('GTW_RESULTS_START');
      console.log(jsonOutput);
      console.log('GTW_RESULTS_END');
    }});
    return results;
  }}

  window.finishComparison = doFinish;

  // ── Navegacao programatica ──────────────────────────────────────────────────
  // O app usa MTTGeneralV2 como gametype na API de historico (game-points/history).
  // Precisamos navegar com esse gametype para que o carregamento nao retorne 422.
  // Apos a tabela carregar, tentamos clicar na linha que corresponde ao nosso board.
  function buildAppUrl(p) {{
    const q = new URLSearchParams({{
      gametype: 'MTTGeneralV2',   // API historico so aceita este formato
      depth: String(p.depth),
      stacks: p.stacks,
      preflop_actions: p.preflop_actions,
      flop_actions: p.flop_actions || '',
      turn_actions: '',
      river_actions: '',
      board: p.board,
    }});
    return '/solutions?' + q.toString();
  }}

  // Tenta clicar em um elemento do DOM que contenha o board (todas as 3 cartas)
  async function tryClickBoard(board) {{
    const cards = [board.slice(0,2), board.slice(2,4), board.slice(4,6)].filter(c => c.length === 2);
    if (cards.length < 3) return false;
    await sleep(1500); // aguarda DOM renderizar apos navegacao
    // Busca em rows, cells e qualquer elemento clicavel
    const candidates = document.querySelectorAll('tr, [role="row"], [class*="row"], [class*="board"], [class*="Board"], td');
    for (const el of candidates) {{
      const txt = el.textContent || '';
      // Checa se todas as 3 cartas estao representadas no texto do elemento
      const found = cards.every(c => {{
        const r = c[0], s = c[1].toLowerCase();
        return txt.includes(r + s) || txt.includes(r.toLowerCase() + s);
      }});
      if (found && el.offsetParent !== null) {{ // elemento visivel
        el.click();
        return true;
      }}
    }}
    return false;
  }}

  async function tryNavigate(p) {{
    const url = buildAppUrl(p);
    // Tenta history API + popstate (React Router / VueRouter / SolidRouter)
    try {{
      window.history.pushState({{gtw: true}}, '', url);
      window.dispatchEvent(new PopStateEvent('popstate', {{state: {{gtw: true}}}}));
    }} catch(e) {{}}
    // Apos URL mudar, tenta clicar no board na tabela que carregar
    return await tryClickBoard(p.board);
  }}

  // ── Fase principal ──────────────────────────────────────────────────────────
  console.log('%c[GTO Comparison v4]', 'color:#4ade80;font-weight:bold',
    `${{SPOTS.length}} spots | interceptor ativo`);
  console.log('Tentando navegacao automatica... Se falhar, navegue manualmente e chame:');
  console.log('  window.finishComparison()');

  for (let i = 0; i < SPOTS.length; i++) {{
    const p = SPOTS[i];
    const key = spotKey(p.board, p.preflop_actions, p.flop_actions || '', String(p.depth));

    if (capturedSolutions.has(key)) {{
      console.log(`[${{i+1}}/${{SPOTS.length}}] ja capturado: ${{p.board}}`);
      continue;
    }}

    console.log(`[${{i+1}}/${{SPOTS.length}}] Navegando: ${{p.meta.position}} | ${{p.board}} | ${{p.depth}}bb`);
    await tryNavigate(p);

    // Aguarda a resposta ser capturada via Response.prototype.json
    let waited = 0;
    while (!capturedSolutions.has(key) && waited < NAV_WAIT_MS) {{
      await sleep(200);
      waited += 200;
    }}

    if (!capturedSolutions.has(key)) {{
      const q = new URLSearchParams({{
        gametype: p.gametype, depth: p.depth, stacks: p.stacks,
        preflop_actions: p.preflop_actions, flop_actions: p.flop_actions || '',
        turn_actions: '', river_actions: '', board: p.board,
      }});
      console.warn(`  ✗ Nao capturado. Navegue manualmente para este spot:`);
      console.warn(`    ${{p.meta.position}} | ${{p.board}} | ${{p.depth}}bb | flop_actions=${{p.flop_actions || 'none'}}`);
    }}
  }}

  // Aguarda navegacao manual para spots nao capturados
  const missing = SPOTS.filter(p => {{
    const key = spotKey(p.board, p.preflop_actions, p.flop_actions || '', String(p.depth));
    return !capturedSolutions.has(key);
  }});

  if (missing.length > 0) {{
    console.log(`\\n${{missing.length}} spots restantes. Navegue manualmente e chame window.finishComparison()`);
    console.log('Timeout automatico em 3 minutos...');
    let t = 0;
    while (missing.some(p => !capturedSolutions.has(spotKey(p.board, p.preflop_actions, p.flop_actions || '', String(p.depth)))) && t < MANUAL_TIMEOUT_MS) {{
      await sleep(1000);
      t += 1000;
    }}
  }}

  doFinish();
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
