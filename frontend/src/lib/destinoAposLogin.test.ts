import { describe, it, expect } from "vitest";
import { urlDeLoginPara, destinoSeguro } from "./destinoAposLogin";

/**
 * O destino sobrevive ao login, e só destino INTERNO sobrevive.
 *
 * ── Por que este arquivo existe ───────────────────────────────────────────────────────────────
 *
 * Medido: os guardas de rota descartavam o destino e o login navegava para `/dashboard`
 * hard-coded. Somado ao token viver em `sessionStorage` (por aba), TODO clique de e-mail
 * terminava no dashboard — e o e-mail existe justamente para quem não está com o app aberto.
 * A prescrição prometia "um clique e você está treinando".
 *
 * A metade defensiva importa igual: `?next=` sem validação é open redirect, e open redirect no
 * nosso domínio é phishing com a nossa credibilidade emprestada.
 */
describe("destino após login — preserva", () => {
  it("guarda o caminho e a query do CTA de e-mail", () => {
    expect(urlDeLoginPara("/leak-trainer", "?foco=leak:rfi:HJ::50&origem=email"))
      .toBe("/login?next=" + encodeURIComponent("/leak-trainer?foco=leak:rfi:HJ::50&origem=email"));
  });

  it("devolve o caminho quando ele é interno", () => {
    expect(destinoSeguro(encodeURIComponent("/leak-trainer?origem=email")))
      .toBe("/leak-trainer?origem=email");
    expect(destinoSeguro("/evolucao")).toBe("/evolucao");
  });

  it("ida e volta: o que o guarda monta, o login lê", () => {
    const url = urlDeLoginPara("/leak-trainer", "?foco=leak:vs_rfi:BB:LJ:30&origem=email");
    const next = new URLSearchParams(url.split("?")[1]).get("next");
    expect(destinoSeguro(next)).toBe("/leak-trainer?foco=leak:vs_rfi:BB:LJ:30&origem=email");
  });

  it("não cria laço mandando o login para o login", () => {
    expect(urlDeLoginPara("/login")).toBe("/login");
    expect(urlDeLoginPara("/")).toBe("/login");
    expect(destinoSeguro("/login?next=/x")).toBeNull();
  });
});

describe("destino após login — recusa (open redirect)", () => {
  it("recusa destino externo", () => {
    for (const mau of [
      "https://site-falso.com",
      "http://site-falso.com/login",
      "//site-falso.com",                    // protocol-relative: sai do domínio
      "/\\site-falso.com",                   // alguns navegadores normalizam para //
      "javascript:alert(1)",
      "data:text/html,<script>1</script>",
      "site-falso.com",
    ]) {
      expect(destinoSeguro(mau), `deixou passar: ${mau}`).toBeNull();
      expect(destinoSeguro(encodeURIComponent(mau)), `deixou passar codificado: ${mau}`).toBeNull();
    }
  });

  it("recusa vazio e percent-encoding quebrado", () => {
    expect(destinoSeguro(null)).toBeNull();
    expect(destinoSeguro("")).toBeNull();
    expect(destinoSeguro("%E0%A4%A")).toBeNull();   // não adivinha: descarta
  });
});
