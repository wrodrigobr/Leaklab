import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Nenhum preço escrito à mão na landing nem no checkout.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * O dono decidiu baixar o Pro de R$99 para R$39,90 e disse, olhando o painel do Stripe: *"me
 * parece que já está configurado"*. Consultando a API com a chave live, a conta tinha só R$99 e
 * R$990 — o preço novo nascera no modo de TESTE, que é outra metade da conta.
 *
 * Se eu tivesse trocado o número na tela confiando no painel, **o site anunciaria R$39,90 e o
 * Stripe cobraria R$99,00**. É o defeito mais caro possível: não quebra nada, não gera erro, e o
 * cliente descobre na fatura.
 *
 * Puxando o fio, o mesmo fato estava escrito em CINCO lugares: o `price` do Stripe,
 * `PLAN_AMOUNTS` no backend, `"R$ 99"` cravado no `Landing.tsx`, as chaves `checkout.preco.*` nas
 * três traduções, e um `-17%` literal no JSX do modal — que, com os valores novos, deveria ser
 * 25%.
 *
 * ── A divisão de trabalho entre os dois guardas ───────────────────────────────────────────
 *
 * Este teste impede que a TELA volte a afirmar um número.
 * `backend/scripts/conferir_precos_no_stripe.py` pergunta ao STRIPE se o que o backend serve é o
 * que o cartão é debitado, e quebra o deploy se divergirem. Um sem o outro deixa metade do
 * caminho aberta.
 */

const RAIZ = path.resolve(__dirname, "..", "..");

/** As telas que falam de dinheiro com quem ainda não pagou. */
const ARQUIVOS = [
  path.join(RAIZ, "src", "pages", "Landing.tsx"),
  path.join(RAIZ, "src", "components", "hud", "CheckoutModal.tsx"),
  ...["pt-BR", "en", "es"].flatMap((l) => [
    path.join(RAIZ, "src", "i18n", "locales", l, "landing.json"),
    path.join(RAIZ, "src", "i18n", "locales", l, "dashboard.json"),
  ]),
];

/** Um valor em reais com centavos ou casa de milhar: "R$ 99", "R$ 39,90", "R$1.188". */
const MOEDA = /R\$\s?\d/;

/** Percentual de desconto escrito à mão, do tipo `-17%`. O `%` sozinho é comum e legítimo
 *  (taxa de acerto, frequência de range), então o padrão exige o sinal de menos colado. */
const DESCONTO = /[-−]\s?\d{1,2}\s?%/;

function semComentario(txt: string): string {
  // Tira blocos `/* */` INTEIROS antes de olhar linha a linha. A 1ª versão filtrava só linhas que
  // COMEÇAM com `*` ou `//`, e um comentário JSX de várias linhas tem continuações que não começam
  // com nada — o guarda acusou o próprio comentário que explica o defeito.
  const semBloco = txt.replace(/\/\*[\s\S]*?\*\//g, "");
  return semBloco
    .split("\n")
    .filter((l) => !l.trim().startsWith("//"))
    .join("\n");
}

describe("o preço não é escrito à mão na landing nem no checkout", () => {
  it("nenhum literal de moeda", () => {
    const violacoes: string[] = [];
    for (const arq of ARQUIVOS) {
      if (!fs.existsSync(arq)) continue;
      const corpo = semComentario(fs.readFileSync(arq, "utf-8"));
      corpo.split("\n").forEach((linha, i) => {
        if (MOEDA.test(linha)) {
          violacoes.push(`${path.basename(arq)}:${i + 1}  ${linha.trim().slice(0, 90)}`);
        }
      });
    }
    expect(
      violacoes,
      `preço escrito à mão. O valor tem de vir de /subscription/plans, que o deriva de uma ` +
        `constante conferida contra o Stripe. Um número cravado aqui pode anunciar um valor ` +
        `enquanto o cartão é debitado de outro.`,
    ).toEqual([]);
  });

  it("nenhum desconto escrito à mão", () => {
    const violacoes: string[] = [];
    for (const arq of ARQUIVOS) {
      if (!fs.existsSync(arq) || !arq.endsWith(".tsx")) continue;
      const corpo = semComentario(fs.readFileSync(arq, "utf-8"));
      corpo.split("\n").forEach((linha, i) => {
        // CSS tem percentual negativo legítimo (`radial-gradient(60% 80% at 50% -10%, ...)`).
        // O guarda existe para copy, não para folha de estilo.
        if (/style=|gradient\(|calc\(|translate/.test(linha)) return;
        if (DESCONTO.test(linha)) {
          violacoes.push(`${path.basename(arq)}:${i + 1}  ${linha.trim().slice(0, 90)}`);
        }
      });
    }
    expect(
      violacoes,
      `desconto escrito à mão. Ele é derivado (full_price vs price) e muda sozinho quando o ` +
        `preço muda; um literal envelhece calado — o \`-17%\` daqui já estava errado em 8 pontos.`,
    ).toEqual([]);
  });

  it("os detectores ACHAM uma violação plantada", () => {
    // CONTRAPROVA. Sem ela um regex quebrado deixaria os dois testes verdes para sempre, que é
    // como uma varredura minha já devolveu "nenhuma suspeita" depois de olhar zero arquivos.
    expect(MOEDA.test('price: "R$ 99",')).toBe(true);
    expect(MOEDA.test('"mensal": "R$ 39,90/mês"')).toBe(true);
    expect(DESCONTO.test("                    -17%")).toBe(true);
    // E não podem acusar o que é legítimo: percentual sem sinal, e a moeda vinda de variável.
    expect(MOEDA.test("brl(anual?.monthly_equiv)")).toBe(false);
    expect(DESCONTO.test("Raise 55% · Fold 45%")).toBe(false);
    expect(DESCONTO.test("-{anual.discount_pct}%")).toBe(false);
  });
});
