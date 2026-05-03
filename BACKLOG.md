# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–L + BACK-008 + BACK-015 — ver CHANGELOG v0.9.0 a v0.43.0.
> **Sprint atual:** — aguardando priorização

---

## Princípio de Produto

> **A plataforma é primariamente um coach IA autônomo para o aluno.**
> O aluno não precisa — e nunca deve precisar — de um coach humano para extrair valor completo do sistema.
> Análise de leaks, plano de estudos, replayer, gamificação e evolução de score são o **core** e funcionam de forma independente.
>
> O marketplace de coaches humanos é uma **camada adicional opcional** — um upgrade de valor, não um pré-requisito.
> Calls-to-action de contratação de coach devem ser **suaves e contextuais**, jamais bloqueantes ou centrais no fluxo principal.
> Sprints de IA têm prioridade estratégica maior do que sprints de marketplace.

---

## Roadmap de Sprints — Status Atual

| Sprint | Itens | Tema | Status |
|---|---|---|---|
| Sprint 1–3 | — | Infraestrutura, Student View, Study Plan | ✅ v0.9.0–v0.10.2 |
| Sprint 4 | BACK-001 + BACK-005 | Anotações de mãos + Selo Coach | ✅ v0.12.0 + v0.32.0 |
| Sprint 5 | BACK-003 + BACK-004 | Coach analytics multi-aluno | ✅ v0.13.0 |
| Sprint 6 | BACK-002 | Feed de progresso + baseline | ✅ v0.14.0 |
| Sprint 7 | BACK-006 pt.1 | Perfil estendido + reviews | ✅ v0.15.0 |
| Sprint 8 | BACK-006 pt.2 + BACK-013 | Diretório público + descoberta contextual | ✅ v0.16.0 |
| Sprint 9 | BACK-007 + BACK-012 | Upload múltiplo + perfil coach unificado | ✅ v0.17.0 |
| Sprint 10 | BACK-009 | Sistema de nível + gamificação | ✅ v0.18.0 |
| — | BACK-008 | Visualizador de ranges no replayer | ✅ v0.19.0 |
| Sprint 11 | BACK-010 | Planos comerciais + quota | ✅ v0.22.0 |
| Sprint 12 | BACK-011 | Anti-injection + moderação de conteúdo | ✅ v0.26.0–v0.27.0 |
| Sprint 13 | UX-004 | Menu de conta com plano e uso | ✅ v0.25.0 |
| Sprint A | UX-001 + UX-003 | Lista de torneios + tooltips auto-explicativos | ✅ v0.31.0 |
| Sprint 15 | BACK-015 | Gateway de pagamento (Stripe) | ✅ v0.29.0 |
| Sprint B | UX-002 | Responsividade mobile/tablet | ✅ v0.33.0 |
| Sprint C+E | BACK-014 + BACK-017 | Revenue share + Admin Panel | ✅ v0.34.0 |
| Sprint D | BACK-016 | WhatsApp Coaching Drills | ✅ v0.36.0 |
| Sprint F | UX-005 | Internacionalização (i18n) — PT/EN/ES | ✅ v0.35.0 |
| Sprint G | UX-006 | Header cleanup + i18n full coverage | ✅ v0.37.0 |
| Sprint H | UX-007 | Dashboard cards i18n — 11 componentes | ✅ v0.38.0 |
| Sprint I | PERF-001 + PERF-002 | ROI Attribution Engine + Leak Priority Optimizer | ✅ v0.39.0 |
| Sprint J | PERF-003 + PERF-004 + PERF-005 | Leak Progression + Pressure Collapse + Confidence Drift | ✅ v0.40.0 |
| Sprint K | PERF-006 | Ghost Table Simulator MVP | ✅ v0.41.0–v0.42.0 |
| Sprint L | PERF-007 | Decision DNA — assinatura estratégica do jogador | ✅ v0.43.0 |

---

## Próximas Sprints — Em Aberto

### ~~[PERF-007] — Decision DNA~~ ✅ *Entregue em v0.43.0*

---

### [PERF-008] — Tournament Narrative Engine *(Sprint M — prioridade média)*

**Valor:** Alto · **Complexidade:** Média · **Dep. estrutural:** Leve (LLM)

Gerar narrativa estratégica de 2–3 frases por torneio descrevendo o arco de qualidade da sessão. Ex: *"Jogo sólido até o nível 6. Colapso técnico detectado após mão X com alta pressão ICM no FT."*

**Dados já disponíveis:** `evolution`, `standard_pct` por fase, `icm_pressure`, `best_action` vs. `action_taken`, `collapse_delta`.

**Backend:**
- `llm_explainer.py` — `generate_tournament_narrative(tournament_id)`: monta prompt com arco de qualidade + eventos-chave + contexto ICM; chama Claude Haiku; cache por `tournament_id`
- `app.py` — narrativa gerada on-demand (botão no detalhe do torneio) ou background task pós-import

**Frontend:**
- `TournamentDetail.tsx` — seção "Narrativa da Sessão" com texto gerado + badge de qualidade geral

**Riscos:** qualidade dependente de prompt engineering; adicionar fallback determinístico se LLM falhar.

**Esforço estimado: ~4h backend + ~3h frontend**

---

### [PERF-009] — GGPoker Parser *(Sprint N — prioridade alta)*

**Valor:** Muito Alto · **Complexidade:** Média · **Dep. estrutural:** Leve

Parser atual suporta apenas PokerStars. GGPoker tem formato diferente (blinds, nomenclatura, hero cards inline). Expandir o parser para aceitar ambos os formatos amplia o mercado endereçável significativamente.

**Esforço estimado: ~6h backend + ~2h frontend (upload aceita ambos)**

---

### Backlog Futuro (não priorizar agora)

| Item | Motivo de adiar |
|---|---|
| Counterfactual Replay | Exige simulação Monte Carlo prospectiva — não temos equity calculator para linhas hipotéticas |
| Reg Archetype Recognition | Exige dados de adversários; fora do escopo atual (análise do herói, não do field) |
| Competitive Benchmark Layer | Exige pool de dados de outros usuários; questões de privacidade + volume mínimo de usuários |
