import { useId } from "react";
import { cn } from "@/lib/utils";
import { TIER_COLORS, type MedalTier } from "@/lib/medalTiers";

/**
 * AchievementMedal — a medalha de uma conquista de treino.
 *
 * ── O bug da referência que motivou reescrever, e não copiar ──────────────────────────────────
 *
 * O componente de referência dava `id` único a três dos quatro gradientes (`metal-`, `core-`,
 * `sheen-`) e deixava o quarto fixo: `id="engrave"`. `id` em SVG é **global do documento**, não do
 * componente. Numa grade de 12 medalhas existem 12 elementos com o mesmo id, e todo
 * `url(#engrave)` resolve para o PRIMEIRO do DOM: os 12 emblemas saem pintados com as cores da
 * primeira medalha, independentemente do tier dela.
 *
 * O `uid` da referência (`tier-emblem-locked`) também não resolvia: duas conquistas de mesmo tier
 * e mesmo emblema colidem. Aqui o id vem de `useId()`, que o React garante único por instância.
 *
 * ── Legibilidade do emblema ───────────────────────────────────────────────────────────────────
 *
 * Na referência o emblema era pintado com um gradiente `light → deep` sobre um núcleo quase preto,
 * e o brilho especular era desenhado DEPOIS dele, lavando o canto superior esquerdo. Bronze e ouro
 * ficavam difíceis de ler a 56px — a mesma família do problema de legibilidade do sufixo s/o.
 *
 * Aqui: o emblema usa o tom CLARO cheio (sem gradiente que escureça o desenho), e o brilho vai
 * ANTES dele, então nada cobre o traço.
 */

export const MEDAL_EMBLEMS = [
  "spade", "heart", "diamond", "club", "chip", "streak",
  "range", "bluff", "shield", "bankroll", "clock", "crown",
] as const;
export type MedalEmblem = (typeof MEDAL_EMBLEMS)[number];

