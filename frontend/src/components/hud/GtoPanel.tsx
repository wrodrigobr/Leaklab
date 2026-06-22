import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronUp, Loader2, Scale, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import { gto } from "@/lib/api";
import type { GtoDecisionResult, GtoStrategyAction } from "@/lib/api";

interface GtoPanelProps {
  decisionId: number;
}

// Action color: the player's action vs top GTO action
function actionColor(action: string, topAction: string) {
  if (!action) return "text-muted-foreground";
  if (action.toLowerCase() === topAction.toLowerCase()) return "text-emerald-400";
  return "text-rose-400";
}

// Bar color per action
function barColor(action: string, playerAction: string, topAction: string): string {
  const a = action.toLowerCase();
  const p = (playerAction || "").toLowerCase();
  const t = (topAction || "").toLowerCase();
  if (a === p && a === t) return "bg-emerald-500";
  if (a === t) return "bg-primary";
  if (a === p) return "bg-rose-500";
  if (a.includes("fold")) return "bg-slate-500";
  if (a.includes("check")) return "bg-sky-500/70";
  if (a.includes("call")) return "bg-sky-500";
  if (a.includes("allin") || a.includes("shove") || a.includes("jam")) return "bg-rose-600";
  return "bg-violet-500";
}

// Does this action key match what the player played?
function isPlayerAction(action: string, playerAction: string): boolean {
  if (!playerAction) return false;
  const a = action.toLowerCase();
  const p = playerAction.toLowerCase();
  if (a === p) return true;
  const isAllin = (s: string) => s === "allin" || s === "all-in" || s === "shove" || s === "jam";
  if (isAllin(p) && isAllin(a)) return true;
  if ((p === "bet" || p === "raise" || isAllin(p)) &&
      (a.includes("bet") || a.includes("raise") || isAllin(a)))
    return true;
  return false;
}

