import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Trophy } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { metrics, LeaderboardResponse, LeaderboardEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

const RANK_TINT: Record<number, string> = {
  1: "text-yellow-400",
  2: "text-slate-300",
  3: "text-amber-600",
};

function MiniBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="font-mono text-[9px] uppercase text-muted-foreground w-20 shrink-0">{label}</span>
      <div className="h-1 flex-1 rounded-full bg-muted/20 overflow-hidden">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="font-mono text-[9px] tabular-nums text-muted-foreground w-7 text-right">{Math.round(pct)}</span>
    </div>
  );
}

function Row({ e }: { e: LeaderboardEntry }) {
  const { t } = useTranslation("dashboard");
  const rank = e.rank ?? 0;
  return (
    <div className="rounded-xl border border-border/40 bg-card/40 p-4">
      <div className="flex items-center gap-4">
        <span className={cn("font-mono text-2xl font-bold tabular-nums w-8 text-center shrink-0",
          RANK_TINT[rank] ?? "text-muted-foreground")}>
          {rank}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-foreground truncate">{e.display_name}</div>
          <div className="font-mono text-[10px] text-muted-foreground">
            {Math.round(e.player_elo)} ELO · {e.hands.toLocaleString()} · {e.tournaments}t · {e.drills}d
          </div>
        </div>
        <span className="font-mono text-3xl font-bold tabular-nums text-primary shrink-0">
          {e.score.toFixed(1)}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4 gap-y-1">
        <MiniBar label={t("leaderboard.dimGto")} pct={e.dimensions.gto} />
        <MiniBar label={t("leaderboard.dimEvolution")} pct={e.dimensions.evolution} />
        <MiniBar label={t("leaderboard.dimEngagement")} pct={e.dimensions.engagement} />
        <MiniBar label={t("leaderboard.dimVolume")} pct={e.dimensions.volume} />
      </div>
    </div>
  );
}

function Body({ data }: { data: LeaderboardResponse }) {
  const { t } = useTranslation("dashboard");
  const w = data.weights;
  const g = data.eligibility;
  const reason = (code: string | null) =>
    code ? t(`leaderboard.reason_${code}`, { defaultValue: code }) : "";

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Ranking principal */}
      <div className="lg:col-span-2 space-y-2">
        {data.ranked.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("leaderboard.empty")}</p>
        ) : (
          data.ranked.map((e) => <Row key={e.user_id} e={e} />)
        )}
      </div>

      {/* Sidebar — como é calculado + inelegíveis */}
      <aside className="space-y-4">
        <div className="rounded-xl border border-border/40 bg-card/40 p-4">
          <div className="font-mono text-[10px] text-muted-foreground space-y-1">
            <div>{t("leaderboard.weightsNote", {
              gto: Math.round(w.gto * 100), evo: Math.round(w.evolution * 100),
              eng: Math.round(w.engagement * 100), vol: Math.round(w.volume * 100),
            })}</div>
            <div>{t("leaderboard.gateNote", {
              hands: g.min_hands, tournaments: g.min_tournaments, gto: g.min_gto_decisions,
            })}</div>
          </div>
        </div>

        {data.ineligible.length > 0 && (
          <section className="space-y-2">
            <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              {t("leaderboard.ineligibleTitle")}
            </h3>
            <div className="rounded-xl border border-border/40 bg-card/30 overflow-hidden">
              {data.ineligible.map((e) => (
                <div key={e.user_id}
                     className="flex items-center justify-between px-4 py-2 border-t border-border/30 first:border-t-0">
                  <span className="text-sm text-muted-foreground truncate">{e.display_name}</span>
                  <span className="font-mono text-[10px] text-amber-400/80 shrink-0">{reason(e.reason)}</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </aside>
    </div>
  );
}

export default function Leaderboard() {
  const { t } = useTranslation("dashboard");
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    metrics.leaderboard()
      .then(setData)
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <HudLayout
      eyebrow={t("leaderboard.eyebrow")}
      title={t("leaderboard.title")}
      description={t("leaderboard.description")}
    >
      {loading && (
        <div className="py-12 text-center font-mono text-sm text-muted-foreground">
          {t("leaderboard.loading")}
        </div>
      )}
      {error && <div className="py-12 text-center text-sm text-destructive">{error}</div>}
      {data && <Body data={data} />}
    </HudLayout>
  );
}
