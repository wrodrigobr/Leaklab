# Glossário

## Qualidade da decisão (dois eixos)

- **`label`** (heurística, reconciliada com gto): `standard` (ok) · `marginal` ·
  `small_mistake` · `clear_mistake`. Severidade 0→3.
- **`gto_label`** (aderência ao solver):
  - `gto_correct` — ação que o GTO joga ≥60% das vezes.
  - `gto_mixed` — ação numa freq 30–59% (mista).
  - `gto_minor_deviation` — freq 10–29% (desvio pequeno).
  - `gto_critical` — freq <10% (erro claro).
  - **NULL** — sem cobertura GTO (NULL honesto, INV-3).
- `label` e `gto_label` **concordam por design** (reconciliação, INV-2).

## Cenários preflop

- **`rfi`** — Raise First In: hero é o primeiro a abrir.
- **`vs_rfi`** — hero defende vs um open simples (1 raise).
- **`vs_3bet`** — hero abriu e enfrenta um 3bet.
- **`squeeze`** — hero dá 3bet sobre open + cold-caller (é o squeezador).
- **`faces_squeeze`** — hero cold/blind **enfrenta** open+3bet/squeeze sem ter aberto.
- **`vs_4bet`** — hero 3betou e enfrenta um 4bet (não implementado — backlog #21).

## Sinais de roteamento

- **`facing_raises` / `preflop_raises_faced`** — nº de raises enfrentados (open=1, 3bet=2). **Distingue vs_rfi de faces_squeeze** (INV-1).
- **`hero_was_aggressor`** — hero foi o agressor (abriu/3betou) antes desta ação. Distingue vs_3bet de faces_squeeze.
- **`facing_size`** — tamanho (bb) que o hero enfrenta. **Não** ajusta a range pelo sizing (INV-8).

## Captura / GW

- **GTO Solver** — branding interno para o GTO Wizard (nunca expor "GTO Wizard"/"RegLife" no produto).
- **pf / preflop_actions** — sequência de ações em seat order: `F` fold, `C` call/complete, `R{x}` raise to x bb, `RAI` all-in.
- **history_spot** — índice do nó que a SPA do GW abre = nº de tokens de ação (INV-5).
- **bucket** — faixa de stack de referência (10/14/17/20/30/40/50/75/100bb).
- **depth válido** — profundidade que o GW MTT resolve (irregular; 70bb não existe — INV-4).

## Resultado

- **`hero_won_hand`** — 1/0/NULL: hero coletou o pote (com ou sem showdown). Base do Results×GTO (INV-9).
- **`showdown_result`** — won/lost/NULL: só quando hero mostrou cartas no showdown.
