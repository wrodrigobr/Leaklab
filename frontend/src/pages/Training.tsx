import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Ghost, GraduationCap } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";

export default function Training() {
  const { t } = useTranslation("training");

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="mx-auto max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* ── Ghost Table card ──────────────────────────────────────────────── */}
        <div className="group flex flex-col rounded-2xl border border-border bg-gradient-to-br from-primary/[0.07] to-transparent overflow-hidden transition-colors hover:border-primary/40">
          <div className="flex-1 p-7 space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex size-14 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/30">
                <Ghost className="size-7 text-primary" aria-hidden />
              </div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-primary bg-primary/10 rounded-full px-2.5 py-1 ring-1 ring-primary/20">
                {t("ghost.badge")}
              </span>
            </div>

            <div>
              <h2 className="font-heading text-xl font-bold text-foreground">{t("ghost.title")}</h2>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                {t("ghost.desc")}
              </p>
            </div>

            <ul className="space-y-2.5">
              {(["f1", "f2", "f3"] as const).map((k) => (
                <li key={k} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="size-3.5 text-primary shrink-0 mt-0.5" aria-hidden />
                  {t(`ghost.${k}`)}
                </li>
              ))}
            </ul>
          </div>

          <div className="p-5 pt-0">
            <Link
              to="/ghost"
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Ghost className="size-4" aria-hidden />
              {t("ghost.cta")}
            </Link>
          </div>
        </div>

        {/* Sparring removido do hub até termos o arco sintético funcional (opção 2). */}

        {/* ── Academia card ─────────────────────────────────────────────────── */}
        <div className="group flex flex-col rounded-2xl border border-violet-500/30 bg-gradient-to-br from-violet-500/[0.1] to-transparent overflow-hidden transition-colors hover:border-violet-500/50">
          <div className="flex-1 p-7 space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex size-14 items-center justify-center rounded-xl bg-violet-500/10 ring-1 ring-violet-500/30">
                <GraduationCap className="size-7 text-violet-400" aria-hidden />
              </div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-violet-400 bg-violet-500/10 rounded-full px-2.5 py-1 ring-1 ring-violet-500/20">
                {t("academy.badge")}
              </span>
            </div>

            <div>
              <h2 className="font-heading text-xl font-bold text-foreground">{t("academy.title")}</h2>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                {t("academy.desc")}
              </p>
            </div>

            <ul className="space-y-2.5">
              {(["f1", "f2", "f3", "f4"] as const).map((k) => (
                <li key={k} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="size-3.5 text-violet-400 shrink-0 mt-0.5" aria-hidden />
                  {t(`academy.${k}`)}
                </li>
              ))}
            </ul>
          </div>

          <div className="p-5 pt-0">
            <Link
              to="/academy"
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-500 px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest text-white hover:bg-violet-400 transition-colors"
            >
              <GraduationCap className="size-4" aria-hidden />
              {t("academy.cta")}
            </Link>
          </div>
        </div>

      </div>
    </HudLayout>
  );
}
