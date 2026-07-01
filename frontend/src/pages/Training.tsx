import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Dumbbell, GraduationCap, RotateCw, Target, Award, Flame, Star, Trophy, Lock, Map, Play, TrendingUp } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { training } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIER: Record<string, { label: string; ring: string; text: string }> = {
  bronze:  { label: "Bronze",   ring: "#b08d57", text: "text-[#d9a86a]" },
  silver:  { label: "Prata",    ring: "#c8d0d8", text: "text-slate-200" },
  gold:    { label: "Ouro",     ring: "#f5c542", text: "text-amber-300" },
  diamond: { label: "Diamante", ring: "#5ad1ff", text: "text-cyan-300" },
};

export default function Training() {
  const { t } = useTranslation("training");
  const { t: ta } = useTranslation("academy");
  const { data: overview } = useQuery({ queryKey: ["training-overview"], queryFn: training.overview });

  // rótulo humano da habilidade a partir da chave de categoria (reusa as chaves do Leak Trainer)
  const skillLabel = (key: string): string => {
    if (key.startsWith("pf:")) return ta("leakTrainer.cat.postflopBb", { pos: "BB", vs: "BTN" });
    const [scn, pos, vs] = key.split(":");
    if (scn === "rfi") return ta("leakTrainer.cat.rfi", { pos });
    if (scn === "vs_rfi") return ta("leakTrainer.cat.vsRfi", { pos, vs });
    if (scn === "vs_3bet") return ta("leakTrainer.cat.vs3bet", { pos, vs });
    return key;
  };
  const unlockedCount = overview?.achievements.filter((a) => a.unlocked).length ?? 0;
  const achKey = (k: string) => k.replace(/:/g, "_");   // ':' é separador de namespace no i18next
  // contagem por tier (visão gamificada da evolução, além das barras)
  const tierCounts = (["bronze", "silver", "gold", "diamond"] as const).map((tier) => ({
    tier, count: overview?.skills.filter((s) => s.tier === tier).length ?? 0,
  }));
  // Jornada: "Aplicar" só desbloqueia quando o jogador DOMINOU TODO o currículo no Diamante
  // (todos os pontos de falha reais, mastery>=90). Régua vem do backend (training_readiness):
  // cobrir todos os spots do plano, não um leak só. Sem isso, sugerir torneio seria vaidade.
  const readiness = overview?.readiness ?? null;
  const ready = readiness?.ready ?? false;
  const gatePct = readiness && readiness.total > 0
    ? Math.round((readiness.diamond / readiness.total) * 100) : 0;
  const JOURNEY = [
    { key: "train", icon: Dumbbell, status: ready ? "done" : "active" },
    { key: "apply", icon: Play, status: ready ? "active" : "locked" },
    { key: "prove", icon: TrendingUp, status: "soon" },
  ] as const;

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="space-y-4">

        {/* ── Ações de treino — compactas, no topo (a ação principal vem primeiro) ── */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Link to="/ghost"
            className="group flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/[0.05] p-3 transition-colors hover:border-primary/50">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/30">
              <RotateCw className="size-5 text-primary" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-heading text-base font-bold text-foreground">{t("trainer.review.title")}</h3>
              <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{t("trainer.review.desc")}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-primary transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
          <Link to="/leak-trainer"
            className="group flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-3 transition-colors hover:border-amber-500/50">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 ring-1 ring-amber-500/30">
              <Target className="size-5 text-amber-400" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-heading text-base font-bold text-foreground">{t("trainer.train.title")}</h3>
              <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{t("trainer.train.desc")}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-amber-400 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
          <Link to="/academy"
            className="group flex items-center gap-3 rounded-xl border border-violet-500/30 bg-violet-500/[0.06] p-3 transition-colors hover:border-violet-500/50">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 ring-1 ring-violet-500/30">
              <GraduationCap className="size-5 text-violet-400" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-heading text-base font-bold text-foreground">{t("academy.title")}</h3>
              <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">{t("academy.desc")}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-violet-400 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>

        {/* ── A JORNADA — Treinar → Aplicar (gate Ouro) → Provar ───────────────── */}
        {overview && (
          <div className="rounded-2xl border border-border bg-card/40 p-5">
            <h2 className="mb-3 flex items-center gap-2 font-heading text-base font-bold text-foreground">
              <Map className="size-4 text-primary" aria-hidden /> {t("journey.title")}
            </h2>
            <div className="grid grid-cols-3 gap-2">
              {JOURNEY.map(({ key, icon: Icon, status }, i) => {
                const done = status === "done", active = status === "active";
                const locked = status === "locked", soon = status === "soon";
                return (
                  <div key={key} className="flex items-center gap-2">
                    <div className={cn("flex flex-1 flex-col items-center gap-1.5 rounded-xl p-3 text-center ring-1 transition-colors",
                      active ? "bg-primary/10 ring-primary/40"
                      : done ? "bg-emerald-500/10 ring-emerald-500/30"
                      : "bg-muted/5 opacity-60 ring-border")}>
                      <div className="relative">
                        <Icon className={cn("size-6", active ? "text-primary" : done ? "text-emerald-400" : "text-muted-foreground")} aria-hidden />
                        {done && <CheckCircle2 className="absolute -right-1.5 -top-1.5 size-3.5 text-emerald-400" aria-hidden />}
                        {(locked || soon) && <Lock className="absolute -right-1.5 -top-1.5 size-3 text-muted-foreground" aria-hidden />}
                      </div>
                      <p className={cn("font-mono text-[11px] font-bold uppercase tracking-wider", active ? "text-foreground" : "text-muted-foreground")}>
                        {t(`journey.${key}.title`)}
                      </p>
                      <p className="text-[10px] leading-tight text-muted-foreground">
                        {soon ? t("journey.soon") : t(`journey.${key}.desc`)}
                      </p>
                    </div>
                    {i < JOURNEY.length - 1 && <ArrowRight className="size-4 shrink-0 text-muted-foreground/50" aria-hidden />}
                  </div>
                );
              })}
            </div>

            {/* Gate "Aplicar": comemorativo se DOMINOU TUDO no Diamante; senão, progresso honesto
                mostrando quantos pontos de falha faltam (abranger TODOS os spots, não um leak só). */}
            {readiness && readiness.total > 0 && (ready ? (
              <div className="mt-4 flex flex-col gap-3 rounded-xl bg-primary/[0.08] p-4 ring-1 ring-primary/30 sm:flex-row sm:items-center">
                <Trophy className="size-6 shrink-0 text-primary" aria-hidden />
                <p className="flex-1 text-sm text-foreground">
                  {t("journey.readyMsg", { count: readiness.total })}
                </p>
                <Link to="/dashboard"
                  className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
                  <Play className="size-4" aria-hidden /> {t("journey.applyCta")}
                </Link>
              </div>
            ) : (
              <div className="mt-4 rounded-xl bg-muted/5 p-4 ring-1 ring-border">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="flex items-center gap-2 text-sm font-bold text-foreground">
                    <Lock className="size-4 text-muted-foreground" aria-hidden /> {t("journey.gateTitle")}
                  </p>
                  <span className="shrink-0 font-mono text-xs font-bold tabular-nums text-cyan-300">
                    {readiness.diamond}/{readiness.total} <span className="text-muted-foreground">{TIER.diamond.label}</span>
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted/30">
                  <div className="h-full rounded-full bg-cyan-400 transition-[width] duration-500" style={{ width: `${gatePct}%` }} />
                </div>
                <p className="mt-2 text-xs leading-snug text-muted-foreground">{t("journey.gateHint", { count: readiness.total })}</p>
                {readiness.pending.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    {readiness.pending.slice(0, 4).map((p) => {
                      const tm = TIER[p.tier] ?? TIER.bronze;
                      return (
                        <div key={p.category_key} className="flex items-center gap-3">
                          <span className="w-36 shrink-0 truncate text-[12px] text-foreground sm:w-44">{skillLabel(p.category_key)}</span>
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted/30">
                            <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.round(p.mastery)}%`, backgroundColor: tm.ring }} />
                          </div>
                          <span className={cn("w-16 shrink-0 text-right font-mono text-[10px] font-bold uppercase", tm.text)}>{tm.label}</span>
                        </div>
                      );
                    })}
                    {readiness.pending.length > 4 && (
                      <p className="pt-0.5 text-[11px] text-muted-foreground">+{readiness.pending.length - 4} {t("journey.morePending")}</p>
                    )}
                  </div>
                )}
                <Link to="/leak-trainer"
                  className="mt-3 inline-flex items-center gap-2 rounded-lg bg-amber-500/15 px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-amber-300 ring-1 ring-amber-500/30 transition-colors hover:bg-amber-500/25">
                  <Target className="size-4" aria-hidden /> {t("journey.keepTraining")}
                </Link>
              </div>
            ))}
          </div>
        )}

        {/* ── SEU TREINO — status/domínio/conquistas (eixo de gamificação, separado do ELO) ── */}
        {overview && (
          <div className="space-y-4 rounded-2xl border border-border bg-card/40 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 font-heading text-lg font-bold text-foreground">
                <Award className="size-5 text-primary" aria-hidden /> {t("status.title")}
              </h2>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 ring-1 ring-primary/25">
                  <Star className="size-3.5 text-primary" aria-hidden />
                  <span className="font-mono text-xs font-bold tabular-nums text-foreground">{overview.xp.xp_total}</span>
                  <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">XP</span>
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-3 py-1.5 ring-1 ring-amber-500/25">
                  <Flame className="size-3.5 text-amber-400" aria-hidden />
                  <span className="font-mono text-xs font-bold tabular-nums text-amber-300">{overview.xp.streak}</span>
                </span>
              </div>
            </div>

            {/* Missões de hoje (Fase 2 — motor de hábito) */}
            {overview.missions.length > 0 && (
              <div>
                <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("missions.title")}</p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {overview.missions.map((m) => {
                    const pct = Math.min(100, Math.round((m.progress / m.target) * 100));
                    return (
                      <div key={m.key} className={cn("rounded-xl p-3 ring-1 transition-colors",
                        m.completed ? "bg-emerald-500/[0.08] ring-emerald-500/30" : "bg-background/60 ring-border")}>
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-[12px] font-bold leading-snug text-foreground">{t(`missions.${m.key}`, { target: m.target })}</span>
                          {m.completed
                            ? <CheckCircle2 className="size-4 shrink-0 text-emerald-400" aria-hidden />
                            : <span className="shrink-0 font-mono text-[10px] font-bold text-primary">+{m.reward}</span>}
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted/30">
                          <div className={cn("h-full rounded-full transition-[width] duration-500", m.completed ? "bg-emerald-400" : "bg-primary")} style={{ width: `${pct}%` }} />
                        </div>
                        <p className="mt-1 font-mono text-[10px] text-muted-foreground">{m.progress}/{m.target}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Medalhas por tier — visão gamificada da evolução */}
            <div className="grid grid-cols-4 gap-2">
              {tierCounts.map(({ tier, count }) => {
                const tm = TIER[tier];
                return (
                  <div key={tier} className={cn("flex flex-col items-center gap-0.5 rounded-xl py-2 ring-1",
                    count > 0 ? "bg-card/60 ring-border" : "bg-muted/5 opacity-50 ring-border")}>
                    <Trophy className="size-5" style={{ color: tm.ring }} aria-hidden />
                    <span className="font-mono text-base font-bold tabular-nums text-foreground">{count}</span>
                    <span className={cn("font-mono text-[9px] uppercase tracking-wider", tm.text)}>{tm.label}</span>
                  </div>
                );
              })}
            </div>

            {/* Domínio por habilidade — onde o jogador está */}
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("status.skills")}</p>
              {overview.skills.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("status.noSkills")}</p>
              ) : (
                <div className="space-y-2">
                  {overview.skills.slice(0, 6).map((s) => {
                    const tm = TIER[s.tier] ?? TIER.bronze;
                    return (
                      <div key={s.category_key} className="flex items-center gap-3">
                        <span className="w-36 shrink-0 truncate text-[13px] text-foreground sm:w-44">{skillLabel(s.category_key)}</span>
                        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted/30">
                          <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.round(s.mastery)}%`, backgroundColor: tm.ring }} />
                        </div>
                        <span className={cn("w-16 shrink-0 text-right font-mono text-[10px] font-bold uppercase", tm.text)}>{tm.label}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Conquistas — o caminho (desbloqueadas + travadas) */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("status.achievements")}</p>
                <span className="font-mono text-[10px] text-muted-foreground">{unlockedCount} {t("status.of")} {overview.achievements.length}</span>
              </div>
              {/* Linha do tempo: 1 linha (com a barra) no desktop; no celular vira grade de 2
                  linhas (6 col), SEM scroll horizontal. px/py dão folga pro ring + hover:scale. */}
              <div className="px-2 py-2">
                <div className="relative grid grid-cols-6 justify-items-center gap-y-3 sm:flex sm:w-full sm:items-center sm:justify-between">
                  <div className="pointer-events-none absolute inset-x-4 top-1/2 hidden h-0.5 -translate-y-1/2 bg-border sm:block" aria-hidden />
                  {overview.achievements.map((a, i) => (
                    <div key={a.key}
                      title={`${ta(`trainAch.${achKey(a.key)}.title`)} · ${ta(`trainAch.${achKey(a.key)}.desc`)}`}
                      className={cn("relative z-10 flex size-8 cursor-default items-center justify-center rounded-full font-mono text-[11px] font-bold ring-2 transition-transform hover:scale-110",
                        a.unlocked ? "bg-primary text-primary-foreground ring-primary" : "bg-card text-muted-foreground ring-border")}>
                      {i + 1}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </HudLayout>
  );
}
