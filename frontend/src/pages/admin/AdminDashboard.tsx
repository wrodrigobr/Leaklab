import React, { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity, BarChart2, CheckCircle2, Clock,
  LayoutDashboard, Loader2, RefreshCw, Search, Shield, Users,
  GraduationCap, X, Check, MessageSquarePlus, Trash2, AlertTriangle,
  Cpu, CircleDot
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { HudHeader } from "@/components/hud/HudHeader";
import { cn } from "@/lib/utils";
import { adminDashboard, AdminUser, AdminCoachStudent, CoachApplication, support } from "@/lib/api";
import { toast } from "sonner";
import { AdminSidebar, AdminSection, NavGroup } from "@/components/admin/AdminSidebar";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { FinanceCockpit } from "@/components/admin/FinanceCockpit";
import { CoachesTab } from "@/components/admin/CoachesTab";

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

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: adminDashboard.stats,
    staleTime: 30_000,
  });
  const { data: demo } = useQuery({
    queryKey: ["admin-demographics"],
    queryFn: adminDashboard.demographics,
    staleTime: 60_000,
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

      {demo && (
        <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">Perfis Demográficos</h3>
            <span className="font-mono text-[10px] text-muted-foreground">{demo.profiles_completed}/{demo.total_players} preenchidos ({demo.completion_rate}%)</span>
          </div>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Top Países</p>
              {demo.top_countries.slice(0, 5).map((c) => (
                <div key={c.country} className="flex items-center gap-2">
                  <span className="flex-1 text-xs text-foreground truncate">{c.country}</span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{c.n}</span>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Tipo de Jogo</p>
              {demo.game_types.map((g) => (
                <div key={g.main_game_type} className="flex items-center gap-2">
                  <span className="flex-1 text-xs text-foreground uppercase font-mono">{g.main_game_type}</span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{g.n}</span>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Faixa de Buy-in</p>
              {demo.buyin_ranges.map((b) => (
                <div key={b.usual_buyin_range} className="flex items-center gap-2">
                  <span className="flex-1 text-xs text-foreground uppercase font-mono">{b.usual_buyin_range}</span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{b.n}</span>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Origem (UTM)</p>
              {(demo.acquisition || []).map((a) => (
                <div key={a.source} className="flex items-center gap-2">
                  <span className="flex-1 text-xs text-foreground font-mono">{a.source}</span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{a.n}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Delete User Modal ─────────────────────────────────────────────────────────

interface DeleteTarget { id: number; username: string; email: string; }

function DeleteUserModal({ target, onClose, onDeleted }: {
  target: DeleteTarget;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [deleting, setDeleting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDelete = async () => {
    if (!password.trim()) { setError("Digite sua senha administrativa"); return; }
    setDeleting(true);
    setError("");
    try {
      await adminDashboard.deleteUser(target.id, password.trim());
      onDeleted();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao excluir");
      setDeleting(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md rounded-2xl border border-destructive/30 bg-hud-surface p-6 shadow-2xl space-y-5">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="size-5 text-destructive" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Excluir usuário permanentemente</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Esta ação é <strong className="text-destructive">irreversível</strong>. Todos os torneios,
              decisões e dados de <strong className="text-foreground">@{target.username}</strong> ({target.email}) serão apagados.
            </p>
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            Confirme com sua senha administrativa
          </label>
          <input
            ref={inputRef}
            type="password"
            value={password}
            onChange={e => { setPassword(e.target.value); setError(""); }}
            onKeyDown={e => e.key === "Enter" && handleDelete()}
            placeholder="Sua senha..."
            autoFocus
            className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-destructive"
          />
          {error && <p className="font-mono text-[10px] text-destructive">{error}</p>}
        </div>

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            disabled={deleting}
            className="rounded-md border border-border px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting || !password.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
          >
            {deleting ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
            {deleting ? "Excluindo…" : "Excluir definitivamente"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Billing standing badge (thin wrapper over the shared StatusBadge) ──────────

function BillingStandingBadge({ standing }: { standing?: string | null }) {
  return <StatusBadge kind={standing ?? "free"} />;
}

// ── Coach roster modal ────────────────────────────────────────────────────────

function CoachStudentsModal({ coachId, coachName, onClose }: {
  coachId: number;
  coachName: string;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-coach-students", coachId],
    queryFn: () => adminDashboard.coachStudents(coachId),
    staleTime: 15_000,
  });
  const students: AdminCoachStudent[] = data?.students ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in p-4" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl border border-border bg-hud-surface p-6 shadow-2xl space-y-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <GraduationCap className="size-5 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">Alunos de @{coachName}</h2>
          </div>
          <button onClick={onClose} className="rounded p-1 text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-4" />
          </button>
        </div>

        <div className="overflow-hidden rounded-xl border border-border">
          <div className="max-h-[60vh] overflow-y-auto">
            <table className="w-full text-xs text-left">
              <thead className="sticky top-0 border-b border-border bg-hud-elevated/80 backdrop-blur">
                <tr>
                  {["Aluno", "Plano", "Pagamento", "Vínculo"].map(h => (
                    <th key={h} className="px-4 py-2.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading ? (
                  <tr><td colSpan={4} className="py-10 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
                ) : students.length === 0 ? (
                  <tr><td colSpan={4} className="py-10 text-center text-muted-foreground">Nenhum aluno vinculado.</td></tr>
                ) : students.map(s => (
                  <tr key={s.id} className="hover:bg-primary/5 transition-colors">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-foreground">@{s.username}</p>
                      <p className="font-mono text-[10px] text-muted-foreground">{s.email}</p>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground uppercase">{s.plan}</td>
                    <td className="px-4 py-2.5"><BillingStandingBadge standing={s.billing_standing} /></td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground">{s.link_status ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Users Tab ─────────────────────────────────────────────────────────────────

function UsersTab() {
  const qc = useQueryClient();
  const [search, setSearch]       = useState("");
  const [plan,   setPlan]         = useState("");
  const [role,   setRole]         = useState("");
  const [billing, setBilling]     = useState("");
  const [offset, setOffset]       = useState(0);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [coachTarget, setCoachTarget] = useState<{ id: number; name: string } | null>(null);
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

  const allUsers: AdminUser[] = data?.users ?? [];
  // billing_standing filter is applied client-side (not a backend list param).
  const users = billing ? allUsers.filter(u => (u.billing_standing ?? "free") === billing) : allUsers;
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
        <select value={billing} onChange={e => { setBilling(e.target.value); setOffset(0); }}
          className="rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none">
          <option value="">Pagamento (todos)</option>
          <option value="paying">Em dia</option>
          <option value="past_due">Atrasado</option>
          <option value="perk">Cortesia</option>
          <option value="free">Free</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="border-b border-border bg-hud-elevated/40">
              <tr>
                {["Usuário", "Role", "Plano", "Pagamento", "Coach", "Torneios", "Último import", "Cadastro", "Ações", ""].map(h => (
                  <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr><td colSpan={10} className="py-12 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={10} className="py-12 text-center text-muted-foreground">Nenhum usuário encontrado.</td></tr>
              ) : users.map(u => (
                <tr key={u.id} className={cn("transition-colors hover:bg-primary/5", u.suspended && "opacity-50")}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{u.display_name || u.username}</p>
                    {u.display_name && <p className="font-mono text-[10px] text-muted-foreground">@{u.username}</p>}
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
                  <td className="px-4 py-3"><BillingStandingBadge standing={u.billing_standing} /></td>
                  <td className="px-4 py-3 font-mono text-[10px] text-muted-foreground">
                    {u.coach_username
                      ? (u.coach_id != null
                          ? <button
                              onClick={() => setCoachTarget({ id: u.coach_id!, name: u.coach_username! })}
                              className="inline-flex items-center gap-1 text-primary hover:underline"
                            >
                              <GraduationCap className="size-3" /> {u.coach_username}
                            </button>
                          : u.coach_username)
                      : "—"}
                    {u.role === "coach" && (
                      <button
                        onClick={() => setCoachTarget({ id: u.id, name: u.username })}
                        title="Ver alunos deste coach"
                        className="ml-1 inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        <Users className="size-3" /> alunos
                      </button>
                    )}
                  </td>
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
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setDeleteTarget({ id: u.id, username: u.username, email: u.email })}
                      title="Excluir permanentemente"
                      className="rounded p-1 text-muted-foreground/40 hover:bg-destructive/10 hover:text-destructive transition-colors"
                    >
                      <Trash2 className="size-3.5" />
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

      {deleteTarget && (
        <DeleteUserModal
          target={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={() => {
            qc.invalidateQueries({ queryKey: ["admin-users"] });
            qc.invalidateQueries({ queryKey: ["admin-stats"] });
            toast.success(`Usuário @${deleteTarget.username} excluído permanentemente`);
            setDeleteTarget(null);
          }}
        />
      )}

      {coachTarget && (
        <CoachStudentsModal
          coachId={coachTarget.id}
          coachName={coachTarget.name}
          onClose={() => setCoachTarget(null)}
        />
      )}
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
                      Nota para o candidato (opcional, enviada no email de rejeição)
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

// ── Support Tab ───────────────────────────────────────────────────────────────

interface SupportTicket {
  id: number;
  user_id: number | null;
  username: string | null;
  category: string;
  subject: string;
  message: string;
  status: string;
  admin_reply: string | null;
  replied_at: string | null;
  created_at: string;
}

const CATEGORY_LABEL: Record<string, string> = {
  bug: "Bug", question: "Dúvida", suggestion: "Sugestão", billing: "Cobrança", other: "Outro",
};

const STATUS_STYLE: Record<string, string> = {
  open:    "bg-destructive/10 text-destructive",
  replied: "bg-primary/10 text-primary",
};

function TicketRow({ ticket, onReplied }: { ticket: SupportTicket; onReplied: () => void }) {
  const qc = useQueryClient();
  const [reply, setReply]   = useState(ticket.admin_reply ?? "");
  const [open, setOpen]     = useState(!ticket.admin_reply);
  const [saving, setSaving] = useState(false);

  const handleReply = async () => {
    if (!reply.trim()) return;
    setSaving(true);
    try {
      await support.replyTicket(ticket.id, reply.trim());
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["admin-support-tickets"] });
      qc.invalidateQueries({ queryKey: ["admin-support-count"] });
      onReplied();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="px-5 py-4 space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-mono text-[9px] font-bold uppercase tracking-wider bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
          {CATEGORY_LABEL[ticket.category] ?? ticket.category}
        </span>
        <span className={cn("font-mono text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full", STATUS_STYLE[ticket.status] ?? "bg-muted text-muted-foreground")}>
          {ticket.status === "open" ? "Aberto" : "Respondido"}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {ticket.username ?? `user #${ticket.user_id}`}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground ml-auto">
          {new Date(ticket.created_at).toLocaleString("pt-BR")}
        </span>
      </div>

      {ticket.subject && (
        <p className="text-sm font-semibold text-foreground">{ticket.subject}</p>
      )}
      <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{ticket.message}</p>

      {ticket.admin_reply && !open ? (
        <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 space-y-1">
          <p className="font-mono text-[9px] font-bold uppercase tracking-wider text-primary">Resposta enviada · {ticket.replied_at ? new Date(ticket.replied_at).toLocaleString("pt-BR") : ""}</p>
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{ticket.admin_reply}</p>
          <button onClick={() => setOpen(true)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors">Editar resposta</button>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            placeholder="Escreva a resposta para o usuário…"
            rows={3}
            className="w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={handleReply}
              disabled={saving || !reply.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary-foreground disabled:opacity-50 hover:bg-primary-glow transition-colors"
            >
              {saving ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
              {saving ? "Enviando…" : "Responder"}
            </button>
            {ticket.admin_reply && (
              <button onClick={() => setOpen(false)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors px-2">
                Cancelar
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SupportTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-support-tickets"],
    queryFn:  () => support.listTickets(),
    staleTime: 30_000,
  });

  const tickets: SupportTicket[] = (data as { tickets: SupportTicket[] })?.tickets ?? [];

  if (isLoading) return (
    <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
      <Loader2 className="size-5 animate-spin text-primary" />
      <span className="font-mono text-xs uppercase tracking-wider">Carregando…</span>
    </div>
  );

  if (tickets.length === 0) return (
    <div className="flex items-center justify-center py-24 text-muted-foreground font-mono text-xs uppercase tracking-wider">
      Nenhuma mensagem de suporte recebida ainda.
    </div>
  );

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
      <div className="px-4 py-3 border-b border-border bg-hud-elevated/40 flex items-center gap-2">
        <MessageSquarePlus className="size-3.5 text-primary" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          Mensagens de Suporte: {tickets.length}
        </span>
        <span className="ml-auto font-mono text-[9px] text-destructive">
          {tickets.filter(t => t.status === "open").length} abertos
        </span>
      </div>
      <div className="divide-y divide-border">
        {tickets.map((t) => (
          <TicketRow
            key={t.id}
            ticket={t}
            onReplied={() => qc.invalidateQueries({ queryKey: ["admin-support-tickets"] })}
          />
        ))}
      </div>
    </div>
  );
}

// ── GTO Worker Tab ───────────────────────────────────────────────────────────

function GtoWorkerTab() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["admin-gto-worker-status"],
    queryFn: adminDashboard.gtoWorkerStatus,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const { data: queueData } = useQuery({
    queryKey: ["admin-gto-hand-queue"],
    queryFn: adminDashboard.gtoHandQueue,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  if (isLoading) return <Loading />;
  if (!data) return null;

  const hq = data.hand_queue ?? {};
  const sq = data.solver_queue ?? {};
  const cov = data.coverage ?? {};

  const handTotal  = Object.values(hq).reduce((a, b) => a + b, 0);
  const handDone   = hq['done']    ?? 0;
  const handPend   = hq['pending'] ?? 0;
  const handErr    = hq['error']   ?? 0;
  const handRun    = hq['running'] ?? 0;

  const solverPend = sq['pending'] ?? 0;
  const solverDone = sq['done']    ?? 0;
  const solverFail = sq['failed']  ?? 0;

  const coverageTotal = cov['total'] ?? 0;
  const coverageWizard = cov['gto_wizard'] ?? 0;
  const coverageSolver = cov['solver'] ?? (cov['solver_cli'] ?? 0);
  const coverageRemote = cov['remote_solver'] ?? 0;

  const throughput = data.throughput ?? [];
  const throughputMax = Math.max(...throughput.map(t => t.count), 1);

  const lastHb = data.worker.last_heartbeat
    ? new Date(data.worker.last_heartbeat).toLocaleString("pt-BR")
    : "—";

  return (
    <div className="space-y-6">
      {/* Worker health */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => refetch()}
          className="ml-auto font-mono text-[10px] text-muted-foreground hover:text-foreground border border-border rounded px-2 py-1 transition-colors"
        >
          Atualizar
        </button>
      </div>

      {/* KPIs row 1 — worker */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className={cn(
          "rounded-xl border p-5 space-y-2 col-span-2 lg:col-span-1",
          data.worker.active ? "border-green-500/30 bg-green-500/5" : "border-yellow-500/30 bg-yellow-500/5"
        )}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Worker</span>
            <CircleDot className={cn("size-4", data.worker.active ? "text-green-500" : "text-yellow-500")} />
          </div>
          <p className={cn("text-2xl font-bold", data.worker.active ? "text-green-500" : "text-yellow-500")}>
            {data.worker.active ? "Ativo" : "Ocioso"}
          </p>
          <p className="font-mono text-[10px] text-muted-foreground">Último proc: {lastHb}</p>
        </div>

        <KpiTile label="Pendentes"  value={String(handPend)} sub="gto_hand_requests" icon={Clock}        />
        <KpiTile label="Processados" value={String(handDone)} sub={`total: ${handTotal}`} icon={CheckCircle2} accent={handDone > 0} />
        <KpiTile label="Erros"      value={String(handErr)}  sub={`em execução: ${handRun}`} icon={AlertTriangle} accent={handErr > 0} />
      </div>

      {/* KPIs row 2 — solver queue + coverage */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiTile label="Solver Pendentes" value={String(solverPend)} sub="gto_solver_queue" icon={Cpu} />
        <KpiTile label="Solver Concluídos" value={String(solverDone)} sub={`falhos: ${solverFail}`} icon={CheckCircle2} accent={solverDone > 0} />
        <KpiTile label="Decisions Cobertas"  value={String(coverageTotal)} sub={`nodes: ${(cov['solver_cli'] ?? 0) + (cov['gto_wizard'] ?? 0)} · preflop: ${cov['preflop_ranges'] ?? 0}`} icon={BarChart2} accent={coverageTotal > 0} />
        <KpiTile label="GTO Solver (remoto)"  value={String(coverageWizard)} sub={`solver_cli: ${coverageSolver}`} icon={Activity} />
      </div>

      {/* Throughput chart */}
      <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
        <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          Throughput: últimas 24h
        </h3>
        {throughput.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum processamento nas últimas 24h.</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={throughput} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
              <XAxis
                dataKey="hour"
                tickFormatter={v => v ? v.slice(11, 16) : ""}
                tick={{ fontSize: 10, fontFamily: "monospace" }}
                stroke="hsl(var(--border))"
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 10, fontFamily: "monospace" }}
                stroke="hsl(var(--border))"
              />
              <Tooltip
                formatter={(v: number) => [v, "requests"]}
                labelFormatter={l => `${l?.toString().slice(0, 16)}`}
                contentStyle={{ background: "hsl(var(--background))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 11 }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {throughput.map((entry, i) => (
                  <Cell key={i} fill={entry.count === throughputMax ? "hsl(var(--primary))" : "hsl(var(--muted))"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Coverage breakdown */}
      {coverageTotal > 0 && (
        <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
          <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Cobertura GTO por Fonte (decisions com label)
          </h3>
          <div className="space-y-2">
            {Object.entries(cov)
              .filter(([k]) => k !== 'total')
              .sort(([, a], [, b]) => b - a)
              .map(([source, n]) => {
                const labels: Record<string, { label: string; sub: string; color: string }> = {
                  preflop_ranges: { label: 'preflop_ranges', sub: 'ranges JSON validados',  color: 'bg-emerald-500' },
                  gto_wizard:     { label: 'gto_solver',     sub: 'GTO Solver (remoto)',     color: 'bg-blue-500'    },
                  solver_cli:     { label: 'solver_cli',     sub: 'solver local (CFR)',       color: 'bg-amber-500'   },
                };
                const meta = labels[source] ?? { label: source, sub: '', color: 'bg-primary' };
                return (
                  <div key={source} className="flex items-center gap-3">
                    <div className="w-32 shrink-0">
                      <span className="font-mono text-[11px] text-foreground">{meta.label}</span>
                      {meta.sub && <p className="font-mono text-[10px] text-muted-foreground">{meta.sub}</p>}
                    </div>
                    <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${meta.color}`}
                        style={{ width: `${coverageTotal > 0 ? Math.round((n / coverageTotal) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="font-mono text-[11px] tabular-nums text-foreground w-12 text-right">{n}</span>
                  </div>
                );
              })
            }
          </div>
        </div>
      )}

      {/* Recent errors */}
      {data.recent_errors.length > 0 && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-5 space-y-3">
          <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-destructive">
            Erros Recentes
          </h3>
          <div className="space-y-2">
            {data.recent_errors.map(e => (
              <div key={e.id} className="rounded-lg border border-border bg-background p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] text-muted-foreground">hand {e.hand_id}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{e.processed_at?.slice(0, 16)}</span>
                </div>
                {e.error_msg && (
                  <p className="text-xs text-destructive break-all">{e.error_msg}</p>
                )}
                {e.user_email && (
                  <p className="font-mono text-[10px] text-muted-foreground">user: {e.user_email}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Request list */}
      {queueData && queueData.queue.length > 0 && (
        <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
          <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Requests por Mão ({queueData.queue.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] font-mono">
              <thead>
                <tr className="text-muted-foreground/60 uppercase tracking-wider text-[9px]">
                  <th className="text-left pb-2 pr-3">Hand ID</th>
                  <th className="text-left pb-2 pr-3">Status</th>
                  <th className="text-left pb-2 pr-3">Decisões</th>
                  <th className="text-left pb-2 pr-3">Criado em</th>
                  <th className="text-left pb-2">Processado em</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {queueData.queue.slice(0, 50).map(r => {
                  const statusCls =
                    r.status === "done"       ? "text-emerald-400" :
                    r.status === "pending"    ? "text-sky-400" :
                    r.status === "processing" || r.status === "running" ? "text-amber-400" :
                    r.status === "error"      ? "text-destructive" : "text-muted-foreground";
                  return (
                    <tr key={r.id} className="hover:bg-muted/10">
                      <td className="py-1.5 pr-3 text-foreground/80">{r.hand_id}</td>
                      <td className={`py-1.5 pr-3 font-bold ${statusCls}`}>{r.status}</td>
                      <td className="py-1.5 pr-3 text-muted-foreground">
                        {r.decisions_done ?? 0}/{r.decisions_found ?? "?"}
                      </td>
                      <td className="py-1.5 pr-3 text-muted-foreground/60">{r.created_at?.slice(11, 16)}</td>
                      <td className="py-1.5 text-muted-foreground/60">{r.processed_at?.slice(11, 16) ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

const SECTION_TITLE: Record<AdminSection, { title: string; sub: string }> = {
  overview:     { title: "Visão geral",    sub: "Métricas operacionais e demografia." },
  finance:      { title: "Financeiro",     sub: "Fluxo de caixa, entradas, saídas e cobrança." },
  users:        { title: "Usuários",       sub: "Gestão de jogadores, planos e suspensões." },
  coaches:      { title: "Coaches",        sub: "Roster de coaches, alunos e repasses." },
  support:      { title: "Tickets",        sub: "Mensagens de suporte dos usuários." },
  candidaturas: { title: "Candidaturas",   sub: "Pedidos para virar coach." },
  "gto-worker": { title: "GTO Worker",     sub: "Monitoramento do worker e cobertura GTO." },
  logs:         { title: "Logs",           sub: "Últimas importações de torneios." },
};

const AdminDashboard = () => {
  const [section, setSection] = useState<AdminSection>("finance");

  // ── Nav badges / attention dots ──
  const { data: supportCount } = useQuery({
    queryKey: ["admin-support-count"],
    queryFn: support.unreadCount,
    staleTime: 30_000,
  });
  const { data: pendingApps } = useQuery({
    queryKey: ["admin-coach-applications", "pending"],
    queryFn: () => adminDashboard.coachApplications("pending"),
    staleTime: 30_000,
  });
  const { data: dunning } = useQuery({
    queryKey: ["admin-finance-dunning"],
    queryFn: adminDashboard.financeDunning,
    staleTime: 60_000,
  });
  const { data: worker } = useQuery({
    queryKey: ["admin-gto-worker-status"],
    queryFn: adminDashboard.gtoWorkerStatus,
    staleTime: 30_000,
  });

  const openTickets = supportCount?.open ?? 0;
  const pendingCount = pendingApps?.applications?.length ?? 0;
  const financeDot = (dunning?.past_due?.length ?? 0) > 0 || (dunning?.recent_failed?.length ?? 0) > 0;
  const workerDot = worker ? (!worker.worker.active || worker.recent_errors.length > 0) : false;

  const groups: NavGroup[] = [
    {
      label: "Negócio",
      items: [
        { id: "overview", label: "Visão geral", icon: LayoutDashboard },
        { id: "finance",  label: "Financeiro",  icon: BarChart2, dot: financeDot },
        { id: "users",    label: "Usuários",    icon: Users },
        { id: "coaches",  label: "Coaches",     icon: GraduationCap },
      ],
    },
    {
      label: "Suporte",
      items: [
        { id: "support",      label: "Tickets",      icon: MessageSquarePlus, badge: openTickets },
        { id: "candidaturas", label: "Candidaturas", icon: Shield, badge: pendingCount },
      ],
    },
    {
      label: "Operação",
      items: [
        { id: "gto-worker",  label: "GTO Worker",  icon: Cpu, dot: workerDot },
        { id: "logs",        label: "Logs",        icon: Activity },
      ],
    },
  ];

  const meta = SECTION_TITLE[section];

  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />
      <main className="mx-auto max-w-[1440px] px-4 pt-8 pb-28 md:px-8 md:pb-8 animate-fade-in">
        <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
          <AdminSidebar groups={groups} active={section} onSelect={setSection} />

          <div className="min-w-0 flex-1 space-y-6">
            <header className="flex flex-col gap-2">
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
                <Shield className="size-3.5" /> Admin
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-foreground">{meta.title}</h1>
              <p className="text-sm text-muted-foreground">{meta.sub}</p>
            </header>

            {section === "overview"     && <OverviewTab />}
            {section === "finance"      && <FinanceCockpit />}
            {section === "users"        && <UsersTab />}
            {section === "coaches"      && <CoachesTab />}
            {section === "support"      && <SupportTab />}
            {section === "candidaturas" && <CandidaturasTab />}
            {section === "gto-worker"   && <GtoWorkerTab />}
            {section === "logs"         && <LogsTab />}
          </div>
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;
