import { useEffect, useState } from "react";
import { Coins, Layers, Percent, Target } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { KpiCard } from "@/components/hud/KpiCard";
import { UploadZone } from "@/components/hud/UploadZone";
import { LeaksPanel } from "@/components/hud/LeaksPanel";
import { BankrollChart } from "@/components/hud/BankrollChart";
import { RecentTournamentsTable } from "@/components/hud/RecentTournamentsTable";
import { metrics, tournaments, EvolutionResponse, Tournament } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const Index = () => {
  const { user } = useAuth();
  const [evo, setEvo] = useState<EvolutionResponse | null>(null);
  const [tourns, setTourns] = useState<Tournament[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    metrics.evolution(90).then(setEvo).catch(() => null);
    tournaments.list().then((r) => setTourns(r.tournaments)).catch(() => null);
  }, [refreshKey]);

  const handleUploadResult = () => setRefreshKey((k) => k + 1);

  // Derived KPIs
  const totalInvested = tourns.reduce((s, t) => s + (t.buy_in ?? 0), 0);
  const totalProfit = tourns.reduce((s, t) => s + (t.profit ?? 0), 0);
  const roi = totalInvested > 0 ? (totalProfit / totalInvested) * 100 : null;
  const itmCount = tourns.filter((t) => (t.profit ?? 0) > 0).length;
  const itmPct = tourns.length > 0 ? (itmCount / tourns.length) * 100 : null;
  const avgBuyIn =
    tourns.length > 0
      ? tourns.reduce((s, t) => s + (t.buy_in ?? 0), 0) / tourns.filter((t) => t.buy_in != null).length
      : null;
  const totalEvents = tourns.length;

  const hasData = tourns.length > 0;
  const syncAgo = hasData ? "há pouco" : "nunca sincronizado";

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />

      <main className="mx-auto max-w-[1440px] space-y-8 px-6 py-8 md:px-8 animate-fade-in">
        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
            <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
            {hasData ? `Sessão sincronizada • ${syncAgo}` : "Importe torneios para começar"}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            {user?.username ? `${user.username} — Centro de comando` : "Centro de comando tático"}
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Monitore métricas de performance, importe novos torneios e revise os leaks identificados
            pela IA em tempo real.
          </p>
        </section>

        <section
          aria-label="Indicadores chave"
          className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-2 lg:grid-cols-4 shadow-elevated"
        >
          <KpiCard
            index="01"
            label="Net ROI"
            value={roi != null ? (roi >= 0 ? `+${roi.toFixed(2)}` : roi.toFixed(2)) : "—"}
            delta={
              roi != null
                ? { value: `${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% total`, trend: roi >= 0 ? "up" : "down" }
                : undefined
            }
            icon={Percent}
            highlight
          />
          <KpiCard
            index="02"
            label="ITM Frequency"
            value={itmPct != null ? itmPct.toFixed(1) : "—"}
            unit={itmPct != null ? "%" : undefined}
            hint={hasData ? `Field avg ~18.5%` : "Sem dados"}
            icon={Target}
          />
          <KpiCard
            index="03"
            label="Avg Buy-In"
            value={avgBuyIn != null && !isNaN(avgBuyIn) ? avgBuyIn.toFixed(2) : "—"}
            unit={avgBuyIn != null ? "$" : undefined}
            hint={hasData ? `${tourns.filter((t) => t.buy_in != null).length} torneios` : "Sem dados"}
            icon={Coins}
          />
          <KpiCard
            index="04"
            label="Total Eventos"
            value={totalEvents > 0 ? totalEvents.toLocaleString() : "—"}
            hint={hasData ? `${tourns.reduce((s, t) => s + (t.hands_count ?? 0), 0).toLocaleString()} mãos` : "Importe torneios"}
            icon={Layers}
          />
        </section>

        <section className="grid grid-cols-1 gap-8 lg:grid-cols-12 items-start">
          <div className="space-y-8 lg:col-span-8">
            <UploadZone onResult={handleUploadResult} />
            <BankrollChart evolution={evo?.evolution} />
            <RecentTournamentsTable tournaments={tourns} />
          </div>

          <aside className="space-y-8 lg:col-span-4">
            <LeaksPanel leaks={evo?.leaks} />

            <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Confiança da IA
                </span>
                <span className="font-mono text-[10px] text-primary">
                  {hasData ? "ativo" : "sem dados"}
                </span>
              </div>
              <div className="flex gap-1">
                {Array.from({ length: 12 }).map((_, i) => {
                  const filled = hasData
                    ? Math.min(12, Math.round((totalEvents / 10) * 12))
                    : 0;
                  return (
                    <span
                      key={i}
                      className={`h-1.5 flex-1 rounded-sm ${i < filled ? "bg-primary" : "bg-border"}`}
                    />
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
      </main>

      <footer className="mx-auto mt-8 flex max-w-[1440px] items-center justify-between border-t border-border/60 px-6 py-6 md:px-8">
        <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          ENC: AES-256 • LATENCY: 14ms • SESSION_LOCKED
        </span>
        <div className="hidden gap-6 sm:flex">
          {["Documentação", "Status", "Suporte"].map((l) => (
            <a
              key={l}
              href="#"
              className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {l}
            </a>
          ))}
        </div>
      </footer>
    </div>
  );
};

export default Index;
