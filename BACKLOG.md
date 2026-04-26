# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprint 1 (infraestrutura coach), Sprint 2 (Student Full View), Sprint 3 (Coach Study Plan Mode) — ver CHANGELOG.

---

## Roadmap de Sprints

| Sprint | Itens | Tema | Esforço | Valor |
|---|---|---|---|---|
| **Sprint 4** | BACK-001 + BACK-005 | Anotações de mãos + Selo revisado | ~12h | Fecha o loop do coaching — coach comenta decisões, aluno vê no replayer |
| **Sprint 5** | BACK-003 + BACK-004 | Coach analytics multi-aluno | ~10h | Coach tem visão consolidada de todos os alunos sem precisar abrir um a um |
| **Sprint 6** | BACK-002 | Feed de progresso + baseline | ~9h | Coach acompanha evolução temporal — argumento de venda do coaching |
| **Sprint 7** | BACK-006 (parte 1) | Perfil estendido do coach + reviews | ~10h | Prepara os coaches para serem descobertos |
| **Sprint 8** | BACK-006 (parte 2) | Diretório público + marketplace | ~10h | Alunos descobrem coaches — crescimento orgânico da plataforma |

### Critérios de priorização
- **Sprint 4 antes de 5/6** — BACK-005 depende de BACK-001; anotações são o core do coaching
- **Sprint 5+6 antes do marketplace** — coaches precisam de ferramentas sólidas antes de serem expostos publicamente
- **BACK-006 dividido em duas sprints** — perfil/reviews primeiro (lado da oferta), diretório depois (lado da demanda)

---

---

## [BACK-001] — Sprint 4 — Anotações em Mãos

**Valor:** Coach comenta decisões específicas de uma mão. O aluno vê a anotação quando revisa aquela mão. Base estruturada para retreinamento do modelo.

### Fluxo
1. No detalhe de uma decisão (aba Torneios ou Mãos Críticas), coach vê campo "Anotação do Coach"
2. Coach escreve o comentário e escolhe o modo:
   - **Complementar** — exibe leak do sistema + nota do coach empilhados
   - **Substituir** — oculta o leak do sistema, exibe apenas a nota do coach
3. Aluno vê a anotação com destaque visual diferente do texto da IA
4. No replayer, ao chegar na ação anotada, o balão do coach aparece no mesmo estilo dos leaks
5. Coach tem painel "Histórico de Anotações" — todas as suas notas por aluno

### Modelo de dados
```sql
CREATE TABLE coach_hand_annotations (
    id           INTEGER PRIMARY KEY,
    coach_id     INTEGER NOT NULL REFERENCES users(id),
    student_id   INTEGER NOT NULL REFERENCES users(id),
    decision_id  INTEGER NOT NULL REFERENCES decisions(id),
    comment      TEXT    NOT NULL,
    mode         TEXT    NOT NULL DEFAULT 'complement',  -- 'complement' | 'replace'
    coach_action TEXT,   -- o que o coach acha correto (pode divergir do sistema)
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coach_id, student_id, decision_id)
);
```