function Emblem({ emblem, color }: { emblem: MedalEmblem; color: string }) {
  const line = {
    fill: "none",
    stroke: color,
    strokeWidth: 2.1,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (emblem) {
    case "spade":
      return <path d="M24 12c4.5 5 10 8.4 10 13.2 0 3.4-2.6 5.8-5.7 5.8-1.8 0-3.3-.8-4.3-2 .2 2.9 1 5.2 2.4 6.8h-4.8c1.4-1.6 2.2-3.9 2.4-6.8-1 1.2-2.5 2-4.3 2-3.1 0-5.7-2.4-5.7-5.8C14 20.4 19.5 17 24 12Z" fill={color} />;
    case "heart":
      return <path d="M24 35c-7-4.6-11-8.6-11-13.2 0-3.3 2.5-5.8 5.6-5.8 2.3 0 4.2 1.3 5.4 3.2 1.2-1.9 3.1-3.2 5.4-3.2 3.1 0 5.6 2.5 5.6 5.8C35 26.4 31 30.4 24 35Z" fill={color} />;
    case "diamond":
      return <path d="M24 12 34 24 24 36 14 24Z" fill={color} />;
    case "club":
      return <path d="M24 12a5 5 0 0 1 3.6 8.5A5 5 0 1 1 29 30c-1.3 0-2.5-.5-3.4-1.3.2 2.7 1 4.8 2.3 6.3h-7.8c1.3-1.5 2.1-3.6 2.3-6.3-.9.8-2.1 1.3-3.4 1.3a5 5 0 1 1 1.4-9.5A5 5 0 0 1 24 12Z" fill={color} />;
    case "chip":
      return (
        <g>
          <circle cx="24" cy="24" r="10.5" {...line} />
          <circle cx="24" cy="24" r="5" {...line} />
          <path d="M24 13.5v3.5M24 31v3.5M13.5 24H17M31 24h3.5" {...line} />
        </g>
      );
    case "streak":
      return <path d="M24 11c1.5 5.4 6.5 6.9 6.5 12.7A6.5 6.5 0 0 1 24 30.2a6.5 6.5 0 0 1-6.5-6.5c0-3 1.6-4.4 2.8-6.4.6 1.6 1.6 2.5 2.6 2.8-.6-3 .3-6.3 1.1-9.1Z" fill={color} />;
    case "range":
      return (
        <g {...line}>
          <rect x="13.5" y="13.5" width="21" height="21" rx="2.5" />
          <path d="M20.5 13.5v21M27.5 13.5v21M13.5 20.5h21M13.5 27.5h21" />
        </g>
      );
    case "bluff":
      return (
        <g {...line}>
          <path d="M12.5 24s4.6-7 11.5-7 11.5 7 11.5 7-4.6 7-11.5 7-11.5-7-11.5-7Z" />
          <circle cx="24" cy="24" r="3.2" />
        </g>
      );
    case "shield":
      return (
        <g {...line}>
          <path d="M24 12.5 33 16v7.4c0 5.5-3.7 9.6-9 12.1-5.3-2.5-9-6.6-9-12.1V16Z" />
          <path d="m20.3 23.8 2.9 3 4.6-5.2" />
        </g>
      );
    case "bankroll":
      return (
        <g {...line}>
          <path d="M14 30.5V18M20 30.5V15M26 30.5v-8M32 30.5V12" />
          <path d="M12.5 34.5h23" />
        </g>
      );
    case "clock":
      return (
        <g {...line}>
          <circle cx="24" cy="24" r="10.5" />
          <path d="M24 18v6.4l4 2.6" />
        </g>
      );
    case "crown":
      return <path d="M13.5 31.5 12 16l6.5 5 5.5-8 5.5 8 6.5-5-1.5 15.5Z" fill={color} />;
    default:
      return null;
  }
}

export function AchievementMedal({
  tier,
  emblem,
  locked = false,
  size = 56,
  label,
  className,
}: {
  tier: MedalTier;
  emblem: MedalEmblem;
  locked?: boolean;
  size?: number;
  /** Texto acessível JÁ TRADUZIDO. O componente não monta frase: PT/EN/ES vêm do chamador. */
  label: string;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const { light, deep } = TIER_COLORS[tier];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label={label}
      className={cn("shrink-0", locked && "opacity-40 saturate-[0.15]", className)}
    >
      <title>{label}</title>
      <defs>
        <linearGradient id={`metal-${uid}`} x1="0" y1="0" x2="0.9" y2="1">
          <stop offset="0%" stopColor={light} />
          <stop offset="45%" stopColor={deep} />
          <stop offset="70%" stopColor={light} />
          <stop offset="100%" stopColor={deep} />
        </linearGradient>
        <radialGradient id={`sheen-${uid}`} cx="0.32" cy="0.22" r="0.55">
          <stop offset="0%" stopColor="rgba(255,255,255,0.34)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
      </defs>

      {/* Serrilha de ficha de poker: 12 entalhes. Desenhada ANTES do disco, então só a ponta aparece. */}
      {Array.from({ length: 12 }).map((_, i) => (
        <rect key={i} x="22.6" y="1.4" width="2.8" height="5.4" rx="1.2"
              fill={`url(#metal-${uid})`} transform={`rotate(${i * 30} 24 24)`} />
      ))}

      <circle cx="24" cy="24" r="21" fill={`url(#metal-${uid})`} />
      <circle cx="24" cy="24" r="21" fill="none" stroke={deep} strokeWidth="0.8" />
      <circle cx="24" cy="24" r="17.4" fill="hsl(var(--background))" />
      <circle cx="24" cy="24" r="17.4" fill="none" stroke={light} strokeOpacity="0.55" strokeWidth="1" />

      {/* O brilho vem ANTES do emblema. Na referência vinha depois e lavava o traço. */}
      <ellipse cx="18" cy="15" rx="13" ry="9" fill={`url(#sheen-${uid})`} />

      <Emblem emblem={emblem} color={light} />

      {locked && (
        <g>
          <circle cx="34" cy="34" r="9" fill="hsl(var(--background))" stroke="hsl(var(--border))" />
          <rect x="30.4" y="33.4" width="7.2" height="5.6" rx="1.2" fill="hsl(var(--muted-foreground))" />
          <path d="M31.9 33.4v-1.6a2.1 2.1 0 0 1 4.2 0v1.6" fill="none"
                stroke="hsl(var(--muted-foreground))" strokeWidth="1.5" />
        </g>
      )}
    </svg>
  );
}
