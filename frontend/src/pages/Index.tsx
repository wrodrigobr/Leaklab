import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Coins, Layers, Percent, Target, GraduationCap, Brain, RotateCcw, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, DragEndEvent } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { HudHeader } from "@/components/hud/HudHeader";
import { KpiCard } from "@/components/hud/KpiCard";
import { LeaksPanel } from "@/components/hud/LeaksPanel";
import { BankrollChart } from "@/components/hud/BankrollChart";
import { EmptyDashboard } from "@/components/hud/EmptyDashboard";
import { GtoPositionCard } from "@/components/hud/GtoPositionCard";
import { IcmBreakdown } from "@/components/hud/IcmBreakdown";
import { PlayerStatsCard } from "@/components/hud/PlayerStatsCard";
import { GtoAlignmentCard } from "@/components/hud/GtoAlignmentCard";
import { GtoAlignmentMatrixCard } from "@/components/hud/GtoAlignmentMatrixCard";
import { ResultsVsGtoCard } from "@/components/hud/ResultsVsGtoCard";
import { GtoQualityCard } from "@/components/hud/GtoQualityCard";
import { AcceptCoachModal } from "@/components/hud/AcceptCoachModal";
import { OnboardingModal } from "@/components/hud/OnboardingModal";
import { SupportModal } from "@/components/hud/SupportModal";
import { PressureProfileCard } from "@/components/hud/PressureProfileCard";
import { PlayerDnaCard } from "@/components/hud/PlayerDnaCard";
import { DailyFocusCard } from "@/components/hud/DailyFocusCard";
import { ProfileCompletionCard } from "@/components/hud/ProfileCompletionCard";
import { LeakCausalMap } from "@/components/hud/LeakCausalMap";
import { CareerGraphCard } from "@/components/hud/CareerGraphCard";
import { CognitiveFailureCard } from "@/components/hud/CognitiveFailureCard";
import { StrategicTwinCard } from "@/components/hud/StrategicTwinCard";
import { DraggableCard } from "@/components/hud/DraggableCard";
import { useDashboardLayout, MainSection, SidebarSection } from "@/hooks/useDashboardLayout";
import { metrics, tournaments, support, EvolutionResponse, Tournament, PlayerStatsResponse, LeakRoiData, PressureProfile, ConfidenceDrift, PlayerDnaResponse, LeakGraphResponse, CareerProjection, CognitiveFailureData, StrategicTwinProfile, GtoAlignmentData, GtoPositionData, GtoQualityData, GtoAlignmentMatrixData, ResultsVsGtoData } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Module-level cache — survives unmount/remount during SPA navigation
let _cachedTourns: Tournament[] | null = null;

