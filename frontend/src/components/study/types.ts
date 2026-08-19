export type LeakSeverity = "critical" | "moderate" | "minor";

export interface LeakRef {
  id: string;
  signature: string;
  /** chave do spot (vem do StudyCard.spot) — casa o deep-link ?spot= e a busca de coach por especialidade */
  spot: string;
  title: string;
  severity: LeakSeverity;
  evLoss: string;
  rationale: string;
  academy?: { id: string; path: string }[];   // aulas da Academia relevantes (leak→aula)
}

export interface StudyResource {
  type: "book" | "video" | "site" | "tool";
  title: string;
  author?: string;
  url?: string;
  note?: string;
}

export interface StudyDay {
  day: number;
  title: string;
  topic: string;
  estimatedMinutes: number;
  objectives: string[];
  leakIds: string[];
}

export interface StudyWeek {
  week: number;
  focus: string;
  days: StudyDay[];
}

export interface StudyPlan {
  generatedAt: string;
  diagnosis: {
    summary: string;
    leaks: LeakRef[];
  };
  weeks: StudyWeek[];
  resourcesByLeak: Record<string, StudyResource[]>;
  observar?: { indicador: string; valor_atual?: string; sample_atual?: number; sample_necessario?: number; por_que_esperar?: string }[];
  naoFocar?: { item: string; motivo: string }[];
}
