import { useState } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// Favicon via serviço do Google (CORS-friendly, sempre responde, tamanho consistente).
// Carregar favicon direto do site é frágil (404/CORS/bloqueio) e o GG não aparecia.
const SITE_DOMAINS: Record<string, string> = {
  pokerstars: "pokerstars.com",
  ggpoker:    "ggpoker.com",
  "888poker": "888poker.com",
  partypoker: "partypoker.com",
  winamax:    "winamax.fr",
  acr:        "americascardroom.eu",
};
const faviconUrl = (key: string): string | undefined => {
  const d = SITE_DOMAINS[key];
  return d ? `https://www.google.com/s2/favicons?domain=${d}&sz=64` : undefined;
};

const DISPLAY_NAMES: Record<string, string> = {
  pokerstars: "PokerStars",
  ggpoker:    "GGPoker",
  "888poker": "888Poker",
  partypoker: "PartyPoker",
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
  const url  = faviconUrl(key);
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
