import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft, SkipBack, SkipForward, GraduationCap, PenLine, X, Check, Trash2, LayoutGrid } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTable, type Seat } from "@/components/hud/PokerTable";
import { RangePanel } from "@/components/replayer/RangePanel";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { cn } from "@/lib/utils";
import { tournaments as tournamentsApi, coachDashboard, ReplayData, ReplayStep, TournamentDecision, CoachAnnotation, CoachOverrideLabel } from "@/lib/api";

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
  const winners = new Set(step.summary?.winners?.map((w) => w.player) ?? []);

  return Object.entries(step.seats).map(([seatNum, sd]) => {
    const seatId      = parseInt(seatNum);
    const isHero      = sd.player === hero;
    const bet         = step.bets?.[seatNum] || undefined;
    const folded      = step.folded?.includes(sd.player) ?? false;
    const displayName = aliases[sd.player] ?? sd.player;

    // Villain cards: revealed as soon as backend marks them (shows mid-hand or showdown)
    let cards: CardData[] | undefined = isHero ? heroCards : undefined;
    if (!isHero) {
      const raw = step.revealed_cards?.[seatNum];
      if (raw?.length) cards = parseCards(raw);
    }

    return {
      id:       seatId,
      name:     `${displayName} (${sd.pos})`,
      stack:    sd.stack,
      hero:     isHero,
      cards,
      revealed: !isHero && Array.isArray(cards) && cards.length > 0,
      winner:   winners.has(sd.player),
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
  const studentId    = params.get("student") ? Number(params.get("student")) : null;

  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [stepIdx, setStepIdx]       = useState(0);
  const [playing, setPlaying]       = useState(false);
  const [speed, setSpeed]           = useState(1);
  const [handList, setHandList]     = useState<string[]>([]);
  const [betUnit, setBetUnit]       = useState<"chips" | "bb">("chips");
  const [decisions, setDecisions]   = useState<TournamentDecision[]>([]);
  const [showRange, setShowRange]           = useState(false);
  const [annotating, setAnnotating]         = useState(false);
  const [annComment, setAnnComment]         = useState("");
  const [annMode, setAnnMode]               = useState<"complement" | "replace">("complement");
  const [annAction, setAnnAction]           = useState("");
  const [annOverride, setAnnOverride]       = useState<CoachOverrideLabel>(null);

  useEffect(() => {
    if (!tournamentId || !handId) return;
    setLoading(true);
    setError("");
    setStepIdx(0);
    setPlaying(false);

    const replayFn = studentId
      ? coachDashboard.studentReplay(studentId, tournamentId, handId)
      : tournamentsApi.replay(tournamentId, handId);

    const tournamentFn = studentId
      ? coachDashboard.studentTournament(studentId, tournamentId)
          .then((r) => ({ decisions: r.decisions }))
          .catch(() => null)
      : tournamentsApi.get(tournamentId).catch(() => null);

    Promise.all([replayFn, tournamentFn])
      .then(([replay, tournamentData]) => {
        setReplayData(replay);
        if (tournamentData) {
          const seen = new Set<string>();
          const ids: string[] = [];
          tournamentData.decisions.forEach((d) => {
            if (d.hand_id && !seen.has(d.hand_id)) { seen.add(d.hand_id); ids.push(d.hand_id); }
          });
          setHandList(ids);
          setDecisions(tournamentData.decisions);
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar replay"))
      .finally(() => setLoading(false));
  }, [tournamentId, handId, studentId]);

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

  // Reset annotation form when step changes
  useEffect(() => { setAnnotating(false); }, [stepIdx]);

  // Coach annotation for current step — must be before early returns (Rules of Hooks)
  const coachAnnotation = useMemo(() => {
    const annotations = replayData?.coach_annotations;
    if (!annotations || !step?.is_error) return null;
    return Object.values(annotations).find(
      (a) => a.street === step.street && a.action_taken === step.action
    ) ?? null;
  }, [replayData?.coach_annotations, step?.is_error, step?.street, step?.action]);

  // decision_id for annotation save/delete (coaches only)
  const currentDecisionId = useMemo(() => {
    if (!studentId || !step?.is_error || !step.is_hero) return null;
    if (coachAnnotation) return coachAnnotation.decision_id;
    return decisions.find(
      (d) => d.hand_id === handId && d.street === step.street && d.action_taken === step.action
    )?.id ?? null;
  }, [studentId, step?.is_error, step?.is_hero, step?.street, step?.action, coachAnnotation, decisions, handId]);

  const saveAnn = useMutation({
    mutationFn: () => coachDashboard.upsertAnnotation(studentId!, {
      decision_id: currentDecisionId!,
      comment: annComment,
      mode: annMode,
      coach_action: annAction || undefined,
      coach_override_label: annOverride,
    }),
    onSuccess: (saved: CoachAnnotation) => {
      setReplayData((prev) => prev ? {
        ...prev,
        coach_annotations: { ...prev.coach_annotations, [String(saved.decision_id)]: saved },
      } : prev);
      setAnnotating(false);
    },
  });

  const deleteAnn = useMutation({
    mutationFn: () => coachDashboard.deleteAnnotation(studentId!, currentDecisionId!),
    onSuccess: () => {
      setReplayData((prev) => {
        if (!prev || !currentDecisionId) return prev;
        const anns = { ...prev.coach_annotations };
        delete anns[String(currentDecisionId)];
        return { ...prev, coach_annotations: anns };
      });
      setAnnotating(false);
    },
  });

  const openAnnotationForm = () => {
    setAnnComment(coachAnnotation?.comment ?? "");
    setAnnMode(coachAnnotation?.mode ?? "complement");
    setAnnAction(coachAnnotation?.coach_action ?? "");
    setAnnOverride(coachAnnotation?.coach_override_label ?? null);
    setAnnotating(true);
  };

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
              onClick={() => prevHand && navigate(`/replayer?t=${tournamentId}&h=${prevHand}${studentId ? `&student=${studentId}` : ""}`)}
              disabled={!prevHand}
              className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary disabled:opacity-30"
            >
              <SkipBack className="size-3.5" /> Mão anterior
            </button>
            <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
              {handIdx + 1}/{handList.length}
            </span>
            <button
              onClick={() => nextHand && navigate(`/replayer?t=${tournamentId}&h=${nextHand}${studentId ? `&student=${studentId}` : ""}`)}
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
          <PokerTable seats={seats} community={community} pot={step.pot} street={step.street} bb={replayData.bb} betUnit={betUnit} />

          {/* Controls */}
          <div className="sticky bottom-14 z-30 md:static border-t border-border md:border md:rounded-xl bg-background/95 backdrop-blur-md md:bg-hud-surface p-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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

            <div className="flex items-center gap-3">
              {/* Speed */}
              <div className="flex items-center gap-1">
                {[0.5, 1, 2].map((s) => (
                  <button key={s} onClick={() => setSpeed(s)}
                    className={cn(
                      "rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                      speed === s ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:text-foreground"
                    )}>{s}x</button>
                ))}
              </div>
              {/* Bet unit toggle */}
              <div className="flex items-center rounded-sm ring-1 ring-border overflow-hidden">
                {(["chips", "bb"] as const).map((u) => (
                  <button key={u} onClick={() => setBetUnit(u)}
                    className={cn(
                      "px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                      betUnit === u ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                    )}>{u}</button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Side panel */}
        <aside className="lg:col-span-4 space-y-4">
          {/* Action log */}
          <section className="rounded-xl border border-border bg-hud-surface overflow-hidden">
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest-2 text-foreground">Action Log</h2>
              <div className="flex items-center gap-3">
                {step.street === 'preflop' && (
                  <button
                    onClick={() => setShowRange(s => !s)}
                    className={cn(
                      'flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 transition-colors',
                      showRange ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <LayoutGrid className="size-3" /> Range
                  </button>
                )}
                <span className="font-mono text-[10px] text-muted-foreground">{step.street?.toUpperCase()}</span>
              </div>
            </header>
            <ol className="max-h-72 overflow-y-auto divide-y divide-border">
              {steps.slice(0, stepIdx + 1).slice().reverse().map((s, ri) => {
                const origIdx = stepIdx - ri;
                return (
                <li key={origIdx} className={cn(
                  "px-4 py-2.5 text-xs transition-colors",
                  origIdx === stepIdx && "bg-primary/5",
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
                );
              })}
            </ol>
          </section>

          {/* Range reference panel */}
          {showRange && step.street === 'preflop' && (
            <RangePanel
              key={stepIdx}
              step={step}
              hero={replayData.hero}
              heroCards={replayData.hero_cards}
              onClose={() => setShowRange(false)}
            />
          )}

          {/* EV feedback — ocultado para aluno quando coach substituiu a análise */}
          {step.type === "action" && step.is_hero &&
           (studentId !== null || coachAnnotation?.mode !== "replace") && (
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

          {/* Coach annotation panel */}
          {studentId && step?.is_hero && step?.is_error && currentDecisionId && (
            <section className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <GraduationCap className="size-4 text-primary" />
                  <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
                    Coach · {coachAnnotation ? (coachAnnotation.mode === "replace" ? "Análise exclusiva" : "Complemento") : "Anotação"}
                  </span>
                </div>
                {!annotating && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={openAnnotationForm}
                      className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors"
                    >
                      <PenLine className="size-3" />
                      {coachAnnotation ? "Editar" : "Anotar"}
                    </button>
                    {coachAnnotation && (
                      <button
                        onClick={() => deleteAnn.mutate()}
                        disabled={deleteAnn.isPending}
                        className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
                      >
                        {deleteAnn.isPending ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Existing annotation display */}
              {!annotating && coachAnnotation && (
                <div className="space-y-1">
                  <p className="text-sm text-foreground leading-relaxed">{coachAnnotation.comment}</p>
                  {coachAnnotation.coach_action && (
                    <p className="font-mono text-[11px] text-primary">→ Correto: {coachAnnotation.coach_action}</p>
                  )}
                </div>
              )}

              {/* No annotation placeholder */}
              {!annotating && !coachAnnotation && (
                <p className="text-xs text-muted-foreground">Nenhuma anotação para esta decisão.</p>
              )}

              {/* Annotation form */}
              {annotating && (
                <div className="space-y-3">
                  {/* Mode toggle */}
                  <div className="flex gap-2">
                    {(["complement", "replace"] as const).map((m) => (
                      <button key={m} type="button" onClick={() => setAnnMode(m)}
                        className={`flex-1 py-1.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest-2 border transition-colors ${
                          annMode === m
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border text-muted-foreground hover:border-primary/50"
                        }`}
                      >
                        {m === "complement" ? "Complementar" : "Substituir IA"}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={annComment}
                    onChange={(e) => setAnnComment(e.target.value)}
                    rows={3}
                    placeholder="Sua análise desta decisão…"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">Ação correta</label>
                      <select
                        value={annAction}
                        onChange={(e) => setAnnAction(e.target.value)}
                        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
                      >
                        {["", "fold", "check", "call", "bet", "raise", "re-raise", "all-in"].map((a) => (
                          <option key={a} value={a}>{a || "— Não especificar"}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">Classificação</label>
                      <select
                        value={annOverride ?? ""}
                        onChange={(e) => setAnnOverride((e.target.value || null) as CoachOverrideLabel)}
                        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"
                      >
                        <option value="">— Sem veredito</option>
                        <option value="standard">✓ Jogada Correta</option>
                        <option value="marginal">~ Marginal</option>
                        <option value="small_mistake">⚠ Erro Pequeno</option>
                        <option value="clear_mistake">✕ Erro Claro</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => saveAnn.mutate()}
                      disabled={!annComment.trim() || saveAnn.isPending}
                      className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] font-bold uppercase text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      {saveAnn.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                      Salvar
                    </button>
                    <button onClick={() => setAnnotating(false)}
                      className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground hover:text-foreground"
                    >
                      <X className="size-3" /> Cancelar
                    </button>
                    {coachAnnotation && (
                      <button
                        onClick={() => deleteAnn.mutate()} disabled={deleteAnn.isPending}
                        className="ml-auto inline-flex items-center gap-1.5 font-mono text-[10px] text-destructive hover:underline disabled:opacity-50"
                      >
                        <Trash2 className="size-3" /> Remover
                      </button>
                    )}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Read-only annotation balloon for students */}
          {!studentId && coachAnnotation && (
            <section className={cn(
              "rounded-xl border p-4 space-y-2",
              coachAnnotation.mode === "replace"
                ? "border-primary/50 bg-primary/8"
                : "border-primary/20 bg-primary/5"
            )}>
              <div className="flex items-center gap-2 flex-wrap">
                <GraduationCap className="size-4 text-primary" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
                  Coach · {coachAnnotation.mode === "replace" ? "Análise exclusiva" : "Complemento do coach"}
                </span>
                {coachAnnotation.coach_override_label && (
                  <span className={cn(
                    "font-mono text-[9px] font-bold px-1.5 py-0.5 rounded ring-1",
                    coachAnnotation.coach_override_label === "standard"
                      ? "text-primary ring-primary/30 bg-primary/10"
                      : coachAnnotation.coach_override_label === "marginal"
                      ? "text-yellow-500 ring-yellow-500/30 bg-yellow-500/10"
                      : coachAnnotation.coach_override_label === "small_mistake"
                      ? "text-amber-400 ring-amber-400/30 bg-amber-400/10"
                      : "text-destructive ring-destructive/30 bg-destructive/10"
                  )}>
                    {coachAnnotation.coach_override_label === "standard" ? "✓ Jogada Correta"
                      : coachAnnotation.coach_override_label === "marginal" ? "~ Marginal"
                      : coachAnnotation.coach_override_label === "small_mistake" ? "⚠ Erro Pequeno"
                      : "✕ Erro Claro"}
                  </span>
                )}
              </div>
              <p className="text-sm text-foreground leading-relaxed">{coachAnnotation.comment}</p>
              {coachAnnotation.coach_action && (
                <p className="font-mono text-[11px] text-primary">
                  → Ação: {coachAnnotation.coach_action}
                </p>
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
                  <li key={i} className={cn(
                    "text-xs space-y-0.5 rounded-lg px-2.5 py-2 -mx-2.5 transition-colors",
                    sd.outcome === "won"
                      ? "bg-primary/10 ring-1 ring-primary/30 shadow-[0_0_12px_rgba(var(--primary-rgb,99,179,132)/0.25)]"
                      : "opacity-60"
                  )}>
                    <div className="flex items-center justify-between gap-2">
                      <span className={cn("font-semibold", sd.outcome === "won" ? "text-primary" : "text-muted-foreground")}>
                        {sd.outcome === "won" && <span className="mr-1">🏆</span>}
                        {playerAliases[sd.player] ?? sd.player}
                      </span>
                      {sd.outcome === "won" && (
                        <span className="font-mono text-[11px] font-bold text-primary">+{sd.won}</span>
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

        </aside>
      </div>
    </HudLayout>
  );
};

export default Replayer;
