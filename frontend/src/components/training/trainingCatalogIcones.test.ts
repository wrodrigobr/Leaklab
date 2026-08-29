import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Todo drill que o backend serve tem ícone próprio no catálogo.
 *
 * ── O que originou (30/08) ────────────────────────────────────────────────────────────────
 *
 * O conjunto A aprovado pelo dono NÃO subiu: o mapa usava os ids de `leak_trainer.CATALOGO_TREINOS`
 * (`fund_rfi`...), mas a API serve os de `trainer_catalog.CATALOGO` (`abrir`, `defender`...).
 * O mapa nunca casava, tudo caía na MiniRange, e só o print do dono mostrou. Suposição sobre o
 * nosso próprio produto morrendo na conferência, de novo.
 *
 * Este guarda lê os ids DO PRÓPRIO arquivo do backend e exige: cada id ou é o destaque (mira),
 * ou está no mapa de ícones. Drill novo no backend sem ícone falha aqui, não na tela.
 */

const BACKEND = path.join(__dirname, "../../../../backend/leaklab/trainer_catalog.py");
const FRONT = path.join(__dirname, "TrainingCatalog.tsx");

describe("ícones do catálogo de treino", () => {
  const py = fs.readFileSync(BACKEND, "utf-8");
  const ids = [...py.matchAll(/\{'id':\s*'([a-z_0-9]+)'/g)].map((m) => m[1]);
  const fonte = fs.readFileSync(FRONT, "utf-8");
  const mapa = fonte.match(/const ILUSTRACAO_POR_DRILL[\s\S]*?=\s*\{([\s\S]*?)\};/);
  const chaves = mapa ? [...mapa[1].matchAll(/^\s*([a-z_0-9]+):/gm)].map((m) => m[1]) : [];

  it("a varredura enxerga o backend (senão aprova o vazio)", () => {
    expect(ids.length, "nenhum id lido de trainer_catalog.py").toBeGreaterThan(3);
    expect(chaves.length, "mapa de ícones não encontrado no componente").toBeGreaterThan(3);
  });

  it("todo id servido tem ícone (ou é o destaque)", () => {
    const destaque = new Set(["meus_leaks"]);
    const sem = ids.filter((i) => !destaque.has(i) && !chaves.includes(i));
    expect(sem, "drill servido pela API sem ícone no mapa — cai na matriz genérica").toEqual([]);
  });

  it("o mapa não guarda id que o backend não serve", () => {
    const mortos = chaves.filter((c) => !ids.includes(c));
    expect(mortos, "id no mapa que a API não serve — foi assim que o conjunto A não subiu")
      .toEqual([]);
  });
});
