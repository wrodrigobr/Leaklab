/**
 * O container de rolagem do Leak Trainer, e as três coisas que ele precisa fazer ao mesmo tempo.
 *
 * As três nasceram de defeitos reportados, e a terceira nasceu do conserto da primeira:
 *
 * 1. **`justify-start`, não `justify-center`.** Quando o conteúdo transborda um flex container
 *    centralizado, o excesso de CIMA fica fora do alcance da rolagem — o navegador não rola para
 *    antes do início da caixa. Era o "as barras de rolagem não são suficientes pra subir até o
 *    topo do componente" no celular.
 *
 * 2. **`pb-20 lg:pb-0`.** Esta tela é uma casca `h-dvh` com rolagem própria, então o recuo dos
 *    containers de página não a alcança, e a barra de navegação `fixed bottom-0` do mobile cobria
 *    o botão do rodapé. Era o "o botão amarelo no rodapé não aparece por completo".
 *
 * 3. **`my-auto`, e NUNCA `m-auto`.** Esta é a regressão que o conserto do item 1 criou. Margem
 *    automática também no eixo HORIZONTAL cancela o `align-items: stretch` do flex-column, e o
 *    filho passa a ter a largura do próprio conteúdo. Como a mesa é `aspect-[16/10] h-full w-auto`,
 *    a largura virava altura × 1,6: estourava a viewport, empurrava o painel de ações para fora da
 *    tela e criava barra de rolagem horizontal no desktop.
 *
 * É um teste de TEXTO porque jsdom não calcula layout: ele não computaria a largura nem em tese.
 * O que dá para travar é a classe, e a classe é a causa.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const fonte = readFileSync(join(__dirname, "LeakTrainer.tsx"), "utf-8");

/** A linha do container de rolagem, sem comentários (senão a explicação do bug conta como bug). */
function containerDeRolagem(): string {
  const semComentarios = fonte
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");
  const linha = semComentarios
    .split("\n")
    .find((l) => l.includes("overflow-y-auto") && l.includes("flex-col") && l.includes("flex-1"));
  expect(linha, "não achei o container de rolagem — o teste passaria sem ler nada").toBeTruthy();
  return linha as string;
}

describe("container de rolagem do Leak Trainer", () => {
  it("ancora no topo em vez de centralizar, senão o excesso de cima fica inalcançável", () => {
    const l = containerDeRolagem();
    expect(l).toContain("justify-start");
    expect(l).not.toContain("justify-center");
  });

  it("reserva o espaço da barra de navegação do mobile, e só do mobile", () => {
    const l = containerDeRolagem();
    expect(l).toMatch(/\bpb-20\b/);
    expect(l).toMatch(/\blg:pb-0\b/);
  });

  it("centra só no eixo vertical: m-auto quebra o stretch e estoura a largura", () => {
    const l = containerDeRolagem();
    expect(l).toContain("[&>*]:my-auto");
    // a asserção que importa: margem automática nos DOIS eixos derruba o desktop
    expect(l, "m-auto cancela o stretch horizontal e cria barra de rolagem lateral")
      .not.toMatch(/\[&>\*\]:m-auto/);
  });
});

describe("a mesa continua sem largura própria", () => {
  it("a mesa deriva a largura da altura, então quem a contém precisa poder encolher", () => {
    // Se a mesa ganhasse largura fixa, o `min-w-0` do pai deixaria de bastar e o overflow
    // voltaria por outro caminho.
    expect(fonte).toContain("aspect-[16/10]");
    expect(fonte).toMatch(/min-w-0[^"]*flex-1|flex-1[^"]*min-w-0/);
  });
});
