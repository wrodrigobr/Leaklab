import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  metrics, leaderboardPrefs,
  LeaderboardResponse, LeaderboardEntry, LeaderboardMe, LeaderboardPrefs, HallOfFameEntry,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Award } from "lucide-react";
import { TrainingLeagueCard } from "@/components/training/TrainingLeagueCard";

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

function Row({ e, self }: { e: LeaderboardEntry; self?: boolean }) {
  const { t } = useTranslation("dashboard");
  const rank = e.rank ?? 0;
  return (
    <div className={cn("rounded-xl border p-4",
      self ? "border-primary/50 bg-primary/[0.04]" : "border-border/40 bg-card/40")}>
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

/** Variação de posição vs. snapshot anterior (▲ subiu / ▼ caiu / — igual). */
function RankDeltaBadge({ me }: { me: LeaderboardMe }) {
  const { t } = useTranslation("dashboard");
  if (!me.rank_delta) return null;
  const d = me.rank_delta.delta;
  const cls = d > 0 ? "text-emerald-400" : d < 0 ? "text-red-400" : "text-muted-foreground";
  const sym = d > 0 ? "▲" : d < 0 ? "▼" : "—";
  return (
    <span className={cn("font-mono text-[11px] tabular-nums", cls)} title={t("leaderboard.rankDeltaSince")}>
      {sym}{d !== 0 ? ` ${Math.abs(d)}` : ""}
    </span>
  );
}

/** "Sua posição" — posição geral (entre todos os elegíveis) + delta + visibilidade. */
function MyPosition({ me }: { me: LeaderboardMe }) {
  const { t } = useTranslation("dashboard");
  const hasRank = me.overall_rank != null;
  return (
    <div className="rounded-xl border border-primary/40 bg-primary/[0.04] p-4 space-y-1">
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {t("leaderboard.myPositionTitle")}
      </div>
      {hasRank ? (
        <>
          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-bold text-foreground">
              {t("leaderboard.overallRank", { rank: me.overall_rank })}
            </span>
            <RankDeltaBadge me={me} />
          </div>
          <div className="font-mono text-[10px] text-muted-foreground">
            {t("leaderboard.myScoreLine", { score: me.score.toFixed(1), elo: Math.round(me.player_elo) })}
          </div>
          <div className="text-[11px] text-muted-foreground">
            {me.opt_in ? t("leaderboard.publicYes") : t("leaderboard.publicNo")}
          </div>
        </>
      ) : (
        <div className="space-y-0.5">
          <div className="text-sm text-foreground">{t("leaderboard.notListed")}</div>
          <div className="text-xs text-muted-foreground">{t("leaderboard.notListedCta")}</div>
        </div>
      )}
    </div>
  );
}

/** Hall of Fame — campeões mensais (#15). Vazio até a série cobrir ≥1 mês. */
function HallOfFameCard() {
  const { t, i18n } = useTranslation("dashboard");
  const [champs, setChamps] = useState<HallOfFameEntry[]>([]);
  useEffect(() => {
    metrics.hallOfFame().then((r) => setChamps(r.champions)).catch(() => {});
  }, []);
  if (champs.length === 0) return null;

  const fmtMonth = (m: string) => {
    const d = new Date(`${m}-01T00:00:00`);
    return isNaN(d.getTime()) ? m : d.toLocaleDateString(i18n.language, { month: "short", year: "numeric" });
  };

  return (
    <section className="space-y-2">
      <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        {t("leaderboard.hofTitle")}
      </h3>
      <div className="rounded-xl border border-border/40 bg-card/40 overflow-hidden">
        {champs.map((c) => (
          <div key={c.month}
               className="flex items-center justify-between px-4 py-2 border-t border-border/30 first:border-t-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className="shrink-0">🏆</span>
              <div className="min-w-0">
                <div className="text-sm text-foreground truncate">
                  {c.anonymous ? t("leaderboard.anonymous") : c.champion}
                </div>
                <div className="font-mono text-[10px] text-muted-foreground">{fmtMonth(c.month)}</div>
              </div>
            </div>
            <span className="font-mono text-sm font-bold tabular-nums text-primary shrink-0">
              {c.score.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Card de opt-in/privacidade — liga/desliga a participação e define o handle. */
function PrivacyCard({ prefs, onSaved }: { prefs: LeaderboardPrefs; onSaved: () => void }) {
  const { t } = useTranslation("dashboard");
  const [optIn, setOptIn] = useState(prefs.opt_in);
  const [handle, setHandle] = useState(prefs.handle ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = optIn !== prefs.opt_in || (handle.trim() || null) !== (prefs.handle ?? null);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await leaderboardPrefs.set(optIn, handle.trim() || null);
      setSaved(true);
      onSaved();
    } catch (e) {
      const msg = String((e as Error)?.message ?? e);
      setError(msg === "handle_taken" ? t("leaderboard.handleTaken") : t("leaderboard.saveError"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <Switch
            id="lb-optin"
            checked={optIn}
            onCheckedChange={(v) => { setOptIn(v); setSaved(false); }}
            className="shrink-0"
          />
          <Label htmlFor="lb-optin" className="text-sm text-foreground cursor-pointer">
            {t("leaderboard.optIn")}
          </Label>
        </div>

        {optIn && (
          <Input
            id="lb-handle"
            value={handle}
            maxLength={24}
            placeholder={t("leaderboard.handlePlaceholder")}
            onChange={(e) => { setHandle(e.target.value); setSaved(false); setError(null); }}
            className="h-8 w-44 text-sm"
          />
        )}

        <div className="ml-auto flex items-center gap-2">
          {saved && !dirty && (
            <span className="font-mono text-[11px] text-emerald-400">{t("leaderboard.saved")}</span>
          )}
          {error && <span className="text-[11px] text-destructive">{error}</span>}
          {dirty && (
            <Button size="sm" onClick={save} disabled={saving} className="h-7 text-xs">
              {saving ? t("leaderboard.saving") : t("leaderboard.save")}
            </Button>
          )}
        </div>
      </div>
      <p className="mt-1.5 text-[10px] text-muted-foreground/70">
        {t("leaderboard.optInHint")} · {t("leaderboard.coachNote")}
      </p>
    </div>
  );
}

function Body({ data, prefs, onSaved }:
  { data: LeaderboardResponse; prefs: LeaderboardPrefs | null; onSaved: () => void }) {
  const { t } = useTranslation("dashboard");
  const w = data.weights;
  const g = data.eligibility;
  const reason = (code: string | null) =>
    code ? t(`leaderboard.reason_${code}`, { defaultValue: code }) : "";

  return (
    <div className="space-y-6">
      {/* Participação compacta (opt-in + apelido), uma linha no topo. */}
      {prefs && <PrivacyCard prefs={prefs} onSaved={onSaved} />}

      {/* Dois rankings LADO A LADO: eixos distintos (skill × esforço). */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Esquerda: Aderência GTO (skill) ── */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Award className="size-4 text-primary" />
            <h2 className="font-heading text-sm font-bold text-foreground">{t("leaderboard.skillTitle")}</h2>
          </div>
          {data.me && <MyPosition me={data.me} />}
          {data.ranked.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("leaderboard.empty")}</p>
          ) : (
            <div className="space-y-2">
              {data.ranked.map((e) => <Row key={e.user_id} e={e} self={e.user_id === data.me?.user_id} />)}
            </div>
          )}
        </section>

        {/* ── Direita: Liga de Treino (esforço) ── */}
        <TrainingLeagueCard />
      </div>

      {/* Secundário (menos destaque): como é calculado · hall of fame · inelegíveis. */}
      <div className="grid gap-4 md:grid-cols-3">
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

        <HallOfFameCard />

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
      </div>
    </div>
  );
}

export default function Leaderboard() {
  const { t } = useTranslation("dashboard");
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [prefs, setPrefs] = useState<LeaderboardPrefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () =>
    metrics.leaderboard()
      .then(setData)
      .catch((e) => setError(String(e?.message ?? e)));

  useEffect(() => {
    Promise.all([
      loadData(),
      leaderboardPrefs.get().then(setPrefs).catch(() => {}),
    ]).finally(() => setLoading(false));
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
      {data && <Body data={data} prefs={prefs} onSaved={loadData} />}
    </HudLayout>
  );
}
