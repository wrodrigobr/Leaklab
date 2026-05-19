import type { StudyPlan, StudyResource, Exercise, LeakRef, LeakSeverity } from "./types";
import type { StudyPlanResponse, StudyCard } from "@/lib/api";

// ── Static exercise bank (deterministic, no AI required) ─────────────────────

const EXERCISE_BANK: Omit<Exercise, "leakId">[] = [
  {
    id: "ex_pre_01",
    prompt: "BTN abre 2.5x, você está no SB com K♠9♠ (35bb). Melhor ação?",
    context: "Villain tem RFI BTN de 45%. Stacks: SB 35bb, BTN 40bb.",
    choices: [
      { id: "a", label: "Fold — K9s OOP é marginal" },
      { id: "b", label: "Call — set-mine e posição ruim, mas playable" },
      { id: "c", label: "3-bet para 9bb — semi-bluff com bom bloqueador" },
      { id: "d", label: "All-in — máxima pressão com 35bb" },
    ],
    correctChoiceId: "c",
    explanation:
      "Contra RFI 45% do BTN, K9s está acima do threshold de 3-bet no SB. 3-bet gera fold equity contra a metade inferior do range dele e joga bem com SPR baixo. Call é inferior: você fica OOP no flop sem iniciativa.",
  },
  {
    id: "ex_pre_02",
    prompt: "EP2 abre 2.5x (25bb stack). Você está no BTN com A♥J♦ (40bb). Ação correta?",
    context: "Mesa de 9 jogadores, early stage MTT. EP2 tem VPIP/PFR 18/14.",
    choices: [
      { id: "a", label: "Fold — AJo é dominado por range de EP" },
      { id: "b", label: "Call — jogue em posição com SPR confortável" },
      { id: "c", label: "3-bet 7.5bb — extrai valor e fecha ação" },
      { id: "d", label: "3-bet all-in — 40bb é short o suficiente" },
    ],
    correctChoiceId: "b",
    explanation:
      "Call é preferível. Range de 3-bet de EP inclui AQ+/KK+/JJ+, onde AJo frequentemente está dominado. Em posição com 40bb e SPR ~4, você tem manobra postflop. 3-bet aqui arrisca muitos chips contra range que domina.",
  },
  {
    id: "ex_post_01",
    prompt: "Pot é 120bb. Villain aposta 60bb no river. Você tem topo par mão fraca (A♣4♦ em board A-7-2-K-Q). Qual equity mínima justifica call?",
    choices: [
      { id: "a", label: "20% — aposta pequena relativa ao pot total" },
      { id: "b", label: "25% — call/(pot+call) = 60/240" },
      { id: "c", label: "33% — precisa ganhar 1 em 3" },
      { id: "d", label: "50% — flip neutro" },
    ],
    correctChoiceId: "b",
    explanation:
      "Pot odds = call ÷ (pot + call) = 60 ÷ (120 + 60 + 60) = 60 ÷ 240 = 25%. Se você acredita ganhar >25% das vezes, o call tem EV positivo. Com TPTK em board estático, a decisão depende do range de valor do villain.",
  },
  {
    id: "ex_post_02",
    prompt: "Você C-bet 33% no flop K♠7♦2♣ (rainbow, single raised pot). Villain checa-levanta 3x. Você tem A♣K♥. Ação?",
    context: "SPR ~3 no flop. Villain é regular 25/20.",
    choices: [
      { id: "a", label: "Re-raise all-in — TPTK é strong" },
      { id: "b", label: "Call — avalie turn antes de investir mais" },
      { id: "c", label: "Fold — check-raise sempre representa set+" },
      { id: "d", label: "Call apenas se tiver backdoor" },
    ],
    correctChoiceId: "b",
    explanation:
      "Call é correto. Check-raise range de regular em board seco inclui sets, dois pares e também bluffs (gutshots, A-high sem equity). Com TPTK e SPR ~3, você tem equity forte. Avalie turn: se blank, pode all-in ou call shove. Fold seria excessivamente tight.",
  },
  {
    id: "ex_icm_01",
    prompt: "Bubble do MTT (top 9 pagam, 10 restantes). Você tem 20bb no BTN. Short stack de 5bb no SB dá all-in. Você tem 8♠8♦. Ação?",
    choices: [
      { id: "a", label: "Fold — ICM é alto no bubble, evite riscos" },
      { id: "b", label: "Call — 88 tem 65%+ de equity, risco mínimo de stack" },
      { id: "c", label: "Depende do tamanho dos demais stacks" },
      { id: "d", label: "Apenas call se tiver ≥70% de equity" },
    ],
    correctChoiceId: "b",
    explanation:
      "Call é correto. Você arrisca apenas 5bb de um stack de 20bb (25%). Com 88 vs range de push de 5bb (~top 60%), você tem ~65% de equity. A penalidade ICM de chamar 5bb é mínima. Fold aqui seria over-tight e -EV.",
  },
  {
    id: "ex_icm_02",
    prompt: "Você é big stack (80bb) no bubble. Stack de 15bb no SB faz all-in. BB tem 18bb e chama. Você no CO com K♦Q♣. Ação?",
    choices: [
      { id: "a", label: "Call — KQo tem 40%+ de equity 3-way" },
      { id: "b", label: "Fold — pot 3-way preflop no bubble é ICM-incorreto" },
      { id: "c", label: "Re-raise para isolar o all-in" },
      { id: "d", label: "Call apenas se KQo tiver 50%+ de equity" },
    ],
    correctChoiceId: "b",
    explanation:
      "Fold correto. Como big stack no bubble, seu valor ICM vem de sobreviver e pressionar short stacks, não de arriscar 15bb em pots 3-way onde você pode estar atrás de AK/AA/KK. ICM penaliza calls amplamente mesmo com equity razoável.",
  },
  {
    id: "ex_pos_01",
    prompt: "Você abriu UTG em mesa de 9, só o BTN chamou. Flop 8♠5♥2♦. Quem tem range advantage?",
    choices: [
      { id: "a", label: "BTN — vê flop mais barato e tem mãos especulativas" },
      { id: "b", label: "UTG — range forte (pares, broadways) conecta melhor" },
      { id: "c", label: "Neutro — board baixo não favorece nenhum range" },
      { id: "d", label: "Depende do stack depth" },
    ],
    correctChoiceId: "b",
    explanation:
      "UTG tem range advantage. Seu range de abertura UTG inclui overpairs (AA-99) e mãos fortes que dominam 852. BTN, ao defender IP, carrega muitos conectores/suited que perdem neste board. UTG tem mais sets, overpairs e representação do board inteiro.",
  },
  {
    id: "ex_pos_02",
    prompt: "Qual board favorece C-bet de alta frequência (>70%) para o preflop aggressor?",
    choices: [
      { id: "a", label: "9♠8♠7♥ — board conectado, draws múltiplos" },
      { id: "b", label: "A♣Q♦J♠ — broadway, todos conectam" },
      { id: "c", label: "K♥7♦2♣ — seco, rainbow, favorece range de EP/MP" },
      { id: "d", label: "T♠T♦6♥ — board pareado, range neutro" },
    ],
    correctChoiceId: "c",
    explanation:
      "K72 rainbow é o board ideal para C-bet alta frequência: seco (sem draws de flush), favorece range do abridor (KK/77 no range, K-x alto frequente), e o defensor tem dificuldade de conectar. Boards conectados ou broadway permitem que o defensor chegue com mais equity.",
  },
];

