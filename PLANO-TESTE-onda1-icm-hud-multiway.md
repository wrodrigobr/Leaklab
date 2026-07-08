# Plano de teste — Onda 1 (base de conhecimento GTO Wizard)

Cobre as 3 entregas desta onda:
- **A. Gate zona-ICM** (Top 7 #1) — aperto correto sob ICM não é mais "Erro".
- **B. Notas de exploit Station** (Top 7 #3) — enriquecidas + variantes na zona de ICM.
- **C. Cauda segura multiway** (Top 7 #4) — re-validação (grading já live em prod).

> Convenção de resultado dos runners: cada suíte termina em `Total: X | Passed: Y | Failed: Z`. Não há pytest.

---

## 0. Pré-requisitos

```bash
# backend
cd backend && pip install -r requirements.txt -r requirements_test.txt
# frontend
cd frontend && npm install
```

No Windows, prefixe os testes com `PYTHONIOENCODING=utf-8` (o runner imprime emoji; o cp1252 do console quebra sem isso — é erro de console, não de teste).

---

## 1. Testes automatizados (regressão)

| # | Suíte | Comando | Esperado |
|---|---|---|---|
| 1.1 | Engine (inclui gate ICM) | `python tests/run_all_tests.py --suite engine` | 395 ok, 0 falhas |
| 1.2 | HUD de oponente (inclui variantes ICM) | `python tests/test_opponent_stats.py` | 15 ok, 0 falhas |
| 1.3 | Cauda segura multiway | `python tests/test_multiway_safety.py` | 14 ok, 0 falhas |
| 1.4 | API (inclui replay + HUD) | `python tests/run_all_tests.py --suite api` | 117 ok, 0 falhas |
| 1.5 | Frontend typecheck | `cd frontend && npx tsc --noEmit` | exit 0 |
| 1.6 | Suíte completa (opcional) | `python tests/run_all_tests.py` | 0 falhas |

**Testes novos a conferir por nome:**
- `test_decision_engine.py::test_icm_gate_softens_tight_fold` — helper puro dispara no caso certo.
- `test_decision_engine.py::test_icm_gate_scope_is_narrow` — NÃO dispara em agressão, pressão baixa, mesa cheia, best=fold.
- `test_decision_engine.py::test_icm_gate_downgrades_error_fold_in_engine` — o Erro vira 'marginal' + `icm_zone_approx=True` no engine; controle (icm=low) mantém o Erro.
- `test_opponent_stats.py::test_exploit_station_icm_zone_variants` — variantes `_icm` na zona; notas normais fora dela.

**Invariantes que NÃO podem regredir** (rodar a suíte completa cobre):
- "Erro nunca vira Correto" por direção (GTO folda ↔ hero agride) — o gate ICM só toca FOLDS, é ortogonal.
- Multiway fora da cauda segura segue informativo (não pune).

---

## 2. Validação manual em DEV

Suba o stack:
```bash
cd backend && python api/app.py         # :5000
cd frontend && npm run dev              # :8080 (proxy /api → :5000)
```

### A. Gate zona-ICM

**Achar candidatos concretos** (read-only, imprime links do Replayer):
```bash
cd backend && python scripts/diag_icm_gate.py --limit 30
```
Lista folds do hero em que o ChipEV manda continuar (best = call/raise/shove) e a pressão de ICM é alta. Abra os links (`/replayer?t=CODE&h=HAND`).

| Caso | Setup | Esperado |
|---|---|---|
| A1 — dispara | Fold em mesa curta (active ≤ 6) + pressão ICM alta, ChipEV recomenda continuar | Card mostra **"≈ Aproximação chipEV"** (âmbar), tooltip explica ICM. NÃO é "✗ Erro". A ação (fold) não é marcada como errada. |
| A2 — controle (não dispara) | Mesmo tipo de fold, mas mesa cheia (active > 6) na mesma pressão, ou pressão não-alta | Segue **"✗ Erro"** (leak real preservado). |
| A3 — escopo | Um call/shove loose que o ChipEV reprova, em zona-ICM | Segue avaliado normalmente (o gate NÃO abranda agressão). |
| A4 — i18n | Trocar idioma PT/EN/ES | Selo e tooltip traduzidos (`vApproxIcm`/`srcIcm`/`tipIcmApprox`). |

**Onde olhar:** o selo aparece no banner de veredito do Decision Card do step do hero. Consistência: o mesmo step não pode aparecer como "Erro" em nenhuma outra superfície (lista, badge).

### B. Notas de exploit Station

O HUD de oponente exige `confidence='high'` (≥ 100 mãos do vilão) — use um torneio com um vilão bem amostrado classificado como calling station.

| Caso | Setup | Esperado |
|---|---|---|
| B1 — value | Hero aposta por valor vs station, fora de ICM | Nota "Calling station: engorde o value…" com orientação de sizing (2/3+, top ~60%, engorde os nutted, corte blefes). |
| B2 — value em ICM | Mesmo spot, mas step em pressão ICM alta | Nota **`value_thicker_station_icm`** (mais forte, "engorde ainda mais", severidade alta). |
| B3 — blefe em ICM | Hero blefa vs station em pressão ICM alta | Nota **`dont_bluff_station_icm`** ("blefe zero…"). |
| B4 — sem amostra | Vilão com < 100 mãos | Nenhuma nota (sem palpite). |
| B5 — i18n | PT/EN/ES | Textos traduzidos nas 3 locales. |

### C. Cauda segura multiway (re-validação)

```bash
cd backend && python scripts/audit_multiway_safety.py --sims 4000 --limit 800
```
| Esperado |
|---|
| ~21% de cauda segura (SAFE_FOLD + SAFE_VALUE); N spots com ação do hero contrariando o veredito seguro. Read-only, não escreve nada. |

O grading da cauda segura já está **ligado em prod** (`MULTIWAY_GRADE_SAFE_TAIL=1` desde 2026-06-29). Validação visual (se quiser, com a flag on no dev): safe_fold + hero continua → "✗ Erro"; safe_value + hero passa → "✗ Erro"; ação garantida → "✓ Correto"; meio ambíguo → informativo.

---

## 3. Smoke test pós-deploy (PROD)

Deploy necessário: **A** e **B** precisam de `git pull && docker compose up -d --build web` no CX23 + rebuild do frontend (Cloudflare). **C** já está live (sem deploy).

1. `/history/tournaments` responde 200 (sem regressão do fix do `?` em comentário SQL).
2. Abrir um replay recente com fold em zona-ICM → conferir o selo "≈ Aproximação chipEV".
3. Abrir um replay com vilão calling station bem amostrado → conferir a nota enriquecida.
4. Conferir que um fold ChipEV-reprovado em early/mid full-ring segue "✗ Erro" (o gate não vazou).
5. Sanidade de ELO/leaks: um torneio de mesa final não deve mais listar folds de ICM defensáveis como top leaks.

> Torneios importados ANTES do deploy só mudam o veredito ao serem **reabertos no Replayer** (re-avaliação ao vivo). As stats/ELO usam o `label` armazenado; só novas análises entram já com o gate. Não há re-grade em massa.

---

## 4. Critérios de aceite

- [ ] 1.1–1.6 todos verdes.
- [ ] A1 mostra o selo; A2 mantém o Erro; A3 não abranda agressão.
- [ ] B1–B3 mostram as notas certas; B4 não mostra nada.
- [ ] C reporta ~21% de cauda segura.
- [ ] Nenhuma superfície mostra o mesmo step como "Erro" e "≈ Aproximação" ao mesmo tempo.
