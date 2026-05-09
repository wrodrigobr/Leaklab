/// solver_cli — Wrapper CLI para postflop-solver (b-inary/postflop-solver).
///
/// Lê um spot JSON via stdin, executa CFR até convergir abaixo do threshold,
/// e escreve a estratégia GTO com exploitability medida em stdout.
///
/// Entrada (stdin):
/// {
///   "street":                   "flop" | "turn" | "river",
///   "board":                    ["Ah","Kd","2c"],
///   "oop_range":                "QQ+,AKs,AQs,AKo",
///   "ip_range":                 "AA,KK,AKs,AKo",
///   "pot_bb":                   10.0,
///   "effective_stack_bb":       40.0,
///   "max_iterations":           1000,
///   "target_exploitability_pct": 1.0
/// }
///
/// Saída (stdout):
/// {
///   "primary_action":   "bet",
///   "primary_freq":     0.72,
///   "ev":               1.43,
///   "exploitability":   0.41,     <- % do pot
///   "iterations":       450,
///   "strategy": { "check": 0.28, "bet_50pct": 0.72 }
/// }

use postflop_solver::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{self, Read};

// ── I/O ───────────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct Input {
    street:                    String,
    board:                     Vec<String>,
    oop_range:                 String,
    ip_range:                  String,
    pot_bb:                    f64,
    effective_stack_bb:        f64,
    #[serde(default = "default_iters")]
    max_iterations:            u32,
    #[serde(default = "default_target")]
    target_exploitability_pct: f64,
}

fn default_iters()  -> u32 { 1500 }
fn default_target() -> f64 { 1.0  }

#[derive(Serialize)]
struct Output {
    primary_action: String,
    primary_freq:   f64,
    ev:             f64,
    exploitability: f64,    // % do pot
    iterations:     u32,
    strategy:       HashMap<String, f64>,
}

#[derive(Serialize)]
struct ErrorOutput {
    error: String,
}

// ── Main ───────────────────────────────────────────────────────────────────────

fn main() {
    let mut raw = String::new();
    io::stdin().read_to_string(&mut raw).expect("falha ao ler stdin");

    let input: Input = match serde_json::from_str(&raw) {
        Ok(v)  => v,
        Err(e) => {
            eprintln!("{}", serde_json::to_string(&ErrorOutput { error: e.to_string() }).unwrap());
            std::process::exit(1);
        }
    };

    match run(&input) {
        Ok(out) => println!("{}", serde_json::to_string(&out).unwrap()),
        Err(e)  => {
            eprintln!("{}", serde_json::to_string(&ErrorOutput { error: e }).unwrap());
            std::process::exit(2);
        }
    }
}

// ── Solver ────────────────────────────────────────────────────────────────────

