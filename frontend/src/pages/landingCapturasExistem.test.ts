import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Toda captura que a landing referencia existe no `public/`.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * A seção "O produto" passava três caminhos de imagem (`/landing/veredito.webp` e companhia). A
 * pasta `frontend/public/landing/` **nunca existiu**. O componente caía no `onError` e renderizava
 * uma caixa tracejada dizendo "captura pendente" com o caminho do arquivo em fonte mono, que era
 * um lembrete que eu tinha escrito para mim.
 *
 * Foi para produção. O `main-CkqZOPrS.js` publicado em grindlabpoker.com continha, literalmente,
 * "captura pendente" e "landing/veredito.webp" — e três dos quatro blocos mostravam isso para quem
 * chegava no site. Encontrado no ARTEFATO PUBLICADO, não no fonte: o fonte parecia certo, porque
 * o defeito era um arquivo que não estava lá.
 *
 * ── Por que este guarda, e não só a correção no componente ────────────────────────────────
 *
 * O componente agora esconde o bloco quando a imagem falha, o que é melhor para o visitante mas
 * PIOR para quem mantém: um arquivo faltando vira um bloco que some calado. A caixa tracejada
 * pelo menos gritava. Este teste devolve o grito no lugar certo, que é a build.
 *
 * Hoje o `Landing.tsx` não referencia captura nenhuma (os três blocos saíram até as capturas
 * existirem), então a lista está vazia e o guarda passa sem nada para conferir. **Por isso a
 * contraprova mede o LEITOR contra uma amostra, e não contra o arquivo vivo**: ancorada no
 * arquivo, ela viraria a asserção "existe pelo menos um print", que é falsa hoje e me obrigaria a
 * escolher entre apagar o guarda e mentir. Leitor quebrado devolve `[]`, e `[]` passa.
 */

const RAIZ = path.resolve(__dirname, "..", "..");
const LANDING = path.join(RAIZ, "src", "pages", "Landing.tsx");
const PUBLIC = path.join(RAIZ, "public");

/** Os caminhos de `print:` declarados num fonte de landing.
 *
 *  O `\b` não é decoração: sem ele o padrão casa dentro de `sprint:`, e a própria contraprova
 *  abaixo pegou isso na primeira execução. Um leitor que casa demais inventa caminho faltando e
 *  quebra a build por nada, que é o jeito mais rápido de um guarda ser desligado. */
export function capturasReferenciadas(fonte: string): string[] {
  return [...fonte.matchAll(/\bprint:\s*"([^"]+)"/g)].map((m) => m[1]);
}

describe("as capturas que a landing referencia existem", () => {
  it("o leitor ACHA um print numa amostra, e ignora o que não é print", () => {
    const amostra = `
      { rotulo: t("x"), print: "/landing/veredito.webp" },
      { rotulo: t("y") },
      { sprint: "/nao/e/print.webp" },
    `;
    expect(capturasReferenciadas(amostra)).toEqual(["/landing/veredito.webp"]);
    expect(capturasReferenciadas("nenhum print aqui")).toEqual([]);
  });

  it("todo caminho referenciado tem arquivo no public/", () => {
    const fonte = fs.readFileSync(LANDING, "utf-8");
    const faltando = capturasReferenciadas(fonte).filter(
      (src) => !fs.existsSync(path.join(PUBLIC, src.replace(/^\//, ""))),
    );
    expect(
      faltando,
      `capturas referenciadas pela landing que não existem em public/. O bloco delas some ` +
        `silenciosamente no site publicado. Capture os arquivos ou remova o "print:" do ` +
        `Landing.tsx, mas não publique o caminho de um arquivo que não existe.`,
    ).toEqual([]);
  });

  it("nenhum aviso de obra sobrou na landing ou nos seus componentes", () => {
    // A mesma doença apareceu em TRÊS lugares: a caixa "captura pendente", o slot de vídeo com
    // "em gravação", e o comentário que justificava os dois ("vazio silencioso parece
    // proposital"). Varrer os três de uma vez é o que impede o quarto.
    const arquivos = [
      LANDING,
      ...fs
        .readdirSync(path.join(RAIZ, "src", "components", "landing"))
        .filter((f) => f.endsWith(".tsx") && !f.endsWith(".test.tsx"))
        .map((f) => path.join(RAIZ, "src", "components", "landing", f)),
    ];
    const semComentario = (txt: string) =>
      txt
        .split("\n")
        .filter((l) => !l.trim().startsWith("*") && !l.trim().startsWith("//"))
        .join("\n");

    const violacoes: string[] = [];
    for (const arq of arquivos) {
      const corpo = semComentario(fs.readFileSync(arq, "utf-8"));
      if (/captura pendente|em grava[çc][ãa]o|coming soon|em breve/i.test(corpo)) {
        violacoes.push(path.basename(arq));
      }
    }
    expect(
      violacoes,
      `aviso de obra renderizável na landing pública. Quem constrói é avisado pela build, não ` +
        `pela tela do visitante.`,
    ).toEqual([]);
  });
});
