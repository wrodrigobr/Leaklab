import { useState } from "react";
import { useTranslation } from "react-i18next";
import confetti from "canvas-confetti";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, XCircle, Shuffle, Users, Play, X, Loader2 } from "lucide-react";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { buildChallengeStep } from "@/lib/challengeTable";
import { metrics, type DailyChallengeResult } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DailyChallengeCard() {
  const { t } = useTranslation("training");
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["daily-challenge"], queryFn: metrics.dailyChallenge });
  const [open, setOpen] = useState(false);   // mesa em tela cheia

  const submit = useMutation({
    mutationFn: (action: string) => metrics.dailyChallengeSubmit(action),
    onSuccess: (res) => {
      // acertou → comemoração (mesma paleta/efeito do fim da lição)
      if (res.result?.is_correct) {
        const colors = ["#2DD4BF", "#f5c542", "#5ad1ff", "#E3E8EC"];
        const burst = (particleCount: number, spread: number, y: number) =>
          confetti({ particleCount, spread, startVelocity: 38, origin: { y }, colors, scalar: 0.9, disableForReducedMotion: true });
        burst(140, 70, 0.55);
        setTimeout(() => burst(70, 110, 0.6), 220);
      }
      qc.invalidateQueries({ queryKey: ["daily-challenge"] });
      qc.invalidateQueries({ queryKey: ["training-overview"] });
    },
  });

  // Não há desafio aprovado hoje → o card some (nada de placeholder confuso).
  if (isLoading || !data?.available || !data.spot) return null;

  const spot = data.spot;
  const answered = data.answered || submit.isSuccess;
  const result: DailyChallengeResult | undefined = submit.data?.result ?? data.result;
  const stats = submit.data?.stats ?? data.stats;

  // rótulo da ação (raise muda por cenário; allin = shove, jam abolido)
  const actLabel = (a: string) => {
    if (a === "raise") {
      return spot.scenario === "vs_3bet" ? t("challenge.act.raise4")
        : spot.scenario === "vs_rfi" ? t("challenge.act.raise3")
        : t("challenge.act.raiseOpen");
    }
    return t(`challenge.act.${a}`, a);
  };

  const context = (() => {
    const pos = spot.position, vs = spot.vs_position;
    if (spot.scenario === "rfi") return t("challenge.ctx.rfi", { pos });
    if (spot.scenario === "vs_rfi") return t("challenge.ctx.vsRfi", { pos, vs });
    if (spot.scenario === "vs_3bet") return t("challenge.ctx.vs3bet", { pos, vs });
    return `${pos}`;
  })();

  const closeFull = () => setOpen(false);

  return (
    <>
      <div className="rounded-2xl border border-sky-500/30 bg-gradient-to-br from-sky-500/[0.08] to-transparent p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 font-heading text-base font-bold text-foreground">
            <CalendarClock className="size-4 text-sky-400" aria-hidden /> {t("challenge.title")}
          </h2>
          {stats && stats.total > 0 && stats.pct !== null && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500/10 px-2.5 py-1 ring-1 ring-sky-500/25">
              <Users className="size-3 text-sky-400" aria-hidden />
              <span className="font-mono text-[11px] font-bold tabular-nums text-sky-200">{stats.pct}%</span>
              <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{t("challenge.todayHit")}</span>
            </span>
          )}
        </div>

        <p className="mb-4 text-xs leading-snug text-muted-foreground">{t("challenge.subtitle")}</p>

        {!answered ? (
          <button onClick={() => setOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-sky-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-sky-400">
            <Play className="size-4" aria-hidden /> {t("challenge.start")}
          </button>
        ) : result && (
          <VerdictBox result={result} actLabel={actLabel} context={context} spot={spot} t={t} />
        )}
      </div>

      {/* ── Mesa em TELA CHEIA (ao iniciar o desafio) ── */}
      {open && (
        <ChallengeFullscreen
          spot={spot} context={context} actLabel={actLabel} t={t}
          result={submit.data?.result} pending={submit.isPending}
          onSubmit={(a) => submit.mutate(a)} onClose={closeFull}
        />
      )}
    </>
  );
}

