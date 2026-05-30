import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { HudLayout } from "@/components/hud/HudLayout";
import {
  metrics, leaderboardPrefs,
  LeaderboardResponse, LeaderboardEntry, LeaderboardMe, LeaderboardPrefs,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

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

/** "Sua posição" — sempre visível pro próprio usuário, mesmo fora do ranking público. */
function MyPosition({ me }: { me: LeaderboardMe }) {
  const { t } = useTranslation("dashboard");
  const listed = me.rank != null;
  return (
    <div className="rounded-xl border border-primary/40 bg-primary/[0.04] p-4 space-y-1">
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {t("leaderboard.myPositionTitle")}
      </div>
      {listed ? (
        <div className="font-mono text-lg font-bold text-foreground">
          {t("leaderboard.myRank", { rank: me.rank })}
        </div>
      ) : (
        <div className="space-y-0.5">
          <div className="text-sm text-foreground">{t("leaderboard.notListed")}</div>
          <div className="text-xs text-muted-foreground">{t("leaderboard.notListedCta")}</div>
        </div>
      )}
      {me.eligible && (
        <div className="font-mono text-[10px] text-muted-foreground">
          {t("leaderboard.myScoreLine", { score: me.score.toFixed(1), elo: Math.round(me.player_elo) })}
        </div>
      )}
    </div>
  );
}

/** Card de opt-in/privacidade — liga/desliga a participação e define o handle. */
function PrivacyCard({ prefs, onSaved }: { prefs: LeaderboardPrefs; onSaved: () => void }) {
  const { t } = useTranslation("dashboard");
  const [optIn, setOptIn] = useState(prefs.opt_in);
  const [handle, setHandle] = useState(prefs.handle ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const dirty = optIn !== prefs.opt_in || (handle.trim() || null) !== (prefs.handle ?? null);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await leaderboardPrefs.set(optIn, handle.trim() || null);
      setSaved(true);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-border/40 bg-card/40 p-4 space-y-3">
      <h3 className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        {t("leaderboard.privacyTitle")}
      </h3>

      <div className="flex items-start justify-between gap-3">
        <Label htmlFor="lb-optin" className="text-sm text-foreground cursor-pointer leading-snug">
          {t("leaderboard.optIn")}
          <span className="block font-normal text-[11px] text-muted-foreground mt-0.5">
            {t("leaderboard.optInHint")}
          </span>
        </Label>
        <Switch
          id="lb-optin"
          checked={optIn}
          onCheckedChange={(v) => { setOptIn(v); setSaved(false); }}
          className="mt-0.5 shrink-0"
        />
      </div>

      {optIn && (
        <div className="space-y-1">
          <Label htmlFor="lb-handle" className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {t("leaderboard.handleLabel")}
          </Label>
          <Input
            id="lb-handle"
            value={handle}
            maxLength={24}
            placeholder={t("leaderboard.handlePlaceholder")}
            onChange={(e) => { setHandle(e.target.value); setSaved(false); }}
            className="h-8 text-sm"
          />
          <p className="text-[11px] text-muted-foreground">{t("leaderboard.handleHint")}</p>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button size="sm" onClick={save} disabled={saving || !dirty} className="h-7 text-xs">
          {saving ? t("leaderboard.saving") : t("leaderboard.save")}
        </Button>
        {saved && !dirty && (
          <span className="font-mono text-[11px] text-emerald-400">{t("leaderboard.saved")}</span>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground/80 border-t border-border/30 pt-2">
        {t("leaderboard.coachNote")}
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
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Ranking principal */}
      <div className="lg:col-span-2 space-y-2">
        {data.ranked.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("leaderboard.empty")}</p>
        ) : (
          data.ranked.map((e) => <Row key={e.user_id} e={e} self={e.user_id === data.me?.user_id} />)
        )}
      </div>

      {/* Sidebar — sua posição, participação, como é calculado, inelegíveis */}
      <aside className="space-y-4">
        {data.me && <MyPosition me={data.me} />}

        {prefs && <PrivacyCard prefs={prefs} onSaved={onSaved} />}

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
