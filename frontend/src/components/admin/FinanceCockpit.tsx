import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  TrendingUp, TrendingDown, Download, ArrowDownToLine, ArrowUpFromLine,
  Loader2, CheckCircle2, Clock, ChevronRight, ChevronDown, AlertTriangle, BarChart2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  adminDashboard, CoachPayout, AdminPayment, FinanceCockpit as Cockpit,
} from "@/lib/api";
import { fmt } from "./format";
import { FinTile } from "./FinTile";
import { StatusBadge } from "./StatusBadge";
import { PaymentCalendar } from "./PaymentCalendar";
import { DunningPanel } from "./DunningPanel";
import { ExpensesPanel } from "./ExpensesPanel";

function prevMonth(month: string): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 2, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// ── Horizontal bar breakdown ──────────────────────────────────────────────────
function Breakdown({ rows }: { rows: Array<{ label: string; amount_cents: number; n: number }> }) {
  const max = Math.max(...rows.map((r) => r.amount_cents), 1);
  return (
    <div className="space-y-2">
      {rows.length === 0 ? (
        <p className="font-mono text-[11px] text-muted-foreground">Sem dados.</p>
      ) : rows.map((r) => (
        <div key={r.label} className="space-y-0.5">
          <div className="flex items-center justify-between font-mono text-[10px]">
            <span className="uppercase text-muted-foreground">{r.label} <span className="text-muted-foreground/50">· {r.n}</span></span>
            <span className="tabular-nums text-foreground">{fmt(r.amount_cents)}</span>
          </div>
          <div className="h-1.5 rounded-full bg-border overflow-hidden">
            <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(r.amount_cents / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Coach payouts table (zone E) ──────────────────────────────────────────────
function CoachPayoutsTable({ period }: { period: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-finance-coaches", period],
    queryFn: () => adminDashboard.coachPayouts(period),
    staleTime: 30_000,
  });
  const payouts: CoachPayout[] = data?.payouts ?? [];
  const totalPending = data?.total_pending_cents ?? 0;

  const payMut = useMutation({
    mutationFn: (paymentId: number) => adminDashboard.markPaid(paymentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-finance-coaches"] });
      qc.invalidateQueries({ queryKey: ["admin-finance-cockpit"] });
      toast.success("Marcado como pago");
    },
  });

  const payAll = async () => {
    const pending = payouts.filter((p) => p.status !== "paid" && p.payment_id);
    if (pending.length === 0) return;
    if (!confirm(`Pagar ${pending.length} repasse(s) pendente(s)?`)) return;
    for (const p of pending) {
      try { await adminDashboard.markPaid(p.payment_id!); } catch { /* keep going */ }
    }
    qc.invalidateQueries({ queryKey: ["admin-finance-coaches"] });
    qc.invalidateQueries({ queryKey: ["admin-finance-cockpit"] });
    toast.success("Repasses pendentes pagos");
  };

  const exportUrl = `/admin/finance/export.csv?period=${period}`;
  const hasPending = payouts.some((p) => p.status !== "paid" && p.payment_id);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
      <div className="px-4 py-3 border-b border-border bg-hud-elevated/40 flex flex-wrap items-center gap-2 justify-between">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Repasses de coaches, {period}</span>
        <div className="flex items-center gap-3">
          {totalPending > 0 && <span className="font-mono text-[10px] text-warning">Pendente: {fmt(totalPending)}</span>}
          {hasPending && (
            <button onClick={payAll}
              className="inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/20 transition-colors">
              <CheckCircle2 className="size-3" /> Pagar todos pendentes
            </button>
          )}
          <a href={exportUrl} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors">
            <Download className="size-3" /> CSV
          </a>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="border-b border-border">
            <tr>
              {["Coach", "Plano", "Alunos vinculados", "Alunos ativos", "Valor (R$)", "Status", ""].map((h) => (
                <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr><td colSpan={7} className="py-12 text-center"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></td></tr>
            ) : payouts.length === 0 ? (
              <tr><td colSpan={7} className="py-12 text-center text-muted-foreground">Nenhum coach cadastrado.</td></tr>
            ) : payouts.map((p) => (
              <tr key={p.id} className="hover:bg-primary/5 transition-colors">
                <td className="px-4 py-3">
                  <p className="font-medium text-foreground">{p.display_name || p.username}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">@{p.username}</p>
                </td>
                <td className="px-4 py-3 font-mono text-muted-foreground">{p.plan}</td>
                <td className="px-4 py-3 font-mono tabular-nums text-foreground text-center">{p.total_students}</td>
                <td className="px-4 py-3 font-mono tabular-nums text-center">
                  <span className={cn("font-bold", p.active_students > 0 ? "text-primary" : "text-muted-foreground")}>{p.active_students}</span>
                </td>
                <td className="px-4 py-3 font-mono tabular-nums font-bold text-foreground">
                  {p.amount_cents > 0 ? fmt(p.amount_cents) : p.active_students > 0 ? "Zerado" : "—"}
                </td>
                <td className="px-4 py-3">
                  {p.status === "paid" ? <StatusBadge kind="paid" /> : <StatusBadge kind="pending" />}
                </td>
                <td className="px-4 py-3 text-right">
                  {p.status !== "paid" && p.payment_id && (
                    <button onClick={() => payMut.mutate(p.payment_id!)} disabled={payMut.isPending}
                      className="inline-flex items-center gap-1 font-mono text-[10px] text-primary hover:underline disabled:opacity-50">
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
  );
}

// ── Student-payments ledger (collapsible audit) ───────────────────────────────
function LedgerExpander() {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<{ gateway?: string; status?: string; search?: string }>({});

  const { data } = useQuery({
    queryKey: ["admin-payments", filter],
    queryFn: () => adminDashboard.payments({ ...filter, limit: 50 }),
    staleTime: 15_000,
    enabled: open,
  });
  const payments: AdminPayment[] = data?.payments ?? [];

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-hud-surface">
      <button onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 bg-hud-elevated/40 hover:bg-hud-elevated/60 transition-colors">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          Ledger de pagamentos de alunos (auditoria){data ? ` · ${data.total}` : ""}
        </span>
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div>
          <div className="px-4 py-2.5 border-b border-border flex flex-wrap items-center gap-2 justify-end">
            <input placeholder="buscar aluno / pi_…" defaultValue={filter.search ?? ""}
              onKeyDown={(e) => { if (e.key === "Enter") setFilter((f) => ({ ...f, search: (e.target as HTMLInputElement).value || undefined })); }}
              className="rounded-md border border-border bg-background px-2.5 py-1 font-mono text-[10px] text-foreground focus:outline-none focus:border-primary w-40" />
            <select value={filter.status ?? ""} onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value || undefined }))}
              className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[10px] text-foreground focus:outline-none focus:border-primary">
              <option value="">todos status</option>
              <option value="approved">aprovado</option>
              <option value="failed">falhou</option>
            </select>
            <select value={filter.gateway ?? ""} onChange={(e) => setFilter((f) => ({ ...f, gateway: e.target.value || undefined }))}
              className="rounded-md border border-border bg-background px-2 py-1 font-mono text-[10px] text-foreground focus:outline-none focus:border-primary">
              <option value="">todos gateways</option>
              <option value="stripe">stripe</option>
              <option value="mercadopago">mercadopago</option>
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b border-border">
                <tr>
                  {["Aluno", "Plano", "Valor", "Status", "Gateway", "ID", "Data"].map((h) => (
                    <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {payments.length === 0 ? (
                  <tr><td colSpan={7} className="py-10 text-center text-muted-foreground">Nenhum pagamento.</td></tr>
                ) : payments.map((p) => (
                  <tr key={p.id} className="hover:bg-primary/5 transition-colors">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-foreground">{p.username}</p>
                      <p className="font-mono text-[10px] text-muted-foreground">{p.email}</p>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-muted-foreground">{p.plan}</td>
                    <td className="px-4 py-2.5 font-mono tabular-nums font-bold text-foreground">{fmt(p.amount_cents)}</td>
                    <td className="px-4 py-2.5"><StatusBadge kind={p.status} /></td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground">{p.gateway}</td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground truncate max-w-[140px]">{p.gateway_id || "—"}</td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground whitespace-nowrap">{p.created_at ? new Date(p.created_at).toLocaleDateString("pt-BR") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Trends (zone D) ───────────────────────────────────────────────────────────
function Trends() {
  const { data } = useQuery({
    queryKey: ["admin-finance-timeseries"],
    queryFn: () => adminDashboard.financeTimeseries(6),
    staleTime: 60_000,
  });
  const series = data?.series ?? [];
  const grossMax = Math.max(...series.map((s) => s.gross_cents), 1);
  const label = (m: string) => m.slice(5);

  const chart = (key: "gross_cents" | "churn_count", title: string, isMoney: boolean) => (
    <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
      <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-muted-foreground">{title}</h3>
      {series.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sem histórico.</p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={series} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <XAxis dataKey="month" tickFormatter={label} tick={{ fontSize: 10, fontFamily: "monospace" }} stroke="hsl(var(--border))" />
            <YAxis allowDecimals={false} tickFormatter={isMoney ? (v: number) => String(Math.round(v / 100)) : undefined}
              tick={{ fontSize: 10, fontFamily: "monospace" }} stroke="hsl(var(--border))" />
            <Tooltip
              formatter={(v: number) => [isMoney ? fmt(v) : v, isMoney ? "receita" : "churn"]}
              contentStyle={{ background: "hsl(var(--background))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 11 }} />
            <Bar dataKey={key} radius={[4, 4, 0, 0]}>
              {series.map((s, i) => (
                <Cell key={i} fill={isMoney && s.gross_cents === grossMax ? "hsl(var(--primary))" : isMoney ? "hsl(var(--muted))" : "hsl(var(--destructive))"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {chart("gross_cents", "Receita, 6 meses", true)}
      {chart("churn_count", "Churn, 6 meses", false)}
    </div>
  );
}

// ── Cockpit root ──────────────────────────────────────────────────────────────
export function FinanceCockpit() {
  const [period, setPeriod] = useState(() => new Date().toISOString().slice(0, 7));

  const { data: cur, isLoading } = useQuery({
    queryKey: ["admin-finance-cockpit", period],
    queryFn: () => adminDashboard.financeCockpit(period),
    staleTime: 30_000,
  });
  const { data: prev } = useQuery({
    queryKey: ["admin-finance-cockpit", prevMonth(period)],
    queryFn: () => adminDashboard.financeCockpit(prevMonth(period)),
    staleTime: 30_000,
  });
  const { data: calData } = useQuery({
    queryKey: ["admin-finance-calendar", period],
    queryFn: () => adminDashboard.financeCalendar(period),
    staleTime: 30_000,
  });
  const { data: dunData, isLoading: dunLoading } = useQuery({
    queryKey: ["admin-finance-dunning"],
    queryFn: adminDashboard.financeDunning,
    staleTime: 30_000,
  });

  const c: Cockpit | undefined = cur;
  const netDelta = c && prev ? c.net_cents - prev.net_cents : null;

  return (
    <div className="space-y-6">
      {/* Period control */}
      <div className="flex items-center gap-2">
        <label className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Período</label>
        <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:border-primary" />
      </div>

      {isLoading || !c ? (
        <div className="flex items-center justify-center py-16 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">Carregando financeiro…</span>
        </div>
      ) : (
        <>
          {/* ── A · Headline ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className={cn(
              "rounded-xl border p-6 lg:col-span-1 flex flex-col justify-between",
              c.net_cents >= 0 ? "border-primary/30 bg-primary/5" : "border-destructive/30 bg-destructive/5"
            )}>
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Fluxo líquido (mês)</span>
                {c.net_cents >= 0 ? <TrendingUp className="size-4 text-primary" /> : <TrendingDown className="size-4 text-destructive" />}
              </div>
              <p className={cn("mt-3 text-4xl font-bold tabular-nums", c.net_cents >= 0 ? "text-primary" : "text-destructive")}>
                {c.net_cents < 0 ? "−" : ""}{fmt(Math.abs(c.net_cents))}
              </p>
              {netDelta != null && (
                <p className={cn("mt-1 font-mono text-[11px]", netDelta >= 0 ? "text-primary" : "text-destructive")}>
                  {netDelta >= 0 ? "▲" : "▼"} {fmt(Math.abs(netDelta))} vs mês anterior
                </p>
              )}
            </div>

            <div className="lg:col-span-2 grid grid-cols-2 lg:grid-cols-4 gap-px overflow-hidden rounded-xl border border-border bg-border">
              <FinTile label="MRR (real)" value={fmt(c.mrr_cents)} sub={`${c.paying_pro} pagantes`} accent="primary" />
              <FinTile label="Entradas" value={fmt(c.gross_in_cents)} sub={`${c.approved_count} pagamento(s)`} />
              <FinTile label="Saídas" value={fmt(c.cash_out_cents)} sub={`repasses + despesas`} accent="warning" />
              <FinTile label="Em risco" value={fmt(c.past_due_risk_cents)} sub={`${c.past_due_count} atrasado(s)`} accent={c.past_due_count > 0 ? "danger" : undefined} />
            </div>
          </div>

          {/* ── B · Entradas vs Saídas ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
              <div className="flex items-center gap-2">
                <ArrowDownToLine className="size-3.5 text-primary" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Entradas</span>
                <span className="ml-auto font-mono text-lg font-light tabular-nums text-primary">{fmt(c.gross_in_cents)}</span>
              </div>
              <div className="space-y-1">
                <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">Por gateway</p>
                <Breakdown rows={c.by_gateway.map((g) => ({ label: g.gateway, amount_cents: g.amount_cents, n: g.n }))} />
              </div>
              <div className="space-y-1">
                <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">Por plano</p>
                <Breakdown rows={c.by_plan.map((p) => ({ label: p.plan, amount_cents: p.amount_cents, n: p.n }))} />
              </div>
            </div>

            <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
              <div className="flex items-center gap-2">
                <ArrowUpFromLine className="size-3.5 text-warning" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Saídas</span>
                <span className="ml-auto font-mono text-lg font-light tabular-nums text-warning">{fmt(c.cash_out_cents)}</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
                  <span className="flex items-center gap-2 text-sm text-foreground">
                    <Clock className="size-3.5 text-muted-foreground" /> Repasses de coaches
                  </span>
                  <span className="text-right">
                    <span className="font-mono tabular-nums font-bold text-foreground">{fmt(c.coach_payout_cents)}</span>
                    {c.coach_payout_pending_cents > 0 && (
                      <span className="ml-2 inline-flex items-center gap-1 rounded bg-warning/10 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-warning ring-1 ring-warning/20">
                        {fmt(c.coach_payout_pending_cents)} pend.
                      </span>
                    )}
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
                  <span className="flex items-center gap-2 text-sm text-foreground">
                    <BarChart2 className="size-3.5 text-muted-foreground" /> Despesas
                  </span>
                  <span className="font-mono tabular-nums font-bold text-foreground">{fmt(c.expenses_cents)}</span>
                </div>
              </div>
              {c.failed_count > 0 && (
                <p className="inline-flex items-center gap-1 font-mono text-[10px] text-destructive">
                  <AlertTriangle className="size-3" /> {c.failed_count} pagamento(s) falho(s) no mês
                </p>
              )}
            </div>
          </div>

          {/* ── C · Calendar + Dunning ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <PaymentCalendar data={calData} month={period} />
            <DunningPanel data={dunData} isLoading={dunLoading} />
          </div>

          {/* ── D · Trends ── */}
          <Trends />

          {/* ── E · Coach payouts ── */}
          <CoachPayoutsTable period={period} />

          {/* ── F · Expenses ── */}
          <ExpensesPanel />

          {/* Ledger (audit, collapsed) */}
          <LedgerExpander />
        </>
      )}
    </div>
  );
}
