import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Nenhuma superfície de JOGADOR nomeia o fornecedor de IA.
 *
 * ── O que originou (30/08, véspera de lançamento) ─────────────────────────────────────────
 *
 * O dono achou "Powered by Claude AI" na landing. A regra já existia
 * ([[feedback_branding_gto_solver]]: o que vende é veredito de SOLVER; concorrente é que
 * vende "IA") e vazou mesmo assim — regra sem guarda é pedido, não regra.
 *
 * Varre i18n e .tsx por nomes de fornecedor. "IA"/"AI" genérico é permitido (o AI Coach é
 * feature); o BANIDO é a marca do fornecedor na tela do jogador.
 */

const SRC = path.join(__dirname, "..");
const BANIDOS = /claude|anthropic|powered by/i;

function arquivos(d: string): string[] {
  return fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) return arquivos(p);
    return /\.(tsx|json)$/.test(e.name) && !/\.test\./.test(e.name) ? [p] : [];
  });
}

describe("branding: solver na frente, fornecedor invisível", () => {
  it("nenhum arquivo de tela ou copy nomeia o fornecedor", () => {
    const violacoes: string[] = [];
    for (const f of arquivos(SRC)) {
      const texto = fs.readFileSync(f, "utf-8");
      const linhas = texto.split("\n");
      linhas.forEach((l, i) => {
        // comentário de código não vai para a tela; copy e JSX vão
        const semComentario = l.replace(/\/\/.*$/, "").replace(/\/\*.*?\*\//g, "");
        if (BANIDOS.test(semComentario)) {
          violacoes.push(`${path.relative(SRC, f)}:${i + 1} ${l.trim().slice(0, 80)}`);
        }
      });
    }
    expect(violacoes, "marca de fornecedor em superfície de jogador").toEqual([]);
  });
});
