// ============================================================
// GTO Wizard Spot Comparison — Console Script
// Gerado por generate_console_script.py
// Execute no console do browser em https://app.gtowizard.com
// Aguarde a conclusão e copie o JSON exibido.
// ============================================================

(async function runComparison() {
  const BASE = 'https://api.gtowizard.com';
  const SPOTS = [
  {
    "gametype": "MTTGeneral_8m",
    "depth": 50,
    "stacks": "50-50-50-50-50-50-50-50",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "X-B12.0",
    "turn_actions": "",
    "river_actions": "",
    "board": "7s5d6d",
    "meta": {
      "spot_id": "flop_BB__4h5d6d6c7s_50_0.67",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "clear_mistake",
      "occurrences": 3,
      "scenario": "BB vs BB, 50bb, board 7s5d6d, bet 12.0bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 10,
    "stacks": "10-10-10-10-10-10-10-10",
    "preflop_actions": "R2-F-F-F-F-F-C",
    "flop_actions": "X-B3.0",
    "turn_actions": "",
    "river_actions": "",
    "board": "5s4h9h",
    "meta": {
      "spot_id": "flop_UTG__4h5s8c9h_10_0.25",
      "position": "UTG",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "clear_mistake",
      "occurrences": 3,
      "scenario": "UTG vs BB, 10bb, board 5s4h9h, bet 3.0bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 10,
    "stacks": "10-10-10-10-10-10-10-10",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "X-B1.0",
    "turn_actions": "",
    "river_actions": "",
    "board": "7sAh8h",
    "meta": {
      "spot_id": "flop_BB__7s8hAh_10_0.5",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "clear_mistake",
      "occurrences": 3,
      "scenario": "BB vs BB, 10bb, board 7sAh8h, bet 1.0bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 30,
    "stacks": "30-30-30-30-30-30-30-30",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "X-B2.3",
    "turn_actions": "",
    "river_actions": "",
    "board": "6sKd6d",
    "meta": {
      "spot_id": "flop_BTN__6s6dKd_30_0.33",
      "position": "BTN",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "small_mistake",
      "occurrences": 3,
      "scenario": "BTN vs BB, 30bb, board 6sKd6d, bet 2.3bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 17,
    "stacks": "17-17-17-17-17-17-17-17",
    "preflop_actions": "F-F-F-F-F-R2-C",
    "flop_actions": "X-B1.5",
    "turn_actions": "",
    "river_actions": "",
    "board": "8s4c2c",
    "meta": {
      "spot_id": "flop_SB__2c4c8s_17_0.5",
      "position": "SB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "small_mistake",
      "occurrences": 3,
      "scenario": "SB vs BB, 17bb, board 8s4c2c, bet 1.5bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 40,
    "stacks": "40-40-40-40-40-40-40-40",
    "preflop_actions": "F-F-F-F-F-R2-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "6cAd7h",
    "meta": {
      "spot_id": "flop_SB__6c7h7dQhAd_40_0.0",
      "position": "SB",
      "villain_position": "BB",
      "our_best_action": "check",
      "our_label": "small_mistake",
      "occurrences": 3,
      "scenario": "SB vs BB, 40bb, board 6cAd7h, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 10,
    "stacks": "10-10-10-10-10-10-10-10",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "X-B1.8",
    "turn_actions": "",
    "river_actions": "",
    "board": "4sJd3c",
    "meta": {
      "spot_id": "flop_BB__3c4sJd_10_0.5",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "BB vs BB, 10bb, board 4sJd3c, bet 1.8bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 20,
    "stacks": "20-20-20-20-20-20-20-20",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "X-B1.8",
    "turn_actions": "",
    "river_actions": "",
    "board": "3dThQd",
    "meta": {
      "spot_id": "flop_BB__3dThQd_20_0.5",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "BB vs BB, 20bb, board 3dThQd, bet 1.8bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 50,
    "stacks": "50-50-50-50-50-50-50-50",
    "preflop_actions": "F-F-F-R2-F-F-C",
    "flop_actions": "X-B2.0",
    "turn_actions": "",
    "river_actions": "",
    "board": "9d2sKd",
    "meta": {
      "spot_id": "flop_CO__2s9dKd_50_0.25",
      "position": "CO",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "CO vs BB, 50bb, board 9d2sKd, bet 2.0bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 15,
    "stacks": "15-15-15-15-15-15-15-15",
    "preflop_actions": "F-F-R2-F-F-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "AhKsTh",
    "meta": {
      "spot_id": "flop_UTG+2__3c7sThKsAh_15_0.0",
      "position": "UTG+2",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "UTG+2 vs BB, 15bb, board AhKsTh, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 100,
    "stacks": "100-100-100-100-100-100-100-100",
    "preflop_actions": "F-F-F-F-F-R2-C",
    "flop_actions": "X-B5.2",
    "turn_actions": "",
    "river_actions": "",
    "board": "QsTcJc",
    "meta": {
      "spot_id": "flop_SB__TcJcQs_100_0.5",
      "position": "SB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "SB vs BB, 100bb, board QsTcJc, bet 5.2bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 50,
    "stacks": "50-50-50-50-50-50-50-50",
    "preflop_actions": "F-F-R2-F-F-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "JcJd5s",
    "meta": {
      "spot_id": "flop_HJ__5sJcJdQsQh_50_0.0",
      "position": "HJ",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "HJ vs BB, 50bb, board JcJd5s, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 25,
    "stacks": "25-25-25-25-25-25-25-25",
    "preflop_actions": "F-F-R2-F-F-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "5h4s3h",
    "meta": {
      "spot_id": "flop_UTG+2__2c3h4s5h_25_0.0",
      "position": "UTG+2",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "UTG+2 vs BB, 25bb, board 5h4s3h, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 15,
    "stacks": "15-15-15-15-15-15-15-15",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "5d6hJc",
    "meta": {
      "spot_id": "flop_BTN__5d5h6hJc_15_0.0",
      "position": "BTN",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "BTN vs BB, 15bb, board 5d6hJc, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 17,
    "stacks": "17-17-17-17-17-17-17-17",
    "preflop_actions": "F-F-F-R2-F-F-C",
    "flop_actions": "X-B23.0",
    "turn_actions": "",
    "river_actions": "",
    "board": "6h6s3h",
    "meta": {
      "spot_id": "flop_CO__3h6h6s_17_0.75",
      "position": "CO",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "marginal",
      "occurrences": 3,
      "scenario": "CO vs BB, 17bb, board 6h6s3h, bet 23.0bb",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 10,
    "stacks": "10-10-10-10-10-10-10-10",
    "preflop_actions": "R2-F-F-F-F-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "5s4h9h",
    "meta": {
      "spot_id": "flop_UTG__4h5s8c9h_10_0.0",
      "position": "UTG",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "UTG vs BB, 10bb, board 5s4h9h, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 40,
    "stacks": "40-40-40-40-40-40-40-40",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "7cTsJh",
    "meta": {
      "spot_id": "flop_BB__7cTsJhKd_40_0.0",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 40bb, board 7cTsJh, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 50,
    "stacks": "50-50-50-50-50-50-50-50",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "7s5d6d",
    "meta": {
      "spot_id": "flop_BB__4h5d6d6c7s_50_0.0",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 50bb, board 7s5d6d, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 25,
    "stacks": "25-25-25-25-25-25-25-25",
    "preflop_actions": "F-F-F-F-F-R2-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "8h6dJd",
    "meta": {
      "spot_id": "flop_SB__6d6c8hJdQs_25_0.0",
      "position": "SB",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "SB vs BB, 25bb, board 8h6dJd, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 10,
    "stacks": "10-10-10-10-10-10-10-10",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "6s7c2s",
    "meta": {
      "spot_id": "flop_BB__2s2c2h6s7c_10_0.0",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "check",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 10bb, board 6s7c2s, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 13,
    "stacks": "13-13-13-13-13-13-13-13",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "8hKdAh",
    "meta": {
      "spot_id": "flop_BB__8hKdAh_13_0.0",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 13bb, board 8hKdAh, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 10,
    "stacks": "10-10-10-10-10-10-10-10",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "7sAh8h",
    "meta": {
      "spot_id": "flop_BB__7s8hAh_10_0.0",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 10bb, board 7sAh8h, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 13,
    "stacks": "13-13-13-13-13-13-13-13",
    "preflop_actions": "F-F-F-F-F-R2-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "4h4cAs",
    "meta": {
      "spot_id": "flop_SB__4h4c5cQcAs_13_0.0",
      "position": "SB",
      "villain_position": "BB",
      "our_best_action": "check",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "SB vs BB, 13bb, board 4h4cAs, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 15,
    "stacks": "15-15-15-15-15-15-15-15",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "",
    "turn_actions": "",
    "river_actions": "",
    "board": "9c8c5h",
    "meta": {
      "spot_id": "flop_BB__5h8c9c_15_0.0",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "bet",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 15bb, board 9c8c5h, no bet",
      "preflop_assumed": true
    }
  },
  {
    "gametype": "MTTGeneral_8m",
    "depth": 13,
    "stacks": "13-13-13-13-13-13-13-13",
    "preflop_actions": "F-F-F-F-R2-F-C",
    "flop_actions": "X-B1.8",
    "turn_actions": "",
    "river_actions": "",
    "board": "Th3s4s",
    "meta": {
      "spot_id": "flop_BB__3s4sTh_13_0.5",
      "position": "BB",
      "villain_position": "BB",
      "our_best_action": "call",
      "our_label": "standard",
      "occurrences": 3,
      "scenario": "BB vs BB, 13bb, board Th3s4s, bet 1.8bb",
      "preflop_assumed": true
    }
  }
];
  const DELAY = 600;

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function buildUrl(p) {
    const q = new URLSearchParams({
      gametype: p.gametype,
      depth: p.depth,
      stacks: p.stacks,
      preflop_actions: p.preflop_actions,
      flop_actions: p.flop_actions,
      turn_actions: p.turn_actions,
      river_actions: p.river_actions,
      board: p.board,
    });
    return `${BASE}/v4/solutions/spot-solution/?${q.toString()}`;
  }

  function parseStrategy(data) {
    const actions = {};
    let topAction = null;
    let topFreq = -1;
    for (const item of (data.action_solutions || [])) {
      const type = (item.action?.type || '').toLowerCase();
      const freq = parseFloat(item.total_frequency || 0);
      const name = {
        'check': 'check', 'call': 'call', 'fold': 'fold',
        'bet': 'bet', 'raise': 'bet', 'all_in': 'allin', 'allin': 'allin'
      }[type] || type;
      actions[name] = (actions[name] || 0) + freq;
      if (freq > topFreq) { topFreq = freq; topAction = name; }
    }
    return { actions, topAction };
  }

  const results = [];
  console.log(`[GTO Compare] Starting ${SPOTS.length} spots...`);

  for (let i = 0; i < SPOTS.length; i++) {
    const p = SPOTS[i];
    const meta = p.meta;
    console.log(`[${i+1}/${SPOTS.length}] ${meta.position} vs ${meta.villain_position} | ${p.board} | ${p.depth}bb`);

    let result = {
      ...meta,
      board: p.board,
      stack: p.depth,
      preflop_actions: p.preflop_actions,
      flop_actions: p.flop_actions,
      gto_found: false,
      gto_strategy: {},
      gto_top_action: null,
      error: null,
    };

    try {
      const url = buildUrl(p);
      const r = await fetch(url);
      if (r.status === 404) {
        result.error = 'not_found_404';
      } else if (!r.ok) {
        result.error = `http_${r.status}`;
      } else {
        const data = await r.json();
        const { actions, topAction } = parseStrategy(data);
        result.gto_found = true;
        result.gto_strategy = actions;
        result.gto_top_action = topAction;
        // Verdict: frequency of our recommended action in GTO
        const ourAction = (meta.our_best_action || '').toLowerCase();
        const mapAction = { 'raise': 'bet', 'all-in': 'allin', 'jam': 'allin' };
        const gtoKey = mapAction[ourAction] || ourAction;
        const freq = actions[gtoKey] || 0;
        result.our_action_gto_freq = freq;
        result.verdict = freq >= 0.40 ? 'agreement' : freq >= 0.15 ? 'mixed' : 'divergence';
        console.log(`  → ${result.verdict} | our=${ourAction} gto_freq=${(freq*100).toFixed(0)}% | gto_top=${topAction}`);
      }
    } catch(e) {
      result.error = e.message;
      console.error(`  ERROR: ${e.message}`);
    }

    results.push(result);
    if (i < SPOTS.length - 1) await sleep(DELAY);
  }

  console.log('\n[GTO Compare] DONE. Copying results to clipboard...');

  // Summary
  const found = results.filter(r => r.gto_found);
  const verdicts = {};
  results.forEach(r => { verdicts[r.verdict || 'error'] = (verdicts[r.verdict || 'error'] || 0) + 1; });
  console.log(`Found: ${found.length}/${results.length}`);
  console.log('Verdicts:', verdicts);

  const jsonOutput = JSON.stringify(results, null, 2);

  // Try to copy to clipboard
  try {
    await navigator.clipboard.writeText(jsonOutput);
    console.log('[GTO Compare] Results copied to clipboard! Paste into comparison_results_raw.json');
  } catch(e) {
    console.log('[GTO Compare] Clipboard failed — printing JSON below:');
    console.log('--- BEGIN JSON ---');
    console.log(jsonOutput);
    console.log('--- END JSON ---');
  }

  return results;
})();