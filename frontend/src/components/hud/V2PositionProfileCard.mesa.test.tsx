// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PositionProfileResponse, PlayerStatsResponse } from "@/lib/api";

/**
 * Seletor de tamanho de mesa (08/09), nascido do report de um fundador: "o UTG abre mais que o
 * UTG+1, deveria ser o inverso". A causa nao era o chart: a LINHA da grade e o rotulo da sala, e
 * somar mesas de tamanhos diferentes junta assentos diferentes (o UTG de 9-max tem 8 atras; o de
 * 6-max, 5). Aqui esta travado o que a TELA faz com isso:
 *   - os chips existem, marcam a mesa que o backend DECLARA ter aplicado e chamam o setter;
 *   - a mesa em vigor viaja para a matriz (o painel pede o MESMO recorte da grade);
 *   - a nota explica o filtro, e muda quando esta em "todas";
 *   - o cabecalho do solver mostra o range do CENARIO, nao a media nas maos que cairam;
 *   - amostra pequena esconde o numero do JOGADOR e mantem o do solver.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));
const hands = vi.fn();
const detail = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, metrics: { ...real.metrics, playerStatsByPositionHands: (...a: unknown[]) => hands(...a), playerStatsByPositionDetail: (...a: unknown[]) => detail(...a) } };
});
afterEach(cleanup);
vi.setConfig({ testTimeout: 30000 });

const MATRIZ = {
  position: "UTG", stack_band: "40+", mesa: "8max", n: 1161, voce_pct: 16.0,
  solver_pct: 14.8, solver_pct_todas: 17.4, amostra_minima: 30, cobertura: 98,
  composicao: [{ mesa: 8, n: 1161, pct: 100 }],
  cells: { AKs: { n: 12, voce: 1, limp: 0, solver: 1 }, "72o": { n: 10, voce: 0, limp: 0, solver: 0 } },
  divergencias: [], minimo_maos: 8, divergencia_minima: 0.3,
};
beforeEach(() => {
  hands.mockReset();
  hands.mockResolvedValue(MATRIZ);
});

const ok = (value: number) => ({ value, band: "ok" as const });
const grade = (mesa: string | null, auto: boolean) => ({
  positions: [
    { position: "UTG", hands: 1161, stats: { vpip: ok(15), rfi: ok(16.0) } },
    { position: "BB", hands: 900, stats: { vpip: ok(37) } },
  ],
  total_hands: 2061, sempre: ["vpip", "rfi"], com_volume: [], stack_band: null, faixas: ["40+", "20-40", "<20"],
  mesa, mesas: ["9max", "8max", "7max", "6max", "curta"], mesa_auto: auto,
  distribuicao_de_mesas: {
    mesas: [{ mesa: "8max", n: 3985, pct: 45 }, { mesa: "7max", n: 2500, pct: 28 }],
    sugerida: "8max", n: 8800,
  },
}) as unknown as PositionProfileResponse;
const HUD = { total_hands: 2061, vpip: 25, rfi: 28 } as unknown as PlayerStatsResponse;

describe("seletor de tamanho de mesa", () => {
  it("o modal pede sem recorte, e a comparacao e sobre AS MESMAS maos", async () => {
    render(<MemoryRouter><V2PositionProfileCard data={grade("8max", true)} geral={HUD} lastN={30} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    // sem stack e sem mesa: quem escolhe o recorte e o backend, e o modal desenha o que voltou
    await waitFor(() => expect(hands).toHaveBeenCalledWith("UTG", 90, 30, null, null));
    await screen.findByTestId("matriz-UTG");
    // 16,0 contra 14,8: os dois sobre as maos que cairam. O 17,4 (as 169 maos) NAO e comparavel
    // com o do jogador e vira legenda da grade do solver — o tamanho do desenho, so isso.
    expect(screen.getByTestId("matriz-voce-pct").textContent).toBe("16.0%");
    expect(screen.getByTestId("matriz-solver-pct").textContent).toBe("14.8%");
    expect(screen.getByTestId("matriz-range-size").textContent).toContain("posProfile.matrix.rangeSize:17.4");
    expect(screen.getByTestId("matriz-delta").textContent).toContain("posProfile.matrix.deltaOk");   // 1,2 ponto: folga
  });

  it("amostra pequena esconde OS DOIS numeros e mantem as grades", async () => {
    // Com 10 maos os dois lados sao ruido: foi assim que "solver 7,2%" apareceu ao lado de uma
    // grade cheia em 08/09. O tamanho do range do solver continua como legenda, porque nao
    // depende das maos que cairam.
    hands.mockResolvedValue({ ...MATRIZ, n: 10, voce_pct: null, solver_pct: 7.2, solver_pct_todas: 20.1 });
    render(<MemoryRouter><V2PositionProfileCard data={grade("8max", true)} geral={HUD} lastN={30} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    await screen.findByTestId("matriz-UTG");
    expect(screen.getByTestId("matriz-amostra").textContent).toContain("posProfile.matrix.smallSample:30");
    expect(screen.queryByTestId("matriz-voce-pct")).toBeNull();
    expect(screen.queryByTestId("matriz-solver-pct")).toBeNull();
    expect(screen.getByTestId("matriz-range-size").textContent).toContain("posProfile.matrix.rangeSize:20.1");
    expect(screen.getByTestId("matriz-voce")).toBeTruthy();
  });

  it("assento que nao existe com N jogadores aparece DESLIGADO com o motivo, e o rodape conta as linhas de verdade", () => {
    // Dono, 09/09, na grade de 7 do Rullian: "ta faltando o UTG+1". Nao faltava — com 7 na mao o
    // segundo a agir e o LJ. Mas sumir em silencio parece esquecimento (mesma licao da BB no modal).
    const data = { ...grade("7max", true), assentos_ausentes: ["UTG+1", "UTG+2"],
                   total: { total_hands: 2064 } } as unknown as PositionProfileResponse;
    render(<MemoryRouter><V2PositionProfileCard data={data} geral={HUD} /></MemoryRouter>);
    const ausente = screen.getByTestId("linha-ausente-UTG+1");
    expect(ausente.textContent).toContain("UTG+1");
    expect(ausente.textContent).toContain("posProfile.seatAbsent:posProfile.tableSize.7max");
    expect(screen.getByTestId("linha-ausente-UTG+2")).toBeTruthy();
    // a linha desligada nao e clicavel: nenhuma celula, nenhum detalhe
    expect(ausente.querySelector("button")).toBeNull();
    // o rodape diz "fora das 2 da grade" (a grade tem 2 linhas: UTG e BB), nao "das 8"
    expect(screen.getByText(/posProfile\.outsideGrid:3,2/)).toBeTruthy();
  });

  it("a grade nao oferece filtro de jogadores nem de stack, e diz que soma tudo", () => {
    // Dono, 09/09 noite: "no perfil por posicao, agora e desnecessario o filtro de jogador e
    // stack... vamos manter so na matriz". A grade quer VOLUME e compara com uma FAIXA de
    // referencia; a matriz quer PRECISAO e mostra UM numero. A mesma lente nos dois so dava ao
    // jogador uma forma de esvaziar a propria tela: o piso e 100 maos por assento, e o recorte
    // de 8 jogadores a 40bb+ deixava 36 — 3.231 maos viravam zero celulas preenchidas.
    render(<MemoryRouter><V2PositionProfileCard data={grade(null, false)} geral={HUD} /></MemoryRouter>);
    expect(screen.queryByTestId("select-mesa")).toBeNull();
    expect(screen.queryByTestId("select-stack")).toBeNull();
    // UMA linha antes da grade, nao tres (dono, 09/09: "e mto texto"). Fica so o que muda a
    // leitura do que esta abaixo; o resto vive no tooltip do titulo.
    expect(screen.getByTestId("nota-mesa").textContent).toBe("posProfile.legend");
  });

  it("o card fora do dashboard segue como era", () => {
    render(<MemoryRouter><V2PositionProfileCard data={grade(null, false)} geral={HUD} /></MemoryRouter>);
    expect(screen.queryByTestId("select-mesa")).toBeNull();
    expect(screen.queryByTestId("select-stack")).toBeNull();
  });
});
