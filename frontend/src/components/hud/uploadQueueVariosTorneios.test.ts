import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { notaDeVariosTorneios, contagemDoArquivo } from "./UploadQueue";

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

  it('"já estava no histórico" NÃO conta como ficou de fora', () => {
    // Achado na homologação, com upload real de arquivo repetido contra o Postgres. O export do
    // PartyPoker é por intervalo de datas: quem reexporta uma semana reenvia a anterior inteira.
    // Dizer "30 ficaram de fora" para 30 torneios que estão lá manda o jogador procurar dado que
    // não falta — e o backend já distinguia os dois casos (409 `duplicate` contra erro de fato).
    const nota = notaDeVariosTorneios({
      torneios_no_arquivo: 36,
      tambem_importados: [
        ...Array(5).fill({ status: 200 }),
        ...Array(30).fill({ status: 409, duplicate: true }),
      ],
    }, t);
    expect(nota).toContain("uploadQueue.variosTorneiosJaEstavam|");
    expect(nota).toContain('"ja":30');
    expect(nota).toContain('"ok":6');   // 36 menos os 30 que já estavam
    expect(nota, "duplicado virou falha").not.toContain("fora");
  });

  it("já estavam E falharam: a frase mista separa as duas coisas", () => {
    const nota = notaDeVariosTorneios({
      torneios_no_arquivo: 36,
      tambem_importados: [
        ...Array(28).fill({ status: 409, duplicate: true }),
        { status: 422 }, { status: 500 },
        ...Array(5).fill({ status: 200 }),
      ],
    }, t);
    expect(nota).toContain("uploadQueue.variosTorneiosMisto|");
    expect(nota).toContain('"ja":28');
    expect(nota).toContain('"fora":2');
    expect(nota).toContain('"ok":6');   // 36 - 28 - 2
  });

  it("as quatro chaves existem nas 3 locales, com os mesmos placeholders", () => {
    const exigidos: Record<string, string[]> = {
      variosTorneios: ["{{n}}"],
      variosTorneiosParcial: ["{{n}}", "{{ok}}", "{{fora}}"],
      variosTorneiosJaEstavam: ["{{n}}", "{{ok}}", "{{ja}}"],
      variosTorneiosMisto: ["{{n}}", "{{ok}}", "{{ja}}", "{{fora}}"],
    };
    for (const loc of LOCALES) {
      const uq = common(loc).uploadQueue ?? {};
      for (const [chave, phs] of Object.entries(exigidos)) {
        expect(uq[chave], `${loc}: falta ${chave}`).toBeTruthy();
        // Placeholder faltando numa locale é o jeito silencioso de a frase sair pela metade.
        for (const ph of phs) {
          expect(uq[chave], `${loc}: ${chave} sem ${ph}`).toContain(ph);
        }
      }
    }
  });

  it("o XP conta os torneios que ENTRARAM, nem o arquivo nem os repetidos", () => {
    // Decisão do dono, 13/09: "acho que deveria ser por torneio". Quem sobe 36 torneios num
    // export do PartyPoker ganhava o XP de um. Os que já estavam no histórico não contam —
    // não é jogo novo, é o mesmo arquivo reexportado.
    const r = {
      torneios_no_arquivo: 36,
      tambem_importados: [
        ...Array(28).fill({ status: 409, duplicate: true }),
        { status: 422 },
        ...Array(6).fill({ status: 200 }),
      ],
    };
    expect(contagemDoArquivo(r).ok, "XP contaria repetido ou falha").toBe(7);   // 36 - 28 - 1
    // arquivo de um torneio só continua valendo um
    expect(contagemDoArquivo({}).ok).toBe(1);
    expect(contagemDoArquivo(null).ok).toBe(1);
  });

  it("a frase e o XP saem da MESMA contagem", () => {
    // O defeito que isto impede: a tela dizer "6 novos" e o contador somar 36. Duas leituras da
    // mesma resposta divergindo é a família de bug que a regra 5 existe para matar.
    const r = {
      torneios_no_arquivo: 36,
      tambem_importados: [
        ...Array(30).fill({ status: 409, duplicate: true }),
        ...Array(5).fill({ status: 200 }),
      ],
    };
    const nota = notaDeVariosTorneios(r, t)!;
    const okDaNota = JSON.parse(nota.split("|")[1]).ok;
    expect(okDaNota).toBe(contagemDoArquivo(r).ok);
  });

  it("FIACAO: o XP recebe a quantidade, e o VALOR fica no backend", () => {
    // 14/09: o upload passou a ser assíncrono (`POST /uploads` devolve recibo e o consumer
    // processa), então a quantidade vem do RECIBO e não da resposta síncrona. O que este guarda
    // defende não mudou: um XP por torneio que entrou, e o VALOR de cada um fica no backend.
    const src = readFileSync("src/components/hud/UploadQueue.tsx", "utf-8");
    expect(src, "o XP voltou a ser um por arquivo")
      .toContain("r.torneios_gravados");
    // E o front não pode multiplicar por valor nenhum: a tabela `_XP_AMOUNTS` mora no backend.
    expect(src, "o front passou a calcular o VALOR do XP, que é regra do backend")
      .not.toMatch(/addXp\([^)]*\*\s*\d/);
  });

  it("regra 5: existe UM lugar que concede o XP de import, não dois", () => {
    // Isto existe porque a primeira versão da correção do XP falhou exatamente aqui: eu passei
    // a contagem no ramo normal e deixei o ramo `analysis_waitlisted` (Free, fila de análise)
    // dando um XP por ARQUIVO. Mesma regra em dois lugares, o segundo errado e calado.
    // O comentário é apagado antes da varredura: senão o guarda casa com a própria explicação.
    const src = readFileSync("src/components/hud/UploadQueue.tsx", "utf-8")
      .replace(/\/\/.*/g, "");
    const chamadas = [...src.matchAll(/addXp\(\s*"tournament_imported"/g)];
    expect(chamadas.length, "o XP de import voltou a ser concedido em mais de um lugar").toBe(1);
    // e a única chamada leva a quantidade, não um XP solto
    expect(src, "a única chamada de XP parou de levar a quantidade de torneios")
      .toMatch(/addXp\([^)]*novos\)/);
    // 14/09: com o upload assíncrono o recibo ACUMULA `torneios_gravados` entre retomadas (um
    // arquivo pausado por cota volta com o que já entrou). Conceder pelo total pagaria os mesmos
    // torneios duas vezes, uma na pausa e outra na conclusão. Só o DELTA conta.
    expect(src, "o XP voltou a ser concedido pelo total acumulado, e não pelo delta")
      .toMatch(/const novos = gravados - \(item\.xpDado \?\? 0\)/);
    expect(src, "o front parou de lembrar quanto XP já concedeu para este arquivo")
      .toContain('type: "SET_XP_DADO"');
  });

  it("a fila de análise NÃO engole a frase dos vários torneios", () => {
    // Jogador Free que sobe um export do PartyPoker precisa das duas informações: quantos
    // torneios entraram, e que a análise GTO está na fila.
    // Esta frase desapareceu calada na primeira versão do upload assíncrono, porque o recibo
    // não carregava `analysis_waitlisted`. Foi este guarda que pegou.
    const src = readFileSync("src/components/hud/UploadQueue.tsx", "utf-8");
    expect(src, "a nota da fila de análise substituiu a do arquivo em vez de somar")
      .toContain('[varios, t("uploadQueue.analiseNaFila")].filter(Boolean).join(" ")');
    expect(src, "o front parou de ler `analysis_waitlisted` do recibo, então a frase nunca sai")
      .toContain("d.analysis_waitlisted");
  });

  it("FIACAO: a fila realmente usa a função na conclusão do upload", () => {
    // Função pura testada e nunca chamada é cobertura sem cobertura.
    const src = readFileSync("src/components/hud/UploadQueue.tsx", "utf-8");
    expect(src, "a fila parou de calcular a nota do arquivo")
      .toContain("notaDaContagem(contagemDoRecibo(r), t)");
    // e o resultado tem de CHEGAR ao dispatch de conclusão. Calcular e jogar fora é o furo que
    // já apareceu hoje: o guarda de texto passa verde porque a chamada continua no arquivo.
    expect(src, "a nota é calculada e não chega à fila")
      .toContain('status: "done", note });');
    // O caminho síncrono (`notaDeVariosTorneios`) fica de pé: ele ainda serve o ramo do
    // Tournament Summary e o `/analyze`, que não foi desligado por causa de bundle em cache.
    expect(src, "a fachada síncrona da nota foi removida")
      .toContain("export function notaDeVariosTorneios");
  });
});
