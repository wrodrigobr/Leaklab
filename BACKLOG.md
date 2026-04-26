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
| **Sprint 9** | BACK-007 | Importação múltipla com fila | ~6h | UX de upload em escala — usuário importa toda a semana de uma vez |
| **Sprint 10** | BACK-009 | Sistema de nível + gamificação | ~8h | Progressão clara — aluno sabe onde está e o que falta; coach usa como referência |
| **Sprint 11** | BACK-010 | Planos comerciais + monetização | ~12h | Plataforma sustentável — freemium para alunos, revenue share para coaches |
| **Sprint 12** | BACK-011 | Segurança: anti-injection + moderação de conteúdo | ~8h | Plataforma segura para uso público — proteção contra abuso de IA e conteúdo inapropriado |

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

## [BACK-007] — Importação Múltipla de Torneios (Fila + Badge de Progresso)

**Valor:** Usuário arrasta N arquivos de uma vez → sistema processa em fila → cada torneio recebe badge de status em tempo real. Elimina o ciclo manual de upload-esperar-upload.

### Fluxo
1. Upload aceita múltiplos arquivos (input `multiple` ou drag-and-drop de vários `.txt`)
2. Cada arquivo entra numa fila local exibida na UI (tabela com nome, status, progresso)
3. Processamento sequencial ou paralelo (limite de 2 simultâneos para não saturar o backend)
4. Badge por arquivo: `Em fila` → `Processando…` → `Analisado ✓` / `Erro ✗`
5. Ao terminar todos, reload automático da lista de torneios

### Estados do badge
| Estado | Cor | Ícone |
|---|---|---|
| Em fila | muted | Clock |
| Processando | amber | Loader2 (spin) |
| Analisado | primary | CheckCircle2 |
| Erro | destructive | AlertTriangle |

### Mudanças de backend
- Nenhuma obrigatória — `/analyze` já processa um arquivo por chamada
- Opcional: endpoint `/analyze/batch` para futura paralelização no servidor

### Mudanças de frontend
- Componente `UploadQueue` — gerencia fila com `useReducer`
- `useEffect` que despacha chamadas sequencialmente à `/analyze`
- Persistência da fila em `sessionStorage` (recarregar página mantém o estado)

### Esforço estimado
- Frontend: ~5h (fila + badges + retry logic)
- Backend: ~1h (opcional: endpoint batch)
- **Total: ~1 sprint pequena**

---

## [BACK-010] — Planos Comerciais + Monetização

**Valor:** Define o modelo de negócio da plataforma — freemium para alunos com limite de uso de IA, plano pago para acesso total, e modelo de receita para coaches baseado em alunos ativos e/ou indicações.

---

### Planos para alunos

| Plano | Preço | Limites | Diferencial |
|---|---|---|---|
| **Free** | Gratuito | 3 torneios/mês · 10 análises de IA/mês · sem coach | Análise básica de erros |
| **Pro** | R$ 29/mês | Ilimitado · coach vinculável · todas as features | Plano de estudos completo + replayer + ranking |
| **Coach** | R$ 49/mês | Todas as features Pro + painel multi-aluno + perfil público | Vitrine no marketplace |

> Valores ilustrativos — ajustáveis por configuração sem alteração de código.

---

### Modelo de receita para coaches

**Opção A — Revenue share por aluno ativo:**
- Coach paga R$ 49/mês base
- Desconto proporcional: cada aluno Pro vinculado = desconto de R$ 5/mês no plano do coach
- Incentivo: quanto mais alunos engajados, menor o custo do coach

**Opção B — Comissão por indicação:**
- Coach recebe link de indicação único (`?ref=<invite_key>`)
- Alunos que assinam Pro via link do coach: plataforma repassa X% no mês seguinte
- Rastreado por `invited_by_key` já existente na tabela `users`

**Opção C (futuro):** marketplace onde aluno paga a sessão direto na plataforma e a plataforma retém % (requer integração com Stripe/PagSeguro)

