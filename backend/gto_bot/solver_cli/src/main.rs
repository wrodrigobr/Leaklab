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
///   "target_exploitability_pct": 1.0,
///   "facing_size_bb":           3.0   // opcional: > 0 → estratégia de OOP enfrentando aposta do IP
/// }
///
/// Quando facing_size_bb > 0 o solver navega internamente para o nó
/// "OOP checked → IP bet closest_to(facing_size_bb) → OOP to act" e retorna
/// a estratégia de resposta (fold/call/raise/allin) daquele nó.
///
/// Saída (stdout):
/// {
///   "primary_action":   "bet",
///   "primary_freq":     0.72,
///   "ev":               1.43,
///   "exploitability":   0.41,     <- % do pot
///   "iterations":       450,
///   "strategy": { "check": 0.28, "bet_50pct": 0.72 },
///   "facing_node":      false     <- true quando facing_size_bb > 0 e navegação ok
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
    /// Budget de tempo (s): para o CFR ao atingir, devolvendo o melhor até então.
    /// Garante throughput consistente — árvores grandes não estouram o timeout.
    #[serde(default = "default_time_budget")]
    time_budget_s:             u64,
    /// Quando > 0: resolve o game tree completo mas retorna a estratégia de OOP
    /// no nó onde IP apostou closest_to(facing_size_bb) após OOP checar.
    #[serde(default)]
    facing_size_bb:            f64,
    /// hero está IN POSITION? Se true, lê a estratégia do IP (player 1) no nó de c-bet
    /// (root → OOP check → IP to act). Default false (hero OOP = player 0). Só facing==0.
    #[serde(default)]
    hero_is_ip:                bool,
}

fn default_iters()  -> u32 { 1500 }
fn default_target() -> f64 { 1.0  }
fn default_time_budget() -> u64 { 150 }

#[derive(Serialize, Clone)]
struct ActionDetail {
    frequency: f64,
    combos:    f64,
}

/// Fase 3 (plano solver): linha da tabela POR MÃO — frequência e EV de cada ação
/// para um combo específico do hero. `freqs`/`evs` seguem a ordem de `actions`
/// do Output. EVs em BB (chips/100), pesos normalizados do range.
#[derive(Serialize)]
struct HandDetail {
    hand:   String,     // ex.: "AhKd"
    weight: f64,        // peso normalizado do combo no range
    freqs:  Vec<f64>,   // frequência por ação
    evs:    Vec<f64>,   // EV por ação, em BB
}

#[derive(Serialize)]
struct Output {
    primary_action:   String,
    primary_freq:     f64,
    ev:               f64,
    exploitability:   f64,    // % do pot
    iterations:       u32,
    strategy:         HashMap<String, f64>,
    strategy_detail:  HashMap<String, ActionDetail>,
    total_combos:     f64,
    facing_node:      bool,   // true quando facing_size_bb navegou com sucesso
    /// Fase 3: ordem canônica das ações (chave p/ freqs/evs do hand_table)
    actions:          Vec<String>,
    /// Fase 3: estratégia + EV por MÃO do range do hero (veredito hand-aware)
    hand_table:       Vec<HandDetail>,
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

    // 1 bet size por street — árvore compacta que cabe no limite de RAM do solver.
    // (testamos 2 sizes, mas o gargalo real era iterações=10 congeladas, não a árvore;
    //  2 sizes só estourava RAM/timeout sem ganho — revertido.)
    let flop_bets  = BetSizeOptions::try_from(("50%", "2.5x"))
        .map_err(|e| format!("bet sizes inválidas: {e}"))?;
    let turn_bets  = BetSizeOptions::try_from(("75%", "2.5x"))
        .map_err(|e| format!("bet sizes inválidas: {e}"))?;
    let river_bets = BetSizeOptions::try_from(("75%", "2x"))
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

    // Verifica uso de memória antes de alocar — retorna erro cedo se spot é grande demais
    let (mem_32bit, mem_16bit) = game.memory_usage();
    const MEM_LIMIT: u64 = 6 * 1024 * 1024 * 1024; // 6 GB
    if mem_16bit > MEM_LIMIT {
        return Err(format!(
            "spot requer {:.1}GB (16-bit) — excede limite de 6GB. Reduza as ranges.",
            mem_16bit as f64 / 1_073_741_824.0
        ));
    }
    // Usa 16-bit comprimido se > 1 GB; 32-bit caso contrário (melhor precisão)
    let use_compression = mem_32bit > 1_073_741_824;
    game.allocate_memory(use_compression);

