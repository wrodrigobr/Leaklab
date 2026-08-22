import type { StudyPlan, StudyResource, LeakRef, LeakSeverity } from "./types";
import type { StudyPlanResponse, StudyCard } from "@/lib/api";

/**
 * Tradutor do namespace `study`, injetado por quem chama.
 *
 * `buildStudyPlan` é uma função pura, fora da árvore do React, então não pode chamar
 * `useTranslation`. Receber o `t` mantém a função testável e resolve o motivo pelo qual esta
 * copy nasceu em português cravado: não havia por onde traduzir sem virar componente.
 */
export type Traduz = (chave: string, opcoes?: Record<string, unknown>) => string;

// ── Transform backend response → StudyPlan ────────────────────────────────────

function severityFromIndex(i: number): LeakSeverity {
  if (i === 0)      return "critical";
  if (i <= 2)       return "moderate";
  return "minor";
}

function resourcesFromCard(card: StudyCard): StudyResource[] {
  // Material externo = só o TIPO/conceito a estudar (saneado no backend, sem títulos nem
  // marcas/concorrentes). NÃO hiperlinkamos pra fora (antes linkava Run It Once/Upswing/etc.):
  // o caminho principal de estudo é o treino DA plataforma (CTA em destaque na StudyPlan).
  const out: StudyResource[] = [];
  card.recursos?.livros?.forEach((t) => out.push({ type: "book", title: t }));
  card.recursos?.videos?.forEach((t) => out.push({ type: "video", title: t }));
  if (card.recursos?.curso) out.push({ type: "tool", title: card.recursos.curso });
  return out;
}

function generateWeeks(cards: StudyCard[], t: Traduz): import("./types").StudyWeek[] {
  const weekThemes = [
    t("planBuilder.week.fundamentos"),
    t("planBuilder.week.expansao"),
    t("planBuilder.week.integracao"),
    t("planBuilder.week.consolidacao"),
  ];

  return [0, 1, 2, 3].map((w) => {
    const primary   = cards[w * 2]     ?? cards[0];
    const secondary = cards[w * 2 + 1] ?? cards[1];

    const primaryConceitos = primary?.conceitos?.join(" · ") ?? t("planBuilder.fallback.estudoDeRange");

    const days: import("./types").StudyDay[] = [
      {
        day: 1,
        title: primary?.titulo ?? t("planBuilder.fallback.teoria"),
        topic: primaryConceitos,
        estimatedMinutes: 50,
        objectives: [
          primary?.diagnostico ?? t("planBuilder.fallback.entenderRaiz"),
          t("planBuilder.objetivo.marcarSpots"),
        ],
        leakIds: [primary?.prioridade ?? `p${w * 2 + 1}`],
      },
      {
        day: 2,
        title: t("planBuilder.dia.drill"),
        topic: primary?.exercicio ?? t("planBuilder.fallback.handHistoryReview"),
        estimatedMinutes: 60,
        objectives: [
          t("planBuilder.objetivo.resolverMaos", { n: 20 }),
          primary?.metrica ?? t("planBuilder.fallback.reduzirErro", { pct: 20 }),
        ],
        leakIds: [primary?.prioridade ?? `p${w * 2 + 1}`],
      },
      {
        day: 3,
        title: secondary?.titulo ?? t("planBuilder.fallback.leakSecundario"),
        topic: secondary?.diagnostico ?? t("planBuilder.fallback.posicaoSpr"),
        estimatedMinutes: 45,
        objectives: [
          secondary?.conceitos?.[0] ?? t("planBuilder.fallback.rangeAdvantage"),
          secondary?.conceitos?.[1] ?? t("planBuilder.fallback.potOddsMultiway"),
          ...(secondary?.conceitos?.slice(2) ?? []),
        ],
        leakIds: [secondary?.prioridade ?? `p${w * 2 + 2}`],
      },
      {
        day: 4,
        title: t("planBuilder.dia.cronometrado"),
        topic: secondary?.exercicio ?? t("planBuilder.fallback.quizTatico", { n: 20 }),
        estimatedMinutes: 30,
        objectives: [
          t("planBuilder.objetivo.acertoQuiz", { pct: 80 }),
          secondary?.metrica ?? t("planBuilder.fallback.reduzirErro", { pct: 10 }),
        ],
        leakIds: [secondary?.prioridade ?? `p${w * 2 + 2}`],
      },
      {
        day: 5,
        title: w < 3 ? t("planBuilder.dia.revisaoSemanal") : t("planBuilder.dia.testeFinal"),
        topic: w < 3
          ? t("planBuilder.topico.revisarReplays")
          : t("planBuilder.topico.reimportar"),
        estimatedMinutes: 25,
        objectives: [
          w < 3
            ? t("planBuilder.objetivo.documentarSpots", { n: 3 })
            : t("planBuilder.objetivo.evLossAbaixoMeta"),
        ],
        leakIds: cards.map((c) => c.prioridade).filter(Boolean),
      },
    ];

    return { week: w + 1, focus: weekThemes[w], days };
  });
}

export function buildStudyPlan(backend: StudyPlanResponse, t: Traduz): StudyPlan {
  const cards = backend.cards ?? [];

  const leaks: LeakRef[] = cards.map((card, i) => ({
    id:        card.prioridade ?? `p${i + 1}`,
    signature: (card.prioridade ?? `P${i + 1}`).toUpperCase(),
    spot:      card.spot ?? "",
    title:     card.titulo,
    severity:  severityFromIndex(i),
    evLoss:    card.ev_ponderado || "—",
    rationale: card.diagnostico ?? card.conceitos?.join(", ") ?? "",
    academy:   card.academy_modules ?? [],
  }));

  const resourcesByLeak: Record<string, StudyResource[]> = {};
  cards.forEach((card) => {
    const id = card.prioridade ?? `p${cards.indexOf(card) + 1}`;
    resourcesByLeak[id] = resourcesFromCard(card);
  });

  return {
    generatedAt: new Date().toISOString(),
    diagnosis: { summary: backend.resumo ?? "", leaks },
    weeks: generateWeeks(cards, t),
    resourcesByLeak,
    observar: backend.observar_mais_dados ?? [],
    naoFocar: backend.nao_focar_agora ?? [],
  };
}
