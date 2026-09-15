// @vitest-environment jsdom
/**
 * O proximo nivel e anunciado em ELO, nao em porcentagem.
 *
 * Auditoria TEL-6 (15/09): `/metrics/level` devolve `next_pct` como LIMIAR DE ELO do proximo
 * nivel (o backend anota "agora e ELO threshold"), e o card interpolava esse numero em
 * "{{next}} em {{pct}}%": a tela do coach escrevia "Estudante em 1570%" ao lado do progresso
 * certo ("97% do caminho"). O JSON abaixo e o corpo real da rota despejado pela auditoria.
 */
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import i18n from "@/i18n";
import { LevelCard } from "@/components/hud/LevelCard";

const LEVEL = {
  decisions_scored: 4,
  elo: 1529.2,
  elo_max: 1570,
  elo_min: 0,
  icon: "🎯",
  level: "Iniciante",
  level_max: 1570,
  level_min: 0,
  next_level: "Estudante",
  next_level_icon: "📖",
  next_pct: 1570,
  peak_elo: 1529.2,
  progress: 0.974,
  standard_pct: 72.73,
  top_blocking_leaks: [],
  tournament_count: 1,
} as unknown as Parameters<typeof LevelCard>[0]["data"];

afterEach(cleanup);

describe("LevelCard: o proximo nivel e anunciado em ELO", () => {
  for (const [lang, esperado] of [
    ["pt-BR", /Estudante a partir de 1570 ELO/],
    ["en", /Student from 1570 ELO/],
    ["es", /Estudiante desde 1570 ELO/],
  ] as const) {
    it(`${lang}: escreve o limiar como ELO e nunca como %`, async () => {
      await i18n.changeLanguage(lang);
      render(<MemoryRouter><LevelCard data={LEVEL} compact showStudyLink={false} /></MemoryRouter>);
      expect(screen.getByText(esperado)).toBeTruthy();
      expect(screen.queryByText(/1570\s*%/)).toBeNull();
    });
  }

  it("o progresso continua em porcentagem (97% do caminho), que e o numero certo", async () => {
    await i18n.changeLanguage("pt-BR");
    render(<MemoryRouter><LevelCard data={LEVEL} compact showStudyLink={false} /></MemoryRouter>);
    expect(screen.getByText(/97%/)).toBeTruthy();
  });
});

beforeAll(async () => { await i18n.changeLanguage("pt-BR"); });
