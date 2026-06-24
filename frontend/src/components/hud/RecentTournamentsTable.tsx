import { CheckCircle2, Clock, Eye, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { Tournament } from "@/lib/api";
import { SiteLogo } from "@/components/hud/SiteLogo";

interface Props {
  tournaments?: Tournament[];
}

function parseLocalDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  // Date-only strings (≤10 chars): use local constructor to avoid UTC-midnight day-shift
  return iso.length <= 10 ? new Date(y, m - 1, d) : new Date(iso);
}

function formatDate(iso: string | null, lang: string): string {
  if (!iso) return "—";
  try {
    const d = parseLocalDate(iso);
    const datePart = d.toLocaleDateString(lang, { day: "2-digit", month: "short" });
    if (iso.length <= 10) return datePart;
    return datePart + " • " + d.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso.slice(0, 10);
  }
}

function formatDateShort(iso: string | null, lang: string): string {
  if (!iso) return "—";
  try {
    return parseLocalDate(iso).toLocaleDateString(lang, { day: "2-digit", month: "short" });
  } catch {
    return iso.slice(0, 10);
  }
}

function formatTournamentLabel(row: Tournament): string {
  if (row.tournament_name) return row.tournament_name;
  return `#${row.tournament_id}`;
}

function formatBadge(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("spin")) return "Spin&Go";
  if (n.includes("satellite") || n.includes("satélite")) return "SAT";
  if (n.includes("knockout") || n.includes("bounty") || /\bpko\b/.test(n) || /\bko\b/.test(n)) return "KO";
  if (n.includes("sit & go") || n.includes("sit&go") || n.startsWith("sng") || /\bsng\b/.test(n)) return "SNG";
  return "MTT";
}

const DEMO_ROWS: Tournament[] = [
  { id: 1, tournament_id: "GG-T_29384", site: "GGPoker", tournament_name: "Spin&Gold #14", hero: "Hero", played_at: "2024-11-24T21:04:00", imported_at: "2024-11-24", hands_count: 120, decisions_count: 240, avg_score: 0.07, standard_pct: 0.82, clear_pct: 0.05, result: "itm", place: 1, buy_in: 108, prize: 1950, profit: 1842, llm_summary: null },
  { id: 2, tournament_id: "PS-K_11029", site: "PokerStars", tournament_name: "NLH $215", hero: "Hero", played_at: "2024-11-24T19:42:00", imported_at: "2024-11-24", hands_count: 80, decisions_count: 160, avg_score: 0.14, standard_pct: 0.71, clear_pct: 0.12, result: null, place: 412, buy_in: 215, prize: 0, profit: -215, llm_summary: null },
];

