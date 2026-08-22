import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface Props {
  content: string;
  className?: string;
}

export function HudTooltip({ content, className }: Props) {
  const { t } = useTranslation("dashboard");
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn("inline-flex items-center text-muted-foreground/50 hover:text-muted-foreground transition-colors focus-visible:outline-none", className)}
            aria-label={t("infoAria")}
          >
            <Info className="size-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[220px] text-xs leading-relaxed">
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
