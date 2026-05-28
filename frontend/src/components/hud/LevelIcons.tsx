import { cn } from "@/lib/utils";

interface IconProps {
  className?: string;
  size?: number;
}

const base = {
  fill: "none" as const,
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  stroke: "currentColor" as const,
};

// ── Set v2 (2026-05-28) — ícones mais refinados, progressão visual de
// "broto → coroa". Cada nível tem um motivo próprio com detalhe preenchido
// pra dar personalidade vs os traços simples anteriores. ──────────────────

// Iniciante — broto/semente saindo do chão (começo da jornada)
export function IconIniciante({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <path d="M12 21v-7" />
      <path d="M12 14c0-2.5-2-4.5-5-4.5 0 3 2 5 5 4.5z" fill="currentColor" fillOpacity="0.12" />
      <path d="M12 12.5c0-2.8 2.2-5 5-5 0 3.2-2.2 5.3-5 5z" fill="currentColor" fillOpacity="0.18" />
      <line x1="7" y1="21" x2="17" y2="21" />
    </svg>
  );
}

// Estudante — birrete de formatura
export function IconEstudante({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <path d="M2 9l10-4 10 4-10 4-10-4z" fill="currentColor" fillOpacity="0.12" />
      <path d="M6 11v4c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-4" />
      <line x1="22" y1="9" x2="22" y2="13" />
      <circle cx="22" cy="14" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

// Grinder — pilha de fichas (alto volume de jogo)
export function IconGrinder({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      {/* três fichas empilhadas (elipses) */}
      <ellipse cx="12" cy="17" rx="7" ry="2.4" fill="currentColor" fillOpacity="0.16" />
      <ellipse cx="12" cy="13.5" rx="7" ry="2.4" fill="currentColor" fillOpacity="0.12" />
      <ellipse cx="12" cy="10" rx="7" ry="2.4" fill="currentColor" fillOpacity="0.08" />
      {/* laterais da pilha conectando topo e base */}
      <path d="M5 10v7" />
      <path d="M19 10v7" />
    </svg>
  );
}

// Regular — gráfico ascendente com seta (progresso consistente)
export function IconRegular({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <polyline points="3 17 9 11 13 14 21 6" />
      <polyline points="21 11 21 6 16 6" />
      <line x1="3" y1="21" x2="21" y2="21" strokeOpacity="0.4" />
    </svg>
  );
}

// Sólido — escudo reforçado com checkmark
export function IconSolido({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <path d="M12 22s8-4 8-10.5V5.5l-8-3-8 3v6C4 18 12 22 12 22z" fill="currentColor" fillOpacity="0.1" />
      <polyline points="8.5 12 11 14.5 15.5 9.5" />
    </svg>
  );
}

// Expert — naipe de espada (símbolo clássico de maestria no poker)
export function IconExpert({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <path d="M12 3C9 7 5 9.5 5 13a3.4 3.4 0 0 0 5.5 2.7c-.2 1.6-.9 2.8-2 3.8h7c-1.1-1-1.8-2.2-2-3.8A3.4 3.4 0 0 0 19 13c0-3.5-4-6-7-10z"
            fill="currentColor" fillOpacity="0.14" />
    </svg>
  );
}

// Elite — coroa ornamentada com joias
export function IconElite({ className, size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base}>
      <path d="M3 18l1.2-9 4.3 4L12 6l3.5 7 4.3-4L21 18z" fill="currentColor" fillOpacity="0.14" />
      <line x1="3" y1="18" x2="21" y2="18" />
      <line x1="3" y1="20.5" x2="21" y2="20.5" />
      <circle cx="4.5" cy="9"  r="1.1" fill="currentColor" stroke="none" />
      <circle cx="12"  cy="6"  r="1.2" fill="currentColor" stroke="none" />
      <circle cx="19.5" cy="9" r="1.1" fill="currentColor" stroke="none" />
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
