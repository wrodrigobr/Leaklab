import { CheckCircle2, Star } from "lucide-react";
import { GtoStrategyAction } from "@/lib/api";
import { cn } from "@/lib/utils";
import { GtoMixedBadge } from "./GtoMixedBadge";
import { ACTION_COLORS, actionKey } from "@/lib/actionColors";

export interface HandStrategyData {
  hand: string;
  actions: { action: string; frequency: number | null; ev_bb: number | null; ev_loss_bb: number | null }[];
}

interface Props {
  strategy: GtoStrategyAction[];
  playedAction?: string | null;
  compact?: boolean;
  /** Fase 3: estratégia da MÃO específica do hero (freq + EV por ação) */
  handStrategy?: HandStrategyData | null;
  handTitle?: string;
  handTip?: string;
}

const SUIT_GLYPH: Record<string, string> = { c: "♣", d: "♦", h: "♥", s: "♠" };

function prettyHand(hand: string): string {
  return (hand || "").replace(/([2-9TJQKA])([cdhs])/gi,
    (_, r: string, s: string) => r.toUpperCase() + (SUIT_GLYPH[s.toLowerCase()] ?? s));
}


function normalizeAction(a: string): string {
  return (a ?? "").toLowerCase().replace(/[-_ ]/g, "");
}

// Base action sem sizing: bet_1.1bb / bet_75pct → "bet", raise_2.5bb → "raise"
function baseAction(action: string, label?: string): string {
  const raw = (label || action || "").trim().toLowerCase();
  const norm = normalizeAction(raw);
  if (norm === "allin" || norm === "allinfold" || norm === "jam" || norm === "shove") return "shove";
  if (norm.startsWith("bet")) return "bet";
  if (norm.startsWith("raise")) return "raise";
  if (norm === "call") return "call";
  if (norm === "fold") return "fold";
  if (norm === "check") return "check";
  return norm;
}

function labelForBase(base: string): string {
  switch (base) {
    case "shove": return "Shove";
    case "bet":   return "Bet";
    case "raise": return "Raise";
    case "call":  return "Call";
    case "fold":  return "Fold";
    case "check": return "Check";
    default:      return base.charAt(0).toUpperCase() + base.slice(1);
  }
}

