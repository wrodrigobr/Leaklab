import React, { useRef } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown, Target, Zap, Brain } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { EmptyDashboard } from "@/components/hud/EmptyDashboard";
import { PlayerStatsCard } from "@/components/hud/PlayerStatsCard";
import { EvSummary, GtoQualityData, GtoPositionData } from "@/lib/api";
import { useMasonryRows } from "@/hooks/useMasonryRows";
import { formatAction } from "@/lib/utils";
import { SECTION_SPAN, DashSection } from "@/hooks/useDashboardLayout";
import { V2EvTrendCard } from "@/components/hud/V2EvTrendCard";
import { V2CoverageCard } from "@/components/hud/V2CoverageCard";
import { V2StreetEvCard } from "@/components/hud/V2StreetEvCard";
import { V2AiInsightsCard, AiInsight } from "@/components/hud/V2AiInsightsCard";
import { V2QualityCard } from "@/components/hud/V2QualityCard";
import { V2PositionCard } from "@/components/hud/V2PositionCard";
import { V2BankrollCard } from "@/components/hud/V2BankrollCard";

/**
 * DashboardV2 — UX-1 (specs/ux-proposal-2026.html), modelo "v2 chaveável".
 *
 * Shell novo AO LADO do Index clássico (v1 intocado): hero "Hoje" responde
 * "quanto estou perdendo e o que treino agora" em 3 segundos, leaks rankeados
 * por CUSTO em bb (diferencial do solver hand-aware), e os cards existentes
 * reusados em ordem FIXA opinada (sem masonry arrastável) via renderCard do
 * Index — zero duplicação de dados ou de componentes.
 */

interface Props {
  onUpload: () => void;
  evSummary: EvSummary | null;
  hasData: boolean;
  renderCard: (id: string, opts?: { v2?: boolean }) => React.ReactNode;
  gtoQuality?: GtoQualityData | null;
  gtoPosition?: GtoPositionData | null;
  pendingGto?: number;
  aiInsights?: AiInsight[];
  aiLocked?: boolean;
  /** onboarding sem dados (tournsLoaded && !hasData) — mesmo EmptyDashboard do clássico */
  showEmpty?: boolean;
  kpis?: { roi: number | null; itmPct: number | null; totalEvents: number; totalHands: number };
  playerStats?: React.ComponentProps<typeof PlayerStatsCard>["stats"];
  drift?: { detected: boolean; sessions: number } | null;
  onDismissDrift?: () => void;
}

// Ordem fixa opinada (UX-2 onda 3) — clusters temáticos em pares de linha:
// resultado (bankroll×results) → perfil (dna×twin) → pressão (pressure×cognitive)
// → futuro (career×causal_map). quality/position/bankroll viraram cards V2
// próprios (hard-coded abaixo, com spans dedicados). "leakfinder" e "leaks"
// seguem FORA: o ranking "Leaks por custo" do hero os substitui (duplicidade).
const CARD_ORDER = [
  "results", "dna", "twin", "pressure", "cognitive", "career", "causal_map",
];

