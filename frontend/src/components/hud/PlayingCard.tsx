import { cn } from "@/lib/utils";

type Suit = "s" | "h" | "d" | "c";
export interface CardData {
  rank: string; // A K Q J T 9 8 ...
  suit: Suit;
}

const suitGlyph: Record<Suit, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
const suitColor: Record<Suit, string> = {
  s: "text-[hsl(var(--card-suit-dark))]",
  c: "text-[hsl(var(--card-suit-dark))]",
  h: "text-[hsl(var(--card-suit-red))]",
  d: "text-[hsl(var(--card-suit-red))]",
};

export function PlayingCard({
  card,
  size = "md",
  hidden,
}: {
  card?: CardData;
  size?: "sm" | "md" | "lg";
  hidden?: boolean;
}) {
  const sz =
    size === "sm" ? "h-10 w-7 text-sm" : size === "lg" ? "h-20 w-14 text-2xl" : "h-14 w-10 text-lg";

  if (hidden || !card) {
    return (
      <div
        className={cn(
          "rounded-md border border-primary/30 bg-gradient-to-br from-hud-elevated to-background ring-1 ring-inset ring-primary/10",
          sz
        )}
        aria-hidden
      >
        <div className="h-full w-full rounded-[inherit] bg-[radial-gradient(circle_at_30%_30%,hsl(var(--primary)/0.2),transparent_60%)]" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-md border border-border bg-[hsl(var(--card-face))] font-bold leading-none shadow-lg",
        sz,
        suitColor[card.suit]
      )}
      role="img"
      aria-label={`${card.rank}${suitGlyph[card.suit]}`}
    >
      <span className="font-mono">{card.rank}</span>
      <span className="text-[1.1em]">{suitGlyph[card.suit]}</span>
    </div>
  );
}
