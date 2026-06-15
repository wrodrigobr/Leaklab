# Coach Dashboard V2 — Command Center

**Status:** plano de design (deep dive) · criado 2026-06-15
**Mockup visual:** [`coach-dashboard-v2.html`](coach-dashboard-v2.html) (abrir no browser — brand GrindLab aplicado, gráficos SVG, dados ilustrativos).
**Relação:** mesma jogada do DashboardV2 do jogador — uma **camada visual de comando** por cima do dado que o cockpit (P1a–P3) já entregou. O clássico congela.

---

## 0. Princípio

O coach abre e, **em um olhar**, sabe: a **saúde da turma**, **o que fazer agora** e **quanto vai receber**. Denso como solver (escuro, teal, mono nos números), pensado para **escala** (20 → 200 alunos). O painel deixa de ser *relatório* e vira *ferramenta de trabalho* (worklist).

---

## 1. Inventário das funcionalidades atuais (o que o V2 reorganiza)

| Hoje (6 abas planas) | O que entrega | Para onde vai no V2 |
|---|---|---|
| **Alunos** | lista + busca/filtro/sort + cockpit P1a–P3 (receita, score, atenção, feed) | parte sobe pro **Comando**; tabela vira **Roster** (matriz) |
| **Atenção Urgente** | piores decisões cross-aluno | vira a **Fila de Ação** do Comando |
| **Leaks Sistêmicos** | leaks que afetam 2+ alunos | **Insights** (+ heatmap) |
| **Efetividade** | antes/depois por aluno | **Insights** (vira gráfico) |
| **Financeiro** | receita, payout, histórico | KPIs sobem pro Comando; detalhe na aba **Receita** |
| **Mensagens** | inbox | **Mensagens** (mantém) |
| **StudentDetail** | 6 sub-abas (overview/torneios/críticas/plano/progresso/msg) | **Aluno V2** (hero + abas elevadas) |

**Lacuna que o V2 cria:** não existe hoje **fila de ação priorizada** nem **sinal de risco de churn** — são os dois maiores ganhos.

---

## 2. Arquitetura de informação (6 planas → 5 contextuais)

- **Comando** (home) — worklist + vitais + atividade + gráficos-chave.
- **Alunos** (roster) — matriz de triagem da turma inteira.
- **Insights** — Leaks Sistêmicos + Efetividade + analytics da turma (gráficos).
- **Receita** — Financeiro detalhado (payout, histórico, conversão).
- **Mensagens** — inbox.

---

## 3. Comando (home) — o coração do V2

**A. Vitais (strip de topo):** Ativos·R$ (sparkline) · A receber + próxima faixa · Indicados · Melhora média (sparkline) · **Precisam de atenção (N)**.

**B. Fila de Ação** (priorizada por impacto) — o diferencial:
1. **Críticas pendentes** (mãos small/clear sem anotação do coach) → "Revisar".
2. **Mensagens não lidas** → "Responder".
3. **Risco de churn** (em queda há N sessões; ou pro+ativo virando inativo) → "Abrir".
4. **Conversão de receita** (recente mas *free* → não conta no repasse) → "Converter".
Cada item: ícone, título, contexto, selo de prioridade, CTA.

**C. Atividade recente** — feed cross-aluno (P2, elevado): aluno · torneio · score colorido · ⚠ críticas · data.

**D. Gráficos** (ver §5).

---

## 4. Roster (Alunos) V2 — matriz de triagem

Cada linha: avatar + nome + **selos** (Indicado / Ativo·R$ / Recente·free / Inativo / plano) · **sparkline de tendência** · **score** colorido (3 níveis) · **sinais** (⚠ críticas, ✉ não-lidas, 📉 queda) · último import. Ordena por **precisa de atenção** / score / ativo / indicado. (Reusa o payload já enriquecido em P1a/P1b; aqui é estilo + sparkline.)

---

## 5. Catálogo de gráficos (o "visual" pedido)

