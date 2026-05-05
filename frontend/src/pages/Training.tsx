import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Ghost, GraduationCap, Swords } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";

export default function Training() {
  const { t } = useTranslation("training");

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="mx-auto max-w-3xl space-y-6">

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* ── Ghost Table card ─────────────────────────────────────────────── */}
          <div className="flex flex-col rounded-xl border border-border bg-hud-surface overflow-hidden">
            <div className="flex-1 p-6 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex size-11 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/30">
                  <Ghost className="size-5 text-primary" aria-hidden />
                </div>
                <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-primary bg-primary/10 rounded-full px-2.5 py-1 ring-1 ring-primary/20">
                  {t("ghost.badge")}
                </span>
              </div>

              <div>
                <h2 className="text-lg font-bold text-foreground">{t("ghost.title")}</h2>
                <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
                  {t("ghost.desc")}
                </p>
              </div>

              <ul className="space-y-2">
                {(["f1", "f2", "f3"] as const).map((k) => (
                  <li key={k} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="size-3.5 text-primary shrink-0 mt-0.5" aria-hidden />
                    {t(`ghost.${k}`)}
                  </li>
                ))}
              </ul>
            </div>

            <div className="border-t border-border p-4">
              <Link
                to="/ghost"
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 font-mono text-sm font-bold uppercase tracking-widest text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Ghost className="size-4" aria-hidden />
                {t("ghost.cta")}
              </Link>
            </div>
          </div>

          {/* ── Sparring Mode card ───────────────────────────────────────────── */}
          <div className="flex flex-col rounded-xl border border-amber-500/30 bg-amber-500/5 overflow-hidden">
            <div className="flex-1 p-6 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex size-11 items-center justify-center rounded-lg bg-amber-500/10 ring-1 ring-amber-500/30">
                  <Swords className="size-5 text-amber-400" aria-hidden />
                </div>
                <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-amber-400 bg-amber-500/10 rounded-full px-2.5 py-1 ring-1 ring-amber-500/20">
                  {t("sparring.badge")}
                </span>
              </div>

              <div>
                <h2 className="text-lg font-bold text-foreground">{t("sparring.title")}</h2>
                <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
                  {t("sparring.desc")}
                </p>
              </div>

              <ul className="space-y-2">
                {(["f1", "f2", "f3"] as const).map((k) => (
                  <li key={k} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="size-3.5 text-amber-400 shrink-0 mt-0.5" aria-hidden />
                    {t(`sparring.${k}`)}
                  </li>
                ))}
              </ul>
            </div>

            <div className="border-t border-amber-500/20 p-4">
              <Link
                to="/sparring"
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-5 py-2.5 font-mono text-sm font-bold uppercase tracking-widest text-black hover:bg-amber-400 transition-colors"
              >
                <Swords className="size-4" aria-hidden />
                {t("sparring.cta")}
              </Link>
            </div>
          </div>

        </div>

        {/* ── Academia card (full width) ────────────────────────────────────── */}
        <div className="flex flex-col rounded-xl border border-violet-500/30 bg-violet-500/5 overflow-hidden">
          <div className="p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-violet-500/10 ring-1 ring-violet-500/30">
                <GraduationCap className="size-5 text-violet-400" aria-hidden />
              </div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-violet-400 bg-violet-500/10 rounded-full px-2.5 py-1 ring-1 ring-violet-500/20">
                {t("academy.badge")}
              </span>
            </div>

            <div className="md:flex md:items-end md:justify-between md:gap-6">
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-foreground">{t("academy.title")}</h2>
                <p className="text-sm text-muted-foreground leading-relaxed max-w-xl">
                  {t("academy.desc")}
                </p>
                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 pt-1">
                  {(["f1", "f2", "f3", "f4"] as const).map((k) => (
                    <li key={k} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="size-3.5 text-violet-400 shrink-0 mt-0.5" aria-hidden />
                      {t(`academy.${k}`)}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-4 md:mt-0 shrink-0">
                <Link
                  to="/academy"
                  className="flex items-center justify-center gap-2 rounded-lg bg-violet-500 px-6 py-2.5 font-mono text-sm font-bold uppercase tracking-widest text-white hover:bg-violet-400 transition-colors whitespace-nowrap"
                >
                  <GraduationCap className="size-4" aria-hidden />
                  {t("academy.cta")}
                </Link>
              </div>
            </div>
          </div>
        </div>

      </div>
    </HudLayout>
  );
}
