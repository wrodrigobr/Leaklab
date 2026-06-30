import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Dumbbell, GraduationCap, RotateCw, Target, Award, Flame, Star, Trophy, Lock } from "lucide-react";
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

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="mx-auto max-w-4xl space-y-6">

        {/* ── SEU TREINO — status/domínio/conquistas (eixo de gamificação, separado do ELO) ── */}
        {overview && (
          <div className="space-y-5 rounded-2xl border border-border bg-card/40 p-6 md:p-7">
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
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {overview.achievements.map((a) => (
                  <div key={a.key} title={a.desc}
                    className={cn("flex items-center gap-2 rounded-lg px-3 py-2 ring-1 transition-colors",
                      a.unlocked ? "bg-primary/[0.08] ring-primary/30" : "bg-muted/10 opacity-55 ring-border")}>
                    {a.unlocked
                      ? <Trophy className="size-4 shrink-0 text-primary" aria-hidden />
                      : <Lock className="size-4 shrink-0 text-muted-foreground" aria-hidden />}
                    <span className={cn("truncate text-[12px] font-bold", a.unlocked ? "text-foreground" : "text-muted-foreground")}>{a.title}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── TREINO — um conceito, dois modos complementares ──────────────────── */}
        <div className="rounded-2xl border border-border bg-gradient-to-br from-primary/[0.06] to-transparent p-6 md:p-7">
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/30">
              <Dumbbell className="size-6 text-primary" aria-hidden />
            </div>
            <div>
              <h2 className="font-heading text-xl font-bold text-foreground">{t("trainer.title")}</h2>
              <p className="text-sm text-muted-foreground">{t("trainer.subtitle")}</p>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">

            {/* Modo: Revisar (Ghost Table — SRS, mãos reais) */}
            <div className="flex flex-col rounded-xl border border-primary/30 bg-primary/[0.04] p-5">
              <div className="flex items-center gap-2">
                <RotateCw className="size-5 text-primary" aria-hidden />
                <h3 className="font-heading text-base font-bold text-foreground">{t("trainer.review.title")}</h3>
              </div>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{t("trainer.review.desc")}</p>
              <ul className="mt-3 space-y-1.5">
                {(["p1", "p2", "p3"] as const).map((k) => (
                  <li key={k} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                    <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
                    {t(`trainer.review.${k}`)}
                  </li>
                ))}
              </ul>
              <Link to="/ghost"
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90">
                <RotateCw className="size-4" aria-hidden /> {t("trainer.review.cta")}
              </Link>
            </div>

            {/* Modo: Treinar (Leak Trainer — adaptativo, sintético) */}
            <div className="flex flex-col rounded-xl border border-amber-500/30 bg-amber-500/[0.05] p-5">
              <div className="flex items-center gap-2">
                <Target className="size-5 text-amber-400" aria-hidden />
                <h3 className="font-heading text-base font-bold text-foreground">{t("trainer.train.title")}</h3>
              </div>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{t("trainer.train.desc")}</p>
              <ul className="mt-3 space-y-1.5">
                {(["p1", "p2", "p3"] as const).map((k) => (
                  <li key={k} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                    <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-amber-400" aria-hidden />
                    {t(`trainer.train.${k}`)}
                  </li>
                ))}
              </ul>
              <Link to="/leak-trainer"
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
                <Target className="size-4" aria-hidden /> {t("trainer.train.cta")}
              </Link>
            </div>
          </div>

          <p className="mt-4 flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground/80">
            <ArrowRight className="size-3 text-primary" aria-hidden /> {t("trainer.hint")}
          </p>
        </div>

        {/* ── Academia (fundamentos, à parte do treino de leaks) ───────────────── */}
        <div className="group flex flex-col overflow-hidden rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-500/[0.1] to-transparent transition-colors hover:border-violet-500/50 md:flex-row">
          <div className="flex-1 space-y-4 p-7">
            <div className="flex items-start justify-between gap-3">
              <div className="flex size-14 items-center justify-center rounded-xl bg-violet-500/10 ring-1 ring-violet-500/30">
                <GraduationCap className="size-7 text-violet-400" aria-hidden />
              </div>
              <span className="rounded-full bg-violet-500/10 px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-widest text-violet-400 ring-1 ring-violet-500/20">
                {t("academy.badge")}
              </span>
            </div>
            <div>
              <h2 className="font-heading text-xl font-bold text-foreground">{t("academy.title")}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t("academy.desc")}</p>
            </div>
            <Link to="/academy"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-violet-500 px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest text-white transition-colors hover:bg-violet-400">
              <GraduationCap className="size-4" aria-hidden /> {t("academy.cta")}
            </Link>
          </div>
        </div>

      </div>
    </HudLayout>
  );
}
