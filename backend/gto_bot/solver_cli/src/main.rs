/// solver_cli — Wrapper CLI para postflop-solver (b-inary/postflop-solver).
///
/// Lê um JSON de spot via stdin, executa o solver CFR, e escreve
/// a estratégia GTO em JSON via stdout.
///
/// Formato de entrada (stdin):
/// ```json
/// {
///   "street":        "flop",
///   "board":         ["Ah", "Kd", "2c"],
///   "hero_range":    "AA,KK,QQ,AKs,AKo",   // range do hero em notação poker
///   "villain_range": "QQ+,AKs,AKo",
///   "hero_position": "OOP",                  // "OOP" ou "IP"
///   "pot_bb":        10.0,
///   "hero_stack_bb": 40.0,
///   "max_iterations": 1000,
///   "target_exploitability": 1.0             // % de pot
/// }
/// ```
///
/// Formato de saída (stdout):
/// ```json
/// {
///   "primary_action":  "bet",
///   "primary_freq":    0.72,
///   "ev":              1.43,
///   "exploitability":  0.8,
///   "strategy": {
///     "bet_75pct":  0.72,
///     "check":      0.18,
///     "bet_125pct": 0.10
///   }
/// }
/// ```
///
/// Compilação:
///   cargo build --release
///
/// O binário resultante fica em:
///   target/release/solver_cli
///
/// Requisitos:
///   - Rust 1.70+ com target x86_64 e suporte AVX2 (Intel Haswell 2013+ / AMD Zen 2017+)
///   - Para Linux (Render): cargo build --release --target x86_64-unknown-linux-gnu

use std::collections::HashMap;
use std::io::{self, Read};

use postflop_solver::*;
use serde::{Deserialize, Serialize};

// ── Estruturas de I/O ──────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct SolverInput {
    street:                 String,
    board:                  Vec<String>,
    hero_range:             String,
    villain_range:          String,
    hero_position:          String,   // "OOP" ou "IP"
    pot_bb:                 f64,
    hero_stack_bb:          f64,
    #[serde(default = "default_iterations")]
    max_iterations:         u32,
    #[serde(default = "default_exploitability")]
    target_exploitability:  f64,
}

fn default_iterations()     -> u32 { 1000 }
fn default_exploitability() -> f64 { 1.0  }

#[derive(Serialize)]
struct SolverOutput {
    primary_action:  String,
    primary_freq:    f64,
    ev:              f64,
    exploitability:  f64,
    strategy:        HashMap<String, f64>,
}

// ── Main ───────────────────────────────────────────────────────────────────────

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).expect("Falha ao ler stdin");

    let spot: SolverInput = match serde_json::from_str(&input) {
        Ok(v)  => v,
        Err(e) => {
            eprintln!("Erro ao parsear input JSON: {e}");
            std::process::exit(1);
        }
    };

    match solve_spot(&spot) {
        Ok(output) => {
            println!("{}", serde_json::to_string(&output).unwrap());
        }
        Err(e) => {
            eprintln!("Erro no solver: {e}");
            std::process::exit(2);
        }
    }
}

// ── Solver core ────────────────────────────────────────────────────────────────

