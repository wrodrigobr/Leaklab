import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
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
  Flame,
  Loader2,
  Brain,
  RefreshCw,
  HelpCircle,
  GraduationCap,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { TournamentAiReport } from "@/components/hud/TournamentAiReport";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { tournaments, Tournament, TournamentDecision, PhaseData, TextureData } from "@/lib/api";

type Severity = "critical" | "major" | "minor" | "ok";
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

function labelToSeverity(label: TournamentDecision["label"]): Severity {
  if (label === "clear_mistake") return "critical";
  if (label === "small_mistake") return "major";
  if (label === "marginal") return "minor";
  return "ok";
}

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

    const leakTag =
      category !== "ok"
        ? worst.draw_profile && worst.draw_profile !== "none"
          ? `${worst.draw_profile.replace(/_/g, " ")} • ${worst.label.replace(/_/g, " ")}`
          : worst.label.replace(/_/g, " ")
        : undefined;

    const actionLine = `${street}: ${worst.action_taken} — ${worst.best_action}`;

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
      evDelta: category !== "ok" ? -Number(worst.score.toFixed(3)) : undefined,
      note: worst.note || undefined,
      stackBb: worst.stack_bb,
      mRatio: worst.m_ratio,
      icm: worst.icm_pressure,
      numPlayers: worst.num_players,
      levelSb: worst.level_sb,
      levelBb: worst.level_bb,
      levelNum: worst.level_num,
      hasAnnotation: decs.some((d) => d.has_annotation),
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

function ScoreLabel({ score }: { score: number }) {
  const { label, cls } = score < 0.08
    ? { label: "Ótimo",    cls: "text-primary" }
    : score < 0.15
    ? { label: "Bom",      cls: "text-primary/70" }
    : score < 0.25
    ? { label: "Moderado", cls: "text-warning" }
    : { label: "Alto",     cls: "text-destructive" };
  return (
    <span className={cn("ml-1.5 font-mono text-[9px] uppercase tracking-wider", cls)}>
      {label}
    </span>
  );
}

// ── Severity meta ────────────────────────────────────────────────────────────

const SEVERITY_META: Record<Severity, { label: string; cls: string; chipCls: string; icon: typeof AlertOctagon }> = {
  critical: { label: "Leak crítico", cls: "text-destructive", chipCls: "bg-destructive/10 text-destructive ring-1 ring-destructive/30", icon: AlertOctagon },
  major:    { label: "Leak relevante", cls: "text-warning",     chipCls: "bg-warning/10 text-warning ring-1 ring-warning/30",         icon: AlertTriangle },
  minor:    { label: "Pequeno ajuste", cls: "text-muted-foreground", chipCls: "bg-muted/40 text-muted-foreground ring-1 ring-border", icon: Flame },
  ok:       { label: "Linha sólida",  cls: "text-primary",     chipCls: "bg-primary/10 text-primary ring-1 ring-primary/30",         icon: CheckCircle2 },
};

const FILTERS: { key: Severity | "all"; label: string }[] = [
  { key: "all",      label: "Todas"     },
  { key: "critical", label: "Críticos"  },
  { key: "major",    label: "Relevantes"},
  { key: "minor",    label: "Pequenos"  },
  { key: "ok",       label: "Sólidas"   },
];

const STREETS: (Street | "all")[] = ["all", "Pré-flop", "Flop", "Turn", "River"];

// ── Page ─────────────────────────────────────────────────────────────────────

const TournamentDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [hands, setHands] = useState<Hand[]>([]);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [street, setStreet] = useState<Street | "all">("all");
  const [analyses, setAnalyses] = useState<Record<number, string>>({});
  const [analysisLoading, setAnalysisLoading] = useState<Record<number, boolean>>({});
  const [phaseAnalysis, setPhaseAnalysis] = useState<PhaseData[]>([]);
  const [textureAnalysis, setTextureAnalysis] = useState<TextureData[]>([]);

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
    tournaments
      .get(id)
      .then((r) => {
        setTournament(r.tournament);
        setHands(groupByHand(r.decisions));
      })
      .catch(() => null)
      .finally(() => setLoading(false));
    tournaments.phaseAnalysis(id).then((r) => setPhaseAnalysis(r.phase_analysis)).catch(() => null);
    tournaments.textureAnalysis(id).then((r) => setTextureAnalysis(r.texture_analysis)).catch(() => null);
  }, [id]);

  const filtered = useMemo(
    () =>
      hands.filter((h) => {
        if (severity !== "all" && h.category !== severity) return false;
        if (street !== "all" && h.street !== street) return false;
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
    [hands, query, severity, street]
  );

  const stats = useMemo(() => ({
    total:    hands.length,
    critical: hands.filter((h) => h.category === "critical").length,
    major:    hands.filter((h) => h.category === "major").length,
    evLost:   hands.reduce((s, h) => s + Math.min(0, h.evDelta ?? 0), 0),
  }), [hands]);

  const tournamentLabel = tournament
    ? `${tournament.site} • ${tournament.hero}`
    : id ?? "—";

  return (
    <HudLayout
      eyebrow={`Torneio · ${id ?? "—"}`}
      title={tournamentLabel}
      description="Todas as mãos do torneio classificadas por severidade de leak. Abra qualquer mão no replayer ou peça análise da IA."
    >
      {loading ? (
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">Carregando torneio…</span>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Link
              to="/tournaments"
              className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
            >
              <ArrowLeft className="size-3.5" aria-hidden />
              Voltar para Torneios
            </Link>
            <div className="flex flex-wrap items-center gap-2">
              {tournament && (
                <TournamentAiReport
                  tournamentName={tournamentLabel}
                  tournamentDbId={tournament.id}
                  existingSummary={tournament.llm_summary}
                />
              )}
              <button
                onClick={() => hands[0] && navigate(`/replayer?t=${id}&h=${hands[0].id}`)}
                disabled={!hands.length}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground shadow-[0_0_20px_-4px_hsl(var(--primary)/0.5)] transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <PlayCircle className="size-3.5" aria-hidden />
                Replay completo
              </button>
            </div>
          </div>

          <section className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-4">
            {[
              { label: "Mãos jogadas",    value: stats.total.toString() },
              { label: "Leaks críticos",  value: stats.critical.toString(), accent: "text-destructive" },
              { label: "Leaks relevantes",value: stats.major.toString(),    accent: "text-warning" },
              { label: "Score médio",     value: tournament?.avg_score != null ? tournament.avg_score.toFixed(4) : "—", accent: "text-destructive" },
            ].map((s, i) => (
              <div key={i} className="bg-hud-surface p-5">
                <div className="mb-2 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">{s.label}</div>
                <div className={cn("font-mono text-2xl font-light tabular-nums", s.accent ?? "text-foreground")}>{s.value}</div>
              </div>
            ))}
          </section>

          {phaseAnalysis.length > 0 && (
            <section>
              <div className="mb-3 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground flex items-center gap-2">
                <span className="inline-block size-1.5 rounded-full bg-primary" />
                Análise por Fase
                <InfoTooltip>
                  Agrupa suas decisões pelas fases do torneio, derivadas do <strong>M-Ratio</strong> (sua pilha ÷ custo de uma órbita completa de blinds+antes).<br /><br />
                  <strong>Folgado (M≥20):</strong> jogo completo, sem urgência.<br />
                  <strong>Médio (M 10–20):</strong> jogo restrito, priorize spots favoráveis.<br />
                  <strong>Pressão (M 6–10):</strong> zona de reshove, fold equity crítica.<br />
                  <strong>Crítico (M&lt;6):</strong> push/fold puro, math decide tudo.
                </InfoTooltip>
              </div>
              <div className="rounded-xl border border-border overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-hud-surface">
                      <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Fase</th>
                      <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">M-Ratio</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Decisões</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        Erros %
                        <InfoTooltip>
                          % de decisões classificadas como erro (pequeno ou claro) nesta fase.<br /><br />
                          <strong>Abaixo de 20%:</strong> consistente.<br />
                          <strong>20–40%:</strong> atenção — fase problemática.<br />
                          <strong>Acima de 40%:</strong> leak grave nesta fase.
                        </InfoTooltip>
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        Score Médio
                        <InfoTooltip>
                          Pontuação média de erro das decisões nesta fase.<br /><br />
                          <strong>Abaixo de 0.08:</strong> ótimo — quase sem erros.<br />
                          <strong>0.08–0.15:</strong> bom — erros leves e raros.<br />
                          <strong>0.15–0.25:</strong> moderado — ajustes necessários.<br />
                          <strong>Acima de 0.25:</strong> alto — leak relevante.<br /><br />
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
                          <ScoreLabel score={row.avg_score} />
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
                Pós-Flop por Textura de Board
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
                      <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Textura</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Decisões</th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        Erros %
                        <InfoTooltip>
                          % de decisões classificadas como erro nesta textura de board.<br />
                          Uma taxa alta indica dificuldade em jogar boards deste tipo.
                        </InfoTooltip>
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        Score Médio
                        <InfoTooltip>
                          Pontuação média de erro nas decisões pós-flop nesta textura.<br /><br />
                          <strong>Abaixo de 0.08:</strong> ótimo.<br />
                          <strong>0.08–0.15:</strong> bom.<br />
                          <strong>0.15–0.25:</strong> moderado.<br />
                          <strong>Acima de 0.25:</strong> alto — priorize este board type no estudo.
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
                          <ScoreLabel score={row.avg_score} />
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
                  placeholder="Buscar por ação, leak…"
                  className="h-10 w-full rounded-md border border-border bg-hud-surface pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
                  aria-label="Buscar mão"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Filter className="size-3.5 text-muted-foreground" aria-hidden />
                {FILTERS.map((f) => (
                  <button
                    key={f.key}
                    onClick={() => setSeverity(f.key)}
                    className={cn(
                      "rounded-sm px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      severity === f.key ? "bg-primary/10 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {f.label}
                  </button>
                ))}
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
                  {s === "all" ? "Todas" : s}
                </button>
              ))}
              <span className="ml-auto font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                {filtered.length} {filtered.length === 1 ? "mão" : "mãos"}
              </span>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-3">
            {filtered.map((h) => {
              const meta = SEVERITY_META[h.category];
              const Icon = meta.icon;
              const positive = (h.evDelta ?? 0) > 0;
              const negative = (h.evDelta ?? 0) < 0;
              return (
                <article
                  key={h.id}
                  className={cn(
                    "group relative grid grid-cols-1 gap-4 overflow-hidden rounded-xl border bg-hud-surface p-4 transition-colors md:grid-cols-[auto,1fr,auto] md:items-center md:p-5",
                    h.category === "critical" ? "border-destructive/40 hover:border-destructive/70" :
                    h.category === "major"    ? "border-warning/30 hover:border-warning/60" :
                    "border-border hover:border-primary/40"
                  )}
                >
                  <span aria-hidden className={cn("absolute inset-y-0 left-0 w-0.5",
                    h.category === "critical" ? "bg-destructive" :
                    h.category === "major"    ? "bg-warning" :
                    h.category === "ok"       ? "bg-primary" : "bg-border"
                  )} />

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
                        <span className={cn("inline-flex items-center gap-1 rounded-sm px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider", meta.chipCls)}>
                          <Icon className="size-3" aria-hidden />
                          {meta.label}
                        </span>
                        {h.hasAnnotation && (
                          <span className="inline-flex items-center gap-1 rounded-sm bg-violet-500/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-400 ring-1 ring-violet-400/30">
                            <GraduationCap className="size-3" aria-hidden />
                            Coach
                          </span>
                        )}
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
                      {h.leakTag && (
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
                              Análise do Coach IA
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <Link
                              to={`/replayer?t=${id}&h=${h.id}`}
                              className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors"
                            >
                              <PlayCircle className="size-3" aria-hidden />
                              Replayer
                            </Link>
                            <button
                              onClick={() => requestAnalysis(h.decisionId, true)}
                              disabled={analysisLoading[h.decisionId]}
                              className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                              title="Gerar nova análise"
                            >
                              <RefreshCw className={cn("size-3", analysisLoading[h.decisionId] && "animate-spin")} />
                              Gerar novamente
                            </button>
                          </div>
                        </div>
                        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                          {analyses[h.decisionId]}
                        </p>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/replayer?t=${id}&h=${h.id}`}
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-secondary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground hover:border-primary/30"
                        >
                          <PlayCircle className="size-3.5" aria-hidden />
                          Abrir no replayer
                        </Link>
                        <button
                          onClick={() => requestAnalysis(h.decisionId)}
                          disabled={analysisLoading[h.decisionId]}
                          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary shadow-[0_0_20px_-6px_hsl(var(--primary)/0.4)] transition-all hover:bg-primary/15 hover:border-primary/50 disabled:opacity-60"
                        >
                          {analysisLoading[h.decisionId] ? (
                            <>
                              <Loader2 className="size-3.5 animate-spin" aria-hidden />
                              Analisando…
                            </>
                          ) : (
                            <>
                              <Sparkles className="size-3.5" aria-hidden />
                              Pedir análise da IA
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
