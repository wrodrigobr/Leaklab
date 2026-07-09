import { useCallback } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookText, Dumbbell, ChevronRight } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { QuizRunner } from "@/components/academy/AcademyQuizPage";
import { academy } from "@/lib/api";

// Verbetes por categoria. `to` = aula que aprofunda o termo (opcional). Nome e definição
// vêm do i18n (lessons.terms.<id>_t / _d) para tradução.
type Term = { id: string; to?: string };
const CATEGORIES: { cat: string; terms: Term[] }[] = [
  {
    cat: "fund",
    terms: [
      { id: "position", to: "/academy/position" },
      { id: "range" },
      { id: "equity", to: "/academy/math" },
      { id: "showdown", to: "/academy/showdown" },
      { id: "bluff" },
      { id: "value" },
      { id: "pot" },
      { id: "stack" },
    ],
  },
  {
    cat: "preflop",
    terms: [
      { id: "open", to: "/academy/gto-preflop?scenario=rfi" },
      { id: "threebet", to: "/academy/3bet" },
      { id: "fourbet" },
      { id: "blinds" },
      { id: "steal" },
      { id: "squeeze" },
    ],
  },
  {
    cat: "postflop",
    terms: [
      { id: "cbet", to: "/academy/postflop" },
      { id: "barrel", to: "/academy/barrels" },
      { id: "board", to: "/academy/board-strength" },
      { id: "draw", to: "/academy/draws" },
      { id: "semibluff", to: "/academy/draws" },
      { id: "blocker", to: "/academy/blockers" },
      { id: "polarized", to: "/academy/imbalances" },
      { id: "checkraise" },
    ],
  },
  {
    cat: "math",
    terms: [
      { id: "potodds", to: "/academy/math" },
      { id: "outs", to: "/academy/math" },
      { id: "rule24", to: "/academy/math" },
      { id: "ev" },
      { id: "mdf", to: "/academy/mdf" },
      { id: "spr" },
      { id: "combos", to: "/academy/combos" },
    ],
  },
  {
    cat: "tour",
    terms: [
      { id: "icm", to: "/academy/icm" },
      { id: "mratio", to: "/academy/push-fold" },
      { id: "pushfold", to: "/academy/push-fold" },
      { id: "bounty", to: "/academy/pko" },
      { id: "multiway", to: "/academy/multiway" },
      { id: "bubble" },
    ],
  },
];

export default function AcademyTerms() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.terms.${k}`);

  const loadDrill   = useCallback(() => academy.termsQuestion(), []);
  const submitDrill = useCallback(
    (idx: number, ci: number, xp: number) => { academy.termsSubmit(idx, ci, xp).catch(() => {}); },
    [],
  );

  return (
    <HudLayout eyebrow={L("eyebrow")} title={L("title")} description={L("subtitle")}>
      <article className="mx-auto max-w-6xl space-y-10 pb-8">

        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{L("intro")}</p>

        {CATEGORIES.map(({ cat, terms }) => (
          <section key={cat} className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-primary">
                {L(`cat_${cat}`)}
              </span>
              <div className="h-px flex-1 bg-border" />
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {terms.map(({ id, to }) => (
                <div key={id} className="rounded-lg border border-border/60 bg-background/40 p-3">
                  <div className="text-sm font-bold text-foreground">{L(`${id}_t`)}</div>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{L(`${id}_d`)}</p>
                  {to && (
                    <Link
                      to={to}
                      className="mt-2 inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-primary hover:underline"
                    >
                      {L("seeLesson")}
                      <ChevronRight className="size-3" aria-hidden />
                    </Link>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}

        <section className="space-y-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-emerald-300">
              <Dumbbell className="size-3.5" aria-hidden />
              {L("drill_title")}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{L("drill_sub")}</p>
          </div>
          <QuizRunner theme="emerald" Icon={BookText} loadFn={loadDrill} submitFn={submitDrill} />
        </section>
      </article>
    </HudLayout>
  );
}
