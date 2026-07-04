import { useState } from "react";
import { useTranslation } from "react-i18next";
import confetti from "canvas-confetti";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, XCircle, Shuffle, Users } from "lucide-react";
import { metrics, type DailyChallengeResult, type DailyChallengeSpot } from "@/lib/api";
import { cn } from "@/lib/utils";

const SUIT_GLYPH: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const SUIT_RED = new Set(["h", "d"]);

/** Carta mini (rank + naipe colorido) — leitura de mão, sem a mesa inteira. */
function MiniCard({ rank, suit }: { rank: string; suit: string }) {
  const red = SUIT_RED.has(suit);
  return (
    <div className={cn(
      "flex h-14 w-10 flex-col items-center justify-center rounded-md bg-white font-bold shadow-md ring-1 ring-black/20",
      red ? "text-red-600" : "text-slate-900",
    )}>
      <span className="text-lg leading-none">{rank}</span>
      <span className="text-base leading-none">{SUIT_GLYPH[suit] ?? suit}</span>
    </div>
  );
}

export function DailyChallengeCard() {
  const { t } = useTranslation("training");
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["daily-challenge"], queryFn: metrics.dailyChallenge });
  const [chosen, setChosen] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: (action: string) => metrics.dailyChallengeSubmit(action),
    onSuccess: (res) => {
      // acertou → comemoração (mesma paleta/efeito do fim da lição)
      if (res.result?.is_correct) {
        const colors = ["#2DD4BF", "#f5c542", "#5ad1ff", "#E3E8EC"];
        const burst = (particleCount: number, spread: number, y: number) =>
          confetti({ particleCount, spread, startVelocity: 38, origin: { y }, colors, scalar: 0.9, disableForReducedMotion: true });
        burst(120, 70, 0.6);
        setTimeout(() => burst(60, 110, 0.62), 200);
      }
      // revalida pra trazer stats atualizadas + estado answered
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

  // frase de contexto legível a partir do cenário
  const context = (() => {
    const pos = spot.position, vs = spot.vs_position;
    if (spot.scenario === "rfi") return t("challenge.ctx.rfi", { pos });
    if (spot.scenario === "vs_rfi") return t("challenge.ctx.vsRfi", { pos, vs });
    if (spot.scenario === "vs_3bet") return t("challenge.ctx.vs3bet", { pos, vs });
    return `${pos}`;
  })();

  const kind = result ? (result.gto_tier === "error" ? "error" : result.mixed ? "mixed" : "correct") : null;

  return (
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

      <p className="mb-3 text-xs leading-snug text-muted-foreground">{t("challenge.subtitle")}</p>

      {/* Spot: contexto + mão do herói */}
      <div className="mb-4 flex flex-col gap-3 rounded-xl bg-background/50 p-4 ring-1 ring-border sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-bold text-foreground">{context}</p>
          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
            {spot.stack_bb}bb
            {spot.facing_size ? ` · ${t("challenge.facing", { size: spot.facing_size })}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {(spot.hero_cards ?? []).map((c, i) => <MiniCard key={i} rank={c.rank} suit={c.suit} />)}
        </div>
      </div>

      {!answered ? (
        <>
          <p className="mb-2 text-center font-mono text-[11px] uppercase tracking-widest text-muted-foreground">{t("challenge.prompt")}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {spot.options.map((a) => (
              <button key={a} disabled={submit.isPending}
                onClick={() => { setChosen(a); submit.mutate(a); }}
                className={cn(
                  "rounded-xl bg-card/70 px-4 py-3 font-mono text-sm font-bold uppercase tracking-wider text-foreground ring-1 ring-border transition-all active:scale-95 hover:text-sky-300 hover:ring-sky-500/60 disabled:opacity-40",
                  submit.isPending && chosen === a && "ring-sky-500/60 text-sky-300",
                )}>
                {actLabel(a)}
              </button>
            ))}
          </div>
        </>
      ) : result && kind && (
        <VerdictBox result={result} kind={kind} actLabel={actLabel} t={t} />
      )}
    </div>
  );
}

function VerdictBox({ result, kind, actLabel, t }: {
  result: DailyChallengeResult;
  kind: "correct" | "mixed" | "error";
  actLabel: (a: string) => string;
  t: (k: string, o?: Record<string, unknown>) => string;
}) {
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

      {/* Estratégia GTO — barras por ação (a mesma linguagem do Leak Trainer) */}
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
      <p className="text-[12px] leading-snug text-muted-foreground">{result.explanation}</p>
      {/* Explicação didática (vetada na criação) — o "porquê" para o jogador entender */}
      {result.teaching && (
        <div className="rounded-lg bg-background/40 p-3 ring-1 ring-border">
          <p className="text-[12px] leading-relaxed text-foreground/90">{result.teaching}</p>
        </div>
      )}
      <p className="text-[10px] leading-snug text-muted-foreground">{t("challenge.comeBack")}</p>
    </div>
  );
}