// Severity label based on player_action_freq
function deviationLabel(freq: number, t: (k: string) => string): { text: string; cls: string } {
  if (freq >= 0.40) return { text: t("gto.verdict.correct"),   cls: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" };
  if (freq >= 0.15) return { text: t("gto.verdict.mixed"),     cls: "text-amber-400   bg-amber-500/10   border-amber-500/30"   };
  return               { text: t("gto.verdict.critical"),  cls: "text-rose-400   bg-rose-500/10    border-rose-500/30"    };
}

export function GtoPanel({ decisionId }: GtoPanelProps) {
  const { t } = useTranslation("sparring");
  const [data, setData]         = useState<GtoDecisionResult | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(false);
    setExpanded(false);

    gto.decisionLookup(decisionId)
      .then((res) => { if (!cancelled) { setData(res); setLoading(false); } })
      .catch(() => { if (!cancelled) { setError(true); setLoading(false); } });

    return () => { cancelled = true; };
  }, [decisionId]);

  return (
    <div className="rounded-lg border border-border bg-hud-surface/60 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border/50">
        <Scale className="size-3 text-muted-foreground shrink-0" aria-hidden />
        <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground flex-1">
          Solver GTO
        </p>
        {data?.found && data.exploitability_pct != null && (
          <span className="font-mono text-[8px] text-muted-foreground/60">
            {t("gto.exploitability")}: {data.exploitability_pct.toFixed(1)}%
          </span>
        )}
      </div>

      <div className="p-3 space-y-3">
        {/* Loading */}
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground py-1">
            <Loader2 className="size-3.5 animate-spin shrink-0" aria-hidden />
            <span className="font-mono text-[11px]">{t("gto.loading")}</span>
          </div>
        )}

        {/* Not found */}
        {!loading && (error || (data && !data.found)) && (
          <p className="font-mono text-[10px] text-muted-foreground/50 italic py-1">
            {t("gto.notFound")}
          </p>
        )}

        {/* Main content */}
        {!loading && data?.found && (() => {
          const strategy    = data.strategy ?? [];
          const topAction   = data.gto_action_label ?? data.gto_action ?? "—";
          const playerLabel = data.player_action_label ?? data.player_action ?? "—";
          const playerFreq  = data.player_action_freq ?? 0;
          const verdict     = deviationLabel(playerFreq, t);
          const isCorrect   = playerFreq >= 0.40;
          const evDiff      = data.ev_diff;

          return (
            <>
              {/* ── Layer 1: Verdict ── */}
              <div className={cn(
                "rounded-md border px-2.5 py-2 space-y-1",
                verdict.cls
              )}>
                {/* Badge */}
                <p className={cn("font-mono text-[8px] uppercase tracking-widest font-bold", verdict.cls.split(" ")[0])}>
                  {verdict.text}
                </p>

                {/* GTO recommends */}
                <div className="flex items-end justify-between gap-2">
                  <div>
                    <p className="font-mono text-[8px] text-muted-foreground uppercase tracking-wide">
                      {t("gto.recommendsLabel")}
                    </p>
                    <p className="font-mono text-lg font-bold text-foreground leading-tight">
                      {topAction}
                    </p>
                    {data.gto_off_tree && (
                      <p className="font-mono text-[8px] text-amber-400/90 uppercase tracking-wide leading-tight mt-0.5"
                         title={t("gto.offTreeHint")}>
                        {t("gto.offTree")}
                      </p>
                    )}
                  </div>
                  {/* Player's action */}
                  <div className="text-right">
                    <p className="font-mono text-[8px] text-muted-foreground uppercase tracking-wide">
                      {t("gto.youPlayedLabel")}
                    </p>
                    <p className={cn(
                      "font-mono text-base font-bold leading-tight",
                      actionColor(data.player_action ?? "", data.gto_action ?? "")
                    )}>
                      {playerLabel}
                    </p>
                  </div>
                </div>

                {/* EV diff — only show if meaningful */}
                {evDiff != null && Math.abs(evDiff) >= 0.05 && (
                  <p className={cn(
                    "font-mono text-[9px]",
                    isCorrect ? "text-emerald-400/80" : "text-rose-400/80"
                  )}>
                    {isCorrect ? "+" : ""}{evDiff > 0 ? "+" : ""}{evDiff.toFixed(2)} bb {t("gto.evDiffLabel")}
                  </p>
                )}
              </div>

              {/* ── Layer 2: Full Strategy ── */}
              {strategy.length > 0 && (
                <div className="space-y-1.5">
                  <p className="font-mono text-[8px] uppercase tracking-widest text-muted-foreground/70">
                    {t("gto.strategyLabel")}
                  </p>
                  {strategy.map((s) => (
                    <StrategyRow
                      key={s.action}
                      s={s}
                      playerAction={data.player_action ?? ""}
                      topAction={data.gto_action ?? ""}
                    />
                  ))}
                </div>
              )}

              {/* ── Layer 3: Context (collapsible) ── */}
              {(data.stack_bb != null || data.facing_bb != null || data.position) && (
                <div>
                  <button
                    onClick={() => setExpanded(v => !v)}
                    className="flex items-center gap-1 text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                  >
                    <span className="font-mono text-[8px] uppercase tracking-widest">
                      {t("gto.contextLabel")}
                    </span>
                    {expanded
                      ? <ChevronUp className="size-2.5" aria-hidden />
                      : <ChevronDown className="size-2.5" aria-hidden />
                    }
                  </button>

                  {expanded && (
                    <div className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-0.5">
                      {data.position && (
                        <CtxRow label={t("gto.ctx.position")} value={data.position} />
                      )}
                      {data.street && (
                        <CtxRow label={t("gto.ctx.street")} value={data.street.toUpperCase()} />
                      )}
                      {data.stack_bb != null && (
                        <CtxRow label={t("gto.ctx.stack")} value={`${data.stack_bb.toFixed(1)} bb`} />
                      )}
                      {data.facing_bb != null && data.facing_bb > 0 && (
                        <CtxRow label={t("gto.ctx.facing")} value={`${data.facing_bb.toFixed(1)} bb`} />
                      )}
                      {data.exploitability_pct != null && (
                        <CtxRow label={t("gto.ctx.solved")} value={`${data.exploitability_pct.toFixed(1)}%`} />
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
}

function StrategyRow({
  s,
  playerAction,
  topAction,
}: {
  s: GtoStrategyAction;
  playerAction: string;
  topAction: string;
}) {
  const isPlayer = isPlayerAction(s.action, playerAction);
  const isTop    = s.action.toLowerCase() === topAction.toLowerCase();
  const pct      = Math.round(s.frequency * 100);
  const color    = barColor(s.action, playerAction, topAction);

  return (
    <div className="flex items-center gap-2">
      {/* Action label */}
      <span className={cn(
        "font-mono text-[9px] w-[68px] shrink-0 font-semibold",
        isPlayer && !isTop  ? "text-rose-400"
        : isTop             ? "text-foreground"
        : "text-muted-foreground"
      )}>
        {s.label}
      </span>

      {/* Bar */}
      <div className="flex-1 h-1.5 rounded-full bg-border/60 overflow-hidden relative">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Pct */}
      <span className={cn(
        "font-mono text-[9px] w-7 text-right shrink-0 tabular-nums",
        isPlayer && !isTop  ? "text-rose-400 font-bold"
        : isTop             ? "text-foreground font-bold"
        : "text-muted-foreground"
      )}>
        {pct}%
      </span>

      {/* Indicator: player played this */}
      {isPlayer && (
        <span className="font-mono text-[7px] text-muted-foreground/50 shrink-0 w-3">
          ←
        </span>
      )}
      {!isPlayer && <span className="w-3 shrink-0" />}
    </div>
  );
}

function CtxRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1">
      <span className="font-mono text-[8px] text-muted-foreground/50 uppercase tracking-wide">
        {label}
      </span>
      <span className="font-mono text-[8px] text-muted-foreground">{value}</span>
    </div>
  );
}
