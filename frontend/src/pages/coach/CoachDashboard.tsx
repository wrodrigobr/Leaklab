import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Users, TrendingUp, Award, Activity, AlertTriangle,
  Play, Filter, ChevronDown, ChevronUp, LayoutDashboard,
  BarChart2, CheckCircle2, Clock, MessageSquare,
  Search, ChevronLeft, ChevronRight as ChevronRightIcon, TrendingDown, Minus,
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { InviteKeyWidget } from "@/components/coach/InviteKeyWidget";
import { StudentRow } from "@/components/coach/StudentRow";
import { VerdictTag } from "@/components/VerdictTag";
import { verdictLevelFromScore, VERDICT_META } from "@/lib/cardLogic";
import { coachDashboard, coachFinance, coachEffectiveness, MultiStudentDecision, CommonLeak, InboxThread, StudentSummary } from "@/lib/api";
import { cn, formatAction } from "@/lib/utils";

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

const PAGE_SIZE = 25;

type SortKey = "username" | "total_tournaments" | "last_import" | "trend";
type SortDir = "asc" | "desc";

// "recente" = importou em 30d (qualquer plano) — sinal de atividade bruto.
function isActive(s: StudentSummary): boolean {
  if (!s.recent_tournament?.imported_at) return false;
  return Date.now() - new Date(s.recent_tournament.imported_at).getTime() < 30 * 86_400_000;
}
// P1a: "ativo que conta na comp" = pro + import 30d (a régua do payout, vinda do backend).
const isActivePaid = (s: StudentSummary): boolean => s.is_active_paid === true;
// score da última sessão (0-1, menor = melhor) → cor do veredito de 3 níveis (FEAT-20).
function scoreCls(score: number | null | undefined): string {
  return score == null ? "text-muted-foreground" : VERDICT_META[verdictLevelFromScore(score)].textCls;
}
// P1b: "precisa de atenção" = crítica pendente OU mensagem não lida OU última sessão = Erro.
const needsAttention = (s: StudentSummary): boolean =>
  (s.critical_pending ?? 0) > 0 ||
  (s.unread ?? 0) > 0 ||
  (s.recent_tournament?.avg_score != null && verdictLevelFromScore(s.recent_tournament.avg_score) === "error");

