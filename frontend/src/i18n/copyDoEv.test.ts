import { describe, expect, it } from "vitest";

import docsPt from "./locales/pt-BR/docs.json";
import docsEn from "./locales/en/docs.json";
import docsEs from "./locales/es/docs.json";
import repPt from "./locales/pt-BR/replayer.json";
import repEn from "./locales/en/replayer.json";
import repEs from "./locales/es/replayer.json";
import dashPt from "./locales/pt-BR/dashboard.json";
import dashEn from "./locales/en/dashboard.json";
import dashEs from "./locales/es/dashboard.json";
import acadPt from "./locales/pt-BR/academy.json";

/**
 * O número de EV fala como FILA DE REVISÃO, nunca como extrato.
 *
 * ── O que originou (18/09) ────────────────────────────────────────────────────────────────
 *
 * A nossa própria definição ensinava a leitura errada. O `/docs` dizia que o indicador
 * 'transforma "errado" em "você vazou X bb"', e as telas diziam "big blinds que você deixou na
 * mesa". "Deixar na mesa" é expressão de DINHEIRO: o jogador lê como prejuízo no bolso.
 *
 * Não é. É a diferença entre a jogada dele e a melhor do solver, dentro do modelo. O resultado
 * real da mão dependeu das cartas que vieram, e ele pode ter ganhado o pote. Pior: o nosso bb
 * perdido subestima em torno de 13%, então apresentar com cara de extrato um número que
 * sabidamente erra junta o pior dos dois mundos.
 *
 * ── O que este guarda cobre, e o que ele NÃO cobre ───────────────────────────────────────
 *
 * COBRE: as chaves que DEFINEM a métrica (a definição do /docs, o tooltip da mão, o tooltip e a
 * manchete do Leak Finder, o rótulo do boletim). Nelas, o idioma de dinheiro é proibido e a
 * ressalva é obrigatória.
 *
 * NÃO COBRE: um sexto lugar novo que nasça amanhã sem a ressalva. Isso é disciplina de copy, e
 * não estrutura — vender cobertura que não existe seria pior do que declarar o limite.
 *
 * O CONTROLE de não-varrer-demais é o último caso: a Academia usa "deixar valor na mesa" oito
 * vezes, e ali é idioma legítimo de poker numa aula sobre apostar pequeno contra station. Uma
 * varredura cega trocaria as duas coisas, e o teste falha se alguém fizer isso.
 */

/** O idioma de caixa, por idioma. Proibido em chave que DEFINE a métrica. */
const IDIOMA_DE_DINHEIRO: Record<string, RegExp> = {
  "pt-BR": /(deixad?[oa]s?|deixou|deixa|dejaste)\s+(de\s+\w+\s+)?na\s+mesa/i,
  en:      /(left|leave|leaving|leaves)\s+(\w+\s+)?on\s+the\s+table/i,
  es:      /(dejad?[oa]s?|dejaste|deja)\s+(\w+\s+)?en\s+la\s+mesa/i,
};

/** A ressalva: a frase precisa NEGAR que o número seja dinheiro. */
const NEGACAO: Record<string, RegExp> = {
  "pt-BR": /\bnão\b/i,
  en:      /\bnot\b/i,
  es:      /\bno\b/i,
};

const IDIOMAS = ["pt-BR", "en", "es"] as const;
const DOCS: Record<string, any> = { "pt-BR": docsPt, en: docsEn, es: docsEs };
const REP: Record<string, any> = { "pt-BR": repPt, en: repEn, es: repEs };
const DASH: Record<string, any> = { "pt-BR": dashPt, en: dashEn, es: dashEs };

/** As chaves que DEFINEM a métrica: [rótulo, função que extrai o texto]. */
const DEFINICOES: [string, (lg: string) => string][] = [
  ["docs.indicators.evloss_interpret", (lg) => DOCS[lg].indicators.evloss_interpret],
  ["replayer.card.evLossTip",          (lg) => REP[lg].card.evLossTip],
  ["dashboard.leakFinder.tooltip",     (lg) => DASH[lg].leakFinder.tooltip],
  ["dashboard.leakFinder.headline_label", (lg) => DASH[lg].leakFinder.headline_label],
  ["dashboard.boletim.bbNaMesa",       (lg) => DASH[lg].boletim.bbNaMesa],
];

describe("a copy do EV nao fala como extrato", () => {
  for (const lg of IDIOMAS) {
    for (const [nome, pega] of DEFINICOES) {
      it(`${lg} · ${nome} nao usa o idioma de dinheiro`, () => {
        const txt = pega(lg);
        expect(typeof txt).toBe("string");
        expect(txt).not.toMatch(IDIOMA_DE_DINHEIRO[lg]);
      });
    }

    // A ressalva só faz sentido onde há frase; a manchete e o rótulo são curtos de propósito.
    it(`${lg} · a definicao do /docs diz o que o numero NAO e`, () => {
      expect(DOCS[lg].indicators.evloss_interpret).toMatch(NEGACAO[lg]);
    });
    it(`${lg} · o tooltip da mao diz o que o numero NAO e`, () => {
      expect(REP[lg].card.evLossTip).toMatch(NEGACAO[lg]);
    });
    it(`${lg} · o Leak Finder declara que o total ordena e nao e extrato`, () => {
      expect(DASH[lg].leakFinder.tooltip).toMatch(NEGACAO[lg]);
    });
    it(`${lg} · a Fila de Treino declara que o valor por mes e projecao`, () => {
      expect(DASH[lg].leaks.tooltip).toMatch(NEGACAO[lg]);
    });

    it(`${lg} · existe a frase de que frequencia nao e ordem`, () => {
      expect(typeof REP[lg].gtoMixed.naoEhOrdem).toBe("string");
      expect(REP[lg].gtoMixed.naoEhOrdem.length).toBeGreaterThan(40);
    });
    it(`${lg} · o custo de oportunidade saiu do codigo e virou chave`, () => {
      expect(REP[lg].gtoMixed.custoDeOportunidade).toContain("{{bb}}");
    });
  }

  it("as tres linguas tem as MESMAS chaves nos blocos tocados", () => {
    const chaves = (o: any) => Object.keys(o).sort().join(",");
    expect(chaves(REP["en"].gtoMixed)).toBe(chaves(REP["pt-BR"].gtoMixed));
    expect(chaves(REP["es"].gtoMixed)).toBe(chaves(REP["pt-BR"].gtoMixed));
    expect(chaves(DASH["en"].leakFinder)).toBe(chaves(DASH["pt-BR"].leakFinder));
    expect(chaves(DASH["es"].leakFinder)).toBe(chaves(DASH["pt-BR"].leakFinder));
  });

  /**
   * CONTROLE: a Academia continua podendo dizer "deixar valor na mesa".
   *
   * Sem este caso, um dia alguém roda a proibição em todos os arquivos, a aula sobre apostar
   * pequeno contra station perde a expressão certa, e o guarda fica verde enquanto piora o
   * produto. O teste falha se as ocorrências legítimas sumirem.
   */
  it("CONTROLE: o idioma de poker sobrevive na Academia", () => {
    const bruto = JSON.stringify(acadPt);
    const achados = bruto.match(/deix\w+\s+(\w+\s+)?na\s+mesa/gi) || [];
    expect(achados.length).toBeGreaterThanOrEqual(4);
  });
});
