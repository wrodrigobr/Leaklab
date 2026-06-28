import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, CheckCircle2, Dumbbell, GraduationCap, RotateCw, Target } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";

export default function Training() {
  const { t } = useTranslation("training");

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="mx-auto max-w-4xl space-y-6">

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
