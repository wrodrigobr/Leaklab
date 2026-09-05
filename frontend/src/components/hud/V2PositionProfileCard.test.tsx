// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PlayerStatsResponse, PositionProfileResponse } from "@/lib/api";

/**
 * A grade de perfil por assento, e a linha TOTAL.
 *
 * ── Por que este arquivo existe ──────────────────────────────────────────────────────────
 *
 * A linha Total nasceu de um pedido do dono (05/09): *"faz sentido ter uma linha de
 * totalizador embaixo igual PT4 pro usuário ver que na média cai no valor que é mostrado no
 * HUD principal?"*. Ela existe para PROVAR coerência entre a grade e o número grande da tela,
 * e por isso tem duas regras que um refactor descuidado quebra sem que nada mais falhe:
 *
 * 1. **Ela vem do payload do HUD principal, não é recalculada.** Se alguém "otimizar" isso
 *    para calcular a partir das linhas, cria uma SEGUNDA fonte para a mesma estatística — o
 *    defeito exato que quebrou o HUD do torneio no mesmo dia (68,9% contra 35,37% do PT4).
 * 2. **Não é a média das linhas.** Média simples de percentual entre assentos de volume
 *    diferente dá outro número, e aí a linha mentiria justamente onde deveria provar
 *    coerência. O fixture abaixo é construído para as duas contas DIVERGIREM: se alguém
 *    trocar o agregado pela média, o teste acusa.
 *
 * E a nota de mãos fora da grade: a grade tem 8 assentos, mas o parser também emite
 * MP/MP1/MP2/LJ. Essas mãos não caem em linha nenhuma e sumiam CALADAS — o jogador somava os
 * assentos, não fechava com o Total, e não tinha como saber por quê.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o && "n" in o ? `${k}:${o.n}` : k,
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);

const cel = (value: number) => ({
  value,
  band: "healthy" as const,
  flag: null,
  healthy: [18, 24] as [number, number],
});

/** Dois assentos de volume MUITO diferente, de proposito: a media simples de 20 e 40 e 30,
 *  e o agregado ponderado (900 maos a 20% + 100 a 40%) e 22. Os dois numeros divergem, entao
 *  o teste consegue distinguir qual conta a linha usou. */
const GRADE: PositionProfileResponse = {
  positions: [
    { position: "UTG", hands: 900, stats: { vpip: cel(20) } },
    { position: "BB", hands: 100, stats: { vpip: cel(40) } },
  ],
  total_hands: 1000,
  sempre: ["vpip"],
  com_volume: [],
} as unknown as PositionProfileResponse;

const HUD_PRINCIPAL = {
  total_hands: 1000,
  vpip: 22,
  flags: { vpip: { band: "healthy", flag: null, healthy: [18, 24] } },
} as unknown as PlayerStatsResponse;

describe("linha TOTAL", () => {
  it("mostra o valor do HUD principal, nao a media das linhas", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD_PRINCIPAL} />);
    const linha = screen.getByText("posProfile.total").closest("div")!;
    // 22 = agregado ponderado (o que o HUD grande mostra). 30 seria a media simples.
    expect(within(linha).getByText("22")).toBeTruthy();
    expect(within(linha).queryByText("30")).toBeNull();
  });

  it("nao aparece sem o payload do HUD principal", () => {
    render(<V2PositionProfileCard data={GRADE} />);
    expect(screen.queryByText("posProfile.total")).toBeNull();
  });
});

describe("maos fora da grade", () => {
  it("declara a diferenca quando os assentos nao somam o total", () => {
    // 1013 no HUD, 1000 somando os assentos: 13 maos em MP1, o caso real do acervo.
    const comSobra = { ...HUD_PRINCIPAL, total_hands: 1013 } as PlayerStatsResponse;
    render(<V2PositionProfileCard data={GRADE} geral={comSobra} />);
    expect(screen.getByText("posProfile.outsideGrid:13")).toBeTruthy();
  });

  it("fica calada quando os assentos fecham com o total", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD_PRINCIPAL} />);
    expect(screen.queryByText(/posProfile\.outsideGrid/)).toBeNull();
  });
});
