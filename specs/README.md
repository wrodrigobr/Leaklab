# Specs — contratos do PokerLeakLab

Esta pasta consolida os **contratos e invariantes** do sistema: o que o projeto
faz, como as partes se conectam, e **o que nunca pode quebrar**. O objetivo é
servir de base para alterar o sistema **sem regredir** comportamento.

## Filosofia (leia antes de adicionar)

> **Spec aqui é contrato, não prosa exaustiva.** Documentação detalhada de tudo
> envelhece e vira *mentira documentada* — pior que não ter. Estes documentos são
> **curtos e duráveis**: focam nas regras estáveis e nos invariantes críticos.

**O que de fato previne quebra, em ordem de eficácia:**
1. **Testes** (specs executáveis) — só o teste **falha o build** quando algo quebra.
   Cada invariante crítico aqui é amarrado a um teste em [`backend/tests/test_invariants.py`](../backend/tests/test_invariants.py).
2. **Fonte única de verdade** — lógica duplicada é o vetor nº 1 de regressão
   (ver INV-1: 4 paths recomputavam o roteamento preflop e divergiram).
3. **Invariantes documentados** (este `invariants.md`) — o "porquê" e o teste que guarda.

Regra ao mexer: **mudou comportamento que um invariante cobre → atualize o teste
E o spec juntos**, no mesmo commit. Se um spec diverge do código, o código vence —
conserte o spec ou apague-o.

## Índice

| Doc | Conteúdo |
|---|---|
| [`architecture.md`](architecture.md) | Subsistemas, fluxo de dados, fronteiras |
| [`invariants.md`](invariants.md) | **Os contratos que nunca podem quebrar** + o teste de cada |
| [`preflop-gto.md`](preflop-gto.md) | Roteamento de cenário, reconciliação label↔gto, cobertura, sizing |
| [`gto-capture.md`](gto-capture.md) | Pipeline de captura no GTO Solver (history_spot, depths válidos, deploy) |
| [`decision-pipeline.md`](decision-pipeline.md) | Como uma decisão é avaliada e salva; os paths que devem concordar |
| [`glossary.md`](glossary.md) | Termos (label vs gto_label, cenários, buckets, classificações) |

## Fontes complementares (não duplicar aqui)

- **`CHANGELOG.md`** — histórico e *rationale* de cada mudança.
- **`CLAUDE.md`** — visão geral de arquitetura/comandos.
- **`/docs`** (frontend) — conceitos para o usuário final.
- **Memória do projeto** (`~/.claude/.../memory`) — decisões de produto, backlog, feedbacks.
