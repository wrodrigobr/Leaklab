import { useMemo, useState } from "react";
import {
  Award,
  BrainCircuit,
  CalendarDays,
  CheckCheck,
  Flame,
  GraduationCap,
  Library,
  Loader2,
  Sparkles,
  Target,
  Timer,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { ExerciseRunner } from "@/components/study/ExerciseRunner";
import { ResourceList } from "@/components/study/ResourceList";
import { buildStudyPlan } from "@/components/study/planBuilder";
import type { StudyPlan } from "@/components/study/types";
import { cn } from "@/lib/utils";
import { study } from "@/lib/api";
import { toast } from "sonner";

// ── localStorage persistence ──────────────────────────────────────────────────

const STORAGE_KEY = "leaklabs:study-progress";

interface Progress {
  exercisesCorrect: number;
  exercisesTotal:   number;
  daysCompleted:    string[];
  streak:           number;
  lastActivity:     string;
}

const DEFAULT_PROGRESS: Progress = {
  exercisesCorrect: 0,
  exercisesTotal:   0,
  daysCompleted:    [],
  streak:           1,
  lastActivity:     "",
};

function loadProgress(): Progress {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_PROGRESS, ...JSON.parse(raw) };
  } catch { /* noop */ }
  return DEFAULT_PROGRESS;
}

function updateStreak(p: Progress): Progress {
  const today     = new Date().toISOString().slice(0, 10);
  if (p.lastActivity === today) return p;
  const yesterday = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
  return { ...p, streak: p.lastActivity === yesterday ? p.streak + 1 : 1, lastActivity: today };
}

// ── KPI tile ─────────────────────────────────────────────────────────────────

