import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  Flame,
  Loader2,
  Swords,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { GtoMixedBadge } from "@/components/replayer/GtoMixedBadge";
import { AiText } from "@/components/ui/AiText";
import { drill, leaktrainer } from "@/lib/api";
import type { SparringHand, SparringStep, DrillSubmitResult, ReplayStep, GtoDecisionResult, LeakTrainerSpot, LeakSessionCat } from "@/lib/api";
import { cn, formatAction } from "@/lib/utils";

type Phase = "idle" | "loading" | "playing" | "feedback" | "summary";

const ACTION_KEYS_FACING    = ["fold", "call", "raise", "jam"] as const;
const ACTION_KEYS_NO_FACING = ["fold", "check", "bet",  "jam"] as const;
const ACTION_KEYS_ALL       = ["fold", "check", "call", "bet", "raise", "jam"] as const;

function getActionKeys(step: SparringStep): readonly string[] {
  if (step.facing_bet !== null) {
    return step.facing_bet > 0 ? ACTION_KEYS_FACING : ACTION_KEYS_NO_FACING;
  }
  if (["call", "raise"].includes(step.best_action)) return ACTION_KEYS_FACING;
  if (["check", "bet"].includes(step.best_action))  return ACTION_KEYS_NO_FACING;
  return ACTION_KEYS_ALL;
}

const STREETS = ["preflop", "flop", "turn", "river"] as const;

// ── Action color helpers (same palette as Replayer) ───────────────────────────

function actionBarColor(action: string): string {
  const a = action.toLowerCase();
  if (a === "fold")                                  return "bg-blue-500";
  if (a === "check")                                 return "bg-sky-400";
  if (a === "call")                                  return "bg-emerald-500";
  if (a.startsWith("bet") || a.startsWith("raise")) return "bg-red-500";
  if (a === "allin" || a.startsWith("allin"))        return "bg-red-600";
  return "bg-purple-500";
}

function actionTextColor(action: string): string {
  const a = action.toLowerCase();
  if (a === "fold")                                  return "text-blue-400";
  if (a === "check")                                 return "text-sky-400";
  if (a === "call")                                  return "text-emerald-400";
  if (a.startsWith("bet") || a.startsWith("raise")) return "text-red-400";
  if (a === "allin" || a.startsWith("allin"))        return "text-red-400";
  return "text-purple-400";
}

function isPlayerAct(action: string, played: string): boolean {
  const a = action.toLowerCase();
  const p = played.toLowerCase();
  if (a === p) return true;
  if (p === "allin" && (a === "all-in" || a === "jam")) return true;
  if ((p === "jam" || p === "shove") && (a === "allin" || a === "all-in")) return true;
  return false;
}

// ── Card parser ───────────────────────────────────────────────────────────────

function parseCardsRaw(raw: string | null): string[] {
  if (!raw) return [];
  const s = raw.trim();
  if (s.startsWith("[")) {
    try { return JSON.parse(s) as string[]; } catch { return []; }
  }
  return s.match(/[2-9TJQKAakqjt][shdcSHDC]/g) ?? [];
}

// ── Poker table adapter (SparringStep → ReplayStep for PokerTableV3) ─────────

function buildSparringStep(
  step: SparringStep,
  replayStep: ReplayStep | null,
): { tableStep: ReplayStep; hero: string; heroCards: string[]; bb: number } {
  const heroCardsStr = parseCardsRaw(step.hero_cards);

  if (replayStep) {
    return { tableStep: replayStep, hero: replayStep.hero, heroCards: heroCardsStr, bb: replayStep.bb };
  }

  const HERO = "Hero";
  const bb   = 100;
  const heroStack = Math.round((step.stack_bb ?? 20) * bb);
  const numP = Math.max(2, Math.min(6, step.num_players ?? 6));
  const heroPos = (step.position ?? "BTN").toUpperCase();
  const layouts: Record<number, string[]> = {
    2: ["BTN", "BB"], 3: ["BTN", "SB", "BB"],
    4: ["CO", "BTN", "SB", "BB"], 5: ["UTG", "CO", "BTN", "SB", "BB"],
    6: ["UTG", "HJ", "CO", "BTN", "SB", "BB"],
  };
  const positions = layouts[numP] ?? layouts[6];
  const btnSeat   = positions.indexOf("BTN") + 1;
  let heroSeatIdx = positions.indexOf(heroPos);
  if (heroSeatIdx < 0) heroSeatIdx = 0;
  const heroSeatNum = heroSeatIdx + 1;

  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets:  Record<string, number> = {};
  positions.forEach((pos, i) => {
    const sn = String(i + 1);
    const isHero = (i + 1) === heroSeatNum;
    seats[sn] = { player: isHero ? HERO : `V${i + 1}`, stack: heroStack, pos };
    if (pos === "SB") bets[sn] = Math.round(bb * 0.5);
    else if (pos === "BB") bets[sn] = bb;
  });
  if (step.facing_bet && step.facing_bet > 0) {
    const facingChips = Math.round(step.facing_bet * bb);
    let agSeat = heroSeatNum - 1;
    if (agSeat < 1) agSeat = numP;
    if (agSeat !== heroSeatNum) bets[String(agSeat)] = facingChips;
  }

  const boardLimit = ({ preflop: 0, flop: 3, turn: 4, river: 5 } as Record<string, number>)[step.street ?? "preflop"] ?? 0;
  const boardRaw   = parseCardsRaw(step.board);
  const potChips   = Math.round((step.pot_size ?? 2) * bb);

  return {
    tableStep: {
      type: "action", street: step.street ?? "preflop",
      seats, bets, folded: [],
      pot_bb: step.pot_size ?? 2, pot: potChips,
      bb, button: btnSeat, board: boardRaw.slice(0, boardLimit),
      player: HERO, seat: heroSeatNum, is_hero: true,
    } as unknown as ReplayStep,
    hero: HERO,
    heroCards: heroCardsStr,
    bb,
  };
}

