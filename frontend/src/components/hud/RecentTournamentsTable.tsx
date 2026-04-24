import { CheckCircle2, Clock, Eye } from "lucide-react";
import { cn } from "@/lib/utils";

interface TournamentRow {
  id: string;
  date: string;
  name: string;
  buyIn: string;
  finish: string;
  result: string;
  status: "analyzed" | "queued";
  positive: boolean;
}

const ROWS: TournamentRow[] = [
  {
    id: "GG-T_29384",
    date: "24 Nov • 21:04",
    name: "GGMasters Bounty $108",
    buyIn: "$108.00",
    finish: "1ª / 2.482",
    result: "+$1.842,50",
    status: "analyzed",
    positive: true,
  },
  {
    id: "PS-K_11029",
    date: "24 Nov • 19:42",
    name: "Sunday Million PKO",
    buyIn: "$215.00",
    finish: "412 / 12.104",
    result: "-$215,00",
    status: "analyzed",
    positive: false,
  },
  {
    id: "WPN-V_9921",
    date: "24 Nov • 18:15",
    name: "Venom PKO Satellite",
    buyIn: "$55.00",
    finish: "ITM • 12º",
    result: "+$340,00",
    status: "analyzed",
    positive: true,
  },
  {
    id: "WX-M_4421",
    date: "24 Nov • 17:00",
    name: "Winamax Main Event D1C",
    buyIn: "€125.00",
    finish: "Em jogo",
    result: "Pendente",
    status: "queued",
    positive: true,
  },
];

export function RecentTournamentsTable() {
  return (
    <section aria-labelledby="recent-tournaments" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 id="recent-tournaments" className="text-sm font-bold uppercase tracking-widest-2 text-foreground">
          Torneios recentes
        </h2>
        <button className="font-mono text-[11px] text-primary hover:text-primary-glow transition-colors">
          Ver todos →
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-border bg-hud-elevated/40">
              <tr>
                {["Data", "Torneio", "Buy-in", "Posição", "Resultado", "Status"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground"
                  >
                    {h}
                  </th>
                ))}
                <th className="sr-only">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ROWS.map((row) => (
                <tr key={row.id} className="group transition-colors hover:bg-primary/5">
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-muted-foreground">{row.date}</td>
                  <td className="px-4 py-3.5">
                    <div className="text-sm font-medium text-foreground">{row.name}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">{row.id}</div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-foreground">{row.buyIn}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-xs text-foreground">{row.finish}</td>
                  <td
                    className={cn(
                      "whitespace-nowrap px-4 py-3.5 font-mono text-xs font-medium",
                      row.positive ? "text-primary" : "text-destructive"
                    )}
                  >
                    {row.result}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3.5">
                    {row.status === "analyzed" ? (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20">
                        <CheckCircle2 className="size-3" aria-hidden />
                        Analisado
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-warning/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-warning ring-1 ring-warning/20">
                        <Clock className="size-3 animate-pulse" aria-hidden />
                        Em fila
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-right">
                    <button
                      className="inline-flex size-7 items-center justify-center rounded-sm text-muted-foreground opacity-0 transition-opacity hover:bg-secondary hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`Abrir ${row.name}`}
                    >
                      <Eye className="size-3.5" aria-hidden />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
