import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useTranslation } from "react-i18next";

const META = {
  // Player's action falls in 30-60% frequency bucket
  gto_mixed: {
    labelKey: "gtoMixed.misto.label",
    cls: "text-sky-400 ring-sky-500/30 bg-sky-500/8",
    tooltipKey: "gtoMixed.misto.tooltip",
  },
  // Player's action falls in 10-30% frequency bucket
  gto_minor_deviation: {
    labelKey: "gtoMixed.defensavel.label",
    cls: "text-amber-400 ring-amber-500/30 bg-amber-500/8",
    tooltipKey: "gtoMixed.defensavel.tooltip",
  },
  // The spot itself has a mixed strategy (≥2 actions with ≥10%), regardless of what was played
  spot_mixed: {
    labelKey: "gtoMixed.spotMisto.label",
    cls: "text-sky-400/80 ring-sky-500/25 bg-sky-500/5",
    tooltipKey: "gtoMixed.spotMisto.tooltip",
  },
} as const;

type GtoMixedLabel = keyof typeof META;

interface Props {
  label: GtoMixedLabel;
  size?: "xs" | "sm";
}

export function GtoMixedBadge({ label, size = "sm" }: Props) {
  const { t } = useTranslation("replayer");
  const m = META[label];
  if (!m) return null;
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-md font-mono font-semibold ring-1 cursor-help select-none shrink-0",
              size === "xs" ? "px-1.5 py-0.5 text-[8px]" : "px-2 py-0.5 text-[9px]",
              m.cls,
            )}
          >
            ◎ {t(m.labelKey)}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[260px] text-xs leading-relaxed">
          {t(m.tooltipKey)}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export type { GtoMixedLabel };