### Endpoints necessários
| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/coach/student/:id/hand-annotations` | Lista todas as anotações do coach para o aluno |
| `POST` | `/coach/student/:id/hand-annotations` | Salva / atualiza anotação por decision_id |
| `DELETE` | `/coach/student/:id/hand-annotations/:decision_id` | Remove anotação |

### Mudanças no Replayer
- `/replay/` e `/coach/student/:id/replay/` retornam `coach_annotations[]` junto à timeline
- Cada `ReplayStep` ganha campo opcional `coach_annotation: { comment, mode, coach_action }`
- UI coach: botão "Comentar" por ação; UI aluno: balão do coach renderizado no passo

### Base de conhecimento / retreinamento
- Registros onde `coach_action != decision.best_action` → divergência coach × sistema → ground truth para correção futura do `decision_engine`

### Esforço estimado
- Backend: ~4h (tabela + 3 endpoints + ajuste no replay endpoint)
- Frontend coach: ~3h (campo de anotação no detalhe de decisão + replayer)
- Frontend aluno: ~2h (exibição do balão no replayer)
- **Total: ~1 sprint pequena**

---

## [BACK-002] — Sprint 6 — Coach Feed & Progresso

**Valor:** Coach acompanha a evolução dos alunos com contexto temporal — feed de atividade, baseline de coaching e relatório de progresso mensal.

### Funcionalidades

**Feed de atividade por aluno**
- Timeline cronológica: "importou torneio X", "atingiu 80% standard", "maior sequência de melhoria"
- Exibido na página do aluno (aba Overview ou painel lateral)

**Baseline de coaching**
- Coach define uma data de início por aluno (quando o coaching começou de fato)
- Comparativo automático: métricas antes vs. depois da baseline
- Armazenado em `coach_baselines (coach_id, student_id, baseline_date)`

**Relatório de progresso mensal**
- Snapshot automático: métricas no início do mês vs. agora
- Leaks eliminados (spots que saíram do top-leaks)
- Disponível como PDF ou view dedicada

### Esforço estimado
- Feed: ~3h (query + frontend timeline)
- Baseline: ~2h (tabela + picker de data + query comparativa)
- Relatório: ~4h (aggregation queries + layout)
- **Total: ~1 sprint média**

---

## [BACK-003] — Sprint 5 — Fila Compartilhada de Erros (Multi-aluno)

**Valor:** Coach vê as piores decisões de **todos os alunos** numa única fila — identifica quem precisa de atenção urgente sem precisar entrar em cada perfil.

### Funcionalidades
- Dashboard do coach: seção "Atenção Urgente" com decisões ordenadas por score (pior primeiro), filtradas por aluno
- Filtros: por aluno, por street, por label (clear_mistake / small_mistake)
- Click na decisão abre diretamente o detalhe do aluno com a decisão destacada

### Esforço estimado
- Backend: ~2h (query cross-student com join)
- Frontend: ~3h (tabela multi-aluno com filtros)
- **Total: ~1 sprint pequena**

---

## [BACK-004] — Sprint 5 — Leaks em Comum Entre Alunos

**Valor:** Coach identifica spots que afetam múltiplos alunos — indica lacuna de ensino sistêmica, não individual.

### Funcionalidades
- Dashboard do coach: seção "Leaks Sistêmicos" — spots ordenados por nº de alunos afetados
- Para cada spot: lista de alunos afetados, score médio, frequência
- Coach pode criar um card de estudo padrão para o spot e aplicar a múltiplos alunos de uma vez

### Esforço estimado
- Backend: ~3h (aggregation cross-student)
- Frontend: ~2h
- **Total: ~1 sprint pequena**

---

## [BACK-006] — Sprints 7+8 — Marketplace de Coaches

**Valor:** Alunos descobrem, avaliam e escolhem coaches dentro da plataforma. Coaches têm vitrine profissional com dados reais de performance. Cria network-effect: quanto mais alunos melhoram, melhor o coach aparece no ranking.

---

### Perfil completo do coach (`/coach-dashboard/profile`)

Campos a adicionar no perfil do professor:

| Campo | Tipo | Descrição |
|---|---|---|
| `photo_url` | text | URL da foto de perfil |
| `experience_years` | int | Anos de experiência como jogador |
| `stakes` | text | Stakes habitualmente jogados (ex: "MTT $5–$50") |
| `coaching_style` | text | Método de coaching: revisão de HH, sessão ao vivo, análise escrita |
| `languages` | text (JSON array) | Idiomas falados (ex: `["pt", "en"]`) |
| `biggest_results` | text (JSON array) | Principais resultados: `[{name, prize, year}]` |
| `price_per_session` | decimal | Preço por sessão (R$ ou USD) |
| `price_monthly` | decimal | Pacote mensal (opcional) |
| `trial_available` | bool | Oferece sessão de avaliação gratuita/reduzida |
| `availability` | text | Disponibilidade semanal (ex: "seg/qua/sex tarde") |
| `social_youtube` | text | Link YouTube |
| `social_twitch` | text | Link Twitch |
| `social_twitter` | text | Link Twitter/X |

**Dado calculado automaticamente pela plataforma** (não declarado pelo coach):
- Nº de alunos ativos na plataforma
- Melhoria média dos alunos: delta de `standard_pct` antes/depois do vínculo

---

### Sistema de avaliações

```sql
CREATE TABLE coach_reviews (
    id          INTEGER PRIMARY KEY,
    coach_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coach_id, student_id)  -- 1 review por aluno por coach
);
```

- Só alunos que **já foram vinculados** ao coach podem avaliar
- Avaliação disponível após desvinculação também (para não criar viés)
- Rating médio exibido como estrelas (1–5) + nº de avaliações
- Reviews recentes (últimas 5) exibidas no perfil público

---

### Diretório público de coaches (`/coaches`)

Página acessível **sem login** (SEO-friendly) e também logada:

- Grid de cards de coach: foto, nome, especialidades, rating, preço, idiomas, nº de alunos
- Filtros: especialidade, faixa de preço, idioma, sessão de avaliação disponível
- Ordenação: melhor avaliado, mais alunos, menor preço
- Busca por nome
- Click no card → perfil completo do coach (`/coaches/:id`)

**Perfil público do coach** (`/coaches/:id`):
- Foto, bio completa, resultados, método de ensino
- Rating com breakdown (quantas estrelas de cada tipo)
- Reviews dos alunos
- Dado de plataforma: "X alunos melhoraram Y% com este coach"
- Botão "Vincular com este coach" (abre o modal com chave de convite)

---

### Endpoints necessários

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/coaches` | Lista coaches públicos com filtros e ordenação |
| `GET` | `/coaches/:id` | Perfil público completo de um coach |
| `POST` | `/coach/review` | Aluno avalia seu coach (atual ou antigo) |
| `GET` | `/coach/reviews` | Coach vê suas próprias avaliações |
| `GET` | `/coach/stats` | Stats calculados: nº alunos, melhoria média |

---

### Esforço estimado
- Backend: ~6h (extensão do schema + queries de ranking + reviews)
- Frontend coach (perfil): ~4h (formulário estendido + upload de foto)
- Frontend aluno (diretório + perfil público): ~6h
- **Total: ~1 sprint grande**

---

## [BACK-005] — Sprint 4 — Selo "Revisado pelo Coach" + Rastreabilidade

**Valor:** Motivação para o aluno + rastreabilidade do coaching no histórico.

### Funcionalidades
- Torneios revisados pelo coach ganham badge "✓ Coach" na listagem do aluno
- Decisões com anotação do coach mostram ícone diferenciado na tabela
- Timeline do aluno exibe marcos de coaching ("Coach revisou este torneio em DD/MM")

### Dependências
- Requer BACK-001 (anotações por decisão) para funcionar completamente

### Esforço estimado
- ~3h (UI somente — dados já existem via BACK-001)

---
