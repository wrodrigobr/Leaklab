import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Trophy, AlertTriangle, BookOpen, LayoutDashboard,
  ChevronRight, Play, TrendingUp, TrendingDown, Minus
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { coachDashboard, StudentWorstDecision } from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar
} from "recharts";

// ── shared ────────────────────────────────────────────────────────────────────

const LABEL_COLOR: Record<string, string> = {
  clear_mistake: "text-destructive",
  small_mistake: "text-amber-400",
  marginal:      "text-yellow-500",
  standard:      "text-primary",
};

const SCORE_COLOR = (s: number) =>
  s >= 80 ? "text-primary" : s >= 60 ? "text-amber-400" : "text-destructive";

function StatPill({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-background px-4 py-3 text-center space-y-0.5">
      <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground">{label}</p>
      <p className="text-xl font-bold text-foreground">{value}</p>
      {sub && <p className="font-mono text-[9px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

// ── tabs ──────────────────────────────────────────────────────────────────────

type Tab = "overview" | "tournaments" | "worst" | "study";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "overview",    label: "Visão Geral",     icon: LayoutDashboard },
  { id: "tournaments", label: "Torneios",         icon: Trophy },
  { id: "worst",       label: "Mãos Críticas",   icon: AlertTriangle },
  { id: "study",       label: "Plano de Estudos", icon: BookOpen },
];

// ── Overview tab ──────────────────────────────────────────────────────────────

function OverviewTab({ studentId }: { studentId: number }) {
  const { data: history, isLoading: loadingHist } = useQuery({
    queryKey: ["coach-student-history", studentId],
    queryFn: () => coachDashboard.studentHistory(studentId, 90),
  });

  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ["coach-student-stats", studentId],
    queryFn: () => coachDashboard.studentStats(studentId, 90),
  });

  const { data: breakdown, isLoading: loadingBd } = useQuery({
    queryKey: ["coach-student-breakdown", studentId],
    queryFn: () => coachDashboard.studentBreakdown(studentId, 90),
  });

  const chartData = (history?.evolution ?? []).map((p) => ({
    date: p.played_at
      ? new Date(p.played_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })
      : "?",
    score: typeof p.avg_score === "number" ? +p.avg_score.toFixed(1) : null,
    std:   typeof p.standard_pct === "number" ? +p.standard_pct.toFixed(1) : null,
  }));

  const streetData = Object.entries(breakdown?.by_street ?? {}).map(([street, v]) => ({
    street,
    score: +(v.avg_score ?? 0).toFixed(1),
    std:   +(((v.standard_rate ?? 0) * 100)).toFixed(1),
  }));

  const posData = Object.entries(breakdown?.by_position ?? {})
    .sort((a, b) => (b[1].standard_rate ?? 0) - (a[1].standard_rate ?? 0))
    .map(([pos, v]) => ({
      pos,
      std: +(((v.standard_rate ?? 0) * 100)).toFixed(1),
      n: v.n,
    }));

  if (loadingHist || loadingStats || loadingBd) {
    return <p className="text-sm text-muted-foreground animate-pulse py-8">Carregando dados…</p>;
  }

  const s = stats;

  return (
    <div className="space-y-6">
      {/* HUD stats */}
      {s && (
        <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
          <StatPill label="VPIP"  value={s.vpip  != null ? `${s.vpip}%`  : "—"} sub="Voluntário" />
          <StatPill label="PFR"   value={s.pfr   != null ? `${s.pfr}%`   : "—"} sub="Preflop raise" />
          <StatPill label="AF"    value={s.af     != null ? `${s.af}x`    : "—"} sub="Agressão" />
          <StatPill label="3BET"  value={s.three_bet != null ? `${s.three_bet}%` : "—"} sub="Re-raise PF" />
          <StatPill label="F3B"   value={s.fold_to_3bet != null ? `${s.fold_to_3bet}%` : "—"} sub="Fold to 3bet" />
          <StatPill label="Flop%" value={s.flop_bet_pct != null ? `${s.flop_bet_pct}%` : "—"} sub="Bet flop" />
          <StatPill label="WTSD"  value={s.wtsd   != null ? `${s.wtsd}%`  : "—"} sub="Vai a SD" />
          <StatPill label="W$SD"  value={s.w_at_sd != null ? `${s.w_at_sd}%` : "—"} sub="Ganha SD" />
        </div>
      )}

      {/* Evolution chart */}
      {chartData.length > 0 && (
        <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Evolução (90 dias)
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ background: "hsl(var(--hud-surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 11 }} />
              <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} name="Score" />
              <Line type="monotone" dataKey="std" stroke="hsl(var(--primary) / 0.4)" strokeWidth={1.5} dot={false} name="Standard %" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        {/* Leaks */}
        {(history?.leaks ?? []).length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              Principais Leaks
            </p>
            {history!.leaks.map((l) => (
              <div key={l.spot} className="flex items-center justify-between border-b border-border/40 last:border-0 pb-2 last:pb-0">
                <span className="text-sm text-foreground truncate">{l.spot}</span>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="font-mono text-[10px] text-muted-foreground">{l.n}x</span>
                  <span className={`font-mono text-xs font-bold ${SCORE_COLOR(l.avg_score)}`}>
                    {l.avg_score.toFixed(0)} pts
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Por street */}
        {streetData.length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              Performance por Street
            </p>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={streetData} barCategoryGap="30%">
                <XAxis dataKey="street" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: "hsl(var(--hud-surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="std" fill="hsl(var(--primary))" name="Standard %" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Por posição */}
      {posData.length > 0 && (
        <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-2">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Performance por Posição
          </p>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
            {posData.map(({ pos, std, n }) => (
              <div key={pos} className="rounded-lg bg-background border border-border px-3 py-2 text-center">
                <p className="font-mono text-[9px] uppercase text-muted-foreground">{pos}</p>
                <p className={`text-lg font-bold ${SCORE_COLOR(std)}`}>{std}%</p>
                <p className="font-mono text-[9px] text-muted-foreground">{n} dec</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tournaments tab ────────────────────────────────────────────────────────────

function TournamentsTab({ studentId }: { studentId: number }) {
  const { data: history, isLoading } = useQuery({
    queryKey: ["coach-student-history", studentId],
    queryFn: () => coachDashboard.studentHistory(studentId, 90),
  });

  const [selectedTid, setSelectedTid] = useState<string | null>(null);

  const { data: detail, isLoading: loadingDetail } = useQuery({
    queryKey: ["coach-student-tournament", studentId, selectedTid],
    queryFn: () => coachDashboard.studentTournament(studentId, selectedTid!),
    enabled: !!selectedTid,
  });

  const navigate = useNavigate();

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse py-8">Carregando…</p>;

  const tournaments = history?.tournaments ?? [];

  if (selectedTid && detail) {
    const t = detail.tournament;
    const decisions = detail.decisions;
    return (
      <div className="space-y-4">
        <button
          onClick={() => setSelectedTid(null)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" /> Lista de torneios
        </button>

        <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-xs text-muted-foreground">{t.tournament_id}</p>
              <p className="text-lg font-bold text-foreground">{t.hero} — {t.site}</p>
            </div>
            <div className="text-right">
              <p className={`text-2xl font-bold ${SCORE_COLOR(t.avg_score ?? 0)}`}>
                {t.avg_score?.toFixed(1) ?? "—"} pts
              </p>
              <p className="font-mono text-[10px] text-muted-foreground">{t.hands_count} mãos</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-background/50">
                <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Street</th>
                <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Ação</th>
                <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Melhor</th>
                <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Score</th>
                <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Label</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {decisions.map((d) => (
                <tr key={d.id} className="border-b border-border/40 last:border-0 hover:bg-primary/5 transition-colors">
                  <td className="px-4 py-2 font-mono text-xs capitalize">{d.street}</td>
                  <td className="px-4 py-2 text-xs">{d.action_taken}</td>
                  <td className="px-4 py-2 text-xs">{d.best_action}</td>
                  <td className={`px-4 py-2 font-mono text-xs font-bold ${SCORE_COLOR(d.score)}`}>{d.score}</td>
                  <td className={`px-4 py-2 font-mono text-[10px] capitalize ${LABEL_COLOR[d.label] ?? ""}`}>{d.label}</td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => navigate(`/replayer?t=${t.tournament_id}&h=${d.hand_id}&student=${studentId}`)}
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
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tournaments.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">Nenhum torneio encontrado.</p>
      )}
      {tournaments.map((t) => (
        <button
          key={t.id}
          onClick={() => setSelectedTid(t.tournament_id)}
          className="w-full flex items-center justify-between rounded-lg border border-border bg-hud-surface px-4 py-3 hover:border-primary/40 hover:bg-primary/5 transition-all text-left"
        >
          <div>
            <p className="font-mono text-xs text-muted-foreground">{t.tournament_id}</p>
            <p className="text-sm font-medium text-foreground">{t.site} — {t.hero}</p>
            <p className="font-mono text-[10px] text-muted-foreground">{t.hands_count} mãos · {t.decisions_count} decisões</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className={`font-mono text-lg font-bold ${SCORE_COLOR(t.avg_score ?? 0)}`}>
                {t.avg_score?.toFixed(1) ?? "—"}
              </p>
              <p className="font-mono text-[9px] text-muted-foreground">pts</p>
            </div>
            {t.profit != null && (
              <div className="text-right">
                <p className={`font-mono text-sm font-bold ${t.profit >= 0 ? "text-primary" : "text-destructive"}`}>
                  {t.profit >= 0 ? "+" : ""}{t.profit.toFixed(0)}
                </p>
                <p className="font-mono text-[9px] text-muted-foreground">profit</p>
              </div>
            )}
            <ChevronRight className="size-4 text-muted-foreground" />
          </div>
        </button>
      ))}
      {loadingDetail && <p className="text-xs text-muted-foreground animate-pulse">Carregando torneio…</p>}
    </div>
  );
}

// ── Worst Decisions tab ───────────────────────────────────────────────────────

function WorstTab({ studentId }: { studentId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["coach-student-worst", studentId],
    queryFn: () => coachDashboard.studentWorstDecisions(studentId, 30),
  });

  const navigate = useNavigate();

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse py-8">Carregando…</p>;

  const decisions = data?.decisions ?? [];

  if (decisions.length === 0) {
    return <p className="text-sm text-muted-foreground py-8 text-center">Nenhuma decisão crítica encontrada.</p>;
  }

  return (
    <div className="space-y-2">
      <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
        {decisions.length} piores decisões — ordenadas por score (maior erro primeiro)
      </p>
      {decisions.map((d: StudentWorstDecision) => (
        <div
          key={d.id}
          className="rounded-lg border border-border bg-hud-surface px-4 py-3 space-y-2"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className={`font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                d.label === "clear_mistake"
                  ? "bg-destructive/10 text-destructive ring-1 ring-destructive/30"
                  : "bg-amber-400/10 text-amber-400 ring-1 ring-amber-400/30"
              }`}>
                {d.label === "clear_mistake" ? "Erro claro" : "Erro pequeno"}
              </span>
              <span className="font-mono text-xs capitalize text-muted-foreground">{d.street}</span>
              {d.position && (
                <span className="font-mono text-[10px] text-muted-foreground">{d.position}</span>
              )}
            </div>
            <span className={`font-mono text-xl font-bold ${SCORE_COLOR(d.score)}`}>{d.score}</span>
          </div>

          <div className="flex items-center gap-6 text-sm">
            <div>
              <p className="font-mono text-[9px] text-muted-foreground uppercase">Jogou</p>
              <p className="font-medium text-destructive">{d.action_taken}</p>
            </div>
            <div>
              <p className="font-mono text-[9px] text-muted-foreground uppercase">Correto</p>
              <p className="font-medium text-primary">{d.best_action}</p>
            </div>
            {d.m_ratio != null && (
              <div>
                <p className="font-mono text-[9px] text-muted-foreground uppercase">M-Ratio</p>
                <p className="font-mono text-xs">{d.m_ratio.toFixed(1)}</p>
              </div>
            )}
            {d.icm_pressure && (
              <div>
                <p className="font-mono text-[9px] text-muted-foreground uppercase">ICM</p>
                <p className="font-mono text-xs capitalize">{d.icm_pressure}</p>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] text-muted-foreground">{d.tournament_id}</p>
            <button
              onClick={() => navigate(`/replayer?t=${d.tournament_id}&h=${d.hand_id}&student=${studentId}`)}
              className="flex items-center gap-1.5 font-mono text-[10px] font-bold text-primary hover:underline"
            >
              <Play className="size-3" /> Ver Replay
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Study Plan tab ────────────────────────────────────────────────────────────

const PRIORITY_STYLE: Record<string, string> = {
  alta:  "border-destructive/40 bg-destructive/5",
  media: "border-amber-400/40 bg-amber-400/5",
  baixa: "border-primary/20 bg-primary/5",
};

function StudyTab({ studentId }: { studentId: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["coach-student-study", studentId],
    queryFn: () => coachDashboard.studentStudyPlan(studentId, 90),
  });

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse py-8">Gerando plano de estudos do aluno…</p>;
  if (isError || !data) return <p className="text-sm text-destructive py-8">Erro ao carregar plano de estudos.</p>;
  if (!data.cards || data.cards.length === 0) {
    return <p className="text-sm text-muted-foreground py-8 text-center">Dados insuficientes para gerar plano.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-hud-surface px-4 py-3">
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-1">
          Nível: {data.nivel}
        </p>
        <p className="text-sm text-foreground">{data.resumo}</p>
      </div>

      {data.cards.map((card, i) => (
        <div
          key={i}
          className={`rounded-xl border p-5 space-y-3 ${PRIORITY_STYLE[card.prioridade] ?? "border-border bg-hud-surface"}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">{card.icone}</span>
              <h3 className="font-semibold text-foreground">{card.titulo}</h3>
            </div>
            <span className={`shrink-0 font-mono text-[9px] font-bold uppercase px-2 py-0.5 rounded ring-1 ${
              card.prioridade === "alta"
                ? "text-destructive ring-destructive/30 bg-destructive/10"
                : card.prioridade === "media"
                ? "text-amber-400 ring-amber-400/30 bg-amber-400/10"
                : "text-primary ring-primary/30 bg-primary/10"
            }`}>
              {card.prioridade}
            </span>
          </div>

          <p className="text-sm text-muted-foreground">{card.diagnostico}</p>

          {card.conceitos?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {card.conceitos.map((c) => (
                <span key={c} className="font-mono text-[10px] bg-background border border-border rounded px-2 py-0.5 text-muted-foreground">
                  {c}
                </span>
              ))}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-3 pt-1">
            <div>
              <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-1">Exercício</p>
              <p className="text-sm text-foreground">{card.exercicio}</p>
            </div>
            <div>
              <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-1">Métrica</p>
              <p className="text-sm text-foreground">{card.metrica}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function StudentDetail() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);
  const [tab, setTab] = useState<Tab>("overview");

  const { data: studentsData } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });

  const studentName = studentsData?.students.find((s) => s.id === studentId)?.username ?? `Aluno #${studentId}`;

  const { data: history } = useQuery({
    queryKey: ["coach-student-history", studentId],
    queryFn: () => coachDashboard.studentHistory(studentId, 90),
    enabled: !isNaN(studentId),
  });

  const tournaments = history?.tournaments ?? [];
  const lastScore = tournaments[0]?.avg_score;
  const prevScore = tournaments[1]?.avg_score;
  const trend =
    lastScore != null && prevScore != null
      ? lastScore < prevScore ? "improving" : lastScore > prevScore ? "worsening" : "stable"
      : null;

  const TrendIcon =
    trend === "improving" ? TrendingUp :
    trend === "worsening" ? TrendingDown : Minus;

  const trendColor =
    trend === "improving" ? "text-primary" :
    trend === "worsening" ? "text-destructive" : "text-muted-foreground";

  return (
    <div className="min-h-dvh bg-background">
      <HudHeader />
      <main className="mx-auto max-w-5xl px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Link
            to="/coach-dashboard"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" /> Dashboard do Coach
          </Link>
        </div>

        {history && (
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">
                {studentName}
              </h1>
              <div className="flex items-center gap-3 mt-1">
                <span className="font-mono text-xs text-muted-foreground">
                  {tournaments.length} torneios analisados
                </span>
                {trend && (
                  <span className={`flex items-center gap-1 font-mono text-xs font-bold ${trendColor}`}>
                    <TrendIcon className="size-3.5" />
                    {trend === "improving" ? "Melhorando" : trend === "worsening" ? "Piorando" : "Estável"}
                  </span>
                )}
              </div>
            </div>
            {lastScore != null && (
              <div className="text-right">
                <p className={`text-3xl font-bold ${SCORE_COLOR(lastScore)}`}>
                  {lastScore.toFixed(1)}
                </p>
                <p className="font-mono text-[10px] text-muted-foreground">último score</p>
              </div>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-border gap-0">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors ${
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

        {/* Tab content */}
        {tab === "overview"    && <OverviewTab     studentId={studentId} />}
        {tab === "tournaments" && <TournamentsTab  studentId={studentId} />}
        {tab === "worst"       && <WorstTab        studentId={studentId} />}
        {tab === "study"       && <StudyTab        studentId={studentId} />}
      </main>
    </div>
  );
}
