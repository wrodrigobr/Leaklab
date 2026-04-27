import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HudLayout } from "@/components/hud/HudLayout";
import { Search, Filter, ArrowUpDown, CheckCircle2, Clock, Loader2, Trash2, AlertTriangle, GraduationCap } from "lucide-react";
import { SiteLogo } from "@/components/hud/SiteLogo";
import { cn } from "@/lib/utils";
import { tournaments as tournamentsApi, Tournament } from "@/lib/api";

type SortKey = "played_at" | "buy_in" | "profit" | "place";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return (
      d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) +
      " " +
      d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
    );
  } catch {
    return iso.slice(0, 10);
  }
}

const Tournaments = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [network, setNetwork] = useState<string>("all");
  const [sort, setSort] = useState<SortKey>("played_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [clearConfirm, setClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);

  const reload = () => {
    setLoading(true);
    tournamentsApi
      .list()
      .then((r) => setData(r.tournaments))
      .catch(() => null)
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  useEffect(() => {
    const handler = () => reload();
    window.addEventListener("leaklab:tournament-imported", handler);
    return () => window.removeEventListener("leaklab:tournament-imported", handler);
  }, []);

  const networks = useMemo(
    () => ["all", ...Array.from(new Set(data.map((t) => t.site).filter(Boolean)))],
    [data]
  );

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    let list = data.filter(
      (t) =>
        (network === "all" || t.site === network) &&
        (!q ||
          t.tournament_id.toLowerCase().includes(q) ||
          (t.tournament_name ?? "").toLowerCase().includes(q) ||
          t.hero.toLowerCase().includes(q))
    );
    list = [...list].sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      if (sort === "played_at") {
        const da = a.played_at || a.imported_at;
        const db = b.played_at || b.imported_at;
        return (da || "").localeCompare(db || "") * dir;
      }
      return ((a[sort] ?? 0) - (b[sort] ?? 0)) * dir;
    });
    return list;
  }, [data, query, network, sort, sortDir]);

  const totals = useMemo(() => {
    const pnl = data.reduce((s, t) => s + (t.profit ?? 0), 0);
    const inv = data.reduce((s, t) => s + (t.buy_in ?? 0), 0);
    return { pnl, inv, count: data.length, roi: inv > 0 ? (pnl / inv) * 100 : 0 };
  }, [data]);

  const toggleSort = (key: SortKey) => {
    if (sort === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSort(key);
      setSortDir("desc");
    }
  };

  const handleDelete = async (e: React.MouseEvent, tournamentId: string) => {
    e.stopPropagation();
    setDeletingId(tournamentId);
    try {
      await tournamentsApi.deleteOne(tournamentId);
      setData((prev) => prev.filter((t) => t.tournament_id !== tournamentId));
    } catch {
      // silently ignore — row stays
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    setClearing(true);
    try {
      await tournamentsApi.clearAll();
      setData([]);
      setClearConfirm(false);
    } catch {
      // silently ignore
    } finally {
      setClearing(false);
    }
  };

  return (
    <HudLayout
      eyebrow="Histórico tático"
      title="Torneios"
      description="Lista completa de sessões importadas. Filtre, ordene e abra qualquer evento para análise profunda."
    >
      {loading ? (
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">Carregando torneios…</span>
        </div>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-4">
            {[
              { label: "Total eventos", value: totals.count.toString() },
              { label: "Investido", value: `$${totals.inv.toLocaleString()}` },
              {
                label: "Lucro líquido",
                value: `${totals.pnl >= 0 ? "+" : ""}$${totals.pnl.toLocaleString()}`,
                accent: totals.pnl >= 0 ? "text-primary" : "text-destructive",
              },
              {
                label: "ROI período",
                value: `${totals.roi >= 0 ? "+" : ""}${totals.roi.toFixed(1)}%`,
                accent: totals.roi >= 0 ? "text-primary" : "text-destructive",
              },
            ].map((s, i) => (
              <div key={i} className="bg-hud-surface p-5">
                <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground mb-2">
                  {s.label}
                </div>
                <div className={cn("font-mono text-2xl font-light tabular-nums", s.accent ?? "text-foreground")}>
                  {s.value}
                </div>
              </div>
            ))}
          </section>

          <section className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar por ID ou herói…"
                className="h-10 w-full rounded-md border border-border bg-hud-surface pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
                aria-label="Buscar torneio"
              />
            </div>
            <div className="flex items-center gap-2 flex-wrap">
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

              {data.length > 0 && (
                <div className="ml-auto">
                  {clearConfirm ? (
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-destructive uppercase tracking-wider flex items-center gap-1">
                        <AlertTriangle className="size-3" />
                        Confirmar?
                      </span>
                      <button
                        onClick={handleClearAll}
                        disabled={clearing}
                        className="rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider bg-destructive/10 text-destructive ring-1 ring-destructive/30 hover:bg-destructive/20 transition-colors disabled:opacity-50"
                      >
                        {clearing ? "Limpando…" : "Sim, limpar tudo"}
                      </button>
                      <button
                        onClick={() => setClearConfirm(false)}
                        className="rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
                      >
                        Cancelar
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setClearConfirm(true)}
                      className="inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-destructive hover:bg-destructive/10 ring-1 ring-border transition-colors"
                    >
                      <Trash2 className="size-3" />
                      Limpar tudo
                    </button>
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-border bg-hud-surface">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="border-b border-border bg-hud-elevated/40">
                  <tr>
                    {[
                      { k: "played_at" as SortKey, label: "Data" },
                      { k: null, label: "ID" },
                      { k: null, label: "Rede" },
                      { k: "buy_in" as SortKey, label: "Buy-in" },
                      { k: "place" as SortKey, label: "Posição" },
                      { k: "profit" as SortKey, label: "Lucro" },
                      { k: null, label: "Status" },
                      { k: null, label: "" },
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
                            <ArrowUpDown
                              className={cn("size-3", sort === c.k && "text-primary")}
                              aria-hidden
                            />
                          </button>
                        ) : (
                          c.label
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rows.map((t) => {
                    const profit = t.profit ?? null;
                    const positive = profit !== null && profit > 0;
                    const isDeleting = deletingId === t.tournament_id;
                    return (
                      <tr
                        key={t.id}
                        className={cn(
                          "group transition-colors hover:bg-primary/5 cursor-pointer",
                          isDeleting && "opacity-40 pointer-events-none"
                        )}
                        onClick={() => navigate(`/tournaments/${t.tournament_id}`)}
                      >
                        <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-muted-foreground">
                          {formatDate(t.played_at)}
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-foreground">
                              {t.tournament_name ?? t.site}
                            </span>
                            {(() => {
                              const name = (t.tournament_name ?? "").toLowerCase();
                              const badge = name.includes("spin") ? "Spin&Go" : name.startsWith("sng") ? "SNG" : "MTT";
                              return (
                                <span className="rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
                                  {badge}
                                </span>
                              );
                            })()}
                          </div>
                          <div className="font-mono text-[10px] text-muted-foreground">
                            {t.tournament_id}
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <SiteLogo site={t.site} />
                        </td>
                        <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs">
                          {t.buy_in != null ? `$${t.buy_in}` : "—"}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3.5 text-xs">
                          {t.place != null ? `${t.place}º` : "—"}
                        </td>
                        <td
                          className={cn(
                            "whitespace-nowrap px-4 py-3.5 font-mono text-xs font-medium",
                            profit === null
                              ? "text-muted-foreground"
                              : positive
                              ? "text-primary"
                              : "text-destructive"
                          )}
                        >
                          {profit === null
                            ? "—"
                            : `${positive ? "+" : ""}$${Math.abs(profit).toFixed(0)}`}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3.5">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {t.avg_score != null ? (
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
                            {t.coach_reviewed && (
                              <span className="inline-flex items-center gap-1 rounded-sm bg-violet-500/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-400 ring-1 ring-violet-400/30">
                                <GraduationCap className="size-3" aria-hidden />
                                Coach
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <button
                            onClick={(e) => handleDelete(e, t.tournament_id)}
                            disabled={isDeleting}
                            className="opacity-0 group-hover:opacity-100 inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            aria-label="Deletar torneio"
                            title="Deletar torneio"
                          >
                            {isDeleting
                              ? <Loader2 className="size-3.5 animate-spin" />
                              : <Trash2 className="size-3.5" />
                            }
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {rows.length === 0 && !loading && (
                    <tr>
                      <td colSpan={8} className="px-4 py-16 text-center text-sm text-muted-foreground">
                        {data.length === 0
                          ? "Nenhum torneio importado ainda. Use o Dashboard para fazer upload."
                          : "Nenhum torneio encontrado para os filtros atuais."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </HudLayout>
  );
};

export default Tournaments;
