# Backlog — PokerLeakLab

Itens planejados, ainda sem sprint definida.

---

## [BACK-001] Anotações do Coach no Replayer

**Valor:** Coach comenta ações específicas de uma mão; comentário aparece no replayer do aluno no mesmo estilo visual dos leaks do sistema. Base de dados estruturada para retreinamento futuro do modelo.

### Fluxo
1. Coach abre o replay de uma mão do aluno (via Mãos Críticas ou Torneios)
2. No replayer, em modo coach, cada ação tem um botão "Comentar"
3. Coach escreve o comentário, define o modo (**Complementar** ou **Substituir** o leak do sistema) e salva
4. Quando o aluno abre o replay da mesma mão, o comentário do coach aparece:
   - **Complementar**: exibe leak do sistema + nota do coach empilhados
   - **Substituir**: oculta o leak do sistema e exibe apenas a nota do coach

### Modelo de dados
```sql
CREATE TABLE coach_hand_annotations (
    id              INTEGER PRIMARY KEY,
    coach_id        INTEGER NOT NULL REFERENCES users(id),
    student_id      INTEGER NOT NULL REFERENCES users(id),
    hand_id         TEXT    NOT NULL,
    decision_id     INTEGER REFERENCES decisions(id),  -- ação específica
    comment         TEXT    NOT NULL,
    mode            TEXT    NOT NULL DEFAULT 'complement',  -- 'complement' | 'replace'
    coach_action    TEXT,   -- o que o coach acha que deveria ser jogado (pode diferir do sistema)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coach_id, student_id, hand_id, decision_id)
);
```

### Endpoints necessários
| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/coach/student/:id/hand-annotations/:hand_id` | Lista anotações do coach para uma mão |
| `POST` | `/coach/student/:id/hand-annotations` | Salva / atualiza anotação |
| `DELETE` | `/coach/student/:id/hand-annotations/:decision_id` | Remove anotação |

### Mudanças no Replayer
- `/replay/:tid/:hid` e `/coach/student/:id/replay/:tid/:hid` passam a retornar `coach_annotations[]` junto à timeline
- Cada `ReplayStep` ganha campo opcional `coach_annotation: { comment, mode, coach_action }`
- UI: botão "Comentar" visível apenas para coach; balão de anotação renderizado no passo correspondente
- Aluno vê o balão do coach (sem o botão de edição)

### Base de conhecimento / retreinamento
- Registros onde `coach_action != decision.best_action` → divergência coach × sistema → ground truth para correção
- Futuramente: pipeline de fine-tuning ou ajuste de prompt no `decision_engine_v11` usando estas divergências como sinal de erro do modelo

### Esforço estimado
- Backend: ~4h (tabela + 3 endpoints + ajuste no replay endpoint)
- Frontend coach: ~3h (botão + modal de anotação no replayer)
- Frontend aluno: ~2h (exibição do balão no replayer)
- **Total: ~1 sprint pequena**

---
