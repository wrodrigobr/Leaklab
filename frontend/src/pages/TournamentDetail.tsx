import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  Search,
  PlayCircle,
  Sparkles,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Filter,
  Loader2,
  Brain,
  RefreshCw,
  HelpCircle,
  GraduationCap,
  FileDown,
  Target,
  Sigma,
  Clock,
  Cpu,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { TournamentAiReport } from "@/components/hud/TournamentAiReport";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AiText } from "@/components/ui/AiText";
import { cn, formatAction } from "@/lib/utils";
import { tournaments, metrics, coachDashboard, Tournament, TournamentDecision, PhaseData, TextureData, SessionReviewResponse } from "@/lib/api";
import { verdictLevelOrError, type VerdictLevel } from "@/lib/cardLogic";

// FEAT-20: o veredito visível colapsa em 3 níveis dirigidos pela SEVERIDADE (label),
// a MESMA régua do card do replayer e do badge de aderência. A frequência (gto_label)
// deixa de ser veredito e vira só um marcador de FONTE (Solver vs Engine).
type Severity = VerdictLevel;   // "correct" | "acceptable" | "error"
type Street = "Pré-flop" | "Flop" | "Turn" | "River" | "Outros";

interface Hand {
  id: string;
  decisionId: number;
  number: number;
  position: string;
  holeCards: [CardData, CardData] | null;
  board: CardData[];
  street: Street;
  action: string;
  category: Severity;
  leakTag?: string;
  evDelta?: number;
  note?: string;
  stackBb?: number | null;
  mRatio?: number | null;
  icm?: string | null;
  numPlayers?: number | null;
  levelSb?: number | null;
  levelBb?: number | null;
  levelNum?: number | null;
  hasAnnotation?: boolean;
  gtoLabel?: string | null;
  gtoAction?: string | null;
  hasPostflop?: boolean;
  divergent?: boolean;            // coach mode: alguma decisão não-aderente (coach × sistema)
  adherence?: string | null;      // categoria representativa (diverge_*/match_*/comentario)
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseCards(raw: string): CardData[] {
  if (!raw) return [];
  // Space-separated: "Ah Kd" → ["Ah", "Kd"]
  const parts = raw.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return parts.map((c) => ({
      rank: c.slice(0, -1) as CardData["rank"],
      suit: c.slice(-1).toLowerCase() as CardData["suit"],
    }));
  }
  // Concatenated (PokerStars parser stores without spaces): "AhKd" → ["Ah", "Kd"]
  const cards: CardData[] = [];
  const s = parts[0] ?? "";
  for (let i = 0; i + 1 < s.length; i += 2) {
    cards.push({
      rank: s[i] as CardData["rank"],
      suit: s[i + 1].toLowerCase() as CardData["suit"],
    });
  }
  return cards;
}

function parseBoard(json: string): CardData[] {
  try {
    const arr: string[] = JSON.parse(json);
    return arr.map((c) => ({
      rank: c.slice(0, -1) as CardData["rank"],
      suit: c.slice(-1).toLowerCase() as CardData["suit"],
    }));
  } catch {
    return [];
  }
}

// standard→correct · marginal→acceptable · small/clear_mistake→error (severidade EV).
const labelToSeverity = (label: TournamentDecision["label"]): Severity => verdictLevelOrError(label);

function streetDisplay(street: string): Street {
  if (street === "preflop") return "Pré-flop";
  if (street === "flop") return "Flop";
  if (street === "turn") return "Turn";
  if (street === "river") return "River";
  return "Outros";
}