/** Overlay imersivo: mesa PokerTableV3 + botões flutuantes + veredito (bottom-sheet). */
function ChallengeFullscreen({ spot, context, actLabel, t, result, pending, onSubmit, onClose }: {
  spot: import("@/lib/api").DailyChallengeSpot;
  context: string;
  actLabel: (a: string) => string;
  t: (k: string, o?: Record<string, unknown>) => string;
  result?: DailyChallengeResult;
  pending: boolean;
  onSubmit: (a: string) => void;
  onClose: () => void;
}) {
  const table = buildChallengeStep(spot);
  return (
    <div className="fixed inset-0 z-[60] flex flex-col hud-scanline"
      style={{ background: "radial-gradient(ellipse at 50% 42%, #14223a 0%, #080f1c 100%)" }}>
      {/* topo: contexto + stack + fechar */}
      <div className="flex items-center justify-between gap-2 px-[calc(0.75rem+env(safe-area-inset-left))] pt-[calc(0.6rem+env(safe-area-inset-top))]">
        <div className="flex items-center gap-1.5 rounded-full bg-background/70 px-3 py-1.5 ring-1 ring-sky-500/30 backdrop-blur">
          <CalendarClock className="size-3.5 text-sky-400" aria-hidden />
          <span className="font-mono text-[11px] font-bold text-foreground">{t("challenge.title")}</span>
          <span className="font-mono text-[10px] text-muted-foreground">{spot.stack_bb}bb</span>
        </div>
        <button onClick={onClose} aria-label={t("challenge.close")}
          className="flex size-9 items-center justify-center rounded-full bg-background/70 text-muted-foreground ring-1 ring-border backdrop-blur transition-colors hover:text-foreground">
          <X className="size-4" aria-hidden />
        </button>
      </div>

      {/* contexto da mão (uma linha, clara) */}
      <p className="px-4 pt-2 text-center text-sm font-bold text-foreground/90">{context}</p>

      {/* mesa (sempre em tamanho cheio; o veredito SOBREPÕE, não empurra → mesa não encolhe) */}
      <div className="relative flex min-h-0 flex-1 items-center justify-center p-1.5">
        <div className="h-full max-h-full w-auto max-w-full" style={{ aspectRatio: "16 / 10" }}>
          <PokerTableV3 step={table.step} hero="Hero" heroCards={table.heroCards} bb={table.bb} betUnit="bb" transparentBg />
        </div>

        {/* respondeu → veredito sobrepõe a mesa (o que importa agora é o veredito, não a mesa) */}
        {result && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm animate-fade-in">
            <div className="max-h-full w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-background/95 p-4 shadow-2xl">
              <VerdictInner result={result} actLabel={actLabel} t={t} />
              <button onClick={onClose}
                className="mt-3 w-full rounded-lg bg-sky-500 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-black transition-colors hover:bg-sky-400">
                {t("challenge.finish")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* base: botões só na fase de pergunta (some quando o veredito aparece) */}
      {!result && (
        <div className="flex flex-wrap items-center justify-center gap-2 px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-2">
          <p className="w-full text-center font-mono text-[11px] uppercase tracking-widest text-muted-foreground">{t("challenge.prompt")}</p>
          {spot.options.map((a) => (
            <button key={a} disabled={pending} onClick={() => onSubmit(a)}
              className="min-w-[92px] rounded-xl bg-card/80 px-5 py-3 font-mono text-sm font-bold uppercase tracking-wider text-foreground shadow-lg ring-1 ring-border backdrop-blur transition-all active:scale-95 hover:text-sky-300 hover:ring-sky-500/60 disabled:opacity-40">
              {pending ? <Loader2 className="mx-auto size-4 animate-spin" aria-hidden /> : actLabel(a)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Veredito no card do hub (quando o jogador já respondeu hoje). */
function VerdictBox({ result, actLabel, context, spot, t }: {
  result: DailyChallengeResult;
  actLabel: (a: string) => string;
  context: string;
  spot: import("@/lib/api").DailyChallengeSpot;
  t: (k: string, o?: Record<string, unknown>) => string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl bg-background/40 p-3 ring-1 ring-border">
        <span className="text-sm font-bold text-foreground">{context}</span>
        <span className="font-mono text-[11px] text-muted-foreground">{spot.hand} · {spot.stack_bb}bb</span>
      </div>
      <VerdictInner result={result} actLabel={actLabel} t={t} />
      <p className="text-[10px] leading-snug text-muted-foreground">{t("challenge.comeBack")}</p>
    </div>
  );
}

/** Corpo do veredito (cabeçalho + mix GTO + explicação) — reusado no hub e na tela cheia. */
function VerdictInner({ result, actLabel, t }: {
  result: DailyChallengeResult;
  actLabel: (a: string) => string;
  t: (k: string, o?: Record<string, unknown>) => string;
}) {
  const kind = result.gto_tier === "error" ? "error" : result.mixed ? "mixed" : "correct";
  const head = kind === "correct" ? t("challenge.verdict.correct")
    : kind === "mixed" ? t("challenge.verdict.mixed")
    : t("challenge.verdict.error");
  return (
    <div className={cn(
      "space-y-3 rounded-xl border p-4",
      kind === "correct" ? "border-emerald-500/30 bg-emerald-500/5"
        : kind === "mixed" ? "border-sky-500/30 bg-sky-500/5"
        : "border-amber-500/30 bg-amber-500/5",
    )}>
      <div className="flex items-center gap-2">
        {kind === "error"
          ? <XCircle className="size-5 shrink-0 text-amber-400" aria-hidden />
          : <CheckCircle2 className={cn("size-5 shrink-0", kind === "mixed" ? "text-sky-400" : "text-emerald-400")} aria-hidden />}
        <p className="font-bold text-foreground">{head}</p>
        <span className="ml-auto flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
          <Shuffle className="size-3" aria-hidden /> {t("challenge.youPlayed")} {actLabel(result.played)}
        </span>
      </div>

      {result.gto_strategy.length > 0 && (
        <div className="space-y-1.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("challenge.gtoStrategy")}</p>
          {result.gto_strategy.filter((s) => s.freq > 0.01).map((s) => {
            const pct = Math.round(s.freq * 100);
            const isBest = s.action === result.best_action;
            return (
              <div key={s.action} className="flex items-center gap-2">
                <span className="w-16 shrink-0 font-mono text-[11px] font-bold uppercase text-foreground">{actLabel(s.action)}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted/30">
                  <div className={cn("h-full rounded-full", isBest ? "bg-emerald-400" : "bg-sky-500/60")} style={{ width: `${pct}%` }} />
                </div>
                <span className="w-9 shrink-0 text-right font-mono text-[10px] tabular-nums text-muted-foreground">{pct}%</span>
              </div>
            );
          })}
        </div>
      )}
      {/* Um único bloco do "porquê": o teaching (LLM em prod, fallback em dev). O
          result.explanation determinístico só repetia o cabeçalho + as barras, então saiu. */}
      {(result.teaching || result.explanation) && (
        <div className="rounded-lg bg-background/40 p-3 ring-1 ring-border">
          <p className="text-[12px] leading-relaxed text-foreground/90">{result.teaching || result.explanation}</p>
        </div>
      )}
    </div>
  );
}
