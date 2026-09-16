import { cn } from "@/lib/utils";

/**
 * A carta de baralho do produto, e o caminho do SVG dela. UM lugar.
 *
 * ── Por que nasceu (16/09) ────────────────────────────────────────────────────────────────────
 *
 * O caminho `/cards/XX.svg` já era montado em dois lugares do app (`LessonKit.deckCardSrc` e
 * `PokerTableV3.CARDS_BASE` + `RANK_FILE`/`SUIT_FILE`), e a lista de mãos do leak seria o
 * terceiro. Regra 5 da casa: a regra que aparece em N lugares vira função antes do N+1, senão a
 * cópia nova envelhece sozinha. O `T` que vira `10` no nome do arquivo é exatamente o tipo de
 * detalhe que uma cópia esquece.
 *
 * ── A ordem das cartas é regra, não enfeite ───────────────────────────────────────────────────
 *
 * `hero_cards` chega do parser na ordem em que a sala escreveu, e a sala escreve na ordem do
 * assento. A lista de leaks mostrava `4dAd`, com o quatro na frente do ás, e o dono notou
 * olhando a tela. Carta alta primeiro é como todo jogador lê uma mão, então `ordenarMao` faz
 * isso num lugar só, e o teste cobre par, suited e offsuit.
 */

const ORDEM = "23456789TJQKA";

/** `"Ah"` → `/cards/AH.svg`; `"Td"` → `/cards/10D.svg` (o baralho não tem arquivo `T`). */
export function cardSrc(code: string): string {
  const rank = code.slice(0, -1).toUpperCase();
  const suit = code.slice(-1).toUpperCase();
  return `/cards/${rank === "T" ? "10" : rank}${suit}.svg`;
}

/**
 * `"4dAd"` → `["Ad", "4d"]`, carta alta primeiro. Devolve `null` quando não são duas cartas:
 * a lista mostra `—` em vez de desenhar carta inventada, que é a regra da casa para célula sem
 * dado (nunca fingir informação).
 */
export function ordenarMao(heroCards: string | null | undefined): [string, string] | null {
  const bruto = (heroCards ?? "").replace(/\s+/g, "");
  if (bruto.length !== 4) return null;
  const a = bruto.slice(0, 2);
  const b = bruto.slice(2, 4);
  const ia = ORDEM.indexOf(a[0].toUpperCase());
  const ib = ORDEM.indexOf(b[0].toUpperCase());
  if (ia < 0 || ib < 0) return null;
  return ia >= ib ? [a, b] : [b, a];
}

export function PlayingCard({ code, className }: { code: string; className?: string }) {
  return (
    <img
      src={cardSrc(code)}
      alt={code}
      className={cn("w-auto rounded-[3px] shadow-md ring-1 ring-black/20", className)}
      draggable={false}
    />
  );
}

/**
 * As duas cartas do herói, na ordem de leitura. `alt` na primeira carrega a mão inteira, para o
 * leitor de tela não anunciar duas cartas soltas.
 */
export function HeroHand({ cards, className, vazio = "—" }: {
  cards: string | null | undefined;
  /** classe das CARTAS (altura); o contêiner já é um flex com folga entre elas */
  className?: string;
  vazio?: string;
}) {
  const par = ordenarMao(cards);
  if (!par) return <span className="text-muted-foreground">{vazio}</span>;
  return (
    <span className="inline-flex items-center gap-[2px]" aria-label={par.join(" ")}>
      <PlayingCard code={par[0]} className={cn("h-6", className)} />
      <PlayingCard code={par[1]} className={cn("h-6", className)} />
    </span>
  );
}
