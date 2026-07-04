import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Award, Zap } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { metrics, leaderboardPrefs, LeaderboardResponse, LeaderboardPrefs } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/hooks/use-mobile";
import { SkillLeague } from "@/components/leaderboard/SkillLeague";
import { EffortLeague } from "@/components/leaderboard/EffortLeague";
import { LeagueSkeleton } from "@/components/leaderboard/shared";
import {
  ParticipationBar,
  HallOfFameCard,
  IneligibleCard,
} from "@/components/leaderboard/secondary";

type Axis = "skill" | "effort";

/** Segmented control (mobile) que alterna entre os dois eixos: skill × esforço. */
function AxisTabs({ value, onChange }: { value: Axis; onChange: (a: Axis) => void }) {
  const { t } = useTranslation("dashboard");
  const tabs: { id: Axis; label: string; icon: typeof Award }[] = [
    { id: "skill", label: t("leaderboard.axisSkill"), icon: Award },
    { id: "effort", label: t("leaderboard.axisEffort"), icon: Zap },
  ];
  return (
    <div role="tablist" aria-label={t("leaderboard.title")} className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-hud-surface p-1">
      {tabs.map(({ id, label, icon: Icon }) => {
        const active = value === id;
        return (
          <button
            key={id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(id)}
            className={cn(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-widest-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {label}
          </button>
        );
      })}
    </div>
  );
}

function Body({
  data,
  prefs,
  onSaved,
}: {
  data: LeaderboardResponse;
  prefs: LeaderboardPrefs | null;
  onSaved: () => void;
}) {
  const isMobile = useIsMobile();
  const [axis, setAxis] = useState<Axis>("skill");

  return (
    <div className="space-y-6">
      {/* Participação compacta: governa os DOIS rankings. Contexto, no topo. */}
      {prefs && <ParticipationBar prefs={prefs} onSaved={onSaved} />}

      {/* Os dois eixos são as estrelas. Desktop = lado a lado; mobile = tabs. */}
      {isMobile ? (
        <div className="space-y-4">
          <AxisTabs value={axis} onChange={setAxis} />
          <div role="tabpanel">
            {axis === "skill" ? <SkillLeague data={data} /> : <EffortLeague />}
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <SkillLeague data={data} />
          <EffortLeague />
        </div>
      )}

      {/* Secundário (baixo destaque): campeões · inelegíveis. */}
      <div className="grid gap-4 border-t border-border/40 pt-6 md:grid-cols-2">
        <HallOfFameCard />
        <IneligibleCard data={data} />
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
    metrics
      .leaderboard()
      .then(setData)
      .catch((e) => setError(String(e?.message ?? e)));

  useEffect(() => {
    Promise.all([loadData(), leaderboardPrefs.get().then(setPrefs).catch(() => {})]).finally(() =>
      setLoading(false)
    );
  }, []);

  return (
    <HudLayout
      eyebrow={t("leaderboard.eyebrow")}
      title={t("leaderboard.title")}
      description={t("leaderboard.description")}
    >
      {loading && (
        <div className="grid gap-6 lg:grid-cols-2">
          <LeagueSkeleton />
          <LeagueSkeleton />
        </div>
      )}
      {error && (
        <div className="py-12 text-center text-sm text-destructive" role="alert">
          {error}
        </div>
      )}
      {!loading && data && <Body data={data} prefs={prefs} onSaved={loadData} />}
    </HudLayout>
  );
}
