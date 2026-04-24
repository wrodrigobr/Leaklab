import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTable, type Seat } from "@/components/hud/PokerTable";
import type { CardData } from "@/components/hud/PlayingCard";
import { cn } from "@/lib/utils";

interface Step {
  street: string;
  community: CardData[];
  pot: number;
  activeSeat: number;
  action: string;
  bet?: number;
  ev?: { correct: boolean; note: string };
}

const HERO_CARDS: [CardData, CardData] = [
  { rank: "A", suit: "s" },
  { rank: "K", suit: "s" },
];

const BASE_SEATS: Seat[] = [
  { id: 1, name: "Hero", stack: 14500, hero: true, cards: HERO_CARDS },
  { id: 2, name: "BlitzKing", stack: 22000 },
  { id: 3, name: "FoldFactory", stack: 8400 },
  { id: 4, name: "RiverGod", stack: 31200 },
  { id: 5, name: "icebucket", stack: 17800 },
  { id: 6, name: "shovemonkey", stack: 9200 },
];

const STEPS: Step[] = [
  { street: "Pré-flop", community: [], pot: 600, activeSeat: 1, action: "Hero raises 800", bet: 800 },
  { street: "Pré-flop", community: [], pot: 1400, activeSeat: 4, action: "RiverGod 3-bets 2.400", bet: 2400, ev: { correct: true, note: "Range tight do 3-bet justifica call." } },
  { street: "Pré-flop", community: [], pot: 4400, activeSeat: 1, action: "Hero calls" },
  { street: "Flop", community: [{ rank: "K", suit: "h" }, { rank: "9", suit: "s" }, { rank: "2", suit: "d" }], pot: 4400, activeSeat: 4, action: "RiverGod c-bets 2.000", bet: 2000 },
  { street: "Flop", community: [{ rank: "K", suit: "h" }, { rank: "9", suit: "s" }, { rank: "2", suit: "d" }], pot: 6400, activeSeat: 1, action: "Hero raises para 6.000", bet: 6000, ev: { correct: false, note: "Call seria mais lucrativo: villain pagaria turn com pares fracos." } },
  { street: "Turn", community: [{ rank: "K", suit: "h" }, { rank: "9", suit: "s" }, { rank: "2", suit: "d" }, { rank: "Q", suit: "c" }], pot: 18400, activeSeat: 4, action: "RiverGod calls" },
  { street: "River", community: [{ rank: "K", suit: "h" }, { rank: "9", suit: "s" }, { rank: "2", suit: "d" }, { rank: "Q", suit: "c" }, { rank: "5", suit: "h" }], pot: 18400, activeSeat: 1, action: "Hero shoves all-in", bet: 6700, ev: { correct: true, note: "Top pair, top kicker — value bet sólido." } },
];

