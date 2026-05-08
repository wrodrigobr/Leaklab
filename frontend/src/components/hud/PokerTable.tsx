import { PlayingCard, type CardData } from "./PlayingCard";
import { cn } from "@/lib/utils";

export interface Seat {
  id:       number;
  name:     string;
  stack:    number;
  hero?:    boolean;
  folded?:  boolean;
  active?:  boolean;
  winner?:  boolean;
  bet?:     number;
  cards?:   CardData[];
  revealed?: boolean; // true on showdown — show villain cards face-up
}

interface Props {
  seats:       Seat[];
  community:   CardData[];
  pot:         number;
  street:      string;
  bb?:         number;
  betUnit?:    "chips" | "bb";
}

// ── Geometry ──────────────────────────────────────────────────────────────────

const CENTER = { x: 50, y: 50 };

const seatPositions = (count: number) =>
  Array.from({ length: count }).map((_, i) => {
    const angle = (Math.PI * 2 * i) / count + Math.PI / 2;
    return {
      x: CENTER.x + Math.cos(angle) * 42,
      y: CENTER.y + Math.sin(angle) * 38,
    };
  });

// Bet chips are placed 42 % of the way from seat toward table center
function betPosition(sx: number, sy: number, t = 0.42) {
  return {
    x: sx + (CENTER.x - sx) * t,
    y: sy + (CENTER.y - sy) * t,
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

function fmt(amount: number, bb: number, unit: "chips" | "bb") {
  if (unit === "bb") return `${(amount / bb).toFixed(1)} BB`;
  return amount.toLocaleString();
}

export function PokerTable({ seats, community, pot, street, bb = 100, betUnit = "chips" }: Props) {
  const positions = seatPositions(seats.length);

  return (
    <div className="relative aspect-[16/10] w-full overflow-hidden rounded-2xl bg-[#1a0a04] ring-hud shadow-[inset_0_0_0_6px_#3d1a08,inset_0_0_0_8px_#6b2f0f]">
      {/* Rail — wood brown gradient ring */}
      <div className="absolute inset-0 rounded-2xl bg-[radial-gradient(ellipse_at_50%_50%,#5a2510_0%,#2d1005_100%)] opacity-100" />

      {/* Felt */}
      <div className="absolute inset-[10%] rounded-[50%] bg-[radial-gradient(ellipse_at_40%_35%,#2e7d46_0%,#1a5230_100%)] shadow-[inset_0_0_60px_rgba(0,0,0,0.55)]">
        <div className="absolute inset-2 rounded-[50%] border border-white/10" />
        <div className="absolute inset-0 rounded-[50%] bg-[radial-gradient(ellipse_at_center,transparent_38%,rgba(0,0,0,0.42))]" />
      </div>

      {/* Community cards + pot (center) */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-3 z-10">
        <div className="font-mono text-[10px] uppercase tracking-widest-2 text-primary/80">
          {street}
        </div>
        <div className="flex gap-1.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <PlayingCard key={i} card={community[i]} hidden={!community[i]} size="md" />
          ))}
        </div>
        <div className="flex items-center gap-2 rounded-full bg-background/80 px-4 py-1.5 ring-1 ring-primary/20 backdrop-blur-sm">
          <span className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">Pot</span>
          <span className="font-mono text-sm font-bold tabular-nums text-primary">{fmt(pot, bb, betUnit)}</span>
        </div>
      </div>

      {/* Bet chips — positioned between each seat and the pot */}
      {seats.map((seat, i) => {
        if (!seat.bet) return null;
        const { x, y } = positions[i];
        const { x: bx, y: by } = betPosition(x, y);
        return (
          <div
            key={`bet-${seat.id}`}
            className="absolute z-20 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${bx}%`, top: `${by}%` }}
          >
            <div className="rounded-full bg-primary/15 px-2.5 py-0.5 font-mono text-[10px] font-bold tabular-nums text-primary ring-1 ring-primary/30 shadow backdrop-blur-sm whitespace-nowrap">
              {fmt(seat.bet, bb, betUnit)}
            </div>
          </div>
        );
      })}

      {/* Seats */}
      {seats.map((seat, i) => {
        const { x, y } = positions[i];
        return (
          <div
            key={seat.id}
            className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${x}%`, top: `${y}%` }}
          >
            <SeatBubble seat={seat} />
          </div>
        );
      })}
    </div>
  );
}

// ── Seat bubble ───────────────────────────────────────────────────────────────

function SeatBubble({ seat }: { seat: Seat }) {
  const showCards = seat.hero || seat.revealed;
  const cards = seat.cards ?? [];

  return (
    <div className="flex flex-col items-center gap-1.5">
      {/* Cards — shown for hero always, for villains only when revealed (showdown) */}
      {cards.length >= 2 && (
        <div className={cn("flex gap-0.5 transition-opacity", seat.folded && "opacity-30")}>
          <PlayingCard card={cards[0]} size="sm" hidden={!showCards} />
          <PlayingCard card={cards[1]} size="sm" hidden={!showCards} />
        </div>
      )}

      {/* Nameplate */}
      <div className={cn(
        "min-w-[110px] rounded-lg border bg-hud-elevated px-2.5 py-1.5 text-center transition-all",
        seat.winner  && "border-primary ring-2 ring-primary/50 shadow-[0_0_18px_rgba(99,179,132,0.45)]",
        seat.active  && !seat.winner && "border-primary ring-2 ring-primary/40 shadow-glow",
        seat.folded  && !seat.active && !seat.winner && "border-border opacity-50",
        !seat.active && !seat.folded && !seat.winner && "border-border",
        seat.hero    && !seat.winner && "border-primary/50 ring-2 ring-white/40 shadow-[0_0_12px_rgba(255,255,255,0.18)]",
      )}>
        <div className="flex items-center justify-center gap-1.5">
          {seat.hero && (
            <span className="rounded-sm bg-primary/20 px-1 py-0.5 font-mono text-[8px] font-bold uppercase tracking-wider text-primary">
              You
            </span>
          )}
          <span className="truncate text-xs font-semibold text-foreground">{seat.name}</span>
        </div>
        <div className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {seat.stack.toLocaleString()}
        </div>
      </div>
    </div>
  );
}
