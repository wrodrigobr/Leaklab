import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity, BarChart2, CheckCircle2, ChevronRight, Clock,
  Download, LayoutDashboard, Loader2, Search, Shield, Users,
  GraduationCap, X, Check
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { cn } from "@/lib/utils";
import { adminDashboard, AdminUser, CoachPayout, CoachApplication } from "@/lib/api";
import { toast } from "sonner";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(cents: number) {
  return `R$ ${(cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}
function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "2-digit" });
}

// ── KPI tile ─────────────────────────────────────────────────────────────────

function KpiTile({ label, value, sub, icon: Icon, accent }: {
  label: string; value: string; sub?: string;
  icon: React.ElementType; accent?: boolean;
}) {
  return (
    <div className={cn(
      "rounded-xl border p-5 space-y-2",
      accent ? "border-primary/30 bg-primary/5" : "border-border bg-hud-surface"
    )}>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">{label}</span>
        <Icon className={cn("size-4", accent ? "text-primary" : "text-muted-foreground")} />
      </div>
      <p className={cn("text-2xl font-bold tabular-nums", accent ? "text-primary" : "text-foreground")}>{value}</p>
      {sub && <p className="font-mono text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = "overview" | "users" | "finance" | "logs" | "candidaturas";
const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "overview",      label: "Visão Geral",   icon: LayoutDashboard },
  { id: "users",         label: "Usuários",      icon: Users },
  { id: "finance",       label: "Financeiro",    icon: BarChart2 },
  { id: "logs",          label: "Logs",          icon: Activity },
  { id: "candidaturas",  label: "Candidaturas",  icon: GraduationCap },
];

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: adminDashboard.stats,
    staleTime: 30_000,
  });

  if (isLoading) return <Loading />;
  if (!data) return null;

  const plans = data.plans ?? {};
  const planTotal = Object.values(plans).reduce((a: number, b) => a + (b as number), 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <KpiTile label="MRR Estimado"      value={fmt(data.mrr_cents)}           sub={`${plans['pro'] ?? 0} usuários PRO`} icon={BarChart2} accent />
        <KpiTile label="Usuários Ativos 30d" value={String(data.active_users_30d)} sub="importaram torneios"                 icon={Activity} />
        <KpiTile label="Repasses Pendentes" value={fmt(data.pending_payouts_cents)} sub="coaches ativos"                    icon={CheckCircle2} />
        <KpiTile label="Total Players"     value={String(data.total_users)}       sub="jogadores cadastrados"               icon={Users} />
        <KpiTile label="Total Coaches"     value={String(data.total_coaches)}     sub="coaches cadastrados"                 icon={Shield} />
        <KpiTile label="Total Contas"      value={String(planTotal)}             sub="todos os planos"                     icon={LayoutDashboard} />
      </div>

      <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
        <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">Distribuição de Planos</h3>
        <div className="space-y-2">
          {Object.entries(plans).sort(([a], [b]) => a.localeCompare(b)).map(([plan, count]) => {
            const pct = planTotal > 0 ? ((count as number) / planTotal) * 100 : 0;
            return (
              <div key={plan} className="flex items-center gap-3">
                <span className="w-16 font-mono text-[10px] uppercase text-muted-foreground">{plan}</span>
                <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                  <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
                </div>
                <span className="w-10 text-right font-mono text-[10px] tabular-nums text-foreground">{count as number}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Users Tab ─────────────────────────────────────────────────────────────────

function UsersTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [plan,   setPlan]   = useState("");
  const [role,   setRole]   = useState("");
  const [offset, setOffset] = useState(0);
  const PAGE = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", search, plan, role, offset],
    queryFn: () => adminDashboard.users({ limit: PAGE, offset, plan: plan || undefined, role: role || undefined, search: search || undefined }),
    staleTime: 15_000,
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { plan?: string; suspended?: boolean } }) =>
      adminDashboard.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-users"] }); toast.success("Usuário atualizado"); },
  });

  const users: AdminUser[] = data?.users ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 flex-1 min-w-[180px]">
          <Search className="size-3.5 text-muted-foreground shrink-0" />
          <input
            value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }}
            placeholder="Buscar por nome ou email…"
            className="bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none w-full"
          />
        </div>
        <select value={plan} onChange={e => { setPlan(e.target.value); setOffset(0); }}
          className="rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none">
          <option value="">Todos os planos</option>
          {["free","pro","coach"].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={role} onChange={e => { setRole(e.target.value); setOffset(0); }}
          className="rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none">
          <option value="">Todos os roles</option>
          {["player","coach","admin"].map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="border-b border-border bg-hud-elevated/40">
              <tr>
                {["Usuário", "Role", "Plano", "Coach", "Torneios", "Último import", "Cadastro", "Ações"].map(h => (
                  <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr><td colSpan={8} className="py-12 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={8} className="py-12 text-center text-muted-foreground">Nenhum usuário encontrado.</td></tr>
              ) : users.map(u => (
                <tr key={u.id} className={cn("transition-colors hover:bg-primary/5", u.suspended && "opacity-50")}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{u.username}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">{u.email}</p>
                  </td>
                  <td className="px-4 py-3 font-mono text-muted-foreground">{u.role}</td>
                  <td className="px-4 py-3">
                    <select
                      defaultValue={u.plan}
                      onChange={e => updateMut.mutate({ id: u.id, data: { plan: e.target.value } })}
                      className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-foreground focus:outline-none"
                    >
                      {["free","pro","coach"].map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3 font-mono text-[10px] text-muted-foreground">{u.coach_username ?? "—"}</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-foreground">{u.tournament_count}</td>
                  <td className="px-4 py-3 font-mono text-muted-foreground whitespace-nowrap">{fmtDate(u.last_import)}</td>
                  <td className="px-4 py-3 font-mono text-muted-foreground whitespace-nowrap">{fmtDate(u.created_at)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => updateMut.mutate({ id: u.id, data: { suspended: !u.suspended } })}
                      className={cn(
                        "font-mono text-[10px] uppercase tracking-wider hover:underline",
                        u.suspended ? "text-primary" : "text-destructive"
                      )}
                    >
                      {u.suspended ? "Reativar" : "Suspender"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <span className="font-mono text-[10px] text-muted-foreground">{total} usuários</span>
          <div className="flex items-center gap-2">
            <button disabled={offset === 0} onClick={() => setOffset(o => Math.max(0, o - PAGE))}
              className="font-mono text-[10px] text-primary disabled:opacity-30 hover:underline">← Anterior</button>
            <span className="font-mono text-[10px] text-muted-foreground">{Math.floor(offset / PAGE) + 1} / {Math.ceil(total / PAGE) || 1}</span>
            <button disabled={offset + PAGE >= total} onClick={() => setOffset(o => o + PAGE)}
              className="font-mono text-[10px] text-primary disabled:opacity-30 hover:underline">Próxima →</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Finance Tab ───────────────────────────────────────────────────────────────

function FinanceTab() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState(() => new Date().toISOString().slice(0, 7));

  const { data, isLoading } = useQuery({
    queryKey: ["admin-finance", period],
    queryFn: () => adminDashboard.coachPayouts(period),
    staleTime: 30_000,
  });

  const payMut = useMutation({
    mutationFn: (paymentId: number) => adminDashboard.markPaid(paymentId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-finance"] }); toast.success("Marcado como pago"); },
  });

  const payouts: CoachPayout[] = data?.payouts ?? [];
  const totalPending = data?.total_pending_cents ?? 0;

  const exportUrl = `/admin/finance/export.csv?period=${period}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">Período</label>
          <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:border-primary" />
        </div>
        <a href={exportUrl} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors">
          <Download className="size-3.5" /> Exportar CSV
        </a>
        {totalPending > 0 && (
          <span className="font-mono text-[10px] text-primary">Total pendente: {fmt(totalPending)}</span>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="px-4 py-3 border-b border-border bg-hud-elevated/40 flex items-center justify-between">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Repasses de Coaches — {period}</span>
          <span className="font-mono text-[10px] text-muted-foreground">1–3 alunos: zerado · 4–9: R$15/aluno · 10+: R$20/aluno</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="border-b border-border">
              <tr>
                {["Coach", "Plano", "Alunos vinculados", "Alunos ativos", "Valor (R$)", "Status", ""].map(h => (
                  <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr><td colSpan={7} className="py-12 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
              ) : payouts.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center text-muted-foreground">Nenhum coach cadastrado.</td></tr>
              ) : payouts.map(p => (
                <tr key={p.id} className="hover:bg-primary/5 transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{p.display_name || p.username}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">@{p.username}</p>
                  </td>
                  <td className="px-4 py-3 font-mono text-muted-foreground">{p.plan}</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-foreground text-center">{p.total_students}</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-center">
                    <span className={cn("font-bold", p.active_students > 0 ? "text-primary" : "text-muted-foreground")}>
                      {p.active_students}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono tabular-nums font-bold text-foreground">
                    {p.amount_cents > 0 ? fmt(p.amount_cents) : p.active_students > 0 ? "Zerado" : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {p.status === "paid" ? (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20">
                        <CheckCircle2 className="size-3" /> Pago
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-warning/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-warning ring-1 ring-warning/20">
                        <Clock className="size-3" /> Pendente
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {p.status !== "paid" && p.payment_id && (
                      <button
                        onClick={() => payMut.mutate(p.payment_id!)}
                        disabled={payMut.isPending}
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-primary hover:underline disabled:opacity-50"
                      >
                        {payMut.isPending ? <Loader2 className="size-3 animate-spin" /> : <ChevronRight className="size-3" />}
                        Marcar pago
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Logs Tab ──────────────────────────────────────────────────────────────────

function LogsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-logs"],
    queryFn: () => adminDashboard.logs(100),
    staleTime: 30_000,
  });

  const logs = data?.logs ?? [];

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
      <div className="px-4 py-3 border-b border-border bg-hud-elevated/40">
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Últimas Importações</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="border-b border-border">
            <tr>
              {["Data", "Usuário", "Plano", "Rede", "Torneio", "Mãos"].map(h => (
                <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr><td colSpan={6} className="py-12 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">Nenhuma importação encontrada.</td></tr>
            ) : logs.map(l => (
              <tr key={l.id} className="hover:bg-primary/5 transition-colors">
                <td className="px-4 py-2.5 font-mono text-muted-foreground whitespace-nowrap">{fmtDate(l.imported_at)}</td>
                <td className="px-4 py-2.5 text-foreground font-medium">{l.username}</td>
                <td className="px-4 py-2.5 font-mono text-muted-foreground">{l.plan}</td>
                <td className="px-4 py-2.5 font-mono text-muted-foreground">{l.site}</td>
                <td className="px-4 py-2.5 font-mono text-muted-foreground">{l.tournament_id}</td>
                <td className="px-4 py-2.5 font-mono tabular-nums text-foreground">{l.hands_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────

function Loading() {
  return (
    <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
      <Loader2 className="size-5 animate-spin text-primary" />
      <span className="font-mono text-xs uppercase tracking-wider">Carregando…</span>
    </div>
  );
}

// ── Candidaturas Tab (BACK-018) ───────────────────────────────────────────────

function CandidaturasTab() {
  const qc = useQueryClient();
  const [status, setStatus]     = useState<"pending" | "approved" | "rejected">("pending");
  const [noteMap, setNoteMap]   = useState<Record<number, string>>({});
  const [expanded, setExpanded] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-coach-applications", status],
    queryFn: () => adminDashboard.coachApplications(status),
    staleTime: 30_000,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-coach-applications"] });

  const approveMut = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      adminDashboard.approveApplication(id, note),
    onSuccess: () => { toast.success("Candidatura aprovada"); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const rejectMut = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      adminDashboard.rejectApplication(id, note),
    onSuccess: () => { toast.success("Candidatura rejeitada"); invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const apps: CoachApplication[] = data?.applications ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        {(["pending", "approved", "rejected"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={cn(
              "rounded-full px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors",
              status === s
                ? "bg-primary text-primary-foreground"
                : "bg-hud-surface text-muted-foreground hover:text-foreground border border-border"
            )}
          >
            {s === "pending" ? "Pendentes" : s === "approved" ? "Aprovadas" : "Rejeitadas"}
          </button>
        ))}
      </div>

      {isLoading && <Loading />}

      {!isLoading && apps.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">Nenhuma candidatura {status === "pending" ? "pendente" : status === "approved" ? "aprovada" : "rejeitada"}.</p>
      )}

      <div className="space-y-3">
        {apps.map((app) => (
          <div key={app.id} className="rounded-xl border border-border bg-hud-surface overflow-hidden">
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-primary/5 transition-colors"
              onClick={() => setExpanded(expanded === app.id ? null : app.id)}
            >
              <div className="flex items-center gap-3">
                <GraduationCap className="size-4 text-primary shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-foreground">{app.username}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{app.email}{app.instagram_handle ? ` · ${app.instagram_handle}` : ""}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="font-mono text-[9px] text-muted-foreground">
                  {new Date(app.created_at).toLocaleDateString("pt-BR")}
                </span>
                {status === "pending" && (
                  <div className="flex gap-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); approveMut.mutate({ id: app.id, note: noteMap[app.id] }); }}
                      disabled={approveMut.isPending}
                      className="flex items-center gap-1 rounded bg-primary/10 px-2 py-1 font-mono text-[10px] font-bold text-primary hover:bg-primary/20 transition-colors"
                    >
                      <Check className="size-3" /> Aprovar
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); if (!noteMap[app.id]) { setExpanded(app.id); } else { rejectMut.mutate({ id: app.id, note: noteMap[app.id] }); } }}
                      disabled={rejectMut.isPending}
                      className="flex items-center gap-1 rounded bg-destructive/10 px-2 py-1 font-mono text-[10px] font-bold text-destructive hover:bg-destructive/20 transition-colors"
                    >
                      <X className="size-3" /> Rejeitar
                    </button>
                  </div>
                )}
              </div>
            </div>

            {expanded === app.id && (
              <div className="border-t border-border px-4 py-4 space-y-3 bg-background/40">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="font-mono text-[9px] uppercase text-muted-foreground mb-1">Bio</p>
                    <p className="text-foreground leading-relaxed">{app.bio || "—"}</p>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <p className="font-mono text-[9px] uppercase text-muted-foreground mb-1">Especialidades</p>
                      <p className="text-foreground">{app.specialties || "—"}</p>
                    </div>
                    <div>
                      <p className="font-mono text-[9px] uppercase text-muted-foreground mb-1">Experiência</p>
                      <p className="text-foreground">{app.experience_years ? `${app.experience_years} anos` : "—"}</p>
                    </div>
                    {app.biggest_results && (
                      <div>
                        <p className="font-mono text-[9px] uppercase text-muted-foreground mb-1">Resultados</p>
                        <p className="text-foreground">{app.biggest_results}</p>
                      </div>
                    )}
                  </div>
                </div>

                {app.admin_note && (
                  <p className="font-mono text-[10px] text-muted-foreground border-t border-border pt-2">
                    Nota: {app.admin_note}
                  </p>
                )}

                {status === "pending" && (
                  <div className="space-y-2 border-t border-border pt-3">
                    <label className="font-mono text-[10px] uppercase text-muted-foreground">
                      Nota para o candidato (opcional — enviada no email de rejeição)
                    </label>
                    <input
                      value={noteMap[app.id] ?? ""}
                      onChange={(e) => setNoteMap((m) => ({ ...m, [app.id]: e.target.value }))}
                      placeholder="ex: Perfil insuficiente, experiência não verificável..."
                      className="h-9 w-full rounded-md border border-border bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => approveMut.mutate({ id: app.id, note: noteMap[app.id] })}
                        disabled={approveMut.isPending}
                        className="flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 font-mono text-[11px] font-bold text-primary-foreground disabled:opacity-50"
                      >
                        <Check className="size-3" /> Aprovar
                      </button>
                      <button
                        onClick={() => rejectMut.mutate({ id: app.id, note: noteMap[app.id] })}
                        disabled={rejectMut.isPending}
                        className="flex items-center gap-1.5 rounded bg-destructive/10 px-3 py-1.5 font-mono text-[11px] font-bold text-destructive disabled:opacity-50"
                      >
                        <X className="size-3" /> Rejeitar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

const AdminDashboard = () => {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />
      <main className="mx-auto max-w-[1440px] space-y-6 px-4 pt-8 pb-28 md:px-8 md:pb-8 animate-fade-in">
        <header className="flex flex-col gap-3">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
            <Shield className="size-3.5" />
            Admin
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Painel Administrativo</h1>
          <p className="text-sm text-muted-foreground">Métricas operacionais, gestão de usuários e repasses de coaches.</p>
        </header>

        {/* Tabs */}
        <div className="flex overflow-x-auto border-b border-border gap-0 scrollbar-none">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex shrink-0 items-center gap-2 px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors ${
                tab === t.id
                  ? "text-primary border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </button>
          ))}
        </div>

        {tab === "overview" && <OverviewTab />}
        {tab === "users"    && <UsersTab />}
        {tab === "finance"  && <FinanceTab />}
        {tab === "logs"          && <LogsTab />}
        {tab === "candidaturas"  && <CandidaturasTab />}
      </main>
    </div>
  );
};

export default AdminDashboard;
