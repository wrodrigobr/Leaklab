import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Calculator,
  ChevronRight,
  Layers,
  Lock,
  Shield,
  Sigma,
  Target,
  TrendingUp,
  Brain,
  Users,
  Hash,
  Ban,
  Eye,
  Crosshair,
  Coins,
  Scale,
  Zap,
  Waves,
  Swords,
  Flame,
  BookText,
  Wallet,
  Sword,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

type ModuleStatus = "available" | "coming_soon";
type Level = "beginner" | "intermediate" | "advanced";

interface Module {
  id: string;
  icon: React.ElementType;
  color: string;
  path?: string;
  status: ModuleStatus;
  level: Level;
  xpReward: number;
}

// ── Module registry ───────────────────────────────────────────────────────────

const MODULES: Module[] = [
  // Beginner
  {
    id: "terms",
    icon: BookText,
    color: "emerald",
    path: "/academy/terms",
    status: "available",
    level: "beginner",
    xpReward: 15,
  },
  {
    id: "math",
    icon: Calculator,
    color: "emerald",
    path: "/academy/math",
    status: "available",
    level: "beginner",
    xpReward: 15,
  },
  {
    id: "board_strength",
    icon: Layers,
    color: "emerald",
    path: "/academy/board-strength",
    status: "available",
    level: "beginner",
    xpReward: 20,
  },
  {
    id: "showdown",
    icon: Eye,
    color: "emerald",
    path: "/academy/showdown",
    status: "available",
    level: "beginner",
    xpReward: 15,
  },
  {
    id: "position",
    icon: Target,
    color: "emerald",
    path: "/academy/position",
    status: "available",
    level: "beginner",
    xpReward: 15,
  },
  // Intermediate
  {
    id: "math_intermediate",
    icon: Sigma,
    color: "amber",
    path: "/academy/math/intermediate",
    status: "available",
    level: "intermediate",
    xpReward: 20,
  },
  {
    id: "ranges",
    icon: Shield,
    color: "emerald",
    path: "/academy/gto-preflop?scenario=rfi",
    status: "available",
    level: "beginner",
    xpReward: 20,
  },
  {
    id: "bet_sizing",
    icon: BookOpen,
    color: "amber",
    path: "/academy/bet-sizing",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "pushfold",
    icon: Zap,
    color: "amber",
    path: "/academy/push-fold",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "postflop",
    icon: Layers,
    color: "amber",
    path: "/academy/postflop",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "draws",
    icon: Waves,
    color: "amber",
    path: "/academy/draws",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "threebet",
    icon: Swords,
    color: "amber",
    path: "/academy/3bet",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "barrels",
    icon: Flame,
    color: "amber",
    path: "/academy/barrels",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "bankroll",
    icon: Wallet,
    color: "amber",
    path: "/academy/bankroll",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "bvb",
    icon: Sword,
    color: "amber",
    path: "/academy/blind-war",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  // Advanced
  {
    id: "tournament",
    icon: Brain,
    color: "rose",
    path: "/academy/tournament",
    status: "available",
    level: "advanced",
    xpReward: 25,
  },
  {
    id: "ranges_advanced",
    icon: TrendingUp,
    color: "rose",
    path: "/academy/gto-preflop?scenario=mixed",
    status: "available",
    level: "advanced",
    xpReward: 30,
  },
  {
    id: "multiway",
    icon: Users,
    color: "rose",
    path: "/academy/multiway",
    status: "available",
    level: "advanced",
    xpReward: 25,
  },
  {
    id: "icm",
    icon: Brain,
    color: "rose",
    path: "/academy/icm",
    status: "available",
    level: "advanced",
    xpReward: 25,
  },
  {
    id: "exploits",
    icon: Crosshair,
    color: "rose",
    path: "/academy/exploits",
    status: "available",
    level: "advanced",
    xpReward: 25,
  },
  {
    id: "pko",
    icon: Coins,
    color: "rose",
    path: "/academy/pko",
    status: "available",
    level: "advanced",
    xpReward: 25,
  },
  {
    id: "imbalances",
    icon: Scale,
    color: "rose",
    path: "/academy/imbalances",
    status: "available",
    level: "advanced",
    xpReward: 30,
  },
  {
    id: "mdf",
    icon: Sigma,
    color: "amber",
    path: "/academy/mdf",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "combos",
    icon: Hash,
    color: "amber",
    path: "/academy/combos",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
  {
    id: "blockers",
    icon: Ban,
    color: "amber",
    path: "/academy/blockers",
    status: "available",
    level: "intermediate",
    xpReward: 25,
  },
];

// ── Module card ───────────────────────────────────────────────────────────────

function ModuleCard({ mod }: { mod: Module }) {
  const { t } = useTranslation("academy");
  const Icon      = mod.icon;
  const available = mod.status === "available";
  const color     = mod.color;

  const colorMap: Record<string, { ring: string; bg: string; icon: string; badge: string }> = {
    emerald: {
      ring:  "ring-emerald-500/30 border-emerald-500/20",
      bg:    "bg-emerald-500/5",
      icon:  "bg-emerald-500/10 ring-emerald-500/30 text-emerald-400",
      badge: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20",
    },
    amber: {
      ring:  "ring-amber-500/30 border-amber-500/20",
      bg:    "bg-amber-500/5",
      icon:  "bg-amber-500/10 ring-amber-500/30 text-amber-400",
      badge: "bg-amber-500/10 text-amber-400 ring-amber-500/20",
    },
    rose: {
      ring:  "ring-rose-500/30 border-rose-500/20",
      bg:    "bg-rose-500/5",
      icon:  "bg-rose-500/10 ring-rose-500/30 text-rose-400",
      badge: "bg-rose-500/10 text-rose-400 ring-rose-500/20",
    },
  };
  const c = colorMap[color] ?? colorMap.emerald;

  const inner = (
    <div className={cn(
      "group flex flex-col rounded-xl border overflow-hidden transition-all",
      available
        ? `${c.ring} ${c.bg} hover:ring-1 cursor-pointer`
        : "border-border bg-hud-surface/40 opacity-60",
    )}>
      <div className="flex-1 p-5 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className={cn("flex size-10 items-center justify-center rounded-lg ring-1", available ? c.icon : "bg-muted/20 ring-border text-muted-foreground")}>
            {available ? <Icon className="size-4" aria-hidden /> : <Lock className="size-4" aria-hidden />}
          </div>
          <span className={cn(
            "font-mono text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full ring-1",
            available ? c.badge : "bg-muted/10 text-muted-foreground/60 ring-border",
          )}>
            {available ? `+${mod.xpReward} XP` : t("comingSoon")}
          </span>
        </div>

        <div>
          <h3 className="text-sm font-bold text-foreground">{t(`modules.${mod.id}.title`)}</h3>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
            {t(`modules.${mod.id}.desc`)}
          </p>
        </div>
      </div>

      {available && (
        <div className={cn("border-t px-5 py-3 flex items-center justify-between", `border-${color}-500/20`)}>
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {t("startDrill")}
          </span>
          <ChevronRight className={cn("size-4 transition-transform group-hover:translate-x-0.5", `text-${color}-400`)} aria-hidden />
        </div>
      )}
    </div>
  );

  return available && mod.path ? (
    <Link to={mod.path}>{inner}</Link>
  ) : (
    <div>{inner}</div>
  );
}

// ── Level section ─────────────────────────────────────────────────────────────

function LevelSection({ level, modules }: { level: Level; modules: Module[] }) {
  const { t } = useTranslation("academy");

  const badgeColors: Record<Level, string> = {
    beginner:     "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20",
    intermediate: "bg-amber-500/10   text-amber-400   ring-amber-500/20",
    advanced:     "bg-rose-500/10    text-rose-400    ring-rose-500/20",
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <span className={cn(
          "font-mono text-[9px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full ring-1",
          badgeColors[level],
        )}>
          {t(`levels.${level}`)}
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {modules.map((m) => <ModuleCard key={m.id} mod={m} />)}
      </div>
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Academy() {
  const { t } = useTranslation("academy");
  const levels: Level[] = ["beginner", "intermediate", "advanced"];

  return (
    <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}>
      <div className="mx-auto max-w-5xl space-y-10">
        {levels.map((level) => {
          const mods = MODULES.filter((m) => m.level === level);
          if (!mods.length) return null;
          return <LevelSection key={level} level={level} modules={mods} />;
        })}
      </div>
    </HudLayout>
  );
}
