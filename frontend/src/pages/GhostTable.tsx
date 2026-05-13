import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Flame,
  Loader2,
  ShieldAlert,
  Swords,
  Target,
  Timer,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
import { AiText } from "@/components/ui/AiText";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { drill } from "@/lib/api";
import type { DrillSpot, DrillStats, DrillSubmitResult, ReplayStep } from "@/lib/api";
import { cn, formatAction } from "@/lib/utils";

type Phase = "intro" | "loading" | "active" | "result" | "done";

const ACTION_KEYS = ["fold", "check", "call", "bet", "raise", "jam"] as const;
const PRESSURE_TIME = 30;

// ── Card parser ───────────────────────────────────────────────────────────────

function parseCards(raw: string | null): CardData[] {
  if (!raw) return [];
  const SUITS = ["s", "h", "d", "c"];

  if (raw.trim().startsWith("[")) {
    try {
      const arr: string[] = JSON.parse(raw);
      return arr.flatMap((t) => parseCards(t));
    } catch { return []; }
  }

  const tokens: string[] = [];
  const str = raw.replace(/\s+/g, "");
  let i = 0;
  while (i < str.length) {
    const two   = str.slice(i, i + 2);
    const three = str.slice(i, i + 3);
    if (three.length === 3 && SUITS.includes(three[2].toLowerCase()) && two === "10") {
      tokens.push(three); i += 3;
    } else if (two.length === 2 && SUITS.includes(two[1].toLowerCase())) {
      tokens.push(two); i += 2;
    } else { i++; }
  }

  return tokens.flatMap((token) => {
    const suit = token.slice(-1).toLowerCase() as "s" | "h" | "d" | "c";
    const rank = token.slice(0, -1).toUpperCase();
    if (!SUITS.includes(suit) || !rank) return [];
    return [{ rank, suit }];
  });
}

// ── Situation context ─────────────────────────────────────────────────────────

type SitVariant = "aggression" | "opening" | "neutral";

interface SituationInfo {
  key: string;
  variant: SitVariant;
}

function getSituation(spot: DrillSpot): SituationInfo {
  const facingPassive = ["call", "fold"].includes(spot.action_taken);
  const pos = (spot.position ?? "").toUpperCase();

  if (spot.street === "preflop") {
    if (spot.is_3bet)        return { key: "facing3bet",   variant: "aggression" };
    if (pos === "BB")        return { key: facingPassive ? "defendingBB" : "openBB",    variant: facingPassive ? "aggression" : "opening" };
    if (pos === "SB")        return { key: facingPassive ? "defendingSB" : "completeSB", variant: facingPassive ? "aggression" : "neutral" };
    if (facingPassive)       return { key: "facingRaise",  variant: "aggression" };
    return                          { key: "openingHand",  variant: "opening" };
  }

  if (facingPassive)                                           return { key: "facingBet",   variant: "aggression" };
  if (spot.action_taken === "check")                          return { key: "checkBet",    variant: "neutral" };
  if (["bet", "raise", "jam"].includes(spot.action_taken))   return { key: "betting",     variant: "opening" };
  return                                                             { key: "actingFirst", variant: "neutral" };
}

const SIT_STYLES: Record<SitVariant, { box: string; label: string; icon: typeof ShieldAlert }> = {
  aggression: { box: "border-warning/50 bg-warning/5",   label: "text-warning",   icon: ShieldAlert },
  opening:    { box: "border-primary/50 bg-primary/5",   label: "text-primary",   icon: Zap },
  neutral:    { box: "border-border bg-hud-surface",     label: "text-foreground", icon: Target },
};

// ── Timer ring ────────────────────────────────────────────────────────────────

function TimerRing({ timeLeft, total = PRESSURE_TIME }: { timeLeft: number; total?: number }) {
  const r     = 16;
  const circ  = 2 * Math.PI * r;
  const pct   = Math.max(0, timeLeft) / total;
  const urgent = timeLeft <= 10;
  return (
    <div className="relative size-10 shrink-0">
      <svg width={40} height={40} viewBox="0 0 40 40" style={{ transform: "rotate(-90deg)" }} aria-hidden>
        <circle cx={20} cy={20} r={r} fill="none" stroke="hsl(var(--border))" strokeWidth={2.5} />
        <circle
          cx={20} cy={20} r={r} fill="none"
          stroke={urgent ? "hsl(var(--destructive))" : "hsl(var(--primary))"}
          strokeWidth={2.5}
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - pct)}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s linear, stroke 0.3s" }}
        />
      </svg>
      <span className={cn(
        "absolute inset-0 flex items-center justify-center font-mono text-[10px] font-bold tabular-nums",
        urgent ? "text-destructive" : "text-foreground"
      )}>
        {timeLeft}
      </span>
    </div>
  );
}

