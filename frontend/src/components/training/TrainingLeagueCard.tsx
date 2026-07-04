import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Trophy, Flame, Loader2 } from "lucide-react";
import { metrics, leaderboardPrefs } from "@/lib/api";
import { cn } from "@/lib/utils";

// Liga de Treino (#32): ranking de ESFORÇO da semana (acertos no treino), NUNCA por
// ELO/skill. Opt-in/handle reusam a mesma vitrine do Ranking (#15). Reset semanal
// automático (a janela é a semana corrente no backend).
export function TrainingLeagueCard() {
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

  return (
    <section className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Trophy className="size-4 text-primary" />
          <h2 className="font-heading text-sm font-bold text-foreground">{t("league.title")}</h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {t("league.thisWeek")}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">{t("league.subtitle")}</p>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {ranked.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("league.empty")}</p>
          ) : (
            <div className="divide-y divide-border">
              {ranked.map((e) => {
                const self = !!me?.is_self && e.user_id === me.user_id;
                return (
                  <div
                    key={e.user_id}
                    className={cn(
                      "flex items-center gap-3 py-2.5",
                      self && "-mx-2 rounded-md bg-primary/5 px-2"
                    )}
                  >
                    <span className="w-6 text-right font-mono text-sm font-bold tabular-nums text-primary">{e.rank}</span>
                    <span className={cn("min-w-0 flex-1 truncate text-sm", self ? "font-bold text-foreground" : "text-foreground")}>
                      {e.display_name}{self ? ` · ${t("league.you")}` : ""}
                    </span>
                    <span className="flex w-10 items-center justify-end gap-1 font-mono text-[11px] text-muted-foreground tabular-nums">
                      <Flame className="size-3 text-amber-400/70" />{e.streak}
                    </span>
                    <span className="w-20 text-right font-mono text-[11px] text-muted-foreground tabular-nums">
                      {e.spots} {t("league.spots")}
                    </span>
                    <span className="w-16 text-right font-mono text-sm font-bold tabular-nums text-foreground">{e.points}</span>
                  </div>
                );
              })}
            </div>
          )}

          {me && (
            <div className="rounded-lg border border-border bg-hud-elevated/40 p-3">
              {me.opt_in ? (
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
                    {t("league.yourPosition")}
                  </span>
                  <span className="font-mono text-xs text-foreground tabular-nums">
                    {me.rank ? `#${me.rank}` : t("league.notRanked")} · {me.points} {t("league.points")}
                  </span>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">{t("league.joinHint")}</p>
                  <button
                    onClick={() => optIn.mutate()}
                    disabled={optIn.isPending}
                    className="inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground transition-all hover:bg-primary-glow disabled:opacity-50"
                  >
                    {optIn.isPending && <Loader2 className="size-3 animate-spin" />}
                    {t("league.join")}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      <p className="font-mono text-[10px] leading-relaxed text-muted-foreground">{t("league.effortNote")}</p>
    </section>
  );
}