    // Loop manual (espelha postflop_solver::solve) para CONTAR as iterações reais:
    // o solve() da lib não devolve quantas iterações rodou, e o campo `iterations`
    // do output ecoava max_iterations (mentia). Exploitability checada a cada 10
    // iterações — mesma cadência do solve() upstream.
    let mut final_exploit  = compute_exploitability(&game);
    let mut iterations_run = 0u32;
    let solve_start = std::time::Instant::now();
    for t in 0..inp.max_iterations {
        if final_exploit <= target_chips {
            break;
        }
        // Budget de tempo: para árvores grandes não estourarem o timeout do cliente —
        // devolve o melhor alcançado dentro do orçamento (throughput consistente).
        if solve_start.elapsed().as_secs() >= inp.time_budget_s {
            final_exploit = compute_exploitability(&game);
            break;
        }
        solve_step(&game, t);
        iterations_run += 1;
        if (t + 1) % 10 == 0 || t + 1 == inp.max_iterations {
            final_exploit = compute_exploitability(&game);
        }
    }
    finalize(&mut game);
    let exploit_pct = (final_exploit as f64 / pot_chips as f64) * 100.0;

    // Jogador do HERO no solver: OOP=0, IP=1. Navega até o nó de DECISÃO do hero:
    //   - hero IP  + facing==0: root → OOP check → IP age (c-bet) — lê player 1;
    //   - hero IP  + facing>0:  root → OOP bet closest(facing) → IP age (enfrenta aposta);
    //   - hero OOP + facing>0:  root → OOP check → IP bet closest(facing) → OOP enfrenta;
    //   - hero OOP + facing==0: root (OOP primeira ação).
    let hero_player: usize = if inp.hero_is_ip { 1 } else { 0 };
    let facing_chips  = (inp.facing_size_bb * 100.0).round() as i32;
    let (facing_node, nav_ok) = if inp.hero_is_ip {
        if inp.facing_size_bb > 0.0 {
            // hero IP enfrentando aposta: OOP aposta no root → IP responde
            let ok = navigate_to_ip_facing_bet(&mut game, facing_chips);
            (ok, ok)          // o pot subiu com a aposta do OOP → facing_node
        } else {
            (false, navigate_to_ip_decision(&mut game))
        }
    } else if inp.facing_size_bb > 0.0 {
        let ok = navigate_to_facing_bet(&mut game, facing_chips);
        (ok, ok)
    } else {
        (false, true)         // hero OOP primeira ação (root) — sempre ok
    };
    // Se a navegação até o nó do hero falhou, aborta (o wrapper cai no heurístico em vez
    // de devolver a estratégia do jogador errado).
    if !nav_ok {
        return Err("navegacao ate o no do hero falhou".to_string());
    }

    // Pot de referência para labels: se navegamos pro facing-bet, o pot subiu com a aposta.
    let label_pot = if facing_node { pot_chips + facing_chips } else { pot_chips };

    // Estratégia no nó atual = jogador da vez (já navegamos até o nó do HERO).
    game.cache_normalized_weights();
    let strategy = game.strategy();
    let actions  = game.available_actions();
    let hands    = game.private_cards(hero_player);
    let evs      = game.expected_values(hero_player);
    let weights  = game.normalized_weights(hero_player);

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

    // Combo counts
    let mut combo_counts = vec![0.0f64; num_actions];
    for hand_idx in 0..num_hands {
        let w = weights[hand_idx] as f64;
        for action_idx in 0..num_actions {
            combo_counts[action_idx] += w * strategy[hand_idx + action_idx * num_hands] as f64;
        }
    }

    // Monta mapa e identifica ação primária
    let mut strategy_map:        HashMap<String, f64>          = HashMap::new();
    let mut strategy_detail_map: HashMap<String, ActionDetail> = HashMap::new();
    let mut primary_action = String::from("check");
    let mut primary_freq   = 0.0f64;

    for (i, action) in actions.iter().enumerate() {
        let label  = action_label(action, label_pot);
        let freq   = (freqs[i] * 1000.0).round() / 1000.0;
        let combos = (combo_counts[i] * 100.0).round() / 100.0;
        if freq > primary_freq {
            primary_freq   = freq;
            primary_action = label.clone();
        }
        if freq > 0.001 {
            strategy_map.insert(label.clone(), freq);
            strategy_detail_map.insert(label, ActionDetail { frequency: freq, combos });
        }
    }

