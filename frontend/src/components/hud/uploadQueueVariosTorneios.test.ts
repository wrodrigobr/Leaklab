import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { notaDeVariosTorneios } from "./UploadQueue";

/**
 * A fila precisa DIZER que um arquivo virou vários torneios (13/09).
 *
 * ── O caso ──────────────────────────────────────────────────────────────────────────────────
 *
 * O export do PartyPoker é por intervalo de datas, não por torneio: o arquivo real de um dos
 * fundadores tem 3.482 mãos e 36 torneios. Até 13/09 o backend gravava tudo como UM torneio, com
 * as mãos de 36 misturadas sob o id de um. Agora ele divide sozinho.
 *
 * O efeito colateral é de TELA: o jogador sobe um arquivo e a lista ganha 36 linhas. Sem uma
 * frase explicando, ele não sabe de onde vieram, nem se alguma ficou de fora. É exatamente a
 * classe de defeito que já escapou aqui antes (bug de vitrine não tem teste e ninguém percebe
 * até o usuário reclamar), então a decisão da nota mora numa função pura e é testada.
 *
 * O guarda de i18n vale para as TRÊS locales de propósito: conferir só o pt-BR deixa en e es
 * envelhecerem calados.
 */
const LOCALES = ["pt-BR", "en", "es"] as const;

/** Um `t` de mentira que devolve a chave e os argumentos: o teste checa a DECISÃO, não a copy. */
const t = (k: string, o?: Record<string, unknown>) => `${k}|${JSON.stringify(o ?? {})}`;

const common = (loc: string) =>
  JSON.parse(readFileSync(`src/i18n/locales/${loc}/common.json`, "utf-8"));

describe("nota de arquivo com vários torneios", () => {
  it("CONTROLE: um torneio só não ganha nota", () => {
    // 97% dos uploads do acervo. Nota óbvia em caso óbvio é ruído.
    expect(notaDeVariosTorneios({ torneios_no_arquivo: 1 }, t)).toBeUndefined();
    expect(notaDeVariosTorneios({}, t)).toBeUndefined();
    expect(notaDeVariosTorneios(null, t)).toBeUndefined();
  });

  it("vários torneios, todos importados: diz quantos", () => {
    const nota = notaDeVariosTorneios(
      { torneios_no_arquivo: 12, tambem_importados: Array(11).fill({ status: 200 }) }, t);
    expect(nota).toContain("uploadQueue.variosTorneios|");
    expect(nota).not.toContain("Parcial");
    expect(nota).toContain('"n":12');
  });

  it("com falhas: a conta de importados DESCONTA os que ficaram de fora", () => {
    // O erro fácil aqui é dizer "12 importados" quando 3 falharam. A nota mentiria sobre o que
    // está no histórico, e o jogador procuraria torneios que não existem.
    const nota = notaDeVariosTorneios({
      torneios_no_arquivo: 12,
      tambem_importados: [
        ...Array(8).fill({ status: 200 }),
        { status: 422 }, { status: 422 }, { status: 500 },
      ],
    }, t);
    expect(nota).toContain("uploadQueue.variosTorneiosParcial|");
    expect(nota).toContain('"ok":9');    // 12 do arquivo menos os 3 que não entraram
    expect(nota).toContain('"fora":3');
  });

  it("as duas chaves existem nas 3 locales, com os mesmos placeholders", () => {
    for (const loc of LOCALES) {
      const uq = common(loc).uploadQueue ?? {};
      expect(uq.variosTorneios, `${loc}: falta variosTorneios`).toBeTruthy();
      expect(uq.variosTorneiosParcial, `${loc}: falta variosTorneiosParcial`).toBeTruthy();
      // Placeholder faltando numa locale é o jeito silencioso de a frase sair pela metade.
      expect(uq.variosTorneios, `${loc}: variosTorneios sem {{n}}`).toContain("{{n}}");
      for (const ph of ["{{n}}", "{{ok}}", "{{fora}}"]) {
        expect(uq.variosTorneiosParcial, `${loc}: variosTorneiosParcial sem ${ph}`).toContain(ph);
      }
    }
  });

  it("FIACAO: a fila realmente usa a função na conclusão do upload", () => {
    // Função pura testada e nunca chamada é cobertura sem cobertura.
    const src = readFileSync("src/components/hud/UploadQueue.tsx", "utf-8");
    expect(src, "a fila parou de chamar notaDeVariosTorneios ao concluir")
      .toContain("note: notaDeVariosTorneios(r, t)");
  });
});
