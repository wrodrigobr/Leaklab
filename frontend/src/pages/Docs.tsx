import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { HudLayout } from "@/components/hud/HudLayout";
import { BookOpen, ChevronRight, TrendingUp } from "lucide-react";

const SECTION_IDS = ["import", "scoring", "indicators", "gto_method", "alignment_matrix", "pko_tournaments", "mstacks", "dna", "leaks", "causal_map", "form", "decisions", "streets", "positions", "pressure", "icm", "bankroll", "level", "ghost", "compare", "coaching", "gamification", "ranking", "career", "cognitive", "twin", "sparring"] as const;
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

// ─── Visual example helpers ───────────────────────────────────────────────────

type BarColor = "emerald" | "amber" | "orange" | "destructive" | "primary";

const BAR_CFG: Record<BarColor, { bar: string; text: string }> = {
  emerald:     { bar: "bg-emerald-500", text: "text-emerald-400" },
  amber:       { bar: "bg-amber-500",   text: "text-amber-400"   },
  orange:      { bar: "bg-orange-500",  text: "text-orange-400"  },
  destructive: { bar: "bg-destructive", text: "text-destructive" },
  primary:     { bar: "bg-primary",     text: "text-primary"     },
};

function ExampleBox({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-hud-surface/60 p-4 space-y-3">
      <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">{label}</p>
      {children}
    </div>
  );
}

function MiniBar({ label, pct, color = "primary", refPct }: {
  label: string; pct: number; color?: BarColor; refPct?: number;
}) {
  const { bar, text } = BAR_CFG[color];
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-[10px] text-muted-foreground w-16 shrink-0 truncate">{label}</span>
      <div className="relative flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        <div className={`h-full rounded-full ${bar}`} style={{ width: `${Math.min(100, pct)}%` }} />
        {refPct !== undefined && (
          <div className="absolute top-0 h-full w-px bg-primary/60" style={{ left: `${refPct}%` }} />
        )}
      </div>
      <span className={`font-mono text-[10px] font-bold tabular-nums w-8 text-right ${text}`}>{pct}%</span>
    </div>
  );
}

const SCORE_BADGE_CFG = {
  standard: "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/20",
  marginal: "bg-yellow-500/15 text-yellow-400 ring-1 ring-yellow-500/20",
  small:    "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/20",
  clear:    "bg-destructive/15 text-destructive ring-1 ring-destructive/20",
} as const;

function MiniScoreLine({ quality, score, decision }: {
  quality: keyof typeof SCORE_BADGE_CFG; score: string; decision: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className={`shrink-0 mt-0.5 inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide ${SCORE_BADGE_CFG[quality]}`}>
        {score}
      </span>
      <span className="text-xs text-muted-foreground leading-tight">{decision}</span>
    </div>
  );
}

const SESSION_CFG = {
  standard: { cls: "bg-emerald-500", pct: 100 },
  marginal: { cls: "bg-yellow-500",  pct: 62  },
  small:    { cls: "bg-orange-500",  pct: 38  },
  clear:    { cls: "bg-destructive", pct: 18  },
} as const;

