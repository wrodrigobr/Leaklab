import { useState } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const FAVICON_URLS: Record<string, string> = {
  pokerstars: "https://www.pokerstars.com/favicon.ico",
  ggpoker:    "https://www.ggpoker.com/favicon.ico",
  "888poker": "https://www.888poker.com/favicon.ico",
  winamax:    "https://www.winamax.fr/favicon.ico",
  acr:        "https://www.americascardroom.eu/favicon.ico",
};

const DISPLAY_NAMES: Record<string, string> = {
  pokerstars: "PokerStars",
  ggpoker:    "GGPoker",
  "888poker": "888Poker",
  winamax:    "Winamax",
  acr:        "ACR",
};

function initials(site: string): string {
  return site.slice(0, 2).toUpperCase();
}

interface Props {
  site: string;
  size?: number;
}

export function SiteLogo({ site, size = 16 }: Props) {
  const key  = site.toLowerCase().replace(/\s+/g, "");
  const url  = FAVICON_URLS[key];
  const name = DISPLAY_NAMES[key] ?? site;
  const [failed, setFailed] = useState(false);

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="inline-flex shrink-0 items-center justify-center rounded-sm bg-secondary ring-1 ring-border"
            style={{ width: size + 8, height: size + 8 }}
            aria-label={name}
          >
            {url && !failed ? (
              <img
                src={url}
                alt={name}
                width={size}
                height={size}
                onError={() => setFailed(true)}
                className="rounded-[2px] object-contain"
              />
            ) : (
              <span className="font-mono text-[8px] font-bold uppercase text-muted-foreground leading-none">
                {initials(site)}
              </span>
            )}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="font-mono text-[11px]">
          {name}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
