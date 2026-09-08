// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PositionProfileResponse, PlayerStatsResponse } from "@/lib/api";

/**
 * AY-21: a grade ganha a visao "Agrupado" (EP / MP / CO / BTN / SB / BB) ao lado da "Por
 * assento". O chip chama `onAgrupado`; na grade agrupada cada linha mostra os assentos que o
 * jogador ocupou dentro do grupo. O dado vem do backend; o card nao agrupa nada sozinho.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);

const ok = (value: number) => ({ value, band: "ok" as const });
const HUD = { total_hands: 800, vpip: 25, rfi: 28 } as unknown as PlayerStatsResponse;
const AGRUPADA = {
  positions: [
    { position: "EP", hands: 300, members: ["UTG", "UTG+2"], stats: { vpip: ok(15), rfi: ok(16.7) } },
    { position: "CO", hands: 200, members: ["CO"], stats: { vpip: ok(28), rfi: ok(30) } },
  ],
  total_hands: 500, sempre: ["vpip", "rfi"], com_volume: [], stack_band: null, faixas: ["40+", "20-40", "<20"],
  agrupado: true, grupos: { EP: ["UTG", "UTG+1", "UTG+2"], CO: ["CO"] },
} as unknown as PositionProfileResponse;

describe("grade agrupada", () => {
  it("os chips Por assento / Agrupado chamam onAgrupado, e o ativo e o da prop", () => {
    const onAgrupado = vi.fn();
    render(<V2PositionProfileCard data={AGRUPADA} geral={HUD} agrupado onAgrupado={onAgrupado} />);
    const chips = screen.getByTestId("grade-visao").querySelectorAll("button");
    expect(chips).toHaveLength(2);
    expect(chips[0].textContent).toBe("posProfile.detailed");
    expect(chips[1].textContent).toBe("posProfile.grouped");
    expect(chips[1].getAttribute("aria-pressed")).toBe("true");
    expect(chips[0].getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(chips[0]);
    expect(onAgrupado).toHaveBeenCalledWith(false);
  });

  it("a linha do grupo mostra os assentos ocupados; grupo de um assento so nao repete", () => {
    render(<V2PositionProfileCard data={AGRUPADA} geral={HUD} agrupado onAgrupado={() => {}} />);
    expect(screen.getByTestId("membros-EP").textContent).toBe("UTG · UTG+2");
    expect(screen.queryByTestId("membros-CO")).toBeNull();
    expect(screen.getByTestId("valor-rfi-EP").textContent).toContain("16.7");
  });

  it("sem onAgrupado (o card fora do dashboard) os chips nao aparecem", () => {
    render(<V2PositionProfileCard data={AGRUPADA} geral={HUD} />);
    expect(screen.queryByTestId("grade-visao")).toBeNull();
  });
});
