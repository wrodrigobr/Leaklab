import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { SALAS_SEM_RESULTADO, SALAS_SUPORTADAS, salaSemResultado } from "@/lib/salas";

/**
 * A coluna de prêmio de uma sala que não fornece o resumo do torneio.
 *
 * O PartyPoker não oferece o Tournament Summary para download: o fluxo de export da sala é
 * `My Game -> Export Hands` e entrega só mãos (conferido também no arquivo real do Rullian, zero
 * linha de colocação ou prêmio em 157 mil linhas). Sem o resumo não há colocação, prêmio, ROI,
 * número de inscritos nem detecção de mesa final.
 *
 * Duas saídas erradas eram possíveis, e as duas já aconteceram neste produto com outras telas:
 *
 *   1. **Deixar um traço.** O jogador vê a coluna vazia e não sabe se falta arquivo, se falta
 *      processamento ou se o produto está quebrado.
 *   2. **Oferecer o botão de upload** (como a ACR, que tem `.ots`). Aí a tela manda a pessoa
 *      procurar um arquivo que a sala não gera. Prometer o que não existe é o defeito que a casa
 *      já levou para a landing uma vez.
 *
 * A tela declara a limitação. Os guardas abaixo defendem a decisão e, principalmente, o
 * CONTROLE NEGATIVO: a ACR não pode perder o botão, e nenhuma sala com resumo pode entrar na
 * lista por descuido.
 */
const LOCALES = ["pt-BR", "en", "es"] as const;
const TELA = "src/pages/Tournaments.tsx";

const copy = (loc: string) =>
  JSON.parse(readFileSync(`src/i18n/locales/${loc}/tournaments.json`, "utf-8")).results;

describe("coluna de prêmio — sala sem resumo de torneio", () => {
  it("reconhece a sala, e só ela", () => {
    expect(salaSemResultado("partypoker")).toBe(true);
    expect(salaSemResultado("PartyPoker")).toBe(true);
    // CONTROLE NEGATIVO: sem estes, uma função que devolvesse `true` sempre passaria no teste
    // acima e apagaria o botão da ACR e os prêmios de todo mundo.
    expect(salaSemResultado("acr")).toBe(false);
    expect(salaSemResultado("pokerstars")).toBe(false);
    expect(salaSemResultado("ggpoker")).toBe(false);
    expect(salaSemResultado("coinpoker")).toBe(false);
    expect(salaSemResultado(null)).toBe(false);
    expect(salaSemResultado(undefined)).toBe(false);
  });

  it("toda sala da lista é uma sala suportada", () => {
    // Nome errado aqui (um typo, um nome comercial) faz o selo nunca aparecer, calado.
    for (const s of SALAS_SEM_RESULTADO) {
      expect(SALAS_SUPORTADAS as readonly string[], `${s} não é uma sala suportada`).toContain(s);
    }
  });

  it("a tela decide pela função, e o ramo da ACR continua de pé", () => {
    const src = readFileSync(TELA, "utf-8");
    expect(src, "a tela não consulta a lista de salas sem resultado")
      .toContain("salaSemResultado(site)");
    // O botão de upload da ACR é o outro ramo do mesmo ternário: se ele cair, quem tem `.ots`
    // perde o caminho de completar a premiação.
    expect(src, "o ramo do upload da ACR desapareceu").toContain('site === "acr"');
    expect(src).toContain("results.semResultado");
  });

  it("a copy existe nas 3 locales e diz o que se perde", () => {
    for (const loc of LOCALES) {
      const c = copy(loc);
      expect(c.semResultado, `${loc}: falta o rótulo do selo`).toBeTruthy();
      expect(c.semResultadoHint, `${loc}: falta a explicação do selo`).toBeTruthy();
      // Rótulo é rótulo: se virar frase, estoura a célula da tabela.
      expect(c.semResultado.length, `${loc}: o rótulo do selo ficou longo`).toBeLessThanOrEqual(20);
      // A explicação precisa dizer POR QUE a coluna está vazia e o que falta. Sem isso o selo
      // troca um traço sem explicação por uma palavra sem explicação.
      expect(c.semResultadoHint.toLowerCase(), `${loc}: a explicação não cita o ROI`)
        .toContain("roi");
      expect(c.semResultadoHint.toLowerCase(), `${loc}: a explicação não nomeia a sala`)
        .toContain("partypoker");
    }
  });
});
