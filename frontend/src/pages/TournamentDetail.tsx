import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
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
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { TournamentAiReport } from "@/components/hud/TournamentAiReport";
import { cn } from "@/lib/utils";
import { tournaments, Tournament, TournamentDecision } from "@/lib/api";

type Severity = "critical" | "major" | "minor" | "ok";
type Street = "Pré-flop" | "Flop" | "Turn" | "River" | "Outros";

interface Hand {
  id: string;
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
    });
  });
  return hands;
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
  const [loading, setLoading] = useState(true);
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [hands, setHands] = useState<Hand[]>([]);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [street, setStreet] = useState<Street | "all">("all");

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
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground shadow-[0_0_20px_-4px_hsl(var(--primary)/0.5)] transition-colors hover:bg-primary/90"
                title="Replay completo da sessão (em breve)"
                disabled
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
              const positive = h.resultBb > 0;
              const negative = h.resultBb < 0;
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

                  <div className="col-span-full flex flex-col gap-2 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-end">
                    <Link
                      to={`/coach?hand=${h.id}`}
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground shadow-[0_0_20px_-4px_hsl(var(--primary)/0.5)] transition-colors hover:bg-primary/90"
                    >
                      <Sparkles className="size-3.5" aria-hidden />
                      Pedir análise da IA
                    </Link>
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
