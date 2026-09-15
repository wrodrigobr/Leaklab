import { describe, expect, it } from "vitest";

import commonPt from "./locales/pt-BR/common.json";
import commonEn from "./locales/en/common.json";
import commonEs from "./locales/es/common.json";

/**
 * A frase do erro de processamento diz so o que acontece.
 *
 * Auditoria FLU-6 (15/09): `uploadQueue.erroNoProcessamento` dizia "Seu envio esta guardado,
 * vamos tentar de novo". Medido no backend (`data/auditoria/repro/FLU_5.py`): quando o
 * recibo vira `erro`, `concluir` zera os bytes e o worker nao volta a olhar para ele
 * (`reivindicar` so pega `recebido`). A metade "nao conseguimos analisar" era honesta; a
 * metade "esta guardado, vamos tentar de novo" descrevia um comportamento que nao existe.
 *
 * O guarda proibe a PROMESSA, nas tres linguas, em vez de fixar a frase: se um dia a
 * retentativa existir de verdade, quem a fizer troca a copy e este teste junto.
 */
const PROMESSAS = [
  /tentar\s+de\s+novo/i,
  /vamos\s+tentar/i,
  /est[aá]\s+guardad[oa]/i,
  /try\s+again/i,
  /we\s+will\s+(re)?try/i,
  /is\s+saved/i,
  /intentar(emos|lo)?\s+de\s+nuevo/i,
  /est[aá]\s+guardad[oa]/i,
];

describe("uploadQueue.erroNoProcessamento nao promete retentativa", () => {
  const locales: Array<[string, { uploadQueue: { erroNoProcessamento: string } }]> = [
    ["pt-BR", commonPt],
    ["en", commonEn],
    ["es", commonEs],
  ];
  for (const [nome, dict] of locales) {
    it(`${nome}: a frase existe e diz so o que acontece`, () => {
      const frase = dict.uploadQueue.erroNoProcessamento;
      expect(frase.length).toBeGreaterThan(10);
      for (const p of PROMESSAS) expect(frase).not.toMatch(p);
    });
  }

  it("o medidor acha a promessa (regra 1)", () => {
    const antigas = [
      "Não conseguimos analisar este arquivo. Seu envio está guardado, vamos tentar de novo.",
      "We could not analyze this file. Your upload is saved and we will try again.",
      "No pudimos analizar este archivo. Tu envío está guardado y lo intentaremos de nuevo.",
    ];
    for (const a of antigas) expect(PROMESSAS.some((p) => p.test(a))).toBe(true);
  });
});
