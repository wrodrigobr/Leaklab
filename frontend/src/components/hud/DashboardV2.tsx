import React, { useRef } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, Target, Zap, Brain, Loader2 } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { EmptyDashboard } from "@/components/hud/EmptyDashboard";
import { ProximoPassoBanner } from "@/components/hud/ProximoPassoBanner";
import { PlayerStatsCard } from "@/components/hud/PlayerStatsCard";
import { EvSummary, GtoQualityData, GtoPositionData, progression, type EvolutionResponse } from "@/lib/api";
import { useMasonryRows } from "@/hooks/useMasonryRows";
import { formatAction } from "@/lib/utils";
import { useSpotLabel } from "@/lib/spotLabel";
import { SECTION_SPAN, DashSection } from "@/hooks/useDashboardLayout";
import { V2EvTrendCard } from "@/components/hud/V2EvTrendCard";
import { V2StreetEvCard } from "@/components/hud/V2StreetEvCard";
import { V2AiInsightsCard, AiInsight } from "@/components/hud/V2AiInsightsCard";
import { V2QualityCard } from "@/components/hud/V2QualityCard";
import { V2PositionCard } from "@/components/hud/V2PositionCard";
import { V2PositionProfileCard } from "@/components/hud/V2PositionProfileCard";
import { ProLockCard } from "@/components/hud/ProLockCard";
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
  /** Filtro "Volume" (03/09): já regia 8 cards via prop drilling em Index.tsx, mas o
      controle visual (pastilhas) vivia no branch CLÁSSICO do dashboard — código latente,
      nunca renderizado desde que o V2 virou padrão. O dono nunca via o filtro. Renderizado
      aqui agora, no componente que de fato aparece na tela. 0 = histórico genuíno. */
  /** Opcional: a tela de Demo (dados fixos, sem refetch real) não precisa fornecer. */
  volumeLimit?: number | null;
  onVolumeLimitChange?: (v: number | null) => void;
  hasData: boolean;
  renderCard: (id: string, opts?: { v2?: boolean }) => React.ReactNode;
  gtoQuality?: GtoQualityData | null;
  gtoPosition?: GtoPositionData | null;
  /** Perfil por assento (VPIP/PFR/3bet por posicao). Opcional: a /demo nao passa. */
  positionProfile?: React.ComponentProps<typeof V2PositionProfileCard>["data"];
  /** Free ve o lock com o motivo, nao um card vazio: card vazio parece produto quebrado. */
  positionProfileLocked?: boolean;
  pendingGto?: number;
  aiInsights?: AiInsight[];
  aiLocked?: boolean;
  /** onboarding sem dados (tournsLoaded && !hasData) — mesmo EmptyDashboard do clássico */
  showEmpty?: boolean;
  /** Série de evolução já pronta. Só a tela de DEMONSTRAÇÃO passa: o dashboard do jogador deixa
      o card buscar por conta própria (ele tem o próprio filtro de período). */
  evolution?: EvolutionResponse;
  kpis?: { roi: number | null; itmPct: number | null; totalEvents: number; totalHands: number; roiLowSample?: boolean; netProfit?: number };
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

