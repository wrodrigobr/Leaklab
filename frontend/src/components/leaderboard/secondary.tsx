import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Trophy, Lock } from "lucide-react";
import { metrics, leaderboardPrefs, LeaderboardResponse, LeaderboardPrefs, HallOfFameEntry } from "@/lib/api";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Controle de participação (opt-in + apelido) que governa OS DOIS rankings. */
export function ParticipationBar({ prefs, onSaved }: { prefs: LeaderboardPrefs; onSaved: () => void }) {
  const { t } = useTranslation("dashboard");
  const [optIn, setOptIn] = useState(prefs.opt_in);
  const [handle, setHandle] = useState(prefs.handle ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Apelido é ONE-TIME: uma vez definido, fica travado (o input vira read-only).
  const locked = !!(prefs.handle && prefs.handle.trim());
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
      setError(
        msg === "handle_taken"
          ? t("leaderboard.handleTaken")
          : msg === "handle_locked"
            ? t("leaderboard.handleLocked")
            : msg === "handle_offensive"
              ? t("leaderboard.handleOffensive")
              : t("leaderboard.saveError")
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-hud-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
          {t("leaderboard.participationTitle")}
        </span>
        <div className="flex items-center gap-2">
          <Switch
            id="lb-optin"
            checked={optIn}
            onCheckedChange={(v) => {
              setOptIn(v);
              setSaved(false);
            }}
            className="shrink-0"
          />
          <Label htmlFor="lb-optin" className="cursor-pointer text-sm text-foreground">
            {t("leaderboard.optIn")}
          </Label>
        </div>

        {optIn &&
          (locked ? (
            <span
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border/60 bg-muted/10 px-2.5 font-mono text-sm text-foreground"
              title={t("leaderboard.handleLocked")}
            >
              <Lock className="size-3 text-muted-foreground" aria-hidden />
              {prefs.handle}
            </span>
          ) : (
            <Input
              id="lb-handle"
              value={handle}
              maxLength={24}
              aria-label={t("leaderboard.handleLabel")}
              placeholder={t("leaderboard.handlePlaceholder")}
              onChange={(e) => {
                setHandle(e.target.value);
                setSaved(false);
                setError(null);
              }}
              className="h-8 w-44 text-sm"
            />
          ))}

        <div className="ml-auto flex items-center gap-2">
          {saved && !dirty && (
            <span className="font-mono text-[11px] text-emerald-400" role="status">
              {t("leaderboard.saved")}
            </span>
          )}
          {error && (
            <span className="text-[11px] text-destructive" role="alert">
              {error}
            </span>
          )}
          {dirty && (
            <Button size="sm" onClick={save} disabled={saving} className="h-7 text-xs">
              {saving ? t("leaderboard.saving") : t("leaderboard.save")}
            </Button>
          )}
        </div>
      </div>
      <p className="mt-1.5 text-[10px] text-muted-foreground/70">
        {t("leaderboard.optInHint")} · {t("leaderboard.coachNote")}
        {optIn && !locked && <span className="text-amber-400/80"> · {t("leaderboard.handleOnceWarning")}</span>}
      </p>
    </div>
  );
}

/** Hall of Fame — campeões mensais (#15). Oculto até a série cobrir ≥1 mês. */
const HOF_PREVIEW = 6; // mostra os N mais recentes; o resto atrás do "ver todos" (backend limita em 12)

export function HallOfFameCard() {
  const { t, i18n } = useTranslation("dashboard");
  const [champs, setChamps] = useState<HallOfFameEntry[]>([]);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    metrics
      .hallOfFame()
      .then((r) => setChamps(r.champions))
      .catch(() => {});
  }, []);
  if (champs.length === 0) return null;

  const fmtMonth = (m: string) => {
    const d = new Date(`${m}-01T00:00:00`);
    return isNaN(d.getTime()) ? m : d.toLocaleDateString(i18n.language, { month: "long", year: "numeric" });
  };
  const shown = expanded ? champs : champs.slice(0, HOF_PREVIEW);

  return (
    <section aria-labelledby="hof" className="space-y-3">
      <div>
        <h3 id="hof" className="flex items-center gap-2 font-heading text-sm font-bold text-foreground">
          <Trophy className="size-4 text-yellow-400" aria-hidden />
          {t("leaderboard.hofTitle")}
        </h3>
        <p className="mt-0.5 text-xs text-muted-foreground">{t("leaderboard.hofSubtitle")}</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((c, i) => (
          <div
            key={c.month}
            className={cn(
              "flex items-center gap-3 rounded-xl border p-3",
              i === 0 ? "border-yellow-400/40 bg-yellow-400/[0.06]" : "border-border/40 bg-card/40"
            )}
          >
            <span
              className={cn(
                "flex size-9 shrink-0 items-center justify-center rounded-lg text-xl",
                i === 0 ? "bg-yellow-400/15" : "bg-muted/10"
              )}
              aria-hidden
            >
              🏆
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-foreground">
                {c.anonymous ? t("leaderboard.anonymous") : c.champion}
              </div>
              <div className="font-mono text-[10px] capitalize text-muted-foreground">{fmtMonth(c.month)}</div>
            </div>
            <span className="shrink-0 font-mono text-lg font-bold tabular-nums text-primary">
              {c.score.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
      {champs.length > HOF_PREVIEW && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="font-mono text-[11px] uppercase tracking-widest-2 text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {expanded ? t("leaderboard.hofShowLess") : t("leaderboard.hofShowAll", { n: champs.length })}
        </button>
      )}
    </section>
  );
}

/** Lista de inelegíveis (#15) com o motivo do gate. Oculta quando vazia. */
export function IneligibleCard({ data }: { data: LeaderboardResponse }) {
  const { t } = useTranslation("dashboard");
  if (data.ineligible.length === 0) return null;
  const reason = (code: string | null) => (code ? t(`leaderboard.reason_${code}`, { defaultValue: code }) : "");
  return (
    <section aria-labelledby="ineligible" className="space-y-2">
      <h3 id="ineligible" className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
        {t("leaderboard.ineligibleTitle")}
      </h3>
      <div className="overflow-hidden rounded-xl border border-border/40 bg-card/30">
        {data.ineligible.map((e) => (
          <div
            key={e.user_id}
            className="flex items-center justify-between border-t border-border/30 px-4 py-2 first:border-t-0"
          >
            <span className="truncate text-sm text-muted-foreground">{e.display_name}</span>
            <span className="shrink-0 font-mono text-[10px] text-amber-400/80">{reason(e.reason)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