const Index = () => {
  const { user, refreshUser } = useAuth();
  const { t, i18n } = useTranslation("dashboard");
  const { t: tc } = useTranslation("common");
  const [showLinkCoach, setShowLinkCoach]   = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(() => !user?.onboarding_completed);
  const [showSupport, setShowSupport]       = useState(false);

  const { data: supportCount } = useQuery({
    queryKey: ["admin-support-count"],
    queryFn:  support.unreadCount,
    refetchInterval: 120_000,
    enabled: user?.role === "admin",
  });
  const openTickets = supportCount?.open ?? 0;

  const [evo, setEvo]                     = useState<EvolutionResponse | null>(null);
  const [playerStats, setPlayerStats]     = useState<PlayerStatsResponse | null>(null);
  const [tourns, setTourns]               = useState<Tournament[]>(_cachedTourns ?? []);
  const [leakRoi, setLeakRoi]             = useState<LeakRoiData[]>([]);
  const [leakSource, setLeakSource]       = useState<'gto' | 'heuristic' | null>(null);
  const [pressureData, setPressureData]   = useState<PressureProfile | null>(null);
  const [driftData, setDriftData]         = useState<ConfidenceDrift | null>(null);

  // Persist drift dismiss in localStorage keyed by user+data fingerprint so it
  // auto-resets whenever a new tournament is uploaded and affected_sessions changes.
  const driftKey = user?.id && driftData?.drift_detected
    ? `leaklab_drift_dismissed_${user.id}_${driftData.affected_sessions}`
    : null;
  const [driftDismissed, setDriftDismissed] = useState(
    () => driftKey ? localStorage.getItem(driftKey) === "1" : false
  );
  const [dnaData, setDnaData]             = useState<PlayerDnaResponse | null>(null);
  const [leakGraph, setLeakGraph]         = useState<LeakGraphResponse | null>(null);
  const [careerData, setCareerData]       = useState<CareerProjection | null>(null);
  const [cognitiveData, setCognitiveData] = useState<CognitiveFailureData | null>(null);
  const [twinData, setTwinData]           = useState<StrategicTwinProfile | null>(null);
  const [loading, setLoading]             = useState(true);
  const [tournsLoaded, setTournsLoaded]   = useState(_cachedTourns !== null);
  const [refreshKey, setRefreshKey]       = useState(0);
  const [volumeLimit, setVolumeLimit]     = useState<number | null>(null); // null = Todos

  // Reset dismiss state whenever fresh data arrives (new upload)
  useEffect(() => {
    if (!driftKey) return;
    setDriftDismissed(localStorage.getItem(driftKey) === "1");
  }, [driftKey]);

  useEffect(() => {
    setLoading(true);
    const ln = volumeLimit ?? undefined;
    Promise.all([
      metrics.evolution(90, ln).then(setEvo).catch(() => null),
      metrics.playerStats(90, ln).then(setPlayerStats).catch(() => null),
      metrics.leakRoi(90, ln).then((r) => { setLeakRoi(r.leaks); setLeakSource(r.source); }).catch(() => null),
      metrics.pressureProfile(90).then(setPressureData).catch(() => null),
      metrics.confidenceDrift(30).then(setDriftData).catch(() => null),
      tournaments.list().then((r) => { _cachedTourns = r.tournaments; setTourns(r.tournaments); setTournsLoaded(true); }).catch(() => null),
      metrics.dna(90).then(setDnaData).catch(() => null),
      metrics.leakGraph(90, i18n.language).then(setLeakGraph).catch(() => null),
      metrics.career(i18n.language).then(setCareerData).catch(() => null),
      metrics.cognitiveFailures(i18n.language).then(setCognitiveData).catch(() => null),
      metrics.strategicTwin(i18n.language).then(setTwinData).catch(() => null),
    ]).finally(() => setLoading(false));
  }, [refreshKey, volumeLimit]);

  // Re-fetch only language-sensitive AI narratives when locale changes
  const langMounted = useRef(false);
  useEffect(() => {
    if (!langMounted.current) { langMounted.current = true; return; }
    metrics.leakGraph(90, i18n.language).then(setLeakGraph).catch(() => null);
    metrics.career(i18n.language).then(setCareerData).catch(() => null);
    metrics.cognitiveFailures(i18n.language).then(setCognitiveData).catch(() => null);
    metrics.strategicTwin(i18n.language).then(setTwinData).catch(() => null);
  }, [i18n.language]);

  const handleUpload = () => setRefreshKey((k) => k + 1);

  const { layout, updateMain, updateSidebar, reset: resetLayout } = useDashboardLayout();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleMainDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const from = layout.main.indexOf(active.id as MainSection);
    const to   = layout.main.indexOf(over.id   as MainSection);
    if (from !== -1 && to !== -1) updateMain(arrayMove(layout.main, from, to));
  };

  const handleSidebarDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const from = layout.sidebar.indexOf(active.id as SidebarSection);
    const to   = layout.sidebar.indexOf(over.id   as SidebarSection);
    if (from !== -1 && to !== -1) updateSidebar(arrayMove(layout.sidebar, from, to));
  };

  // KPIs derived from tourns — slice to last N when volumeLimit is set
  const visibleTourns = volumeLimit ? tourns.slice(-volumeLimit) : tourns;
  const totalInvested = visibleTourns.reduce((s, t) => s + (t.buy_in ?? 0), 0);
  const totalProfit   = visibleTourns.reduce((s, t) => s + (t.profit ?? 0), 0);
  const roi           = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : null;
  const itmCount      = visibleTourns.filter((t) => (t.profit ?? 0) > 0).length;
  const itmPct        = visibleTourns.length > 0 ? (itmCount / visibleTourns.length) * 100 : null;
  const totalEvents   = visibleTourns.length;
  const totalHands    = visibleTourns.reduce((s, t) => s + (t.hands_count ?? 0), 0);

  const hasData = tourns.length > 0;

  const { data: pendingGtoData } = useQuery({
    queryKey: ["pending-gto", refreshKey],
    queryFn: metrics.pendingGtoCount,
    staleTime: 30_000,
    refetchInterval: (query) => (query.state.data?.pending ?? 0) > 0 ? 30_000 : false,
  });
  const pendingGto = pendingGtoData?.pending ?? 0;

  const { data: gtoAlignmentData } = useQuery<GtoAlignmentData>({
    queryKey: ["gto-alignment", refreshKey, volumeLimit],
    queryFn: () => metrics.gtoAlignment(volumeLimit ?? undefined),
    staleTime: 120_000,
  });

  const gtoAligned = gtoAlignmentData && gtoAlignmentData.total_with_gto >= 10
    ? gtoAlignmentData.overall_aligned_pct
    : null;

  const { data: gtoPositionData } = useQuery<GtoPositionData>({
    queryKey: ["gto-position", refreshKey, volumeLimit],
    queryFn: () => metrics.gtoPosition(volumeLimit ?? undefined),
    staleTime: 120_000,
  });

  const { data: gtoMatrixData } = useQuery<GtoAlignmentMatrixData>({
    queryKey: ["gto-matrix", refreshKey, volumeLimit],
    queryFn: () => metrics.gtoAlignmentMatrix(volumeLimit ?? undefined),
    staleTime: 120_000,
  });

  const { data: gtoQualityData } = useQuery<GtoQualityData>({
    queryKey: ["gto-quality", refreshKey, volumeLimit],
    queryFn: () => metrics.gtoQuality(volumeLimit ?? undefined),
    staleTime: 120_000,
  });

  const { data: resultsVsGtoData } = useQuery<ResultsVsGtoData>({
    queryKey: ["results-vs-gto", refreshKey, volumeLimit],
    queryFn: () => metrics.resultsVsGto(volumeLimit ?? undefined),
    staleTime: 120_000,
  });

  const renderMainRow = (id: MainSection) => {
    if (id === "quality_row") return <GtoQualityCard data={gtoQualityData} pendingGto={pendingGto} />;
    if (id === "bankroll_row") return <BankrollChart />;
    if (id === "street_row") return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <GtoAlignmentCard data={gtoAlignmentData} pendingGto={pendingGto} />
          <GtoPositionCard data={gtoPositionData} pendingGto={pendingGto} />
        </div>
        <GtoAlignmentMatrixCard data={gtoMatrixData} />
        <ResultsVsGtoCard data={resultsVsGtoData} />
      </div>
    );
    if (id === "dna_row") return <PlayerDnaCard data={dnaData} />;
    if (id === "drill_row") return (
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <PressureProfileCard data={pressureData} />
        <IcmBreakdown icm={evo?.icm} />
      </div>
    );
    if (id === "insight_row") return (
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <CareerGraphCard data={careerData ?? { insufficient_data: true, tournament_count: 0 }} />
        <CognitiveFailureCard data={cognitiveData ?? { insufficient_data: true, patterns: [], total_decisions: 0 }} />
      </div>
    );
    return null;
  };

  const renderSidebarCard = (id: SidebarSection) => {
    if (id === "leaks") return (
      <DraggableCard key={id} id={id}>
        <LeaksPanel leaks={leakRoi.length > 0 ? leakRoi : evo?.leaks} source={leakRoi.length > 0 ? leakSource : null} />
      </DraggableCard>
    );
    if (id === "pressure") return (
      <DraggableCard key={id} id={id}>
        <PressureProfileCard data={pressureData} />
      </DraggableCard>
    );
    if (id === "icm") return (
      <DraggableCard key={id} id={id}>
        <IcmBreakdown icm={evo?.icm} />
      </DraggableCard>
    );
    if (id === "causal_map") return leakGraph && leakGraph.nodes.length >= 3 ? (
      <DraggableCard key={id} id={id}>
        <LeakCausalMap
          nodes={leakGraph.nodes}
          edges={leakGraph.edges}
          narrative={leakGraph.narrative}
        />
      </DraggableCard>
    ) : <div key={id} />;
    if (id === "level") return null;
    if (id === "twin") return (
      <DraggableCard key={id} id={id}>
        <StrategicTwinCard data={twinData ?? { insufficient_data: true, total_decisions: 0 }} />
      </DraggableCard>
    );
    return null;
  };

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader onUpload={handleUpload} />

      {showLinkCoach   && <AcceptCoachModal  onClose={() => setShowLinkCoach(false)} />}
      {showOnboarding  && <OnboardingModal   onClose={() => setShowOnboarding(false)} />}

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
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
              {hasData ? t("eyebrow") : t("eyebrowEmpty")}
            </div>
            {hasData && (
              <div className="flex items-center gap-2">
                {/* Volume filter */}
                <div className="flex items-center gap-px rounded-md ring-1 ring-border overflow-hidden">
                  {([null, 20, 50, 100] as (number | null)[]).map((val) => {
                    const label = val === null ? t("volumeFilter.all")
                      : val === 20 ? t("volumeFilter.last20")
                      : val === 50 ? t("volumeFilter.last50")
                      : t("volumeFilter.last100");
                    return (
                      <button
                        key={String(val)}
                        onClick={() => setVolumeLimit(val)}
                        className={`px-2.5 py-1.5 font-mono text-[9px] uppercase tracking-widest transition-colors ${
                          volumeLimit === val
                            ? "bg-primary/20 text-primary"
                            : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
                <button
                  onClick={resetLayout}
                  title={tc("actions.resetLayout")}
                  className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground ring-1 ring-border hover:text-foreground hover:ring-primary/40 transition-colors"
                >
                  <RotateCcw className="size-3" />
                  {tc("actions.resetLayout")}
                </button>
              </div>
            )}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            {t("title")}
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("subtitle")}
          </p>
          {user?.coach_id && user.role !== "coach" && user.coach_username && (
            <div className="flex items-center gap-2 self-start rounded-full bg-primary/10 px-3 py-1.5 ring-1 ring-primary/20">
              <GraduationCap className="size-3.5 text-primary" />
              <span className="font-mono text-[10px] font-medium uppercase tracking-widest text-primary">
                {user.coach_username}
              </span>
            </div>
          )}
        </section>

        {driftData?.drift_detected && !driftDismissed && (
          <div className="flex items-start justify-between gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-4 py-3">
            <div className="flex items-start gap-2">
              <Brain className="size-4 text-yellow-400 shrink-0 mt-0.5" aria-hidden />
              <div>
                <p className="text-sm font-medium text-foreground">{t("drift.alertTitle")}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t("drift.alertDesc", { n: driftData.affected_sessions })}
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                if (driftKey) localStorage.setItem(driftKey, "1");
                setDriftDismissed(true);
              }}
              className="shrink-0 font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              aria-label={t("drift.dismiss")}
            >
              ✕
            </button>
          </div>
        )}

        {hasData && <DailyFocusCard />}

        {user?.role === "player" && <ProfileCompletionCard />}

        {tournsLoaded && !hasData ? (
          <EmptyDashboard onComplete={handleUpload} />
        ) : (
          <>
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
                hint={t("kpis.itmHint")}
                icon={Target}
                tooltip={t("kpis.itmTooltip")}
              />
              <KpiCard
                index="03"
                label={t("kpis.standard")}
                value={gtoAligned != null ? `${gtoAligned.toFixed(1)}%` : tc("labels.noData")}
                hint={gtoAligned != null ? t("kpis.standardHint", { pct: gtoAlignmentData?.overall_coverage_pct ?? 0 }) : undefined}
                icon={Coins}
                tooltip={t("kpis.standardTooltip")}
              />
              <KpiCard
                index="04"
                label={t("kpis.events")}
                value={totalEvents > 0 ? totalEvents.toLocaleString() : tc("labels.noData")}
                hint={t("kpis.eventsHint", { hands: totalHands.toLocaleString() })}
                icon={Layers}
                tooltip={t("kpis.eventsTooltip")}
              />
            </section>

            {pendingGto > 0 && (
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground font-mono">
                <Loader2 className="size-3 animate-spin shrink-0 text-primary/60" />
                <span>{t(pendingGto === 1 ? "pendingGto.notice" : "pendingGto.notice_plural", { n: pendingGto })}</span>
              </div>
            )}

            <PlayerStatsCard stats={playerStats} />

            <section className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
              {/* ── Main column (sortable rows) ──────────────────────────────── */}
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleMainDragEnd}>
                <SortableContext items={layout.main} strategy={verticalListSortingStrategy}>
                  <div className="space-y-6 lg:col-span-8">
                    {layout.main.map((id) => (
                      <DraggableCard key={id} id={id}>
                        {renderMainRow(id)}
                      </DraggableCard>
                    ))}
                  </div>
                </SortableContext>
              </DndContext>

              {/* ── Sidebar (sortable cards) ─────────────────────────────────── */}
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleSidebarDragEnd}>
                <SortableContext items={layout.sidebar} strategy={verticalListSortingStrategy}>
                  <aside className="space-y-6 lg:col-span-4 order-first lg:order-none">
                    {layout.sidebar.map(renderSidebarCard)}
                  </aside>
                </SortableContext>
              </DndContext>
            </section>
          </>
        )}
      </main>

      <footer className="mx-auto mt-8 flex max-w-[1440px] items-center justify-end border-t border-border/60 px-6 py-6 md:px-8">
        <div className="flex gap-6">
          <a href="/docs" className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors">{tc("docs")}</a>
          <button
            onClick={() => setShowSupport(true)}
            className="relative font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            {tc("support")}
            {openTickets > 0 && (
              <span className="absolute -top-2 -right-3 flex size-4 items-center justify-center rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground">
                {openTickets > 9 ? "9+" : openTickets}
              </span>
            )}
          </button>
        </div>
      </footer>

      {showSupport && <SupportModal onClose={() => setShowSupport(false)} />}
    </div>
  );
};

export default Index;