export function GtoStrategyPanel({ strategy, playedAction, compact, handStrategy, handTitle, handTip }: Props) {
  if (!strategy || strategy.length === 0) return null;

  // Fase 3: agrega a estratégia da MÃO por ação-base (mesma regra das barras da
  // range). EV por base = MAIOR EV entre os sizes (melhor execução da classe).
  const handAgg = (() => {
    const acts = handStrategy?.actions ?? [];
    if (!acts.length) return [] as { action: string; label: string; frequency: number; ev: number | null }[];
    const m = new Map<string, { freq: number; ev: number | null }>();
    for (const r of acts) {
      const b = baseAction(r.action);
      const slot = m.get(b) ?? { freq: 0, ev: null };
      slot.freq += r.frequency || 0;
      if (r.ev_bb != null) slot.ev = slot.ev == null ? r.ev_bb : Math.max(slot.ev, r.ev_bb);
      m.set(b, slot);
    }
    return Array.from(m.entries())
      .map(([base, v]) => ({ action: base, label: labelForBase(base), frequency: v.freq, ev: v.ev }))
      .sort((a, b) => b.frequency - a.frequency);
  })();
  const handBestEv = handAgg.reduce<number | null>(
    (mx, r) => (r.ev != null && (mx == null || r.ev > mx) ? r.ev : mx), null);

  // Agrega por ação-base (bet_1.1bb + bet_2.5bb → "bet" com freq somada)
  const aggMap = new Map<string, { freq: number; evWeighted: number; evTotal: number }>();
  for (const r of strategy) {
    const b = baseAction(r.action, r.label);
    const slot = aggMap.get(b) ?? { freq: 0, evWeighted: 0, evTotal: 0 };
    slot.freq += r.frequency || 0;
    if (r.ev_bb != null) {
      slot.evWeighted += r.ev_bb * (r.frequency || 0);
      slot.evTotal    += r.frequency || 0;
    }
    aggMap.set(b, slot);
  }
  const sorted = Array.from(aggMap.entries())
    .map(([base, v]) => ({
      action: base,
      label: labelForBase(base),
      frequency: v.freq,
      ev_bb: v.evTotal > 0 ? v.evWeighted / v.evTotal : null,
      combos: null,
      exploitability_pct: null,
    }))
    .sort((a, b) => b.frequency - a.frequency);

  // A estratégia EXIBIDA é a da MÃO específica do hero quando existe — nunca o range
  // agregado ao lado. Mostrar "range folda 63%" junto de "sua mão levanta 93%" confunde:
  // o veredito é SEMPRE da mão. O range (`sorted`) só aparece como fallback quando não há
  // tabela por mão (nó postflop sem gto_tree_strategies — raro).
  const usingHand = handAgg.length > 0;
  const primary = usingHand
    ? handAgg.map(r => ({ action: r.action, label: r.label, frequency: r.frequency, ev_bb: r.ev }))
    : sorted;
  const primaryBestEv = usingHand ? handBestEv : (sorted[0]?.ev_bb ?? null);

  const topRow = primary[0];
  const topEv = topRow?.ev_bb ?? null;

  const playedBase = playedAction ? baseAction(playedAction) : null;
  const playedRow = playedBase ? primary.find(r => r.action === playedBase) : null;
  const playedEv = playedRow?.ev_bb ?? null;

  const opportunityCost =
    topEv != null && playedEv != null && topEv > playedEv
      ? topEv - playedEv
      : null;

  return (
    <div className="space-y-2">
      {usingHand && (
        <div className="font-mono text-[8px] uppercase tracking-wide text-teal-300/90" title={handTip}>
          {handTitle || "Sua mão"} · {prettyHand(handStrategy!.hand)}
        </div>
      )}
      {primary.map((row, idx) => {
        const isPlayed = playedBase != null && row.action === playedBase;
        const isTop = idx === 0;
        const isTopAndPlayed = isTop && isPlayed;
        const pct = Math.round(row.frequency * 100);
        const displayLabel = row.label;
        const actColor = ACTION_COLORS[actionKey(row.action)];

        return (
          <div
            key={row.action}
            className={cn(
              "rounded-md px-2 py-1 space-y-0.5 transition-colors border",
              isPlayed ? "border-foreground/40 bg-foreground/5" : "border-transparent",
            )}
          >
            <div className="flex items-center gap-2">
              {/* bar — cor canônica da ação */}
              <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, background: actColor }}
                />
              </div>
              {/* top star — apenas indica ação dominante */}
              {isTop && !compact && (
                <Star className="shrink-0 size-2.5 text-amber-400 fill-amber-400" />
              )}
              {/* label colorido pela ação */}
              <span
                className={cn(
                  "font-mono shrink-0",
                  compact ? "text-[8px]" : "text-[9px]",
                  isTopAndPlayed || isTop || isPlayed ? "font-bold" : ""
                )}
                style={{ color: actColor }}
              >
                {displayLabel}
              </span>
              {/* frequency */}
              <span className={cn(
                "font-mono shrink-0 w-7 text-right",
                compact ? "text-[8px]" : "text-[9px]",
                isTop || isPlayed ? "text-foreground font-semibold" : "text-muted-foreground"
              )}>
                {pct}%
              </span>
              {/* EV/loss da MÃO — só quando exibindo a estratégia da mão (tem EV por ação) */}
              {usingHand && (() => {
                const loss = primaryBestEv != null && row.ev_bb != null ? primaryBestEv - row.ev_bb : null;
                return (
                  <span className={cn(
                    "font-mono shrink-0 w-12 text-right",
                    compact ? "text-[8px]" : "text-[9px]",
                    loss != null && loss > 0.05 ? "text-amber-400/90" : "text-muted-foreground/60"
                  )}>
                    {loss != null && loss > 0.05 ? `−${loss.toFixed(1)}bb` : (row.ev_bb != null ? `${row.ev_bb.toFixed(1)}bb` : "")}
                  </span>
                );
              })()}
              {/* played checkmark */}
              {isPlayed && (
                <CheckCircle2 className={cn(
                  "shrink-0",
                  compact ? "size-2.5" : "size-3"
                )}
                style={{ color: actColor }} />
              )}
            </div>
          </div>
        );
      })}

      {/* Mixed strategy badge — when ≥2 actions have ≥10% frequency.
          Texto "Fold 85% · Raise 15%" removido: redundante com as barras acima. */}
      {primary.filter(r => r.frequency >= 0.10).length >= 2 && (
        <div className="flex items-center gap-2 pt-0.5">
          <GtoMixedBadge label="spot_mixed" size={compact ? "xs" : "sm"} />
        </div>
      )}

      {/* Opportunity cost footer */}
      {opportunityCost != null && opportunityCost > 0.01 && !compact && (
        <p className="font-mono text-[8px] text-amber-400/80 pt-0.5">
          Custo de oportunidade: -{opportunityCost.toFixed(2)} BB vs linha ótima
        </p>
      )}
    </div>
  );
}