function groupByHand(decisions: TournamentDecision[]): Hand[] {
  const map = new Map<string, TournamentDecision[]>();
  decisions.forEach((d) => {
    const key = d.hand_id || `hand-${d.id}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(d);
  });

  let num = 0;
  const hands: Hand[] = [];
  map.forEach((decs, handId) => {
    num++;
    const worst = [...decs].sort((a, b) => b.score - a.score)[0];
    const cards = parseCards(worst.hero_cards);
    const holeCards: [CardData, CardData] | null =
      cards.length >= 2 ? [cards[0], cards[1]] : null;
    const board = parseBoard(worst.board);

    const category = labelToSeverity(worst.label);
    const street = streetDisplay(worst.street);

    // só o draw_profile como tag textual — o veredito (Aceitável/Erro) vem do chip de
    // severidade, sem vazar o vocabulário de 4 níveis ("small mistake") no texto.
    const leakTag =
      category !== "correct" && worst.draw_profile && worst.draw_profile !== "none"
        ? worst.draw_profile.replace(/_/g, " ")
        : undefined;

    const played = formatAction(worst.action_taken);
    const ideal  = formatAction(worst.best_action);
    const actionLine = played.toLowerCase() === ideal.toLowerCase()
      ? `${street}: ${played}`
      : `${street}: ${played}, ${ideal}`;

    hands.push({
      id: handId,
      decisionId: worst.id,
      number: num,
      position: worst.position || "—",
      holeCards,
      board,
      street,
      action: actionLine,
      category,
      leakTag,
      evDelta: category !== "correct" ? -Number(worst.score.toFixed(3)) : undefined,
      note: worst.note || undefined,
      stackBb: worst.stack_bb,
      mRatio: worst.m_ratio,
      icm: worst.icm_pressure,
      numPlayers: worst.num_players,
      levelSb: worst.level_sb,
      levelBb: worst.level_bb,
      levelNum: worst.level_num,
      hasAnnotation: decs.some((d) => d.has_annotation),
      gtoLabel: worst.gto_label ?? null,
      gtoAction: worst.gto_action ?? null,
      hasPostflop: decs.some((d) => d.street === "flop" || d.street === "turn" || d.street === "river"),
      divergent: decs.some((d) => d.adherence === "diverge_rigido" || d.adherence === "diverge_perdido"),
      adherence: (decs.find((d) => d.adherence === "diverge_perdido")
        ?? decs.find((d) => d.adherence === "diverge_rigido")
        ?? decs.find((d) => d.adherence === "match_erro")
        ?? decs.find((d) => d.adherence != null))?.adherence ?? null,
    });
  });
  return hands;
}

// ── Tooltip helper ───────────────────────────────────────────────────────────

function InfoTooltip({ children }: { children: React.ReactNode }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <HelpCircle className="inline-block size-3 cursor-help text-muted-foreground/60 hover:text-muted-foreground transition-colors ml-1 align-middle" aria-hidden />
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[260px] text-xs leading-relaxed font-normal normal-case tracking-normal">
          {children}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ScoreLabel and SEVERITY_META/FILTERS moved inside TournamentDetail component for i18n access

const STREETS: (Street | "all")[] = ["all", "Pré-flop", "Flop", "Turn", "River"];

// ── Page ─────────────────────────────────────────────────────────────────────

const TournamentDetail = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const coachStudentId = searchParams.get("student");   // coach revisando o aluno (modo coach)
  const replayHref = (handId: string) =>
    `/replayer?t=${id}&h=${handId}${coachStudentId ? `&student=${coachStudentId}` : ""}`;
  const navigate = useNavigate();
  const { t } = useTranslation("tournaments");
  const { t: tc } = useTranslation("common");

  // 3 níveis (FEAT-20). Paleta idêntica ao card do replayer: error=red, acceptable=sky,
  // correct=emerald. Texto vem do namespace common (`verdict.*`).
  const SEVERITY_META: Record<Severity, { label: string; cls: string; chipCls: string; icon: typeof AlertOctagon }> = {
    error:      { label: tc("verdict.error"),      cls: "text-red-400",     chipCls: "bg-red-500/10 text-red-400 ring-1 ring-red-500/30",            icon: AlertOctagon },
    acceptable: { label: tc("verdict.acceptable"), cls: "text-sky-400",     chipCls: "bg-sky-500/10 text-sky-400 ring-1 ring-sky-500/30",            icon: AlertTriangle },
    correct:    { label: tc("verdict.correct"),    cls: "text-emerald-400", chipCls: "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30", icon: CheckCircle2 },
  };


  const scoreLabel = (score: number) => score < 0.08
    ? { label: t("detail.score.great"), cls: "text-primary" }
    : score < 0.15
    ? { label: t("detail.score.good"),  cls: "text-primary/70" }
    : score < 0.25
    ? { label: t("detail.score.moderate"), cls: "text-warning" }
    : { label: t("detail.score.high"), cls: "text-destructive" };
  const [loading, setLoading] = useState(true);
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [hands, setHands] = useState<Hand[]>([]);
  const [query, setQuery] = useState("");
  const [street, setStreet] = useState<Street | "all">("all");
  const [resultFilter, setResultFilter] = useState<"all" | "correct" | "attention" | "error" | "pending">("all");
  const [onlyDiverg, setOnlyDiverg] = useState(false);   // coach mode: filtrar mãos não-aderentes
  const [analyses, setAnalyses] = useState<Record<number, string>>({});
  const [analysisLoading, setAnalysisLoading] = useState<Record<number, boolean>>({});
  const [phaseAnalysis, setPhaseAnalysis] = useState<PhaseData[]>([]);
  const [textureAnalysis, setTextureAnalysis] = useState<TextureData[]>([]);
  const [narrative, setNarrative] = useState<{ narrative: string; quality_level: "solid" | "regular" | "poor" } | null>(null);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfFallback, setPdfFallback] = useState(false);
  const [sessionReview, setSessionReview] = useState<SessionReviewResponse | null>(null);

  const requestAnalysis = async (decisionId: number, force = false) => {
    if (analysisLoading[decisionId]) return;
    setAnalysisLoading((p) => ({ ...p, [decisionId]: true }));
    try {
      const res = await tournaments.analyzeDecision(decisionId);
      setAnalyses((p) => ({ ...p, [decisionId]: res.analysis }));
    } catch (err: unknown) {
      setAnalyses((p) => ({
        ...p,
        [decisionId]: err instanceof Error ? err.message : "Erro ao gerar análise",
      }));
    } finally {
      setAnalysisLoading((p) => ({ ...p, [decisionId]: false }));
    }
    void force;
  };

  useEffect(() => {
    if (!id) return;
    // Modo coach (?student=): busca o torneio DO ALUNO (com aderência por decisão); senão o próprio.
    const fetchTournament = coachStudentId
      ? coachDashboard.studentTournament(Number(coachStudentId), id)
      : tournaments.get(id);
    fetchTournament
      .then((r) => {
        setTournament(r.tournament);
        setHands(groupByHand(r.decisions));
      })
      .catch(() => null)
      .finally(() => setLoading(false));
    if (!coachStudentId) {   // análises são user-scoped; pulam no modo coach
      tournaments.phaseAnalysis(id).then((r) => setPhaseAnalysis(r.phase_analysis)).catch(() => null);
      tournaments.textureAnalysis(id).then((r) => setTextureAnalysis(r.texture_analysis)).catch(() => null);
      tournaments.narrative(id).then(setNarrative).catch(() => null);
    }
  }, [id, coachStudentId]);

  useEffect(() => {
    if (!tournament?.id) return;
    metrics.sessionReview(tournament.id).then(setSessionReview).catch(() => null);
  }, [tournament?.id]);

  const filtered = useMemo(
    () =>
      hands.filter((h) => {
        if (onlyDiverg && !h.divergent) return false;   // coach mode: só não-aderentes
        if (street !== "all" && h.street !== street) return false;
        if (resultFilter !== "all") {
          // FEAT-20: filtro dirigido pela SEVERIDADE (mesmo veredito do card), não pela
          // frequência GTO. "Pendente" segue sendo um estado de FONTE (postflop sem solver).
          const isCorrect   = h.category === "correct";
          const isAttention = h.category === "acceptable";
          const isError     = h.category === "error";
          const isPending   = h.hasPostflop && !h.gtoLabel;
          if (resultFilter === "correct"   && !isCorrect)   return false;
          if (resultFilter === "attention" && !isAttention) return false;
          if (resultFilter === "error"     && !isError)     return false;
          if (resultFilter === "pending"   && !isPending)   return false;
        }
        if (query) {
          const q = query.toLowerCase();
          return (
            h.id.toLowerCase().includes(q) ||
            h.action.toLowerCase().includes(q) ||
            (h.leakTag?.toLowerCase().includes(q) ?? false)
          );
        }
        return true;
      }),
    [hands, query, resultFilter, street, onlyDiverg]
  );
  const divergCount = useMemo(() => hands.filter((h) => h.divergent).length, [hands]);

  const stats = useMemo(() => ({
    total:    hands.length,
    critical: hands.filter((h) => h.category === "error").length,       // erros (severidade)
    major:    hands.filter((h) => h.category === "acceptable").length,  // aceitáveis (atenção)
    evLost:   hands.reduce((s, h) => s + Math.min(0, h.evDelta ?? 0), 0),
  }), [hands]);

  const tournamentLabel = tournament
    ? `${tournament.site} • ${tournament.hero}`
    : id ?? "—";

  return (
    <HudLayout
      eyebrow={t("detail.eyebrow", { id: id ?? "—" })}
      title={tournamentLabel}
      description={t("detail.description")}
    >
      {loading ? (
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">{t("loading")}</span>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Link
              to="/tournaments"
              className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
            >
              <ArrowLeft className="size-3.5" aria-hidden />
              {t("detail.backToList")}
            </Link>
            <div className="flex flex-wrap items-center gap-2">
              {tournament && (
                <TournamentAiReport
                  tournamentName={tournamentLabel}
                  tournamentDbId={tournament.id}
                  existingSummary={tournament.llm_summary}
                />
              )}
              <div className="flex flex-col items-end gap-1">
                <button
                  onClick={async () => {
                    if (!id || pdfDownloading) return;
                    setPdfDownloading(true);
                    setPdfFallback(false);
                    try {
                      const { format } = await tournaments.downloadReport(id);
                      if (format === "html") setPdfFallback(true);
                    } catch { /* silently ignore */ }
                    finally { setPdfDownloading(false); }
                  }}
                  disabled={pdfDownloading || !tournament}
                  className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-hud-surface px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Baixar relatório PDF"
                >
                  {pdfDownloading
                    ? <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    : <FileDown className="size-3.5" aria-hidden />}
                  PDF
                </button>
                {pdfFallback && (
                  <span className="font-mono text-[9px] text-yellow-400 text-right leading-tight">
                    WeasyPrint indisponível: baixado como HTML
                  </span>
                )}
              </div>
              <button
                onClick={() => hands[0] && navigate(replayHref(hands[0].id))}
                disabled={!hands.length}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground shadow-[0_0_20px_-4px_hsl(var(--primary)/0.5)] transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <PlayCircle className="size-3.5" aria-hidden />
                {t("detail.replay")}
              </button>
            </div>
          </div>

          <section className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-4">
            {[
              { label: t("detail.stats.handsPlayed"),   value: stats.total.toString() },
              { label: t("detail.stats.criticalLeaks"), value: stats.critical.toString(), accent: "text-destructive" },
              { label: t("detail.stats.relevantLeaks"), value: stats.major.toString(),    accent: "text-warning" },
              { label: t("detail.stats.avgScore"),      value: tournament?.avg_score != null ? tournament.avg_score.toFixed(4) : "—", accent: "text-destructive" },
            ].map((s, i) => (
              <div key={i} className="bg-hud-surface p-5">
                <div className="mb-2 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{s.label}</div>
                <div className={cn("font-mono text-2xl font-light tabular-nums", s.accent ?? "text-foreground")}>{s.value}</div>
              </div>
            ))}
          </section>

          {narrative && (
            <section className="rounded-xl border border-border bg-hud-surface px-5 py-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  {t("detail.narrative.title")}
                </span>
                <span className={cn(
                  "rounded-sm px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase ring-1",
                  narrative.quality_level === "solid"
                    ? "text-primary bg-primary/10 ring-primary/20"
                    : narrative.quality_level === "regular"
                    ? "text-yellow-400 bg-yellow-400/10 ring-yellow-400/20"
                    : "text-destructive bg-destructive/10 ring-destructive/20"
                )}>
                  {t(`detail.narrative.${narrative.quality_level}`)}
                </span>
              </div>
              <AiText>{narrative.narrative}</AiText>
            </section>
          )}

          {sessionReview?.goal && (
            <section className="rounded-xl border border-primary/30 bg-primary/5 px-5 py-4 space-y-3">
              <div className="flex items-center gap-2">
                <Target className="size-3.5 text-primary" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
                  Review da Sessão
                </span>
              </div>

              <div className="flex flex-wrap gap-3 text-xs">
                {sessionReview.goal.goal_leak_spot && (
                  <div className="flex items-center gap-1.5 rounded-md bg-background/60 px-2.5 py-1 ring-1 ring-border">
                    <span className="text-muted-foreground">Foco:</span>
                    <span className="font-medium text-foreground">{sessionReview.goal.goal_leak_spot}</span>
                  </div>
                )}
                {sessionReview.goal.target_standard_pct != null && (
                  <div className="flex items-center gap-1.5 rounded-md bg-background/60 px-2.5 py-1 ring-1 ring-border">
                    <span className="text-muted-foreground">Meta:</span>
                    <span className="font-medium text-foreground">{sessionReview.goal.target_standard_pct}% {tc("verdict.correct")}</span>
                    {tournament?.standard_pct != null && (
                      <span className={cn(
                        "font-mono text-[10px] font-bold",
                        tournament.standard_pct >= sessionReview.goal.target_standard_pct
                          ? "text-primary"
                          : "text-destructive"
                      )}>
                        → {tournament.standard_pct.toFixed(1)}%
                        {tournament.standard_pct >= sessionReview.goal.target_standard_pct ? " ✓" : " ✗"}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {sessionReview.review && (
                <div className="flex gap-2.5">
                  <Brain className="size-3.5 text-primary shrink-0 mt-0.5" />
                  <p className="text-sm leading-relaxed text-foreground">{sessionReview.review}</p>
                </div>
              )}

              {sessionReview.requires_pro && !sessionReview.review && (
                <div className="flex items-center gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2.5">
                  <Sparkles className="size-3.5 text-amber-400 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-foreground">Review por IA disponível no plano Pro</p>
                    <p className="font-mono text-[10px] text-muted-foreground mt-0.5">
                      Faça upgrade para receber análise comparativa da meta vs resultado.
                    </p>
                  </div>
                </div>
              )}

              {sessionReview.goal.notes && (
                <p className="text-xs text-muted-foreground italic border-t border-border/50 pt-2">
                  &ldquo;{sessionReview.goal.notes}&rdquo;
                </p>
              )}
            </section>
          )}

          {phaseAnalysis.length > 0 && (
            <section>
              <div className="mb-3 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-2">
                <span className="inline-block size-1.5 rounded-full bg-primary" />
                {t("detail.phase.title")}
                <InfoTooltip>
                  Agrupa suas decisões pelas fases do torneio, derivadas do <strong>M-Ratio</strong> (sua pilha ÷ custo de uma órbita completa de blinds+antes).<br /><br />
                  <strong>Deep Stack (M≥20):</strong> jogo completo, sem urgência.<br />
                  <strong>Mid Stack (M 10–20):</strong> jogo restrito, priorize spots favoráveis.<br />
                  <strong>Short Stack (M 6–10):</strong> zona de reshove, fold equity crítica.<br />
                  <strong>Push/Fold (M&lt;6):</strong> push/fold puro, math decide tudo.
                </InfoTooltip>
              </div>
              <div className="rounded-xl border border-border overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-hud-surface">
                      <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{t("detail.phase.phase")}</th>
                      <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{t("detail.phase.mRatio")}</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{t("detail.phase.decisions")}</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t("detail.phase.errorPct")}
                        <InfoTooltip>
                          % de decisões classificadas como erro (pequeno ou claro) nesta fase.<br /><br />
                          <strong>Abaixo de 20%:</strong> consistente.<br />
                          <strong>20–40%:</strong> atenção, fase problemática.<br />
                          <strong>Acima de 40%:</strong> leak grave nesta fase.
                        </InfoTooltip>
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t("detail.phase.avgScore")}
                        <InfoTooltip>
                          Pontuação média de erro das decisões nesta fase.<br /><br />
                          <strong>Abaixo de 0.08:</strong> ótimo, quase sem erros.<br />
                          <strong>0.08–0.15:</strong> bom, erros leves e raros.<br />
                          <strong>0.15–0.25:</strong> moderado, ajustes necessários.<br />
                          <strong>Acima de 0.25:</strong> alto, leak relevante.<br /><br />
                          Quanto menor, melhor.
                        </InfoTooltip>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {phaseAnalysis.map((row) => (
                      <tr key={row.phase} className="border-b border-border/50 last:border-0 hover:bg-secondary/30 transition-colors">
                        <td className="px-4 py-2.5 font-mono font-semibold text-foreground">{row.phase}</td>
                        <td className="px-4 py-2.5 font-mono text-[10px] text-muted-foreground">{row.range}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums text-foreground">{row.n}</td>
                        <td className={cn("px-4 py-2.5 text-right font-mono tabular-nums", row.mistake_rate > 40 ? "text-destructive" : row.mistake_rate > 25 ? "text-warning" : "text-primary")}>
                          {row.mistake_rate.toFixed(1)}%
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                          <span className={cn(row.avg_score > 0.25 ? "text-destructive" : row.avg_score > 0.15 ? "text-warning" : "text-muted-foreground")}>
                            {row.avg_score.toFixed(3)}
                          </span>
                          {(() => { const sl = scoreLabel(row.avg_score); return <span className={cn("ml-1.5 font-mono text-[9px] uppercase tracking-wider", sl.cls)}>{sl.label}</span>; })()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {textureAnalysis.length > 0 && (
            <section>
              <div className="mb-3 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-2">
                <span className="inline-block size-1.5 rounded-full bg-primary" />
                {t("detail.texture.title")}
                <InfoTooltip>
                  Classifica os boards pós-flop pelo nível de conectividade e risco de draws, revelando em que tipo de textura você comete mais erros.<br /><br />
                  <strong>Seco:</strong> poucas draws possíveis (ex: A♠ 7♦ 2♣).<br />
                  <strong>Coordenado:</strong> potencial de sequência (ex: K♠ Q♦ J♣).<br />
                  <strong>Molhado:</strong> flush draw + straight draw (ex: J♥ T♠ 9♥).<br />
                  <strong>Monocromático:</strong> três cartas do mesmo naipe.<br />
                  <strong>Pareado:</strong> par no board (ex: A♠ A♦ 7♣).
                </InfoTooltip>
              </div>
              <div className="rounded-xl border border-border overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-hud-surface">
                      <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{t("detail.texture.texture")}</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{t("detail.texture.decisions")}</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t("detail.texture.errorPct")}
                        <InfoTooltip>
                          % de decisões classificadas como erro nesta textura de board.<br />
                          Uma taxa alta indica dificuldade em jogar boards deste tipo.
                        </InfoTooltip>
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t("detail.texture.avgScore")}
                        <InfoTooltip>
                          Pontuação média de erro nas decisões pós-flop nesta textura.<br /><br />
                          <strong>Abaixo de 0.08:</strong> ótimo.<br />
                          <strong>0.08–0.15:</strong> bom.<br />
                          <strong>0.15–0.25:</strong> moderado.<br />
                          <strong>Acima de 0.25:</strong> alto, priorize este board type no estudo.
                        </InfoTooltip>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {textureAnalysis.map((row) => (
                      <tr key={row.texture} className="border-b border-border/50 last:border-0 hover:bg-secondary/30 transition-colors">
                        <td className="px-4 py-2.5 font-mono font-semibold text-foreground">{row.label}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums text-foreground">{row.n}</td>
                        <td className={cn("px-4 py-2.5 text-right font-mono tabular-nums", row.mistake_rate > 40 ? "text-destructive" : row.mistake_rate > 25 ? "text-warning" : "text-primary")}>
                          {row.mistake_rate.toFixed(1)}%
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                          <span className={cn(row.avg_score > 0.25 ? "text-destructive" : row.avg_score > 0.15 ? "text-warning" : "text-muted-foreground")}>
                            {row.avg_score.toFixed(3)}
                          </span>
                          {(() => { const sl = scoreLabel(row.avg_score); return <span className={cn("ml-1.5 font-mono text-[9px] uppercase tracking-wider", sl.cls)}>{sl.label}</span>; })()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="space-y-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative max-w-sm flex-1">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t("detail.searchPlaceholder")}
                  className="h-10 w-full rounded-md border border-border bg-hud-surface pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
                  aria-label={t("detail.searchAriaLabel")}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Street</span>
              {STREETS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStreet(s)}
                  className={cn(
                    "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    street === s ? "bg-primary/10 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  {s === "all" ? t("detail.streets.all") : s}
                </button>
              ))}
            </div>

            {/* Resultado unificado — GTO quando disponível, engine como fallback */}
            {(() => {
              const pendingGto = hands.filter((h) => h.hasPostflop && !h.gtoLabel).length;
              type RKey = typeof resultFilter;
              const RESULT_FILTERS: { key: RKey; label: string; cls: string; title?: string }[] = [
                { key: "all",       label: "Todas",       cls: "text-muted-foreground" },
                { key: "correct",   label: "✓ Correto",   cls: "text-emerald-400" },
                { key: "attention", label: "⚠ Atenção",   cls: "text-amber-400" },
                { key: "error",     label: "✗ Erro",      cls: "text-red-400" },
                ...(pendingGto > 0 ? [{
                  key: "pending" as RKey,
                  label: `⏱ Pendente (${pendingGto})`,
                  cls: "text-muted-foreground/50",
                  title: "Mãos postflop aguardando solver, análise atual pelo engine",
                }] : []),
              ];
              return (
                <div className="flex flex-wrap items-center gap-2">
                  <Filter className="size-3 text-muted-foreground shrink-0" aria-hidden />
                  {RESULT_FILTERS.map((f) => (
                    <button
                      key={f.key}
                      onClick={() => setResultFilter(f.key)}
                      title={f.title}
                      className={cn(
                        "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        resultFilter === f.key
                          ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                          : cn("hover:bg-secondary hover:text-foreground", f.cls)
                      )}
                    >
                      {f.label}
                    </button>
                  ))}
                  <span className="ml-auto font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                    {t(filtered.length === 1 ? "detail.handCount" : "detail.handCount_plural", { count: filtered.length })}
                  </span>
                </div>
              );
            })()}
          </section>

          {coachStudentId && (
            <div className="mb-3 flex items-center justify-between gap-3 rounded-xl border border-amber-400/30 bg-amber-500/5 px-4 py-3">
              <div className="flex items-center gap-2">
                <GraduationCap className="size-4 text-amber-300" aria-hidden />
                <span className="text-sm text-foreground">Revisão do coach, <b className="text-amber-300">{divergCount}</b> mão(s) não-aderente(s) (coach × sistema)</span>
              </div>
              <button
                onClick={() => setOnlyDiverg((v) => !v)}
                className={cn("inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider ring-1 transition-colors",
                  onlyDiverg ? "bg-amber-400/20 text-amber-200 ring-amber-400/50" : "bg-background/40 text-muted-foreground ring-border hover:text-foreground")}
              >
                <Filter className="size-3" aria-hidden /> {onlyDiverg ? "mostrando só divergências" : "só não-aderentes"}
              </button>
            </div>
          )}
          <section className="grid grid-cols-1 gap-3">
            {filtered.map((h) => {
              const meta = SEVERITY_META[h.category];
              const Icon = meta.icon;
              const positive = (h.evDelta ?? 0) > 0;
              const negative = (h.evDelta ?? 0) < 0;
              return (
                <article
                  key={h.id}
                  className="group relative grid grid-cols-1 gap-4 overflow-hidden rounded-xl border border-border bg-hud-surface p-4 transition-colors hover:border-primary/40 md:grid-cols-[auto,1fr,auto] md:items-center md:p-5"
                >

                  <div className="flex items-center gap-4">
                    <div className="flex flex-col items-center gap-1.5">
                      <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">#{h.number}</div>
                      {h.holeCards ? (
                        <div className="flex gap-1">
                          <PlayingCard card={h.holeCards[0]} size="sm" />
                          <PlayingCard card={h.holeCards[1]} size="sm" />
                        </div>
                      ) : (
                        <div className="flex gap-1">
                          <div className="size-7 rounded bg-border/50 flex items-center justify-center font-mono text-[10px] text-muted-foreground">?</div>
                          <div className="size-7 rounded bg-border/50 flex items-center justify-center font-mono text-[10px] text-muted-foreground">?</div>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Veredito (severidade, 3 níveis) — sempre, inclusive Correto (badge ✓ verde) */}
                        <span className={cn("inline-flex items-center gap-1 rounded-sm px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider", meta.chipCls)}>
                          <Icon className="size-3" aria-hidden />
                          {meta.label}
                        </span>
                        {coachStudentId && h.adherence && (() => {
                          const A: Record<string, [string, string]> = {
                            diverge_perdido: ["⚠ NÃO ADERENTE · coach aponta", "bg-red-500/10 text-red-400 ring-red-400/40"],
                            diverge_rigido:  ["⚠ NÃO ADERENTE · nós flagamos", "bg-amber-500/10 text-amber-300 ring-amber-400/40"],
                            match_erro:      ["coach confirma o erro", "bg-sky-500/10 text-sky-300 ring-sky-400/30"],
                            match_ok:        ["aderente", "bg-primary/10 text-primary ring-primary/30"],
                            comentario:      ["coach comentou", "bg-muted/30 text-muted-foreground ring-border"],
                          };
                          const [lbl, cls] = A[h.adherence] ?? ["", ""];
                          if (!lbl) return null;
                          return <span className={cn("inline-flex items-center rounded-sm px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1", cls)}>{lbl}</span>;
                        })()}
                        {h.hasAnnotation && (
                          <span className="inline-flex items-center gap-1 rounded-sm bg-violet-500/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-400 ring-1 ring-violet-400/30">
                            <GraduationCap className="size-3" aria-hidden />
                            {tc("status.coach")}
                          </span>
                        )}
                        {/* Marcador de FONTE (contexto, não veredito): Solver vs Engine. */}
                        {h.gtoLabel ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-sm bg-muted/30 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 ring-1 ring-border/40"
                            title={h.gtoAction ? `GTO Solver: ${formatAction(h.gtoAction)}` : t("detail.source.solver")}
                          >
                            <Sigma className="size-3" aria-hidden />
                            {t("detail.source.solver")}
                          </span>
                        ) : h.hasPostflop ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-sm bg-muted/30 px-2 py-0.5 font-mono text-[10px] text-muted-foreground/50 ring-1 ring-border/30"
                            title={t("detail.source.engineTip")}
                          >
                            <Clock className="size-3" aria-hidden />
                            {t("detail.source.engine")}
                          </span>
                        ) : null}
                        {h.position && h.position !== "—" && (
                          <span className="rounded-sm bg-secondary px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-foreground">
                            {h.position}
                          </span>
                        )}
                        {h.icm && h.icm !== "low" && (
                          <span className="font-mono text-[10px] text-warning">ICM {h.icm}</span>
                        )}
                      </div>
                      {(h.levelNum || h.levelSb) && (
                        <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                          {h.levelNum ? `Lvl ${h.levelNum} · ` : ""}
                          {h.levelSb && h.levelBb ? `${h.levelSb}/${h.levelBb}` : ""}
                          {h.numPlayers ? ` · vs ${h.numPlayers - 1}` : ""}
                        </div>
                      )}
                      {h.leakTag && !h.gtoLabel && (
                        <div className={cn("font-mono text-[11px] font-semibold uppercase tracking-wider", meta.cls)}>
                          ▸ {h.leakTag}
                        </div>
                      )}
                      <div className="text-sm text-foreground">{h.action}</div>
                      {h.note && <p className="max-w-xl text-xs text-muted-foreground">{h.note}</p>}
                    </div>
                  </div>

                  <div className="flex items-center justify-start gap-4 md:justify-end">
                    {h.board.length > 0 && (
                      <div className="hidden items-center gap-1 lg:flex">
                        {h.board.map((c, i) => <PlayingCard key={i} card={c} size="sm" />)}
                      </div>
                    )}
                    <div className="flex flex-col items-end gap-0.5">
                      {h.evDelta != null && (
                        <div className={cn("inline-flex items-center gap-1 font-mono text-base font-medium tabular-nums", positive ? "text-primary" : negative ? "text-destructive" : "text-muted-foreground")}>
                          {negative ? <TrendingDown className="size-3.5" aria-hidden /> : <TrendingUp className="size-3.5" aria-hidden />}
                          score: {Math.abs(h.evDelta).toFixed(3)}
                        </div>
                      )}
                      {h.stackBb != null && (
                        <div className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                          Stack {h.stackBb.toFixed(0)} bb
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="col-span-full border-t border-border pt-3 space-y-3">
                    {analyses[h.decisionId] ? (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Brain className="size-3.5 text-primary" aria-hidden />
                            <span className="font-mono text-[10px] uppercase tracking-widest-2 text-primary">
                              {t("detail.analysis.title")}
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <Link
                              to={replayHref(h.id)}
                              className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors"
                            >
                              <PlayCircle className="size-3" aria-hidden />
                              Replayer
                            </Link>
                            <button
                              onClick={() => requestAnalysis(h.decisionId, true)}
                              disabled={analysisLoading[h.decisionId]}
                              className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <RefreshCw className={cn("size-3", analysisLoading[h.decisionId] && "animate-spin")} />
                              {t("detail.analysis.regenerate")}
                            </button>
                          </div>
                        </div>
                        <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                          <AiText>{analyses[h.decisionId]}</AiText>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={replayHref(h.id)}
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-secondary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground hover:border-primary/30"
                        >
                          <PlayCircle className="size-3.5" aria-hidden />
                          {t("detail.analysis.openReplayer")}
                        </Link>
                        <button
                          onClick={() => requestAnalysis(h.decisionId)}
                          disabled={analysisLoading[h.decisionId]}
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary shadow-[0_0_20px_-6px_hsl(var(--primary)/0.4)] transition-all hover:bg-primary/15 hover:border-primary/50 disabled:opacity-60"
                        >
                          {analysisLoading[h.decisionId] ? (
                            <>
                              <Loader2 className="size-3.5 animate-spin" aria-hidden />
                              {t("detail.analysis.analyzing")}
                            </>
                          ) : (
                            <>
                              <Sparkles className="size-3.5" aria-hidden />
                              {t("detail.analysis.requestAnalysis")}
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}

            {filtered.length === 0 && (
              <div className="rounded-xl border border-dashed border-border bg-hud-surface p-12 text-center">
                <p className="text-sm text-muted-foreground">
                  {hands.length === 0
                    ? "Nenhuma mão encontrada para este torneio."
                    : "Nenhuma mão encontrada para os filtros atuais."}
                </p>
              </div>
            )}
          </section>
        </>
      )}
    </HudLayout>
  );
};

export default TournamentDetail;
