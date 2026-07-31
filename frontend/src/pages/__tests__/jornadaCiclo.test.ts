import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";

/**
 * A jornada Treinar → Jogar → Validar é um CICLO, e o cadeado é recomendação, não bloqueio.
 *
 * ── O bug que o usuário achou ─────────────────────────────────────────────────────────────────
 *
 * A condição do passo "jogar" era `dominadas.length ? ... : "locked"`. `dominadas` é a lista
 * histórica de leaks já dominados, então **ter dominado um leak na vida destravava o passo para
 * sempre**. Cinco leaks novos podiam aparecer que ele nunca mais fechava. Nas palavras dele: *"o
 * problema é que o ciclo nunca reiniciava"*.
 *
 * A condição correta é haver leak EM TREINO agora (`foco`), porque leak novo repõe o foco e o
 * ciclo fecha de novo.
 *
 * ── O que o cadeado NÃO é ─────────────────────────────────────────────────────────────────────
 *
 * Ele nunca bloqueou nada, e não deve. O aluno joga e importa quando quiser, e a tela precisa
 * dizer isso: sem torneio novo não há amostra, e sem amostra não há validação. Um cadeado sem essa
 * nota lê como "pare de jogar até treinar", que desincentiva exatamente o que alimenta o sistema.
 */
const SRC = readFileSync("src/pages/Training.tsx", "utf-8");

describe("jornada — o ciclo reinicia", () => {
  it("o passo jogar depende do FOCO atual, não do histórico de dominados", () => {
    expect(SRC).toMatch(/key: "apply"[\s\S]{0,300}status: foco \? "locked"/);
    // a condição antiga não pode voltar
    expect(SRC).not.toMatch(/key: "apply"[\s\S]{0,200}dominadas\.length \? \(proof/);
  });

  it("o passo validar também não destrava enquanto houver leak em treino", () => {
    expect(SRC).toMatch(/key: "prove"[\s\S]{0,200}!foco && proof\.length/);
  });
});

describe("jornada — o cadeado é recomendação, não bloqueio", () => {
  it("a nota que diz que jogar é sempre permitido aparece junto do cadeado", () => {
    expect(SRC).toMatch(/\{foco && \([\s\S]{0,400}journey\.lockNote/);
  });

  it("a nota existe nas 3 locales e diz que pode jogar", async () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = (await import(`@/i18n/locales/${loc}/training.json`)).default as
        { journey: Record<string, unknown> };
      const nota = d.journey.lockNote as string;
      expect(nota, `${loc}.journey.lockNote`).toBeTruthy();
      expect(nota.length).toBeGreaterThan(30);
      expect(nota).not.toContain("—");
    }
  });
});
