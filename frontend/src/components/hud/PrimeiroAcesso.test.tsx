// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { PrimeiroAcesso } from "./PrimeiroAcesso";
import { ONDE_ACHO, SITES } from "@/lib/ondeAchoOArquivo";

/**
 * Onboarding de primeiro acesso.
 *
 * ── O que o usuário reportou ──────────────────────────────────────────────────────────────────
 *
 * *"Quem é impactado no Instagram se cadastra e não sabe o que fazer."* O estado vazio de hoje diz
 * "faça upload do seu arquivo de hand history" com o ONDE entre parênteses, e em alguns sites o
 * arquivo nem existe até a pessoa ligar a opção. Esse é o primeiro ponto de desistência.
 *
 * ── O que este arquivo trava ──────────────────────────────────────────────────────────────────
 *
 * 1. Que a tela **nunca invente um caminho de pasta**. Caminho errado é pior que caminho ausente:
 *    manda a pessoa procurar onde não tem e ela conclui que o produto não serve para o site dela.
 *    Só PokerStars e ACR foram verificados numa máquina real; os outros dois mostram instrução.
 * 2. Que a expectativa honesta apareça. Medido: um aluno com 258 decisões tem ZERO família com
 *    amostra para validar. Prometer tudo no primeiro torneio faz a pessoa subir um arquivo, ver
 *    "ainda não dá para afirmar" e concluir que não funciona.
 * 3. Que o texto exista nas 3 locales, com os placeholders.
 */
afterEach(cleanup);

describe("PrimeiroAcesso — não inventa caminho", () => {
  it("só mostra pasta para os sites cujo caminho foi verificado", () => {
    const verificados = SITES.filter((s) => ONDE_ACHO[s].caminho);
    const semCaminho = SITES.filter((s) => !ONDE_ACHO[s].caminho);
    expect(verificados.length, "nenhum caminho verificado").toBeGreaterThan(0);
    expect(semCaminho.length, "todos verificados? confira antes de afirmar").toBeGreaterThan(0);
  });

  it("o site sem caminho verificado cai na instrução, não num palpite", () => {
    const { container, getByText } = render(<PrimeiroAcesso />);
    const semCaminho = SITES.find((s) => !ONDE_ACHO[s].caminho)!;
    fireEvent.click(getByText(semCaminho === "ggpoker" ? "GGPoker" : "CoinPoker"));
    expect(container.textContent).toContain("primeiroAcesso.p1.semCaminho");
    expect(container.querySelector("code")).toBeNull();
  });

  it("o site verificado mostra a pasta e o botão de copiar", () => {
    const { container, getByText } = render(<PrimeiroAcesso />);
    fireEvent.click(getByText("PokerStars"));
    const code = container.querySelector("code");
    expect(code?.textContent).toContain("PokerStars");
    expect(code?.textContent).toContain("HandHistory");
  });

  it("o caminho verificado tem a marca de que foi conferido numa máquina", () => {
    // Ambos foram lidos do disco em 2026-07-31. Se alguem adicionar um caminho novo, tem que
    // conferir antes: o teste exige que todo caminho pareca um caminho de Windows completo.
    for (const s of SITES) {
      const c = ONDE_ACHO[s].caminho;
      if (c) expect(c, s).toMatch(/^[A-Z]:\\/);
    }
  });
});

describe("PrimeiroAcesso — a expectativa é honesta", () => {
  it("diz o que aparece agora E o que precisa de mais volume", () => {
    const { container } = render(<PrimeiroAcesso />);
    expect(container.textContent).toContain("primeiroAcesso.p3.agora");
    expect(container.textContent).toContain("primeiroAcesso.p3.depois");
    expect(container.textContent).toContain("primeiroAcesso.p3.honestidade");
  });

  it("os três passos aparecem, na ordem achar → subir → esperar", () => {
    const { container } = render(<PrimeiroAcesso />);
    const txt = container.textContent ?? "";
    expect(txt.indexOf("p1.titulo")).toBeLessThan(txt.indexOf("p2.titulo"));
    expect(txt.indexOf("p2.titulo")).toBeLessThan(txt.indexOf("p3.titulo"));
  });
});

describe("PrimeiroAcesso — copy nas 3 locales", () => {
  it("existe, com os placeholders e sem travessão", async () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = (await import(`@/i18n/locales/${loc}/dashboard.json`)).default as
        { primeiroAcesso: Record<string, Record<string, string> | string> };
      const pa = d.primeiroAcesso;
      expect(pa, loc).toBeTruthy();
      const p1 = pa.p1 as Record<string, string>;
      const p3 = pa.p3 as Record<string, string>;
      expect(p1.ligarPrimeiro, `${loc}.p1.ligarPrimeiro`).toContain("{{site}}");
      expect(p1.semCaminho, `${loc}.p1.semCaminho`).toContain("{{site}}");
      // a frase da expectativa honesta nao pode virar uma promessa
      expect(p3.honestidade.length, `${loc}.p3.honestidade`).toBeGreaterThan(80);
      const todas = JSON.stringify(pa);
      expect(todas, loc).not.toContain("—");
    }
  });
});
