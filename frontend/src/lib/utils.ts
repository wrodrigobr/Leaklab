import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatAction(a: string): string {
  if (!a) return a;
  const s = a.toLowerCase().replace(/[-_ ]/g, "");
  if (s === "allin" || s === "jam" || s === "shove") return "Shove";
  if (s === "fold")  return "Fold";
  if (s === "call")  return "Call";
  if (s === "check") return "Check";
  if (s === "bet")   return "Bet";
  if (s === "raise") return "Raise";
  return a.charAt(0).toUpperCase() + a.slice(1);
}