// ── Transform backend response → StudyPlan ────────────────────────────────────

function severityFromIndex(i: number): LeakSeverity {
  if (i === 0)      return "critical";
  if (i <= 2)       return "moderate";
  return "minor";
}

function resourcesFromCard(card: StudyCard): StudyResource[] {
  const out: StudyResource[] = [];
  const KNOWN_URLS: Record<string, string> = {
    "Solver GTO":       "https://gtowizard.com",
    "Run It Once":      "https://www.runitonce.com",
    "PokerCoaching":    "https://www.pokercoaching.com",
    "Upswing Poker":    "https://www.upswingpoker.com",
    "Jonathan Little":  "https://www.pokercoaching.com",
  };

  const maybeUrl = (title: string) => {
    for (const [k, v] of Object.entries(KNOWN_URLS)) {
      if (title.toLowerCase().includes(k.toLowerCase())) return v;
    }
    return undefined;
  };

  card.recursos?.livros?.forEach((t) =>
    out.push({ type: "book", title: t, url: maybeUrl(t) })
  );
  card.recursos?.videos?.forEach((t) =>
    out.push({ type: "video", title: t, url: maybeUrl(t) })
  );
  if (card.recursos?.curso)
    out.push({ type: "tool", title: card.recursos.curso });

  return out;
}

function generateWeeks(cards: StudyCard[]): import("./types").StudyWeek[] {
  const weekThemes = [
    "Fundamentos — Leaks Críticos",
    "Expansão — Leaks Secundários",
    "Integração — Aprofundamento",
    "Consolidação — Revisão e Medição",
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
        topic: primary?.exercicio ?? "Hand history review — filtre mãos perdidas neste spot",
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
        topic: secondary?.exercicio ?? "Quiz tático — resolva 20 questões cronometrado",
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
    title:     card.titulo,
    severity:  severityFromIndex(i),
    evLoss:    "—",
    rationale: card.diagnostico ?? card.conceitos?.join(", ") ?? "",
  }));

  const resourcesByLeak: Record<string, StudyResource[]> = {};
  cards.forEach((card) => {
    const id = card.prioridade ?? `p${cards.indexOf(card) + 1}`;
    resourcesByLeak[id] = resourcesFromCard(card);
  });

  // Assign exercises to leaks round-robin
  const exercises = EXERCISE_BANK.map((ex, i) => ({
    ...ex,
    leakId: leaks[i % leaks.length]?.id ?? "p1",
  }));

  return {
    generatedAt: new Date().toISOString(),
    diagnosis: { summary: backend.resumo ?? "", leaks },
    weeks: generateWeeks(cards),
    resourcesByLeak,
    exercises,
  };
}