---

### Controle de limites de IA

Campos necessários para tracking mensal por usuário:

```sql
ALTER TABLE users ADD COLUMN ai_calls_this_month INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN ai_calls_reset_at   DATE;
ALTER TABLE users ADD COLUMN tournaments_this_month INTEGER NOT NULL DEFAULT 0;
```

Middleware a adicionar em `app.py`:
- `_check_ai_quota(user_id)` — antes de qualquer chamada ao LLM: verifica se o usuário Free atingiu o limite; retorna 402 com mensagem de upgrade
- `_check_upload_quota(user_id)` — antes de `POST /analyze`: mesma lógica para torneios
- Reset automático no 1º de cada mês (via scheduled job ou lazy reset na primeira chamada do mês)

---

### Integração de pagamentos (escopo futuro / opcional nesta sprint)

- **Stripe** (recomendado): `stripe.checkout.Session` → webhook `checkout.session.completed` → atualiza `users.plan`
- **PagSeguro** — alternativa BR
- Sprint desta entrega: apenas estrutura de planos + quotas de uso; pagamento manual/externo é aceitável na v1

---

### Endpoints necessários

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/subscription/plans` | Lista planos disponíveis com preços e limites |
| `GET` | `/subscription/status` | Plano atual do usuário + uso do mês |
| `POST` | `/subscription/upgrade` | Inicia fluxo de upgrade (redireciona para Stripe ou marca manualmente) |
| `GET` | `/coach/referrals` | Coach vê seus alunos indicados e comissões acumuladas |

---

### Esforço estimado
- Backend: ~6h (quotas + middleware + endpoints + reset mensal)
- Frontend aluno: ~3h (banner de upgrade + indicador de uso do mês)
- Frontend coach: ~3h (painel de indicações + earnings)
- **Total: ~1 sprint grande**

---

## [BACK-011] — Segurança: Anti-Prompt Injection + Moderação de Conteúdo

**Valor:** Proteger a plataforma contra abuso da IA (usuários tentando desviar o comportamento dos modelos via input malicioso) e garantir que reviews e anotações de coaches não contenham conteúdo inapropriado antes de serem exibidos publicamente.

---

### Camada 1 — Anti-Prompt Injection

**Riscos atuais:**
- Usuário envia hand history com texto malicioso nos nomes dos jogadores ou notas
- Coach insere instruções no campo "bio" ou "comentário de anotação" que alteram o comportamento do LLM
- Aluno tenta injetar via campo de texto livre enviado ao `/coach/chat`

**Mitigações:**

```python
# Sanitização antes de qualquer chamada LLM
def sanitize_llm_input(text: str, max_len: int = 2000) -> str:
    # Remove sequências típicas de prompt injection
    PATTERNS = [
        r"ignore (all |previous |above )?instructions?",
        r"(you are now|act as|pretend (you are|to be))",
        r"(system|assistant|user)\s*:",   # role spoofing
        r"<\|.*?\|>",                     # token markers
        r"\[INST\]|\[/INST\]",            # Llama-style
    ]
    for p in PATTERNS:
        text = re.sub(p, "[REMOVIDO]", text, flags=re.IGNORECASE)
    return text[:max_len]
```

- Aplicar em: `llm_explainer.py` (decisões), `coach_chat_reply` (chat), anotações antes de salvar
- Log de tentativas detectadas para análise posterior

---

### Camada 2 — Moderação de Conteúdo em Texto Livre

**Campos expostos publicamente que precisam de moderação:**
- `coach_profiles.bio` — exibido no diretório público
- `coach_profiles.biggest_results[].name` — exibido no perfil público
- `coach_reviews.review_text` — exibido no perfil público
- `coach_hand_annotations.comment` — exibido ao aluno

**Abordagem v1 — Blocklist local (rápida, sem custo):**
```python
BLOCKED_TERMS = [...]  # lista de palavras proibidas em pt/en
def moderate_text(text: str) -> tuple[bool, str]:
    """Retorna (is_clean, cleaned_text_or_reason)."""
    lower = text.lower()
    for term in BLOCKED_TERMS:
        if term in lower:
            return False, f"Conteúdo não permitido detectado"
    return True, text