fn solve_spot(spot: &SolverInput) -> Result<SolverOutput, String> {
    // Converte board para cards
    let board_cards: Vec<u8> = spot.board.iter()
        .filter_map(|c| card_from_str(c))
        .collect();

    if board_cards.len() < 3 {
        return Err(format!("Board inválido: {:?}", spot.board));
    }

    // Parse ranges
    let oop_range_str = if spot.hero_position.to_uppercase() == "OOP" {
        &spot.hero_range
    } else {
        &spot.villain_range
    };
    let ip_range_str = if spot.hero_position.to_uppercase() == "OOP" {
        &spot.villain_range
    } else {
        &spot.hero_range
    };

    let oop_range = oop_range_str.parse::<Range>()
        .map_err(|e| format!("Range OOP inválida: {e}"))?;
    let ip_range = ip_range_str.parse::<Range>()
        .map_err(|e| format!("Range IP inválida: {e}"))?;

    // Bet sizes padrão por street
    let (oop_bets, ip_bets) = default_bet_sizes(&spot.street);

    // Configura o game tree
    let config = TreeConfig {
        initial_state: match spot.street.to_lowercase().as_str() {
            "flop"  => BoardState::Flop,
            "turn"  => BoardState::Turn,
            "river" => BoardState::River,
            _       => BoardState::Flop,
        },
        starting_pot:     (spot.pot_bb * 100.0) as i32,
        effective_stack:  (spot.hero_stack_bb * 100.0) as i32,
        rake_rate:        0.0,
        rake_cap:         0.0,
        flop_bet_sizes:   oop_bets.flop.clone(),
        flop_raise_sizes: Default::default(),
        turn_bet_sizes:   oop_bets.turn.clone(),
        turn_raise_sizes: Default::default(),
        river_bet_sizes:  oop_bets.river.clone(),
        river_raise_sizes: Default::default(),
        turn_donk_sizes:  None,
        river_donk_sizes: None,
        add_allin_threshold: 1.5,
        force_allin_threshold: 0.15,
        merging_threshold: 0.1,
    };

    let tree = ActionTree::new(config).map_err(|e| format!("ActionTree: {e:?}"))?;

    let mut game = PostFlopGame::with_config(
        CardConfig {
            range:       [oop_range, ip_range],
            flop:        board_cards[..3].try_into().unwrap(),
            turn:        board_cards.get(3).copied().unwrap_or(NOT_DEALT),
            river:       board_cards.get(4).copied().unwrap_or(NOT_DEALT),
        },
        tree,
    ).map_err(|e| format!("PostFlopGame: {e:?}"))?;

    // Resolve
    solve(
        &mut game,
        spot.max_iterations,
        (spot.target_exploitability / 100.0) as f32,
        false,
    );

    let exploitability = compute_exploitability(&game) * 100.0;

    // Extrai estratégia do nó raiz para o hero
    game.cache_normalized_weights();
    let strategy = game.strategy();
    let actions  = game.available_actions();

    if strategy.is_empty() || actions.is_empty() {
        return Err("Estratégia vazia".to_string());
    }

    // Agrega frequências por action (média sobre combos do hero)
    let num_combos   = strategy.len() / actions.len();
    let mut freqs    = vec![0.0f64; actions.len()];
    for combo_idx in 0..num_combos {
        for action_idx in 0..actions.len() {
            freqs[action_idx] += strategy[combo_idx * actions.len() + action_idx] as f64;
        }
    }
    let total: f64 = freqs.iter().sum();
    if total > 0.0 {
        for f in freqs.iter_mut() { *f /= total; }
    }

    // Monta mapa action_label → frequency
    let mut strategy_map = HashMap::new();
    let mut primary_action = String::from("check");
    let mut primary_freq   = 0.0f64;

    for (i, action) in actions.iter().enumerate() {
        let label = action_label(action);
        let freq  = freqs.get(i).copied().unwrap_or(0.0);
        if freq > primary_freq {
            primary_freq   = freq;
            primary_action = label.clone();
        }
        strategy_map.insert(label, (freq * 1000.0).round() / 1000.0);
    }

    // EV do hero no nó raiz
    let ev_raw  = game.expected_values();
    let ev_mean = if !ev_raw.is_empty() {
        ev_raw.iter().map(|&x| x as f64).sum::<f64>() / ev_raw.len() as f64 / 100.0
    } else { 0.0 };

    Ok(SolverOutput {
        primary_action,
        primary_freq: (primary_freq * 1000.0).round() / 1000.0,
        ev: (ev_mean * 100.0).round() / 100.0,
        exploitability: (exploitability * 100.0).round() / 100.0,
        strategy: strategy_map,
    })
}

// ── Helpers ────────────────────────────────────────────────────────────────────

fn card_from_str(s: &str) -> Option<u8> {
    let s = s.trim();
    if s.len() < 2 { return None; }
    let rank = match s.chars().next()? {
        '2' => 0, '3' => 1, '4' => 2, '5' => 3, '6' => 4,
        '7' => 5, '8' => 6, '9' => 7, 'T'|'t' => 8,
        'J'|'j' => 9, 'Q'|'q' => 10, 'K'|'k' => 11, 'A'|'a' => 12,
        _ => return None,
    };
    let suit = match s.chars().nth(1)? {
        'c'|'C' => 0, 'd'|'D' => 1, 'h'|'H' => 2, 's'|'S' => 3,
        _ => return None,
    };
    Some(rank * 4 + suit)
}

fn action_label(action: &Action) -> String {
    match action {
        Action::Fold        => "fold".to_string(),
        Action::Check       => "check".to_string(),
        Action::Call        => "call".to_string(),
        Action::Bet(amount) => format!("bet_{}", amount),
        Action::Raise(amount) => format!("raise_{}", amount),
        Action::AllIn(amount) => format!("allin_{}", amount),
        _ => "unknown".to_string(),
    }
}

struct BetSizesByStreet {
    flop:  BetSizeOptions,
    turn:  BetSizeOptions,
    river: BetSizeOptions,
}

fn default_bet_sizes(_street: &str) -> (BetSizesByStreet, BetSizesByStreet) {
    let oop = BetSizesByStreet {
        flop:  BetSizeOptions { bet: vec!["50%".to_string(), "100%".to_string()], raise: vec!["2.5x".to_string()] },
        turn:  BetSizeOptions { bet: vec!["67%".to_string(), "100%".to_string()], raise: vec!["2.5x".to_string()] },
        river: BetSizeOptions { bet: vec!["75%".to_string(), "125%".to_string()], raise: vec!["2x".to_string()]   },
    };
    let ip = BetSizesByStreet {
        flop:  BetSizeOptions { bet: vec!["33%".to_string(), "75%".to_string()],  raise: vec!["2.5x".to_string()] },
        turn:  BetSizeOptions { bet: vec!["50%".to_string(), "100%".to_string()], raise: vec!["2.5x".to_string()] },
        river: BetSizeOptions { bet: vec!["67%".to_string(), "100%".to_string()], raise: vec!["2x".to_string()]   },
    };
    (oop, ip)
}