const Replayer = () => {
  const [stepIdx, setStepIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const step = STEPS[stepIdx];

  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => {
      setStepIdx((i) => (i < STEPS.length - 1 ? i + 1 : (setPlaying(false), i)));
    }, 1600 / speed);
    return () => clearTimeout(t);
  }, [playing, stepIdx, speed]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
      if (e.code === "ArrowRight") setStepIdx((i) => Math.min(STEPS.length - 1, i + 1));
      if (e.code === "ArrowLeft") setStepIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Build seats with active highlight + bet
  const seats = BASE_SEATS.map((s) => ({
    ...s,
    active: s.id === step.activeSeat,
    bet: s.id === step.activeSeat ? step.bet : undefined,
  }));

  return (
    <HudLayout
      eyebrow="Hand Replayer"
      title="Reproduza e analise mãos críticas"
      description="Use os controles ou as setas do teclado (← →) e barra de espaço para navegar passo a passo. A IA destaca decisões -EV em tempo real."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 space-y-4">
          <PokerTable seats={seats} community={step.community} pot={step.pot} street={step.street} />

          {/* Controls */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-border bg-hud-surface p-3">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setStepIdx(0)}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Reiniciar"
              >
                <Rewind className="size-4" aria-hidden />
              </button>
              <button
                onClick={() => setStepIdx((i) => Math.max(0, i - 1))}
                disabled={stepIdx === 0}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Passo anterior"
              >
                <ChevronLeft className="size-5" aria-hidden />
              </button>
              <button
                onClick={() => setPlaying((p) => !p)}
                className="inline-flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={playing ? "Pausar" : "Reproduzir"}
              >
                {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
              </button>
              <button
                onClick={() => setStepIdx((i) => Math.min(STEPS.length - 1, i + 1))}
                disabled={stepIdx === STEPS.length - 1}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Próximo passo"
              >
                <ChevronRight className="size-5" aria-hidden />
              </button>
              <button
                onClick={() => setStepIdx(STEPS.length - 1)}
                className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Final da mão"
              >
                <FastForward className="size-4" aria-hidden />
              </button>
            </div>

            {/* Progress */}
            <div className="flex flex-1 items-center gap-3 sm:max-w-md">
              <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                {stepIdx + 1}/{STEPS.length}
              </span>
              <div className="flex-1 flex gap-0.5">
                {STEPS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => setStepIdx(i)}
                    className={cn(
                      "h-1.5 flex-1 rounded-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      i <= stepIdx ? "bg-primary" : "bg-border",
                      s.ev && !s.ev.correct && i <= stepIdx && "bg-destructive"
                    )}
                    aria-label={`Ir para passo ${i + 1}`}
                  />
                ))}
              </div>
            </div>

            <div className="flex items-center gap-1">
              {[0.5, 1, 2].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={cn(
                    "rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    speed === s ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Side panel: action log + AI feedback */}
        <aside className="lg:col-span-4 space-y-6">
          <section className="rounded-xl border border-border bg-hud-surface overflow-hidden">
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">Action Log</h2>
              <span className="font-mono text-[10px] text-muted-foreground">{step.street}</span>
            </header>
            <ol className="max-h-80 overflow-y-auto divide-y divide-border">
              {STEPS.slice(0, stepIdx + 1).map((s, i) => (
                <li key={i} className={cn("px-4 py-2.5 text-xs", i === stepIdx && "bg-primary/5")}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-foreground">{s.action}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">{s.street}</span>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {step.ev && (
            <section
              className={cn(
                "rounded-xl border p-4 space-y-2",
                step.ev.correct ? "border-primary/30 bg-primary/5" : "border-destructive/40 bg-destructive/5"
              )}
            >
              <div className="flex items-center gap-2">
                <AlertOctagon className={cn("size-4", step.ev.correct ? "text-primary" : "text-destructive")} aria-hidden />
                <span className={cn("font-mono text-[10px] font-bold uppercase tracking-widest-2", step.ev.correct ? "text-primary" : "text-destructive")}>
                  IA Coach • {step.ev.correct ? "+EV" : "-EV"}
                </span>
              </div>
              <p className="text-sm text-foreground leading-relaxed">{step.ev.note}</p>
            </section>
          )}

          <div className="rounded-xl border border-border bg-hud-surface p-4">
            <div className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground mb-3">Atalhos</div>
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              <li className="flex items-center justify-between"><span>Play / Pause</span><kbd className="font-mono text-[10px] rounded bg-secondary px-1.5 py-0.5">Space</kbd></li>
              <li className="flex items-center justify-between"><span>Próximo passo</span><kbd className="font-mono text-[10px] rounded bg-secondary px-1.5 py-0.5">→</kbd></li>
              <li className="flex items-center justify-between"><span>Passo anterior</span><kbd className="font-mono text-[10px] rounded bg-secondary px-1.5 py-0.5">←</kbd></li>
            </ul>
          </div>
        </aside>
      </div>
    </HudLayout>
  );
};

export default Replayer;
