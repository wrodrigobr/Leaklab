import { Coins, Layers, Percent, Target } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { KpiCard } from "@/components/hud/KpiCard";
import { UploadZone } from "@/components/hud/UploadZone";
import { LeaksPanel } from "@/components/hud/LeaksPanel";
import { BankrollChart } from "@/components/hud/BankrollChart";
import { RecentTournamentsTable } from "@/components/hud/RecentTournamentsTable";

const Index = () => {
  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />

      <main className="mx-auto max-w-[1440px] space-y-8 px-6 py-8 md:px-8 animate-fade-in">
        {/* Hero / page intro */}
        <section className="flex flex-col gap-3">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
            <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
            Sessão sincronizada • há 2 min
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            Centro de comando tático
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Monitore métricas de performance, importe novos torneios e revise os leaks identificados pela IA em tempo real.
          </p>
        </section>

        {/* KPIs */}
        <section aria-label="Indicadores chave" className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-2 lg:grid-cols-4 shadow-elevated">
          <KpiCard
            index="01"
            label="Net ROI"
            value="+18.42"
            delta={{ value: "+2.4% sessão", trend: "up" }}
            icon={Percent}
            highlight
          />
          <KpiCard
            index="02"
            label="ITM Frequency"
            value="24.2"
            unit="%"
            hint="Field avg 18.5%"
            icon={Target}
          />
          <KpiCard
            index="03"
            label="Avg Buy-In"
            value="52.80"
            unit="$"
            hint="Limite: $100"
            icon={Coins}
          />
          <KpiCard
            index="04"
            label="Total Eventos"
            value="1.428"
            hint="Última sync 2m atrás"
            icon={Layers}
          />
        </section>

        {/* Main grid */}
        <section className="grid grid-cols-1 gap-8 lg:grid-cols-12 items-start">
          <div className="space-y-8 lg:col-span-8">
            <UploadZone />
            <BankrollChart />
            <RecentTournamentsTable />
          </div>

          <aside className="space-y-8 lg:col-span-4">
            <LeaksPanel />

            <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Confiança da IA
                </span>
                <span className="font-mono text-[10px] text-primary">87%</span>
              </div>
              <div className="flex gap-1">
                {Array.from({ length: 12 }).map((_, i) => (
                  <span
                    key={i}
                    className={`h-1.5 flex-1 rounded-sm ${i < 10 ? "bg-primary" : "bg-border"}`}
                  />
                ))}
              </div>
              <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                Volume amostral suficiente para sugerir ajustes confiáveis em ranges de pré-flop e c-bet.
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
            <a key={l} href="#" className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors">
              {l}
            </a>
          ))}
        </div>
      </footer>
    </div>
  );
};

export default Index;
