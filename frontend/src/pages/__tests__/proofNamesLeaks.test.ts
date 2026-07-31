import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";

/**
 * O card "Validar aprendizado" NOMEIA o leak, e nomeia pela chave certa.
 *
 * ── O que o usuário reportou ──────────────────────────────────────────────────────────────────
 *
 * *"Aqui só falamos que ele provou algo em jogo, mas não falamos qual foi o leak."* O card mostrava
 * quatro contadores (provados / reabertos / em validação / sem amostra) e nada mais. Um placar sem
 * nome não vira memória nem orgulho, e no caso da REGRESSÃO não vira ação: o alerta vermelho dizia
 * "1 leak regrediu" sem dizer qual, sendo a única coisa ali que exige reação imediata.
 *
 * ── A armadilha, que está declarada no próprio tipo ───────────────────────────────────────────
 *
 * `TrainingProofItem` tem DUAS chaves. `category_key` é a do TREINO e carrega a profundidade;
 * `familia` é a que a MEDIÇÃO usa e ignora profundidade. Rotular pela primeira afirma uma precisão
 * que o número não tem ("Abertura de UTG+1 · 50bb" para uma taxa medida em todas as profundidades)
 * e duplica a mesma família até seis vezes na lista.
 *
 * A página de evolução já resolvia isso. Este teste existe para que o card novo não recrie o erro,
 * que é o padrão deste projeto: a mesma regra aplicada em dois lugares diverge no terceiro.
 */
const SRC = readFileSync("src/pages/Training.tsx", "utf-8");

describe("card de validação — nomeia o leak", () => {
  it("lista os provados, e não só o contador", () => {
    // Exige a CONDIÇÃO que renderiza, não só a presença do texto: desligar o ramo com `{false &&`
    // deixava as strings no arquivo e o teste passava.
    expect(SRC).toMatch(/\{nomesProvados\.length > 0 && \(/);
    expect(SRC).toContain("proof.provedTitle");
    expect(SRC).toMatch(/veredito === "melhorou"[\s\S]{0,400}spotLabel/);
  });

  it("nomeia também os que REGREDIRAM, que é o que exige ação", () => {
    // A primeira versão deste teste só exigia que a string `nomesReabertos` aparecesse no arquivo.
    // Desligar a renderização (`{false && (`) mantinha a declaração da variável e o teste passava:
    // guarda que lê o texto e não o RAMO não cobre nada. Agora exige a condição que o renderiza.
    expect(SRC).toMatch(/\{nomesReabertos\.length > 0 && \(/);
    expect(SRC).toMatch(/nomesReabertos\.join/);
  });

  it("rotula por `familia`, com `category_key` só de reserva", () => {
    // Um refactor que troque a ordem volta a afirmar profundidade que a medição não tem.
    const usos = SRC.match(/spotLabel\(p\.familia \?\? p\.category_key/g) ?? [];
    expect(usos.length, "spotLabel deve partir de familia").toBeGreaterThanOrEqual(2);
    expect(SRC).not.toMatch(/spotLabel\(p\.category_key \?\? p\.familia/);
  });

  it("pede o rótulo SEM profundidade", () => {
    // `stack: true` (o default) reintroduz o "· 50bb" que o número não sustenta.
    const semStack = SRC.match(/stack: false/g) ?? [];
    expect(semStack.length).toBeGreaterThanOrEqual(2);
  });

  it("o número ao lado do nome vem da VALIDAÇÃO, não do delta cru", () => {
    // `delta` não tem intervalo de confiança; a validação tem, e é ela que sustenta a palavra
    // "comprovado". Mostrar o delta ao lado de "comprovado" seria dar régua diferente ao mesmo card.
    expect(SRC).toMatch(/proof\.fromTo[\s\S]{0,200}taxa_antes_ajustada/);
    expect(SRC).not.toMatch(/proof\.fromTo[\s\S]{0,120}p\.delta/);
  });
});

describe("copy do card em 3 locales", () => {
  it("as chaves novas existem e carregam os placeholders", async () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = (await import(`@/i18n/locales/${loc}/training.json`)).default as
        { proof: Record<string, string> };
      expect(d.proof.provedTitle, `${loc}.provedTitle`).toContain("{{count}}");
      expect(d.proof.fromTo, `${loc}.fromTo`).toContain("{{antes}}");
      expect(d.proof.fromTo, `${loc}.fromTo`).toContain("{{depois}}");
      // regra do projeto: sem travessão na copy visível
      expect(d.proof.provedTitle).not.toContain("—");
      expect(d.proof.fromTo).not.toContain("—");
    }
  });
});
