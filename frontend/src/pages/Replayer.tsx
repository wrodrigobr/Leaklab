import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft, SkipBack, SkipForward } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTable, type Seat } from "@/components/hud/PokerTable";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { cn } from "@/lib/utils";
import { tournaments as tournamentsApi, ReplayData, ReplayStep } from "@/lib/api";

// ── Card parsing ──────────────────────────────────────────────────────────────

function parseCard(raw: string): CardData {
  return {
    rank: raw.slice(0, -1) as CardData["rank"],
    suit: raw.slice(-1).toLowerCase() as CardData["suit"],
  };
}

function parseCards(arr: string[]): CardData[] {
  return arr.map(parseCard);
}

// ── Map backend step to PokerTable seats ──────────────────────────────────────

function buildSeats(step: ReplayStep, hero: string, heroCards: CardData[], aliases: Record<string, string>): Seat[] {
  const isShowdown = step.type === "showdown";

  return Object.entries(step.seats).map(([seatNum, sd]) => {
    const seatId      = parseInt(seatNum);
    const isHero      = sd.player === hero;
    const bet         = step.bets?.[seatNum] || undefined;
    const folded      = step.folded?.includes(sd.player) ?? false;
    const displayName = aliases[sd.player] ?? sd.player;

    // No showdown, mostra cartas reveladas dos villains vindas do backend
    let cards: CardData[] | undefined = isHero ? heroCards : undefined;
    if (isShowdown && !isHero) {
      const raw = step.revealed_cards?.[seatNum];
      if (raw?.length) cards = parseCards(raw);
    }

    return {
      id:       seatId,
      name:     `${displayName} (${sd.pos})`,
      stack:    sd.stack,
      hero:     isHero,
      cards,
      revealed: isShowdown && !isHero && Array.isArray(cards) && cards.length > 0,
      bet:      bet || undefined,
      active:   step.seat === seatId,
      folded,
    };
  });
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function anonymizeDesc(desc: string, aliases: Record<string, string>): string {
  let result = desc;
  for (const [name, alias] of Object.entries(aliases)) {
    if (name !== alias) result = result.replace(new RegExp(escapeRegex(name), "g"), alias);
  }
  return result;
}

// ── Replayer ──────────────────────────────────────────────────────────────────

const Replayer = () => {
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const tournamentId = params.get("t") ?? "";
  const handId       = params.get("h") ?? "";

  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [stepIdx, setStepIdx]       = useState(0);
  const [playing, setPlaying]       = useState(false);
  const [speed, setSpeed]           = useState(1);
  const [handList, setHandList]     = useState<string[]>([]);

  useEffect(() => {
    if (!tournamentId || !handId) return;
    setLoading(true);
    setError("");
    setStepIdx(0);
    setPlaying(false);
    Promise.all([
      tournamentsApi.replay(tournamentId, handId),
      tournamentsApi.get(tournamentId).catch(() => null),
    ])
      .then(([replay, tournamentData]) => {
        setReplayData(replay);
        if (tournamentData) {
          const seen = new Set<string>();
          const ids: string[] = [];
          tournamentData.decisions.forEach((d) => {
            if (d.hand_id && !seen.has(d.hand_id)) { seen.add(d.hand_id); ids.push(d.hand_id); }
          });
          setHandList(ids);
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar replay"))
      .finally(() => setLoading(false));
  }, [tournamentId, handId]);

  const steps = replayData?.timeline ?? [];
  const step  = steps[stepIdx] as ReplayStep | undefined;

  // Hand navigation
  const handIdx  = handList.indexOf(handId);
  const prevHand = handIdx > 0 ? handList[handIdx - 1] : null;
  const nextHand = handIdx >= 0 && handIdx < handList.length - 1 ? handList[handIdx + 1] : null;

  // Alias map: hero keeps real name, others become "Villain N"
  const playerAliases = useMemo<Record<string, string>>(() => {
    if (!replayData) return {};
    const aliases: Record<string, string> = {};
    let n = 1;
    Object.entries(replayData.seats)
      .sort(([a], [b]) => parseInt(a) - parseInt(b))
      .forEach(([, seat]) => {
        if (!(seat.player in aliases)) {
          aliases[seat.player] = seat.player === replayData.hero ? replayData.hero : `Villain ${n++}`;
        }
      });
    return aliases;
  }, [replayData]);

  // Auto-play
  useEffect(() => {
    if (!playing || !step) return;
    const t = setTimeout(() => {
      setStepIdx((i) => {
        if (i < steps.length - 1) return i + 1;
        setPlaying(false);
        return i;
      });
    }, 1600 / speed);
    return () => clearTimeout(t);
  }, [playing, stepIdx, speed, steps.length, step]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.code === "ArrowRight") setStepIdx((i) => Math.min(steps.length - 1, i + 1));
      if (e.code === "ArrowLeft")  setStepIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [steps.length]);

  // ── No params: show placeholder ──────────────────────────────────────────────
  if (!tournamentId || !handId) {
    return (
      <HudLayout eyebrow="Hand Replayer" title="Selecione uma mão" description="Abra uma mão a partir da página de detalhe do torneio.">
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
          <p className="text-sm">Nenhuma mão selecionada. Volte para o torneio e clique em "Abrir no replayer".</p>
          <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> Voltar
          </button>
        </div>
      </HudLayout>
    );
  }

  if (loading) {
    return (
      <HudLayout eyebrow="Hand Replayer" title="Carregando…" description="">
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">Carregando mão…</span>
        </div>
      </HudLayout>
    );
  }

  if (error) {
    return (
      <HudLayout eyebrow="Hand Replayer" title="Erro" description="">
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> Voltar
          </button>
        </div>
      </HudLayout>
    );
  }

  if (!replayData || !step) {
    return (
      <HudLayout eyebrow="Hand Replayer" title="—" description="">
        <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">Sem dados.</div>
      </HudLayout>
    );
  }

  const heroCards = parseCards(replayData.hero_cards);
  const community = parseCards(step.board ?? []);
  const seats     = buildSeats(step, replayData.hero, heroCards as [CardData, CardData], playerAliases);

  const isError   = step.is_error ?? false;
  const isCorrect = step.is_hero && !isError && step.type === "action";

  return (
    <HudLayout
      eyebrow={`Replayer · Mão ${replayData.hand_id}`}
      title={`${replayData.hero} — ${replayData.seats ? Object.values(replayData.seats).length : "?"} jogadores`}
      description={`Use ← → ou barra de espaço para navegar. Hero: ${replayData.hero} · BB: ${replayData.bb}`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
        >
          <ArrowLeft className="size-3.5" /> Voltar
        </button>

        {handList.length > 1 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => prevHand && navigate(`/replayer?t=${tournamentId}&h=${prevHand}`)}
              disabled={!prevHand}
              className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30"
            >
              <SkipBack className="size-3.5" /> Mão anterior
            </button>
            <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
              {handIdx + 1}/{handList.length}
            </span>
            <button
              onClick={() => nextHand && navigate(`/replayer?t=${tournamentId}&h=${nextHand}`)}
              disabled={!nextHand}
              className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30"
            >
              Próxima mão <SkipForward className="size-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 space-y-4">
          <PokerTable seats={seats} community={community} pot={step.pot} street={step.street} />

          {/* Controls */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-border bg-hud-surface p-3">
            <div className="flex items-center gap-1">
              <button onClick={() => setStepIdx(0)}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Reiniciar"><Rewind className="size-4" /></button>
              <button onClick={() => setStepIdx((i) => Math.max(0, i - 1))} disabled={stepIdx === 0}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Anterior"><ChevronLeft className="size-5" /></button>
              <button onClick={() => setPlaying((p) => !p)}
                className="inline-flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={playing ? "Pausar" : "Reproduzir"}>
                {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
              </button>
              <button onClick={() => setStepIdx((i) => Math.min(steps.length - 1, i + 1))} disabled={stepIdx === steps.length - 1}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Próximo"><ChevronRight className="size-5" /></button>
              <button onClick={() => setStepIdx(steps.length - 1)}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Final"><FastForward className="size-4" /></button>
            </div>

            <div className="flex flex-1 items-center gap-3 sm:max-w-md">
              <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                {stepIdx + 1}/{steps.length}
              </span>
              <div className="flex-1 flex gap-0.5">
                {steps.map((s, i) => (
                  <button key={i} onClick={() => setStepIdx(i)}
                    className={cn(
                      "h-1.5 flex-1 rounded-sm transition-colors focus-visible:outline-none",
                      i <= stepIdx
                        ? (s.is_error ? "bg-destructive" : "bg-primary")
                        : "bg-border"
                    )}
                    aria-label={`Passo ${i + 1}`}
                  />
                ))}
              </div>
            </div>

            <div className="flex items-center gap-1">
              {[0.5, 1, 2].map((s) => (
                <button key={s} onClick={() => setSpeed(s)}
                  className={cn(
                    "rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                    speed === s ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:text-foreground"
                  )}>{s}x</button>
              ))}
            </div>
          </div>
        </div>

        {/* Side panel */}
        <aside className="lg:col-span-4 space-y-4">
          {/* Action log */}
          <section className="rounded-xl border border-border bg-hud-surface overflow-hidden">
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">Action Log</h2>
              <span className="font-mono text-[10px] text-muted-foreground">{step.street?.toUpperCase()}</span>
            </header>
            <ol className="max-h-72 overflow-y-auto divide-y divide-border">
              {steps.slice(0, stepIdx + 1).map((s, i) => (
                <li key={i} className={cn(
                  "px-4 py-2.5 text-xs transition-colors",
                  i === stepIdx && "bg-primary/5",
                  s.is_error && "border-l-2 border-destructive",
                  s.type === "showdown" && "border-l-2 border-primary/50"
                )}>
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn("text-foreground", s.is_hero && "font-semibold text-primary")}>{anonymizeDesc(s.desc, playerAliases)}</span>
                    <span className="font-mono text-[10px] text-muted-foreground shrink-0">{s.street?.toUpperCase()}</span>
                  </div>
                  {s.is_error && s.best_action && (
                    <div className="mt-0.5 font-mono text-[10px] text-destructive">
                      correto: {s.best_action} · score {s.error_score?.toFixed(3)}
                    </div>
                  )}
                  {s.type === "showdown" && s.summary?.seats && s.summary.seats.length > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {s.summary.seats.map((sd, j) => (
                        <div key={j} className="font-mono text-[10px] text-muted-foreground">
                          {playerAliases[sd.player] ?? sd.player}
                          {sd.cards?.length > 0 && ` [${sd.cards.join(" ")}]`}
                          {" · "}
                          <span className={sd.outcome === "won" ? "text-primary" : ""}>
                            {sd.outcome === "won" ? `ganhou ${sd.won}` : sd.hand_desc}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </section>

          {/* EV feedback */}
          {step.type === "action" && step.is_hero && (
            <section className={cn(
              "rounded-xl border p-4 space-y-2",
              isError
                ? "border-destructive/40 bg-destructive/5"
                : isCorrect
                ? "border-primary/30 bg-primary/5"
                : "border-border bg-hud-surface"
            )}>
              <div className="flex items-center gap-2">
                {isError
                  ? <AlertOctagon className="size-4 text-destructive" />
                  : <CheckCircle2 className="size-4 text-primary" />}
                <span className={cn("font-mono text-[10px] font-bold uppercase tracking-widest-2",
                  isError ? "text-destructive" : "text-primary")}>
                  IA Coach · {isError ? (step.error_label?.replace(/_/g," ") ?? "-EV") : "+EV"}
                </span>
              </div>
              {isError ? (
                <div className="space-y-1.5 text-xs text-foreground">
                  <p>Ação: <strong>{step.action}</strong> — Recomendado: <strong>{step.best_action}</strong></p>
                  {step.hand_equity != null && (
                    <p className="text-muted-foreground">
                      Equity: {(step.hand_equity * 100).toFixed(1)}%
                      {step.pot_odds_equity != null && ` (necessário: ${(step.pot_odds_equity * 100).toFixed(1)}%)`}
                    </p>
                  )}
                  {step.m_ratio != null && (
                    <p className="text-muted-foreground">M ratio: {step.m_ratio} · ICM: {step.icm_pressure}</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-foreground">Linha sólida para o spot.</p>
              )}
            </section>
          )}

          {/* Showdown result panel */}
          {step.type === "showdown" && step.summary && (
            <section className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
              <div className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">Resultado da mão</div>
              {step.summary.total_pot != null && (
                <div className="text-xs text-muted-foreground">
                  Pot total: <span className="font-mono font-medium text-foreground">{(step.summary.total_pot / (replayData?.bb ?? 100)).toFixed(1)} BB</span>
                </div>
              )}
              <ul className="space-y-2">
                {step.summary.seats.map((sd, i) => (
                  <li key={i} className="text-xs space-y-0.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className={cn("font-semibold", sd.outcome === "won" ? "text-primary" : "text-muted-foreground")}>
                        {playerAliases[sd.player] ?? sd.player}
                      </span>
                      {sd.outcome === "won" && (
                        <span className="font-mono text-[10px] text-primary">+{sd.won}</span>
                      )}
                    </div>
                    {sd.cards?.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {parseCards(sd.cards).map((c, j) => (
                          <PlayingCard key={j} card={c} size="sm" />
                        ))}
                        {sd.hand_desc && sd.hand_desc !== "mucked" && sd.hand_desc !== "collected" && (
                          <span className="self-center font-mono text-[10px] text-muted-foreground ml-1">{sd.hand_desc}</span>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Pot & stack info */}
          <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-2">
            <div className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-2">Situação</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div><span className="text-muted-foreground">Pot</span><div className="font-mono font-medium">{step.pot_bb?.toFixed(1)} BB</div></div>
              <div><span className="text-muted-foreground">Street</span><div className="font-mono font-medium">{step.street?.toUpperCase()}</div></div>
            </div>
            <div className="mt-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-1">Atalhos</div>
            <ul className="space-y-1 text-xs text-muted-foreground">
              <li className="flex items-center justify-between"><span>Play/Pause</span><kbd className="font-mono text-[10px] rounded bg-secondary px-1.5 py-0.5">Space</kbd></li>
              <li className="flex items-center justify-between"><span>Próximo</span><kbd className="font-mono text-[10px] rounded bg-secondary px-1.5 py-0.5">→</kbd></li>
              <li className="flex items-center justify-between"><span>Anterior</span><kbd className="font-mono text-[10px] rounded bg-secondary px-1.5 py-0.5">←</kbd></li>
            </ul>
          </div>
        </aside>
      </div>
    </HudLayout>
  );
};

export default Replayer;
