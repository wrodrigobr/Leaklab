import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft, Trophy, AlertTriangle, BookOpen, LayoutDashboard,
  ChevronRight, Play, TrendingUp, TrendingDown, Minus,
  CheckCircle2, MessageSquare, PenLine, Trash2, X, Check, Loader2,
  Activity, Flag, Star, BarChart2, Save, Send, FileText
} from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { formatAction } from "@/lib/utils";
import { PlayingCard } from "@/components/hud/PlayingCard";
import { LevelCard } from "@/components/hud/LevelCard";
import { coachDashboard, CoachTemplate, CoachMessage, StudentWorstDecision, StudyCard, StudyOverride, CoachAnnotation, CoachOverrideLabel, ActivityEvent, ProgressReport } from "@/lib/api";
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

type Tab = "overview" | "tournaments" | "worst" | "study" | "progress" | "mensagens";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "overview",    label: "Visão Geral",     icon: LayoutDashboard },
  { id: "tournaments", label: "Torneios",         icon: Trophy },
  { id: "worst",       label: "Mãos Críticas",   icon: AlertTriangle },
  { id: "study",       label: "Plano de Estudos", icon: BookOpen },
  { id: "progress",   label: "Progresso",         icon: Activity },
  { id: "mensagens",  label: "Mensagens",          icon: MessageSquare },
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

  const { data: levelData } = useQuery({
    queryKey: ["coach-student-level", studentId],
    queryFn: () => coachDashboard.studentLevel(studentId),
    staleTime: 60_000,
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

  // Comparativo histórico: primeiros 3 vs últimos 3 torneios
  const evo = history?.evolution ?? [];
  const slice3 = (arr: typeof evo) => arr.filter((e) => e.avg_score != null);
  const avg = (arr: typeof evo, key: "avg_score" | "standard_pct") => {
    const vals = arr.map((e) => e[key]).filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  };
  const early  = slice3(evo).slice(0, 3);
  const recent = slice3(evo).slice(-3);
  const earlyScore  = avg(early,  "avg_score");
  const recentScore = avg(recent, "avg_score");
  const earlyStd    = avg(early,  "standard_pct");
  const recentStd   = avg(recent, "standard_pct");
  const deltaScore  = earlyScore != null && recentScore != null ? recentScore - earlyScore : null;
  const deltaStd    = earlyStd   != null && recentStd   != null ? recentStd   - earlyStd   : null;

  if (loadingHist || loadingStats || loadingBd) {
    return <p className="text-sm text-muted-foreground animate-pulse py-8">Carregando dados…</p>;
  }

  const s = stats;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">

      {/* ── Main column ──────────────────────────────────────────────────── */}
      <div className="space-y-6 lg:col-span-8">
        {levelData?.level && <LevelCard data={levelData} compact showStudyLink={false} />}

        {/* HUD stats */}
        {s && (
          <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
            <StatPill label="VPIP"  value={s.vpip  != null ? `${s.vpip}%`  : "—"} sub="Voluntário" />
            <StatPill label="PFR"   value={s.pfr   != null ? `${s.pfr}%`   : "—"} sub="Preflop raise" />
            <StatPill label="AF"    value={s.af     != null ? `${s.af}x`    : "—"} sub="Agressão" />
            <StatPill label="3BET"  value={s.three_bet != null ? `${s.three_bet}%` : "—"} sub="Re-raise PF" />
            <StatPill label="F3B"   value={s.fold_to_3bet != null ? `${s.fold_to_3bet}%` : "—"} sub="Fold to 3bet" />
            <StatPill label="C-Bet" value={s.cbet_pct != null ? `${s.cbet_pct}%` : "—"} sub="C-bet flop" />
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
            <ResponsiveContainer width="100%" height={220}>
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

        {/* Comparativo histórico */}
        {evo.length >= 2 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              Comparativo — primeiros 3 vs últimos 3 torneios
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: "Score Inicial",    value: earlyScore?.toFixed(1),  unit: "pts" },
                { label: "Score Atual",      value: recentScore?.toFixed(1), unit: "pts" },
                { label: "Standard Inicial", value: earlyStd?.toFixed(1),    unit: "%" },
                { label: "Standard Atual",   value: recentStd?.toFixed(1),   unit: "%" },
              ].map(({ label, value, unit }) => (
                <div key={label} className="rounded-lg bg-background border border-border px-3 py-2 text-center">
                  <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider">{label}</p>
                  <p className="text-xl font-bold text-foreground">{value ?? "—"}{value ? ` ${unit}` : ""}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-4">
              {deltaScore != null && (
                <div className={`flex items-center gap-1.5 text-sm font-semibold ${deltaScore > 0 ? "text-destructive" : deltaScore < 0 ? "text-primary" : "text-muted-foreground"}`}>
                  {deltaScore < 0 ? <TrendingDown className="size-4" /> : deltaScore > 0 ? <TrendingUp className="size-4" /> : <Minus className="size-4" />}
                  Score: {deltaScore > 0 ? "+" : ""}{deltaScore.toFixed(1)} pts
                  <span className="text-xs font-normal text-muted-foreground">
                    {deltaScore < 0 ? "(melhorou)" : deltaScore > 0 ? "(piorou)" : "(estável)"}
                  </span>
                </div>
              )}
              {deltaStd != null && (
                <div className={`flex items-center gap-1.5 text-sm font-semibold ${deltaStd > 0 ? "text-primary" : deltaStd < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                  Standard: {deltaStd > 0 ? "+" : ""}{deltaStd.toFixed(1)}%
                  <span className="text-xs font-normal text-muted-foreground">
                    {deltaStd > 0 ? "(melhorou)" : deltaStd < 0 ? "(piorou)" : "(estável)"}
                  </span>
                </div>
              )}
              <span className="font-mono text-[10px] text-muted-foreground ml-auto">{evo.length} torneios no período</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Aside ────────────────────────────────────────────────────────── */}
      <aside className="space-y-6 lg:col-span-4 order-first lg:order-none">
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

        {/* Por posição */}
        {posData.length > 0 && (
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-2">
            <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              Performance por Posição
            </p>
            <div className="grid grid-cols-3 gap-2">
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
      </aside>

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
              <p className="font-mono text-xs text-muted-foreground">{t.site} • {t.tournament_id}</p>
              <p className="text-lg font-bold text-foreground">{t.tournament_name ?? t.site}</p>
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
                  <td className="px-4 py-2 text-xs">{formatAction(d.action_taken)}</td>
                  <td className="px-4 py-2 text-xs">{formatAction(d.best_action)}</td>
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
            <p className="font-mono text-xs text-muted-foreground">{t.site} • {t.tournament_id}</p>
            <p className="text-sm font-medium text-foreground">{t.tournament_name ?? t.site}</p>
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

function parseHeroCards(s: string): { rank: string; suit: string }[] {
  const cards = [];
  for (let i = 0; i + 1 < s.length; i += 2) cards.push({ rank: s[i], suit: s[i + 1] });
  return cards;
}

function parseBoardCards(s: string): { rank: string; suit: string }[] {
  try { return (JSON.parse(s) as string[]).map((c) => ({ rank: c[0], suit: c[1] })); }
  catch { return []; }
}

const POKER_ACTIONS = [
  "", "fold", "check", "call", "bet", "raise", "re-raise", "all-in",
];

const OVERRIDE_LABELS: { value: CoachOverrideLabel; label: string; color: string }[] = [
  { value: null,           label: "— Sem veredito",  color: "text-muted-foreground" },
  { value: "standard",    label: "✓ Jogada Correta", color: "text-primary" },
  { value: "marginal",    label: "~ Marginal",        color: "text-yellow-500" },
  { value: "small_mistake", label: "⚠ Erro Pequeno", color: "text-amber-400" },
  { value: "clear_mistake", label: "✕ Erro Claro",   color: "text-destructive" },
];

function AnnotationForm({
  studentId, decisionId, existing, onDone,
}: {
  studentId: number;
  decisionId: number;
  existing: CoachAnnotation | undefined;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  const [comment, setComment]         = useState(existing?.comment ?? "");
  const [mode, setMode]               = useState<"complement"|"replace">(existing?.mode ?? "complement");
  const [coachAction, setCoachAction] = useState(existing?.coach_action ?? "");
  const [overrideLabel, setOverrideLabel] = useState<CoachOverrideLabel>(existing?.coach_override_label ?? null);

  const save = useMutation({
    mutationFn: () => coachDashboard.upsertAnnotation(studentId, {
      decision_id: decisionId, comment, mode,
      coach_action: coachAction || undefined,
      coach_override_label: overrideLabel,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["coach-annotations", studentId] }); onDone(); },
  });

  const remove = useMutation({
    mutationFn: () => coachDashboard.deleteAnnotation(studentId, decisionId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["coach-annotations", studentId] }); onDone(); },
  });

  const selectCls = "w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40";

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 p-3 space-y-3 mt-2">
      <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
        Anotação do Coach
      </p>

      {/* Mode */}
      <div className="flex gap-2">
        {(["complement", "replace"] as const).map((m) => (
          <button key={m} type="button" onClick={() => setMode(m)}
            className={`flex-1 py-1.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest-2 border transition-colors ${
              mode === m
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:border-primary/50"
            }`}
          >
            {m === "complement" ? "Complementar" : "Substituir IA"}
          </button>
        ))}
      </div>

      {/* Comment */}
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={3}
        placeholder="Sua análise desta decisão…"
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
      />

      <div className="grid grid-cols-2 gap-2">
        {/* Coach action — combo */}
        <div className="space-y-1">
          <label className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
            Ação correta
          </label>
          <select value={coachAction} onChange={(e) => setCoachAction(e.target.value)} className={selectCls}>
            {POKER_ACTIONS.map((a) => (
              <option key={a} value={a}>{a || "— Não especificar"}</option>
            ))}
          </select>
        </div>

        {/* Override label — combo */}
        <div className="space-y-1">
          <label className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
            Classificação
          </label>
          <select
            value={overrideLabel ?? ""}
            onChange={(e) => setOverrideLabel((e.target.value || null) as CoachOverrideLabel)}
            className={selectCls}
          >
            {OVERRIDE_LABELS.map((o) => (
              <option key={String(o.value)} value={o.value ?? ""}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => save.mutate()} disabled={!comment.trim() || save.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] font-bold uppercase text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {save.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
          Salvar
        </button>
        <button onClick={onDone}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground hover:text-foreground"
        >
          <X className="size-3" /> Cancelar
        </button>
        {existing && (
          <button
            onClick={() => remove.mutate()} disabled={remove.isPending}
            className="ml-auto inline-flex items-center gap-1.5 font-mono text-[10px] text-destructive hover:underline disabled:opacity-50"
          >
            <Trash2 className="size-3" /> Remover
          </button>
        )}
      </div>
    </div>
  );
}

function WorstTab({ studentId }: { studentId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["coach-student-worst", studentId],
    queryFn: () => coachDashboard.studentWorstDecisions(studentId, 30),
  });
  const { data: annData } = useQuery({
    queryKey: ["coach-annotations", studentId],
    queryFn: () => coachDashboard.getAnnotations(studentId),
  });

  const navigate = useNavigate();
  const [editing, setEditing] = useState<number | null>(null);

  const annotationMap = Object.fromEntries(
    (annData?.annotations ?? []).map((a) => [a.decision_id, a])
  );

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse py-8">Carregando…</p>;

  const decisions = data?.decisions ?? [];
  if (decisions.length === 0)
    return <p className="text-sm text-muted-foreground py-8 text-center">Nenhuma decisão crítica encontrada.</p>;

  return (
    <div className="space-y-2">
      <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest-2">
        {decisions.length} piores decisões — ordenadas por score (maior erro primeiro)
      </p>
      {decisions.map((d: StudentWorstDecision) => {
        const heroCards  = d.hero_cards ? parseHeroCards(d.hero_cards) : [];
        const boardCards = d.board ? parseBoardCards(d.board) : [];
        const annotation = annotationMap[d.id];
        const isEditing  = editing === d.id;

        return (
          <div key={d.id} className="rounded-lg border border-border bg-hud-surface px-4 py-3 space-y-2">
            {/* Label + street + score */}
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
                {d.position && <span className="font-mono text-[10px] text-muted-foreground">{d.position}</span>}
                {annotation && (
                  <span className="flex items-center gap-1 font-mono text-[9px] text-primary">
                    <MessageSquare className="size-3" /> Anotado
                  </span>
                )}
              </div>
              <span className={`font-mono text-xl font-bold ${SCORE_COLOR(d.score)}`}>{d.score}</span>
            </div>

            {/* Cards */}
            {(heroCards.length > 0 || boardCards.length > 0) && (
              <div className="flex items-center gap-4 py-1">
                {heroCards.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <p className="font-mono text-[9px] text-muted-foreground uppercase mr-1">Mão</p>
                    {heroCards.map((c, i) => (
                      <PlayingCard key={i} card={{ rank: c.rank, suit: c.suit as "s"|"h"|"d"|"c" }} size="sm" />
                    ))}
                  </div>
                )}
                {boardCards.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <p className="font-mono text-[9px] text-muted-foreground uppercase mr-1">Board</p>
                    {boardCards.map((c, i) => (
                      <PlayingCard key={i} card={{ rank: c.rank, suit: c.suit as "s"|"h"|"d"|"c" }} size="sm" />
                    ))}
                  </div>
                )}
              </div>
            )}

            <p className="font-mono text-[9px] text-muted-foreground">ID: {d.hand_id}</p>

            {/* Actions */}
            <div className="flex items-center gap-6 text-sm">
              <div>
                <p className="font-mono text-[9px] text-muted-foreground uppercase">Jogou</p>
                <p className="font-medium text-destructive">{formatAction(d.action_taken)}</p>
              </div>
              <div>
                <p className="font-mono text-[9px] text-muted-foreground uppercase">Correto</p>
                <p className="font-medium text-primary">{formatAction(d.best_action)}</p>
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

            {/* Existing annotation display */}
            {annotation && !isEditing && (
              <div className={`rounded-md px-3 py-2 text-sm space-y-1 ${
                annotation.mode === "replace"
                  ? "border border-primary/40 bg-primary/5"
                  : "border border-border bg-background"
              }`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-mono text-[9px] uppercase text-primary tracking-widest-2">
                    {annotation.mode === "replace" ? "Coach (substitui IA)" : "Coach (complementa)"}
                  </p>
                  {annotation.coach_override_label && (
                    <span className={`font-mono text-[9px] font-bold px-1.5 py-0.5 rounded ring-1 ${
                      annotation.coach_override_label === "standard"
                        ? "text-primary ring-primary/30 bg-primary/10"
                        : annotation.coach_override_label === "marginal"
                        ? "text-yellow-500 ring-yellow-500/30 bg-yellow-500/10"
                        : annotation.coach_override_label === "small_mistake"
                        ? "text-amber-400 ring-amber-400/30 bg-amber-400/10"
                        : "text-destructive ring-destructive/30 bg-destructive/10"
                    }`}>
                      {annotation.coach_override_label === "standard" ? "✓ Correta"
                        : annotation.coach_override_label === "marginal" ? "~ Marginal"
                        : annotation.coach_override_label === "small_mistake" ? "⚠ Erro Pequeno"
                        : "✕ Erro Claro"}
                    </span>
                  )}
                </div>
                <p className="text-foreground leading-relaxed">{annotation.comment}</p>
                {annotation.coach_action && (
                  <p className="font-mono text-[10px] text-primary">
                    → Ação: {annotation.coach_action}
                  </p>
                )}
              </div>
            )}

            {/* Annotation form */}
            {isEditing && (
              <AnnotationForm
                studentId={studentId}
                decisionId={d.id}
                existing={annotation}
                onDone={() => setEditing(null)}
              />
            )}

            {/* Footer */}
            <div className="flex items-center justify-between pt-1">
              <p className="font-mono text-[10px] text-muted-foreground">{d.tournament_id}</p>
              <div className="flex items-center gap-3">
                {!isEditing && (
                  <button
                    onClick={() => setEditing(d.id)}
                    className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors"
                  >
                    <PenLine className="size-3" />
                    {annotation ? "Editar nota" : "Anotar"}
                  </button>
                )}
                <button
                  onClick={() => navigate(`/replayer?t=${d.tournament_id}&h=${d.hand_id}&student=${studentId}`)}
                  className="flex items-center gap-1.5 font-mono text-[10px] font-bold text-primary hover:underline"
                >
                  <Play className="size-3" /> Ver Replay
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Study Plan tab ────────────────────────────────────────────────────────────

const PRIORITY_STYLE: Record<string, string> = {
  alta:  "border-destructive/40 bg-destructive/5",
  media: "border-amber-400/40 bg-amber-400/5",
  baixa: "border-primary/20 bg-primary/5",
};

type EditMode = "comment" | "replace" | null;

function StudyCardItem({
  card,
  override,
  studentId,
}: {
  card: StudyCard;
  override: StudyOverride | undefined;
  studentId: number;
}) {
  const qc = useQueryClient();
  const [editMode, setEditMode] = useState<EditMode>(null);
  const [noteText, setNoteText] = useState(override?.note ?? "");
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [customTitle, setCustomTitle] = useState(() => {
    try { return JSON.parse(override?.custom_card ?? "{}").titulo ?? card.titulo; } catch { return card.titulo; }
  });
  const [customDiag, setCustomDiag] = useState(() => {
    try { return JSON.parse(override?.custom_card ?? "{}").diagnostico ?? card.diagnostico; } catch { return card.diagnostico; }
  });
  const [customEx, setCustomEx] = useState(() => {
    try { return JSON.parse(override?.custom_card ?? "{}").exercicio ?? card.exercicio; } catch { return card.exercicio; }
  });
  const [customLivros, setCustomLivros] = useState(() => {
    try { return (JSON.parse(override?.custom_card ?? "{}").recursos?.livros ?? card.recursos?.livros ?? []).join("\n"); } catch { return (card.recursos?.livros ?? []).join("\n"); }
  });
  const [customVideos, setCustomVideos] = useState(() => {
    try { return (JSON.parse(override?.custom_card ?? "{}").recursos?.videos ?? card.recursos?.videos ?? []).join("\n"); } catch { return (card.recursos?.videos ?? []).join("\n"); }
  });
  const [customCurso, setCustomCurso] = useState(() => {
    try { return JSON.parse(override?.custom_card ?? "{}").recursos?.curso ?? card.recursos?.curso ?? ""; } catch { return card.recursos?.curso ?? ""; }
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["coach-study-overrides", studentId] });

  const saveMut = useMutation({
    mutationFn: (payload: Parameters<typeof coachDashboard.saveStudyOverride>[1]) =>
      coachDashboard.saveStudyOverride(studentId, payload),
    onSuccess: () => { invalidate(); setEditMode(null); },
  });

  const deleteMut = useMutation({
    mutationFn: () => coachDashboard.deleteStudyOverride(studentId, card.spot),
    onSuccess: invalidate,
  });

  const validate = () =>
    saveMut.mutate({ card_spot: card.spot, status: "validated" });

  const saveComment = () =>
    saveMut.mutate({ card_spot: card.spot, status: "commented", note: noteText });

  const saveReplace = () =>
    saveMut.mutate({
      card_spot: card.spot,
      status: "replaced",
      custom_card: {
        titulo: customTitle,
        diagnostico: customDiag,
        exercicio: customEx,
        recursos: {
          livros: customLivros.split("\n").map((s) => s.trim()).filter(Boolean),
          videos: customVideos.split("\n").map((s) => s.trim()).filter(Boolean),
          curso:  customCurso.trim() || null,
        },
      },
    });

  const isReplaced = override?.status === "replaced";
  const _custom = () => { try { return JSON.parse(override!.custom_card ?? "{}"); } catch { return {}; } };
  const displayTitle    = isReplaced ? (_custom().titulo      ?? card.titulo)      : card.titulo;
  const displayDiag     = isReplaced ? (_custom().diagnostico ?? card.diagnostico) : card.diagnostico;
  const displayEx       = isReplaced ? (_custom().exercicio   ?? card.exercicio)   : card.exercicio;
  const displayRecursos = isReplaced ? (_custom().recursos    ?? card.recursos)    : card.recursos;

  return (
    <div className={`rounded-xl border p-5 space-y-3 ${PRIORITY_STYLE[card.prioridade] ?? "border-border bg-hud-surface"}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-xl shrink-0">{card.icone}</span>
          <h3 className="font-semibold text-foreground truncate">{displayTitle}</h3>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {override && (
            <span className={`font-mono text-[9px] font-bold uppercase px-2 py-0.5 rounded ring-1 ${
              override.status === "validated" ? "text-primary ring-primary/30 bg-primary/10" :
              override.status === "commented" ? "text-amber-400 ring-amber-400/30 bg-amber-400/10" :
              "text-purple-400 ring-purple-400/30 bg-purple-400/10"
            }`}>
              {override.status === "validated" ? "✓ Validado" : override.status === "commented" ? "💬 Comentado" : "✏️ Substituído"}
            </span>
          )}
          <span className={`font-mono text-[9px] font-bold uppercase px-2 py-0.5 rounded ring-1 ${
            card.prioridade === "alta"
              ? "text-destructive ring-destructive/30 bg-destructive/10"
              : card.prioridade === "media"
              ? "text-amber-400 ring-amber-400/30 bg-amber-400/10"
              : "text-primary ring-primary/30 bg-primary/10"
          }`}>
            {card.prioridade}
          </span>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">{displayDiag}</p>

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
          <p className="text-sm text-foreground">{displayEx}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-1">Métrica</p>
          <p className="text-sm text-foreground">{card.metrica}</p>
        </div>
      </div>

      {/* Recursos */}
      {displayRecursos && (
        <div className="rounded-md border border-border bg-background px-3 py-2.5 space-y-2">
          <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground">Recursos</p>
          {displayRecursos.livros?.length > 0 && (
            <div>
              <p className="font-mono text-[9px] text-muted-foreground mb-1">📚 Livros</p>
              <ul className="space-y-0.5">
                {displayRecursos.livros.map((l: string, i: number) => (
                  <li key={i} className="text-xs text-foreground flex gap-1.5">
                    <span className="text-muted-foreground shrink-0">·</span>{l}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {displayRecursos.videos?.length > 0 && (
            <div>
              <p className="font-mono text-[9px] text-muted-foreground mb-1">🎬 Vídeos</p>
              <ul className="space-y-0.5">
                {displayRecursos.videos.map((v: string, i: number) => (
                  <li key={i} className="text-xs text-foreground flex gap-1.5">
                    <span className="text-muted-foreground shrink-0">·</span>{v}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {displayRecursos.curso && (
            <div>
              <p className="font-mono text-[9px] text-muted-foreground mb-1">🎓 Curso</p>
              <p className="text-xs text-foreground">{displayRecursos.curso}</p>
            </div>
          )}
        </div>
      )}

      {/* Coach comment display */}
      {override?.status === "commented" && override.note && editMode !== "comment" && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/5 px-3 py-2">
          <p className="font-mono text-[9px] font-bold uppercase text-amber-400 mb-1">Nota do Coach</p>
          <p className="text-sm text-foreground">{override.note}</p>
        </div>
      )}

      {/* Edit modes */}
      {editMode === "comment" && (
        <div className="space-y-2 pt-1">
          <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground">Sua nota para o aluno</p>
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={3}
            placeholder="Explique o que o aluno precisa focar neste ponto…"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
          />
          <div className="flex gap-2">
            <button onClick={saveComment} disabled={saveMut.isPending || !noteText.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-mono text-[10px] font-bold uppercase disabled:opacity-50">
              {saveMut.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />} Salvar
            </button>
            <button onClick={() => setEditMode(null)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border font-mono text-[10px] text-muted-foreground hover:text-foreground">
              <X className="size-3" /> Cancelar
            </button>
          </div>
        </div>
      )}

      {editMode === "replace" && (
        <div className="space-y-3 pt-1 border-t border-border">
          <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground">Substituir card</p>

          {/* Conteúdo */}
          {[
            { label: "Título", val: customTitle, set: setCustomTitle, rows: 1 },
            { label: "Diagnóstico", val: customDiag, set: setCustomDiag, rows: 3 },
            { label: "Exercício", val: customEx, set: setCustomEx, rows: 2 },
          ].map(({ label, val, set, rows }) => (
            <div key={label} className="space-y-1">
              <label className="font-mono text-[9px] uppercase text-muted-foreground">{label}</label>
              <textarea value={val} onChange={(e) => set(e.target.value)} rows={rows}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none" />
            </div>
          ))}

          {/* Recursos */}
          <div className="rounded-md border border-border/60 bg-background/50 px-3 py-2.5 space-y-2.5">
            <p className="font-mono text-[9px] font-bold uppercase tracking-widest-2 text-muted-foreground">Recursos</p>
            <div className="space-y-1">
              <label className="font-mono text-[9px] uppercase text-muted-foreground">📚 Livros <span className="normal-case">(um por linha)</span></label>
              <textarea value={customLivros} onChange={(e) => setCustomLivros(e.target.value)} rows={3}
                placeholder={"Applications of No-Limit Hold'em, cap. 7\nThe Mental Game of Poker, cap. 3"}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none" />
            </div>
            <div className="space-y-1">
              <label className="font-mono text-[9px] uppercase text-muted-foreground">🎬 Vídeos <span className="normal-case">(um por linha)</span></label>
              <textarea value={customVideos} onChange={(e) => setCustomVideos(e.target.value)} rows={3}
                placeholder={"Hand history reviews no solver\nSolver study sessions — spots de 3bet"}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none" />
            </div>
            <div className="space-y-1">
              <label className="font-mono text-[9px] uppercase text-muted-foreground">🎓 Curso</label>
              <input value={customCurso} onChange={(e) => setCustomCurso(e.target.value)}
                placeholder="Nome do curso ou treinamento (opcional)"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40" />
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={saveReplace} disabled={saveMut.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-mono text-[10px] font-bold uppercase disabled:opacity-50">
              {saveMut.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />} Salvar
            </button>
            <button onClick={() => setEditMode(null)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border font-mono text-[10px] text-muted-foreground hover:text-foreground">
              <X className="size-3" /> Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Action bar */}
      {editMode === null && (
        <div className="flex items-center gap-2 pt-2 border-t border-border/40">
          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider mr-2">Coach:</p>
          <button onClick={validate} disabled={saveMut.isPending || override?.status === "validated"}
            title="Validar este card"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[10px] font-bold uppercase transition-colors ${
              override?.status === "validated"
                ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                : "border border-border text-muted-foreground hover:text-primary hover:border-primary/40"
            }`}>
            <CheckCircle2 className="size-3" /> Validar
          </button>
          <button onClick={() => { setNoteText(override?.note ?? ""); setEditMode("comment"); }}
            title="Adicionar nota"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[10px] font-bold uppercase transition-colors ${
              override?.status === "commented"
                ? "bg-amber-400/10 text-amber-400 ring-1 ring-amber-400/30"
                : "border border-border text-muted-foreground hover:text-amber-400 hover:border-amber-400/40"
            }`}>
            <MessageSquare className="size-3" /> Comentar
          </button>
          <button onClick={() => setEditMode("replace")}
            title="Substituir card"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[10px] font-bold uppercase transition-colors ${
              override?.status === "replaced"
                ? "bg-purple-400/10 text-purple-400 ring-1 ring-purple-400/30"
                : "border border-border text-muted-foreground hover:text-purple-400 hover:border-purple-400/40"
            }`}>
            <PenLine className="size-3" /> Substituir
          </button>
          {override?.status === "replaced" && (
            <button
              onClick={async () => {
                setSavingTemplate(true);
                try {
                  const custom = (() => { try { return JSON.parse(override!.custom_card ?? "{}"); } catch { return {}; } })();
                  await coachDashboard.createTemplate({
                    name: custom.titulo ?? card.titulo ?? card.spot,
                    target_archetype: undefined,
                    cards_json: [{ ...custom, spot: card.spot }],
                  });
                  qc.invalidateQueries({ queryKey: ["coach-templates"] });
                } finally {
                  setSavingTemplate(false);
                }
              }}
              disabled={savingTemplate}
              title="Salvar este card substituído como template reutilizável"
              className="flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[10px] font-bold uppercase border border-border text-muted-foreground hover:text-blue-400 hover:border-blue-400/40 transition-colors disabled:opacity-40"
            >
              {savingTemplate ? <Loader2 className="size-3 animate-spin" /> : <Save className="size-3" />}
              Template
            </button>
          )}
          {override && (
            <button onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}
              title="Remover anotação"
              className="ml-auto flex items-center gap-1 px-2 py-1 rounded-md font-mono text-[10px] text-muted-foreground hover:text-destructive border border-transparent hover:border-destructive/30 transition-colors">
              {deleteMut.isPending ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Messaging tab — FEAT-10 ──────────────────────────────────────────────────

function MessagingTab({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["coach-messages", studentId],
    queryFn: () => coachDashboard.getMessages(studentId),
    refetchInterval: 15_000,
  });

  const sendMut = useMutation({
    mutationFn: (text: string) => coachDashboard.sendMessage(studentId, text),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["coach-messages", studentId] });
      qc.invalidateQueries({ queryKey: ["coach-inbox"] });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data?.messages]);

  const handleSend = () => {
    const text = body.trim();
    if (!text || sendMut.isPending) return;
    sendMut.mutate(text);
  };

  const messages: CoachMessage[] = data?.messages ?? [];

  return (
    <div className="flex flex-col h-[520px] rounded-xl border border-border bg-hud-surface overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center gap-2">
        <MessageSquare className="size-3.5 text-primary" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          Conversa com o aluno
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {isLoading && (
          <p className="text-xs text-muted-foreground text-center py-8 animate-pulse">Carregando mensagens…</p>
        )}
        {!isLoading && messages.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-8">Nenhuma mensagem ainda. Inicie a conversa.</p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.sender_role === "coach" ? "justify-end" : "justify-start"}`}
          >
            <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
              m.sender_role === "coach"
                ? "bg-primary text-primary-foreground"
                : "bg-hud-surface border border-border text-foreground"
            }`}>
              {m.body}
              <p className={`font-mono text-[9px] mt-1 ${
                m.sender_role === "coach" ? "text-primary-foreground/60" : "text-muted-foreground"
              }`}>
                {new Date(m.created_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                {m.sender_role === "student" && !m.read_at && (
                  <span className="ml-1 text-amber-400">● não lida</span>
                )}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border px-3 py-2.5 flex gap-2">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          placeholder="Mensagem… (Enter para enviar)"
          rows={2}
          className="flex-1 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
        <button
          onClick={handleSend}
          disabled={!body.trim() || sendMut.isPending}
          className="self-end rounded-md bg-primary px-3 py-1.5 text-primary-foreground disabled:opacity-40 transition-opacity"
        >
          {sendMut.isPending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        </button>
      </div>
    </div>
  );
}

// ── Progress tab (BACK-002) ───────────────────────────────────────────────────

const MILESTONE_CONFIG = {
  improvement:   { icon: TrendingUp,   color: "text-primary",     label: "Melhora" },
  regression:    { icon: TrendingDown, color: "text-destructive",  label: "Regressão" },
  high_standard: { icon: Star,         color: "text-amber-400",    label: "Alta Qualidade" },
};

function ActivityTimeline({ events }: { events: ActivityEvent[] }) {
  if (!events.length) return (
    <p className="text-center text-muted-foreground py-8 font-mono text-xs">Nenhum torneio registrado ainda.</p>
  );
  return (
    <div className="space-y-2">
      {events.map((ev, i) => {
        const ms = ev.milestone ? MILESTONE_CONFIG[ev.milestone] : null;
        const MsIcon = ms?.icon;
        return (
          <div key={i} className="flex gap-3 items-start">
            <div className="flex flex-col items-center pt-1">
              <div className={`size-2 rounded-full ${ms ? "bg-primary" : "bg-border"}`} />
              {i < events.length - 1 && <div className="w-px flex-1 bg-border mt-1" style={{ minHeight: 20 }} />}
            </div>
            <div className="flex-1 rounded border border-border bg-card px-3 py-2 mb-1">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">{ev.ts?.slice(0, 10)}</span>
                {ms && MsIcon && (
                  <span className={`flex items-center gap-1 font-mono text-[10px] font-bold ${ms.color}`}>
                    <MsIcon className="size-3" />{ms.label}
                  </span>
                )}
              </div>
              <div className="flex gap-4 mt-1">
                <span className="text-xs text-foreground">{ev.site}</span>
                <span className={`font-mono text-xs font-bold ${SCORE_COLOR(100 - (ev.avg_score ?? 100))}`}>
                  score {ev.avg_score?.toFixed(1)}
                </span>
                <span className="font-mono text-xs text-muted-foreground">
                  {(ev.standard_pct ?? 0).toFixed(0)}% std
                </span>
                <span className="font-mono text-xs text-muted-foreground">{ev.hands_count}m</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MetricsCompare({ label, before, after }: { label: string; before: number | null; after: number | null }) {
  if (before == null && after == null) return null;
  const b = before ?? 0;
  const a = after ?? 0;
  const delta = a - b;
  const better = delta < 0; // lower score = better
  return (
    <div className="rounded border border-border bg-card px-4 py-3 space-y-1">
      <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{label}</p>
      <div className="flex items-end gap-3">
        <span className="font-mono text-sm text-muted-foreground">{b.toFixed(1)}</span>
        <ChevronRight className="size-3 text-border" />
        <span className={`font-mono text-xl font-bold ${better ? "text-primary" : delta > 0 ? "text-destructive" : "text-foreground"}`}>
          {a.toFixed(1)}
        </span>
        {delta !== 0 && (
          <span className={`font-mono text-[11px] ${better ? "text-primary" : "text-destructive"}`}>
            {better ? "" : "+"}{delta.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}

function ProgressTab({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [baselineDate, setBaselineDate] = useState("");
  const [baselineNote, setBaselineNote] = useState("");
  const [editingBaseline, setEditingBaseline] = useState(false);

  const { data: baseline, isLoading: loadingBaseline } = useQuery({
    queryKey: ["coach-baseline", studentId],
    queryFn: () => coachDashboard.getBaseline(studentId),
  });

  const { data: feed, isLoading: loadingFeed } = useQuery({
    queryKey: ["coach-activity-feed", studentId],
    queryFn: () => coachDashboard.activityFeed(studentId, 30),
  });

  const { data: report, isLoading: loadingReport } = useQuery({
    queryKey: ["coach-progress-report", studentId],
    queryFn: () => coachDashboard.progressReport(studentId),
    enabled: !!(baseline && "baseline_date" in baseline),
    retry: false,
  });

  const setBaselineMut = useMutation({
    mutationFn: () => coachDashboard.setBaseline(studentId, baselineDate, baselineNote || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["coach-baseline", studentId] });
      qc.invalidateQueries({ queryKey: ["coach-progress-report", studentId] });
      setEditingBaseline(false);
    },
  });

  const deleteBaselineMut = useMutation({
    mutationFn: () => coachDashboard.deleteBaseline(studentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["coach-baseline", studentId] });
      qc.invalidateQueries({ queryKey: ["coach-progress-report", studentId] });
    },
  });

  const hasBaseline = baseline && "baseline_date" in baseline;

  return (
    <div className="p-6 space-y-6">

      {/* Baseline section */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-mono text-xs font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-2">
            <Flag className="size-3.5" /> Baseline de Coaching
          </h3>
          {hasBaseline && !editingBaseline && (
            <div className="flex gap-2">
              <button
                onClick={() => { setBaselineDate((baseline as any).baseline_date); setBaselineNote((baseline as any).note ?? ""); setEditingBaseline(true); }}
                className="font-mono text-[10px] text-muted-foreground hover:text-foreground border border-border px-2 py-1 rounded"
              >Editar</button>
              <button
                onClick={() => deleteBaselineMut.mutate()}
                className="font-mono text-[10px] text-destructive hover:text-destructive/80 border border-destructive/30 px-2 py-1 rounded"
              >Remover</button>
            </div>
          )}
        </div>

        {loadingBaseline ? (
          <div className="flex items-center gap-2 text-muted-foreground text-xs"><Loader2 className="size-3 animate-spin" />Carregando…</div>
        ) : hasBaseline && !editingBaseline ? (
          <div className="rounded border border-primary/30 bg-primary/5 px-4 py-3 space-y-1">
            <p className="font-mono text-sm font-bold text-primary">{(baseline as any).baseline_date}</p>
            {(baseline as any).note && <p className="text-xs text-muted-foreground">{(baseline as any).note}</p>}
          </div>
        ) : (
          <div className="rounded border border-border bg-card p-4 space-y-3">
            <p className="text-xs text-muted-foreground">
              {hasBaseline ? "Alterar data de início do coaching para comparar métricas antes/depois." : "Defina a data de início do coaching para habilitar comparação de métricas."}
            </p>
            <div className="flex gap-3 items-end">
              <div className="space-y-1 flex-1">
                <label className="font-mono text-[10px] text-muted-foreground uppercase">Data de início</label>
                <input
                  type="date"
                  value={baselineDate}
                  onChange={e => setBaselineDate(e.target.value)}
                  className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="space-y-1 flex-2">
                <label className="font-mono text-[10px] text-muted-foreground uppercase">Nota (opcional)</label>
                <input
                  type="text"
                  value={baselineNote}
                  onChange={e => setBaselineNote(e.target.value)}
                  placeholder="ex: início das sessões semanais"
                  className="w-full rounded border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setBaselineMut.mutate()}
                  disabled={!baselineDate || setBaselineMut.isPending}
                  className="flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 font-mono text-[11px] font-bold text-primary-foreground disabled:opacity-50"
                >
                  {setBaselineMut.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                  Salvar
                </button>
                {editingBaseline && (
                  <button onClick={() => setEditingBaseline(false)} className="px-2 py-1.5 text-muted-foreground hover:text-foreground">
                    <X className="size-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Before/After comparison */}
      {hasBaseline && (
        <section>
          <h3 className="font-mono text-xs font-bold uppercase tracking-widest-2 text-muted-foreground mb-3 flex items-center gap-2">
            <BarChart2 className="size-3.5" /> Antes vs. Depois
          </h3>
          {loadingReport ? (
            <div className="flex items-center gap-2 text-muted-foreground text-xs"><Loader2 className="size-3 animate-spin" />Carregando…</div>
          ) : report ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <MetricsCompare
                  label="Score médio (↓ melhor)"
                  before={report.before.avg_score}
                  after={report.after.avg_score}
                />
                <MetricsCompare
                  label="% Decisões Standard"
                  before={report.before.standard_pct != null ? report.before.standard_pct * 100 : null}
                  after={report.after.standard_pct != null ? report.after.standard_pct * 100 : null}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded border border-border bg-card px-4 py-3">
                  <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground mb-2">Torneios analisados</p>
                  <div className="flex gap-4">
                    <div><p className="font-mono text-[10px] text-muted-foreground">Antes</p><p className="font-bold">{report.before.n}</p></div>
                    <div><p className="font-mono text-[10px] text-muted-foreground">Depois</p><p className="font-bold text-primary">{report.after.n}</p></div>
                  </div>
                </div>
                <div className="rounded border border-border bg-card px-4 py-3">
                  <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground mb-2">Leaks resolvidos</p>
                  <p className={`font-bold text-xl ${report.fixed_leaks.length > 0 ? "text-primary" : "text-muted-foreground"}`}>
                    {report.fixed_leaks.length}
                  </p>
                  {report.fixed_leaks.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {report.fixed_leaks.map(l => (
                        <li key={l.spot} className="font-mono text-[10px] text-primary flex items-center gap-1">
                          <CheckCircle2 className="size-2.5" />{l.spot}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
              {(report.leaks_before.length > 0 || report.leaks_after.length > 0) && (
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { title: "Top leaks antes", items: report.leaks_before },
                    { title: "Top leaks depois", items: report.leaks_after },
                  ].map(({ title, items }) => (
                    <div key={title} className="rounded border border-border bg-card px-4 py-3">
                      <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground mb-2">{title}</p>
                      {items.length === 0 ? (
                        <p className="font-mono text-[10px] text-primary">Nenhum leak!</p>
                      ) : (
                        <ul className="space-y-1">
                          {items.map(l => (
                            <li key={l.spot} className="flex items-center justify-between">
                              <span className="font-mono text-[10px] text-foreground">{l.spot}</span>
                              <span className="font-mono text-[10px] text-muted-foreground">{l.n}×</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Dados insuficientes para comparação.</p>
          )}
        </section>
      )}

      {/* Activity feed */}
      <section>
        <h3 className="font-mono text-xs font-bold uppercase tracking-widest-2 text-muted-foreground mb-3 flex items-center gap-2">
          <Activity className="size-3.5" /> Feed de Atividade
        </h3>
        {loadingFeed ? (
          <div className="flex items-center gap-2 text-muted-foreground text-xs"><Loader2 className="size-3 animate-spin" />Carregando…</div>
        ) : (
          <ActivityTimeline events={feed ?? []} />
        )}
      </section>
    </div>
  );
}

function StudyTab({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [generating, setGenerating] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["coach-student-study", studentId],
    queryFn: () => coachDashboard.studentStudyPlan(studentId, 90),
  });

  const { data: overridesData } = useQuery({
    queryKey: ["coach-study-overrides", studentId],
    queryFn: () => coachDashboard.getStudyOverrides(studentId),
  });

  const overridesMap = Object.fromEntries(
    (overridesData?.overrides ?? []).map((o) => [o.card_spot, o])
  );

  const generateNew = async () => {
    setGenerating(true);
    try {
      await coachDashboard.studentStudyPlan(studentId, 90, true);
      qc.invalidateQueries({ queryKey: ["coach-student-study", studentId] });
    } finally {
      setGenerating(false);
    }
  };

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse py-8">Gerando plano de estudos do aluno…</p>;
  if (isError || !data) return <p className="text-sm text-destructive py-8">Erro ao carregar plano de estudos.</p>;
  if (!data.cards || data.cards.length === 0) {
    return <p className="text-sm text-muted-foreground py-8 text-center">Dados insuficientes para gerar plano.</p>;
  }

  const validated = (overridesData?.overrides ?? []).filter((o) => o.status === "validated").length;
  const commented = (overridesData?.overrides ?? []).filter((o) => o.status === "commented").length;
  const replaced  = (overridesData?.overrides ?? []).filter((o) => o.status === "replaced").length;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-hud-surface px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-0.5">
            Nível: {data.nivel}
          </p>
          <p className="text-sm text-foreground">{data.resumo}</p>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <div className="flex items-center gap-3">
            {validated > 0 && <span className="font-mono text-[10px] text-primary">✓ {validated} validado{validated > 1 ? "s" : ""}</span>}
            {commented > 0 && <span className="font-mono text-[10px] text-amber-400">💬 {commented} comentado{commented > 1 ? "s" : ""}</span>}
            {replaced  > 0 && <span className="font-mono text-[10px] text-purple-400">✏️ {replaced} substituído{replaced  > 1 ? "s" : ""}</span>}
          </div>
          <button
            onClick={generateNew}
            disabled={generating}
            title="Gera um novo plano com IA e substitui o atual do aluno"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-mono text-[10px] font-bold uppercase tracking-widest-2 hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {generating ? <Loader2 className="size-3 animate-spin" /> : <BookOpen className="size-3" />}
            {generating ? "Gerando…" : "Gerar novo plano"}
          </button>
        </div>
      </div>

      {data.cards.map((card, i) => (
        <StudyCardItem
          key={card.spot || i}
          card={card}
          override={overridesMap[card.spot]}
          studentId={studentId}
        />
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function StudentDetail() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);
  const [searchParams] = useSearchParams();
  const initialTab = (searchParams.get("tab") as Tab | null) ?? "overview";
  const [tab, setTab] = useState<Tab>(initialTab);

  const { data: studentsData } = useQuery({
    queryKey: ["coach-students"],
    queryFn: coachDashboard.students,
  });

  const { data: messagesData } = useQuery({
    queryKey: ["coach-messages", studentId],
    queryFn: () => coachDashboard.getMessages(studentId),
    refetchInterval: 30_000,
    enabled: !isNaN(studentId),
  });

  const unreadFromStudent = (messagesData?.messages ?? []).filter(
    (m) => m.sender_role === "student" && !m.read_at
  ).length;

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
      <main className="mx-auto max-w-[1440px] px-4 py-8 space-y-6 md:px-8">
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
        <div className="flex overflow-x-auto overflow-y-hidden border-b border-border gap-0 scrollbar-none">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative flex shrink-0 items-center gap-2 px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors ${
                tab === t.id
                  ? "text-primary border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <t.icon className="size-3.5" />
              {t.label}
              {t.id === "mensagens" && unreadFromStudent > 0 && (
                <span className="absolute -top-0.5 right-1 flex size-4 items-center justify-center rounded-full bg-destructive font-mono text-[9px] font-bold text-destructive-foreground">
                  {unreadFromStudent}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === "overview"    && <OverviewTab     studentId={studentId} />}
        {tab === "tournaments" && <TournamentsTab  studentId={studentId} />}
        {tab === "worst"       && <WorstTab        studentId={studentId} />}
        {tab === "study"       && <StudyTab        studentId={studentId} />}
        {tab === "progress"    && <ProgressTab     studentId={studentId} />}
        {tab === "mensagens"   && <MessagingTab    studentId={studentId} />}
      </main>
    </div>
  );
}
