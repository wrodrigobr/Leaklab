import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Download, FileWarning } from "lucide-react";
import { toast } from "sonner";
import { adminDashboard, type AdminTournament } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Torneios de TODOS os usuários (admin) + download do hand history CRU em .txt.
 *
 * Uso: reproduzir na própria conta um bug reportado por um jogador — baixa o .txt e
 * reimporta pelo fluxo normal. O nome do arquivo vem do backend (padrão único, espelhado
 * em scripts/export_tournament_raw.py): {site}_{tournament_id}_{nome-do-torneio}.txt
 *
 * Privacidade: é dado de jogador. Endpoint é @require_admin e cada download fica logado
 * no servidor (quem baixou, qual torneio, de quem).
 */

const PAGE = 25;

const SITES = ["pokerstars", "ggpoker", "acr", "coinpoker", "partypoker", "888poker"];

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s.includes("T") ? s : s.replace(" ", "T"));
  return isNaN(d.getTime()) ? s : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

export function TournamentsTab() {
  const [search, setSearch] = useState("");
  const [site,   setSite]   = useState("");
  const [offset, setOffset] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-tournaments", search, site, offset],
    queryFn: () => adminDashboard.tournaments({
      limit: PAGE, offset, site: site || undefined, search: search || undefined,
    }),
    staleTime: 15_000,
  });

  const rows: AdminTournament[] = data?.tournaments ?? [];
  const total = data?.total ?? 0;

  const download = async (t: AdminTournament) => {
    setBusyId(t.id);
    try {
      await adminDashboard.downloadTournamentRaw(t.id);
      toast.success(`Hand history de ${t.username} baixado`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao baixar");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="flex flex-wrap gap-2">
        <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 flex-1 min-w-[220px]">
          <Search className="size-3.5 text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setOffset(0); }}
            placeholder="Buscar por usuário, id ou nome do torneio…"
            className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
        </div>
        <select
          value={site}
          onChange={e => { setSite(e.target.value); setOffset(0); }}
          className="rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none"
        >
          <option value="">Todas as salas</option>
          {SITES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Tabela */}
      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border bg-hud-elevated/40">
              <tr>
                {["Usuário", "Sala", "Torneio", "Hero", "Mãos", "Decisões", "Importado", "Raw"].map(h => (
                  <th key={h} className="whitespace-nowrap px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">Carregando…</td></tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">Nenhum torneio encontrado.</td></tr>
              )}
              {rows.map(t => (
                <tr key={t.id} className="transition-colors hover:bg-muted/10">
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">{t.username}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">{t.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                      {t.site}
                    </span>
                  </td>
                  <td className="max-w-[260px] px-4 py-3">
                    <div className="truncate text-foreground" title={t.tournament_name ?? undefined}>
                      {t.tournament_name || "—"}
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">#{t.tournament_id}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">{t.hero}</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-foreground">{t.hands_count}</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-muted-foreground">{t.decisions_count}</td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-[11px] text-muted-foreground">{fmtDate(t.imported_at)}</td>
                  <td className="px-4 py-3">
                    {t.has_raw ? (
                      <button
                        onClick={() => download(t)}
                        disabled={busyId === t.id}
                        title="Baixar hand history cru (.txt) para reimportar e reproduzir"
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1",
                          "font-mono text-[10px] uppercase tracking-wider text-foreground transition-colors",
                          "hover:border-primary/40 hover:text-primary disabled:opacity-50",
                        )}
                      >
                        <Download className="size-3" />
                        {busyId === t.id ? "baixando…" : ".txt"}
                      </button>
                    ) : (
                      <span
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground/60"
                        title="Import antigo, anterior ao armazenamento do hand history cru"
                      >
                        <FileWarning className="size-3" /> sem raw
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Paginação */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <span className="font-mono text-[10px] text-muted-foreground">
            {total > 0 ? `${offset + 1}–${Math.min(offset + PAGE, total)} de ${total}` : "0 torneios"}
          </span>
          <div className="flex gap-2">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(o => Math.max(0, o - PAGE))}
              className="rounded-md border border-border px-3 py-1 font-mono text-[10px] uppercase text-foreground disabled:opacity-40"
            >
              anterior
            </button>
            <button
              disabled={offset + PAGE >= total}
              onClick={() => setOffset(o => o + PAGE)}
              className="rounded-md border border-border px-3 py-1 font-mono text-[10px] uppercase text-foreground disabled:opacity-40"
            >
              próxima
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
