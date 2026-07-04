import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Flame, Loader2, Zap } from "lucide-react";
import { metrics, leaderboardPrefs, TrainingLeagueEntry, TrainingLeagueMe } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AxisHeader, MedalRank, EmptyLine } from "./shared";

/** "Sua posição" (esforço): rank público da semana + acertos + streak. */
function MyEffort({ me, onJoin, joining }: { me: TrainingLeagueMe; onJoin: () => void; joining: boolean }) {
  const { t } = useTranslation("training");
  if (!me.opt_in) {
    return (
      <div className="space-y-2 rounded-xl border border-primary/40 bg-primary/[0.06] p-4">
        <p className="text-xs text-muted-foreground">{t("league.joinHint")}</p>
        <button
          onClick={onJoin}
          disabled={joining}
          className="inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        >
          {joining && <Loader2 className="size-3 animate-spin" aria-hidden />}
          {t("league.join")}
        </button>
      </div>
    );
  }
  return (
    <div className="min-h-[6.5rem] rounded-xl border border-primary/40 bg-primary/[0.06] p-4">
      <div className="mb-1 font-mono text-[10px] uppercase tracking-widest-2 text-primary">
        {t("league.yourPosition")}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-heading text-2xl font-bold text-foreground">
          {me.rank ? `#${me.rank}` : t("league.notRanked")}
        </span>
        <span className="font-mono text-[11px] text-muted-foreground">
          {me.points} {t("league.points")}
        </span>
        {me.streak > 0 && (
          <span className="flex items-center gap-1 font-mono text-[11px] tabular-nums text-amber-400/90">
            <Flame className="size-3" aria-hidden />
            {me.streak}
          </span>
        )}
      </div>
    </div>
  );
}

/** Barra de esforço relativa ao líder da semana (espelha a MiniBar do eixo skill). */
function EffortBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-20 shrink-0 font-mono text-[9px] uppercase text-muted-foreground">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted/20">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
    </div>
  );
}

/** Linha de jogador na liga de esforço. MESMA estrutura/dimensão do eixo skill:
 *  cabeçalho (rank + nome/meta + acertos em destaque) + barra no rodapé. */
function EffortRow({ e, self, max }: { e: TrainingLeagueEntry; self?: boolean; max: number }) {
  const { t } = useTranslation("training");
  const pct = max > 0 ? (e.points / max) * 100 : 0;
  return (
    <div
      className={cn(
        "flex min-h-[6.75rem] flex-col rounded-xl border p-4 transition-colors",
        self ? "border-primary/50 bg-primary/[0.04]" : "border-border/40 bg-card/40"
      )}
    >
      <div className="flex items-center gap-4">
        <MedalRank rank={e.rank ?? 0} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">
            {e.display_name}
            {self && <span className="ml-1.5 font-mono text-[10px] uppercase text-primary">· {t("league.you")}</span>}
          </div>
          <div className="flex items-center gap-2 font-mono text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <Flame className="size-3 text-amber-400/70" aria-hidden />
              {e.streak}
            </span>
            <span>· {e.spots} {t("league.spots")}</span>
          </div>
        </div>
        <span className="shrink-0 font-mono text-3xl font-bold tabular-nums text-primary">{e.points}</span>
      </div>
      <div className="mt-auto pt-3">
        <EffortBar label={t("league.points")} pct={pct} />
      </div>
    </div>
  );
}

/** Painel do EIXO ESFORÇO — Liga de Treino (#32). Ranking semanal por acertos, nunca por skill. */
export function EffortLeague() {
  const { t } = useTranslation("training");
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["training-league"],
    queryFn: metrics.trainingLeague,
    staleTime: 60_000,
  });
  const optIn = useMutation({
    mutationFn: () => leaderboardPrefs.set(true, data?.me?.handle ?? null),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["training-league"] }),
  });

  const me = data?.me;
  const ranked = data?.ranked ?? [];
  const maxPoints = Math.max(1, ...ranked.map((r) => r.points));

  return (
    <section aria-labelledby="effort-heading" className="flex flex-col gap-3">
      <AxisHeader
        id="effort-heading"
        icon={<Zap className="size-4 text-primary" aria-hidden />}
        title={t("league.title")}
        subtitle={t("league.effortSubtitle")}
        aside={
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            {t("league.thisWeek")}
          </span>
        }
      />

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
        </div>
      ) : (
        <>
          {me && <MyEffort me={me} onJoin={() => optIn.mutate()} joining={optIn.isPending} />}
          {ranked.length === 0 ? (
            <EmptyLine>{t("league.empty")}</EmptyLine>
          ) : (
            <div className="space-y-2">
              {ranked.map((e) => (
                <EffortRow key={e.user_id} e={e} self={!!me?.is_self && e.user_id === me.user_id} max={maxPoints} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