// ── Street timeline ───────────────────────────────────────────────────────────

interface StepResult { step: SparringStep; result: DrillSubmitResult | null }

function StreetTimeline({
  steps, history, currentIndex, t,
}: {
  steps: SparringStep[];
  history: StepResult[];
  currentIndex: number;
  t: (k: string) => string;
}) {
  return (
    <div className="flex items-center gap-0">
      {steps.map((s, i) => {
        const done      = i < history.length;
        const current   = i === currentIndex;
        const correct   = done && history[i]?.result?.is_correct;
        const incorrect = done && !history[i]?.result?.is_correct;
        return (
          <div key={i} className="flex items-center">
            {i > 0 && (
              <div className={cn("h-px w-8", done ? (correct ? "bg-emerald-500/60" : "bg-destructive/60") : "bg-border")} />
            )}
            <div className="flex flex-col items-center gap-1">
              <div className={cn(
                "size-7 rounded-full border-2 flex items-center justify-center transition-all",
                current   && "border-amber-400 bg-amber-400/20 ring-2 ring-amber-400/30",
                correct   && "border-emerald-500 bg-emerald-500/20",
                incorrect && "border-destructive bg-destructive/20",
                !done && !current && "border-border bg-background",
              )}>
                {correct   && <CheckCircle2 className="size-3.5 text-emerald-400" />}
                {incorrect && <XCircle      className="size-3.5 text-destructive" />}
                {current   && <Flame        className="size-3.5 text-amber-400 animate-pulse" />}
                {!done && !current && <span className="size-1.5 rounded-full bg-border" />}
              </div>
              <span className={cn("font-mono text-[8px] uppercase tracking-wider", current ? "text-amber-400 font-bold" : "text-muted-foreground")}>
                {t(`street.${s.street}`).slice(0, 3)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Previous decisions recap ──────────────────────────────────────────────────

function HandRecap({ history, t }: { history: StepResult[]; t: (k: string) => string }) {
  if (!history.length) return null;
  return (
    <div className="rounded-lg border border-border bg-hud-surface/60 px-3 py-2 space-y-1">
      <p className="font-mono text-[8px] uppercase tracking-widest text-muted-foreground/60">{t("historyLabel")}</p>
      <div className="space-y-0.5">
        {history.map(({ step, result }, i) => (
          <div key={i} className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-muted-foreground w-12 shrink-0">{t(`street.${step.street}`).slice(0, 3).toUpperCase()}</span>
            <span className={cn("font-bold", result?.is_correct ? "text-emerald-400" : "text-destructive")}>
              {formatAction(result?.new_action ?? step.action_taken).toUpperCase()}
            </span>
            {!result?.is_correct && (
              <span className="text-muted-foreground/60">→ {formatAction(step.best_action).toUpperCase()}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Unified coach card (GTO > Engine) ─────────────────────────────────────────

interface CoachCardProps {
  result: DrillSubmitResult;
  gtoData: GtoDecisionResult | null;
  gtoLoading: boolean;
  step: SparringStep;
  t: (k: string, opts?: Record<string, unknown>) => string;
}

function CoachCard({ result, gtoData, gtoLoading, step, t }: CoachCardProps) {
  const hasGto = !gtoLoading && (gtoData?.found ?? false);

  // Frequência GTO da AÇÃO QUE O USUÁRIO JOGOU (result.new_action) — NÃO usar
  // gtoData.player_action_freq, que é da ação ARMAZENADA (a jogada real do herói).
  // No Sparring o usuário re-decide; o veredito tem que refletir a escolha DELE.
  // Bug: folding com GTO fold 100% aparecia como "desvio crítico" (era o raise original).
  const _playedKey = (result.new_action ?? "").toLowerCase();
  const playedFreq = result.gto_freq != null
    ? result.gto_freq
    : ((gtoData?.strategy ?? []).find(s => (s.action ?? "").toLowerCase() === _playedKey)?.frequency ?? 0);

  // ── Unified verdict: GTO > Engine ────────────────────────────────────────
  type Verdict = { icon: string; label: string; cls: string; borderCls: string; hdrCls: string; source: string };
  let verdict: Verdict;

  if (hasGto && gtoData) {
    const freq = playedFreq;
    if (freq >= 0.40)
      verdict = { icon: "✓", label: t("gto.verdict.correct"),  cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8",  source: "GTO Solver" };
    else if (freq >= 0.15)
      verdict = { icon: "◎", label: t("gto.verdict.mixed"),    cls: "text-amber-400",   borderCls: "border-amber-500/30",   hdrCls: "bg-amber-500/8",    source: "GTO Solver" };
    else
      verdict = { icon: "✗", label: t("gto.verdict.critical"), cls: "text-rose-400",    borderCls: "border-rose-500/30",    hdrCls: "bg-rose-500/8",     source: "GTO Solver" };
  } else {
    verdict = result.is_correct
      ? { icon: "✓", label: t("result.correct"), cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8",  source: "Engine" }
      : { icon: "✗", label: t("result.wrong"),   cls: "text-destructive", borderCls: "border-destructive/40", hdrCls: "bg-destructive/5",  source: "Engine" };
  }

  // Fonte real da validação (hand-aware > range > stored > heurística)
  if (result.validation_source) {
    verdict = { ...verdict, source: t(`valSource.${result.validation_source}`) };
  }

  const xpGained = result.xp?.gained ?? 0;

  // ── Action comparison ─────────────────────────────────────────────────────
  const playedAction = result.new_action;
  const idealAction  = hasGto && gtoData
    ? (gtoData.gto_action ?? result.best_action)
    : result.best_action;
  const isActionOk   = hasGto && gtoData
    ? playedFreq >= 0.40
    : result.is_correct;
  const showTwoCols  = idealAction.toLowerCase() !== playedAction.toLowerCase();

  // ── Strategy bars ─────────────────────────────────────────────────────────
  const strategy    = (hasGto && gtoData ? gtoData.strategy : []) ?? [];
  const stratSorted = [...strategy].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0));
  const evDiff      = hasGto && gtoData ? gtoData.ev_diff : null;

  // ── Engine/GTO conflict footnote ──────────────────────────────────────────
  const showConflict = hasGto && gtoData && !result.is_correct &&
    gtoData.gto_action &&
    result.best_action &&
    gtoData.gto_action.toLowerCase() !== result.best_action.toLowerCase();

  return (
    <section className={cn("rounded-xl border overflow-hidden shrink-0", verdict.borderCls)}>

      {/* Header: verdict + source */}
      <div className={cn("flex items-center justify-between px-3 py-2.5", verdict.hdrCls)}>
        <span className="flex items-center gap-2">
          <span className={cn("font-mono text-sm font-bold uppercase tracking-wide", verdict.cls)}>
            {verdict.icon} {verdict.label}
          </span>
          {result.mixed && <GtoMixedBadge label="gto_mixed" size="xs" />}
          {result.gto_tier === "deviation" && <GtoMixedBadge label="gto_minor_deviation" size="xs" />}
        </span>
        <span className="font-mono text-[9px] text-muted-foreground/45 uppercase tracking-wider">
          {verdict.source}{xpGained > 0 ? ` · +${xpGained} XP` : ""}
        </span>
      </div>

      <div className="p-3 space-y-3">

        {/* Você jogou / Ideal — 2 colunas se diferentes */}
        <div className={cn("grid gap-2", showTwoCols ? "grid-cols-2" : "grid-cols-1")}>
          <div className="rounded-lg px-2.5 py-2 ring-1 bg-background/60 ring-border/50">
            <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">
              {t("gto.youPlayedLabel")}
            </div>
            <div className={cn("font-mono text-sm font-bold uppercase",
              isActionOk ? verdict.cls : "text-foreground")}>
              {formatAction(playedAction)}
              {isActionOk && <span className="ml-1.5 opacity-80">✓</span>}
            </div>
          </div>
          {showTwoCols && (
            <div className="rounded-lg px-2.5 py-2 ring-1 bg-background/60 ring-border/50">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">
                {hasGto ? t("gto.recommendsLabel") : "Ideal"}
              </div>
              <div className={cn("font-mono text-sm font-bold uppercase", verdict.cls)}>
                {formatAction(idealAction)}
              </div>
            </div>
          )}
        </div>

        {/* GTO: loading inline */}
        {gtoLoading && (
          <div className="flex items-center gap-2 text-muted-foreground border-t border-border/30 pt-2">
            <Loader2 className="size-3 animate-spin shrink-0" />
            <span className="font-mono text-[10px]">{t("gto.loading")}</span>
          </div>
        )}

        {/* GTO: strategy bars */}
        {hasGto && stratSorted.length > 0 && (
          <div className="space-y-1.5 border-t border-border/30 pt-2">
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/50">
              {t("gto.strategyLabel")}
            </p>
            {stratSorted.map((s) => {
              const isP = isPlayerAct(s.action, playedAction);
              const freq = Math.round((s.frequency ?? 0) * 100);
              return (
                <div key={s.action} className="flex items-center gap-2">
                  <span className={cn(
                    "font-mono text-[11px] font-bold w-14 shrink-0 uppercase truncate",
                    isP ? "text-amber-400" : actionTextColor(s.action)
                  )}>
                    {s.label ?? formatAction(s.action)}
                  </span>
                  <div className="flex-1 h-[5px] rounded-full bg-border/50 overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all duration-500",
                        isP ? "bg-amber-400" : actionBarColor(s.action))}
                      style={{ width: `${freq}%` }}
                    />
                  </div>
                  <span className={cn(
                    "font-mono text-[11px] font-bold w-8 text-right tabular-nums shrink-0",
                    isP ? "text-amber-400" : "text-muted-foreground"
                  )}>
                    {freq}%
                  </span>
                  <span className={cn("font-mono text-[9px] w-2 shrink-0 select-none",
                    isP ? "text-amber-400" : "invisible")}>←</span>
                </div>
              );
            })}
            {evDiff != null && Math.abs(evDiff) >= 0.05 && (
              <p className={cn("font-mono text-[10px] tabular-nums pt-0.5",
                evDiff > 0 ? "text-destructive/70" : "text-emerald-400/70")}>
                {evDiff > 0
                  ? `EV perdida: −${evDiff.toFixed(2)} bb vs GTO`
                  : `+${Math.abs(evDiff).toFixed(2)} bb acima do GTO`}
              </p>
            )}
          </div>
        )}

        {/* GTO: spot não encontrado — footnote sutil */}
        {!gtoLoading && !hasGto && gtoData && !gtoData.found && (
          <p className="font-mono text-[10px] text-muted-foreground/35 italic border-t border-border/30 pt-2">
            {t("gto.notFound")}
          </p>
        )}

        {/* Engine/GTO conflict footnote — apenas quando são diferentes */}
        {showConflict && gtoData && (
          <p className="text-[10px] text-muted-foreground/50 leading-relaxed border-t border-border/20 pt-2">
            Engine→ <span className="font-mono text-foreground/60">{formatAction(result.best_action)}</span>
            {" · "}Solver→ <span className="font-mono text-foreground/60">{formatAction(gtoData.gto_action ?? "")}</span>
            {" · "}Priorizando GTO.
          </p>
        )}

        {/* Context footer: posição, stack, M-ratio, ICM */}
        {(step.m_ratio != null || (step.icm_pressure && step.icm_pressure !== "none") || step.position) && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-t border-border/30 pt-2">
            {step.position && (
              <span className="font-mono text-[9px] text-muted-foreground">{step.position}</span>
            )}
            {step.stack_bb != null && (
              <span className="font-mono text-[9px] text-muted-foreground">{step.stack_bb.toFixed(0)}bb</span>
            )}
            {step.pot_size != null && step.pot_size > 0 && (
              <span className="font-mono text-[9px] text-muted-foreground">Pote {step.pot_size.toFixed(1)}bb</span>
            )}
            {step.facing_bet != null && step.facing_bet > 0 && (
              <span className="font-mono text-[9px] text-amber-400/80">vs {step.facing_bet.toFixed(1)}bb</span>
            )}
            {step.m_ratio != null && (
              <span className={cn("font-mono text-[9px] font-semibold",
                step.m_ratio <= 5 ? "text-destructive" : step.m_ratio <= 10 ? "text-amber-400" : "text-muted-foreground")}>
                M {step.m_ratio.toFixed(1)}
              </span>
            )}
            {step.icm_pressure && step.icm_pressure !== "low" && step.icm_pressure !== "none" && (
              <span className={cn("font-mono text-[9px] font-semibold uppercase",
                step.icm_pressure === "critical" ? "text-destructive" :
                step.icm_pressure === "high" ? "text-amber-400" : "text-sky-400")}>
                ICM {step.icm_pressure}
              </span>
            )}
          </div>
        )}

      </div>
    </section>
  );
}

// ── Summary ───────────────────────────────────────────────────────────────────

function Summary({
  history, onNewHand, t,
}: {
  history: StepResult[];
  onNewHand: () => void;
  t: (k: string, opts?: Record<string, unknown>) => string;
}) {
  const correct    = history.filter((h) => h.result?.is_correct).length;
  const total      = history.length;
  const pct        = total > 0 ? Math.round((correct / total) * 100) : 0;
  const allCorrect = correct === total;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className={cn(
        "rounded-xl border p-6 space-y-3 text-center",
        allCorrect ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
      )}>
        <Swords className={cn("mx-auto size-10", allCorrect ? "text-emerald-400" : "text-amber-400")} aria-hidden />
        <h2 className="text-xl font-bold text-foreground">{t("summary.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("summary.subtitle")}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
          <p className={cn("font-mono text-3xl font-bold tabular-nums", pct >= 70 ? "text-emerald-400" : "text-amber-400")}>
            {pct}%
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {t("summary.accuracy")}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
          <p className="font-mono text-3xl font-bold tabular-nums text-foreground">{correct}/{total}</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {t("summary.decisions")}
          </p>
        </div>
      </div>

      <div className={cn("space-y-2", history.length > 2 && "lg:grid lg:grid-cols-2 lg:gap-3 lg:space-y-0")}>
        {history.map(({ step, result }, i) => (
          <div key={i} className={cn(
            "flex items-center justify-between rounded-lg border px-4 py-2.5",
            result?.is_correct ? "border-emerald-500/20 bg-emerald-500/5" : "border-destructive/20 bg-destructive/5"
          )}>
            <div className="flex items-center gap-2">
              {result?.is_correct
                ? <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />
                : <XCircle      className="size-4 text-destructive shrink-0" />
              }
              <span className="font-mono text-xs text-foreground">
                {t("summary.step", { n: i + 1 })} — {t(`street.${step.street}`)}
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[10px]">
              <span className={result?.is_correct ? "text-emerald-400 font-bold" : "text-muted-foreground"}>
                {formatAction(result?.new_action ?? step.action_taken).toUpperCase()}
              </span>
              {!result?.is_correct && (
                <span className="text-emerald-400">→ {formatAction(step.best_action).toUpperCase()}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={onNewHand}
        className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 transition-colors"
      >
        <Swords className="size-4" aria-hidden />
        {t("newHand")}
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

// Estado da sessão do Leak Trainer (por categoria: hits/misses/seen/streak) — persiste
// no client; o grading é server-side, então adulterar isto não falsifica acerto.
const LEAKTRAINER_SESSION_KEY = "leaktrainer_session_state";

function loadSessionState(): Record<string, LeakSessionCat> {
  try { return JSON.parse(localStorage.getItem(LEAKTRAINER_SESSION_KEY) ?? "{}"); }
  catch { return {}; }
}
function saveSessionState(s: Record<string, LeakSessionCat>) {
  try { localStorage.setItem(LEAKTRAINER_SESSION_KEY, JSON.stringify(s)); } catch { /* ignore */ }
}

export default function Sparring() {
  const { t } = useTranslation("sparring");

  const SESSION_LEN = 15;   // spots por sessão antes do resumo

  const [phase, setPhase]                   = useState<Phase>("idle");
  const [spot, setSpot]                     = useState<LeakTrainerSpot | null>(null);
  const [history, setHistory]               = useState<StepResult[]>([]);
  const [currentResult, setCurrentResult]   = useState<DrillSubmitResult | null>(null);
  const [submitting, setSubmitting]         = useState(false);
  const [analysis, setAnalysis]             = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError]                   = useState("");
  const [sessionState, setSessionState]     = useState<Record<string, LeakSessionCat>>(loadSessionState);
  const [sessionCount, setSessionCount]     = useState(0);

  // O grade do Leak Trainer já devolve a estratégia → sem fetch separado de GTO.
  const [gtoData, setGtoData] = useState<GtoDecisionResult | null>(null);
  const gtoLoading = false;

  // Mapeia o spot canônico (LeakTrainerSpot) para o shape SparringStep que o render usa.
  const current: SparringStep | null = spot ? ({
    decision_id:  -1,
    street:       spot.street,
    hero_cards:   spot.hero_cards,
    board:        spot.board,
    action_taken: "",
    best_action:  "",          // resposta NÃO vem no /next (anti-spoiler); vem só no /grade
    position:     spot.position,
    num_players:  spot.num_players,
    stack_bb:     spot.stack_bb,
    pot_size:     spot.pot_size,
    facing_bet:   spot.facing_bet,
    is_3bet:      spot.is_3bet,
    m_ratio:      spot.m_ratio,
    icm_pressure: spot.icm_pressure,
    gto_label:    null,
    gto_action:   null,
    label:        "standard",
    score:        0,
  } as unknown as SparringStep) : null;
  const steps = current ? [current] : [];
  const isLastStep = sessionCount + 1 >= SESSION_LEN;

  // Busca o próximo spot GTO canônico (mirando os leaks + adaptando à sessão).
  const loadSpot = async (resetSession = false) => {
    setPhase("loading");
    setError("");
    setCurrentResult(null);
    setAnalysis(null);
    setGtoData(null);
    if (resetSession) { setHistory([]); setSessionCount(0); }
    try {
      const data = await leaktrainer.next(sessionState);
      if (data.insufficient_data) { setError(t("noData")); setPhase("idle"); return; }
      setSpot(data);
      setPhase("playing");
    } catch {
      setError(t("noData"));
      setPhase("idle");
    }
  };

  const submitAction = async (action: string) => {
    if (!spot || !current || submitting) return;
    setSubmitting(true);
    try {
      const result = await leaktrainer.grade(spot.spot, action);
      setCurrentResult(result);
      setHistory((h) => [...h, { step: current, result }]);
      // gtoData sintético a partir do grade → o CoachCard mostra veredito 3-níveis +
      // barras de estratégia sem fetch separado.
      setGtoData({
        found:              true,
        gto_action:         result.best_action,
        player_action:      result.new_action,
        player_action_freq: result.gto_freq,
        strategy:           result.gto_strategy ?? [],
        ev_diff:            null,
      } as unknown as GtoDecisionResult);
      // atualiza o estado da sessão da categoria do spot (dirige a adaptação do /next)
      const cat = String((spot.spot as Record<string, unknown>).category ?? "");
      if (cat) {
        setSessionState((prev) => {
          const c = prev[cat] ?? { hits: 0, misses: 0, seen: 0, hit_streak: 0 };
          const ok = !!result.is_correct;
          const upd: LeakSessionCat = {
            seen:       c.seen + 1,
            hits:       c.hits + (ok ? 1 : 0),
            misses:     c.misses + (ok ? 0 : 1),
            hit_streak: ok ? (c.hit_streak ?? 0) + 1 : 0,
          };
          const ns = { ...prev, [cat]: upd };
          saveSessionState(ns);
          return ns;
        });
      }
      setSessionCount((n) => n + 1);
      setPhase("feedback");
    } catch {
      // keep playing
    } finally {
      setSubmitting(false);
    }
  };

  const nextStep = () => {
    setAnalysis(null);
    setGtoData(null);
    if (sessionCount >= SESSION_LEN) { setPhase("summary"); }
    else { setCurrentResult(null); loadSpot(); }
  };

  const requestAnalysis = async () => {
    if (!current || analysisLoading) return;
    setAnalysisLoading(true);
    try {
      const res = await drill.analysis(current.decision_id);
      setAnalysis(res.analysis);
    } catch { setAnalysis(t("result.analysisError")); }
    finally { setAnalysisLoading(false); }
  };

  // ── PLAYING / FEEDBACK — full-screen layout ──────────────────────────────
  if ((phase === "playing" || phase === "feedback") && current) {
    // SÓ revela o replay (que mostra a ação REAL do herói, ex.: "Hero raises") DEPOIS de
    // responder. Durante a decisão (phase "playing") usa a mesa sintética sem a ação do
    // herói — senão spoila a jogada antes do clique (e a mesa "muda sozinha" quando o
    // fetch async do replay chega).
    // Leak Trainer não tem mão real → mesa sempre sintética (sem replay/spoiler).
    const replayStep: ReplayStep | null = null;
    const { tableStep, hero: tableHero, heroCards: tableHeroCards, bb: tableBb } = buildSparringStep(current, replayStep);
    const actionKeys = getActionKeys(current);
    const cols = actionKeys.length === 4 ? "grid-cols-2" : "grid-cols-3";
    const isCallEqualToJam =
      (current.facing_bet ?? 0) > 0 &&
      (current.stack_bb ?? 0) > 0 &&
      (current.facing_bet ?? 0) >= (current.stack_bb ?? 9999) * 0.95;

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
            <Swords className="size-3 text-amber-400" aria-hidden />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-amber-400">Sparring</span>
          </div>
          {spot?.category_label && (
            <span className="hidden sm:flex items-center gap-1.5 font-mono text-[9px] text-amber-400/70 truncate max-w-[280px]" title="Categoria de leak treinada">
              <Flame className="size-3 shrink-0" aria-hidden />
              <span className="truncate">{spot.category_label}</span>
            </span>
          )}
          <span className="ml-auto font-mono text-[9px] text-muted-foreground/50">
            {sessionCount}/{SESSION_LEN}
          </span>
          <div>
            <StreetTimeline steps={steps} history={history} currentIndex={phase === "playing" ? 0 : -1} t={t} />
          </div>
        </div>

        <div className="flex-1 min-h-0 flex gap-3 px-3 md:px-5 pt-1 pb-3 mx-auto w-full max-w-[1600px]">

          {/* Table column */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col gap-2">
            <div className="flex-1 min-h-0 overflow-visible pt-10">
              <div className="mx-auto aspect-[16/10] max-w-[90%]" style={{ maxHeight: "calc(100% - 2.5rem)" }}>
                <PokerTableV3 step={tableStep} hero={tableHero} heroCards={tableHeroCards} bb={tableBb} betUnit="bb" />
              </div>
            </div>

            {/* Mobile: actions / next */}
            <div className="lg:hidden shrink-0 space-y-2">
              {phase === "playing" && (
                <div className={`grid gap-2 ${cols}`}>
                  {actionKeys.map((action) => (
                    <button key={action} onClick={() => submitAction(action)}
                      disabled={submitting || (action === 'jam' && isCallEqualToJam)}
                      title={action === 'jam' && isCallEqualToJam ? 'Equivalente a Call (stack coberto)' : undefined}
                      className="min-h-[40px] rounded-lg border border-border bg-hud-surface px-2 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-amber-500/60 hover:bg-amber-500/5 hover:text-amber-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95">
                      {t(`actions.${action}`)}
                    </button>
                  ))}
                </div>
              )}
              {phase === "feedback" && currentResult && (
                <button onClick={nextStep}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 transition-colors">
                  {isLastStep ? t("viewSummary") : t("next")} <ArrowRight className="size-4" aria-hidden />
                </button>
              )}
            </div>
          </div>

          {/* Side panel — desktop only */}
          <aside className="hidden lg:flex w-72 shrink-0 flex-col gap-3 overflow-y-auto pb-2 pt-10">

            {phase === "playing" && (
              <>
                {history.length > 0 && <HandRecap history={history} t={t} />}

                {/* Context card */}
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 space-y-2 shrink-0">
                  <div className="flex items-center gap-2">
                    <Flame className="size-3.5 shrink-0 text-amber-400" aria-hidden />
                    <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-amber-400">
                      {t(`street.${current.street}`)}
                    </p>
                    {spot?.category_label && (
                      <span className="ml-auto font-mono text-[9px] text-amber-400/70 truncate">{spot.category_label}</span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-amber-500/20 pt-2">
                    {current.position    && <span className="font-mono text-[10px] text-muted-foreground">{t("context.position")}: <span className="text-foreground font-semibold">{current.position}</span></span>}
                    {current.stack_bb != null && <span className="font-mono text-[10px] text-muted-foreground">Stack: <span className="text-foreground font-semibold">{t("context.bb", { n: current.stack_bb.toFixed(0) })}</span></span>}
                    {current.m_ratio != null  && <span className="font-mono text-[10px] text-muted-foreground">M: <span className="text-foreground font-semibold">{current.m_ratio.toFixed(1)}</span></span>}
                    {current.num_players != null && <span className="font-mono text-[10px] text-muted-foreground">{t("context.players", { n: current.num_players })}</span>}
                    {current.is_3bet && <span className="font-mono text-[10px] font-semibold text-amber-400">{t("context.is3bet")}</span>}
                    {current.pot_size != null && current.pot_size > 0 && <span className="font-mono text-[10px] text-muted-foreground">{t("context.pot")}: <span className="text-foreground font-semibold">{t("context.bb", { n: current.pot_size.toFixed(1) })}</span></span>}
                    {current.facing_bet != null && current.facing_bet > 0 && <span className="font-mono text-[10px] text-amber-400 font-semibold">{t("context.facing")}: {t("context.bb", { n: current.facing_bet.toFixed(1) })}</span>}
                    {current.icm_pressure && current.icm_pressure !== "none" && (
                      <span className="font-mono text-[10px] text-muted-foreground">ICM: <span className={cn("font-semibold", { "text-destructive": current.icm_pressure === "high", "text-amber-400": current.icm_pressure === "medium", "text-emerald-400": current.icm_pressure === "low" })}>{t(`icmLabel.${current.icm_pressure}`)}</span></span>
                    )}
                  </div>
                </div>

                <p className="text-center text-sm font-semibold text-foreground shrink-0">{t("question")}</p>
                <div className={`grid gap-2 shrink-0 ${cols}`}>
                  {actionKeys.map((action) => (
                    <button key={action} onClick={() => submitAction(action)}
                      disabled={submitting || (action === 'jam' && isCallEqualToJam)}
                      title={action === 'jam' && isCallEqualToJam ? 'Equivalente a Call (stack coberto)' : undefined}
                      className="min-h-[48px] rounded-lg border border-border bg-hud-surface px-3 py-3 font-mono text-xs font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-amber-500/60 hover:bg-amber-500/5 hover:text-amber-400 hover:ring-amber-500/40 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95">
                      {t(`actions.${action}`)}
                    </button>
                  ))}
                </div>
              </>
            )}

            {phase === "feedback" && currentResult && (
              <div className="flex flex-col gap-3 min-h-0 overflow-y-auto">

                {/* ── Unified coach card ── */}
                <CoachCard
                  result={currentResult}
                  gtoData={gtoData}
                  gtoLoading={gtoLoading}
                  step={current}
                  t={t}
                />

                {/* ── SRS + delta compact row ── */}
                <div className="grid grid-cols-2 gap-2 shrink-0">
                  <div className={cn(
                    "rounded-lg border p-2.5 flex items-center gap-2",
                    currentResult.delta < 0 || currentResult.is_correct
                      ? "border-emerald-500/30 bg-emerald-500/5"
                      : "border-border bg-hud-surface"
                  )}>
                    <TrendingUp className="size-3.5 text-muted-foreground shrink-0" />
                    <span className={cn(
                      "font-mono text-xs font-bold tabular-nums",
                      currentResult.delta < 0 || currentResult.is_correct ? "text-emerald-400" : "text-destructive"
                    )}>
                      {currentResult.delta > 0 ? "+" : ""}{currentResult.delta.toFixed(3)}
                    </span>
                  </div>
                  {currentResult.srs_interval_days != null && (
                    <div className={cn(
                      "rounded-lg border px-2.5 py-2 flex items-center",
                      currentResult.is_correct
                        ? "border-amber-500/30 bg-amber-500/5 text-amber-400"
                        : "border-warning/30 bg-warning/5 text-warning"
                    )}>
                      <span className="font-mono text-[10px] leading-tight">
                        {currentResult.is_correct
                          ? t("result.srsCorrect", { n: currentResult.srs_interval_days })
                          : t("result.srsReset",   { n: currentResult.srs_interval_days })}
                      </span>
                    </div>
                  )}
                </div>

                {/* ── AI analysis — só spots com decision_id real (Leak Trainer é sintético) ── */}
                {(current?.decision_id ?? -1) >= 0 && (analysis ? (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-2 shrink-0">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-amber-400">{t("result.engineNote")}</p>
                    <AiText>{analysis}</AiText>
                  </div>
                ) : (
                  <button onClick={requestAnalysis} disabled={analysisLoading}
                    className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-5 py-2.5 font-mono text-sm font-semibold text-muted-foreground hover:border-amber-500/40 hover:text-amber-400 hover:bg-amber-500/5 disabled:opacity-60 transition-colors shrink-0">
                    {analysisLoading
                      ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("result.analysisLoading")}</>
                      : <><BookOpen className="size-4" aria-hidden /> {t("result.requestAnalysis")}</>}
                  </button>
                ))}

                {/* ── Next button ── */}
                <button onClick={nextStep}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 transition-colors shrink-0">
                  {isLastStep ? t("viewSummary") : t("next")} <ArrowRight className="size-4" aria-hidden />
                </button>

              </div>
            )}

          </aside>
        </div>
      </div>
    );
  }

  // ── IDLE / LOADING / SUMMARY ──────────────────────────────────────────────
  return (
    <HudLayout eyebrow="Sparring Mode" title={t("title")} description={t("subtitle")}>

      {(phase === "idle" || phase === "loading") && (
        <div className="mx-auto max-w-lg space-y-6">
          <div className="relative overflow-hidden rounded-xl border border-amber-500/30 bg-amber-500/5 p-8 text-center space-y-4">
            <div className="absolute inset-0 bg-gradient-to-b from-amber-500/5 to-transparent pointer-events-none" />
            <Swords className="mx-auto size-12 text-amber-400" aria-hidden />
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-amber-400 mb-2">{t("arenaLabel")}</p>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-sm mx-auto">{t("arenaDesc")}</p>
            </div>
            <div className="flex items-center justify-center gap-2 pt-2">
              {STREETS.map((s, i) => (
                <div key={s} className="flex items-center gap-2">
                  {i > 0 && <div className="h-px w-5 bg-amber-500/30" />}
                  <span className="font-mono text-[9px] uppercase tracking-wider text-amber-400/70 rounded-full border border-amber-500/30 px-2 py-0.5">
                    {t(`street.${s}`).slice(0, 3)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center text-sm text-destructive">{error}</p>
          )}

          <button
            onClick={() => loadSpot(true)}
            disabled={phase === "loading"}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 disabled:opacity-60 transition-colors"
          >
            {phase === "loading"
              ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("loading")}</>
              : <><Swords className="size-4" aria-hidden /> {t("startBtn")}</>
            }
          </button>
        </div>
      )}

      {phase === "summary" && (
        <Summary history={history} onNewHand={() => loadSpot(true)} t={t} />
      )}

    </HudLayout>
  );
}
