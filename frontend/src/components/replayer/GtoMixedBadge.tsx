import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const META = {
  gto_mixed: {
    label: "GTO Misto",
    cls: "text-sky-400 ring-sky-500/30 bg-sky-500/8",
    tooltip:
      "Estratégia mista — o solver distribui frequência entre múltiplas ações neste spot. " +
      "Sua jogada tem entre 30–60% de frequência no equilíbrio de Nash: é uma linha teoricamente válida. " +
      "Não é um erro; qualquer ação com ≥30% de frequência é considerada equilibrada.",
  },
  gto_minor_deviation: {
    label: "Defensável",
    cls: "text-amber-400 ring-amber-500/30 bg-amber-500/8",
    tooltip:
      "Desvio leve — ação com 10–30% de frequência no equilíbrio do solver. " +
      "Incomum no GTO puro, mas defensável em contextos específicos de range e exploração. " +
      "Prefira a linha de maior frequência para minimizar erros de exploração.",
  },
} as const;

type GtoMixedLabel = keyof typeof META;

interface Props {
  label: GtoMixedLabel;
  size?: "xs" | "sm";
}

export function GtoMixedBadge({ label, size = "sm" }: Props) {
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
            ◎ {m.label}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[260px] text-xs leading-relaxed">
          {m.tooltip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export type { GtoMixedLabel };