export function RecentTournamentsTable({ tournaments }: Props) {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation("dashboard");
  const lang = i18n.language;
  const rows = tournaments && tournaments.length > 0 ? tournaments.slice(0, 5) : DEMO_ROWS;
  const isDemo = !tournaments || tournaments.length === 0;

  return (
    <section aria-labelledby="recent-tournaments" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2
          id="recent-tournaments"
          className="text-sm font-bold uppercase tracking-widest-2 text-foreground"
        >
          {t("table.title")}{isDemo && <span className="ml-2 font-mono text-[10px] text-muted-foreground normal-case tracking-normal">{t("table.demo")}</span>}
        </h2>
        <button
          onClick={() => navigate("/tournaments")}
          className="font-mono text-[11px] text-primary hover:text-primary-glow transition-colors"
        >
          {t("table.viewAll")}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        {/* ── Mobile card list ──────────────────────────────────────────────── */}
        <ul className="md:hidden divide-y divide-border">
          {rows.map((row) => {
            const profit = row.profit ?? null;
            const positive = profit !== null && profit > 0;
            const analyzed = !!row.avg_score;
            return (
              <li
                key={row.id}
                className="flex items-center gap-3 px-4 py-3 hover:bg-primary/5 transition-colors cursor-pointer active:bg-primary/10"
                onClick={() => navigate(`/tournaments/${row.tournament_id}`)}
              >
                <SiteLogo site={row.site} size={16} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-sm font-medium text-foreground truncate">
                      {formatTournamentLabel(row)}
                    </span>
                    <span className="rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-muted-foreground shrink-0">
                      {formatBadge(row.tournament_name ?? "")}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {formatDateShort(row.played_at || row.imported_at, lang)}
                    </span>
                    {row.buy_in != null && (
                      <span className="font-mono text-[10px] text-muted-foreground">· ${row.buy_in}</span>
                    )}
                    {row.place != null && (
                      <span className="font-mono text-[10px] text-muted-foreground">· {row.place}º</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className={cn(
                    "font-mono text-sm font-medium tabular-nums",
                    profit === null ? "text-muted-foreground" : positive ? "text-primary" : "text-destructive"
                  )}>
                    {profit === null ? "—" : `${positive ? "+" : ""}$${Math.abs(profit).toFixed(2).replace(/\.00$/, "")}`}
                  </span>
                  {analyzed && row.labels_reconciled_at == null ? (
                    <Loader2 className="size-3.5 text-warning animate-spin" aria-label={t("table.gtoPending")} />
                  ) : analyzed ? (
                    <CheckCircle2 className="size-3.5 text-primary" aria-label={t("table.analyzed")} />
                  ) : (
                    <Clock className="size-3.5 text-warning animate-pulse" aria-label={t("table.inQueue")} />
                  )}
                </div>
              </li>
            );
          })}
        </ul>

        {/* ── Desktop table ─────────────────────────────────────────────────── */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-border bg-hud-elevated/40">
              <tr>
                {(["hDate", "hTournament", "hBuyin", "hPlace", "hResult", "hStatus"] as const).map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground"
                  >
                    {t(`table.${h}`)}
                  </th>
                ))}
                <th className="sr-only">{t("table.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => {
                const profit = row.profit ?? null;
                const positive = profit !== null && profit > 0;
                const analyzed = !!row.avg_score;
                return (
                  <tr key={row.id} className="group transition-colors hover:bg-primary/5">
                    <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-muted-foreground">
                      {formatDate(row.played_at || row.imported_at, lang)}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2">
                        <SiteLogo site={row.site} size={14} />
                        <span className="text-sm font-medium text-foreground">
                          {formatTournamentLabel(row)}
                        </span>
                        <span className="rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
                          {formatBadge(row.tournament_name ?? "")}
                        </span>
                      </div>
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {row.tournament_id}
                        {row.hands_count != null && (
                          <span className="ml-2 text-muted-foreground/60">{t("table.hands", { n: row.hands_count })}</span>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-foreground">
                      {row.buy_in != null ? `$${row.buy_in}` : "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3.5 text-xs text-foreground">
                      {row.place != null ? `${row.place}º` : "—"}
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
                        : `${positive ? "+" : ""}$${Math.abs(profit).toFixed(2).replace(/\.00$/, "")}`}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3.5">
                      {analyzed && row.labels_reconciled_at == null ? (
                        <span
                          className="inline-flex items-center gap-1 rounded-sm bg-warning/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-warning ring-1 ring-warning/20"
                          title={t("table.gtoPendingTooltip")}
                        >
                          <Loader2 className="size-3 animate-spin" aria-hidden />
                          {t("table.gtoPending")}
                        </span>
                      ) : analyzed ? (
                        <div className="inline-flex flex-col items-start gap-0.5">
                          {/* qualidade da sessão — o número que mais importa */}
                          <span className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20"
                            title={t("table.qualityTooltip")}>
                            <CheckCircle2 className="size-3" aria-hidden />
                            {row.standard_pct != null
                              ? t("table.qualitySolid", { pct: Math.round(row.standard_pct) })
                              : t("table.analyzed")}
                          </span>
                          {/* cobertura GTO separada: preflop (GW ~imediato) · postflop (cresce, em análise) */}
                          {(row.preflop_coverage_pct != null || row.postflop_coverage_pct != null) && (
                            <span className="font-mono text-[9px] font-normal text-muted-foreground/70" title={t("table.gtoSplitTooltip")}>
                              GTO
                              {row.preflop_coverage_pct != null && ` · ${t("table.covPre", { pct: Math.round(row.preflop_coverage_pct) })}`}
                              {row.postflop_coverage_pct != null && (
                                <>
                                  {" · "}
                                  {row.solver_analyzing
                                    ? <span className="text-warning/80">{t("table.gtoAnalyzing")}</span>
                                    : t("table.covPost", { pct: Math.round(row.postflop_coverage_pct) })}
                                </>
                              )}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-sm bg-warning/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-warning ring-1 ring-warning/20">
                          <Clock className="size-3 animate-pulse" aria-hidden />
                          {t("table.inQueue")}
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3.5 text-right">
                      <button
                        className="inline-flex size-7 items-center justify-center rounded-sm text-muted-foreground opacity-0 transition-opacity hover:bg-secondary hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label={t("table.open", { id: row.tournament_id })}
                      >
                        <Eye className="size-3.5" aria-hidden />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
