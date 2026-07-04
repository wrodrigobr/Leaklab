import { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Tinta de rank para o pódio (ouro/prata/bronze); demais em muted. */
export const RANK_TINT: Record<number, string> = {
  1: "text-yellow-400",
  2: "text-slate-300",
  3: "text-amber-600",
};

/** Anel do pódio para o número de rank (top-3 destacado). */
const RANK_RING: Record<number, string> = {
  1: "border-yellow-400/50 bg-yellow-400/10",
  2: "border-slate-300/40 bg-slate-300/10",
  3: "border-amber-600/40 bg-amber-600/10",
};

/** Número de rank com destaque de pódio no top-3. */
export function MedalRank({ rank, size = "lg" }: { rank: number; size?: "sm" | "lg" }) {
  const podium = rank >= 1 && rank <= 3;
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-lg border font-mono font-bold tabular-nums",
        size === "lg" ? "size-9 text-lg" : "size-7 text-sm",
        podium ? RANK_RING[rank] : "border-transparent",
        RANK_TINT[rank] ?? "text-muted-foreground"
      )}
      aria-label={`#${rank}`}
    >
      {rank}
    </span>
  );
}

/** Cabeçalho de um eixo (skill/esforço): ícone + título + subtítulo do eixo. */
export function AxisHeader({
  id,
  icon,
  title,
  subtitle,
  aside,
}: {
  id?: string;
  icon: ReactNode;
  title: string;
  subtitle: string;
  aside?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {icon}
          <h2 id={id} className="font-heading text-base font-bold text-foreground">
            {title}
          </h2>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </div>
  );
}

/** Texto de estado vazio padronizado dentro de um card. */
export function EmptyLine({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border/50 bg-card/20 px-4 py-8 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

/** Skeleton de carregamento para uma coluna de ranking. */
export function LeagueSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="h-5 w-40 animate-pulse rounded bg-muted/20" />
      <div className="h-16 animate-pulse rounded-xl bg-muted/10" />
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-20 animate-pulse rounded-xl bg-muted/10" />
      ))}
    </div>
  );
}