    // ── Fase 3 (plano solver): tabela POR MÃO ────────────────────────────────
    // O veredito da plataforma usava só a frequência AGREGADA da range — mas num
    // K72r a range checa 60% enquanto AA aposta 90%. expected_values_detail dá
    // EV de cada ação para cada combo (mesmo layout de índice da strategy:
    // hand + action*num_hands). Custo: 1 traversal extra, ~zero vs o solve.
    let ev_detail = game.expected_values_detail(hero_player);
    let action_labels: Vec<String> =
        actions.iter().map(|a| action_label(a, label_pot)).collect();
    let mut hand_table: Vec<HandDetail> = Vec::with_capacity(num_hands);
    for hand_idx in 0..num_hands {
        let w = weights[hand_idx] as f64;
        if w <= 0.0 {
            continue;   // combo bloqueado pelo board / fora do range
        }
        let (c1, c2) = hands[hand_idx];
        let combo = format!(
            "{}{}",
            card_to_string(c1).unwrap_or_default(),
            card_to_string(c2).unwrap_or_default()
        );
        let mut freqs_h = Vec::with_capacity(num_actions);
        let mut evs_h   = Vec::with_capacity(num_actions);
        for action_idx in 0..num_actions {
            let idx = hand_idx + action_idx * num_hands;
            freqs_h.push((strategy[idx] as f64 * 1000.0).round() / 1000.0);
            evs_h.push((ev_detail[idx] as f64).round() / 100.0);   // chips → BB, 2 casas
        }
        hand_table.push(HandDetail {
            hand:   combo,
            weight: (w * 10000.0).round() / 10000.0,
            freqs:  freqs_h,
            evs:    evs_h,
        });
    }

    Ok(Output {
        primary_action,
        primary_freq:    (primary_freq * 1000.0).round() / 1000.0,
        ev:              (avg_ev * 100.0).round() / 100.0,
        exploitability:  (exploit_pct * 100.0).round() / 100.0,
        iterations:      iterations_run,
        strategy:        strategy_map,
        strategy_detail: strategy_detail_map,
        total_combos:    (total_weight * 100.0).round() / 100.0,
        facing_node,
        actions:         action_labels,
        hand_table,
    })
}

// ── Navegação para nó facing-bet ──────────────────────────────────────────────

/// Avança o game tree de OOP check → IP bet closest_to(facing_chips).
/// Retorna true se conseguiu navegar, false se o nó não existe na árvore.
/// Navega root → OOP check → IP to act (nó de DECISÃO de c-bet do IP). Só facing==0.
/// Depois disso, game.strategy()/private_cards(1) são do IP (hero IP).
fn navigate_to_ip_decision(game: &mut PostFlopGame) -> bool {
    let root_actions = game.available_actions();
    match root_actions.iter().position(|a| matches!(a, Action::Check)) {
        Some(i) => { game.play(i); true }   // OOP checa → IP age (c-bet)
        None    => false,
    }
}


/// Navega root → OOP bet closest_to(facing_chips) → IP age (hero IP enfrentando aposta).
/// Para hero IP + facing>0 (ex.: pote 3-bet, OOP c-beta, IP responde). Retorna false se o
/// OOP não tem ação de aposta no root (aí o nó não existe na árvore). Depois disso,
/// game.strategy()/private_cards(1) são do IP.
fn navigate_to_ip_facing_bet(game: &mut PostFlopGame, facing_chips: i32) -> bool {
    let root_actions = game.available_actions();
    let best = root_actions.iter().enumerate()
        .filter_map(|(i, a)| {
            let chips = match a {
                Action::Bet(c) | Action::Raise(c) | Action::AllIn(c) => *c as i32,
                _ => return None,
            };
            Some((i, (chips - facing_chips).abs()))
        })
        .min_by_key(|(_, diff)| *diff);

    match best {
        Some((bet_idx, _)) => { game.play(bet_idx); true }   // OOP aposta → IP age
        None => { game.back_to_root(); false }               // OOP não pode apostar no root
    }
}


fn navigate_to_facing_bet(game: &mut PostFlopGame, facing_chips: i32) -> bool {
    // Passo 1: OOP precisa de uma ação Check disponível
    let root_actions = game.available_actions();
    let check_idx = match root_actions.iter().position(|a| matches!(a, Action::Check)) {
        Some(i) => i,
        None    => return false,
    };
    game.play(check_idx);

    // Passo 2: encontra a aposta do IP mais próxima de facing_chips
    let ip_actions = game.available_actions();
    let best = ip_actions.iter().enumerate()
        .filter_map(|(i, a)| {
            let chips = match a {
                Action::Bet(c) | Action::Raise(c) | Action::AllIn(c) => *c as i32,
                _ => return None,
            };
            Some((i, (chips - facing_chips).abs()))
        })
        .min_by_key(|(_, diff)| *diff);

    match best {
        Some((bet_idx, _)) => {
            game.play(bet_idx);
            true
        }
        None => {
            // IP não tem ação de aposta na árvore — volta para root
            game.back_to_root();
            false
        }
    }
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
