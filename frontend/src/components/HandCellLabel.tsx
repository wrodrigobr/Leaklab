import { cellLabel } from "@/data/ranges";

/**
 * O conteúdo de uma célula da matriz 13x13: o par de cartas e o sufixo `s`/`o`.
 *
 * ── Por que é um componente, e não duas cópias ────────────────────────────────────────────────
 *
 * Vivia duplicado na grade do Replayer e na do treino de memorização, com os mesmos números
 * mágicos copiados. Regra do projeto: rule que aparece em N lugares vira função, senão a segunda
 * cópia envelhece sozinha. Aqui isso já estava acontecendo, com tamanhos diferentes nas duas.
 *
 * ── Por que o sufixo cresceu ──────────────────────────────────────────────────────────────────
 *
 * Ele nasceu propositalmente menor e mais apagado, com a ideia de que o par de cartas é a
 * informação principal e o naipe é a qualificação. A ideia estava certa e a execução não:
 * medido na tela, numa célula de 40px o rank saía a 10px e o sufixo a **7,2px com 70% de
 * opacidade**. Reportado como ilegível, e era. Hierarquia se faz com uma diferença perceptível,
 * não com uma que apaga o texto: 0,85em e opacidade cheia mantêm a distinção e continuam
 * legíveis. O rank também subiu, porque 10px numa célula de 40px sobrava espaço à toa.
 */
export function HandCellLabel({ row, col, hand }: {
  row: number;
  col: number;
  /** A mão já resolvida ("AKs"/"AKo"/"AA"). Pares não têm sufixo. */
  hand: string;
}) {
  const sufixo = hand.endsWith("s") ? "s" : hand.endsWith("o") ? "o" : "";
  return (
    <>
      {cellLabel(row, col)}
      {sufixo && <span className="ml-[0.5px] text-[0.85em] opacity-90">{sufixo}</span>}
    </>
  );
}

/** Tamanho de fonte da célula, compartilhado pelas duas grades. */
export const CLASSE_FONTE_CELULA = "text-[9px] sm:text-[12px]";
