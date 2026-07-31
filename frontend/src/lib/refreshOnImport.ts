import type { QueryClient } from "@tanstack/react-query";

/**
 * refreshOnImport — o que precisa ser recarregado quando um torneio entra. FONTE ÚNICA.
 *
 * ── O bug que originou (auditoria de 2026-07-30) ──────────────────────────────────────────────
 *
 * O usuário reportou: *"por mais que eu esteja jogando torneios, nem todos os indicadores estão
 * sendo modificados"*. A varredura das 174 queries do app achou **quatro chaves** que mostram
 * número derivado de torneio e não escutavam o import:
 *
 *     bankroll-evolution     → o gráfico de banca (o mais visível de todos)
 *     progression-status     → o leak em foco e o estado dele
 *     proximo-passo          → a faixa "seu próximo passo"
 *     training-daily-status  → o status diário no HUD
 *
 * Cada uma vivia num componente que busca por conta própria, com `staleTime` de 30 a 60 segundos.
 * Como o React Query não refaz sozinho sem foco ou remontagem, quem subia um torneio e continuava
 * na tela via esses quatro parados. As queries do `Index` estavam certas porque carregam uma chave
 * de refresh; as dos componentes-filhos não tinham nada.
 *
 * ── Por que uma LISTA e não `invalidateQueries()` sem filtro ──────────────────────────────────
 *
 * Invalidar tudo recarregaria também tickets de suporte, mensagens do coach e catálogo de coaches,
 * que nada têm a ver com torneio. Medido: um ciclo completo do dashboard custa ~17s de backend, e
 * três endpoints sozinhos levam de 3 a 5s. Vale declarar o que entra.
 *
 * ── O ratchet ─────────────────────────────────────────────────────────────────────────────────
 *
 * Toda chave do app tem que estar numa das duas listas. `refreshOnImport.test.ts` varre o código e
 * falha quando aparece uma chave nova que não foi classificada — o autor é obrigado a decidir se
 * ela deriva de torneio. Sem esse guarda, o próximo card criado repete o bug em silêncio, que é
 * exatamente o que aconteceu com os seis componentes acima.
 */

/** Deriva de torneio: tem que recarregar quando um import termina. */
export const CHAVES_DE_TORNEIO = [
  "bankroll-evolution",
  "progression-status",
  "progression-missions",
  "proximo-passo",
  "training-daily-status",
  "training-overview",
  "training-proof",
  "player-level",
  "evolution",
  "evolution-history",
  "evolution-snapshot",
  "ev-summary",
  "gto-alignment",
  "gto-position",
  "gto-quality",
  "leak-finder",
  "results-vs-gto",
  "pending-gto",
  "leaktrainer-options",
  "coach-replay",
] as const;

/**
 * NÃO deriva de torneio. Declarado, não omitido: uma chave fora das duas listas é um esquecimento,
 * e o teste não sabe distinguir esquecimento de decisão a menos que a decisão esteja escrita.
 */
export const CHAVES_NAO_DERIVADAS = [
  // conta, perfil, mensagens, suporte
  "me", "player-profile", "my-demographics", "player-messages-unread", "player-coach-messages",
  "my-support-tickets", "my-support-unread", "admin-support-count",
  // coaches (catálogo público e vínculo)
  "public-coaches-exist", "coaches-directory", "coaches-top", "coaches-for-spot", "public-coach",
  "my-review", "coach-contact-thread", "coach-invites", "coach-invite-key", "coach-students",
  "coach-profile", "coach-reviews", "coach-trial-status",
  // treino não ligado a torneio
  "daily-challenge", "training-league",
  // painéis de coach (leem o aluno, não o import do próprio usuário)
  "coach-inbox", "coach-link-requests", "coach-recent-activity", "coach-students-leaderboard",
  "coach-impact", "coach-effectiveness", "coach-cohort-analytics", "coach-common-leaks",
  "coach-all-worst", "coach-annotations", "coach-baseline", "coach-messages",
  "coach-progress-report", "coach-student-breakdown", "coach-student-history",
  "coach-student-level", "coach-student-stats", "coach-student-study", "coach-student-tournament",
  "coach-student-worst", "coach-study-overrides", "coach-templates", "coach-activity-feed",
  "coach-finance-history", "coach-finance-students", "coach-finance-summary",
  // admin
  "admin-users", "admin-stats", "admin-logs", "admin-payments", "admin-expenses",
  "admin-tournaments", "admin-demographics", "admin-feature-usage", "admin-msg-users",
  "admin-coach-students", "admin-coach-applications", "admin-challenge-pool",
  "admin-gto-hand-queue", "admin-gto-worker-status", "admin-support-tickets",
  "admin-finance-coaches", "admin-finance-cockpit", "admin-finance-calendar",
  "admin-finance-dunning", "admin-finance-timeseries",
] as const;

/**
 * Evento disparado UMA vez quando a fila de upload esvazia, e não por arquivo.
 *
 * O `leaklab:tournament-imported` continua existindo e é por arquivo (a lista de torneios quer
 * saber de cada um). Este aqui é o de LOTE, e a diferença é medida: um ciclo completo do dashboard
 * custa ~17s de backend, e no dia 28/07 houve 14 uploads — por arquivo seriam 14 ciclos.
 */
export const EVENTO_LOTE = "leaklab:import-batch-done";

/** Recarrega tudo que depende de torneio. Chamado uma vez por lote. */
export function invalidarAposImport(qc: QueryClient) {
  for (const chave of CHAVES_DE_TORNEIO) {
    // prefixo: `["ev-summary", refreshKey]` casa com `["ev-summary"]`, então as chaves do Index
    // que carregam parâmetros também são atingidas.
    qc.invalidateQueries({ queryKey: [chave] });
  }
}
