import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTable, type Seat } from "@/components/hud/PokerTable";
import type { CardData } from "@/components/hud/PlayingCard";
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

function buildSeats(step: ReplayStep, hero: string, heroCards: CardData[]): Seat[] {
  return Object.entries(step.seats).map(([seatNum, sd]) => {
    const seatId = parseInt(seatNum);
    const isHero = sd.player === hero;
    const bet    = step.bets?.[seatNum] || undefined;
    const folded = step.folded?.includes(sd.player) ?? false;
    return {
      id:      seatId,
      name:    `${sd.player} (${sd.pos})`,
      stack:   sd.stack,
      hero:    isHero,
      cards:   isHero ? heroCards : undefined,
      bet:     bet || undefined,
      active:  step.seat === seatId,
      folded,
    };
  });
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

  useEffect(() => {
    if (!tournamentId || !handId) return;
    setLoading(true);
    setError("");
    setStepIdx(0);
    setPlaying(false);
    tournamentsApi
      .replay(tournamentId, handId)
      .then(setReplayData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar replay"))
      .finally(() => setLoading(false));
  }, [tournamentId, handId]);

  const steps = replayData?.timeline ?? [];
  const step  = steps[stepIdx] as ReplayStep | undefined;

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
  const seats     = buildSeats(step, replayData.hero, heroCards as [CardData, CardData]);

  const isError   = step.is_error ?? false;
  const isCorrect = step.is_hero && !isError && step.type === "action";

  return (
    <HudLayout
      eyebrow={`Replayer · Mão ${replayData.hand_id}`}
      title={`${replayData.hero} — ${replayData.seats ? Object.values(replayData.seats).length : "?"} jogadores`}
      description={`Use ← → ou barra de espaço para navegar. Hero: ${replayData.hero} · BB: ${replayData.bb}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
        >
          <ArrowLeft className="size-3.5" /> Voltar
        </button>
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
                  s.is_error && "border-l-2 border-destructive"
                )}>
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn("text-foreground", s.is_hero && "font-semibold text-primary")}>{s.desc}</span>
                    <span className="font-mono text-[10px] text-muted-foreground shrink-0">{s.street?.toUpperCase()}</span>
                  </div>
                  {s.is_error && s.best_action && (
                    <div className="mt-0.5 font-mono text-[10px] text-destructive">
                      correto: {s.best_action} · score {s.error_score?.toFixed(3)}
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