// ── Stat tile ─────────────────────────────────────────────────────────────────

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-border bg-hud-surface p-4 text-center">
      <p className="font-mono text-2xl font-bold tabular-nums text-foreground">{value}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
    </div>
  );
}

// ── Drill → ReplayStep adapter ────────────────────────────────────────────────

function buildDrillStep(spot: DrillSpot): { step: ReplayStep; hero: string; heroCards: string[]; bb: number } {
  const HERO = 'Hero';
  const bb   = spot.level_bb ?? 100;
  const heroStack = Math.round((spot.stack_bb ?? 20) * bb);
  const numP = Math.max(2, Math.min(6, spot.num_players ?? 6));
  const heroPos = (spot.position ?? 'BTN').toUpperCase();

  const layouts: Record<number, string[]> = {
    2: ['BTN', 'BB'],
    3: ['BTN', 'SB', 'BB'],
    4: ['CO',  'BTN', 'SB', 'BB'],
    5: ['UTG', 'CO',  'BTN', 'SB', 'BB'],
    6: ['UTG', 'HJ',  'CO',  'BTN', 'SB', 'BB'],
  };
  const positions = layouts[numP] ?? layouts[6];
  const btnSeat   = positions.indexOf('BTN') + 1;

  let heroSeatIdx = positions.indexOf(heroPos);
  if (heroSeatIdx < 0) heroSeatIdx = positions.indexOf('BTN');
  const heroSeatNum = heroSeatIdx + 1;

  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets:  Record<string, number> = {};

  positions.forEach((pos, i) => {
    const sn    = String(i + 1);
    const isHero = (i + 1) === heroSeatNum;
    seats[sn] = { player: isHero ? HERO : `V${i + 1}`, stack: heroStack, pos };
    if (pos === 'SB') bets[sn] = Math.round(bb * 0.5);
    else if (pos === 'BB') bets[sn] = bb;
  });

  // Facing bet → assign to villain seat immediately before hero
  if (spot.facing_bet && spot.facing_bet > 0) {
    const facingChips = Math.round(spot.facing_bet * bb);
    let agSeat = heroSeatNum - 1;
    if (agSeat < 1) agSeat = numP;
    if (agSeat !== heroSeatNum) bets[String(agSeat)] = facingChips;
  }

  const boardLimit = ({ preflop: 0, flop: 3, turn: 4, river: 5 } as Record<string, number>)[spot.street ?? 'preflop'] ?? 0;
  const boardRaw: string[] = (() => {
    if (!spot.board) return [];
    const s = spot.board.trim();
    if (s.startsWith('[')) { try { return JSON.parse(s) as string[]; } catch { return []; } }
    return s.split(/\s+/).filter(Boolean);
  })();
  const board     = boardRaw.slice(0, boardLimit);
  const heroCards = spot.hero_cards
    ? (spot.hero_cards.trim().startsWith('[')
        ? (() => { try { return JSON.parse(spot.hero_cards!) as string[]; } catch { return []; } })()
        : (spot.hero_cards.match(/[2-9TJQKAakqjt][shdcSHDC]/g) ?? []))
    : [];
  const potChips   = Math.round((spot.pot_size ?? 2) * bb);

  const step = {
    type: 'action', street: spot.street ?? 'preflop',
    seats, bets, folded: [] as string[],
    pot_bb: spot.pot_size ?? 2, pot: potChips,
    bb, button: btnSeat, board,
    player: HERO, seat: heroSeatNum, is_hero: true,
  } as unknown as ReplayStep;

  return { step, hero: HERO, heroCards, bb };
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function GhostTable() {
  const { t } = useTranslation("ghost");

  const [phase, setPhase]                   = useState<Phase>("intro");
  const [spots, setSpots]                   = useState<DrillSpot[]>([]);
  const [stats, setStats]                   = useState<DrillStats | null>(null);
  const [index, setIndex]                   = useState(0);
  const [lastResult, setLastResult]         = useState<DrillSubmitResult | null>(null);
  const [sessionCorrect, setSessionCorrect] = useState(0);
  const [sessionTotal, setSessionTotal]     = useState(0);
  const [loadError, setLoadError]           = useState("");
  const [submitting, setSubmitting]         = useState(false);
  const [analysis, setAnalysis]             = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // ── Pressure mode state ───────────────────────────────────────────────────
  const [pressureMode, setPressureMode] = useState(false);
  const [timeLeft, setTimeLeft]         = useState(PRESSURE_TIME);
  const [streak, setStreak]             = useState(0);
  const [timedOut, setTimedOut]         = useState(false);
  // Keep a ref to submitAction so the timer interval can call it without stale closure
  const submitRef = useRef<((action: string) => Promise<void>) | null>(null);

  const current = spots[index] ?? null;

  const submitAction = useCallback(async (action: string) => {
    if (!current || submitting) return;
    setSubmitting(true);
    setTimedOut(false);
    try {
      const result = await drill.submit(current.id, action);
      if (result.is_correct) {
        setSessionCorrect((c) => c + 1);
        setStreak((s) => s + 1);
      } else {
        setStreak(0);
      }
      setSessionTotal((n) => n + 1);
      setLastResult(result);
      setPhase("result");
    } catch {
      // keep active on error
    } finally {
      setSubmitting(false);
    }
  }, [current, submitting]);

  // Always keep submitRef in sync with the latest submitAction
  useEffect(() => { submitRef.current = submitAction; });

  // ── Timer effect: start/reset when active+pressure, index changes ─────────
  useEffect(() => {
    if (!pressureMode || phase !== "active") return;
    setTimeLeft(PRESSURE_TIME);
    setTimedOut(false);
    const id = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(id);
          setTimedOut(true);
          // Delay slightly so React processes the state update first
          setTimeout(() => submitRef.current?.("fold"), 50);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [phase, index, pressureMode]);

  const startDrill = async () => {
    setPhase("loading");
    setLoadError("");
    setStreak(0);
    try {
      const data = await drill.spots({ limit: 10 });
      setStats(data.stats);
      if (!data.spots.length) { setPhase("intro"); return; }
      setSpots(data.spots);
      setIndex(0);
      setSessionCorrect(0);
      setSessionTotal(0);
      setLastResult(null);
      setPhase("active");
    } catch (err) {
      console.error("[GhostTable] startDrill error:", err);
      setLoadError(t("errorLoad"));
      setPhase("intro");
    }
  };

  const nextSpot = () => {
    const next = index + 1;
    setAnalysis(null);
    if (next >= spots.length) { setPhase("done"); }
    else { setIndex(next); setLastResult(null); setPhase("active"); }
  };

  const requestAnalysis = async () => {
    if (!current || analysisLoading) return;
    setAnalysisLoading(true);
    try {
      const res = await drill.analysis(current.id);
      setAnalysis(res.analysis);
    } catch {
      setAnalysis(t("result.analysisError"));
    } finally {
      setAnalysisLoading(false);
    }
  };

  const resetDrill = () => {
    setPhase("intro"); setSpots([]); setIndex(0);
    setLastResult(null); setSessionCorrect(0); setSessionTotal(0);
    setAnalysis(null); setStreak(0); setTimedOut(false);
  };

  const accuracy = sessionTotal > 0 ? Math.round((sessionCorrect / sessionTotal) * 100) : 0;

  // ── Full-screen layout: active + result ─────────────────────────────────────
  if (current && (phase === "active" || (phase === "result" && lastResult))) {
    const sit    = getSituation(current);
    const style  = SIT_STYLES[sit.variant];
    const SitIcon = style.icon;
    const { step: drillStep, hero: drillHero, heroCards: drillCards, bb: drillBb } = buildDrillStep(current);
    if (phase === "result") (drillStep as unknown as Record<string, unknown>).seat = undefined;

    const progressBar = (
      <div className="flex items-center gap-3 shrink-0">
        <span className="font-mono text-xs text-muted-foreground shrink-0">{t("spot", { n: index + 1, total: spots.length })}</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
          <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${((index + 1) / spots.length) * 100}%` }} />
        </div>
        {current.days_overdue != null && current.days_overdue > 0 && (
          <span className={cn("flex items-center gap-1 font-mono text-[10px] shrink-0", current.days_overdue > 7 ? "text-destructive" : "text-warning")}>
            <Clock className="size-3" aria-hidden />{current.days_overdue}d
          </span>
        )}
        {pressureMode && streak > 0 && (
          <span className="flex items-center gap-1 font-mono text-[10px] font-bold text-amber-400 shrink-0">
            <Flame className="size-3" aria-hidden />{streak}
          </span>
        )}
        <span className="font-mono text-xs text-muted-foreground shrink-0">{sessionCorrect}/{sessionTotal}</span>
        {pressureMode && <TimerRing timeLeft={timeLeft} />}
      </div>
    );

    const sitStrip = (
      <div className={cn("flex items-center gap-x-3 gap-y-1 flex-wrap rounded-lg border px-3 py-2 shrink-0", style.box)}>
        <div className="flex items-center gap-1.5 shrink-0">
          <SitIcon className={cn("size-3.5", style.label)} aria-hidden />
          <span className={cn("font-mono text-[10px] font-bold uppercase tracking-wide", style.label)}>{t(`situation.${sit.key}`)}</span>
        </div>
        <div className="flex items-center gap-x-3 gap-y-0.5 flex-wrap font-mono text-[10px] text-muted-foreground">
          <span className="font-semibold text-foreground">{t(`street.${current.street}`)}</span>
          {current.position    && <span>{current.position}</span>}
          {current.stack_bb != null && <span>Stack: <span className="text-foreground font-semibold">{current.stack_bb.toFixed(0)}bb</span></span>}
          {current.m_ratio   != null && <span>M: <span className="text-foreground">{current.m_ratio.toFixed(1)}</span></span>}
          {current.pot_size  != null && current.pot_size  > 0 && <span>Pot: <span className="text-foreground">{current.pot_size.toFixed(1)}bb</span></span>}
          {current.facing_bet != null && current.facing_bet > 0 && (
            <span className={sit.variant === "aggression" ? "text-warning font-semibold" : ""}>
              Facing: <span className="font-semibold">{current.facing_bet.toFixed(1)}bb</span>
            </span>
          )}
          {!!current.is_3bet && <span className="font-semibold text-warning">{t("context.is3bet")}</span>}
          {current.icm_pressure && current.icm_pressure !== "none" && (
            <span className={cn({ "text-destructive font-semibold": current.icm_pressure === "high", "text-warning font-semibold": current.icm_pressure === "medium", "text-primary font-semibold": current.icm_pressure === "low" })}>
              ICM {t(`icmLabel.${current.icm_pressure}`)}
            </span>
          )}
        </div>
      </div>
    );

    return (
      <div className="h-dvh flex flex-col overflow-hidden bg-background hud-scanline">
        <HudHeader />

        {/* Identity bar */}
        <div className="shrink-0 border-b border-border/30 px-3 md:px-5 py-1.5 flex items-center gap-3">
          <Link to="/training" className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors">
            <ChevronLeft className="size-3.5" />
            <span className="font-mono text-[10px] uppercase tracking-wide">{t("backToTraining")}</span>
          </Link>
          <div className="flex items-center gap-1.5">
            <Swords className="size-3 text-primary" aria-hidden />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-primary">Ghost Table</span>
          </div>
          {pressureMode && streak > 0 && (
            <div className="flex items-center gap-1 ml-auto">
              <Flame className="size-3 text-amber-400" aria-hidden />
              <span className="font-mono text-[10px] font-bold text-amber-400">{streak}</span>
            </div>
          )}
        </div>

        <div className="flex-1 min-h-0 flex gap-3 px-3 md:px-5 pt-1 pb-3 mx-auto w-full max-w-[1600px]">

          {/* Table column */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col gap-2">
            <div className="lg:hidden">{progressBar}</div>
            {/* Table — pt-10 gives room for top-player cards that overflow above SVG viewBox */}
            <div className="flex-1 min-h-0 overflow-visible pt-10">
              <div className="mx-auto aspect-[16/10] max-w-[90%]" style={{ maxHeight: 'calc(100% - 2.5rem)' }}>
                <PokerTableV3 step={drillStep} hero={drillHero} heroCards={drillCards} bb={drillBb} betUnit="bb" />
              </div>
            </div>
            {/* Mobile: actions/next below table */}
            <div className="lg:hidden shrink-0 space-y-2">
              {phase === "active" && (
                <>
                  {timedOut && (
                    <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
                      <Timer className="size-3.5 text-destructive shrink-0" /><span className="font-mono text-xs font-semibold text-destructive">{t("pressure.timedOut")}</span>
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-2">
                    {ACTION_KEYS.map(action => (
                      <button key={action} onClick={() => submitAction(action)} disabled={submitting || timedOut}
                        className="min-h-[40px] rounded-lg border border-border bg-hud-surface px-2 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-primary/60 hover:bg-primary/5 hover:text-primary disabled:opacity-60 transition-all active:scale-95">
                        {t(`actions.${action}`)}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {phase === "result" && lastResult && (
                <button onClick={nextSpot} className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors">
                  {t("next")} <ArrowRight className="size-4" aria-hidden />
                </button>
              )}
            </div>
          </div>

          {/* Side panel — desktop only */}
          <aside className="hidden lg:flex w-64 shrink-0 flex-col gap-3 overflow-y-auto pb-2">
            {progressBar}
            {sitStrip}
            <p className="font-mono text-[10px] text-muted-foreground shrink-0">
              {t("result.originalMistake", { action: formatAction(current.action_taken).toUpperCase(), score: current.score.toFixed(2) })}
            </p>

            {/* Active: action buttons */}
            {phase === "active" && (
              <>
                {timedOut && (
                  <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 shrink-0">
                    <Timer className="size-3.5 text-destructive shrink-0" /><span className="font-mono text-xs font-semibold text-destructive">{t("pressure.timedOut")}</span>
                  </div>
                )}
                <p className="text-center text-sm font-semibold text-foreground shrink-0">{t("question")}</p>
                <div className="grid grid-cols-2 gap-2 shrink-0">
                  {ACTION_KEYS.map(action => (
                    <button key={action} onClick={() => submitAction(action)} disabled={submitting || timedOut}
                      className="min-h-[44px] rounded-lg border border-border bg-hud-surface px-3 py-3 font-mono text-xs font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-primary/60 hover:bg-primary/5 hover:text-primary hover:ring-primary/40 disabled:opacity-60 transition-all active:scale-95">
                      {t(`actions.${action}`)}
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* Result: outcome panel */}
            {phase === "result" && lastResult && (
              <div className="flex flex-col gap-3 min-h-0 overflow-y-auto">
                <div className={cn("flex items-center gap-3 rounded-xl border p-4 shrink-0", lastResult.is_correct ? "border-success/40 bg-success/5" : "border-destructive/40 bg-destructive/5")}>
                  {lastResult.is_correct ? <CheckCircle2 className="size-8 shrink-0 text-success" aria-hidden /> : <XCircle className="size-8 shrink-0 text-destructive" aria-hidden />}
                  <div className="flex-1 min-w-0">
                    <p className={cn("font-bold", lastResult.is_correct ? "text-success" : "text-destructive")}>
                      {lastResult.is_correct ? t("result.correct") : t("result.wrong")}
                    </p>
                    <p className="text-xs text-muted-foreground">{t("result.bestAction", { action: formatAction(lastResult.best_action).toUpperCase() })}</p>
                  </div>
                  {pressureMode && streak > 0 && (
                    <div className="flex items-center gap-1 font-mono text-sm font-bold text-amber-400 shrink-0">
                      <Flame className="size-4" aria-hidden />{streak}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 shrink-0">
                  <div className="rounded-lg border border-border bg-hud-surface p-3">
                    <p className="font-mono text-[9px] uppercase text-muted-foreground">{t("result.yourAction", { action: "" }).split(":")[0]}</p>
                    <p className="mt-1 font-mono text-lg font-bold text-foreground">{formatAction(lastResult.new_action).toUpperCase()}</p>
                  </div>
                  <div className="rounded-lg border border-border bg-hud-surface p-3">
                    <p className="font-mono text-[9px] uppercase text-muted-foreground">{t("result.bestAction", { action: "" }).split(":")[0]}</p>
                    <p className="mt-1 font-mono text-lg font-bold text-foreground">{formatAction(lastResult.best_action).toUpperCase()}</p>
                  </div>
                </div>

                <div className={cn("flex items-center justify-between rounded-lg border p-3 shrink-0", lastResult.delta < 0 ? "border-success/30 bg-success/5" : "border-border bg-hud-surface")}>
                  <div className="flex items-center gap-1.5">
                    <TrendingUp className="size-3.5 text-muted-foreground" aria-hidden />
                    <span className="text-xs text-muted-foreground">{lastResult.delta < 0 ? t("result.improvement", { delta: Math.abs(lastResult.delta).toFixed(3) }) : t("result.noImprovement")}</span>
                  </div>
                  <span className={cn("font-mono text-sm font-bold tabular-nums", lastResult.delta < 0 ? "text-success" : "text-destructive")}>
                    {lastResult.delta > 0 ? "+" : ""}{lastResult.delta.toFixed(3)}
                  </span>
                </div>

                {lastResult.srs_interval_days && (
                  <div className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 shrink-0", lastResult.is_correct ? "border-primary/30 bg-primary/5 text-primary" : "border-warning/30 bg-warning/5 text-warning")}>
                    <Clock className="size-3.5 shrink-0" aria-hidden />
                    <span className="font-mono text-[10px]">
                      {lastResult.is_correct ? `${t("next")} em ${lastResult.srs_interval_days}d` : `Resetado — em ${lastResult.srs_interval_days}d`}
                    </span>
                  </div>
                )}

                {analysis ? (
                  <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-primary">{t("result.engineNote")}</p>
                    <AiText>{analysis}</AiText>
                  </div>
                ) : (
                  <button onClick={requestAnalysis} disabled={analysisLoading}
                    className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-4 py-2.5 font-mono text-xs font-semibold text-muted-foreground hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:opacity-60 transition-colors shrink-0">
                    {analysisLoading ? <><Loader2 className="size-3.5 animate-spin" aria-hidden />{t("result.analysisLoading")}</> : <><BookOpen className="size-3.5" aria-hidden />{t("result.requestAnalysis")}</>}
                  </button>
                )}

                <button onClick={nextSpot}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors shrink-0">
                  {t("next")} <ArrowRight className="size-4" aria-hidden />
                </button>
              </div>
            )}
          </aside>

        </div>
      </div>
    );
  }

  // ── Normal layout: intro / loading / done ─────────────────────────────────
  return (
    <HudLayout eyebrow="Ghost Table" title={t("title")} description={t("subtitle")}>

      {/* ── INTRO / LOADING ──────────────────────────────────────────────────── */}
      {(phase === "intro" || phase === "loading") && (
        <div className="mx-auto max-w-lg space-y-6">
          {stats && (
            <div className="grid grid-cols-3 gap-3">
              <StatTile value={String(stats.total)} label={t("stats.title").replace(/\s*\(.*\)/, "")} />
              <StatTile
                value={stats.accuracy !== null ? `${Math.round(stats.accuracy * 100)}%` : "—"}
                label="Accuracy"
              />
              <StatTile
                value={stats.avg_delta !== null ? (stats.avg_delta > 0 ? `+${stats.avg_delta.toFixed(2)}` : stats.avg_delta.toFixed(2)) : "—"}
                label="Δ avg"
              />
            </div>
          )}
          {stats && stats.total === 0 && !loadError && (
            <p className="rounded-lg border border-border bg-hud-surface p-5 text-center text-sm text-muted-foreground">
              {t("noSpots")}
            </p>
          )}
          {loadError && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center text-sm text-destructive">
              {loadError}
            </p>
          )}

          {/* Pressure mode toggle */}
          <button
            onClick={() => setPressureMode((m) => !m)}
            className={cn(
              "w-full flex items-center justify-between rounded-xl border px-4 py-3 transition-colors",
              pressureMode
                ? "border-destructive/40 bg-destructive/5"
                : "border-border bg-hud-surface hover:border-border/80"
            )}
            type="button"
          >
            <div className="flex items-center gap-2">
              <Timer className={cn("size-4 shrink-0", pressureMode ? "text-destructive" : "text-muted-foreground")} aria-hidden />
              <div className="text-left">
                <p className={cn("font-mono text-xs font-bold uppercase tracking-wider", pressureMode ? "text-destructive" : "text-foreground")}>
                  {t("pressure.toggle")}
                </p>
                <p className="font-mono text-[10px] text-muted-foreground mt-0.5">
                  {t("pressure.desc")}
                </p>
              </div>
            </div>
            <div className={cn(
              "h-5 w-9 rounded-full border-2 transition-colors shrink-0",
              pressureMode ? "border-destructive bg-destructive" : "border-border bg-border/40"
            )}>
              <div className={cn(
                "h-3.5 w-3.5 rounded-full bg-white shadow transition-transform mt-px",
                pressureMode ? "translate-x-[18px]" : "translate-x-px"
              )} />
            </div>
          </button>

          <button
            onClick={startDrill}
            disabled={phase === "loading"}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow disabled:opacity-60 transition-colors"
          >
            {phase === "loading"
              ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("loading")}</>
              : <><Target className="size-4" aria-hidden /> {t("startBtn")}</>
            }
          </button>
        </div>
      )}

      {/* ── ACTIVE ───────────────────────────────────────────────────────────── */}
      {phase === "active" && current && (() => {
        const sit = getSituation(current);
        const style = SIT_STYLES[sit.variant];
        const SitIcon = style.icon;
        const { step: drillStep, hero: drillHero, heroCards: drillCards, bb: drillBb } = buildDrillStep(current);

        return (
          <div className="mx-auto max-w-3xl space-y-3">

            {/* Progress + streak + timer */}
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-muted-foreground shrink-0">
                {t("spot", { n: index + 1, total: spots.length })}
              </span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${((index + 1) / spots.length) * 100}%` }}
                />
              </div>
              {current.days_overdue != null && current.days_overdue > 0 && (
                <span className={cn(
                  "flex items-center gap-1 font-mono text-[10px] shrink-0",
                  current.days_overdue > 7 ? "text-destructive" : "text-warning"
                )}>
                  <Clock className="size-3" aria-hidden />
                  {current.days_overdue}d
                </span>
              )}
              {pressureMode && streak > 0 && (
                <span className="flex items-center gap-1 font-mono text-[10px] font-bold text-amber-400 shrink-0">
                  <Flame className="size-3" aria-hidden />
                  {streak}
                </span>
              )}
              <span className="font-mono text-xs text-muted-foreground shrink-0">
                {sessionCorrect}/{sessionTotal}
              </span>
              {pressureMode && <TimerRing timeLeft={timeLeft} />}
            </div>

            {/* Situation + context strip (compact) */}
            <div className={cn("flex items-center gap-x-3 gap-y-1 flex-wrap rounded-lg border px-3 py-2", style.box)}>
              <div className="flex items-center gap-1.5 shrink-0">
                <SitIcon className={cn("size-3.5", style.label)} aria-hidden />
                <span className={cn("font-mono text-[10px] font-bold uppercase tracking-wide", style.label)}>
                  {t(`situation.${sit.key}`)}
                </span>
              </div>
              <div className="flex items-center gap-x-3 gap-y-0.5 flex-wrap font-mono text-[10px] text-muted-foreground">
                <span className="font-semibold text-foreground">{t(`street.${current.street}`)}</span>
                {current.position    && <span>{current.position}</span>}
                {current.stack_bb != null && <span>Stack: <span className="text-foreground font-semibold">{current.stack_bb.toFixed(0)}bb</span></span>}
                {current.m_ratio   != null && <span>M: <span className="text-foreground">{current.m_ratio.toFixed(1)}</span></span>}
                {current.pot_size  != null && current.pot_size  > 0 && <span>Pot: <span className="text-foreground">{current.pot_size.toFixed(1)}bb</span></span>}
                {current.facing_bet!= null && current.facing_bet > 0 && (
                  <span className={sit.variant === "aggression" ? "text-warning font-semibold" : ""}>
                    Facing: <span className="font-semibold">{current.facing_bet.toFixed(1)}bb</span>
                  </span>
                )}
                {!!current.is_3bet && <span className="font-semibold text-warning">{t("context.is3bet")}</span>}
                {current.icm_pressure && current.icm_pressure !== "none" && (
                  <span className={cn({
                    "text-destructive font-semibold": current.icm_pressure === "high",
                    "text-warning font-semibold":     current.icm_pressure === "medium",
                    "text-primary font-semibold":     current.icm_pressure === "low",
                  })}>ICM {t(`icmLabel.${current.icm_pressure}`)}</span>
                )}
              </div>
            </div>

            {/* Visual poker table */}
            <div className="rounded-xl overflow-hidden ring-1 ring-border/60">
              <PokerTableV3
                step={drillStep}
                hero={drillHero}
                heroCards={drillCards}
                bb={drillBb}
                betUnit="bb"
              />
            </div>

            <p className="font-mono text-[10px] text-muted-foreground text-center">
              {t("result.originalMistake", { action: formatAction(current.action_taken).toUpperCase(), score: current.score.toFixed(2) })}
            </p>

            {/* Timeout banner */}
            {timedOut && (
              <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-2.5">
                <Timer className="size-4 text-destructive shrink-0" aria-hidden />
                <span className="font-mono text-xs font-semibold text-destructive">{t("pressure.timedOut")}</span>
              </div>
            )}

            {/* Question + Actions */}
            <p className="text-center text-sm font-semibold text-foreground">{t("question")}</p>

            <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
              {ACTION_KEYS.map((action) => (
                <button
                  key={action}
                  onClick={() => submitAction(action)}
                  disabled={submitting || timedOut}
                  className="min-h-[44px] rounded-lg border border-border bg-hud-surface px-3 py-3 font-mono text-xs font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-primary/60 hover:bg-primary/5 hover:text-primary hover:ring-primary/40 disabled:opacity-60 transition-all active:scale-95"
                >
                  {t(`actions.${action}`)}
                </button>
              ))}
            </div>
          </div>
        );
      })()}

      {/* ── RESULT ───────────────────────────────────────────────────────────── */}
      {phase === "result" && lastResult && current && (
        <div className="mx-auto max-w-lg space-y-4">
          <div className={cn(
            "flex items-center gap-4 rounded-xl border p-5",
            lastResult.is_correct ? "border-success/40 bg-success/5" : "border-destructive/40 bg-destructive/5"
          )}>
            {lastResult.is_correct
              ? <CheckCircle2 className="size-9 shrink-0 text-success" aria-hidden />
              : <XCircle     className="size-9 shrink-0 text-destructive" aria-hidden />
            }
            <div className="flex-1 min-w-0">
              <p className={cn("text-lg font-bold", lastResult.is_correct ? "text-success" : "text-destructive")}>
                {lastResult.is_correct ? t("result.correct") : t("result.wrong")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("result.bestAction", { action: formatAction(lastResult.best_action).toUpperCase() })}
              </p>
            </div>
            {/* Streak badge in result */}
            {pressureMode && streak > 0 && (
              <div className="flex items-center gap-1 font-mono text-sm font-bold text-amber-400 shrink-0">
                <Flame className="size-4" aria-hidden />
                {streak}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-hud-surface p-4">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("result.yourAction", { action: "" }).split(":")[0]}</p>
              <p className="mt-1 font-mono text-xl font-bold text-foreground">{formatAction(lastResult.new_action).toUpperCase()}</p>
            </div>
            <div className="rounded-lg border border-border bg-hud-surface p-4">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("result.bestAction", { action: "" }).split(":")[0]}</p>
              <p className="mt-1 font-mono text-xl font-bold text-foreground">{formatAction(lastResult.best_action).toUpperCase()}</p>
            </div>
          </div>

          <div className={cn(
            "flex items-center justify-between rounded-lg border p-4",
            lastResult.delta < 0 ? "border-success/30 bg-success/5" : "border-border bg-hud-surface"
          )}>
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4 text-muted-foreground" aria-hidden />
              <span className="text-sm text-muted-foreground">
                {lastResult.delta < 0
                  ? t("result.improvement", { delta: Math.abs(lastResult.delta).toFixed(3) })
                  : t("result.noImprovement")
                }
              </span>
            </div>
            <span className={cn("font-mono text-sm font-bold tabular-nums", lastResult.delta < 0 ? "text-success" : "text-destructive")}>
              {lastResult.delta > 0 ? "+" : ""}{lastResult.delta.toFixed(3)}
            </span>
          </div>

          {lastResult.srs_interval_days && (
            <div className={cn(
              "flex items-center gap-2 rounded-lg border px-4 py-2.5",
              lastResult.is_correct
                ? "border-primary/30 bg-primary/5 text-primary"
                : "border-warning/30 bg-warning/5 text-warning"
            )}>
              <Clock className="size-3.5 shrink-0" aria-hidden />
              <span className="font-mono text-[11px]">
                {lastResult.is_correct
                  ? `Próxima revisão em ${lastResult.srs_interval_days} dias`
                  : `Resetado — revisão em ${lastResult.srs_interval_days} dias`
                }
              </span>
            </div>
          )}

          {analysis ? (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-2">
              <p className="font-mono text-[9px] uppercase tracking-widest text-primary">
                {t("result.engineNote")}
              </p>
              <AiText>{analysis}</AiText>
            </div>
          ) : (
            <button
              onClick={requestAnalysis}
              disabled={analysisLoading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-5 py-3 font-mono text-sm font-semibold text-muted-foreground hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:opacity-60 transition-colors"
            >
              {analysisLoading
                ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("result.analysisLoading")}</>
                : <><BookOpen className="size-4" aria-hidden /> {t("result.requestAnalysis")}</>
              }
            </button>
          )}

          <button
            onClick={nextSpot}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
          >
            {t("next")} <ArrowRight className="size-4" aria-hidden />
          </button>
        </div>
      )}

      {/* ── DONE ─────────────────────────────────────────────────────────────── */}
      {phase === "done" && (
        <div className="mx-auto max-w-lg space-y-5 text-center">
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-8 space-y-3">
            <Swords className="mx-auto size-12 text-primary" aria-hidden />
            <h2 className="text-xl font-bold text-foreground">{t("done")}</h2>
            <p className="text-sm text-muted-foreground">{t("doneSub")}</p>
          </div>
          <div className={cn("grid gap-3", pressureMode ? "grid-cols-3" : "grid-cols-2")}>
            <div className="rounded-lg border border-border bg-hud-surface p-5">
              <p className="font-mono text-3xl font-bold tabular-nums text-primary">{accuracy}%</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {t("doneAccuracy", { pct: accuracy }).split(":")[0].trim()}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-hud-surface p-5">
              <p className="font-mono text-3xl font-bold tabular-nums text-foreground">{sessionCorrect}/{sessionTotal}</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {t("doneCorrect", { correct: sessionCorrect, total: sessionTotal })}
              </p>
            </div>
            {pressureMode && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-5">
                <p className="font-mono text-3xl font-bold tabular-nums text-amber-400 flex items-center justify-center gap-1">
                  <Flame className="size-6" aria-hidden />{streak}
                </p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {t("pressure.streakLabel")}
                </p>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              to="/dashboard"
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-5 py-3 font-mono text-sm font-bold uppercase tracking-wider text-foreground hover:border-primary/40 hover:bg-primary/5 transition-colors"
            >
              {t("backDashboard")}
            </Link>
            <button
              onClick={resetDrill}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
            >
              <Target className="size-4" aria-hidden /> {t("drillAgain")}
            </button>
          </div>
        </div>
      )}

    </HudLayout>
  );
}
