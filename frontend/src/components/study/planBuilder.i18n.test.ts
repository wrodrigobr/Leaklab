import { describe, it, expect } from "vitest";
import i18next from "i18next";
import { buildStudyPlan } from "./planBuilder";
import ptBR from "@/i18n/locales/pt-BR/study.json";
import en from "@/i18n/locales/en/study.json";
import es from "@/i18n/locales/es/study.json";
import type { StudyPlanResponse } from "@/lib/api";

/**
 * A copy do plano de estudo nasceu cravada em português porque `buildStudyPlan` é função pura,
 * fora da árvore do React, e não tinha por onde chamar `useTranslation`. Agora recebe o `t`.
 *
 * O teste do backend (`test_i18n_copy_do_frontend.py`) confere que toda chave pedida existe
 * nos três locales. Este confere o outro lado: que a FIAÇÃO funciona — o plano montado com o
 * `t` de verdade sai traduzido, e não com a chave crua na tela.
 */

const LOCALES = { "pt-BR": ptBR, en, es } as const;

function traduzPara(idioma: keyof typeof LOCALES) {
  const inst = i18next.createInstance();
  inst.init({
    lng: idioma,
    resources: { [idioma]: { study: LOCALES[idioma] } },
    defaultNS: "study",
    // Sem fallback: se a chave faltar neste idioma, quero ver o buraco, não o português.
    fallbackLng: false,
    interpolation: { escapeValue: false },
  });
  return (chave: string, opcoes?: Record<string, unknown>) => inst.t(chave, opcoes) as string;
}

// Resposta MÍNIMA do backend: sem cards, todo texto do plano vem dos fallbacks — que é
// exatamente onde morava a maior parte da copy cravada.
const SEM_CARDS: StudyPlanResponse = { cards: [] } as unknown as StudyPlanResponse;

function textosDoPlano(idioma: keyof typeof LOCALES): string[] {
  const plano = buildStudyPlan(SEM_CARDS, traduzPara(idioma));
  return plano.weeks.flatMap((w) => [
    w.focus,
    ...w.days.flatMap((d) => [d.title, d.topic, ...d.objectives]),
  ]);
}

describe("plano de estudo traduzido", () => {
  it.each(["pt-BR", "en", "es"] as const)("%s não vaza chave crua para a tela", (idioma) => {
    const textos = textosDoPlano(idioma);
    expect(textos.length).toBeGreaterThan(30);

    const cruas = textos.filter((t) => /^planBuilder\./.test(t) || t.includes("planBuilder."));
    expect(cruas, `chaves sem tradução em ${idioma}`).toEqual([]);

    // e nada de placeholder por interpolar
    const naoInterpolados = textos.filter((t) => t.includes("{{"));
    expect(naoInterpolados, `placeholder não interpolado em ${idioma}`).toEqual([]);
  });

  it("cada idioma produz texto PRÓPRIO, e não o português para todos", () => {
    const pt = textosDoPlano("pt-BR");
    const ingles = textosDoPlano("en");
    const espanhol = textosDoPlano("es");

    // O controle que importa: se o `t` fosse ignorado e a copy voltasse a ser cravada, os três
    // sairiam idênticos e o teste acima ainda passaria.
    expect(ingles).not.toEqual(pt);
    expect(espanhol).not.toEqual(pt);
    expect(ingles[0]).toBe("Fundamentals: Critical Leaks");
    expect(pt[0]).toBe("Fundamentos: Leaks Críticos");
  });

  it("interpola os números que a copy carrega", () => {
    const textos = textosDoPlano("en");
    expect(textos.some((t) => t.includes("20+ hands"))).toBe(true);
    expect(textos.some((t) => t.includes("80%+ accuracy"))).toBe(true);
  });
});