```

**Abordagem v2 — API de moderação (mais robusta):**
- OpenAI Moderation API (gratuita): `POST https://api.openai.com/v1/moderations`
- Ou Claude Haiku com prompt de classificação (já temos a chave)
- Retorna categorias: `hate`, `harassment`, `sexual`, `violence`, `self-harm`
- Chamada assíncrona — não bloqueia o save, mas marca o registro como `pending_review`

**Fluxo sugerido:**
1. Usuário salva texto → backend chama moderador
2. Se limpo → salva normalmente
3. Se suspeito → salva com `moderation_status = 'flagged'` e não exibe publicamente até revisão manual

---

### Campos de banco necessários

```sql
ALTER TABLE coach_profiles     ADD COLUMN moderation_status TEXT DEFAULT 'approved';
ALTER TABLE coach_reviews       ADD COLUMN moderation_status TEXT DEFAULT 'approved';
ALTER TABLE coach_hand_annotations ADD COLUMN moderation_status TEXT DEFAULT 'approved';
```

---

### Esforço estimado
- Camada 1 (anti-injection): ~2h (regex + aplicar nos pontos de entrada LLM)
- Camada 2 v1 (blocklist local): ~2h (lista + middleware + campo no banco)
- Camada 2 v2 (API externa): ~4h adicionais
- Painel de revisão manual (admin): ~4h
- **Total sprint básico (camadas 1 + 2v1): ~1 sprint pequena**

---

## [BACK-009] — Sistema de Nível e Gamificação do Aluno

**Valor:** Aluno e coach enxergam imediatamente em qual nível de jogo o aluno está, qual o badge atual, e o que precisa melhorar para avançar. Cria senso de progressão, aumenta retenção e dá ao coach um vocabulário comum com o aluno ("você está no nível Shark, falta 8% de standard para chegar a Reg").

---

### Níveis propostos (baseados em `standard_pct` médio dos últimos 30 torneios)

| Badge | Nome | Standard % | Perfil |
|---|---|---|---|
| 🐟 | **Fish** | < 40% | Comete erros claros com frequência; jogo não estruturado |
| 🎯 | **Calling Station** | 40–54% | Melhorou defesa, mas ainda passivo/sem agressão correta |
| ♠ | **Rec** | 55–64% | Joga recreacionalmente; leaks pontuais e recorrentes |
| 📈 | **Grinder** | 65–74% | Jogo consistente; volume sem exploitar bem os spots |
| 🦈 | **Shark** | 75–84% | Leaks apenas situacionais; jogo forte na maioria dos spots |
| 🏆 | **Reg** | 85–92% | Quase sem leaks identificáveis; domina range construction |
| 👑 | **Elite** | > 92% | Nível alto-stakes/profissional; decisões quase ótimas |

> Nomes e thresholds são configuráveis — podem ser ajustados sem quebrar o modelo.

---

### O que exibir por nível

**Card de nível (visível para aluno e para coach no perfil do aluno):**
- Badge + nome do nível atual com cor temática
- Barra de progresso dentro do nível (ex: "Shark — 78% / 85% para Reg")
- Próximo milestone: "Reduza erros em flop/BTN para avançar"
- Histórico de mudanças de nível com data ("Subiu para Shark em 12/04/2026")

**Para o coach (aba Progresso / Overview do aluno):**
- Nível atual + data da última mudança
- Previsão baseada na tendência das últimas 4 semanas: "no ritmo atual, chega a Reg em ~3 semanas"
- Alerta quando aluno regrediu de nível

**Para o aluno (dashboard próprio):**
- Card de nível em destaque no topo
- Lista dos 3 principais leaks que impedem o próximo nível
- Botão "Ver plano de estudos para avançar" → linka para o plano de estudos focado nos leaks do nível atual

