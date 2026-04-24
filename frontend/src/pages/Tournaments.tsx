import { useMemo, useState } from "react";
import { HudLayout } from "@/components/hud/HudLayout";
import { Search, Filter, ArrowUpDown, CheckCircle2, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface Row {
  id: string;
  date: string;
  name: string;
  network: string;
  buyIn: number;
  field: number;
  finish: string;
  result: number;
  status: "analyzed" | "queued";
}

const DATA: Row[] = [
  { id: "GG-T_29384", date: "24/11 21:04", name: "GGMasters Bounty", network: "GGPoker", buyIn: 108, field: 2482, finish: "1ª", result: 1842.5, status: "analyzed" },
  { id: "PS-K_11029", date: "24/11 19:42", name: "Sunday Million PKO", network: "PokerStars", buyIn: 215, field: 12104, finish: "412ª", result: -215, status: "analyzed" },
  { id: "WPN-V_9921", date: "24/11 18:15", name: "Venom Satellite", network: "ACR", buyIn: 55, field: 450, finish: "12ª", result: 340, status: "analyzed" },
  { id: "WX-M_4421", date: "24/11 17:00", name: "Winamax Main D1C", network: "Winamax", buyIn: 125, field: 3200, finish: "—", result: 0, status: "queued" },
  { id: "GG-D_88102", date: "23/11 22:18", name: "Daily Cooldown", network: "GGPoker", buyIn: 22, field: 1800, finish: "Bust", result: -22, status: "analyzed" },
  { id: "PS-N_55021", date: "23/11 20:45", name: "Bounty Builder $55", network: "PokerStars", buyIn: 55, field: 5400, finish: "98ª", result: 412, status: "analyzed" },
  { id: "888-T_3320", date: "23/11 19:12", name: "Mystery Bounty", network: "888", buyIn: 33, field: 880, finish: "Bust", result: -33, status: "analyzed" },
  { id: "GG-S_77432", date: "22/11 21:00", name: "GG Spin & Gold High", network: "GGPoker", buyIn: 50, field: 3, finish: "1ª", result: 920, status: "analyzed" },
];

type SortKey = "date" | "buyIn" | "result" | "field";

const Tournaments = () => {
  const [query, setQuery] = useState("");
  const [network, setNetwork] = useState<string>("all");
  const [sort, setSort] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const networks = useMemo(() => ["all", ...Array.from(new Set(DATA.map((r) => r.network)))], []);

  const rows = useMemo(() => {
    let list = DATA.filter(
      (r) =>
        (network === "all" || r.network === network) &&
        (r.name.toLowerCase().includes(query.toLowerCase()) || r.id.toLowerCase().includes(query.toLowerCase()))
    );
    list = [...list].sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      if (sort === "date") return a.date.localeCompare(b.date) * dir;
      return ((a[sort] as number) - (b[sort] as number)) * dir;
    });
    return list;
  }, [query, network, sort, sortDir]);

  const totals = useMemo(() => {
    const pnl = DATA.reduce((s, r) => s + r.result, 0);
    const inv = DATA.reduce((s, r) => s + r.buyIn, 0);
    return { pnl, inv, count: DATA.length, roi: (pnl / inv) * 100 };
  }, []);

  const toggleSort = (key: SortKey) => {
    if (sort === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSort(key);
      setSortDir("desc");
    }
  };

  return (
    <HudLayout
      eyebrow="Histórico tático"
      title="Torneios"
      description="Lista completa de sessões importadas. Filtre, ordene e abra qualquer evento para análise profunda."
    >
      {/* Stats summary */}
      <section className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-4">
        {[
          { label: "Total eventos", value: totals.count.toString() },
          { label: "Investido", value: `$${totals.inv.toLocaleString()}` },
          { label: "Lucro líquido", value: `${totals.pnl >= 0 ? "+" : ""}$${totals.pnl.toLocaleString()}`, accent: totals.pnl >= 0 ? "text-primary" : "text-destructive" },
          { label: "ROI período", value: `${totals.roi >= 0 ? "+" : ""}${totals.roi.toFixed(1)}%`, accent: totals.roi >= 0 ? "text-primary" : "text-destructive" },
        ].map((s, i) => (
          <div key={i} className="bg-hud-surface p-5">
            <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground mb-2">{s.label}</div>
            <div className={cn("font-mono text-2xl font-light tabular-nums", s.accent ?? "text-foreground")}>{s.value}</div>
          </div>
        ))}
      </section>

      {/* Filters */}
      <section className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por nome ou ID…"
            className="h-10 w-full rounded-md border border-border bg-hud-surface pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
            aria-label="Buscar torneio"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="size-3.5 text-muted-foreground" aria-hidden />
          {networks.map((n) => (
            <button
              key={n}
              onClick={() => setNetwork(n)}
              className={cn(
                "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                network === n
                  ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              {n === "all" ? "Todas" : n}
            </button>
          ))}
        </div>
      </section>

      {/* Table */}
      <section className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-border bg-hud-elevated/40">
              <tr>
                {[
                  { k: "date" as SortKey, label: "Data" },
                  { k: null, label: "Torneio" },
                  { k: null, label: "Rede" },
                  { k: "buyIn" as SortKey, label: "Buy-in" },
                  { k: "field" as SortKey, label: "Field" },
                  { k: null, label: "Posição" },
                  { k: "result" as SortKey, label: "Resultado" },
                  { k: null, label: "Status" },
                ].map((c, i) => (
                  <th
                    key={i}
                    className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground"
                  >
                    {c.k ? (
                      <button
                        onClick={() => toggleSort(c.k!)}
                        className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                      >
                        {c.label}
                        <ArrowUpDown className={cn("size-3", sort === c.k && "text-primary")} aria-hidden />
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.id} className="group transition-colors hover:bg-primary/5 cursor-pointer">
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-muted-foreground">{r.date}</td>
                  <td className="px-4 py-3.5">
                    <div className="text-sm font-medium text-foreground">{r.name}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">{r.id}</div>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-muted-foreground">{r.network}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs">${r.buyIn}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-muted-foreground">{r.field.toLocaleString()}</td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-xs">{r.finish}</td>
                  <td className={cn("whitespace-nowrap px-4 py-3.5 font-mono text-xs font-medium", r.result > 0 ? "text-primary" : r.result < 0 ? "text-destructive" : "text-muted-foreground")}>
                    {r.result === 0 ? "—" : `${r.result > 0 ? "+" : ""}$${r.result.toLocaleString()}`}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3.5">
                    {r.status === "analyzed" ? (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20">
                        <CheckCircle2 className="size-3" aria-hidden />
                        Analisado
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-warning/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-warning ring-1 ring-warning/20">
                        <Clock className="size-3" aria-hidden />
                        Em fila
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-16 text-center text-sm text-muted-foreground">
                    Nenhum torneio encontrado para os filtros atuais.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </HudLayout>
  );
};

export default Tournaments;
