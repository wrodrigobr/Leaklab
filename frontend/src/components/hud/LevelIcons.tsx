import { cn } from "@/lib/utils";

interface IconProps {
  className?: string;
  size?: number;
}

const base = {
  fill: "none" as const,
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  stroke: "currentColor" as const,
};

// Iniciante — playing card com um pip central
export function IconIniciante({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
      {/* corner pips */}
      <line x1="8" y1="6.5" x2="8.01" y2="6.5" strokeWidth="2" />
      <line x1="16" y1="17.5" x2="16.01" y2="17.5" strokeWidth="2" />
    </svg>
  );
}

// Estudante — duas cartas sobrepostas em ângulo
export function IconEstudante({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      {/* carta de trás */}
      <rect x="8" y="5" width="11" height="15" rx="2" />
      {/* carta da frente */}
      <rect x="5" y="4" width="11" height="15" rx="2" fill="currentColor" fillOpacity="0.08" />
      {/* linhas de conteúdo */}
      <line x1="8" y1="9"  x2="13" y2="9"  />
      <line x1="8" y1="12" x2="13" y2="12" />
      <line x1="8" y1="15" x2="11" y2="15" />
    </svg>
  );
}

// Grinder — relógio (volume/tempo de estudo)
export function IconGrinder({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <circle cx="12" cy="12" r="9.5" />
      <polyline points="12 6.5 12 12 15.5 14" />
      {/* marcas de hora */}
      <line x1="12" y1="3"    x2="12" y2="4.5"  />
      <line x1="12" y1="19.5" x2="12" y2="21"   />
      <line x1="3"  y1="12"   x2="4.5"  y2="12" />
      <line x1="19.5" y1="12" x2="21"   y2="12" />
    </svg>
  );
}

// Regular — ficha de poker com 4 entalhes nos eixos
export function IconRegular({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5.5" />
      {/* entalhes */}
      <line x1="12" y1="3"    x2="12" y2="6.5"  />
      <line x1="12" y1="17.5" x2="12" y2="21"   />
      <line x1="3"  y1="12"   x2="6.5"  y2="12" />
      <line x1="17.5" y1="12" x2="21"   y2="12" />
    </svg>
  );
}

// Sólido — escudo com checkmark
export function IconSolido({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <path d="M12 22s8-4 8-10.5V5.5l-8-3-8 3v6C4 18 12 22 12 22z" />
      <polyline points="9 12 11 14.5 15.5 9.5" />
    </svg>
  );
}

// Expert — estrela de 5 pontas
export function IconExpert({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

// Elite — coroa com 5 pontos e base
export function IconElite({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      {/* corpo da coroa */}
      <path d="M3 20L3 14.5L6.5 10L12 14.5L17.5 10L21 14.5L21 20Z" />
      {/* base */}
      <line x1="3" y1="20" x2="21" y2="20" />
      {/* joias nos picos */}
      <circle cx="6.5"  cy="10" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12"   cy="8"  r="1.5" fill="currentColor" stroke="none" />
      <circle cx="17.5" cy="10" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

export const LEVEL_ICONS: Record<string, React.ComponentType<IconProps>> = {
  "Iniciante": IconIniciante,
  "Estudante": IconEstudante,
  "Grinder":   IconGrinder,
  "Regular":   IconRegular,
  "Sólido":    IconSolido,
  "Expert":    IconExpert,
  "Elite":     IconElite,
};
