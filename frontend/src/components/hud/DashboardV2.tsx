import React, { useRef } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown, Target, Zap } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { EvSummary } from "@/lib/api";
import { useMasonryRows } from "@/hooks/useMasonryRows";
import { SECTION_SPAN, DashSection } from "@/hooks/useDashboardLayout";
import { V2EvTrendCard } from "@/components/hud/V2EvTrendCard";
import { V2CoverageCard } from "@/components/hud/V2CoverageCard";
import { V2StreetEvCard } from "@/components/hud/V2StreetEvCard";
import { V2AiInsightsCard, AiInsight } from "@/components/hud/V2AiInsightsCard";

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
  renderCard: (id: string) => React.ReactNode;
  onBackToClassic: () => void;
  aiInsights?: AiInsight[];
  aiLocked?: boolean;
}

// Ordem fixa opinada (UX-2 refinará): qualidade/diagnóstico → evolução → perfis → IA (Pro)
const CARD_ORDER = [
  "quality", "leakfinder", "results", "bankroll", "position",
  "dna", "pressure", "career", "cognitive", "twin", "causal_map",
];

export function DashboardV2({ onUpload, evSummary, hasData, renderCard, onBackToClassic, aiInsights = [], aiLocked = false }: Props) {
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
          <button
            onClick={onBackToClassic}
            className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 hover:text-teal-300 transition-colors"
            title={t("v2.toggleTip")}
          >
            {t("v2.backToClassic")}
          </button>
        </div>

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
                  <span className="font-mono font-bold uppercase">{topLeak.action_taken}</span>
                  <span className="text-muted-foreground"> {t("v2.insteadOf")} </span>
                  <span className="font-mono font-bold uppercase text-teal-300">{topLeak.best_action}</span>
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
                      <span className="font-mono font-bold uppercase">{l.action_taken}</span>
                      <span className="text-muted-foreground"> → </span>
                      <span className="font-mono font-bold uppercase text-teal-300">{l.best_action}</span>
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
            {CARD_ORDER.map((id) => {
              const card = renderCard(id);
              return card ? (
                <div key={id} className={SECTION_SPAN[id as DashSection] ?? "lg:col-span-6"}>
                  {card}
                </div>
              ) : null;
            })}
          </section>
        )}
      </main>
    </div>
  );
}