fn run(inp: &Input) -> Result<Output, String> {
    // Parse ranges
    let oop_range: Range = inp.oop_range.parse()
        .map_err(|e| format!("oop_range inválida: {e}"))?;
    let ip_range: Range = inp.ip_range.parse()
        .map_err(|e| format!("ip_range inválida: {e}"))?;

    // Parse board
    let board = parse_board(&inp.board, &inp.street)?;

    // Bet sizes padrão por street (OOP e IP iguais, simplificação razoável)
    let flop_bets  = BetSizeOptions::try_from(("33%, 50%, 75%, 100%", "2.5x"))
        .map_err(|e| format!("bet sizes inválidas: {e}"))?;
    let turn_bets  = BetSizeOptions::try_from(("50%, 75%, 100%", "2.5x"))
        .map_err(|e| format!("bet sizes inválidas: {e}"))?;
    let river_bets = BetSizeOptions::try_from(("50%, 75%, 100%, 125%", "2x"))
        .map_err(|e| format!("bet sizes inválidas: {e}"))?;

    let initial_state = match inp.street.to_lowercase().as_str() {
        "flop"  => BoardState::Flop,
        "turn"  => BoardState::Turn,
        "river" => BoardState::River,
        s       => return Err(format!("street inválida: {s}")),
    };

    let pot_chips   = (inp.pot_bb * 100.0).round() as i32;
    let stack_chips = (inp.effective_stack_bb * 100.0).round() as i32;

    let tree_config = TreeConfig {
        initial_state,
        starting_pot:    pot_chips,
        effective_stack: stack_chips,
        rake_rate:       0.0,
        rake_cap:        0.0,
        flop_bet_sizes:  [flop_bets.clone(), flop_bets],
        turn_bet_sizes:  [turn_bets.clone(), turn_bets],
        river_bet_sizes: [river_bets.clone(), river_bets],
        turn_donk_sizes:  None,
        river_donk_sizes: None,
        add_allin_threshold:   1.5,
        force_allin_threshold: 0.15,
        merging_threshold:     0.1,
    };

    let card_config = CardConfig {
        range: [oop_range, ip_range],
        flop:  board.flop,
        turn:  board.turn,
        river: board.river,
    };

    let action_tree = ActionTree::new(tree_config)
        .map_err(|e| format!("ActionTree: {e:?}"))?;
    let mut game = PostFlopGame::with_config(card_config, action_tree)
        .map_err(|e| format!("PostFlopGame: {e:?}"))?;

    // Target em chips absolutos (pot * pct/100)
    let target_chips = pot_chips as f32 * (inp.target_exploitability_pct as f32 / 100.0);

    game.allocate_memory(false);

    let final_exploit = solve(&mut game, inp.max_iterations, target_chips, false);
    let exploit_pct   = (final_exploit as f64 / pot_chips as f64) * 100.0;

    // Estratégia no nó raiz (OOP = player 0)
    game.cache_normalized_weights();
    let strategy = game.strategy();
    let actions  = game.available_actions();
    let hands    = game.private_cards(0);
    let evs      = game.expected_values(0);
    let weights  = game.normalized_weights(0);

    let num_actions = actions.len();
    let num_hands   = hands.len();

    if num_actions == 0 || num_hands == 0 {
        return Err("Estratégia vazia — spot inválido".to_string());
    }

    // Agrega frequências ponderadas por peso de cada combo
    // Indexação: strategy[hand_idx + action_idx * num_hands]
    let total_weight: f64 = weights.iter().map(|&w| w as f64).sum();
    let mut freqs = vec![0.0f64; num_actions];

    if total_weight > 0.0 {
        for hand_idx in 0..num_hands {
            let w = weights[hand_idx] as f64 / total_weight;
            for action_idx in 0..num_actions {
                freqs[action_idx] += w * strategy[hand_idx + action_idx * num_hands] as f64;
            }
        }
    }

    // EV médio ponderado
    let avg_ev = if total_weight > 0.0 {
        let ev_sum: f64 = (0..num_hands)
            .map(|i| evs[i] as f64 * weights[i] as f64)
            .sum::<f64>();
        ev_sum / (total_weight * 100.0)  // converte chips → BBs
    } else { 0.0 };

    // Monta mapa e identifica ação primária
    let mut strategy_map: HashMap<String, f64> = HashMap::new();
    let mut primary_action = String::from("check");
    let mut primary_freq   = 0.0f64;

    for (i, action) in actions.iter().enumerate() {
        let label = action_label(action, pot_chips);
        let freq  = (freqs[i] * 1000.0).round() / 1000.0;
        if freq > primary_freq {
            primary_freq   = freq;
            primary_action = label.clone();
        }
        if freq > 0.001 {
            strategy_map.insert(label, freq);
        }
    }

    Ok(Output {
        primary_action,
        primary_freq: (primary_freq * 1000.0).round() / 1000.0,
        ev:           (avg_ev * 100.0).round() / 100.0,
        exploitability: (exploit_pct * 100.0).round() / 100.0,
        iterations: inp.max_iterations,
        strategy: strategy_map,
    })
}

// ── Board parsing ─────────────────────────────────────────────────────────────

struct Board {
    flop:  [u8; 3],
    turn:  u8,
    river: u8,
}

fn parse_board(cards: &[String], street: &str) -> Result<Board, String> {
    let parsed: Vec<u8> = cards.iter()
        .filter_map(|c| card_from_str(c.trim()).ok())
        .collect();

    let flop = match parsed.get(0..3) {
        Some(f) => [f[0], f[1], f[2]],
        None    => return Err(format!("Board precisa de pelo menos 3 cartas, recebeu {}", parsed.len())),
    };

    let turn  = match street.to_lowercase().as_str() {
        "turn" | "river" => parsed.get(3).copied().unwrap_or(NOT_DEALT),
        _                => NOT_DEALT,
    };
    let river = match street.to_lowercase().as_str() {
        "river" => parsed.get(4).copied().unwrap_or(NOT_DEALT),
        _       => NOT_DEALT,
    };

    Ok(Board { flop, turn, river })
}

// ── Action label ──────────────────────────────────────────────────────────────

fn action_label(action: &Action, pot: i32) -> String {
    match action {
        Action::Fold          => "fold".to_string(),
        Action::Check         => "check".to_string(),
        Action::Call          => "call".to_string(),
        Action::Bet(amount)   => {
            let pct = (*amount as f64 / pot as f64 * 100.0).round() as i32;
            format!("bet_{pct}pct")
        }
        Action::Raise(amount) => {
            let pct = (*amount as f64 / pot as f64 * 100.0).round() as i32;
            format!("raise_{pct}pct")
        }
        Action::AllIn(_)      => "allin".to_string(),
        _                     => "unknown".to_string(),
    }
}