function KpiTile({
  icon: Icon, label, value, hint, progress,
}: { icon: typeof Award; label: string; value: string; hint?: string; progress?: number }) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {label}
        </span>
        <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="size-3.5" aria-hidden />
        </span>
      </div>
      <p className="text-xl font-semibold tabular-nums text-foreground">{value}</p>
      {hint && <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{hint}</p>}
      {typeof progress === "number" && (
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-secondary">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${Math.min(100, Math.max(0, progress * 100)).toFixed(1)}%` }}
          />
        </div>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

type LoadState = "idle" | "loading" | "error";

const StudyPlanPage = () => {
  const [plan, setPlan]           = useState<StudyPlan | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [errorMsg, setErrorMsg]   = useState("");
  const [generating, setGenerating] = useState(false);
  const [activeLeakId, setActiveLeakId] = useState<string>("");
  const [progress, setProgress]   = useState<Progress>(loadProgress);

  const persist = (next: Progress) => {
    setProgress(next);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* noop */ }
  };

  const fetchPlan = async (force = false) => {
    setLoadState("loading");
    setErrorMsg("");
    try {
      const data = await study.plan(90);
      if (data.error && !data.cards?.length) {
        setErrorMsg(data.error);
        setLoadState("error");
        return;
      }
      const built = buildStudyPlan(data);
      setPlan(built);
      if (!activeLeakId && built.diagnosis.leaks[0]) {
        setActiveLeakId(built.diagnosis.leaks[0].id);
      }
      setLoadState("idle");
      if (force) toast.success("Plano regenerado com IA.");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao gerar plano";
      setErrorMsg(msg);
      setLoadState("error");
    }
  };

  // Fetch on mount
  useMemo(() => { fetchPlan(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = async () => {
    setGenerating(true);
    await fetchPlan(true);
    setGenerating(false);
  };

  const toggleDay = (key: string) => {
    const has = progress.daysCompleted.includes(key);
    persist(updateStreak({
      ...progress,
      daysCompleted: has
        ? progress.daysCompleted.filter((d) => d !== key)
        : [...progress.daysCompleted, key],
    }));
  };

  const onExerciseProgress = (correct: number, total: number) => {
    persist(updateStreak({ ...progress, exercisesCorrect: correct, exercisesTotal: total }));
  };

  const totalDays     = useMemo(() => plan?.weeks.reduce((a, w) => a + w.days.length, 0) ?? 0, [plan]);
  const xp            = progress.exercisesCorrect * 50 + progress.daysCompleted.length * 100;
  const level         = Math.max(1, Math.floor(xp / 500) + 1);
  const xpInLevel     = xp % 500;
  const completedRatio = totalDays ? progress.daysCompleted.length / totalDays : 0;
  const activeLeak    = plan?.diagnosis.leaks.find((l) => l.id === activeLeakId) ?? plan?.diagnosis.leaks[0];

  const SEVERITY_COLOR: Record<string, string> = {
    critical: "text-destructive",
    moderate: "text-warning",
    minor:    "text-primary",
  };

  return (
    <HudLayout
      eyebrow="Plano de Estudos · Adaptive"
      title="Seu roteiro tático personalizado"
      description="Diagnóstico de leaks, roteiro semanal, recursos curados e exercícios com correção automática."
    >
      {/* Toolbar */}
      <section className="flex flex-col gap-4 rounded-xl border border-border bg-hud-surface p-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex size-10 items-center justify-center rounded-md bg-primary/15 text-primary">
            <BrainCircuit className="size-5" aria-hidden />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {plan ? "Plano gerado a partir dos seus leaks reais" : "Carregando plano de estudos…"}
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
              {plan?.diagnosis.summary ?? "Aguarde enquanto o Coach IA analisa seu histórico."}
            </p>
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating || loadState === "loading"}
          className="inline-flex shrink-0 items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow disabled:opacity-60 transition-colors"
        >
          {generating || loadState === "loading"
            ? <Loader2 className="size-3.5 animate-spin" aria-hidden />
            : <Sparkles className="size-3.5" aria-hidden />}
          {generating || loadState === "loading" ? "Gerando…" : "Gerar com IA"}
        </button>
      </section>

      {/* Loading state */}
      {loadState === "loading" && !plan && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
          <Loader2 className="size-6 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">Coach IA analisando seus leaks…</span>
          <p className="text-xs text-center max-w-xs">Pode levar alguns segundos na primeira vez.</p>
        </div>
      )}

      {/* Error state */}
      {loadState === "error" && (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <GraduationCap className="size-6 text-muted-foreground" />
          <p className="text-sm text-destructive text-center max-w-sm">{errorMsg}</p>
          <p className="text-xs text-muted-foreground text-center max-w-xs">
            Importe pelo menos um torneio para gerar um plano personalizado.
          </p>
          <button
            onClick={() => fetchPlan()}
            className="mt-2 font-mono text-[10px] uppercase tracking-wider text-primary hover:underline"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Loaded */}
      {plan && (
        <>
          {/* KPIs gamificação */}
          <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KpiTile
              icon={Award}
              label="Nível"
              value={`Lv ${level}`}
              hint={`${xpInLevel}/500 XP`}
              progress={xpInLevel / 500}
            />
            <KpiTile
              icon={Flame}
              label="Streak"
              value={`${progress.streak} dia${progress.streak === 1 ? "" : "s"}`}
              hint="Estude todo dia para manter"
            />
            <KpiTile
              icon={CheckCheck}
              label="Roteiro"
              value={`${progress.daysCompleted.length}/${totalDays}`}
              hint="Dias concluídos"
              progress={completedRatio}
            />
            <KpiTile
              icon={Target}
              label="Exercícios"
              value={`${progress.exercisesCorrect}/${plan.exercises.length}`}
              hint="Acertos no quiz"
              progress={plan.exercises.length ? progress.exercisesCorrect / plan.exercises.length : 0}
            />
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Main — diagnóstico + roteiro */}
            <section className="lg:col-span-8 space-y-6">

              {/* Diagnóstico priorizado */}
              <article className="rounded-xl border border-border bg-hud-surface p-5">
                <header className="mb-4 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                    <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
                    Diagnóstico priorizado
                  </h3>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {plan.diagnosis.leaks.length} leaks ativos
                  </span>
                </header>
                <ul className="space-y-3">
                  {plan.diagnosis.leaks.map((leak) => {
                    const isActive = leak.id === (activeLeak?.id ?? plan.diagnosis.leaks[0]?.id);
                    return (
                      <li key={leak.id}>
                        <button
                          onClick={() => setActiveLeakId(leak.id)}
                          className={cn(
                            "w-full text-left rounded-md border p-3 transition-colors",
                            isActive
                              ? "border-primary/60 bg-primary/5"
                              : "border-border bg-background hover:border-primary/40"
                          )}
                        >
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <span className="font-mono text-[10px] text-muted-foreground">{leak.signature}</span>
                            <span className={cn(
                              "font-mono text-[10px] font-bold uppercase tracking-wider",
                              SEVERITY_COLOR[leak.severity] ?? "text-muted-foreground"
                            )}>
                              {leak.severity}
                            </span>
                          </div>
                          <p className="text-sm font-semibold text-foreground">{leak.title}</p>
                          <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{leak.rationale}</p>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </article>

              {/* Roteiro semanal */}
              <article className="rounded-xl border border-border bg-hud-surface p-5">
                <header className="mb-4 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                    <CalendarDays className="size-4 text-primary" aria-hidden />
                    Roteiro semanal
                  </h3>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {plan.weeks.length} semanas ·{" "}
                    ~{Math.round(
                      plan.weeks.reduce((a, w) => a + w.days.reduce((b, d) => b + d.estimatedMinutes, 0), 0) / 60
                    )}h totais
                  </span>
                </header>

                <div className="space-y-5">
                  {plan.weeks.map((week) => (
                    <section key={week.week} className="rounded-md border border-border bg-background p-4">
                      <header className="mb-3 flex items-center justify-between">
                        <h4 className="text-xs font-bold uppercase tracking-widest-2 text-primary">
                          Semana {week.week}
                        </h4>
                        <p className="text-xs text-muted-foreground">{week.focus}</p>
                      </header>
                      <ul className="space-y-2">
                        {week.days.map((day) => {
                          const key  = `${week.week}-${day.day}`;
                          const done = progress.daysCompleted.includes(key);
                          return (
                            <li key={key} className={cn(
                              "rounded-md border p-3 transition-colors",
                              done ? "border-success/40 bg-success/5" : "border-border bg-hud-surface"
                            )}>
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex-1">
                                  <div className="mb-1 flex items-center gap-2">
                                    <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                                      Dia {day.day}
                                    </span>
                                    <span className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
                                      <Timer className="size-3" aria-hidden />
                                      {day.estimatedMinutes} min
                                    </span>
                                  </div>
                                  <p className="text-sm font-semibold text-foreground">{day.title}</p>
                                  <p className="mt-0.5 text-xs text-muted-foreground">{day.topic}</p>
                                  <ul className="mt-2 space-y-1">
                                    {day.objectives.map((o, i) => (
                                      <li key={i} className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
                                        <span className="mt-1 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                                        {o}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                                <button
                                  onClick={() => toggleDay(key)}
                                  aria-pressed={done}
                                  className={cn(
                                    "inline-flex shrink-0 items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider ring-1 transition-colors",
                                    done
                                      ? "bg-success/15 text-success ring-success/30 hover:bg-success/25"
                                      : "bg-secondary text-foreground ring-border hover:bg-muted"
                                  )}
                                >
                                  <CheckCheck className="size-3" aria-hidden />
                                  {done ? "Concluído" : "Marcar"}
                                </button>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </section>
                  ))}
                </div>
              </article>
            </section>

            {/* Sidebar — recursos + instruções */}
            <aside className="lg:col-span-4 space-y-6">
              <section className="rounded-xl border border-border bg-hud-surface p-5">
                <header className="mb-4 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                    <Library className="size-4 text-primary" aria-hidden />
                    Recursos do leak
                  </h3>
                </header>
                {activeLeak && (
                  <>
                    <p className="mb-3 rounded-md border border-border bg-background px-3 py-2 font-mono text-[10px] text-muted-foreground">
                      <span className="text-primary">{activeLeak.signature}</span>
                      {" · "}
                      <span className="text-foreground">{activeLeak.title}</span>
                    </p>
                    <ResourceList resources={plan.resourcesByLeak[activeLeak.id] ?? []} />
                  </>
                )}
              </section>

              <section className="rounded-xl border border-border bg-hud-surface p-5">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                  <Sparkles className="size-4 text-primary" aria-hidden />
                  Como usar
                </h3>
                <ul className="space-y-2 text-xs text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <span className="mt-1 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                    Clique num leak para ver os recursos correspondentes na sidebar.
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                    Siga o roteiro diário e marque o dia como concluído.
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                    Resolva os exercícios abaixo para fixar cada conceito.
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                    Re-importe seu histórico ao fim da semana para medir o delta.
                  </li>
                </ul>
              </section>
            </aside>
          </div>

          {/* Bateria de exercícios */}
          <section className="space-y-3">
            <header className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
                Bateria de exercícios
              </h2>
              <span className="font-mono text-[10px] text-muted-foreground">
                Auto-correção · {plan.exercises.length} questões
              </span>
            </header>
            <ExerciseRunner exercises={plan.exercises} onProgressChange={onExerciseProgress} />
          </section>
        </>
      )}
    </HudLayout>
  );
};

export default StudyPlanPage;