---

### Cálculo

```
standard_pct_media = AVG(standard_pct) dos últimos N torneios com avg_score NOT NULL
N = max(5, torneios dos últimos 30 dias)  -- mínimo 5 torneios para ter badge estável
```

- Badge calculado on-the-fly (sem coluna extra necessária — derivado do histórico existente)
- "Mudança de nível" detectada quando a média cruza um threshold por 2 torneios consecutivos (evita oscilação)

---

### Modelo de dados (opcional — apenas para histórico de nível)

```sql
CREATE TABLE student_level_history (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    level       TEXT    NOT NULL,   -- 'fish' | 'calling_station' | 'rec' | 'grinder' | 'shark' | 'reg' | 'elite'
    standard_pct REAL   NOT NULL,  -- valor no momento da transição
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

- Populado apenas quando o nível muda (evento, não snapshot periódico)
- Permite timeline "histórico de nível" sem custo de storage

---

### Endpoints necessários

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/metrics/level` | Nível atual do aluno autenticado + progresso + próximos passos |
| `GET` | `/coach/student/:id/level` | Mesmo dado, acessado pelo coach |

---

### Esforço estimado
- Backend: ~3h (cálculo de nível + endpoint + detecção de mudança)
- Frontend aluno: ~3h (card de nível no dashboard + barra de progresso + lista de leaks para avançar)
- Frontend coach: ~2h (nível no perfil do aluno + alerta de regressão)
- **Total: ~1 sprint pequena**

---

## [BACK-008] — Visualizador de Ranges no Replayer

**Valor:** Durante sessão de treinamento, coach e aluno podem consultar ranges de referência (open, call, 3bet, fold-to-3bet, etc.) diretamente no replayer — sem precisar alternar para outra ferramenta como GTO Wizard ou planilha.

### Funcionalidades

**Painel de ranges** (sidebar ou modal no replayer):
- Abre ao clicar no botão "Range" em qualquer step de ação do herói
- Pré-seleciona automaticamente o tipo de range sugerido pelo contexto:
  - Preflop sem raise anterior → **Open**
  - Preflop com raise anterior + posição IP → **Call / 3bet**
  - Facing 3bet → **4bet / fold-to-3bet**
  - Postflop → **C-bet / Check-back / Fold**
- Seletor manual de tipo: Open · RFI · Call · 3bet · 4bet · Squeeze · Fold-to-3bet

**Visualização da range matrix:**
- Grid 13×13 (AKs na diagonal, AKo fora da diagonal — padrão Texas Hold'em)
- Cores por ação: raise (verde), call (azul), fold (fundo escuro/vazio)
- Percentual da range exibido (ex: "22% das mãos")
- Destaque visual na célula correspondente às cartas do herói naquela mão

**Fonte dos dados:**
- Sprint inicial: ranges estáticas em JSON embutidas no frontend (GTO approx. por posição)
  - Cobertura mínima: 6max MTT — BU, CO, HJ, MP, UTG (open + call + 3bet)
- Sprint futura: endpoint próprio ou integração com API externa (GTO Wizard, Poker Solver, etc.)

**Integração com coach:**
- Coach pode salvar override de range por posição/spot no plano de estudo do aluno (extensão de BACK-001 / estudo customizado)
- Badge "Range do coach" quando há customização ativa

### Contexto técnico
- Grid pode ser componente React puro — sem dependência de biblioteca
- JSON de ranges: ~50KB para cobrir posições essenciais de 6max MTT
- Detectar contexto a partir de `step.street`, `step.action`, posição do herói (já presentes no replay step)

### Esforço estimado
- Frontend (grid + ranges estáticas): ~6h
- Integração contextual com replayer: ~2h
- Sprint futura (ranges dinâmicas / API externa): ~8h adicionais
- **Total Sprint inicial: ~1 sprint média**

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
