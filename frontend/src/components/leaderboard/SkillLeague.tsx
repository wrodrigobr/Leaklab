import { useTranslation } from "react-i18next";
import { Award, Check } from "lucide-react";
import { LeaderboardResponse, LeaderboardEntry, LeaderboardMe } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AxisHeader, MedalRank, EmptyLine } from "./shared";

/** Barra fina de dimensão (GTO / Evolução / Engajamento / Volume). */
function MiniBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-20 shrink-0 font-mono text-[9px] uppercase text-muted-foreground">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted/20">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="w-7 text-right font-mono text-[9px] tabular-nums text-muted-foreground">{Math.round(pct)}</span>
    </div>
  );
}

/** Linha de jogador no ranking de skill (com barras de dimensão). */
function Row({ e, self }: { e: LeaderboardEntry; self?: boolean }) {
  const { t } = useTranslation("dashboard");
  const rank = e.rank ?? 0;
  return (
    <div
      className={cn(
        "rounded-xl border p-4 transition-colors",
        self ? "border-primary/50 bg-primary/[0.04]" : "border-border/40 bg-card/40"
      )}
    >
      <div className="flex items-center gap-4">
        <MedalRank rank={rank} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">
            {e.display_name}
            {self && <span className="ml-1.5 font-mono text-[10px] uppercase text-primary">· {t("leaderboard.you", { defaultValue: "you" })}</span>}
          </div>
          <div className="font-mono text-[10px] text-muted-foreground">
            {Math.round(e.player_elo)} ELO · {e.hands.toLocaleString()} · {e.tournaments}t · {e.drills}d
          </div>
        </div>
        <span className="shrink-0 font-mono text-3xl font-bold tabular-nums text-primary">
          {e.score.toFixed(1)}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2">
        <MiniBar label={t("leaderboard.dimGto")} pct={e.dimensions.gto} />
        <MiniBar label={t("leaderboard.dimEvolution")} pct={e.dimensions.evolution} />
        <MiniBar label={t("leaderboard.dimEngagement")} pct={e.dimensions.engagement} />
        <MiniBar label={t("leaderboard.dimVolume")} pct={e.dimensions.volume} />
      </div>
    </div>
  );
}

/** Variação de posição vs. snapshot anterior (▲ subiu / ▼ caiu / — igual). */
function RankDeltaBadge({ me }: { me: LeaderboardMe }) {
  const { t } = useTranslation("dashboard");
  if (!me.rank_delta) return null;
  const d = me.rank_delta.delta;
  const cls = d > 0 ? "text-emerald-400" : d < 0 ? "text-red-400" : "text-muted-foreground";
  const sym = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  return (
    <span className={cn("font-mono text-[11px] tabular-nums", cls)} title={t("leaderboard.rankDeltaSince")}>
      {sym}
      {d !== 0 ? ` ${Math.abs(d)}` : ""}
    </span>
  );
}

/** "Sua posição" (skill): se elegível, posição/score/ELO/delta; se não, um CHECKLIST
 *  do que falta pra entrar (torneios/mãos/decisões GTO) com o progresso do jogador —
 *  pra ele saber por que não aparece, em vez de procurar o nome à toa. */
function MyPosition({ me, eligibility }: { me: LeaderboardMe; eligibility: LeaderboardResponse["eligibility"] }) {
  const { t } = useTranslation("dashboard");
  const hasRank = me.overall_rank != null;
  const reqs = [
    { label: t("leaderboard.reqTournaments"), have: me.tournaments, need: eligibility.min_tournaments },
    { label: t("leaderboard.reqHands"), have: me.hands, need: eligibility.min_hands },
    { label: t("leaderboard.reqGto"), have: me.gto_decisions, need: eligibility.min_gto_decisions },
  ];
  return (
    <div className="rounded-xl border border-primary/40 bg-primary/[0.06] p-4">
      <div className="mb-1 font-mono text-[10px] uppercase tracking-widest-2 text-primary">
        {t("leaderboard.myPositionTitle")}
      </div>
      {hasRank ? (
        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="font-heading text-2xl font-bold text-foreground">
              {t("leaderboard.overallRank", { rank: me.overall_rank })}
            </span>
            <RankDeltaBadge me={me} />
          </div>
          <div className="font-mono text-[11px] text-muted-foreground">
            {t("leaderboard.myScoreLine", { score: me.score.toFixed(1), elo: Math.round(me.player_elo) })}
          </div>
          <div className="text-[11px] text-muted-foreground">
            {me.opt_in ? t("leaderboard.publicYes") : t("leaderboard.publicNo")}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="text-sm text-foreground">{t("leaderboard.notEligibleTitle")}</div>
          <div className="space-y-1.5">
            {reqs.map((r) => {
              const done = r.have >= r.need;
              return (
                <div key={r.label} className="flex items-center gap-2">
                  {done ? (
                    <Check className="size-3.5 shrink-0 text-emerald-400" aria-hidden />
                  ) : (
                    <span className="size-3.5 shrink-0 rounded-full border border-muted-foreground/40" aria-hidden />
                  )}
                  <span className="flex-1 text-[11px] text-muted-foreground">{r.label}</span>
                  <span
                    className={cn(
                      "font-mono text-[11px] tabular-nums",
                      done ? "text-emerald-400" : "text-foreground"
                    )}
                  >
                    {r.have.toLocaleString()}/{r.need.toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/** Painel do EIXO SKILL — aderência GTO (#15). Ranking permanente por aprendizado. */
export function SkillLeague({ data }: { data: LeaderboardResponse }) {
  const { t } = useTranslation("dashboard");
  return (
    <section aria-labelledby="skill-heading" className="flex flex-col gap-3">
      <AxisHeader
        id="skill-heading"
        icon={<Award className="size-4 text-primary" aria-hidden />}
        title={t("leaderboard.skillTitle")}
        subtitle={t("leaderboard.skillSubtitle")}
      />
      {data.me && <MyPosition me={data.me} eligibility={data.eligibility} />}
      {data.ranked.length === 0 ? (
        <EmptyLine>{t("leaderboard.empty")}</EmptyLine>
      ) : (
        <div className="space-y-2">
          {data.ranked.map((e) => (
            <Row key={e.user_id} e={e} self={e.user_id === data.me?.user_id} />
          ))}
        </div>
      )}
    </section>
  );
}
