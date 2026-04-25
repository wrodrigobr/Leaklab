import { useEffect, useState } from "react";
import { Coins, Layers, Percent, Target } from "lucide-react";
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
import { metrics, tournaments, EvolutionResponse, Tournament, BreakdownResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const Index = () => {
  const { user } = useAuth();
  const [evo, setEvo]           = useState<EvolutionResponse | null>(null);
  const [breakdown, setBreakdown] = useState<BreakdownResponse | null>(null);
  const [tourns, setTourns]     = useState<Tournament[]>([]);
  const [loading, setLoading]   = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      metrics.evolution(90).then(setEvo).catch(() => null),
      metrics.breakdown(90).then(setBreakdown).catch(() => null),
      tournaments.list().then((r) => setTourns(r.tournaments)).catch(() => null),
    ]).finally(() => setLoading(false));
  }, [refreshKey]);

  const handleUpload = () => setRefreshKey((k) => k + 1);

  // KPIs
  const totalInvested = tourns.reduce((s, t) => s + (t.buy_in ?? 0), 0);
  const totalProfit   = tourns.reduce((s, t) => s + (t.profit ?? 0), 0);
  const roi           = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : null;
  const itmCount      = tourns.filter((t) => (t.profit ?? 0) > 0).length;
  const itmPct        = tourns.length > 0 ? (itmCount / tourns.length) * 100 : null;
  const totalEvents   = tourns.length;
  const totalHands    = tourns.reduce((s, t) => s + (t.hands_count ?? 0), 0);

  // standard_pct já está em escala 0-100 no banco (ex: 84.3 = 84.3%)
  const stdPcts   = (evo?.evolution ?? []).map((e) => e.standard_pct).filter((v) => v != null) as number[];
  const avgStdPct = stdPcts.length > 0 ? stdPcts.reduce((a, b) => a + b, 0) / stdPcts.length : null;

  const hasData = tourns.length > 0;

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader onUpload={handleUpload} />

      <main className="mx-auto max-w-[1440px] space-y-8 px-6 py-8 md:px-8 animate-fade-in">
        {/* Hero */}
        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
            <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
            {hasData ? "Sessão sincronizada" : "Importe torneios para começar"}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            {user?.username ? `${user.username} — Centro de comando` : "Centro de comando tático"}
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Monitore métricas de performance, importe novos torneios e revise os leaks identificados
            pela IA em tempo real.
          </p>
        </section>

        {/* KPIs */}
        <section
          aria-label="Indicadores chave"
          className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-2 lg:grid-cols-4 shadow-elevated"
        >
          <KpiCard
            index="01"
            label="Net ROI"
            value={roi != null ? (roi >= 0 ? `+${roi.toFixed(2)}` : roi.toFixed(2)) : "—"}
            delta={roi != null ? { value: `${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% total`, trend: roi >= 0 ? "up" : "down" } : undefined}
            icon={Percent}
            highlight
            tooltip="Retorno sobre investimento acumulado. ROI positivo significa que você está lucrando acima do buy-in médio. Referência: jogadores regulares consistentes ficam entre +20% e +80% em MTTs."
          />
          <KpiCard
            index="02"
            label="ITM Frequency"
            value={itmPct != null ? `${itmPct.toFixed(1)}%` : "—"}
            hint={hasData ? "Field avg ~18.5%" : "Sem dados"}
            icon={Target}
            tooltip="Percentual de torneios em que você terminou no dinheiro (in-the-money). A média do field é ~18%. Acima de 22% sugere jogo sólido ou conservador; abaixo pode indicar bust-out precoce."
          />
          <KpiCard
            index="03"
            label="Standard %"
            value={avgStdPct != null ? `${avgStdPct.toFixed(1)}%` : "—"}
            hint={hasData ? "decisões dentro do range" : "Sem dados"}
            icon={Coins}
            tooltip="Percentual médio de decisões classificadas como 'standard' (score ≤ 0.08). Meta: acima de 70%. Abaixo de 60% indica volume significativo de erros que estão custando EV real."
          />
          <KpiCard
            index="04"
            label="Total Eventos"
            value={totalEvents > 0 ? totalEvents.toLocaleString() : "—"}
            hint={hasData ? `${totalHands.toLocaleString()} mãos` : "Importe torneios"}
            icon={Layers}
            tooltip="Volume total de torneios analisados. Amostras menores que 30 torneios podem ter resultados financeiros distorcidos por variância. A análise de decisões é confiável a partir de ~500 mãos."
          />
        </section>

        {!loading && !hasData ? (
          <EmptyDashboard onComplete={handleUpload} />
        ) : (
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">

            {/* Coluna principal */}
            <div className="space-y-6 lg:col-span-8">
              {/* Forma recente + qualidade lado a lado */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <RecentForm evolution={evo?.evolution} />
                <DecisionQualityCard byLabel={breakdown?.by_label} />
              </div>

              {/* Gráfico de bankroll */}
              <BankrollChart evolution={evo?.evolution} />

              {/* Street + Position lado a lado */}
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <StreetBreakdown byStreet={breakdown?.by_street} />
                <PositionChart byPosition={breakdown?.by_position} />
              </div>

              {/* Tabela de torneios recentes */}
              <RecentTournamentsTable tournaments={tourns} />
            </div>

            {/* Sidebar */}
            <aside className="space-y-6 lg:col-span-4">
              <LeaksPanel leaks={evo?.leaks} />
              <IcmBreakdown icm={evo?.icm} />

              {/* Confiança da IA */}
              <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                      Confiança da IA
                    </span>
                    <HudTooltip content="Indica a confiabilidade das análises baseada no volume de dados. Quanto mais torneios importados, mais precisas as recomendações de leaks e plano de estudos." />
                  </div>
                  <span className="font-mono text-[10px] text-primary">
                    {hasData ? "ativo" : "sem dados"}
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
                    ? `${totalEvents} torneios analisados. Volume suficiente para sugerir ajustes confiáveis.`
                    : "Importe torneios para ativar a análise de confiança da IA."}
                </p>
              </div>
            </aside>
          </section>
        )}
      </main>

      <footer className="mx-auto mt-8 flex max-w-[1440px] items-center justify-between border-t border-border/60 px-6 py-6 md:px-8">
        <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          ENC: AES-256 • LATENCY: 14ms • SESSION_LOCKED
        </span>
        <div className="hidden gap-6 sm:flex">
          {["Documentação", "Status", "Suporte"].map((l) => (
            <a key={l} href="#" className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors">{l}</a>
          ))}
        </div>
      </footer>
    </div>
  );
};

export default Index;
