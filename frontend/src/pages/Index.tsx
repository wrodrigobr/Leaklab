import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Coins, Layers, Percent, Target, GraduationCap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudHeader } from "@/components/hud/HudHeader";
import { KpiCard } from "@/components/hud/KpiCard";
import { LeaksPanel } from "@/components/hud/LeaksPanel";
import { BankrollChart } from "@/components/hud/BankrollChart";
import { RecentTournamentsTable } from "@/components/hud/RecentTournamentsTable";
import { EmptyDashboard } from "@/components/hud/EmptyDashboard";
import { DecisionQualityCard } from "@/components/hud/DecisionQualityCard";
import { StreetBreakdown } from "@/components/hud/StreetBreakdown";
import { PositionChart } from "@/components/hud/PositionChart";
import { RecentForm } from "@/components/hud/RecentForm";
import { IcmBreakdown } from "@/components/hud/IcmBreakdown";
import { HudTooltip } from "@/components/hud/HudTooltip";
import { PlayerStatsCard } from "@/components/hud/PlayerStatsCard";
import { AcceptCoachModal } from "@/components/hud/AcceptCoachModal";
import { LevelCard } from "@/components/hud/LevelCard";
import { metrics, tournaments, EvolutionResponse, Tournament, BreakdownResponse, PlayerStatsResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const Index = () => {
  const { user } = useAuth();
  const { t } = useTranslation("dashboard");
  const { t: tc } = useTranslation("common");
  const [showLinkCoach, setShowLinkCoach] = useState(false);
  const [evo, setEvo]           = useState<EvolutionResponse | null>(null);
  const [breakdown, setBreakdown] = useState<BreakdownResponse | null>(null);
  const [playerStats, setPlayerStats] = useState<PlayerStatsResponse | null>(null);
  const [tourns, setTourns]     = useState<Tournament[]>([]);
  const [loading, setLoading]   = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      metrics.evolution(90).then(setEvo).catch(() => null),
      metrics.breakdown(90).then(setBreakdown).catch(() => null),
      metrics.playerStats(90).then(setPlayerStats).catch(() => null),
      tournaments.list().then((r) => setTourns(r.tournaments)).catch(() => null),
    ]).finally(() => setLoading(false));
  }, [refreshKey]);

  const handleUpload = () => setRefreshKey((k) => k + 1);

  const totalInvested = tourns.reduce((s, t) => s + (t.buy_in ?? 0), 0);
  const totalProfit   = tourns.reduce((s, t) => s + (t.profit ?? 0), 0);
  const roi           = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : null;
  const itmCount      = tourns.filter((t) => (t.profit ?? 0) > 0).length;
  const itmPct        = tourns.length > 0 ? (itmCount / tourns.length) * 100 : null;
  const totalEvents   = tourns.length;
  const totalHands    = tourns.reduce((s, t) => s + (t.hands_count ?? 0), 0);

  const stdPcts   = (evo?.evolution ?? []).map((e) => e.standard_pct).filter((v) => v != null) as number[];
  const avgStdPct = stdPcts.length > 0 ? stdPcts.reduce((a, b) => a + b, 0) / stdPcts.length : null;

  const hasData = tourns.length > 0;

  const { data: levelData } = useQuery({
    queryKey: ["player-level", refreshKey],
    queryFn: metrics.level,
    staleTime: 60_000,
  });

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader onUpload={handleUpload} />

      {showLinkCoach && <AcceptCoachModal onClose={() => setShowLinkCoach(false)} />}

      <main className="mx-auto max-w-[1440px] space-y-8 px-4 pt-8 pb-28 md:px-8 md:pb-8 animate-fade-in">
        {user?.role === "player" && !user?.coach_id && (
          <div className="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-foreground">
              <GraduationCap className="size-4 text-primary" />
              <span>{t("linkCoach.message")}</span>
            </div>
            <button
              onClick={() => setShowLinkCoach(true)}
              className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary hover:underline"
            >
              {t("linkCoach.action")}
            </button>
          </div>
        )}

        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
            <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
            {hasData ? t("eyebrow") : t("eyebrowEmpty")}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            {user?.username ? t("title", { name: user.username }) : t("titleDefault")}
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("subtitle")}
          </p>
        </section>

        <section
          aria-label="KPIs"
          className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border lg:grid-cols-4 shadow-elevated"
        >
          <KpiCard
            index="01"
            label={t("kpis.roi")}
            value={roi != null ? (roi >= 0 ? `+${roi.toFixed(2)}` : roi.toFixed(2)) : tc("labels.noData")}
            delta={roi != null ? { value: t("kpis.roiDelta", { value: `${roi >= 0 ? "+" : ""}${roi.toFixed(1)}` }), trend: roi >= 0 ? "up" : "down" } : undefined}
            icon={Percent}
            highlight
            tooltip={t("kpis.roiTooltip")}
          />
          <KpiCard
            index="02"
            label={t("kpis.itm")}
            value={itmPct != null ? `${itmPct.toFixed(1)}%` : tc("labels.noData")}
            hint={hasData ? t("kpis.itmHint") : t("kpis.noData")}
            icon={Target}
            tooltip={t("kpis.itmTooltip")}
          />
          <KpiCard
            index="03"
            label={t("kpis.standard")}
            value={avgStdPct != null ? `${avgStdPct.toFixed(1)}%` : tc("labels.noData")}
            hint={hasData ? t("kpis.standardHint") : t("kpis.noData")}
            icon={Coins}
            tooltip={t("kpis.standardTooltip")}
          />
          <KpiCard
            index="04"
            label={t("kpis.events")}
            value={totalEvents > 0 ? totalEvents.toLocaleString() : tc("labels.noData")}
            hint={hasData ? t("kpis.eventsHint", { hands: totalHands.toLocaleString() }) : t("kpis.eventsHintEmpty")}
            icon={Layers}
            tooltip={t("kpis.eventsTooltip")}
          />
        </section>

        {!loading && !hasData ? (
          <EmptyDashboard onComplete={handleUpload} />
        ) : (
          <>
          <PlayerStatsCard stats={playerStats} />

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
            <div className="space-y-6 lg:col-span-8">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <RecentForm evolution={evo?.evolution} />
                <DecisionQualityCard byLabel={breakdown?.by_label} />
              </div>

              <BankrollChart evolution={evo?.evolution} />

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <StreetBreakdown byStreet={breakdown?.by_street} />
                <PositionChart byPosition={breakdown?.by_position} />
              </div>

              <RecentTournamentsTable tournaments={tourns} />
            </div>

            <aside className="space-y-6 lg:col-span-4 order-first lg:order-none">
              {levelData?.level && <LevelCard data={levelData} showStudyLink />}
              <LeaksPanel leaks={evo?.leaks} />
              <IcmBreakdown icm={evo?.icm} />

              <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                      {t("aiConfidence.title")}
                    </span>
                    <HudTooltip content={t("aiConfidence.tooltip")} />
                  </div>
                  <span className="font-mono text-[10px] text-primary">
                    {hasData ? t("aiConfidence.active") : t("aiConfidence.noData")}
                  </span>
                </div>
                <div className="flex gap-1">
                  {Array.from({ length: 12 }).map((_, i) => {
                    const filled = hasData ? Math.min(12, Math.round((totalEvents / 10) * 12)) : 0;
                    return (
                      <span key={i} className={`h-1.5 flex-1 rounded-sm ${i < filled ? "bg-primary" : "bg-border"}`} />
                    );
                  })}
                </div>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                  {hasData
                    ? t("aiConfidence.summary", { count: totalEvents })
                    : t("aiConfidence.empty")}
                </p>
              </div>
            </aside>
          </section>
          </>
        )}
      </main>

      <footer className="mx-auto mt-8 flex max-w-[1440px] items-center justify-between border-t border-border/60 px-6 py-6 md:px-8">
        <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {tc("sessionLocked")}
        </span>
        <div className="hidden gap-6 sm:flex">
          {([tc("docs"), tc("status_page"), tc("support")] as const).map((l) => (
            <a key={l} href="#" className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors">{l}</a>
          ))}
        </div>
      </footer>
    </div>
  );
};

export default Index;
