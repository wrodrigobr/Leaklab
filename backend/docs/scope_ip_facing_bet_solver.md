# Scope — cobertura GTO para hero IP enfrentando aposta (postflop)

> **STATUS: Fase 1 ✅ DEPLOYADA + Fase 2 ✅ IMPLEMENTADA.** Fase 1 (navigate_to_ip_facing_bet
> no main.rs, deployado + flag + precompute). Fase 2 (ranges de pote 3-bet via hash backward-
> compat — `compute_spot_hash` com `pot_type`; 3-bettor=`vs_RFI.raise`, caller=`vs_3bet.call`;
> precompute_3bet_pots.py). Único pendente: 4-bet pots (1%) usam aproximação SRP.

## Problema

Quando o hero é **IP** e **enfrenta uma aposta** postflop (ex.: pote 3-bet, BB c-beta o flop,
hero BTN dá flat call IP), não há veredito GTO — só heurístico. É um **bloqueio deliberado**,
não um bug:

```python
# gto_solver.py:367
_ip_blocked = _hero_ip and not (_TEXAS_HERO_IP and facing_size_bb == 0.0)
```

O patch IP (`hero_is_ip` no main.rs) só sabe navegar até o nó de **c-bet** do IP
(`root → OOP check → IP age`). Não há navegação para `root → OOP bet → IP age`. O main.rs
aborta explicitamente:

```rust
// main.rs:206
if inp.hero_is_ip && !ip_node {
    return Err("hero_is_ip: facing>0 IP nao suportado (sem no de c-bet)".to_string());
}
```

## Causa-raiz (Rust)

`main.rs` tem 3 navegações de nó, falta a 4ª:

| Cenário | Função | Existe? |
|---|---|---|
| hero OOP, primeira ação (root) | — (root direto) | ✅ |
| hero OOP enfrentando aposta | `navigate_to_facing_bet` (OOP check → IP bet → OOP age) | ✅ |
| hero IP, c-bet | `navigate_to_ip_decision` (OOP check → IP age) | ✅ |
| **hero IP enfrentando aposta** | **`navigate_to_ip_facing_bet` (OOP bet → IP age)** | ❌ |

O nó EXISTE na árvore CFR solvada (a árvore tem OOP podendo bet no root → IP responde). Só
falta navegar até ele e ler `strategy()` do player 1 (IP).

## Mudanças

### 1. Rust — `solver_cli/src/main.rs` (núcleo)

**a)** Nova função (espelha `navigate_to_facing_bet`, mas sem o OOP check — OOP aposta no root):

```rust
/// Navega root → OOP bet closest_to(facing_chips) → IP age (IP enfrentando aposta).
/// Para hero IP + facing>0. Depois: strategy()/private_cards(1) são do IP.
fn navigate_to_ip_facing_bet(game: &mut PostFlopGame, facing_chips: i32) -> bool {
    let root_actions = game.available_actions();
    let best = root_actions.iter().enumerate()
        .filter_map(|(i, a)| match a {
            Action::Bet(c) | Action::Raise(c) | Action::AllIn(c) =>
                Some((i, (*c as i32 - facing_chips).abs())),
            _ => None,
        })
        .min_by_key(|(_, diff)| *diff);
    match best {
        Some((bet_idx, _)) => { game.play(bet_idx); true }
        None => { game.back_to_root(); false }
    }
}
```

**b)** Reescrever o bloco de navegação em `run()` (linhas ~195-208):

```rust
let hero_player: usize = if inp.hero_is_ip { 1 } else { 0 };
let facing_chips = (inp.facing_size_bb * 100.0).round() as i32;
let (facing_node, nav_ok) = if inp.hero_is_ip {
    if inp.facing_size_bb > 0.0 {
        let ok = navigate_to_ip_facing_bet(&mut game, facing_chips);
        (ok, ok)                       // pot cresceu com a aposta → facing_node=true
    } else {
        (false, navigate_to_ip_decision(&mut game))
    }
} else if inp.facing_size_bb > 0.0 {
    let ok = navigate_to_facing_bet(&mut game, facing_chips);
    (ok, ok)
} else {
    (false, true)                      // hero OOP root
};
if !nav_ok {
    return Err("navegacao do no falhou".to_string());
}
```

Remove o `if inp.hero_is_ip && !ip_node { return Err(...) }`. O `label_pot` (pot + facing)
já fica correto com `facing_node=true`.

**Tamanho:** ~1 função nova + ~15 linhas reescritas. Contido, sem mudar o resto do solver.

### 2. Python — `gto_solver.py`

Liberar o lookup IP+facing>0, **atrás de um flag novo** (rollout seguro — o binário antigo na
VM aborta com facing>0 até o redeploy):

