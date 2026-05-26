/**
 * Paleta canônica de cores por ação. Use ACTION_COLORS em qualquer widget
 * que represente ação visualmente (barras de freq, range grid, badges, etc).
 *
 * Convenção:
 *   - Fold:  zinc-500 (cinza-azulado neutro, contrasta com fundo dark)
 *   - Check: sky-400 (azul claro — ação passiva sem investir fichas)
 *   - Call:  blue-500 (azul — comprometeu mas passivo)
 *   - Bet:   emerald-500 (verde — agressão inicial)
 *   - Raise: emerald-600 (verde escuro — agressão sobre aposta)
 *   - Allin: red-500 (vermelho — máxima agressão)
 */
export const ACTION_COLORS = {
  fold:  "#71717a",  // zinc-500
  check: "#38bdf8",  // sky-400
  call:  "#3b82f6",  // blue-500
  bet:   "#10b981",  // emerald-500
  raise: "#059669",  // emerald-600
  allin: "#ef4444",  // red-500
} as const;

export type ActionKey = keyof typeof ACTION_COLORS;

// Versão Tailwind classes — quando precisar de bg-/text-/ring-
export const ACTION_TW = {
  fold:  { bg: "bg-zinc-500",     text: "text-zinc-400",    ring: "ring-zinc-500/30" },
  check: { bg: "bg-sky-400",      text: "text-sky-300",     ring: "ring-sky-400/30"  },
  call:  { bg: "bg-blue-500",     text: "text-blue-400",    ring: "ring-blue-500/30" },
  bet:   { bg: "bg-emerald-500",  text: "text-emerald-400", ring: "ring-emerald-500/30" },
  raise: { bg: "bg-emerald-600",  text: "text-emerald-400", ring: "ring-emerald-600/30" },
  allin: { bg: "bg-red-500",      text: "text-red-400",     ring: "ring-red-500/30" },
} as const;

/** Normaliza string de ação para a chave canônica. */
export function actionKey(raw: string | null | undefined): ActionKey {
  const s = (raw ?? "").toLowerCase().replace(/[-_ ]/g, "");
  if (s === "fold" || s === "folds") return "fold";
  if (s === "check" || s === "checks") return "check";
  if (s === "call" || s === "calls" || s === "limp") return "call";
  if (s.startsWith("bet")) return "bet";
  if (s.startsWith("raise")) return "raise";
  if (s === "jam" || s === "shove" || s === "allin" || s === "alli") return "allin";
  return "fold"; // fallback seguro
}

export function colorFor(action: string | null | undefined): string {
  return ACTION_COLORS[actionKey(action)];
}
