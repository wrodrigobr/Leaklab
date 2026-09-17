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
  });

  it("a sala sem resumo OFERECE o preenchimento manual, e não é mais beco sem saída", () => {
    // ── A decisão mudou em 17/09 ────────────────────────────────────────────────────────────
    //
    // Este arquivo dizia que havia duas saídas erradas (deixar um traço, ou oferecer um upload
    // que não existe) e que a terceira era DECLARAR a limitação. Declarar era melhor que as duas,
    // e ainda assim era beco sem saída: o torneio de PartyPoker nunca teria ROI.
    //
    // O dono: "nao haviamos criado um meio de torneios do party poker, o usuario conseguir
    // preencher os dados do summary que precisamos?". Agora o selo é um BOTÃO que abre o
    // formulário, e o número digitado fica marcado como digitado.
    //
    // Este caso existe porque o guarda anterior passou VERDE quando eu troquei o selo pelo botão:
    // ele exigia `results.semResultado` no fonte, e `results.semResultadoHint` (que continuou lá,
    // no `title`) contém aquela string como prefixo. Um `toContain` sobre nome de chave casa
    // prefixo, e foi assim que a mudança de desenho passou sem ninguém notar.
    const src = readFileSync(TELA, "utf-8");
    expect(src, "o botão de preencher não está na coluna de prêmio")
      .toContain("abrir-resultado-manual");
    expect(src, "o rótulo do botão não veio da copy").toContain("manual.preencher");
    // a explicação de POR QUE não há arquivo continua, agora como `title` do botão
    expect(src, "a explicação da sala sem resumo desapareceu").toContain("results.semResultadoHint");
    // E a procedência aparece onde o número aparece. O guarda pede o COMPONENTE, e não a chave de
    // copy: ela mora dentro dele, e o comportamento ("aparece só no digitado") tem teste próprio
    // em `ResultadoManual.test.tsx`. Guarda textual sobre chave de i18n foi o que deixou a
    // troca do selo pelo botão passar verde, aqui mesmo, algumas horas antes.
    expect(src, "o número digitado não se distingue do número de arquivo")
      .toContain("MarcaDeProcedencia");
    expect(src).toContain("financeiro_origem");
  });

  it("a copy do formulário existe nas 3 locales, com os erros em português claro", () => {
    for (const loc of LOCALES) {
      const m = JSON.parse(readFileSync(`src/i18n/locales/${loc}/tournaments.json`, "utf-8")).manual;
      expect(m, `${loc}: falta o bloco do formulário`).toBeTruthy();
      for (const k of ["titulo", "colocacao", "jogadores", "buyIn", "premio", "lucro", "salvar",
                       "avisoOrigem", "preencher", "digitado"]) {
        expect(m[k], `${loc}: falta ${k}`).toBeTruthy();
      }
      // As mensagens de erro são FRASES, e não códigos: o dono foi explícito ("nao podemos
      // retornar codigo de erro para o usuario, temos que ter o erro tratado").
      for (const k of ["erroColocacao", "erroPremio", "erroBuyIn", "erroColocacaoMaior",
                       "erroSalvar"]) {
        expect(m[k], `${loc}: falta ${k}`).toBeTruthy();
        expect(m[k].length, `${loc}: ${k} curto demais para explicar`).toBeGreaterThan(20);
        expect(m[k], `${loc}: ${k} parece código`).not.toMatch(/\d{3}/);
      }
      // O aviso tem de dizer que o número entra no ROI e no bankroll: é o que justifica a marca
      // de procedência na tela.
      expect(m.avisoOrigem.toLowerCase(), `${loc}: o aviso não cita o ROI`).toContain("roi");
    }
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
