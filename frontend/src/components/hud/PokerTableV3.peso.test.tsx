// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { PokerTableV3 } from "./PokerTableV3";
import type { ReplayStep } from "@/lib/api";

/**
 * O PESO de uma mesa, medido em nós de DOM.
 *
 * ── Por que existe ────────────────────────────────────────────────────────────────────────────
 *
 * O dono, ao aprovar o modo Prática com até 4 mesas: "pode ser que fique pesado visualmente para
 * renderizar as mesas com os nossos padrões atuais, mas vale testarmos". A pergunta se mede, e o
 * palpite seria a pior resposta possível.
 *
 * jsdom não faz layout, então isto NÃO mede pintura nem fps. Mede o que dá para medir aqui: o
 * tamanho da árvore que cada mesa cria, e se quatro mesas custam quatro vezes uma (custo linear)
 * ou mais do que isso (algo compartilhado explodindo).
 *
 * Como guarda permanente, ele trava o crescimento: quem dobrar o número de nós por mesa vai ter
 * de justificar no teste, em vez de descobrir no telefone de um aluno.
 */
afterEach(cleanup);

/** Mesa de 9 assentos no formato que o Prática monta: preflop, blinds postados, um open. */
function step9max(): ReplayStep {
  const POS = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
  const seats: Record<string, { player: string; stack: number; stack_bb: number; pos: string }> = {};
  POS.forEach((pos, i) => {
    seats[String(i + 1)] = {
      player: pos === "HJ" ? "Hero" : pos, stack: 2000, stack_bb: 20, pos,
    };
  });
  return {
    type: "action", street: "preflop",
    seats,
    hero: "Hero", hero_cards: ["Ah", "Kh"], board: [],
    pot: 370, pot_bb: 3.7,
    bets: { "1": 220, "8": 50, "9": 100 },     // UTG abre 2.2, SB 0.5, BB 1
    folded: ["UTG+1", "UTG+2"],
    bb: 100, button: 7, player: "Hero", seat: 5, is_hero: true,
  } as unknown as ReplayStep;
}

function nos(el: HTMLElement): number {
  return el.querySelectorAll("*").length;
}

describe("peso da mesa", () => {
  it("uma mesa de 9 assentos e o custo de quatro", () => {
    const um = render(<PokerTableV3 step={step9max()} hero="Hero" heroCards={["Ah", "Kh"]} bb={100} />);
    const umaMesa = nos(um.container);
    cleanup();

    const quatro = render(
      <div>
        {[0, 1, 2, 3].map((i) => (
          <PokerTableV3 key={i} step={step9max()} hero="Hero" heroCards={["Ah", "Kh"]} bb={100} />
        ))}
      </div>,
    );
    const quatroMesas = nos(quatro.container);

    // O número em si vai para o relatório; o que o guarda trava é o teto por mesa. Uma mesa
    // acima de 400 nós põe 4 mesas perto de 1.600, que é onde o telefone começa a sofrer.
    expect(umaMesa, `uma mesa cria ${umaMesa} nós`).toBeLessThan(400);

    // CUSTO LINEAR: quatro mesas não podem custar mais que quatro vezes uma (com folga de 10%
    // para o contêiner). Se isto falhar, alguma coisa compartilhada está sendo recriada por mesa.
    expect(quatroMesas, `4 mesas = ${quatroMesas} nós, 1 mesa = ${umaMesa}`)
      .toBeLessThanOrEqual(Math.ceil(umaMesa * 4 * 1.1) + 10);

    // e as quatro renderizaram de fato, em vez de uma só ter aparecido
    expect(quatroMesas).toBeGreaterThan(umaMesa * 3);
  });

  it("a mesa nao arma timer nem animacao por instancia", () => {
    // Quatro mesas com um timer cada é o caminho conhecido para a aba esquentar sem nada se
    // mexer na tela. Se algum dia a mesa precisar de animação, ela entra com desligamento.
    const { container } = render(
      <PokerTableV3 step={step9max()} hero="Hero" heroCards={["Ah", "Kh"]} bb={100} />);
    expect(container.querySelectorAll("[class*='animate-']").length).toBe(0);
  });
});
