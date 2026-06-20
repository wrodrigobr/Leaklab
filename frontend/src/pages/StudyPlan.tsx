import { useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Award,
  BrainCircuit,
  CalendarDays,
  CheckCheck,
  Flame,
  GraduationCap,
  Library,
  Loader2,
  Lock,
  Sparkles,
  Target,
  Timer,
  Star,
  Users,
  ChevronRight,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { ExerciseRunner } from "@/components/study/ExerciseRunner";
import { ResourceList } from "@/components/study/ResourceList";
import { buildStudyPlan } from "@/components/study/planBuilder";
import type { StudyPlan } from "@/components/study/types";
import { cn } from "@/lib/utils";
import { study, coaches, metrics, PublicCoach } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";

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

// ── Coach recommendation strip ────────────────────────────────────────────────

function CoachMiniCard({ coach }: { coach: PublicCoach }) {
  const r = coach.avg_rating ?? 0;
  return (
    <Link
      to={`/coaches/${coach.user_id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5 hover:border-primary/50 transition-colors min-w-[200px] shrink-0"
    >
      {coach.photo_url ? (
        <img src={coach.photo_url} alt={coach.display_name}
          className="size-9 rounded-full object-cover border border-border shrink-0" />
      ) : (
        <div className="size-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
          <GraduationCap className="size-4 text-primary" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold text-foreground truncate">{coach.display_name || coach.username}</p>
        {coach.stakes && (
          <p className="font-mono text-[9px] text-muted-foreground">{coach.stakes}</p>
        )}
        <div className="flex items-center gap-2 mt-0.5">
          <div className="flex gap-0.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star key={n} className={cn("size-2.5", r >= n ? "fill-amber-400 text-amber-400" : "text-border")} />
            ))}
          </div>
          <span className="font-mono text-[9px] text-muted-foreground flex items-center gap-0.5">
            <Users className="size-2.5" /> {coach.student_count}
          </span>
        </div>
      </div>
      <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />
    </Link>
  );
}

function CoachRecommendationStrip({ spot }: { spot: string }) {
  const { t } = useTranslation("study");
  const { data, isLoading } = useQuery({
    queryKey: ["coaches-for-spot", spot],
    queryFn: () => coaches.list({ specialty: spot, sort: "rating", limit: 4 }),
    staleTime: 60_000,
  });

  const list = data?.coaches ?? [];
  if (isLoading || list.length === 0) return null;

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] text-muted-foreground flex items-center gap-1">
          <GraduationCap className="size-3" /> {t("resources.coachesTitle")}
        </p>
        <Link to="/coaches" className="font-mono text-[10px] text-primary hover:underline">
          {t("resources.viewAll")}
        </Link>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {list.map((c) => <CoachMiniCard key={c.user_id} coach={c} />)}
      </div>
    </div>
  );
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
  const { user } = useAuth();
  const { t } = useTranslation("study");
  const [searchParams]            = useSearchParams();
  const spotParam                 = searchParams.get("spot") ?? "";
  const [plan, setPlan]           = useState<StudyPlan | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [errorMsg, setErrorMsg]   = useState("");
  const [generating, setGenerating] = useState(false);
  const [coachManaged, setCoachManaged] = useState(false);
  const [planSource, setPlanSource]   = useState<'gto' | 'heuristic' | 'empty' | null>(null);
  const hasCoach = !!user?.coach_id;
  const [activeLeakId, setActiveLeakId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"diagnosis" | "schedule" | "exercises">("diagnosis");
  const [progress, setProgress]   = useState<Progress>(loadProgress);

  const persist = (next: Progress) => {
    setProgress(next);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* noop */ }
  };

  const fetchPlan = async (force = false) => {
    setLoadState("loading");
    setErrorMsg("");
    try {
      const data = await study.plan(90, force);
      if (data.error && !data.cards?.length) {
        // Falha de geração (ex.: IA indisponível / sem saldo) — NUNCA vazar o erro
        // cru da API pro usuário; mostra mensagem amigável e mantém o resto da tela.
        setErrorMsg(t("error.aiUnavailable"));
        setLoadState("error");
        return;
      }
      setCoachManaged(data.coach_managed ?? false);
      setPlanSource(data.source ?? null);
      const built = buildStudyPlan(data);
      setPlan(built);
      if (!activeLeakId) {
        const target = spotParam
          ? built.diagnosis.leaks.find((l) => l.id === spotParam || l.spot === spotParam)
          : null;
        setActiveLeakId(target?.id ?? built.diagnosis.leaks[0]?.id ?? "");
      }
      setLoadState("idle");
      if (force) toast.success(t("toolbar.regenerated"));
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
    const prev = progress.exercisesCorrect;
    persist(updateStreak({ ...progress, exercisesCorrect: correct, exercisesTotal: total }));
    if (correct > prev) {
      metrics.addXp("exercise_correct").catch(() => null);
    }
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
      eyebrow={t("eyebrow")}
      title={t("title")}
      description={t("subtitle")}
    >
      {/* Toolbar */}
      <section className="flex flex-col gap-4 rounded-xl border border-border bg-hud-surface p-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex size-10 items-center justify-center rounded-md bg-primary/15 text-primary">
            <BrainCircuit className="size-5" aria-hidden />
          </span>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-semibold text-foreground">
                {plan ? t("toolbar.planReady") : t("toolbar.planLoading")}
              </h2>
              {planSource && planSource !== 'empty' && (
                <span
                  className={
                    "inline-flex items-center rounded-sm px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider ring-1 " +
                    (planSource === 'gto'
                      ? "text-primary bg-primary/10 ring-primary/20"
                      : "text-muted-foreground bg-muted/30 ring-border")
                  }
                  title={t(planSource === 'gto' ? "source.gtoTooltip" : "source.heuristicTooltip")}
                >
                  {t(planSource === 'gto' ? "source.gto" : "source.heuristic")}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {plan?.diagnosis.summary ?? t("toolbar.analysisWaiting")}
            </p>
          </div>
        </div>
        {hasCoach ? (
          <div className="flex items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-muted-foreground" title="Seu coach gerencia este plano">
            <Lock className="size-3.5 shrink-0" />
            <div className="text-left">
              <p className="font-mono text-[11px] font-bold uppercase tracking-widest-2">
                {t("toolbar.managedBy", { coach: user?.coach_username ?? "Coach" })}
              </p>
              <p className="font-mono text-[9px] text-muted-foreground/70">{t("toolbar.managedSub")}</p>
            </div>
          </div>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={generating || loadState === "loading"}
            className="inline-flex shrink-0 items-center gap-2 rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow disabled:opacity-60 transition-colors"
          >
            {generating || loadState === "loading"
              ? <Loader2 className="size-3.5 animate-spin" aria-hidden />
              : <Sparkles className="size-3.5" aria-hidden />}
            {generating || loadState === "loading" ? t("toolbar.generating") : t("toolbar.generateBtn")}
          </button>
        )}
      </section>

      {/* Loading state */}
      {loadState === "loading" && !plan && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
          <Loader2 className="size-6 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">{t("loading.analyzing")}</span>
          <p className="text-xs text-center max-w-xs">{t("loading.firstTime")}</p>
        </div>
      )}

      {/* Error state */}
      {loadState === "error" && (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <GraduationCap className="size-6 text-muted-foreground" />
          <p className="text-sm text-destructive text-center max-w-sm">{errorMsg}</p>
          <p className="text-xs text-muted-foreground text-center max-w-xs">
            {t("error.retryHint")}
          </p>
          <button
            onClick={() => fetchPlan()}
            className="mt-2 font-mono text-[10px] uppercase tracking-wider text-primary hover:underline"
          >
            {t("toolbar.generateBtn")}
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
              label={t("kpis.level")}
              value={t("kpis.levelValue", { level })}
              hint={t("kpis.xpHint", { xp: xpInLevel })}
              progress={xpInLevel / 500}
            />
            <KpiTile
              icon={Flame}
              label={t("kpis.streak")}
              value={t(progress.streak === 1 ? "kpis.streakValue" : "kpis.streakValue_plural", { count: progress.streak })}
              hint={t("kpis.streakHint")}
            />
            <KpiTile
              icon={CheckCheck}
              label={t("kpis.roadmap")}
              value={`${progress.daysCompleted.length}/${totalDays}`}
              hint={t("kpis.daysCompleted")}
              progress={completedRatio}
            />
            <KpiTile
              icon={Target}
              label={t("kpis.exercises")}
              value={`${progress.exercisesCorrect}/${plan.exercises.length}`}
              hint={t("kpis.exercisesHint")}
              progress={plan.exercises.length ? progress.exercisesCorrect / plan.exercises.length : 0}
            />
          </section>

          {/* Tab bar */}
          <div role="tablist" className="flex gap-1 rounded-lg border border-border bg-hud-surface p-1">
            {([
              { id: "diagnosis" as const, icon: BrainCircuit, label: t("tabs.diagnosis") },
              { id: "schedule"  as const, icon: CalendarDays, label: t("tabs.schedule")  },
              { id: "exercises" as const, icon: Flame,         label: t("tabs.exercises") },
            ]).map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                role="tab"
                aria-selected={activeTab === id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2.5 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors",
                  activeTab === id
                    ? "bg-primary/15 text-primary ring-1 ring-primary/30"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="size-3.5 shrink-0" aria-hidden />
                {label}
              </button>
            ))}
          </div>

          {/* Tab: Diagnóstico */}
          {activeTab === "diagnosis" && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              <section className="lg:col-span-8 space-y-6">
                <article className="rounded-xl border border-border bg-hud-surface p-5">
                  <header className="mb-4 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                      <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
                      {t("diagnosis.title")}
                    </h3>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {t("diagnosis.leaksCount", { count: plan.diagnosis.leaks.length })}
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
                            <p className="mt-1 text-xs text-muted-foreground">{leak.rationale}</p>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  {!hasCoach && activeLeak && (
                    <CoachRecommendationStrip spot={activeLeak.spot} />
                  )}
                </article>
              </section>

              <aside className="lg:col-span-4 space-y-6">
                <section className="rounded-xl border border-border bg-hud-surface p-5">
                  <header className="mb-4 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                      <Library className="size-4 text-primary" aria-hidden />
                      {t("resources.title")}
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
                    {t("howTo.title")}
                  </h3>
                  <ul className="space-y-2 text-xs text-muted-foreground">
                    {[t("howTo.tip1"), t("howTo.tip2"), t("howTo.tip3"), t("howTo.tip4")].map((tip, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="mt-1 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                        {tip}
                      </li>
                    ))}
                  </ul>
                </section>
              </aside>
            </div>
          )}

          {/* Tab: Roteiro */}
          {activeTab === "schedule" && (
            <article className="rounded-xl border border-border bg-hud-surface p-5">
              <header className="mb-4 flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                  <CalendarDays className="size-4 text-primary" aria-hidden />
                  {t("weekly.title")}
                </h3>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {t("weekly.totalHint", {
                    weeks: plan.weeks.length,
                    hours: Math.round(plan.weeks.reduce((a, w) => a + w.days.reduce((b, d) => b + d.estimatedMinutes, 0), 0) / 60),
                  })}
                </span>
              </header>
              <div className="space-y-5">
                {plan.weeks.map((week) => (
                  <section key={week.week} className="rounded-md border border-border bg-background p-4">
                    <header className="mb-3 flex items-center justify-between">
                      <h4 className="text-xs font-bold uppercase tracking-widest-2 text-primary">
                        {t("weekly.weekLabel", { week: week.week })}
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
                                    {t("day.label", { n: day.day })}
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
                                {done ? t("day.done") : t("day.mark")}
                              </button>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))}
              </div>

              {/* Novo modelo: aguardando mais dados + não focar agora */}
              {((plan.observar?.length ?? 0) > 0 || (plan.naoFocar?.length ?? 0) > 0) && (
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  {(plan.observar?.length ?? 0) > 0 && (
                    <section className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4">
                      <h4 className="mb-2 text-xs font-bold uppercase tracking-widest-2 text-amber-400">{t("observe.title")}</h4>
                      <ul className="space-y-1.5">
                        {plan.observar!.map((o, i) => (
                          <li key={i} className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground">{o.indicador}</span>
                            {o.valor_atual ? ` (${o.valor_atual})` : ""}, {o.sample_atual ?? "?"}/{o.sample_necessario ?? "?"} {t("observe.hands")}. {o.por_que_esperar ?? ""}
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {(plan.naoFocar?.length ?? 0) > 0 && (
                    <section className="rounded-md border border-border bg-hud-surface p-4">
                      <h4 className="mb-2 text-xs font-bold uppercase tracking-widest-2 text-muted-foreground">{t("skip.title")}</h4>
                      <ul className="space-y-1.5">
                        {plan.naoFocar!.map((s, i) => (
                          <li key={i} className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground">{s.item}</span>, {s.motivo}
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                </div>
              )}
            </article>
          )}

          {/* Tab: Exercícios */}
          {activeTab === "exercises" && (
            <section className="space-y-3">
              <header className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest-2 text-foreground">
                  <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
                  {t("exercises.title")}
                </h2>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {t("exercises.hint", { count: plan.exercises.length })}
                </span>
              </header>
              <ExerciseRunner exercises={plan.exercises} onProgressChange={onExerciseProgress} />
            </section>
          )}
        </>
      )}
    </HudLayout>
  );
};

export default StudyPlanPage;
