// Identidade GrindLab (marca): teal, light, bg escuro. Headings Chakra Petch.
export const THEME = {
  teal: "#2DD4BF",
  light: "#E3E8EC",
  bg: "#0A0E1A",
  bgPanel: "#111726",
  muted: "#8A94A6",
  amber: "#F5C542",
  sky: "#5AD1FF",
  red: "#F87171",
  heading: "'Chakra Petch', 'Segoe UI', sans-serif",
  body: "'Inter', 'Segoe UI', sans-serif",
  mono: "'JetBrains Mono', 'Consolas', monospace",
};

export const RANKS = "AKQJT98765432".split("");

// Constrói o tipo de mão canônico da célula (i=linha rank alto, j=coluna rank baixo).
export function handAt(i: number, j: number): string {
  const hi = RANKS[i], lo = RANKS[j];
  if (i === j) return hi + hi; // par
  if (i < j) return hi + lo + "s"; // suited (acima da diagonal)
  return lo + hi + "o"; // offsuit (abaixo)
}
