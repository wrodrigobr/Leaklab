import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { HudLayout } from "@/components/hud/HudLayout";
import { BookOpen, ChevronRight } from "lucide-react";

const SECTION_IDS = ["scoring", "indicators", "mstacks", "dna", "ghost", "compare", "coaching", "gamification", "career", "cognitive", "twin", "sparring"] as const;
type SectionId = typeof SECTION_IDS[number];

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-widest ${color}`}>
      {children}
    </span>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 space-y-4">
      <h2 className="text-xl font-semibold tracking-tight text-foreground border-b border-border pb-2">{title}</h2>
      <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">{children}</div>
    </section>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-hud-surface">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left font-mono font-bold uppercase tracking-widest text-muted-foreground">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-hud-surface/50 transition-colors">
              {row.map((cell, j) => <td key={j} className="px-3 py-2 text-foreground">{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Docs() {
  const { t } = useTranslation("docs");
  const [active, setActive] = useState<SectionId>("scoring");
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) setActive(visible[0].target.id as SectionId);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
    );
    SECTION_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observerRef.current?.observe(el);
    });
    return () => observerRef.current?.disconnect();
  }, []);

  return (
    <HudLayout>
      <div className="mx-auto max-w-[1440px] px-4 pt-8 pb-28 md:px-8 md:pb-12">
        <div className="mb-8">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary mb-3">
            <BookOpen className="size-3.5" />
            {t("eyebrow")}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">{t("title")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>

        <div className="flex gap-10 items-start">
          {/* Sidebar nav */}
          <nav className="hidden lg:block sticky top-24 w-52 shrink-0 space-y-0.5">
            {SECTION_IDS.map((id) => (
              <a
                key={id}
                href={`#${id}`}
                className={`flex items-center gap-2 rounded-md px-3 py-2 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  active === id ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-hud-surface"
                }`}
              >
                {active === id ? <ChevronRight className="size-3 shrink-0" /> : <span className="size-3 shrink-0" />}
                {t(`nav.${id}`)}
              </a>
            ))}
          </nav>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-14">

            {/* Scoring */}
            <Section id="scoring" title={t("scoring.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("scoring.p1") }} />
              <Table
                headers={[t("scoring.table.col_label"), t("scoring.table.col_score"), t("scoring.table.col_meaning")]}
                rows={[
                  [<Badge color="bg-emerald-500/15 text-emerald-400">Standard</Badge>,    t("scoring.table.standard_score"), t("scoring.table.standard_meaning")],
                  [<Badge color="bg-yellow-500/15 text-yellow-400">Marginal</Badge>,       t("scoring.table.marginal_score"), t("scoring.table.marginal_meaning")],
                  [<Badge color="bg-orange-500/15 text-orange-400">Small Mistake</Badge>,  t("scoring.table.small_score"),    t("scoring.table.small_meaning")],
                  [<Badge color="bg-destructive/15 text-destructive">Clear Mistake</Badge>, t("scoring.table.clear_score"),   t("scoring.table.clear_meaning")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("scoring.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("scoring.p3") }} />
            </Section>

            {/* Indicators */}
            <Section id="indicators" title={t("indicators.title")}>
              <Table
                headers={[t("indicators.col_indicator"), t("indicators.col_measures"), t("indicators.col_interpret")]}
                rows={[
                  ["Standard%",          t("indicators.std_measures"),      t("indicators.std_interpret")],
                  ["Avg Score",          t("indicators.avg_measures"),      t("indicators.avg_interpret")],
                  ["Clear Mistakes%",    t("indicators.clear_measures"),    t("indicators.clear_interpret")],
                  ["Leak ROI",           t("indicators.leakroi_measures"),  t("indicators.leakroi_interpret")],
                  ["ICM Pressure",       t("indicators.icm_measures"),      t("indicators.icm_interpret")],
                  ["Confidence Drift",   t("indicators.drift_measures"),    t("indicators.drift_interpret")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("indicators.p1") }} />
            </Section>

            {/* M-Ratio Phases */}
            <Section id="mstacks" title={t("mstacks.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("mstacks.p1") }} />
              <Table
                headers={[t("mstacks.col_phase"), t("mstacks.col_mratio"), t("mstacks.col_strategy")]}
                rows={[
                  ["Deep Stack",  "> 20",    t("mstacks.deep_strategy")],
                  ["Mid Stack",   "10 – 20", t("mstacks.mid_strategy")],
                  ["Short Stack", "6 – 10",  t("mstacks.short_strategy")],
                  ["Push/Fold",   "≤ 6",     t("mstacks.pushfold_strategy")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("mstacks.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("mstacks.p3") }} />
            </Section>

            {/* Decision DNA */}
            <Section id="dna" title={t("dna.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("dna.p1") }} />
              <Table
                headers={[t("dna.col_axis"), t("dna.col_calc"), t("dna.col_ref")]}
                rows={[
                  ["Aggression Index",     t("dna.aggression_calc"), t("dna.aggression_ref")],
                  ["Fold Frequency",       t("dna.fold_calc"),       t("dna.fold_ref")],
                  ["3-Bet%",              t("dna.threebet_calc"),   t("dna.threebet_ref")],
                  ["Positional Awareness", t("dna.positional_calc"), t("dna.positional_ref")],
                  ["Discipline",           t("dna.discipline_calc"), t("dna.discipline_ref")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("dna.p2") }} />
            </Section>

            {/* Ghost Table */}
            <Section id="ghost" title={t("ghost.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("ghost.p1") }} />
              <p>{t("ghost.p2")}</p>
              <Table
                headers={[t("ghost.col_result"), t("ghost.col_next")]}
                rows={[
                  [t("ghost.result_hit"),    t("ghost.hit_next")],
                  [t("ghost.result_miss"),   t("ghost.miss_next")],
                  [t("ghost.result_mastery"), t("ghost.mastery_next")],
                ]}
              />
              <p>{t("ghost.p3")}</p>
              <p dangerouslySetInnerHTML={{ __html: t("ghost.p4") }} />
            </Section>

            {/* Tournament Comparison */}
            <Section id="compare" title={t("compare.title")}>
              <p>{t("compare.p1")}</p>
              <ul className="list-disc pl-5 space-y-1">
                <li><strong className="text-foreground">{t("compare.bullet_standard")}</strong></li>
                <li>{t("compare.bullet_leaks")}</li>
                <li>{t("compare.bullet_breakdown")}</li>
                <li>{t("compare.bullet_icm")}</li>
                <li>{t("compare.bullet_narrative")}</li>
              </ul>
              <p dangerouslySetInnerHTML={{ __html: t("compare.p2") }} />
            </Section>

            {/* Coaching */}
            <Section id="coaching" title={t("coaching.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("coaching.p1") }} />
              <Table
                headers={[t("coaching.col_term"), t("coaching.col_meaning")]}
                rows={[
                  ["Baseline",          t("coaching.baseline_meaning")],
                  ["Baseline Delta",    t("coaching.delta_meaning")],
                  ["Coach Reviewed",    t("coaching.reviewed_meaning")],
                  [t("coaching.term_override"), t("coaching.override_meaning")],
                  ["Coach Effectiveness", t("coaching.effectiveness_meaning")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("coaching.p2") }} />
            </Section>

            {/* Gamification */}
            <Section id="gamification" title={t("gamification.title")}>
              <p>{t("gamification.p1")}</p>
              <Table
                headers={[t("gamification.col_event"), t("gamification.col_xp")]}
                rows={[
                  [t("gamification.event_import"),   "50 XP"],
                  [t("gamification.event_exercise"),  "10 XP"],
                  [t("gamification.event_drill"),     "25 XP"],
                  [t("gamification.event_mastery"),  "100 XP"],
                ]}
              />
              <p className="mt-2">{t("gamification.levels_title")}</p>
              <Table
                headers={[t("gamification.col_level"), t("gamification.col_req")]}
                rows={[
                  [t("gamification.level_beginner"), "< 60%"],
                  [t("gamification.level_student"),  "60% – 70%"],
                  [t("gamification.level_grinder"),  "70% – 77%"],
                  [t("gamification.level_regular"),  "77% – 86%"],
                  [t("gamification.level_solid"),    "86% – 92%"],
                  [t("gamification.level_expert"),   "92% – 96%"],
                  [t("gamification.level_elite"),    "≥ 96%"],
                ]}
              />
              <p>{t("gamification.streak_desc")}</p>
              <p><strong className="text-foreground">{t("gamification.achievements_title")}</strong></p>
              <ul className="list-disc pl-5 space-y-1">
                <li>🎯 {t("gamification.ach_first")}</li>
                <li>📊 {t("gamification.ach_100")}</li>
                <li>🎮 {t("gamification.ach_drill")}</li>
                <li>🔥 {t("gamification.ach_streak")}</li>
                <li>🏆 {t("gamification.ach_10")}</li>
              </ul>
            </Section>

            {/* Career Trajectory */}
            <Section id="career" title={t("career.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("career.p1") }} />
              <Table
                headers={[t("career.table.col_term"), t("career.table.col_meaning")]}
                rows={[
                  [t("career.table.slope_term"),     t("career.table.slope_meaning")],
                  [t("career.table.milestone_term"),  t("career.table.milestone_meaning")],
                  [t("career.table.blocking_term"),  t("career.table.blocking_meaning")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("career.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("career.p3") }} />
            </Section>

            {/* Cognitive Failure Mapper */}
            <Section id="cognitive" title={t("cognitive.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("cognitive.p1") }} />
              <Table
                headers={[t("cognitive.table.col_pattern"), t("cognitive.table.col_trigger"), t("cognitive.table.col_signal")]}
                rows={[
                  [<Badge color="bg-destructive/15 text-destructive">{t("cognitive.patterns.revenge")}</Badge>,     t("cognitive.patterns.revenge_trigger"),     t("cognitive.patterns.revenge_signal")],
                  [<Badge color="bg-orange-500/15 text-orange-400">{t("cognitive.patterns.fear")}</Badge>,          t("cognitive.patterns.fear_trigger"),          t("cognitive.patterns.fear_signal")],
                  [<Badge color="bg-yellow-500/15 text-yellow-400">{t("cognitive.patterns.sunk")}</Badge>,          t("cognitive.patterns.sunk_trigger"),          t("cognitive.patterns.sunk_signal")],
                  [<Badge color="bg-orange-500/15 text-orange-400">{t("cognitive.patterns.entitlement")}</Badge>,  t("cognitive.patterns.entitlement_trigger"),  t("cognitive.patterns.entitlement_signal")],
                  [<Badge color="bg-yellow-500/15 text-yellow-400">{t("cognitive.patterns.compensation")}</Badge>, t("cognitive.patterns.compensation_trigger"), t("cognitive.patterns.compensation_signal")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("cognitive.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("cognitive.p3") }} />
            </Section>

            {/* Strategic Twin */}
            <Section id="twin" title={t("twin.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("twin.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("twin.p2") }} />
              <Table
                headers={[t("twin.table.col_term"), t("twin.table.col_meaning")]}
                rows={[
                  [t("twin.table.avg_term"),    t("twin.table.avg_meaning")],
                  [t("twin.table.costly_term"), t("twin.table.costly_meaning")],
                  [t("twin.table.delta_term"),  t("twin.table.delta_meaning")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("twin.p3") }} />
            </Section>

            {/* Sparring Mode */}
            <Section id="sparring" title={t("sparring.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("sparring.p1") }} />
              <Table
                headers={[t("sparring.col_phase"), t("sparring.col_desc")]}
                rows={[
                  [t("sparring.phase_playing"), t("sparring.phase_playing_desc")],
                  [t("sparring.phase_feedback"), t("sparring.phase_feedback_desc")],
                  [t("sparring.phase_summary"), t("sparring.phase_summary_desc")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("sparring.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("sparring.p3") }} />
            </Section>

          </div>
        </div>
      </div>
    </HudLayout>
  );
}
