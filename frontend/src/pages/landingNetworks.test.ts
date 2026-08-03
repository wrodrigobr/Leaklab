import { describe, it, expect } from "vitest";
import { LANDING_NETWORKS } from "./Landing";
import ptBR from "@/i18n/locales/pt-BR/landing.json";
import en from "@/i18n/locales/en/landing.json";
import es from "@/i18n/locales/es/landing.json";

/* A faixa de redes e a frase abaixo dela dizem O MESMO FATO por duas fontes diferentes: uma é
 * código (os chips), a outra é copy em três idiomas.
 *
 * **Elas já divergiram, e quem pegou foi o usuário:** os chips mostravam CoinPoker e a frase dizia
 * "PokerStars, GGPoker e ACR (WPN)". Quem lesse a frase concluiria que a rede não era suportada —
 * numa página cujo trabalho é responder "dá pra importar de onde eu jogo?".
 *
 * O guarda vale para as TRÊS locales de propósito. Conferir só o pt-BR deixaria en e es
 * envelhecerem calados, que é como a maior parte da copy traduzida apodrece.
 */

const LOCALES = { "pt-BR": ptBR, en, es } as const;

describe("landing — a copy das redes cobre o que a faixa mostra", () => {
  it("há redes para conferir", () => {
    // Sem isto, uma lista vazia faria todos os testes abaixo passarem medindo nada.
    expect(LANDING_NETWORKS.length).toBeGreaterThanOrEqual(3);
  });

  for (const [locale, dict] of Object.entries(LOCALES)) {
    it(`${locale}: a frase menciona todas as redes da faixa`, () => {
      const frase = (dict as { networks: { subtitle: string } }).networks.subtitle;
      const faltando = LANDING_NETWORKS.filter((n) => !frase.includes(n.token)).map((n) => n.name);
      expect(faltando, `a frase de ${locale} não menciona: ${faltando.join(", ")}`).toEqual([]);
    });
  }

  it("o passo 1 do 'como funciona' também menciona todas", () => {
    // Segundo lugar onde a mesma lista aparece em prosa. Foi só a frase da faixa que ficou para
    // trás na última vez, mas nada impede que da próxima seja esta.
    for (const [locale, dict] of Object.entries(LOCALES)) {
      const passo = (dict as { howItWorks: { step1Desc: string } }).howItWorks.step1Desc;
      const faltando = LANDING_NETWORKS.filter((n) => !passo.includes(n.token)).map((n) => n.name);
      expect(faltando, `o passo 1 de ${locale} não menciona: ${faltando.join(", ")}`).toEqual([]);
    }
  });
});
