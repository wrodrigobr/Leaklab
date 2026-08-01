// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { makeRenderCard, type DadosDoDashboard } from "@/components/hud/dashboardCards";
import { DEFAULT_SECTIONS } from "@/hooks/useDashboardLayout";

/**
 * A tela de demonstração (`/demo`) tem que mostrar o produto POVOADO.
 *
 * Ela existe porque o dashboard é vazio antes do primeiro upload, e um tour guiado sobre a tela
 * vazia apontaria para cards sem número — o que ensina que o produto é vazio.
 *
 * O teste lê a MESMA fixture que o backend serve (o arquivo, não uma cópia): fixture que
 * empobreça derruba isto aqui também. E confere card a card, porque a falha real não é a tela
 * quebrar, é um card devolver `null` e sumir sem ninguém notar.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: "pt-BR" } }),
}));

const FIXTURE = "../backend/fixtures/dashboard_demo.json";
const demo = JSON.parse(readFileSync(FIXTURE, "utf-8"));

function dados(): DadosDoDashboard {
  return {
    evo:              demo.evolution,
    leakRoi:          demo.leakRoi.leaks,
    leakSource:       demo.leakRoi.source,
    pressureData:     demo.pressureProfile,
    dnaData:          demo.dna,
    leakGraph:        demo.leakGraph,
    careerData:       demo.career,
    cognitiveData:    demo.cognitiveFailures,
    twinData:         demo.strategicTwin,
    sessionData:      demo.sessionContext,
    gtoQualityData:   demo.gtoQuality,
    gtoPositionData:  demo.gtoPosition,
    resultsVsGtoData: demo.resultsVsGto,
    leakFinderData:   demo.leakFinder,
    pendingGto:       0,
  };
}

describe("tela de demonstração — nenhum card nasce vazio", () => {
  it("os 13 cards do bento têm o que renderizar com a fixture real", () => {
    const render = makeRenderCard(dados(), { isFree: false, tc: (k) => k });
    const vazios = DEFAULT_SECTIONS.filter((id) => render(id, { v2: true }) == null);
    expect(vazios, "card que some da demonstração sem quebrar nada").toEqual([]);
    expect(DEFAULT_SECTIONS.length, "o bento encolheu — regenerar a fixture?").toBeGreaterThanOrEqual(13);
  });

  it("nenhum card do dashboard busca os próprios dados sem aceitar dado pronto", () => {
    /**
     * O guarda que faltava, e a história dele importa.
     *
     * A primeira versão do teste procurava card VAZIO. O `V2BankrollCard` passou: ele buscava a
     * evolução de quem estava VISITANDO (deslogado, vazia) e renderizava "sem torneios
     * suficientes" — um estado-vazio COM TEXTO, que passa por cheio em qualquer contagem de
     * caracteres. Foi encontrado olhando a tela, não pelo teste.
     *
     * A regra que sobrou: card que chama `metrics.` tem que aceitar `data` por prop e desligar a
     * própria busca com `enabled`. Sem isso ele mente na demonstração.
     */
    const suspeitos = ["BankrollChart", "V2BankrollCard"];
    for (const nome of suspeitos) {
      const src = readFileSync(`src/components/hud/${nome}.tsx`, "utf-8");
      expect(src, `${nome}: busca própria sem aceitar dado pronto`).toMatch(/data\?:\s*EvolutionResponse/);
      expect(src, `${nome}: não desliga a busca quando recebe dado`).toMatch(/enabled:\s*dataFixa === undefined/);
    }
    // E a demonstração precisa realmente passar a série adiante.
    expect(readFileSync("src/pages/Demo.tsx", "utf-8")).toContain("evolution={dados.evolution}");
  });

  it("com o gate Free ligado os cards Pro viram cadeado, e a demonstração NÃO usa isso", () => {
    // Guarda de sentido: prova que `isFree` muda o resultado, senão o teste acima passaria mesmo
    // se o mapa ignorasse o parâmetro — e a demonstração mostra o produto completo de propósito.
    const comCadeado = makeRenderCard(dados(), { isFree: true, tc: (k) => k })("career", { v2: true });
    const semCadeado = makeRenderCard(dados(), { isFree: false, tc: (k) => k })("career", { v2: true });
    expect(JSON.stringify(comCadeado)).not.toEqual(JSON.stringify(semCadeado));
  });
});

describe("tela de demonstração — não é uma cópia do dashboard", () => {
  it("usa o mesmo mapa de cards do dashboard real", () => {
    const src = readFileSync("src/pages/Demo.tsx", "utf-8");
    expect(src, "a demonstração tem que consumir o mapa compartilhado")
      .toContain('from "@/components/hud/dashboardCards"');
    expect(src, "a demonstração tem que renderizar o DashboardV2 real")
      .toContain('from "@/components/hud/DashboardV2"');
  });

  it("o Index também consome o mapa, e não uma segunda cópia", () => {
    const src = readFileSync("src/pages/Index.tsx", "utf-8");
    expect(src).toContain("makeRenderCard");
    // Se o switch voltar para dentro do Index, são dois mapas divergindo em silêncio.
    expect(src, "mapa de cards de volta dentro do Index").not.toMatch(/case "causal_map":/);
  });

  it("a tela declara que é demonstração, nas 3 locales", () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = JSON.parse(readFileSync(`src/i18n/locales/${loc}/dashboard.json`, "utf-8"));
      expect(d.demo?.selo, `${loc}: selo ausente`).toBeTruthy();
      expect(d.demo?.explicacao, `${loc}: explicação ausente`).toBeTruthy();
    }
    expect(readFileSync("src/pages/Demo.tsx", "utf-8")).toContain('t("demo.selo")');
  });
});