| Gráfico | O que mostra | Fonte de dado | Viz |
|---|---|---|---|
| **Distribuição de qualidade da turma** | quantas decisões Correto/Aceitável/Erro | labels (3 níveis, FEAT-20) agregados | barras |
| **Receita & ativos no tempo** | R$ por mês + faixas de payout (4+/10+) | `coach_payments` por período + `calculate_coach_payout` | linha + bandas |
| **Heatmap de leaks da turma** | street × ação, nº de alunos com leak ali | `get_leak_roi_impact` agregado por aluno | grid de cores → drill por spot |
| **Sparkline de tendência (por aluno)** | curva de score recente | evolution por aluno (já existe) | sparkline na linha do roster |
| **Funil ativo / indicado / inativo** | composição da turma | students + finance | donut/barras |
| **Efetividade (waterfall)** | melhora antes→depois por aluno | dados de Efetividade (já existem) | barras delta |

---

## 6. Sinais NOVOS (não existem hoje)

- **Risco de churn:** "em queda há N sessões" (derivável do evolution) e "pro+ativo prestes a inativar" (último import perto de 30d). Vira **item da fila** e **selo no roster**. Alto valor: retenção = receita.
- **Conversão:** "recente mas free" já é detectável (P1a) — vira CTA de receita na fila.

---

## 7. Linguagem visual (brand GrindLab)

bg `#0A0E1A` · teal `#2DD4BF` (acento/CTA) · Chakra Petch (títulos/números grandes) · JetBrains Mono (numéricos) · cards HUD com borda sutil + glow. Cores semânticas: **emerald/sky/red** (veredito 3 níveis, FEAT-20), **violet** (indicação/coach), **amber** (atenção/receita). Densidade de solver: tabelas compactas, sparklines, sem espaço morto.

---

## 8. Back-end (pouco novo — quase tudo já existe)

- **`GET /coach/action-queue`** (NOVO): agrega o que já é calculável — críticas pendentes (`get_students_attention_signals`), não-lidas (idem), queda (evolution), free-recente (P1a) → lista priorizada.
- **`GET /coach/cohort-analytics`** (NOVO): distribuição de qualidade + receita-no-tempo + heatmap de leaks (reusa `get_leak_roi_impact`, `coach_payments`).
- Resto: `/coach/students` (enriquecido), `/coach/finance/summary`, `/coach/recent-activity` — **já existem** (P1a–P3). Charts no front com SVG/recharts (já no projeto).

---

## 9. Faseamento

- **V2-1 ✅ — Comando (home):** nova aba **Comando** (default) = vitais (ativos·R$/a receber+próxima faixa/indicados/total/precisam atenção) + **Fila de Ação** priorizada (críticas → churn → não-lidas → conversão, cada com CTA deep-link) + atividade recente. **Sem endpoint novo:** a fila é agregada no front a partir do payload já enriquecido de `/coach/students` (critical_pending/unread/trend/is_active_paid/plan) — mais barato que a spec original sugeria e sem N+1. Churn = `trend==='worsening' && is_active_paid`. *(tsc/build ok.)*
- **V2-2 — Gráficos da turma:** distribuição, receita-no-tempo, heatmap. (1 endpoint cohort-analytics + SVG/recharts)
- **V2-3 — Roster V2:** matriz com sparklines + selos + ordenação "precisa de atenção". (front sobre payload já pronto)
- **V2-4 — Aluno detalhe V2:** hero + abas elevadas. (estilo; reusa dados)
- **Sinal de churn** entra no V2-1 (fila) e V2-3 (roster).

---

## 10. Decisões / dependências
1. **Toggle V2 vs clássico** (como no DashboardV2 do jogador) ou substituição direta? Sugiro toggle até validar.
2. **"Indicado"** confiável depende do **SEC-01** (single-use); até lá, `invited_by_key`.
3. **"Ativo"** = pro + import 30d (régua única já adotada no P1a; cruza com **PAY-01**).
4. **Risco de churn:** definir o gatilho exato (N sessões em queda? Δstd%? proximidade de 30d sem import?) — decisão de produto.
