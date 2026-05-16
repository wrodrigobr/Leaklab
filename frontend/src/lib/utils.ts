import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatAction(a: string): string {
  if (!a) return a;
  if (a.toLowerCase() === "jam") return "Shove";
  return a.charAt(0).toUpperCase() + a.slice(1);
}
