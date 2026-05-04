import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Users, TrendingUp, Award, Activity, AlertTriangle,
  Play, Filter, ChevronDown, ChevronUp, LayoutDashboard,
  BarChart2, CheckCircle2, Clock,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { InviteKeyWidget } from "@/components/coach/InviteKeyWidget";
import { StudentRow } from "@/components/coach/StudentRow";
import { coachDashboard, coachFinance, coachEffectiveness, MultiStudentDecision, CommonLeak } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── shared ────────────────────────────────────────────────────────────────────

const SCORE_COLOR = (s: number) =>
  s >= 80 ? "text-primary" : s >= 60 ? "text-amber-400" : "text-destructive";

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: React.ElementType }) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-1">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-3.5" />
        <span className="font-mono text-[10px] uppercase tracking-widest-2">{label}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
    </div>
  );
}

// ── Tab: Alunos ────────────────────────────────────────────────────────────────

function AlunosTab() {
  const { data: studentsData, isLoading } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });
  const { data: impact } = useQuery({
    queryKey: ["coach-impact"],
    queryFn: () => coachDashboard.impact(30),
  });

  const students = studentsData?.students ?? [];

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-2 space-y-3">
        {isLoading && <p className="text-sm text-muted-foreground animate-pulse">Carregando…</p>}
        {!isLoading && students.length === 0 && (
          <div className="rounded-xl border border-dashed border-border p-8 text-center space-y-2">
            <p className="text-sm text-muted-foreground">Nenhum aluno vinculado ainda.</p>
            <p className="text-xs text-muted-foreground">Compartilhe sua chave de convite para que alunos possam se vincular.</p>
          </div>
        )}
        <div className="space-y-2">
          {students.map((s) => <StudentRow key={s.id} student={s} />)}
        </div>
      </div>

      <div className="space-y-4">
        <InviteKeyWidget />

        {impact?.top_leaks && impact.top_leaks.length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              Leaks em comum
            </p>
            <div className="space-y-2">
              {impact.top_leaks.slice(0, 5).map((leak) => (
                <div key={leak.spot} className="flex items-center justify-between">
                  <span className="text-xs text-foreground truncate max-w-[140px]">{leak.spot}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{leak.n}x</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: Atenção Urgente (BACK-003) ───────────────────────────────────────────

const STREETS = ["preflop", "flop", "turn", "river"];
const LABELS: { value: string; label: string }[] = [
  { value: "clear_mistake", label: "Erro claro" },
  { value: "small_mistake", label: "Erro pequeno" },
];

function UrgentTab() {
  const navigate = useNavigate();
  const { data: studentsData } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });

  const [studentFilter, setStudentFilter] = useState<number | undefined>();
  const [streetFilter, setStreetFilter]   = useState<string | undefined>();
  const [labelFilter, setLabelFilter]     = useState<string | undefined>();

  const { data, isLoading } = useQuery({
    queryKey: ["coach-all-worst", studentFilter, streetFilter, labelFilter],
    queryFn: () => coachDashboard.allWorstDecisions({
      n: 30,
      student_id: studentFilter,
      street: streetFilter,
      label: labelFilter,
    }),
  });

  const students = studentsData?.students ?? [];
  const decisions: MultiStudentDecision[] = data?.decisions ?? [];

  const FilterBtn = ({
    active, onClick, children,
  }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      className={cn(
        "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors",
        active
          ? "bg-primary/10 text-primary ring-1 ring-primary/30"
          : "text-muted-foreground hover:bg-secondary hover:text-foreground"
      )}
    >
      {children}
    </button>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Filter className="size-3.5 text-muted-foreground shrink-0" />

        {/* Student filter */}
        <FilterBtn active={!studentFilter} onClick={() => setStudentFilter(undefined)}>Todos</FilterBtn>
        {students.map((s) => (
          <FilterBtn key={s.id} active={studentFilter === s.id} onClick={() => setStudentFilter(s.id)}>
            {s.username}
          </FilterBtn>
        ))}

        <span className="text-border mx-1">|</span>

        {/* Street filter */}
        <FilterBtn active={!streetFilter} onClick={() => setStreetFilter(undefined)}>Todas streets</FilterBtn>
        {STREETS.map((st) => (
          <FilterBtn key={st} active={streetFilter === st} onClick={() => setStreetFilter(st)}>
            {st}
          </FilterBtn>
        ))}

        <span className="text-border mx-1">|</span>

        {/* Label filter */}
        <FilterBtn active={!labelFilter} onClick={() => setLabelFilter(undefined)}>Todos erros</FilterBtn>
        {LABELS.map((l) => (
          <FilterBtn key={l.value} active={labelFilter === l.value} onClick={() => setLabelFilter(l.value)}>
            {l.label}
          </FilterBtn>
        ))}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse py-6">Carregando decisões…</p>}

      {!isLoading && decisions.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Nenhuma decisão crítica encontrada com os filtros atuais.
        </p>
      )}

      {decisions.length > 0 && (
        <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-background/50">
                {["Aluno", "Street", "Jogou", "Correto", "Score", "Label", ""].map((h, i) => (
                  <th key={i} className="px-4 py-2.5 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {decisions.map((d) => (
                <tr key={d.id} className="border-b border-border/40 last:border-0 hover:bg-primary/5 transition-colors">
                  <td className="px-4 py-2.5 text-xs font-medium text-foreground">{d.username}</td>
                  <td className="px-4 py-2.5 font-mono text-xs capitalize text-muted-foreground">{d.street}</td>
                  <td className="px-4 py-2.5 text-xs text-destructive font-medium">{d.action_taken}</td>
                  <td className="px-4 py-2.5 text-xs text-primary font-medium">{d.best_action}</td>
                  <td className={`px-4 py-2.5 font-mono text-xs font-bold ${SCORE_COLOR(d.score)}`}>{d.score}</td>
                  <td className="px-4 py-2.5">
                    <span className={cn(
                      "font-mono text-[10px] font-bold px-2 py-0.5 rounded",
                      d.label === "clear_mistake"
                        ? "bg-destructive/10 text-destructive ring-1 ring-destructive/30"
                        : "bg-amber-400/10 text-amber-400 ring-1 ring-amber-400/30"
                    )}>
                      {d.label === "clear_mistake" ? "Claro" : "Pequeno"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => navigate(`/replayer?t=${d.tournament_id}&h=${d.hand_id}&student=${d.student_id}`)}
                      className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors"
                    >
                      <Play className="size-3" /> Replay
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab: Leaks Sistêmicos (BACK-004) ──────────────────────────────────────────

function LeakRow({ leak }: { leak: CommonLeak }) {
  const [expanded, setExpanded] = useState(false);
  const multi = leak.num_students > 1;

  return (
    <div className="rounded-lg border border-border bg-hud-surface overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-primary/5 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {multi && (
            <span className="shrink-0 rounded-sm bg-destructive/10 text-destructive font-mono text-[10px] font-bold px-2 py-0.5 ring-1 ring-destructive/30">
              {leak.num_students} alunos
            </span>
          )}
          <span className="text-sm font-medium text-foreground truncate">{leak.spot}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-3">
          <span className="font-mono text-[10px] text-muted-foreground">{leak.total_n}x total</span>
          <span className={`font-mono text-sm font-bold ${SCORE_COLOR(leak.avg_score)}`}>
            {leak.avg_score.toFixed(1)} pts
          </span>
          {expanded ? <ChevronUp className="size-3.5 text-muted-foreground" /> : <ChevronDown className="size-3.5 text-muted-foreground" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border bg-background/50 px-4 py-3 space-y-2">
          <p className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground mb-2">
            Alunos afetados
          </p>
          {leak.students.map((s) => (
            <div key={s.id} className="flex items-center justify-between text-xs">
              <span className="text-foreground font-medium">{s.username}</span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[10px] text-muted-foreground">{s.n}x</span>
                <span className={`font-mono text-xs font-bold ${SCORE_COLOR(s.avg_score)}`}>
                  {s.avg_score} pts
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LeaksTab() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ["coach-common-leaks", days],
    queryFn: () => coachDashboard.commonLeaks(days),
  });

  const leaks = data?.leaks ?? [];
  const systemic = leaks.filter((l) => l.num_students > 1);
  const individual = leaks.filter((l) => l.num_students === 1);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Período:</span>
        {[30, 60, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={cn(
              "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors",
              days === d
                ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            )}
          >
            {d}d
          </button>
        ))}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse py-6">Analisando leaks…</p>}

      {!isLoading && leaks.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Nenhum leak encontrado no período selecionado.
        </p>
      )}

      {systemic.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-destructive">
            Leaks sistêmicos — afetam múltiplos alunos
          </p>
          {systemic.map((l) => <LeakRow key={l.spot} leak={l} />)}
        </div>
      )}

      {individual.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Leaks individuais
          </p>
          {individual.map((l) => <LeakRow key={l.spot} leak={l} />)}
        </div>
      )}
    </div>
  );
}

// ── Tabs definition ───────────────────────────────────────────────────────────

// ── Tabs definition ───────────────────────────────────────────────────────────

type Tab = "alunos" | "urgente" | "leaks" | "financeiro" | "efetividade";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "alunos",       label: "Alunos",           icon: Users },
  { id: "urgente",      label: "Atenção Urgente",  icon: AlertTriangle },
  { id: "leaks",        label: "Leaks Sistêmicos", icon: LayoutDashboard },
  { id: "efetividade",  label: "Efetividade",      icon: TrendingUp },
  { id: "financeiro",   label: "Financeiro",       icon: BarChart2 },
];

// ── Effectiveness Tab ─────────────────────────────────────────────────────────

function DeltaBadge({ delta }: { delta: number }) {
  const positive = delta > 0;
  const zero     = delta === 0;
  return (
    <span className={cn(
      "font-mono text-xs font-bold tabular-nums",
      zero ? "text-muted-foreground" : positive ? "text-emerald-400" : "text-red-400"
    )}>
      {positive ? "+" : ""}{delta.toFixed(1)}pp
    </span>
  );
}

function EfetividadeTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["coach-effectiveness"],
    queryFn: coachEffectiveness.report,
    staleTime: 5 * 60_000,
  });

  const summary  = data?.summary;
  const students = data?.students ?? [];

  if (isLoading) {
    return <p className="mt-6 text-sm text-muted-foreground animate-pulse">Calculando efetividade…</p>;
  }

  if (!summary || summary.students_analyzed === 0) {
    return (
      <div className="mt-6 rounded-xl border border-border bg-hud-surface p-8 text-center space-y-2">
        <TrendingUp className="mx-auto size-8 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">Sem dados de efetividade ainda</p>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          Configure a data de baseline de pelo menos um aluno para começar a medir a evolução com seu coaching.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-6">
      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-1 text-center">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Alunos analisados</p>
          <p className="text-2xl font-bold text-foreground">{summary.students_analyzed}</p>
        </div>
        <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-1 text-center">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Melhora mediana</p>
          <p className={cn("text-2xl font-bold tabular-nums",
            (summary.median_delta ?? 0) > 0 ? "text-emerald-400" : "text-red-400"
          )}>
            {summary.median_delta != null
              ? `${summary.median_delta > 0 ? "+" : ""}${summary.median_delta.toFixed(1)}pp`
              : "—"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-1 text-center">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">% com melhora</p>
          <p className={cn("text-2xl font-bold tabular-nums",
            (summary.positive_pct ?? 0) >= 50 ? "text-emerald-400" : "text-amber-400"
          )}>
            {summary.positive_pct != null ? `${summary.positive_pct}%` : "—"}
          </p>
        </div>
      </div>

      {/* Badge preview */}
      {summary.badge && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-2.5">
          <Award className="size-4 text-emerald-400 shrink-0" />
          <p className="text-sm text-emerald-400 font-medium">{summary.badge}</p>
          <span className="ml-auto font-mono text-[10px] text-muted-foreground">visível no perfil público</span>
        </div>
      )}

      {/* Per-student table */}
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-0 border-b border-border bg-muted/30 px-4 py-2">
          {["Aluno", "Antes", "Depois", "Δ Standard%", "Leaks corrigidos"].map((h) => (
            <span key={h} className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
              {h}
            </span>
          ))}
        </div>
        {students.map((s) => (
          <div
            key={s.student_id}
            className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-0 border-b border-border/50 px-4 py-3 last:border-b-0 hover:bg-muted/20 transition-colors"
          >
            <span className="text-sm font-medium text-foreground">{s.username}</span>
            <span className="font-mono text-xs text-muted-foreground tabular-nums pr-6">{s.std_before.toFixed(1)}%</span>
            <span className="font-mono text-xs text-foreground tabular-nums pr-6">{s.std_after.toFixed(1)}%</span>
            <span className="pr-6"><DeltaBadge delta={s.delta} /></span>
            <span className="font-mono text-xs text-muted-foreground text-right">
              {s.fixed_leaks > 0
                ? <span className="text-emerald-400">{s.fixed_leaks} corrigido{s.fixed_leaks > 1 ? "s" : ""}</span>
                : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Finance Tab ───────────────────────────────────────────────────────────────

function fmtCents(cents: number) {
  return `R$ ${(cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}
function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "2-digit" });
}

function FinanceiroTab() {
  const { data: summary, isLoading: loadSum } = useQuery({
    queryKey: ["coach-finance-summary"],
    queryFn: coachFinance.summary,
    staleTime: 60_000,
  });
  const { data: stData, isLoading: loadSt } = useQuery({
    queryKey: ["coach-finance-students"],
    queryFn: coachFinance.students,
    staleTime: 60_000,
  });
  const { data: histData, isLoading: loadHist } = useQuery({
    queryKey: ["coach-finance-history"],
    queryFn: coachFinance.history,
    staleTime: 60_000,
  });

  const students = stData?.students ?? [];
  const payments = histData?.payments ?? [];
  const activeCount = students.filter(s => s.is_active).length;

  return (
    <div className="space-y-6 mt-4">
      {/* Resumo do ciclo */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Alunos Vinculados", value: loadSum ? "…" : String(summary?.total_students ?? 0), sub: "total" },
          { label: "Alunos Ativos", value: loadSt ? "…" : String(activeCount), sub: "PRO + importaram este mês" },
          { label: "Receita Estimada", value: loadSum ? "…" : fmtCents(summary?.amount_cents ?? 0), sub: summary?.period ?? "" },
          { label: "Mensalidade", value: summary?.monthly_fee_waived ? "Zerada" : "Normal", sub: summary?.monthly_fee_waived ? "≥1 aluno ativo" : "sem alunos" },
        ].map(k => (
          <div key={k.label} className="rounded-xl border border-border bg-hud-surface p-4 space-y-1">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">{k.label}</p>
            <p className="text-xl font-bold text-foreground">{k.value}</p>
            <p className="font-mono text-[9px] text-muted-foreground">{k.sub}</p>
          </div>
        ))}
      </div>

      {/* Lista de alunos com status */}
      <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-hud-elevated/40">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Alunos — Status de Atividade</span>
        </div>
        {loadSt ? (
          <div className="py-10 flex justify-center"><Activity className="size-5 animate-spin text-primary" /></div>
        ) : students.length === 0 ? (
          <p className="px-4 py-8 text-sm text-muted-foreground text-center">Nenhum aluno vinculado.</p>
        ) : (
          <ul className="divide-y divide-border">
            {students.map(s => (
              <li key={s.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{s.username}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">
                    {s.plan} · {s.tournament_count} torneios · último: {fmtDate(s.last_import)}
                  </p>
                </div>
                <div className="shrink-0">
                  {s.is_active ? (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20">
                      <CheckCircle2 className="size-3" /> Ativo
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground ring-1 ring-border">
                      <Clock className="size-3" /> Inativo
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Histórico de repasses */}
      <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-hud-elevated/40">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Histórico de Repasses</span>
        </div>
        {loadHist ? (
          <div className="py-10 flex justify-center"><Activity className="size-5 animate-spin text-primary" /></div>
        ) : payments.length === 0 ? (
          <p className="px-4 py-8 text-sm text-muted-foreground text-center">Nenhum histórico ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b border-border">
                <tr>
                  {["Período", "Alunos Ativos", "Valor", "Status", "Pago em"].map(h => (
                    <th key={h} className="px-4 py-3 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {payments.map(p => (
                  <tr key={p.id} className="hover:bg-primary/5 transition-colors">
                    <td className="px-4 py-3 font-mono text-foreground">{p.period}</td>
                    <td className="px-4 py-3 font-mono tabular-nums text-center text-foreground">{p.active_students}</td>
                    <td className="px-4 py-3 font-mono font-bold tabular-nums text-foreground">
                      {p.amount_cents > 0 ? fmtCents(p.amount_cents) : "—"}
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
                    <td className="px-4 py-3 font-mono text-muted-foreground">{fmtDate(p.paid_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CoachDashboard() {
  const [tab, setTab] = useState<Tab>("alunos");

  const { data: impact, isLoading: loadingImpact } = useQuery({
    queryKey: ["coach-impact"],
    queryFn: () => coachDashboard.impact(30),
  });

  const summary = impact?.summary;

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-5xl px-6 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard do Professor</h1>
          <p className="text-sm text-muted-foreground mt-1">Acompanhe a evolução dos seus alunos</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Alunos"        value={loadingImpact ? "…" : (summary?.total_students ?? 0)}  icon={Users} />
          <StatCard label="Ativos (30d)"  value={loadingImpact ? "…" : (summary?.active_students ?? 0)} icon={Activity} />
          <StatCard
            label="Melhoria Média"
            value={loadingImpact ? "…" : summary?.avg_improvement_pct != null ? `${summary.avg_improvement_pct.toFixed(1)}%` : "—"}
            icon={TrendingUp}
          />
          <StatCard
            label="Melhor Aluno"
            value={loadingImpact ? "…" : (summary?.best_student ?? "—")}
            icon={Award}
          />
        </div>

        {/* Tabs */}
        <div className="flex overflow-x-auto border-b border-border gap-0 scrollbar-none">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors",
                tab === t.id
                  ? "text-primary border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </button>
          ))}
        </div>

        {tab === "alunos"       && <AlunosTab />}
        {tab === "urgente"      && <UrgentTab />}
        {tab === "leaks"        && <LeaksTab />}
        {tab === "efetividade"  && <EfetividadeTab />}
        {tab === "financeiro"   && <FinanceiroTab />}
      </main>
    </div>
  );
}