function fmtImport(s: StudentSummary): string {
  const d = s.recent_tournament?.imported_at ?? s.recent_tournament?.played_at;
  if (!d) return "—";
  return new Date(d).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

const TREND_ORDER: Record<string, number> = { improving: 0, stable: 1, worsening: 2 };
const TREND_LABEL: Record<string, string> = { improving: "Melhorando", stable: "Estável", worsening: "Piorando" };
const TrendIcon = ({ trend }: { trend: string | null }) => {
  if (trend === "improving") return <TrendingUp  className="size-3.5 text-primary" />;
  if (trend === "worsening") return <TrendingDown className="size-3.5 text-destructive" />;
  if (trend === "stable")    return <Minus        className="size-3.5 text-muted-foreground" />;
  return null;
};

const RANK_TINT = (rank: number) =>
  rank === 1 ? "text-yellow-400" : rank === 2 ? "text-slate-300" : rank === 3 ? "text-amber-600" : "text-muted-foreground";

/** Ranking dos próprios alunos (#15 coach view) — nomes reais, sem opt-in, read-only. */
function CoachStudentsRanking() {
  const { t } = useTranslation("dashboard");
  const { data, isLoading } = useQuery({
    queryKey: ["coach-students-leaderboard"],
    queryFn: () => coachDashboard.studentsLeaderboard(90),
  });
  const ranked = data?.ranked ?? [];
  const ineligible = data?.ineligible ?? [];

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-4">
        <p className="text-sm text-muted-foreground animate-pulse">{t("leaderboard.loading")}</p>
      </div>
    );
  }
  if (ranked.length === 0 && ineligible.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {t("leaderboard.coachRankingTitle")}
        </p>
        <p className="text-[11px] text-muted-foreground mt-0.5">{t("leaderboard.coachRankingHint")}</p>
      </div>

      {ranked.length > 0 ? (
        <div className="space-y-1.5">
          {ranked.map((e) => (
            <div key={e.user_id} className="flex items-center gap-2.5">
              <span className={cn("font-mono text-sm font-bold tabular-nums w-5 text-center shrink-0", RANK_TINT(e.rank ?? 0))}>
                {e.rank}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-foreground truncate">{e.display_name}</div>
                <div className="font-mono text-[10px] text-muted-foreground">
                  {Math.round(e.player_elo)} ELO · {e.hands.toLocaleString()} · {e.tournaments}t
                </div>
              </div>
              <span className="font-mono text-lg font-bold tabular-nums text-primary shrink-0">{e.score.toFixed(1)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{t("leaderboard.coachRankingNoneEligible")}</p>
      )}

      {ineligible.length > 0 && (
        <div className="border-t border-border/50 pt-2 space-y-1">
          {ineligible.map((e) => (
            <div key={e.user_id} className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground truncate">{e.display_name}</span>
              <span className="font-mono text-[10px] text-amber-400/80 shrink-0">
                {e.reason ? t(`leaderboard.reason_${e.reason}`, { defaultValue: e.reason }) : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AlunosTab() {
  const navigate = useNavigate();
  const { data: studentsData, isLoading } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });
  const { data: impact } = useQuery({
    queryKey: ["coach-impact"],
    queryFn: () => coachDashboard.impact(30),
  });
  // P1a cockpit: receita do período (indicados / ativos que contam / valor + próxima faixa)
  const { data: finance } = useQuery({
    queryKey: ["coach-finance-summary"],
    queryFn: coachFinance.summary,
  });

  const [search,  setSearch]  = useState("");
  const [status,  setStatus]  = useState<"all" | "active" | "inactive" | "attention">("all");
  const [sortKey, setSortKey] = useState<SortKey>("username");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page,    setPage]    = useState(0);

  const allStudents = studentsData?.students ?? [];

  const filtered = allStudents
    .filter((s) => {
      if (search && !s.username.toLowerCase().includes(search.toLowerCase())) return false;
      if (status === "active"    && !isActivePaid(s)) return false;
      if (status === "inactive"  &&  isActivePaid(s)) return false;
      if (status === "attention" && !needsAttention(s)) return false;
      return true;
    })
    .sort((a, b) => {
      let cmp = 0;
      if (sortKey === "username")          cmp = a.username.localeCompare(b.username);
      else if (sortKey === "total_tournaments") cmp = (a.total_tournaments ?? 0) - (b.total_tournaments ?? 0);
      else if (sortKey === "last_import")  {
        const da = a.recent_tournament?.imported_at ?? "";
        const db = b.recent_tournament?.imported_at ?? "";
        cmp = da.localeCompare(db);
      }
      else if (sortKey === "trend") cmp = (TREND_ORDER[a.trend ?? ""] ?? 3) - (TREND_ORDER[b.trend ?? ""] ?? 3);
      return sortDir === "asc" ? cmp : -cmp;
    });

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
    setPage(0);
  };

  const SortHeader = ({ col, label }: { col: SortKey; label: string }) => (
    <button
      onClick={() => toggleSort(col)}
      className="flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground hover:text-foreground transition-colors"
    >
      {label}
      {sortKey === col
        ? <span className="text-primary">{sortDir === "asc" ? "↑" : "↓"}</span>
        : <span className="opacity-30">↕</span>}
    </button>
  );

  return (
    <div className="space-y-4">
      {/* Cockpit — faixa de receita & saúde (P1a) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px overflow-hidden rounded-xl border border-border bg-border">
        <div className="bg-hud-surface p-4">
          <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Indicados</div>
          <div className="mt-1 font-mono text-2xl font-light tabular-nums text-foreground">{finance?.referred_count ?? allStudents.length}</div>
          <div className="font-mono text-[10px] text-muted-foreground/70">{allStudents.length} vinculados</div>
        </div>
        <div className="bg-hud-surface p-4">
          <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Ativos · conta R$</div>
          <div className="mt-1 font-mono text-2xl font-light tabular-nums text-primary">{finance?.active_students ?? allStudents.filter(isActivePaid).length}</div>
          <div className="font-mono text-[10px] text-muted-foreground/70">pro + import 30d</div>
        </div>
        <div className="bg-hud-surface p-4">
          <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">A receber</div>
          <div className="mt-1 font-mono text-2xl font-light tabular-nums text-foreground">{finance ? fmtCents(finance.amount_cents) : "—"}</div>
          <div className="font-mono text-[10px] text-muted-foreground/70">{finance?.period ?? ""}</div>
        </div>
        <div className="bg-hud-surface p-4">
          <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Próxima faixa</div>
          {finance?.next_tier ? (
            <>
              <div className="mt-1 font-mono text-sm font-bold text-amber-400">
                faltam {finance.next_tier.needed} ativo{finance.next_tier.needed > 1 ? "s" : ""}
              </div>
              <div className="font-mono text-[10px] text-muted-foreground/70">→ {fmtCents(finance.next_tier.rate_cents)}/aluno</div>
            </>
          ) : (
            <div className="mt-1 font-mono text-sm font-bold text-primary">faixa máxima ✓</div>
          )}
        </div>
      </div>

    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-2 space-y-4">
        {/* Toolbar */}
        <div className="flex flex-wrap gap-2">
          <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5 flex-1 min-w-[160px]">
            <Search className="size-3.5 text-muted-foreground shrink-0" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              placeholder="Buscar aluno…"
              className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
          </div>
          {(["all", "active", "inactive", "attention"] as const).map((s) => {
            const attnCount = s === "attention" ? allStudents.filter(needsAttention).length : 0;
            const isAttn = s === "attention";
            return (
              <button
                key={s}
                onClick={() => { setStatus(s); setPage(0); }}
                className={cn(
                  "rounded-md px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors",
                  status === s
                    ? (isAttn ? "bg-amber-400/15 text-amber-400 ring-1 ring-amber-400/40" : "bg-primary/10 text-primary ring-1 ring-primary/30")
                    : (isAttn && attnCount > 0 ? "border border-amber-400/30 text-amber-400 hover:text-amber-300" : "border border-border text-muted-foreground hover:text-foreground")
                )}
              >
                {s === "all" ? "Todos" : s === "active" ? "Ativos" : s === "inactive" ? "Inativos" : `⚠ Atenção${attnCount > 0 ? ` (${attnCount})` : ""}`}
              </button>
            );
          })}
        </div>

        {isLoading && <p className="text-sm text-muted-foreground animate-pulse py-4">Carregando…</p>}

        {!isLoading && filtered.length === 0 && (
          <div className="rounded-xl border border-dashed border-border p-8 text-center">
            <p className="text-sm text-muted-foreground">
              {allStudents.length === 0 ? "Nenhum aluno vinculado ainda." : "Nenhum aluno encontrado com este filtro."}
            </p>
          </div>
        )}

        {!isLoading && filtered.length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-hud-elevated/40">
                <tr>
                  <th className="px-4 py-2.5 text-left"><SortHeader col="username"          label="Aluno" /></th>
                  <th className="px-4 py-2.5 text-right hidden sm:table-cell"><SortHeader col="total_tournaments" label="Torneios" /></th>
                  <th className="px-4 py-2.5 text-right hidden md:table-cell"><SortHeader col="last_import"        label="Último import" /></th>
                  <th className="px-4 py-2.5 text-right hidden sm:table-cell font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Score</th>
                  <th className="px-4 py-2.5 text-center hidden lg:table-cell"><SortHeader col="trend"             label="Tendência" /></th>
                  <th className="px-4 py-2.5 text-center font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paged.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/coach-dashboard/student/${s.id}`)}
                    className="hover:bg-primary/5 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 font-bold text-primary text-xs uppercase">
                          {s.username[0]}
                        </div>
                        <span className="font-medium text-foreground">{s.username}</span>
                        {s.is_referred && (
                          <span className="hidden sm:inline-flex items-center rounded-sm bg-violet-500/10 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-violet-400 ring-1 ring-violet-400/30" title="Indicado pelo seu convite">Indicado</span>
                        )}
                        {(s.critical_pending ?? 0) > 0 && (
                          <span className="inline-flex items-center gap-0.5 rounded-sm bg-red-500/10 px-1.5 py-0.5 font-mono text-[9px] font-bold text-red-400 ring-1 ring-red-500/30" title={`${s.critical_pending} mão(s) crítica(s) sem sua anotação`}>
                            <AlertTriangle className="size-2.5" /> {s.critical_pending}
                          </span>
                        )}
                        {(s.unread ?? 0) > 0 && (
                          <span className="inline-flex items-center gap-0.5 rounded-sm bg-amber-400/10 px-1.5 py-0.5 font-mono text-[9px] font-bold text-amber-400 ring-1 ring-amber-400/30" title={`${s.unread} mensagem(ns) não lida(s)`}>
                            <MessageSquare className="size-2.5" /> {s.unread}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground text-right hidden sm:table-cell">
                      {s.total_tournaments}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground text-right hidden md:table-cell">
                      {fmtImport(s)}
                    </td>
                    <td className={cn("px-4 py-3 font-mono text-xs tabular-nums text-right hidden sm:table-cell", scoreCls(s.recent_tournament?.avg_score))}>
                      {s.recent_tournament?.avg_score != null ? s.recent_tournament.avg_score.toFixed(3) : "—"}
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell">
                      <div className="flex items-center justify-center gap-1.5">
                        <TrendIcon trend={s.trend} />
                        {s.trend && <span className="font-mono text-[10px] text-muted-foreground">{TREND_LABEL[s.trend]}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isActivePaid(s)
                        ? <span className="inline-flex items-center gap-1 rounded-sm bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/20" title="Pro + import nos últimos 30d — conta no seu repasse"><CheckCircle2 className="size-3" /> Ativo · R$</span>
                        : isActive(s)
                        ? <span className="inline-flex items-center gap-1 rounded-sm bg-amber-400/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-400 ring-1 ring-amber-400/30" title="Importou recentemente mas não é Pro — não conta no repasse (oportunidade de conversão)">Recente · free</span>
                        : <span className="inline-flex items-center gap-1 rounded-sm bg-border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground ring-1 ring-border"><Clock className="size-3" /> Inativo</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {pageCount > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                <span className="font-mono text-[10px] text-muted-foreground">
                  {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} de {filtered.length}
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => setPage((p) => p - 1)}
                    disabled={page === 0}
                    className="size-7 flex items-center justify-center rounded-md border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                  >
                    <ChevronLeft className="size-3.5" />
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page >= pageCount - 1}
                    className="size-7 flex items-center justify-center rounded-md border border-border text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
                  >
                    <ChevronRightIcon className="size-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="space-y-4">
        <InviteKeyWidget />
        <CoachStudentsRanking />
        {impact?.top_leaks && impact.top_leaks.length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">Leaks em comum</p>
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
    </div>
  );
}

// ── Tab: Atenção Urgente (BACK-003) ───────────────────────────────────────────

const STREETS = ["preflop", "flop", "turn", "river"];
// FEAT-20: clear/small colapsam em "Erro" no display, então o filtro por severidade
// some — a magnitude vira o Score (ordenado). Erros = small_mistake + clear_mistake.

function UrgentTab() {
  const navigate = useNavigate();
  const { data: studentsData } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });

  const [studentFilter, setStudentFilter] = useState<number | undefined>();
  const [streetFilter, setStreetFilter]   = useState<string | undefined>();

  const { data, isLoading } = useQuery({
    queryKey: ["coach-all-worst", studentFilter, streetFilter],
    queryFn: () => coachDashboard.allWorstDecisions({
      n: 30,
      student_id: studentFilter,
      street: streetFilter,
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
                {["Aluno", "Street", "Jogou", "Correto", "Score", "Veredito", ""].map((h, i) => (
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
                  <td className="px-4 py-2.5 text-xs text-destructive font-medium">{formatAction(d.action_taken)}</td>
                  <td className="px-4 py-2.5 text-xs text-primary font-medium">{formatAction(d.best_action)}</td>
                  <td className={`px-4 py-2.5 font-mono text-xs font-bold ${SCORE_COLOR(d.score)}`}>{d.score}</td>
                  <td className="px-4 py-2.5">
                    <VerdictTag label={d.label} />
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

type Tab = "alunos" | "urgente" | "leaks" | "financeiro" | "efetividade" | "mensagens";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "alunos",       label: "Alunos",           icon: Users },
  { id: "urgente",      label: "Atenção Urgente",  icon: AlertTriangle },
  { id: "leaks",        label: "Leaks Sistêmicos", icon: LayoutDashboard },
  { id: "efetividade",  label: "Efetividade",      icon: TrendingUp },
  { id: "financeiro",   label: "Financeiro",       icon: BarChart2 },
  { id: "mensagens",    label: "Mensagens",         icon: MessageSquare },
];

// ── Mensagens Tab ─────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins  = Math.floor(diff / 60_000);
  if (mins < 1)   return "agora";
  if (mins < 60)  return `${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)   return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7)   return `${days}d`;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function MensagensTab() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["coach-inbox"],
    queryFn: coachDashboard.inbox,
    refetchInterval: 60_000,
  });

  const threads: InboxThread[] = data?.threads ?? [];
  const totalUnread = threads.reduce((s, t) => s + (t.unread_count ?? 0), 0);

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse py-8 text-center">Carregando…</p>;

  if (threads.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <MessageSquare className="size-8 text-muted-foreground/30" />
        <p className="text-sm text-muted-foreground">Nenhuma conversa ainda.</p>
        <p className="text-xs text-muted-foreground">Quando um aluno enviar uma mensagem, aparecerá aqui.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {totalUnread > 0 && (
        <p className="font-mono text-[10px] text-destructive uppercase tracking-widest-2">
          {totalUnread} mensagem{totalUnread > 1 ? "ns" : ""} não lida{totalUnread > 1 ? "s" : ""}
        </p>
      )}
      <div className="rounded-xl border border-border bg-hud-surface overflow-hidden divide-y divide-border">
        {threads.map((t) => (
          <button
            key={t.student_id}
            type="button"
            onClick={() => navigate(`/coach-dashboard/student/${t.student_id}?tab=mensagens`)}
            className="flex w-full items-center gap-4 px-4 py-3 hover:bg-muted/20 transition-colors text-left"
          >
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 font-bold text-primary text-sm uppercase select-none">
              {t.student_username.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-sm text-foreground ${t.unread_count > 0 ? "font-bold" : "font-semibold"}`}>
                {t.student_username}
              </p>
              <p className={`font-mono text-xs truncate max-w-[340px] ${t.unread_count > 0 ? "text-foreground" : "text-muted-foreground"}`}>
                {t.last_sender_role === "student" && t.unread_count === 0 && (
                  <span className="text-amber-400 mr-1">↩</span>
                )}
                {t.last_message_body}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0">
              <span className="font-mono text-[10px] text-muted-foreground">{relativeTime(t.last_message_at)}</span>
              {t.unread_count > 0 && (
                <span className="flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground px-1">
                  {t.unread_count > 9 ? "9+" : t.unread_count}
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

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

  const { data: inboxData } = useQuery({
    queryKey: ["coach-inbox"],
    queryFn: coachDashboard.inbox,
    refetchInterval: 60_000,
  });

  const inboxUnread = (inboxData?.threads ?? []).reduce((s, t) => s + (t.unread_count ?? 0), 0);
  const summary = impact?.summary;

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-[1440px] px-4 py-8 space-y-8 md:px-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard do Coach</h1>
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
        <div className="flex overflow-x-auto overflow-y-hidden border-b border-border gap-0 scrollbar-none">
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
              {t.id === "mensagens" && inboxUnread > 0 && (
                <span className="flex items-center justify-center min-w-[16px] h-4 rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground px-1">
                  {inboxUnread > 9 ? "9+" : inboxUnread}
                </span>
              )}
            </button>
          ))}
        </div>

        {tab === "alunos"       && <AlunosTab />}
        {tab === "urgente"      && <UrgentTab />}
        {tab === "leaks"        && <LeaksTab />}
        {tab === "efetividade"  && <EfetividadeTab />}
        {tab === "financeiro"   && <FinanceiroTab />}
        {tab === "mensagens"    && <MensagensTab />}
      </main>
    </div>
  );
}
