export type LeakSeverity = "critical" | "moderate" | "minor";

export interface LeakRef {
  id: string;
  signature: string;
  title: string;
  severity: LeakSeverity;
  evLoss: string;
  rationale: string;
}

export interface StudyResource {
  type: "book" | "video" | "site" | "tool";
  title: string;
  author?: string;
  url?: string;
  note?: string;
}

export interface ExerciseChoice {
  id: string;
  label: string;
}

export interface Exercise {
  id: string;
  leakId: string;
  prompt: string;
  context?: string;
  choices: ExerciseChoice[];
  correctChoiceId: string;
  explanation: string;
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
  exercises: Exercise[];
}