function MiniSessionBars({ sessions }: { sessions: ReadonlyArray<keyof typeof SESSION_CFG> }) {
  return (
    <div className="flex items-end gap-1 h-12">
      {sessions.map((q, i) => (
        <div
          key={i}
          className={`flex-1 rounded-sm ${SESSION_CFG[q].cls}`}
          style={{ height: `${SESSION_CFG[q].pct}%` }}
        />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

export default function Docs() {
  const { t } = useTranslation("docs");
  const { t: td } = useTranslation("dashboard");
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
            <Link
              to="/docs/rating"
              className="mt-1 flex items-center gap-2 rounded-md border-t border-border/50 px-3 pt-3 pb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:bg-hud-surface hover:text-foreground"
            >
              <TrendingUp className="size-3 shrink-0" />
              {t("nav.rating")}
            </Link>
          </nav>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-14">

            {/* Supported Sites & Import */}
            <Section id="import" title={t("import.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("import.p1") }} />
              <Table
                headers={[t("import.col_site"), t("import.col_formats"), t("import.col_where")]}
                rows={[
                  ["PokerStars", "MTT · SNG · Cash", t("import.ps_where")],
                  ["GGPoker",    "MTT · SNG · Spin", t("import.gg_where")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("import.p2") }} />
            </Section>

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
              <ExampleBox label={t("exampleLabel")}>
                <MiniScoreLine quality="standard" score="0.04" decision={t("scoring.example_standard")} />
                <MiniScoreLine quality="marginal" score="0.14" decision={t("scoring.example_marginal")} />
                <MiniScoreLine quality="small"    score="0.28" decision={t("scoring.example_small")} />
                <MiniScoreLine quality="clear"    score="0.51" decision={t("scoring.example_clear")} />
              </ExampleBox>
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

            {/* GTO Classification Methodology */}
            <Section id="gto_method" title={t("gto_method.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("gto_method.p1") }} />
              <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground/70">{t("gto_method.scenarios_title")}</p>
              <Table
                headers={[t("gto_method.col_scenario"), t("gto_method.col_condition"), t("gto_method.col_range_used")]}
                rows={[
                  [t("gto_method.rfi_scenario"),     t("gto_method.rfi_condition"),     t("gto_method.rfi_range")],
                  [t("gto_method.vs_rfi_scenario"),  t("gto_method.vs_rfi_condition"),  t("gto_method.vs_rfi_range")],
                  [t("gto_method.vs_3bet_scenario"), t("gto_method.vs_3bet_condition"), t("gto_method.vs_3bet_range")],
                ]}
              />
              <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground/70">{t("gto_method.quality_title")}</p>
              <Table
                headers={[t("gto_method.col_quality"), t("gto_method.col_quality_meaning"), t("gto_method.col_label_impact")]}
                rows={[
                  [<Badge color="bg-emerald-500/15 text-emerald-400">{t("gto_method.correct_label")}</Badge>,    t("gto_method.correct_meaning"),    t("gto_method.correct_impact")],
                  [<Badge color="bg-sky-500/15 text-sky-400">{t("gto_method.acceptable_label")}</Badge>,         t("gto_method.acceptable_meaning"), t("gto_method.acceptable_impact")],
                  [<Badge color="bg-amber-500/15 text-amber-400">{t("gto_method.leak_label")}</Badge>,           t("gto_method.leak_meaning"),       t("gto_method.leak_impact")],
                  [<Badge color="bg-destructive/15 text-destructive">{t("gto_method.major_leak_label")}</Badge>, t("gto_method.major_leak_meaning"), t("gto_method.major_leak_impact")],
                ]}
              />
              <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground/70">{t("gto_method.buckets_title")}</p>
              <Table
                headers={[t("gto_method.col_bucket"), t("gto_method.col_bb_range")]}
                rows={[
                  ["10bb", "≤ 12bb"],
                  ["14bb", "13 – 16bb"],
                  ["20bb", "17 – 24bb"],
                  ["30bb", "25 – 35bb"],
                  ["40bb", "36 – 45bb"],
                  ["50bb", "46 – 62bb"],
                  ["75bb", "63 – 87bb"],
                  ["100bb", "> 87bb"],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("gto_method.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("gto_method.p3") }} />
            </Section>

            {/* Alignment Matrix (Heatmap posição × street) */}
            <Section id="alignment_matrix" title={t("alignment_matrix.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("alignment_matrix.p1") }} />
              <Table
                headers={[t("alignment_matrix.col_color"), t("alignment_matrix.col_pct"), t("alignment_matrix.col_meaning")]}
                rows={[
                  [<Badge color="bg-emerald-500/20 text-emerald-300">{t("alignment_matrix.bucket_strong")}</Badge>, "≥ 70%",   t("alignment_matrix.meaning_strong")],
                  [<Badge color="bg-amber-500/20 text-amber-300">{t("alignment_matrix.bucket_ok")}</Badge>,         "55–70%", t("alignment_matrix.meaning_ok")],
                  [<Badge color="bg-orange-500/20 text-orange-300">{t("alignment_matrix.bucket_weak")}</Badge>,     "40–55%", t("alignment_matrix.meaning_weak")],
                  [<Badge color="bg-red-500/20 text-red-300">{t("alignment_matrix.bucket_leak")}</Badge>,           "< 40%",  t("alignment_matrix.meaning_leak")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("alignment_matrix.p2") }} />
            </Section>

            {/* PKO Tournaments */}
            <Section id="pko_tournaments" title={t("pko_tournaments.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("pko_tournaments.p1") }} />
              <Table
                headers={[t("pko_tournaments.col_situation"), t("pko_tournaments.col_classic"), t("pko_tournaments.col_pko")]}
                rows={[
                  [t("pko_tournaments.row_required"),  "~14%", "~6% (−2pp aplicado)"],
                  [t("pko_tournaments.row_pre_ft"),    "high → medium → low", t("pko_tournaments.pre_ft_pko")],
                  [t("pko_tournaments.row_final"),     t("pko_tournaments.final_classic"), t("pko_tournaments.final_pko")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("pko_tournaments.p2") }} />
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

            {/* Top Leaks */}
            <Section id="leaks" title={t("leaks.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("leaks.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("leaks.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("leaks.p3") }} />
              <p dangerouslySetInnerHTML={{ __html: t("leaks.p4") }} />
              <ExampleBox label={t("exampleLabel")}>
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="size-1.5 rounded-full bg-destructive shrink-0" />
                      <span className="font-mono text-[11px] font-semibold text-foreground truncate">River overcall OOP</span>
                      <Badge color="bg-destructive/15 text-destructive">{td("leaks.critical")}</Badge>
                    </div>
                    <span className="font-mono text-[10px] text-destructive shrink-0">~$9/mo</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pl-3.5">
                    {[
                      { val: "31",  label: t("leaks.example_freq") },
                      { val: "0.44", label: "avg score" },
                      { val: "↘ reg.", label: t("leaks.example_trend") },
                    ].map(({ val, label }) => (
                      <div key={label} className="text-center">
                        <p className="font-mono text-sm font-bold text-destructive">{val}</p>
                        <p className="font-mono text-[9px] uppercase tracking-wide text-muted-foreground">{label}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{t("leaks.example")}</p>
              </ExampleBox>
            </Section>

            {/* Causal Map */}
            <Section id="causal_map" title={t("causal_map.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("causal_map.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("causal_map.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("causal_map.p3") }} />
            </Section>

            {/* Recent Form */}
            <Section id="form" title={t("form.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("form.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("form.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("form.p3") }} />
              <ExampleBox label={t("exampleLabel")}>
                <MiniSessionBars sessions={["standard", "standard", "marginal", "clear", "small", "marginal", "standard"]} />
                <div className="flex gap-4 flex-wrap">
                  {(["standard", "marginal", "small", "clear"] as const).map((q) => (
                    <div key={q} className="flex items-center gap-1.5">
                      <div className={`size-2 rounded-sm ${SESSION_CFG[q].cls}`} />
                      <span className="font-mono text-[9px] text-muted-foreground capitalize">{td(`form.${q === "small" ? "smallMistake" : q === "clear" ? "clearError" : q}`)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">{t("form.example")}</p>
              </ExampleBox>
            </Section>

            {/* Decision Quality */}
            <Section id="decisions" title={t("decisions.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("decisions.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("decisions.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("decisions.p3") }} />
              <ExampleBox label={t("exampleLabel")}>
                <MiniBar label="Standard"  pct={74} color="emerald" />
                <MiniBar label="Marginal"  pct={16} color="amber"   />
                <MiniBar label="Small Err" pct={7}  color="orange"  />
                <MiniBar label="Clear Err" pct={3}  color="destructive" />
                <p className="text-xs text-muted-foreground">{t("decisions.example")}</p>
              </ExampleBox>
            </Section>

            {/* Performance by Street */}
            <Section id="streets" title={t("streets.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("streets.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("streets.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("streets.p3") }} />
              <ExampleBox label={t("exampleLabel")}>
                <MiniBar label="Preflop" pct={84} color="emerald" />
                <MiniBar label="Flop"    pct={76} color="emerald" />
                <MiniBar label="Turn"    pct={70} color="amber"   />
                <MiniBar label="River"   pct={63} color="amber"   />
                <p className="text-xs text-muted-foreground">{t("streets.example")}</p>
              </ExampleBox>
            </Section>

            {/* Performance by Position */}
            <Section id="positions" title={t("positions.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("positions.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("positions.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("positions.p3") }} />
              <ExampleBox label={t("exampleLabel")}>
                <MiniBar label="BTN" pct={84} color="emerald" />
                <MiniBar label="CO"  pct={79} color="emerald" />
                <MiniBar label="MP"  pct={73} color="amber"   />
                <MiniBar label="UTG" pct={71} color="amber"   />
                <MiniBar label="BB"  pct={63} color="orange"  />
                <MiniBar label="SB"  pct={60} color="orange"  />
                <p className="text-xs text-muted-foreground">{t("positions.example")}</p>
              </ExampleBox>
            </Section>

            {/* Pressure Collapse */}
            <Section id="pressure" title={t("pressure.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("pressure.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("pressure.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("pressure.p3") }} />
              <Table
                headers={[t("pressure.table.col_term"), t("pressure.table.col_meaning")]}
                rows={[
                  [t("pressure.table.none_term"),   t("pressure.table.none_meaning")],
                  [t("pressure.table.low_term"),    t("pressure.table.low_meaning")],
                  [t("pressure.table.medium_term"), t("pressure.table.medium_meaning")],
                  [t("pressure.table.high_term"),   t("pressure.table.high_meaning")],
                ]}
              />
              <ExampleBox label={t("exampleLabel")}>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-emerald-400">
                      {t("pressure.example_stable_label")}
                    </p>
                    <MiniBar label="No ICM"   pct={79} color="emerald" />
                    <MiniBar label="High ICM" pct={75} color="emerald" />
                    <Badge color="bg-emerald-500/15 text-emerald-400">Δ 4pts</Badge>
                  </div>
                  <div className="space-y-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-destructive">
                      {t("pressure.example_collapse_label")}
                    </p>
                    <MiniBar label="No ICM"   pct={79} color="emerald"     />
                    <MiniBar label="High ICM" pct={61} color="destructive" />
                    <Badge color="bg-destructive/15 text-destructive">Δ 18pts</Badge>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{t("pressure.example")}</p>
              </ExampleBox>
            </Section>

            {/* ICM Pressure */}
            <Section id="icm" title={t("icm.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("icm.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("icm.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("icm.p3") }} />
              <ExampleBox label={t("exampleLabel")}>
                <MiniBar label="No ICM" pct={8}  color="primary"     />
                <MiniBar label="Low"    pct={15}  color="primary"     />
                <MiniBar label="Medium" pct={38}  color="amber"       />
                <MiniBar label="High"   pct={39}  color="destructive" />
                <p className="text-xs text-muted-foreground">{t("icm.example")}</p>
              </ExampleBox>
            </Section>

            {/* Bankroll */}
            <Section id="bankroll" title={t("bankroll.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("bankroll.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("bankroll.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("bankroll.p3") }} />
              <p dangerouslySetInnerHTML={{ __html: t("bankroll.p4") }} />
            </Section>

            {/* My Level */}
            <Section id="level" title={t("level.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("level.p1") }} />
              <p dangerouslySetInnerHTML={{ __html: t("level.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("level.p3") }} />
              <ExampleBox label={t("exampleLabel")}>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center rounded border border-amber-400/30 bg-amber-400/5 px-2 py-1 font-mono text-[10px] font-bold text-amber-400">
                        Grinder
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">1680 ELO</span>
                    </div>
                    <span className="font-mono text-[9px] text-muted-foreground">Regular → 1710</span>
                  </div>
                  <div className="space-y-1">
                    <div className="h-2 rounded-full bg-border overflow-hidden">
                      <div className="h-full rounded-full bg-amber-500" style={{ width: "75%" }} />
                    </div>
                    <p className="font-mono text-[9px] text-muted-foreground">75% {t("level.example_progress")}</p>
                  </div>
                  <div className="rounded-md border border-orange-500/20 bg-orange-500/5 px-3 py-2">
                    <p className="font-mono text-[9px] uppercase tracking-wide text-orange-400 mb-0.5">{t("level.example_blocker")}</p>
                    <p className="text-[11px] text-muted-foreground">river overcall OOP · 31 occ.</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{t("level.example")}</p>
              </ExampleBox>
            </Section>

            {/* Ghost Table */}
            <Section id="ghost" title={t("ghost.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("ghost.p1") }} />
              <p>{t("ghost.p2")}</p>
              <Table
                headers={[t("ghost.col_result"), t("ghost.col_next")]}
                rows={[
                  [t("ghost.result_hit"),     t("ghost.hit_next")],
                  [t("ghost.result_miss"),    t("ghost.miss_next")],
                  [t("ghost.result_mastery"), t("ghost.mastery_next")],
                ]}
              />
              <p>{t("ghost.p3")}</p>
              <p dangerouslySetInnerHTML={{ __html: t("ghost.p4") }} />
              <p dangerouslySetInnerHTML={{ __html: t("ghost.p5") }} />
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
                  ["Baseline",            t("coaching.baseline_meaning")],
                  ["Baseline Delta",      t("coaching.delta_meaning")],
                  ["Coach Reviewed",      t("coaching.reviewed_meaning")],
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
                  [t("gamification.event_import"),    "50 XP"],
                  [t("gamification.event_exercise"),  "10 XP"],
                  [t("gamification.event_drill"),     "25 XP"],
                  [t("gamification.event_mastery"),  "100 XP"],
                ]}
              />
              <p className="mt-2">{t("gamification.levels_title")}</p>
              <Table
                headers={[t("gamification.col_level"), t("gamification.col_req")]}
                rows={[
                  [t("gamification.level_beginner"), "< 1570"],
                  [t("gamification.level_student"),  "1570 – 1646"],
                  [t("gamification.level_grinder"),  "1647 – 1709"],
                  [t("gamification.level_regular"),  "1710 – 1815"],
                  [t("gamification.level_solid"),    "1816 – 1923"],
                  [t("gamification.level_expert"),   "1924 – 2052"],
                  [t("gamification.level_elite"),    "≥ 2053"],
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
                <li>🏅 {t("gamification.ach_top10")}</li>
                <li>🥉 {t("gamification.ach_top3")}</li>
                <li>👑 {t("gamification.ach_first_place")}</li>
                <li>📈 {t("gamification.ach_climber")}</li>
                <li>♠ {t("gamification.ach_expert")}</li>
              </ul>
            </Section>

            {/* Ranking de Alunos (#15) */}
            <Section id="ranking" title={t("ranking.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("ranking.p1") }} />

              <p><strong className="text-foreground">{t("ranking.privacy_title")}</strong></p>
              <p dangerouslySetInnerHTML={{ __html: t("ranking.privacy") }} />

              <p><strong className="text-foreground">{t("ranking.position_title")}</strong></p>
              <p dangerouslySetInnerHTML={{ __html: t("ranking.position") }} />

              <p><strong className="text-foreground">{t("ranking.hof_title")}</strong></p>
              <p>{t("ranking.hof")}</p>

              <p><strong className="text-foreground">{t("ranking.coach_title")}</strong></p>
              <p>{t("ranking.coach")}</p>

              <p className="text-xs text-muted-foreground">{t("ranking.note")}</p>
            </Section>

            {/* Career Trajectory */}
            <Section id="career" title={t("career.title")}>
              <p dangerouslySetInnerHTML={{ __html: t("career.p1") }} />
              <Table
                headers={[t("career.table.col_term"), t("career.table.col_meaning")]}
                rows={[
                  [t("career.table.slope_term"),    t("career.table.slope_meaning")],
                  [t("career.table.milestone_term"), t("career.table.milestone_meaning")],
                  [t("career.table.blocking_term"), t("career.table.blocking_meaning")],
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
                  [<Badge color="bg-orange-500/15 text-orange-400">{t("cognitive.patterns.fear")}</Badge>,           t("cognitive.patterns.fear_trigger"),         t("cognitive.patterns.fear_signal")],
                  [<Badge color="bg-yellow-500/15 text-yellow-400">{t("cognitive.patterns.sunk")}</Badge>,           t("cognitive.patterns.sunk_trigger"),         t("cognitive.patterns.sunk_signal")],
                  [<Badge color="bg-orange-500/15 text-orange-400">{t("cognitive.patterns.entitlement")}</Badge>,   t("cognitive.patterns.entitlement_trigger"),  t("cognitive.patterns.entitlement_signal")],
                  [<Badge color="bg-yellow-500/15 text-yellow-400">{t("cognitive.patterns.compensation")}</Badge>,  t("cognitive.patterns.compensation_trigger"), t("cognitive.patterns.compensation_signal")],
                  [<Badge color="bg-destructive/15 text-destructive">{t("cognitive.patterns.icm")}</Badge>,         t("cognitive.patterns.icm_trigger"),          t("cognitive.patterns.icm_signal")],
                ]}
              />
              <p dangerouslySetInnerHTML={{ __html: t("cognitive.p2") }} />
              <p dangerouslySetInnerHTML={{ __html: t("cognitive.p3") }} />
            </Section>

            {/* Strategic Patterns */}
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
                  [t("sparring.phase_playing"),  t("sparring.phase_playing_desc")],
                  [t("sparring.phase_feedback"), t("sparring.phase_feedback_desc")],
                  [t("sparring.phase_summary"),  t("sparring.phase_summary_desc")],
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
