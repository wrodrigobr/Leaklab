import { useEffect, useRef, useState } from "react";
import { EVENTO_LOTE } from "@/lib/refreshOnImport";
import { useQuery } from "@tanstack/react-query";
import { Coins, Layers, Percent, Target, GraduationCap, Brain, RotateCcw, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, DragEndEvent } from "@dnd-kit/core";
import { SortableContext, rectSortingStrategy, arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { HudHeader } from "@/components/hud/HudHeader";
import { DashboardV2 } from "@/components/hud/DashboardV2";
import { KpiCard } from "@/components/hud/KpiCard";
import { EmptyDashboard } from "@/components/hud/EmptyDashboard";
import { RitualDaSessao } from "@/components/hud/RitualDaSessao";
import { PlayerStatsCard } from "@/components/hud/PlayerStatsCard";
import { AcceptCoachModal } from "@/components/hud/AcceptCoachModal";
import { OnboardingModal } from "@/components/hud/OnboardingModal";
import { SupportModal } from "@/components/hud/SupportModal";
import { ProfileCompletionCard } from "@/components/hud/ProfileCompletionCard";
import { DraggableCard } from "@/components/hud/DraggableCard";
import { useDashboardLayout, DashSection, SECTION_SPAN } from "@/hooks/useDashboardLayout";
import { useMasonryRows } from "@/hooks/useMasonryRows";
import { makeRenderCard } from "@/components/hud/dashboardCards";
import { metrics, tournaments, support, EvolutionResponse, Tournament, PlayerStatsResponse, PositionProfileResponse, LeakRoiData, PressureProfile, ConfidenceDrift, PlayerDnaResponse, LeakGraphResponse, CareerProjection, CognitiveFailureData, StrategicTwinProfile, GtoAlignmentData, GtoPositionData, GtoQualityData, ResultsVsGtoData, LeakFinderData, SessionContextData } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { shouldShowDrift, readDriftSeen, writeDriftSeen } from "@/lib/driftDismiss";

// Module-level cache — survives unmount/remount during SPA navigation
let _cachedTourns: Tournament[] | null = null;

const Index = () => {
  const { user, refreshUser } = useAuth();
  const { t, i18n } = useTranslation("dashboard");
  const { t: tc } = useTranslation("common");
  // Insights avançados de IA são exclusivos do Pro (espelha o gate do backend). Free vê lock.
  const isFree = (user?.plan || "free") === "free";
  const [showLinkCoach, setShowLinkCoach]   = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showSupport, setShowSupport]       = useState(false);

  // Quem decide o modal de primeiro acesso é o efeito, não o inicializador do useState: o
  // inicializador congela o valor da PRIMEIRA renderização, e `!user?.onboarding_completed`
  // com `user` ainda nulo dá `true` — abriria o onboarding para um perfil que ainda não
  // chegou. Começar em `false` erra para o lado de não mostrar nada até saber quem é.
  // O efeito depende do BOOLEANO (não do objeto): um refreshUser que devolva o mesmo estado
  // não reabre o modal que o jogador acabou de fechar. `null` = ainda não sei, não decide.
  const onboardingDone = user ? !!user.onboarding_completed : null;
  useEffect(() => {
    if (onboardingDone === null) return;
    setShowOnboarding(!onboardingDone);
  }, [onboardingDone]);

  const { data: supportCount } = useQuery({
    queryKey: ["admin-support-count"],
    queryFn:  support.unreadCount,
    refetchInterval: 120_000,
    enabled: user?.role === "admin",
  });
  const openTickets = supportCount?.open ?? 0;

  const [evo, setEvo]                     = useState<EvolutionResponse | null>(null);
  const [playerStats, setPlayerStats]     = useState<PlayerStatsResponse | null>(null);
  const [posProfile, setPosProfile]       = useState<PositionProfileResponse | null>(null);
  const [tourns, setTourns]               = useState<Tournament[]>(_cachedTourns ?? []);
  const [leakRoi, setLeakRoi]             = useState<LeakRoiData[]>([]);
  const [leakSource, setLeakSource]       = useState<'gto' | 'heuristic' | null>(null);
  const [pressureData, setPressureData]   = useState<PressureProfile | null>(null);
  const [driftData, setDriftData]         = useState<ConfidenceDrift | null>(null);

  // Dismiss por MARCA D'ÁGUA (ver lib/driftDismiss): guarda o maior id de sessão em drift já
  // dispensado e só reabre com um id MAIOR. A chave por fingerprint anterior mudava sozinha
  // quando a janela de 30 dias deslizava e a composição das sessões marcadas mudava — o jogador
  // fechava e o alerta voltava sem nada ter sido detectado.
  const [driftSeen, setDriftSeen] = useState(() => readDriftSeen(user?.user_id));
  const [dnaData, setDnaData]             = useState<PlayerDnaResponse | null>(null);
  const [leakGraph, setLeakGraph]         = useState<LeakGraphResponse | null>(null);
  const [careerData, setCareerData]       = useState<CareerProjection | null>(null);
  const [cognitiveData, setCognitiveData] = useState<CognitiveFailureData | null>(null);
  const [twinData, setTwinData]           = useState<StrategicTwinProfile | null>(null);
  const [sessionData, setSessionData]     = useState<SessionContextData | null>(null);
  const [loading, setLoading]             = useState(true);
  const [tournsLoaded, setTournsLoaded]   = useState(_cachedTourns !== null);
  const [refreshKey, setRefreshKey]       = useState(0);
  // 03/09 (unificação pós-auditoria): default RECENTE (50), não "Todos" — sem isto, quem
  // melhorou ao longo dos meses carregava o passado ruim pra sempre nos números. `0` = botão
  // "Histórico", explícito (não é mais o default silencioso). `null` só existe transitoriamente
  // (nunca setado pela UI) e cai no fallback de 90 dias do backend.
  const [volumeLimit, setVolumeLimit]     = useState<number | null>(50);

  // A marca d'água é por USUÁRIO (não por detecção), então só precisa reler quando o usuário muda.
  useEffect(() => { setDriftSeen(readDriftSeen(user?.user_id)); }, [user?.user_id]);

  const showDrift = shouldShowDrift(
    !!driftData?.drift_detected, driftData?.latest_flagged_id, driftSeen);
  const dismissDrift = () => {
    writeDriftSeen(user?.user_id, driftData?.latest_flagged_id);
    setDriftSeen(readDriftSeen(user?.user_id));
  };

  useEffect(() => {
    setLoading(true);
    const ln = volumeLimit ?? undefined;
    Promise.all([
      metrics.evolution(90, ln).then(setEvo).catch(() => null),
      metrics.playerStats(90, ln).then(setPlayerStats).catch(() => null),
      // Pro: nem chama quando e free — o backend responderia 402 e a UI ja mostra o
      // lock pelo plano do usuario. Request que se sabe que vai falhar e ruido.
      isFree ? Promise.resolve(null)
             : metrics.playerStatsByPosition(90, ln).then(setPosProfile).catch(() => null),
      metrics.leakRoi(90, ln).then((r) => { setLeakRoi(r.leaks); setLeakSource(r.source); }).catch(() => null),
      metrics.pressureProfile(90).then(setPressureData).catch(() => null),
      metrics.confidenceDrift(30).then(setDriftData).catch(() => null),
      tournaments.list().then((r) => { _cachedTourns = r.tournaments; setTourns(r.tournaments); setTournsLoaded(true); }).catch(() => null),
      metrics.dna(90).then(setDnaData).catch(() => null),
      metrics.leakGraph(90, i18n.language).then(setLeakGraph).catch(() => null),
      metrics.career(i18n.language).then(setCareerData).catch(() => null),
      metrics.cognitiveFailures(i18n.language).then(setCognitiveData).catch(() => null),
      metrics.strategicTwin(i18n.language).then(setTwinData).catch(() => null),
      metrics.sessionContext().then(setSessionData).catch(() => null),
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

  // A fila de upload é global (sobrevive à navegação); ela dispara este evento a cada import
  // concluído. O dashboard recarrega ao ouvir, no lugar do antigo callback onComplete/onUpload.
  useEffect(() => {
    // Escuta o LOTE, não cada arquivo. Antes era por arquivo, e um dia de 14 uploads disparava 14
    // ciclos completos do dashboard, ~17s de backend cada. Ver `lib/refreshOnImport`.
    const h = () => setRefreshKey((k) => k + 1);
    window.addEventListener(EVENTO_LOTE, h);
    return () => window.removeEventListener(EVENTO_LOTE, h);
  }, []);

  // DashboardV2 é o layout PADRÃO (decisão de produto). O clássico abaixo permanece como
  // código latente (não renderizado) — sem toggle. useState mantém dashV2 como variável de
  // runtime (não literal) p/ o branch do clássico não virar código inalcançável no lint.
  const [dashV2] = useState<boolean>(true);
  // Bloco "Hoje" (headline, sólidas, leak mais caro, tendência, sangria por street) agora usa
  // o MESMO `volumeLimit` do filtro "Volume" que já regia os outros cards — 03/09, unificação
  // pós-auditoria (antes eram dois controles fazendo a mesma coisa com convenções diferentes).
  const { data: evSummary } = useQuery({
    queryKey: ["ev-summary", refreshKey, volumeLimit],
    queryFn: () => metrics.evSummary(volumeLimit ?? undefined),
    staleTime: 120_000,
    enabled: dashV2,
  });

  const { sections, updateSections, reset: resetLayout } = useDashboardLayout();
  const bentoRef = useRef<HTMLElement>(null);
  // masonry real: cada card ocupa N linhas pela sua altura → curtos liberam o vão, dense empacota
  useMasonryRows(bentoRef, [sections]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const from = sections.indexOf(active.id as DashSection);
    const to   = sections.indexOf(over.id   as DashSection);
    if (from !== -1 && to !== -1) updateSections(arrayMove(sections, from, to));
  };

  // KPIs derived from tourns — slice to last N when volumeLimit is set
  const visibleTourns = volumeLimit ? tourns.slice(-volumeLimit) : tourns;
  // ROI: numerador e denominador sobre o MESMO conjunto (só torneios com buy-in conhecido),
  // senão lucro de torneio sem buy_in entra sem o investimento e infla o ROI.
  const ratedTourns   = visibleTourns.filter((t) => (t.buy_in ?? 0) > 0);
  const totalInvested = ratedTourns.reduce((s, t) => s + (t.buy_in ?? 0), 0);
  const totalProfit   = ratedTourns.reduce((s, t) => s + (t.profit ?? 0), 0);
  const roi           = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : null;
  // ROI% só é representativo com volume; abaixo do mínimo um único cash distorce (ex.: n=2 → +958%).
  // Nesse caso mostramos o LUCRO ABSOLUTO (sempre honesto) em vez do percentual.
  const ROI_MIN_SAMPLE = 30;
  const roiLowSample  = ratedTourns.length > 0 && ratedTourns.length < ROI_MIN_SAMPLE;
  const netProfit     = totalProfit;
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

  const { data: leakFinderData } = useQuery<LeakFinderData>({
    queryKey: ["leak-finder", refreshKey, volumeLimit],
    queryFn: () => metrics.leakFinder(volumeLimit ?? undefined),
    staleTime: 120_000,
  });

  // O mapa de cards vive em `dashboardCards` desde que a tela de demonstração passou a precisar
  // dos MESMOS cards com dados de outra origem. Cópia de vitrine mente sozinha quando um card
  // muda, sem quebrar nada.
  // Ancora do submenu do AI Coach (30/08): os cards carregam async, entao o scroll espera o
  // alvo EXISTIR no DOM em vez de disparar no mount e mirar no vazio.
  useEffect(() => {
    const alvo = window.location.hash.slice(1);
    if (!alvo) return;
    let tentativas = 0;
    const tenta = () => {
      const el = document.getElementById(alvo);
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
      if (tentativas++ < 20) setTimeout(tenta, 250);
    };
    tenta();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const renderCard = makeRenderCard({
    evo, leakRoi, leakSource, pressureData, dnaData, leakGraph, careerData, cognitiveData,
    twinData, sessionData, gtoQualityData, gtoPositionData, resultsVsGtoData, leakFinderData,
    pendingGto,
  }, { isFree, tc });

  /* O convite para vincular coach tinha o MESMO defeito do modal de primeiro acesso: o
     `setShowLinkCoach(true)` só existia dentro do return clássico, que nunca roda desde que o
     V2 virou padrão. O modal `AcceptCoachModal` já estava nos dois ramos; faltava quem o
     abrisse. Agora o gatilho mora aqui, junto dos modais, e serve os dois. */
  const convitePraCoach = user?.role === "player" && !user?.coach_id ? (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
      <div className="flex items-center gap-2 text-sm text-foreground">
        <GraduationCap className="size-4 shrink-0 text-primary" />
        <span>{t("linkCoach.message")}</span>
      </div>
      <button
        onClick={() => setShowLinkCoach(true)}
        className="shrink-0 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary hover:underline"
      >
        {t("linkCoach.action")}
      </button>
    </div>
  ) : null;

  // Modais globais do dashboard: ficam FORA do ramo V2/clássico.
  // `dashV2` é fixo em true (o clássico é código latente), e os modais viviam só no return do
  // clássico — o do primeiro acesso nunca chegou ao DOM desde que o V2 virou padrão. Quem
  // renderizar um modal novo põe AQUI, não dentro de um dos dois returns.
  const modaisGlobais = (
    <>
      {showLinkCoach   && <AcceptCoachModal  onClose={() => setShowLinkCoach(false)} />}
      {showOnboarding  && <OnboardingModal   onClose={() => setShowOnboarding(false)} />}
    </>
  );

  if (dashV2) {
    return (
      <>
      {modaisGlobais}
      {convitePraCoach && (
        <div className="mx-auto max-w-[1440px] px-4 pt-6 md:px-8">{convitePraCoach}</div>
      )}
      <DashboardV2
        onUpload={handleUpload}
        evSummary={evSummary ?? null}
        volumeLimit={volumeLimit}
        onVolumeLimitChange={setVolumeLimit}
        hasData={hasData}
        renderCard={renderCard}
        gtoQuality={gtoQualityData}
        gtoPosition={gtoPositionData}
        pendingGto={pendingGto}
        showEmpty={tournsLoaded && !hasData}
        kpis={{ roi, itmPct, totalEvents, totalHands, roiLowSample, netProfit }}
        playerStats={playerStats}
        positionProfile={posProfile}
        positionProfileLocked={isFree}
        drift={showDrift && driftData
          ? { detected: true, sessions: driftData.affected_sessions }
          : null}
        onDismissDrift={dismissDrift}
        aiLocked={isFree}
        aiInsights={[
          twinData?.narrative      && { key: "twin",      title: t("v2.aiTwin"),      text: twinData.narrative },
          cognitiveData?.narrative && { key: "cognitive", title: t("v2.aiCognitive"), text: cognitiveData.narrative },
          careerData?.narrative    && { key: "career",    title: t("v2.aiCareer"),    text: careerData.narrative },
          leakGraph?.narrative     && { key: "causal",    title: t("v2.aiCausal"),    text: leakGraph.narrative },
        ].filter(Boolean) as { key: string; title: string; text: string }[]}
      />
      </>
    );
  }

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader onUpload={handleUpload} />

      {modaisGlobais}

      <main className="mx-auto max-w-[1440px] space-y-8 px-4 pt-8 pb-28 md:px-8 lg:pb-8 animate-fade-in">
        {convitePraCoach}

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
              {hasData ? t("eyebrow") : t("eyebrowEmpty")}
            </div>
            {hasData && (
              <div className="flex items-center gap-2">
                {/* Volume filter — 0 = histórico genuíno (03/09: antes era `null`, que
                    secretamente caía no fallback de 90 dias do backend; "Todos" mentia). */}
                <div className="flex items-center gap-px rounded-md ring-1 ring-border overflow-hidden">
                  {([20, 50, 100, 0] as number[]).map((val) => {
                    const label = val === 0 ? t("volumeFilter.all")
                      : val === 20 ? t("volumeFilter.last20")
                      : val === 50 ? t("volumeFilter.last50")
                      : t("volumeFilter.last100");
                    return (
                      <button
                        key={String(val)}
                        onClick={() => setVolumeLimit(val)}
                        className={`px-3 py-2.5 sm:px-2.5 sm:py-1.5 font-mono text-[9px] uppercase tracking-widest transition-colors ${
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

        {showDrift && driftData && (
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
              onClick={dismissDrift}
              className="shrink-0 font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              aria-label={t("drift.dismiss")}
            >
              ✕
            </button>
          </div>
        )}


        {user?.role === "player" && <ProfileCompletionCard />}

        {/* Ritual da sessão (30/08): check-in antes de jogar, debriefing no import seguinte.
            O torneio mais recente decide se o laço fecha. */}
        {user?.role === "player" && hasData && (
          <RitualDaSessao
            ultimoTorneioId={tourns[0]?.id ?? null}
            ultimoImportadoEm={tourns[0]?.imported_at ?? null}
          />
        )}

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
                label={roiLowSample ? t("kpis.netProfit") : t("kpis.roi")}
                value={
                  roi == null ? tc("labels.noData")
                  : roiLowSample ? `${netProfit >= 0 ? "+" : "−"}$${Math.abs(netProfit).toFixed(2)}`
                  : `${roi >= 0 ? "+" : ""}${roi.toFixed(2)}%`
                }
                delta={
                  roi == null ? undefined
                  : roiLowSample ? { value: t("kpis.lowSample"), trend: "flat" }
                  : { value: t("kpis.roiDelta", { value: `${roi >= 0 ? "+" : ""}${roi.toFixed(1)}` }), trend: roi >= 0 ? "up" : "down" }
                }
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
                <span>{t(pendingGto === 1 ? "pendingGto.notice" : "pendingGto.notice_plural", {
                  n: pendingGto,
                  // ETA como faixa honesta (não promessa): ancorada no throughput do cron
                  // (~10 spots por ciclo de 5 min). Bucket por N de spots pendentes.
                  eta: t(
                    pendingGto <= 10 ? "pendingGto.eta.minutes"
                    : pendingGto <= 40 ? "pendingGto.eta.halfHour"
                    : pendingGto <= 100 ? "pendingGto.eta.hour"
                    : "pendingGto.eta.hours"
                  ),
                })}</span>
              </div>
            )}

            <PlayerStatsCard stats={playerStats} />

            {/* ── Bento: grid único 12-col com packing (grid-flow-dense) ──────── */}
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={sections} strategy={rectSortingStrategy}>
                <section
                  ref={bentoRef}
                  aria-label="Dashboard"
                  className="grid grid-cols-1 gap-x-6 gap-y-6 md:grid-cols-2 lg:grid-cols-12 lg:grid-flow-dense lg:auto-rows-[8px] lg:gap-y-0 items-start"
                >
                  {sections.map((id) => {
                    const node = renderCard(id);
                    if (!node) return null;   // ex.: causal_map sem grafo suficiente
                    return (
                      <DraggableCard key={id} id={id} className={SECTION_SPAN[id]}>
                        {node}
                      </DraggableCard>
                    );
                  })}
                </section>
              </SortableContext>
            </DndContext>
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