export function DashboardV2({ onUpload, evSummary, hasData, renderCard, gtoQuality = null, gtoPosition = null, pendingGto = 0, aiInsights = [], aiLocked = false, showEmpty = false, kpis, playerStats = null, drift = null, onDismissDrift }: Props) {
  const { t } = useTranslation("dashboard");
  // Masonry real (mesmo hook do dashboard clássico): cards curtos liberam o vão
  // vertical e o grid-flow-dense empacota — sem blocos vazios na grade.
  const gridRef = useRef<HTMLElement>(null);
  useMasonryRows(gridRef, [evSummary, hasData]);
  const s = evSummary;
  const trendDelta =
    s?.ev_per_100_recent != null && s?.ev_per_100_prev != null
      ? s.ev_per_100_recent - s.ev_per_100_prev
      : null;
  const topLeak = s?.top_leaks?.[0] ?? null;

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader onUpload={onUpload} />
      <main className="mx-auto max-w-[1440px] space-y-6 px-4 pt-6 pb-28 md:px-8 md:pb-8 animate-fade-in">

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
            <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
            {t("v2.eyebrow")}
          </div>
        </div>

        {showEmpty ? (
          <EmptyDashboard onComplete={onUpload} />
        ) : (
        <>

        {/* ── Alerta de drift cognitivo (mesma detecção do clássico, visual V2) ── */}
        {drift?.detected && (
          <div className="flex items-start justify-between gap-3 rounded-xl ring-1 ring-amber-500/30 bg-amber-500/5 px-4 py-3">
            <div className="flex items-start gap-2">
              <Brain className="size-4 text-amber-400 shrink-0 mt-0.5" aria-hidden />
              <div>
                <p className="text-sm font-medium text-foreground">{t("drift.alertTitle")}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t("drift.alertDesc", { n: drift.sessions })}
                </p>
              </div>
            </div>
            {onDismissDrift && (
              <button
                onClick={onDismissDrift}
                className="shrink-0 font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                aria-label={t("drift.dismiss")}
              >
                ✕
              </button>
            )}
          </div>
        )}

        {/* ── HERO "Hoje" ───────────────────────────────────────────────── */}
        <section className="grid gap-3 md:grid-cols-3">
          {/* EV perdido /100 — a métrica-líder */}
          <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              <TrendingDown className="size-3" /> {t("v2.evLabel")}
            </div>
            {s?.ev_per_100 != null ? (
              <>
                <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-red-400">
                  −{s.ev_per_100.toFixed(1)} <span className="text-sm text-muted-foreground">bb</span>
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {trendDelta != null && (
                    <span className={trendDelta < 0 ? "text-emerald-400" : "text-amber-400"}>
                      {trendDelta < 0 ? "▼" : "▲"} {Math.abs(trendDelta).toFixed(1)}bb{" "}
                    </span>
                  )}
                  {trendDelta != null
                    ? (trendDelta < 0 ? t("v2.evImproving") : t("v2.evWorsening"))
                    : t("v2.evBasis", { n: s.decisions_with_ev })}
                </div>
              </>
            ) : (
              <div className="mt-2 text-[12px] text-muted-foreground">{t("v2.evNoData")}</div>
            )}
          </div>

          {/* % de decisões sólidas */}
          <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              <Target className="size-3" /> {t("v2.solidLabel")}
            </div>
            {s?.standard_pct != null ? (
              <>
                <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-teal-300">
                  {s.standard_pct.toFixed(0)}<span className="text-sm text-muted-foreground">%</span>
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">{t("v2.solidSub")}</div>
              </>
            ) : (
              <div className="mt-2 text-[12px] text-muted-foreground">—</div>
            )}
          </div>

          {/* CTA: leak mais caro → treinar */}
          <div className="rounded-xl ring-1 ring-teal-500/40 bg-teal-500/5 p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-teal-300">
                <Zap className="size-3" /> {t("v2.ctaLabel")}
              </div>
              {topLeak ? (
                <div className="mt-1 text-[13px] text-foreground">
                  <span className="font-mono font-bold uppercase">{formatAction(topLeak.action_taken)}</span>
                  <span className="text-muted-foreground"> {t("v2.insteadOf")} </span>
                  <span className="font-mono font-bold uppercase text-teal-300">{formatAction(topLeak.best_action)}</span>
                  <span className="text-muted-foreground"> · {topLeak.street} · </span>
                  <span className="font-mono font-bold text-red-400">−{topLeak.loss_bb.toFixed(1)}bb</span>
                </div>
              ) : (
                <div className="mt-1 text-[12px] text-muted-foreground">{t("v2.ctaNoLeak")}</div>
              )}
            </div>
            <a
              href="/training"
              className="mt-3 inline-flex items-center justify-center rounded-lg bg-teal-400 px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-[#06281f] hover:bg-teal-300 transition-colors"
            >
              {t("v2.ctaButton")}
            </a>
          </div>
        </section>

        {/* ── KPIs secundários (ROI / ITM / volume) — chips compactos ───── */}
        {kpis && hasData && (
          <section className="grid grid-cols-3 gap-3">
            <div className="rounded-xl ring-1 ring-border bg-card/60 px-4 py-2.5">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("kpis.roi")}</div>
              <div className={`font-mono text-lg font-bold tabular-nums ${
                kpis.roi == null ? "text-muted-foreground" : kpis.roi >= 0 ? "text-teal-300" : "text-red-400"
              }`}>
                {kpis.roi != null ? `${kpis.roi >= 0 ? "+" : ""}${kpis.roi.toFixed(1)}%` : "—"}
              </div>
            </div>
            <div className="rounded-xl ring-1 ring-border bg-card/60 px-4 py-2.5">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("kpis.itm")}</div>
              <div className="font-mono text-lg font-bold tabular-nums text-foreground">
                {kpis.itmPct != null ? `${kpis.itmPct.toFixed(0)}%` : "—"}
              </div>
            </div>
            <div className="rounded-xl ring-1 ring-border bg-card/60 px-4 py-2.5">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("kpis.events")}</div>
              <div className="font-mono text-lg font-bold tabular-nums text-foreground">
                {kpis.totalEvents}
                <span className="ml-1.5 font-normal text-[10px] text-muted-foreground">
                  {t("kpis.eventsHint", { hands: kpis.totalHands.toLocaleString() })}
                </span>
              </div>
            </div>
          </section>
        )}

        {/* ── Leaks por custo ──────────────────────────────────────────── */}
        {s?.top_leaks && s.top_leaks.length > 0 && (
          <section className="rounded-xl ring-1 ring-border bg-card/60 p-4">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-3">
              {t("v2.leaksTitle")}
            </div>
            <div className="space-y-2">
              {s.top_leaks.map((l, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="font-mono text-base font-bold text-muted-foreground/60 w-5">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px]">
                      <span className="font-mono font-bold uppercase">{formatAction(l.action_taken)}</span>
                      <span className="text-muted-foreground"> → </span>
                      <span className="font-mono font-bold uppercase text-teal-300">{formatAction(l.best_action)}</span>
                      <span className="text-muted-foreground text-[11px]"> · {l.street} · {t("v2.leakSpots", { n: l.count })}</span>
                    </div>
                    <div className="mt-1 h-1 rounded-full bg-muted/20 overflow-hidden">
                      <div className="h-full rounded-full bg-red-400/70" style={{ width: `${Math.min(100, l.share_pct)}%` }} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-mono text-[13px] font-bold text-red-400">−{l.loss_bb.toFixed(1)}bb</div>
                    <div className="font-mono text-[9px] text-muted-foreground">{t("v2.leakShare", { pct: l.share_pct })}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── HUD Stats (VPIP/PFR/…) — faixa completa, casca V2. SEM gate por
            total_hands: o card tem estado vazio próprio — esconder silenciosamente
            quando a query atrasa fazia ele "sumir" do V2. ─────────────────── */}
        {hasData && <PlayerStatsCard stats={playerStats} v2 />}

        {/* ── Cards existentes em ordem fixa (reuso via renderCard) ─────── */}
        {hasData && (
          <section
            ref={gridRef}
            className="grid grid-cols-1 gap-x-6 gap-y-6 md:grid-cols-2 lg:grid-cols-12 lg:grid-flow-dense lg:auto-rows-[8px] lg:gap-y-0 items-start"
          >
            <div className="lg:col-span-8"><V2EvTrendCard evSummary={s} /></div>
            <div className="lg:col-span-4"><V2CoverageCard evSummary={s} /></div>
            <div className="lg:col-span-7"><V2AiInsightsCard insights={aiInsights} locked={aiLocked} /></div>
            <div className="lg:col-span-5"><V2StreetEvCard evSummary={s} /></div>
            {/* UX-2 onda 3 — medição GTO (anel + barras) e resultado financeiro */}
            <div className="lg:col-span-4"><V2QualityCard data={gtoQuality} pendingGto={pendingGto} /></div>
            <div className="lg:col-span-8"><V2PositionCard data={gtoPosition} /></div>
            <div className="lg:col-span-6"><V2BankrollCard /></div>
            {CARD_ORDER.map((id) => {
              const card = renderCard(id, { v2: true });
              return card ? (
                <div key={id} className={SECTION_SPAN[id as DashSection] ?? "lg:col-span-6"}>
                  {card}
                </div>
              ) : null;
            })}
          </section>
        )}

        </>
        )}
      </main>
    </div>
  );
}
