import type { StudyPlan, StudyResource, LeakRef, LeakSeverity } from "./types";
import type { StudyPlanResponse, StudyCard } from "@/lib/api";


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

function generateWeeks(cards: StudyCard[]): import("./types").StudyWeek[] {
  const weekThemes = [
    "Fundamentos: Leaks Críticos",
    "Expansão: Leaks Secundários",
    "Integração: Aprofundamento",
    "Consolidação: Revisão e Medição",
  ];

  return [0, 1, 2, 3].map((w) => {
    const primary   = cards[w * 2]     ?? cards[0];
    const secondary = cards[w * 2 + 1] ?? cards[1];

    const primaryConceitos = primary?.conceitos?.join(" · ") ?? "Estudo de range";

    const days: import("./types").StudyDay[] = [
      {
        day: 1,
        title: primary?.titulo ?? "Teoria",
        topic: primaryConceitos,
        estimatedMinutes: 50,
        objectives: [
          primary?.diagnostico ?? "Entender a raiz do leak",
          "Identificar os spots de erro em sessão passada e marcá-los para revisão",
        ],
        leakIds: [primary?.prioridade ?? `p${w * 2 + 1}`],
      },
      {
        day: 2,
        title: "Drill prático",
        topic: primary?.exercicio ?? "Hand history review: filtre mãos perdidas neste spot",
        estimatedMinutes: 60,
        objectives: [
          "Resolver ≥20 mãos no solver focando neste padrão",
          primary?.metrica ?? "Reduzir frequência de erro neste spot em ≥20%",
        ],
        leakIds: [primary?.prioridade ?? `p${w * 2 + 1}`],
      },
      {
        day: 3,
        title: secondary?.titulo ?? "Leak secundário",
        topic: secondary?.diagnostico ?? "Análise de posição e SPR",
        estimatedMinutes: 45,
        objectives: [
          secondary?.conceitos?.[0] ?? "Conceitos de range advantage",
          secondary?.conceitos?.[1] ?? "Pot odds e implied odds em pots multi-way",
          ...(secondary?.conceitos?.slice(2) ?? []),
        ],
        leakIds: [secondary?.prioridade ?? `p${w * 2 + 2}`],
      },
      {
        day: 4,
        title: "Exercício cronometrado",
        topic: secondary?.exercicio ?? "Quiz tático: resolva 20 questões cronometrado",
        estimatedMinutes: 30,
        objectives: [
          "Acerto ≥80% no quiz da plataforma",
          secondary?.metrica ?? "Reduzir frequência de erro neste spot em ≥10%",
        ],
        leakIds: [secondary?.prioridade ?? `p${w * 2 + 2}`],
      },
      {
        day: 5,
        title: w < 3 ? "Revisão semanal + métricas" : "Teste final + próximos 90 dias",
        topic: w < 3
          ? "Re-assistir replays marcados + medir delta dos leaks"
          : "Re-importar histórico e comparar score antes/depois",
        estimatedMinutes: 25,
        objectives: [
          w < 3
            ? "Documentar os 3 principais spots ainda problemáticos"
            : "EV loss total abaixo da meta do plano",
        ],
        leakIds: cards.map((c) => c.prioridade).filter(Boolean),
      },
    ];

    return { week: w + 1, focus: weekThemes[w], days };
  });
}

export function buildStudyPlan(backend: StudyPlanResponse): StudyPlan {
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
    weeks: generateWeeks(cards),
    resourcesByLeak,
    observar: backend.observar_mais_dados ?? [],
    naoFocar: backend.nao_focar_agora ?? [],
  };
}
