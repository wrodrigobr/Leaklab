import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2, TrendingDown, CheckCircle2, XCircle, MinusCircle, Play } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { ProLockCard } from "@/components/hud/ProLockCard";
import { metrics, type CoachReplayVerdict } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Coach Replay — a revisão guiada dos erros mais caros de UM torneio.
 *
 * O backend (`/player/coach-replay/<code>`) já montava a playlist há tempos: mãos filtradas por
 * custo, com veredito, EV perdido e narração, mais um plano de estudo. Faltava a tela — o
 * endpoint existia sem porta de entrada.
 *
 * Cada mão abre no Replayer REAL por deep-link (`/replayer?t=…&h=…`), em vez de embutir uma
 * segunda mesa aqui: o Replayer é a superfície onde o veredito já é consistente com o resto do
 * produto, e recriá-lo seria criar uma segunda verdade sobre a mesma mão — o erro que esta base
 * já pagou caro várias vezes.
 */
const VERDICT_STYLE: Record<CoachReplayVerdict, { icon: typeof CheckCircle2; cls: string; ring: string }> = {
  error:      { icon: XCircle,      cls: "text-amber-400",   ring: "ring-amber-500/30 bg-amber-500/[0.06]" },
  acceptable: { icon: MinusCircle,  cls: "text-sky-400",     ring: "ring-sky-500/25 bg-sky-500/[0.05]" },
  correct:    { icon: CheckCircle2, cls: "text-emerald-400", ring: "ring-emerald-500/25 bg-emerald-500/[0.05]" },
};

export default function CoachReplay() {
  const { t } = useTranslation("tournaments");
  const { tournamentId = "" } = useParams();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["coach-replay", tournamentId],
    queryFn: () => metrics.coachReplay(tournamentId),
    enabled: !!tournamentId,
    retry: false,
  });

  const code = data?.tournament?.code ?? tournamentId;

  return (
    <HudLayout
      eyebrow={t("coachReplay.eyebrow")}
      title={t("coachReplay.title")}
      description={t("coachReplay.subtitle")}
    >
      {isLoading && (
        <div className="flex flex-col items-center gap-3 py-20">
          <Loader2 className="size-7 animate-spin text-primary" aria-hidden />
          <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
            {t("coachReplay.loading")}
          </p>
        </div>
      )}

      {isError && (
        <p className="py-16 text-center text-sm text-muted-foreground">{t("coachReplay.error")}</p>
      )}

      {/* Gate Pro: o backend responde {requires_pro:true} em vez de 403 pra a tela poder vender */}
      {data?.requires_pro && <ProLockCard feature={t("coachReplay.proFeature")} />}

      {data && !data.requires_pro && (
        <div className="space-y-4">
          {/* ── Intro: por que estas mãos, e não as outras ── */}
          <section className="rounded-2xl border border-border bg-card/40 p-5">
            <h2 className="font-heading text-lg font-bold text-foreground">{data.tournament.name}</h2>
            <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
              {t("coachReplay.intro", {
                kept: data.intro.hands_kept,
                total: data.intro.hands_total,
                mistakes: data.intro.mistakes_count,
              })}
            </p>
            <div className="mt-3 flex flex-wrap gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {t("coachReplay.evLost")}
                </p>
                <p className="font-mono text-xl font-bold tabular-nums text-red-400">
                  −{data.intro.ev_lost_bb.toFixed(1)}<span className="text-xs text-muted-foreground">bb</span>
                </p>
              </div>
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {t("coachReplay.skipped")}
                </p>
                <p className="font-mono text-xl font-bold tabular-nums text-muted-foreground">
                  {data.intro.hands_skipped}
                </p>
              </div>
            </div>
          </section>

          {/* ── A playlist ── */}
          {data.hands.length === 0 ? (
            <p className="rounded-2xl border border-border bg-card/40 p-8 text-center text-sm text-muted-foreground">
              {t("coachReplay.noHands")}
            </p>
          ) : (
            <ol className="space-y-2">
              {data.hands.map((h) => {
                const st = VERDICT_STYLE[h.verdict] ?? VERDICT_STYLE.error;
                const Icon = st.icon;
                return (
                  <li key={h.hand_id}>
                    <Link
                      to={`/replayer?t=${encodeURIComponent(code)}&h=${encodeURIComponent(h.hand_id)}`}
                      className={cn("group flex items-start gap-3 rounded-xl p-4 ring-1 transition-colors hover:ring-primary/40", st.ring)}
                    >
                      <span className="mt-0.5 font-mono text-[11px] font-bold tabular-nums text-muted-foreground">
                        {String(h.seq).padStart(2, "0")}
                      </span>
                      <Icon className={cn("mt-0.5 size-4 shrink-0", st.cls)} aria-hidden />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline gap-x-2">
                          <span className="font-mono text-[12px] font-bold text-foreground">{h.position}</span>
                          <span className="font-mono text-[12px] text-muted-foreground">{h.hero_cards}</span>
                          <span className="font-mono text-[10px] uppercase text-muted-foreground/70">
                            {h.street_reached}
                          </span>
                          {h.ev_loss_bb > 0 && (
                            <span className="flex items-center gap-0.5 font-mono text-[11px] font-bold text-red-400">
                              <TrendingDown className="size-3" aria-hidden />−{h.ev_loss_bb.toFixed(1)}bb
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-[12px] leading-snug text-muted-foreground">{h.narration}</p>
                      </div>
                      <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
                    </Link>
                  </li>
                );
              })}
            </ol>
          )}

          {/* ── O plano: o que fazer com o que acabou de ver ── */}
          {data.plan?.length > 0 && (
            <section className="rounded-2xl border border-border bg-card/40 p-5">
              <h3 className="mb-2 font-heading text-base font-bold text-foreground">
                {t("coachReplay.planTitle")}
              </h3>
              <ol className="space-y-1.5">
                {data.plan.map((p) => (
                  <li key={p.week} className="flex gap-3 text-[13px]">
                    <span className="shrink-0 font-mono text-[11px] font-bold text-primary">
                      {t("coachReplay.week", { n: p.week })}
                    </span>
                    <span className="text-muted-foreground">{p.focus}</span>
                  </li>
                ))}
              </ol>
              <Link
                to="/leak-trainer"
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400"
              >
                <Play className="size-4" aria-hidden /> {t("coachReplay.trainCta")}
              </Link>
            </section>
          )}
        </div>
      )}
    </HudLayout>
  );
}
