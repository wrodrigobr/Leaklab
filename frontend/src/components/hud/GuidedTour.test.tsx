// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";
import { GuidedTour, type TourStep } from "./GuidedTour";

/**
 * O tour guiado.
 *
 * ── O guarda principal ────────────────────────────────────────────────────────────────────────
 *
 * **Passo sem alvo no DOM é PULADO, nunca apontado.** O dashboard mostra card conforme o volume
 * de dados, então o mesmo tour roda sobre telas diferentes. Apontar para um alvo ausente é
 * exatamente o defeito que fez a tela de demonstração existir: um tour sobre cards vazios ensina
 * que o produto é vazio.
 *
 * O resto do arquivo defende que o tour não vire um quiz vencível sem ler: contagem de passos
 * honesta, e copy nas 3 locales.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: "pt-BR" } }),
}));

const passo = (target: string): TourStep => ({
  target, code: `code-${target}`, title: `titulo-${target}`, description: `desc-${target}`,
});

function comAlvos(nomes: string[]) {
  document.body.innerHTML = nomes.map((n) => `<div data-tour="${n}">alvo ${n}</div>`).join("");
}

beforeEach(() => {
  // jsdom não implementa scrollIntoView; o componente o chama antes de medir.
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); document.body.innerHTML = ""; });

describe("tour guiado — alvo ausente é pulado", () => {
  it("só monta os passos cujo alvo existe na tela", async () => {
    comAlvos(["a", "c"]);
    render(<GuidedTour steps={[passo("a"), passo("b"), passo("c")]} open onClose={() => {}} />);

    // O passo "b" não tem alvo: some. Restam 2, e a contagem de bolinhas prova.
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
    const dialogo = screen.getByRole("dialog");
    expect(dialogo.querySelectorAll("span.rounded-full").length,
      "a contagem de passos tem que refletir só os alvos vivos").toBe(2);
    expect(dialogo.textContent).toContain("titulo-a");
    expect(dialogo.textContent, "passo sem alvo apareceu").not.toContain("titulo-b");
  });

  it("não renderiza nada quando NENHUM alvo existe", async () => {
    comAlvos([]);
    const { container } = render(
      <GuidedTour steps={[passo("a"), passo("b")]} open onClose={() => {}} />);
    await waitFor(() => expect(container.querySelector('[role="dialog"]')).toBeNull());
  });

  it("fechado, não renderiza nada", () => {
    comAlvos(["a"]);
    const { container } = render(
      <GuidedTour steps={[passo("a")]} open={false} onClose={() => {}} />);
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });
});

describe("tour guiado — navegação", () => {
  it("avança e termina chamando onClose", async () => {
    comAlvos(["a", "b"]);
    const aoFechar = vi.fn();
    render(<GuidedTour steps={[passo("a"), passo("b")]} open onClose={aoFechar} />);

    await waitFor(() => expect(screen.getByRole("dialog").textContent).toContain("titulo-a"));
    const avancar = () => {
      const bs = [...screen.getByRole("dialog").querySelectorAll("button")];
      fireEvent.click(bs[bs.length - 1]);
    };
    avancar();
    await waitFor(() => expect(screen.getByRole("dialog").textContent).toContain("titulo-b"));
    avancar();
    expect(aoFechar).toHaveBeenCalled();
  });

  it("Esc fecha", async () => {
    comAlvos(["a"]);
    const aoFechar = vi.fn();
    render(<GuidedTour steps={[passo("a")]} open onClose={aoFechar} />);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(aoFechar).toHaveBeenCalled();
  });
});

describe("tour guiado — copy e âncoras", () => {
  it("os 6 passos têm copy completa nas 3 locales", () => {
    const chaves = ["fechar", "proximo", "fim", "botao",
      ...[1, 2, 3, 4, 5, 6].flatMap((n) => [`p${n}code`, `p${n}title`, `p${n}desc`])];
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = JSON.parse(readFileSync(`src/i18n/locales/${loc}/dashboard.json`, "utf-8"));
      for (const k of chaves) {
        expect(d.tour?.[k], `${loc}: tour.${k} ausente`).toBeTruthy();
      }
    }
  });

  it("cada passo da demonstração aponta para uma âncora que EXISTE no código", () => {
    // Passo apontando para âncora inexistente se auto-pula em runtime — silenciosamente. Aqui a
    // divergência entre a lista de passos e as âncoras plantadas vira falha.
    const demo = readFileSync("src/pages/Demo.tsx", "utf-8");
    const alvos = [...demo.matchAll(/target:\s*"([^"]+)"/g)].map((m) => m[1]);
    expect(alvos.length, "nenhum passo declarado na demonstração").toBeGreaterThanOrEqual(6);

    const fontes = ["src/components/hud/DashboardV2.tsx", "src/components/hud/HudHeader.tsx"]
      .map((f) => readFileSync(f, "utf-8")).join("\n");
    const semAncora = alvos.filter((a) => !fontes.includes(`"${a}"`));
    expect(semAncora, "passo aponta para âncora que ninguém planta").toEqual([]);
  });

  it("a copy de volume não some: os passos de número citam o mínimo exigido", () => {
    // Sem isto o jogador sobe um torneio, lê "ainda não dá para afirmar" e conclui que o produto
    // não funciona — a segunda restrição registrada do onboarding.
    const d = JSON.parse(readFileSync("src/i18n/locales/pt-BR/dashboard.json", "utf-8"));
    expect(d.tour.p2desc, "passo do EV sem o volume mínimo").toMatch(/\d/);
    expect(d.tour.p3desc, "passo do ROI sem o volume mínimo").toMatch(/30/);
  });
});