export function DashboardV2({ onUpload, evSummary, volumeLimit = 50, onVolumeLimitChange = () => {}, hasData, renderCard, gtoQuality = null, gtoPosition = null, positionProfile = null, positionProfileLocked = false, pendingGto = 0, aiInsights = [], aiLocked = false, showEmpty = false, evolution, kpis, playerStats = null, drift = null, onDismissDrift }: Props) {
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

  // A AÇÃO do hero é a missão do protocolo, não o leak mais caro.
  // O leak mais caro é DIAGNÓSTICO e frequentemente é postflop ("flop −65.9bb"); mandar
  // "treinar agora" a partir dele levava a um hub genérico e prometia treinar algo que o
  // protocolo (preflop, por família) não treina. O ranking por custo segue logo abaixo,
  // então nenhuma informação se perde — o que muda é a PROMESSA do botão.
  const { data: protocolo } = useQuery({
    queryKey: ["progression-status"],
    queryFn: () => progression.status(),
    staleTime: 60_000,
    retry: false,
    enabled: hasData,
  });
  const spotLabel = useSpotLabel();
  const missao = protocolo?.ativa ?? null;
  const gateOk = missao?.mastery.criterios.filter((c) => c.ok).length ?? 0;
  const gateTot = missao?.mastery.criterios.length ?? 5;

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader onUpload={onUpload} />
      <main className="mx-auto max-w-[1440px] space-y-6 px-4 pt-6 pb-28 md:px-8 lg:pb-8 animate-fade-in">

        <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
          {t("v2.eyebrow")}
        </div>

        {/* ── Escopo dos dados (05/09) ──────────────────────────────────────────────
            Achado do dono: "este filtro esta muito escondido, temos que pensar uma
            forma de ficar mais evidente para o jogador ver que os dados sao com base
            neste filtro". Estava em 9px mono a 60% de opacidade, no canto OPOSTO ao
            conteudo que ele rege, e nenhum card dizia de onde vinham os numeros.

            O conserto nao e aumentar o widget: e trocar o widget por uma AFIRMACAO.
            A frase diz o escopo em linguagem corrida ("estes numeros sao dos seus
            ultimos 50 torneios") e declara a AMOSTRA junto, que e a informacao que
            faltava — filtro sem amostra ainda deixa o jogador sem saber sobre quantas
            maos esta olhando. O controle fica ao lado, como ajuste da frase.

            Faixa propria, largura inteira, logo abaixo do eyebrow: o escopo vale para
            a pagina toda, entao ele nao pode morar num canto. */}
        {hasData && (
          <div
            data-tour="volume"
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2
                       rounded-lg border border-primary/25 bg-primary/[0.06] px-4 py-2.5"
          >
            <p className="text-[13px] leading-snug text-foreground">
              {volumeLimit
                ? t("volumeFilter.scopeLastN", { n: volumeLimit })
                : t("volumeFilter.scopeAll", { tourneys: (kpis?.totalEvents ?? 0).toLocaleString() })}
              {!!kpis?.totalHands && (
                <span className="text-muted-foreground">
                  {" · "}
                  {t("volumeFilter.sample", { hands: kpis.totalHands.toLocaleString() })}
                </span>
              )}
            </p>
            <div
              role="group"
              aria-label={t("volumeFilter.label")}
              className="flex items-center gap-px overflow-hidden rounded-md bg-background/50 ring-1 ring-border"
            >
              {([20, 50, 100, 0] as number[]).map((val) => {
                const label = val === 0 ? t("volumeFilter.all")
                  : val === 20 ? t("volumeFilter.last20")
                  : val === 50 ? t("volumeFilter.last50")
                  : t("volumeFilter.last100");
                const ativo = volumeLimit === val;
                return (
                  <button
                    key={val}
                    onClick={() => onVolumeLimitChange(val)}
                    aria-pressed={ativo}
                    className={`px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors ${
                      ativo
                        ? "bg-primary text-primary-foreground font-bold"
                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {showEmpty ? (
          <EmptyDashboard onComplete={onUpload} />
        ) : (
        <>

        {/* A prescrição lidera a primeira dobra (spec cobranca-proximo-passo.md §4). Usuário
            sem upload não a vê: o EmptyDashboard acima já faz o CTA certo (subir torneio). */}
        <div data-tour="proximo-passo"><ProximoPassoBanner /></div>

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

        {/* ── #29: validação GTO em andamento — stats recomputando ── */}
        {pendingGto > 0 && (
          <div className="flex items-start gap-3 rounded-xl ring-1 ring-primary/30 bg-primary/5 px-4 py-3">
            <Loader2 className="size-4 text-primary shrink-0 mt-0.5 animate-spin" aria-hidden />
            <div>
              <p className="text-sm font-medium text-foreground">{t("gtoNotice.bannerTitle")}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t(pendingGto === 1 ? "gtoNotice.bannerDesc" : "gtoNotice.bannerDesc_plural", { n: pendingGto })}
              </p>
            </div>
          </div>
        )}

        {/* ── HERO "Hoje" ───────────────────────────────────────────────── */}
        <section data-tour="hero" className="grid gap-3 md:grid-cols-3">
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

          {/* CTA: a MISSÃO do protocolo (fallback: leak mais caro, p/ quem ainda não tem missão) */}
          <div className="rounded-xl ring-1 ring-teal-500/40 bg-teal-500/5 p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-teal-300">
                <Zap className="size-3" /> {missao ? t("v2.missionLabel") : t("v2.ctaLabel")}
              </div>
              {missao ? (
                <div className="mt-1">
                  <div className="text-[13px] font-bold leading-snug text-foreground">{spotLabel(missao, { fallback: missao.titulo })}</div>
                  <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[11px]">
                    <span className="text-muted-foreground">{gateOk}/{gateTot}</span>
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-border">
                      <div className="h-full rounded-full bg-teal-400"
                        style={{ width: `${(gateOk / Math.max(1, gateTot)) * 100}%` }} />
                    </div>
                    {missao.reaberto && <span className="shrink-0 text-amber-400">{t("v2.missionReopened")}</span>}
                  </div>
                </div>
              ) : topLeak ? (
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
            {/* Costura 11: era <a href> (reload completo) e sem foco/origem — o CTA nomeava a
                missão e entregava a intro genérica. Link + deep-link com janela do protocolo. */}
            <Link
              to={missao
                ? "/leak-trainer?origem=dashboard&protocolo=1"
                : "/training"}
              className="mt-3 inline-flex items-center justify-center rounded-lg bg-teal-400 px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-[#06281f] hover:bg-teal-300 transition-colors"
            >
              {t("v2.ctaButton")}
            </Link>
          </div>
        </section>

        {/* ── KPIs secundários (ROI / ITM / volume) — chips compactos ───── */}
        {kpis && hasData && (
          <section data-tour="kpis" className="grid grid-cols-3 gap-3">
            <div className="rounded-xl ring-1 ring-border bg-card/60 px-4 py-2.5">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{kpis.roiLowSample ? t("kpis.netProfit") : t("kpis.roi")}</div>
              <div className={`font-mono text-lg font-bold tabular-nums ${
                kpis.roi == null ? "text-muted-foreground"
                  : (kpis.roiLowSample ? (kpis.netProfit ?? 0) : kpis.roi) >= 0 ? "text-teal-300" : "text-red-400"
              }`}>
                {kpis.roi == null ? "—"
                  : kpis.roiLowSample ? `${(kpis.netProfit ?? 0) >= 0 ? "+" : "−"}$${Math.abs(kpis.netProfit ?? 0).toFixed(2)}`
                  : `${kpis.roi >= 0 ? "+" : ""}${kpis.roi.toFixed(1)}%`}
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
          <section data-tour="leaks" className="rounded-xl ring-1 ring-border bg-card/60 p-4">
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
            total_hands: o card tem estado vazio próprio, esconder silenciosamente
            quando a query atrasa fazia ele "sumir" do V2. ─────────────────── */}
        {hasData && <PlayerStatsCard stats={playerStats} v2 />}

        {/* ── Cards existentes em ordem fixa (reuso via renderCard) ─────── */}
        {hasData && (
          <section
            ref={gridRef}
            className="grid grid-cols-1 gap-x-6 gap-y-6 md:grid-cols-2 lg:grid-cols-12 lg:grid-flow-dense lg:auto-rows-[8px] lg:gap-y-0 items-start"
          >
            {/* Masonry de 2 colunas uniformes: TODO card col-span-6 (ver SECTION_SPAN) —
                larguras mistas reabrem vãos. Hero cards normalizados (eram 8/4/7/5/4/8). */}
            <div className="lg:col-span-6"><V2EvTrendCard evSummary={s} /></div>
            <div className="lg:col-span-6"><V2AiInsightsCard insights={aiInsights} locked={aiLocked} /></div>
            <div className="lg:col-span-6"><V2StreetEvCard evSummary={s} /></div>
            {/* UX-2 onda 3 — medição GTO (anel + barras) e resultado financeiro */}
            <div data-tour="qualidade" className="lg:col-span-6"><V2QualityCard data={gtoQuality} pendingGto={pendingGto} /></div>
            <div className="lg:col-span-6"><V2PositionCard data={gtoPosition} /></div>
            {/* A grade de PERFIL fica colada na de ALINHAMENTO de proposito: uma diz de
                onde o jogador erra mais, a outra qual e o perfil dele ali. Perguntas
                vizinhas, respostas vizinhas. */}
            {/* col-span-full, nao lg:col-span-12: a grade e larga em QUALQUER largura, e
                fora do breakpoint lg ela dividia a linha com outro card e forcava rolagem
                horizontal (achado do dono, 05/09). Linha inteira sempre. */}
            <div className="col-span-full">
              {positionProfileLocked
                ? <ProLockCard feature={t("posProfile.title")} v2 />
                : <V2PositionProfileCard data={positionProfile} geral={playerStats} />}
            </div>
            <div className="lg:col-span-6"><V2BankrollCard data={evolution} /></div>
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
