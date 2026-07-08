import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CheckCircle2,
  LayoutGrid,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { RangePanel } from "@/components/replayer/RangePanel";
import {
  LessonSection, Prose, Callout, LessonTable, Objectives, PlayerCompare,
  Mistakes, Checklist, Glossary, GrindLabDetects, Takeaways,
} from "@/components/academy/LessonKit";
import { gtoPreflop } from "@/lib/api";
import type { GtoPreflopQuestion, GtoPreflopVerdict, ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";

type Phase = "loading" | "question" | "feedback" | "error";
type Scenario = "mixed" | "rfi" | "vs_rfi" | "vs_3bet";

// Ordem de ação preflop 9-max (early → late). Seats 1..9 nesta ordem.
const ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

const FREQ_LABEL: Record<string, string> = {
  raise: "raise", call: "call", allin: "all-in", fold: "fold",
};
const FREQ_COLOR: Record<string, string> = {
  raise: "bg-emerald-500", call: "bg-sky-500", allin: "bg-violet-500", fold: "bg-muted-foreground/40",
};

/** Monta um ReplayStep 9-max sintético a partir do spot da questão. */
function buildPreflopStep(q: GtoPreflopQuestion) {
  const bb = 100;
  const sp = q.spot;
  const heroPos = sp.position;
  const vsPos = sp.vs_position;
  const scen = sp.scenario;
  const heroIdx = ORDER.indexOf(heroPos);
  const vsIdx = vsPos ? ORDER.indexOf(vsPos) : -1;
  const stackChips = Math.round((sp.stack_bb || 50) * bb);

  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets: Record<string, number> = {};
  const folded: string[] = [];

  ORDER.forEach((pos, i) => {
    const sn = String(i + 1);
    const isHero = pos === heroPos;
    const player = isHero ? "Hero" : pos;
    seats[sn] = { player, stack: stackChips, pos };

    if (pos === "SB") bets[sn] = Math.round(bb * 0.5);
    else if (pos === "BB") bets[sn] = bb;

    let isFolded = false;
    if (scen === "rfi") isFolded = i < heroIdx;                       // foldou até o hero
    else if (scen === "vs_rfi") isFolded = i < heroIdx && pos !== vsPos; // só o opener segue
    else isFolded = !isHero && pos !== vsPos;                          // vs_3bet: hero vs 3-bettor
    if (isFolded) folded.push(player);
  });

  // Apostas de raise/3-bet por cenário
  if (scen === "vs_rfi" && vsIdx >= 0) {
    bets[String(vsIdx + 1)] = Math.round((sp.facing_size || 2.2) * bb);
  } else if (scen === "vs_3bet") {
    if (heroIdx >= 0) bets[String(heroIdx + 1)] = Math.round(2.2 * bb);          // open do hero
    if (vsIdx >= 0) bets[String(vsIdx + 1)] = Math.round((sp.facing_size || 8) * bb); // 3-bet do vilão
  }

  const potChips = Object.values(bets).reduce((a, b) => a + b, 0);
  const step = {
    type: "action", street: "preflop",
    seats, bets, folded,
    pot_bb: potChips / bb, pot: potChips, bb,
    button: ORDER.indexOf("BTN") + 1,
    board: [],
    player: "Hero", seat: heroIdx + 1, is_hero: true,
    // Dica de cenário para a tabela de ranges abrir na aba certa (sem banner GTO).
    preflop_gto: { available: false, scenario: scen, vs_position: vsPos || null },
  } as unknown as ReplayStep;

  const heroCards = q.hero_cards.map((c) => `${c.rank}${c.suit}`);
  return { step, heroCards, bb };
}

export default function AcademyGtoPreflop() {
  const { t } = useTranslation("academy");
  const L = (k: string) => t(`lessons.ranges.${k}`);
  const [params] = useSearchParams();
  const scenario = ((params.get("scenario") as Scenario) || "mixed");

  const [phase, setPhase]               = useState<Phase>("loading");
  const [question, setQuestion]         = useState<GtoPreflopQuestion | null>(null);
  const [verdict, setVerdict]           = useState<GtoPreflopVerdict | null>(null);
  const [selected, setSelected]         = useState<string | null>(null);
  const [submitting, setSubmitting]     = useState(false);
  const [showRange, setShowRange]       = useState(false);
  const [streak, setStreak]             = useState(0);
  const [totalDone, setTotalDone]       = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);

  const loadQuestion = useCallback(async () => {
    setPhase("loading");
    setSelected(null);
    setVerdict(null);
    setShowRange(false);
    try {
      const timeout = new Promise<never>((_, rej) =>
        setTimeout(() => rej(new Error("timeout")), 12000)
      );
      const q = await Promise.race([gtoPreflop.question(scenario), timeout]);
      setQuestion(q);
      setPhase("question");
    } catch {
      setPhase("error");
    }
  }, [scenario]);

  useEffect(() => { loadQuestion(); }, [loadQuestion]);

  const submitAnswer = async (action: string) => {
    if (!question || phase !== "question" || submitting) return;
    setSelected(action);
    setSubmitting(true);
    try {
      const v = await gtoPreflop.submit(question.spot, action, question.xp_value);
      setVerdict(v);
      setTotalDone((n) => n + 1);
      if (v.is_correct) {
        setStreak((s) => s + 1);
        setTotalCorrect((n) => n + 1);
      } else {
        setStreak(0);
      }
      setPhase("feedback");
    } catch {
      setPhase("error");
    } finally {
      setSubmitting(false);
    }
  };

  const accuracy = totalDone > 0 ? Math.round((totalCorrect / totalDone) * 100) : null;
  const table = question ? buildPreflopStep(question) : null;
  const freqEntries = verdict
    ? Object.entries(verdict.hand_freq || {}).filter(([, v]) => v && v > 0.01).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <HudLayout
      eyebrow={t("gtoPreflop.eyebrow")}
      title={t("gtoPreflop.title")}
      description={t("gtoPreflop.subtitle")}
    >
      {/* Aula prependada (só no cenário RFI / módulo "ranges" iniciante) */}
      {scenario === "rfi" && (
        <article className="mx-auto max-w-2xl space-y-12 pb-10">
          <LessonSection n={1} title={L("intro_title")}>
            <Prose html={L("intro_p1")} />
            <Prose html={L("intro_p2")} />
            <Callout tone="note" title={L("intro_note_title")}>{L("intro_note")}</Callout>
          </LessonSection>

          <Objectives title={L("obj_title")} items={[L("obj1"), L("obj2"), L("obj3"), L("obj4")]} />

          <LessonSection n={2} title={L("fund_title")}>
            <Prose html={L("fund_p1")} />
            <Prose html={L("fund_p2")} />
          </LessonSection>

          <LessonSection n={3} title={L("c1_title")}>
            <Prose html={L("c1_p1")} />
            <Callout tone="key" title={L("c1_key_title")}>{L("c1_key")}</Callout>
          </LessonSection>

          <LessonSection n={4} title={L("c2_title")}>
            <Prose html={L("c2_p1")} />
            <Callout tone="tip" title={L("c2_tip_title")}>{L("c2_tip")}</Callout>
          </LessonSection>

          <LessonSection n={5} title={L("c3_title")}>
            <Prose html={L("c3_p1")} />
            <Callout tone="coach" title={L("c3_coach_title")}>{L("c3_coach")}</Callout>
          </LessonSection>

          <LessonSection n={6} title={L("c4_title")}>
            <Prose html={L("c4_p1")} />
            <LessonTable
              headers={[L("tbl_h1"), L("tbl_h2")]}
              rows={[
                [L("tbl_r1_a"), L("tbl_r1_b")],
                [L("tbl_r2_a"), L("tbl_r2_b")],
                [L("tbl_r3_a"), L("tbl_r3_b")],
                [L("tbl_r4_a"), L("tbl_r4_b")],
              ]}
            />
          </LessonSection>

          <LessonSection n={7} title={L("ex_title")}>
            <Prose html={L("ex_p1")} />
            <Prose html={L("ex_p2")} />
          </LessonSection>

          <PlayerCompare
            title={L("cmp_title")}
            cols={[L("cmp_col_rec"), L("cmp_col_reg"), L("cmp_col_pro")]}
            rows={[
              { label: L("cmp_r1"), rec: L("cmp_r1_rec"), reg: L("cmp_r1_reg"), pro: L("cmp_r1_pro") },
              { label: L("cmp_r2"), rec: L("cmp_r2_rec"), reg: L("cmp_r2_reg"), pro: L("cmp_r2_pro") },
              { label: L("cmp_r3"), rec: L("cmp_r3_rec"), reg: L("cmp_r3_reg"), pro: L("cmp_r3_pro") },
            ]}
          />

          <Mistakes
            title={L("err_title")}
            items={[
              { mistake: L("e1_m"), why: L("e1_why"), fix: L("e1_fix") },
              { mistake: L("e2_m"), why: L("e2_why"), fix: L("e2_fix") },
              { mistake: L("e3_m"), why: L("e3_why"), fix: L("e3_fix") },
              { mistake: L("e4_m"), why: L("e4_why"), fix: L("e4_fix") },
              { mistake: L("e5_m"), why: L("e5_why"), fix: L("e5_fix") },
              { mistake: L("e6_m"), why: L("e6_why"), fix: L("e6_fix") },
            ]}
          />

          <Checklist title={L("chk_title")} items={[L("chk1"), L("chk2"), L("chk3"), L("chk4"), L("chk5")]} />

          <Takeaways title={L("takeaways_title")} items={[L("t1"), L("t2"), L("t3"), L("t4")]} />

          <Glossary
            title={L("glo_title")}
            terms={[
              { term: L("g1_term"), def: L("g1_def") },
              { term: L("g2_term"), def: L("g2_def") },
              { term: L("g3_term"), def: L("g3_def") },
              { term: L("g4_term"), def: L("g4_def") },
              { term: L("g5_term"), def: L("g5_def") },
              { term: L("g6_term"), def: L("g6_def") },
            ]}
          />

          <GrindLabDetects
            title={L("gl_title")}
            intro={L("gl_intro")}
            items={[L("gl1"), L("gl2"), L("gl3"), L("gl4"), L("gl5")]}
          />

          <Callout tone="key" title={L("practice_note_title")}>{L("practice_note")}</Callout>
        </article>
      )}

      <div className="mx-auto w-full max-w-[1500px] space-y-4">

        {/* Loading (initial) */}
        {phase === "loading" && (
          <div className="flex flex-col items-center gap-4 py-16">
            <Loader2 className="size-8 animate-spin text-amber-400" aria-hidden />
            <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest">{t("loading")}</p>
          </div>
        )}

        {/* Error */}
        {phase === "error" && (
          <div className="flex flex-col items-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8">
            <XCircle className="size-10 text-destructive" aria-hidden />
            <p className="text-sm text-muted-foreground">{t("loadError")}</p>
            <button
              onClick={loadQuestion}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-hud-surface px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground hover:bg-amber-500/5 transition-colors"
            >
              <RefreshCw className="size-3.5" aria-hidden />
              {t("retry")}
            </button>
          </div>
        )}

        {/* Table (left) + decision/verdict (right) */}
        {(phase === "question" || phase === "feedback") && question && table && (
          <div className="flex flex-col lg:flex-row gap-4 items-stretch">

            {/* Table column */}
            <div className="flex-1 min-w-0">
              <div className="w-full aspect-[16/10]">
                <PokerTableV3 step={table.step} hero="Hero" heroCards={table.heroCards} bb={table.bb} betUnit="bb" />
              </div>
            </div>

            {/* Side panel */}
            <aside className="w-full lg:w-72 shrink-0 flex flex-col gap-3">

              {/* Stats */}
              {totalDone > 0 && (
                <div className="flex items-center justify-around rounded-lg border border-border bg-hud-surface px-3 py-2">
                  <div className="text-center">
                    <p className="font-mono text-base font-bold tabular-nums text-foreground">{totalDone}</p>
                    <p className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{t("stats.done")}</p>
                  </div>
                  <div className="h-6 w-px bg-border" />
                  <div className="text-center">
                    <p className={cn("font-mono text-base font-bold tabular-nums", accuracy !== null && accuracy >= 70 ? "text-emerald-400" : "text-amber-400")}>{accuracy}%</p>
                    <p className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{t("stats.accuracy")}</p>
                  </div>
                  <div className="h-6 w-px bg-border" />
                  <div className="text-center">
                    <p className={cn("font-mono text-base font-bold tabular-nums", streak >= 3 ? "text-amber-400" : "text-foreground")}>{streak}🔥</p>
                    <p className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{t("stats.streak")}</p>
                  </div>
                </div>
              )}

              {/* Scenario + context */}
              <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 space-y-1.5">
                <span className="font-mono text-[10px] uppercase tracking-widest text-amber-400">
                  {t(`qtypes.${question.type}`, question.type)}
                </span>
                <p className="text-sm text-foreground leading-relaxed">{question.context}</p>
              </div>

              {/* Consultar tabela de ranges */}
              <button
                onClick={() => setShowRange(true)}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
              >
                <LayoutGrid className="size-3.5" aria-hidden />
                {t("gtoPreflop.showRange")}
              </button>

              {/* Decision (question phase) */}
              {phase === "question" && (
                <div className="space-y-2">
                  <p className="font-mono text-xs uppercase tracking-wider text-amber-400">{question.prompt}</p>
                  <div className="grid grid-cols-1 gap-2">
                    {question.options.map((opt) => (
                      <button
                        key={opt.action}
                        onClick={() => submitAnswer(opt.action)}
                        disabled={submitting}
                        className={cn(
                          "min-h-[48px] rounded-lg border px-4 py-3 text-left font-mono text-sm font-bold uppercase tracking-wider transition-all active:scale-95",
                          "border-border bg-hud-surface text-foreground ring-1 ring-border hover:border-amber-500/60 hover:bg-amber-500/5 hover:text-amber-400",
                          "disabled:opacity-40 disabled:cursor-not-allowed",
                          submitting && selected === opt.action && "border-amber-500/60 bg-amber-500/5 text-amber-400",
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Verdict (feedback phase) */}
              {phase === "feedback" && verdict && (
                <div className="flex flex-col gap-3">
                  <div className={cn(
                    "rounded-xl border p-4 space-y-3",
                    verdict.is_correct ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5",
                  )}>
                    <div className="flex items-center gap-2">
                      {verdict.is_correct
                        ? <CheckCircle2 className="size-5 text-emerald-400 shrink-0" aria-hidden />
                        : <XCircle className="size-5 text-amber-400 shrink-0" aria-hidden />}
                      <span className={cn("font-mono text-xs font-bold uppercase tracking-wider",
                        verdict.is_correct ? "text-emerald-400" : "text-amber-400")}>
                        {verdict.is_correct ? t("feedback.correct") : t("feedback.wrong")}
                      </span>
                      {verdict.xp_awarded > 0 && (
                        <span className="ml-auto font-mono text-[10px] text-emerald-400">+{verdict.xp_awarded} XP</span>
                      )}
                    </div>

                    {/* Frequências GTO da mão */}
                    {freqEntries.length > 0 && (
                      <div className="space-y-1.5">
                        {freqEntries.map(([act, freq]) => (
                          <div key={act} className="flex items-center gap-2">
                            <span className="font-mono text-[10px] text-muted-foreground w-10 shrink-0">{FREQ_LABEL[act] ?? act}</span>
                            <div className="relative flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                              <div className={cn("h-full rounded-full", FREQ_COLOR[act] ?? "bg-primary")} style={{ width: `${Math.min(100, freq * 100)}%` }} />
                            </div>
                            <span className="font-mono text-[10px] font-bold tabular-nums w-8 text-right text-foreground">{Math.round(freq * 100)}%</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <p className="text-sm text-muted-foreground leading-relaxed">{verdict.explanation}</p>
                  </div>

                  <button
                    onClick={loadQuestion}
                    className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400"
                  >
                    <ArrowRight className="size-4" aria-hidden />
                    {t("nextQuestion")}
                  </button>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>

      {/* Range table overlay (consulta) */}
      {showRange && table && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowRange(false)}
        >
          <div
            className="w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <RangePanel step={table.step} hero="Hero" heroCards={table.heroCards} onClose={() => setShowRange(false)} />
          </div>
        </div>
      )}
    </HudLayout>
  );
}
