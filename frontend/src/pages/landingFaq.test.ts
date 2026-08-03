import { describe, it, expect } from "vitest";
import { FAQ_COUNT } from "./Landing";
import ptBR from "@/i18n/locales/pt-BR/landing.json";
import en from "@/i18n/locales/en/landing.json";
import es from "@/i18n/locales/es/landing.json";

/* O FAQ é copy pura em três idiomas, e o modo de falha dele é silencioso: **chave faltando não
 * quebra o i18next — ele imprime a chave crua na tela.** Um "faq.q7" apareceria como texto para o
 * visitante, na página cujo trabalho é passar confiança.
 *
 * Por isso o guarda cobra as três locales contra `FAQ_COUNT`, que é o que a seção realmente
 * desenha, e não contra o que uma delas por acaso tem.
 */

const LOCALES = { "pt-BR": ptBR, en, es } as const;
const faqDe = (d: unknown) => (d as { faq?: Record<string, string> }).faq ?? {};

describe("landing — FAQ", () => {
  it("a seção desenha um número plausível de perguntas", () => {
    // Sem isto, `FAQ_COUNT = 0` faria todos os testes abaixo passarem sobre um FAQ vazio.
    expect(FAQ_COUNT).toBeGreaterThanOrEqual(3);
  });

  for (const [locale, dict] of Object.entries(LOCALES)) {
    it(`${locale}: tem as ${FAQ_COUNT} perguntas e respostas, sem vazio`, () => {
      const faq = faqDe(dict);
      const faltando: string[] = [];
      for (let i = 1; i <= FAQ_COUNT; i++) {
        for (const campo of [`q${i}`, `a${i}`]) {
          if (!faq[campo] || !faq[campo].trim()) faltando.push(campo);
        }
      }
      expect(faltando, `${locale} não traduziu: ${faltando.join(", ")}`).toEqual([]);
      expect(faq.heading?.trim(), `${locale} sem heading`).toBeTruthy();
      expect(faq.eyebrow?.trim(), `${locale} sem eyebrow`).toBeTruthy();
    });

    it(`${locale}: não tem pergunta ESCRITA e nunca exibida`, () => {
      // O inverso do teste acima: copy que existe no JSON mas está fora do alcance da seção é
      // trabalho de tradução jogado fora, e ninguém descobre porque nada quebra.
      const orfas = Object.keys(faqDe(dict)).filter((k) => {
        const m = /^[qa](\d+)$/.exec(k);
        return m && Number(m[1]) > FAQ_COUNT;
      });
      expect(orfas, `${locale} tem copy que a tela nunca mostra: ${orfas.join(", ")}`).toEqual([]);
    });
  }

  it("as três locales têm exatamente o mesmo conjunto de chaves", () => {
    const chaves = Object.entries(LOCALES).map(([l, d]) => [l, Object.keys(faqDe(d)).sort()] as const);
    const [, base] = chaves[0];
    for (const [locale, ks] of chaves.slice(1)) {
      expect(ks, `${locale} divergiu de pt-BR`).toEqual(base);
    }
  });

  it("nenhuma resposta ficou igual em dois idiomas (sinal de tradução esquecida)", () => {
    // Copy nova costuma ser colada igual nas 3 locales "para traduzir depois", e o depois não vem.
    const repetidas: string[] = [];
    for (let i = 1; i <= FAQ_COUNT; i++) {
      const textos = Object.values(LOCALES).map((d) => faqDe(d)[`a${i}`]);
      if (new Set(textos).size !== textos.length) repetidas.push(`a${i}`);
    }
    expect(repetidas, `respostas idênticas entre idiomas: ${repetidas.join(", ")}`).toEqual([]);
  });
});