```python
_TEXAS_HERO_IP_FACING = os.environ.get('TEXAS_HERO_IP_FACING', '0') == '1'
...
# linha 367
_ip_blocked = _hero_ip and not (
    _TEXAS_HERO_IP and (facing_size_bb == 0.0 or _TEXAS_HERO_IP_FACING)
)
```

`_facing_unconvertible` (precisa de `bb_chips` p/ converter o facing) já cuida do resto — sem
mudança. A atribuição de ranges (linhas 392-401) **não muda nesta fase** (ver Caveat).

### 3. Deploy (VM GCP, `/opt/leaklab`)

```
ssh → cd /opt/leaklab/backend/gto_bot/solver_cli
git pull
cargo build --release            # ~1-3 min
sudo systemctl restart leaklab-solver
```

Validar o binário ANTES de ligar o flag: mandar um payload `hero_is_ip=true, facing_size_bb>0`
direto no /solve e conferir que volta estratégia (não erro).

### 4. Precompute (pra aparecer no /replay)

O /replay é read-only (`allow_remote_solve=False`) → não solva na request. Os nós IP-facing-bet
precisam ser **precomputados** e gravados em `gto_nodes`, senão o card continua heurístico mesmo
com o fix. Estender `scripts/precompute_common_spots.py` (ou um `requeue_ip_facing_bet.py`) pra
enfileirar os spots IP-facing-bet dos torneios existentes, com `GTO_SOLVER_URL` + `allow_remote_solve=True`.

## ⚠️ Caveat de RANGES (o ponto mais importante)

O solver hoje **sempre** assume **pote single-raised** (linhas 398-401):
`ip_range = opener (RFI)`, `oop_range = caller (call vs RFI)`.

O spot do usuário é um **pote 3-bet**: OOP (BB) é o 3-bettor/agressor; IP (BTN) é o caller. As
ranges corretas seriam `oop = range de 3-bet`, `ip = range de call-vs-3bet`. Com as ranges SRP
atuais, o nó "OOP bet → IP age" modela um **donk de SRP**, não um **c-bet de pote 3-bet** —
então a estratégia do IP sairia **aproximada/enviesada** justamente no caso mais comum.

**Importante:** essa aproximação **já existe** na cobertura atual de OOP-facing-bet (o nó que
serve hoje também usa ranges SRP em potes 3-bet). Então:

- **Fase 1 (Rust + flag):** traz IP-facing-bet à **paridade** com o que já existe pra OOP —
  correto em SRP (donk), aproximado em pote 3-bet. Entrega rápida, consistente.
- **Fase 2 (follow-up, maior):** ranges cientes do tipo de pote (3-bet ranges do GW) — corrige
  3-bet pots para IP **e** OOP de uma vez. Depende de ter as ranges 3-bet capturadas e de
  passar o tipo de pote (preflop_raises_faced/aggressor) ao solver.

Recomendação: entregar Fase 1 (fecha a lacuna estrutural, paridade), e tratar a correção de
ranges de pote 3-bet como item separado de roadmap (impacta toda a cobertura postflop, não só IP).

## Validação

1. **Unit Rust:** payload sintético `hero_is_ip=true, facing_size_bb=5, board flop` → retorna
   `strategy` com ações do IP (fold/call/raise), não bet/check.
2. **Jogador certo:** conferir que a estratégia é do IP (player 1), não do OOP — comparar com o
   nó OOP do mesmo board (devem diferir; o IP responde, o OOP aposta).
3. **Mão de referência:** `t=27 h=100000009` flop/call (IP vs 7.13bb) → passa de heurístico a
   coberto, com estratégia plausível (call/raise/fold).
4. **Sem regressão:** os 3 cenários existentes (OOP root, OOP-facing, IP c-bet) inalterados —
   o flag novo só adiciona o 4º caminho.
5. **Exploitability:** o nó solvado deve ter exploitability dentro do alvo (senão é descartado
   pelo pipeline, como os outros).

## Riscos

| Risco | Mitigação |
|---|---|
| Jogador errado (regressão do bug original) | Flag separado + validação #2 antes de ligar; binário valida player 1 |
| Ranges SRP enganosas em pote 3-bet | Caveat documentado; selo de aproximação; Fase 2 separada |
| Solve lento / VM single-thread | Precompute offline (não na request); /replay continua read-only |
| Binário antigo na VM aborta facing>0 IP | Flag default OFF até redeploy confirmado |
| `bb_chips` ausente → facing inconvertível | `_facing_unconvertible` já pula (heurístico, sem nó errado) |

## Esforço

- Fase 1 (Rust + Python flag + deploy + precompute + validação): **contido** — a mudança Rust é
  pequena e localizada; o grosso é deploy/precompute/validação.
- Fase 2 (ranges de pote 3-bet): **maior** — toca a modelagem de ranges de toda a cobertura
  postflop; depende de captura de ranges 3-bet.
