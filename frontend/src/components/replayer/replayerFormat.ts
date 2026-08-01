import { type CardData } from "@/components/hud/PlayingCard";

/**
 * Formatação compartilhada entre a página do Replayer e o painel de análise (`SidePanels`).
 *
 * Os três viviam no topo de `Replayer.tsx`. Quando o painel virou arquivo próprio — para que o
 * exemplo da landing use o MESMO componente que renderiza a análise real — os dois passaram a
 * precisar deles, e página importando de componente (ou o contrário) fecharia um ciclo.
 */

export function parseCard(raw: string): CardData {
  return {
    rank: raw.slice(0, -1) as CardData["rank"],
    suit: raw.slice(-1).toLowerCase() as CardData["suit"],
  };
}

export function parseCards(arr: string[]): CardData[] {
  return arr.map(parseCard);
}

/**
 * NÃO é o mesmo que `formatAction` de `@/lib/utils`, e a diferença é de propósito: esta entende
 * sizing (`bet_50pct` → "Bet 50%", `raise_75pct` → "Raise 75%"), que só o Replayer exibe. A de
 * `utils` normaliza separadores e resolveria `bet_50pct` como "Bet_50pct".
 *
 * Unificar as duas é possível, mas é mudança de comportamento em duas telas — não cabia na
 * mudança que apenas MOVEU este código de lugar.
 */
export function fmtAction(a: string): string {
  if (!a) return a;
  const s = a.toLowerCase();
  if (s === "fold")    return "Fold";
  if (s === "call")    return "Call";
  if (s === "check")   return "Check";
  if (s === "allin" || s === "all-in" || s === "shove" || s === "jam") return "Shove";
  if (s === "bet")     return "Bet";
  if (s === "raise")   return "Raise";
  if (s.startsWith("bet_"))   return `Bet ${s.replace("bet_", "").replace("pct", "%")}`;
  if (s.startsWith("raise_")) return `Raise ${s.replace("raise_", "").replace("pct", "%")}`;
  return a.toUpperCase();
}
