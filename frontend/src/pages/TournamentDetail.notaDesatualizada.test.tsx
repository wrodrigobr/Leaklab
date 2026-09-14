// @vitest-environment jsdom
/**
 * A linha da mão quando a explicação foi RETIRADA por discordar do veredito (14/09).
 *
 * O backend retira a nota que manda fazer coisa diferente do que a linha recomenda hoje
 * (`repositories.silencia_nota_desatualizada`), porque ela é texto congelado no instante da
 * análise e o resync do solver reescreve o veredito horas depois. Eram 1.519 decisões, 1.167
 * delas na forma pior: chip verde de Correto e o texto mandando fazer outra coisa.
 *
 * O teste monta a PÁGINA e olha o DOM em vez de checar estado, pela mesma razão do onboarding:
 * o defeito desta classe mora no caminho de renderização. Um teste de `noteStale` passaria
 * verde com a tela sem mostrar nada, e "bug da vitrine escapa" é justamente a lição da casa.
 *
 * Três coisas, e a segunda é a que impede o guarda de se desarmar:
 *   1. sem nota e com a flag acesa, a tela DIZ que não há explicação escrita;
 *   2. com nota, a tela mostra a NOTA e não a frase de ausência;
 *   3. sem nota e sem flag, a tela não inventa frase nenhuma.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const estado = vi.hoisted(() => ({ decisoes: [] as unknown[] }));

vi.mock("react-router-dom", async () => {
  const real = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...real, useParams: () => ({ id: "T-1" }) };
});

vi.mock("@/lib/api", () => {
  // declarado DENTRO da fabrica: o `vi.mock` e icado para o topo do arquivo, e uma const de
  // modulo usada aqui estoura com "Cannot access before initialization"
  const nunca = () => new Promise(() => {});
  return {
  tournaments: {
    get: () => Promise.resolve({
      tournament: {
        id: 1, tournament_id: "T-1", tournament_name: "Teste", site: "pokerstars",
        hands_count: 1, decisions_count: 1, avg_score: 1, played_at: "2026-09-07",
      },
      decisions: estado.decisoes,
    }),
    phaseAnalysis: nunca, textureAnalysis: nunca, narrative: nunca, heroHud: nunca,
    sessionReview: nunca, analyzeDecision: nunca, downloadReport: nunca,
  },
  metrics: new Proxy({}, { get: () => nunca }),
  coachDashboard: new Proxy({}, { get: () => nunca }),
  };
});
vi.mock("@/components/hud/HudLayout", () => ({
  HudLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/hud/TournamentAiReport", () => ({ TournamentAiReport: () => null }));
vi.mock("@/components/hud/HudDoTorneio", () => ({ HudDoTorneio: () => null }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    // devolve a CHAVE: o teste procura `detail.noteStale`, então ele falha se a tela parar de
    // pedir a frase ao i18n (copy cravada no código é defeito registrado da casa)
    t: (k: string, o?: unknown) => (typeof o === "string" ? o : k),
    i18n: { language: "pt-BR" },
  }),
}));

import TournamentDetail from "./TournamentDetail";

const NOTA = "Com equity de 53.1% vs 37.9% exigidos pelo pot, o call tinha valor positivo.";

/** Uma decisão de erro claro, no formato que a rota devolve. */
const decisao = (extra: Record<string, unknown>) => ({
  id: 1, hand_id: "900001", street: "flop", hero_cards: "JcQc",
  board: '["5h", "Qs", "8c"]', action_taken: "fold", best_action: "jam",
  label: "clear_mistake", score: 1.0, math_penalty: 0, range_penalty: 0,
  m_ratio: 26.1, icm_pressure: "low", stack_bb: 74.4, draw_profile: "none",
  position: "BB", num_players: 9, level_sb: 10, level_bb: 20, level_num: 1,
  note: null, gto_label: "gto_critical", gto_action: "jam",
  ...extra,
});

const monta = () => render(
  <MemoryRouter><TournamentDetail /></MemoryRouter>
);

afterEach(() => { cleanup(); estado.decisoes = []; });

describe("a linha da mão sem explicação escrita", () => {
  it("diz que não há explicação quando o backend retirou a nota", async () => {
    estado.decisoes = [decisao({ note: null, note_desatualizada: true })];
    monta();
    await waitFor(() => expect(screen.getByText("detail.noteStale")).toBeTruthy());
  });

  it("mostra a NOTA quando ela existe, e não a frase de ausência", async () => {
    // O controle que impede o guarda de se desarmar: sem ele, uma tela que mostrasse a frase
    // SEMPRE passaria no caso de cima e apagaria 135 mil notas boas da vista do jogador.
    estado.decisoes = [decisao({ note: NOTA, note_desatualizada: false })];
    monta();
    await waitFor(() => expect(screen.getByText(NOTA)).toBeTruthy());
    expect(screen.queryByText("detail.noteStale")).toBeNull();
  });

  it("não inventa frase quando não há nota nem flag", async () => {
    estado.decisoes = [decisao({ note: null })];
    monta();
    // espera a linha da mão aparecer antes de afirmar a AUSÊNCIA: sem essa espera o caso
    // passaria verde só porque a página ainda não tinha renderizado nada
    await waitFor(() => expect(screen.getByText(/Fold/)).toBeTruthy());
    expect(screen.queryByText("detail.noteStale")).toBeNull();
  });
});
