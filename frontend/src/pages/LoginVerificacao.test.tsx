// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

/**
 * A tela de confirmação de e-mail não pode mais ser um beco sem saída.
 *
 * **O caso real:** um usuário se cadastrou pelo celular, saiu sem querer da tela do código e ficou
 * com o código na mão, sem onde digitá-lo. A tela vivia só na memória da página; trocar de app
 * bastava para perdê-la. A saída existia — tentar entrar devolve `email_unverified` e reenvia —
 * mas nada na interface dizia isso, então só era encontrada por acidente.
 *
 * Os três caminhos que passam a existir, e que este arquivo trava:
 *   1. o link do e-mail conclui num clique (`?verificar=&codigo=`);
 *   2. o e-mail pendente vive na URL, então recarregar devolve a tela;
 *   3. há um link VISÍVEL de recuperação na tela de login.
 */
// `vi.mock` é içado para o topo do arquivo, então as fábricas não podem fechar sobre variáveis
// declaradas aqui em cima. `vi.hoisted` sobe junto com elas.
const { verifyEmail, resendCode } = vi.hoisted(() => ({
  verifyEmail: vi.fn(), resendCode: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: "pt-BR" } }),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ login: vi.fn(), register: vi.fn(), verifyEmail, user: null }),
}));
vi.mock("@/lib/api", () => ({
  auth: { resendCode, forgotPassword: vi.fn(), resetPassword: vi.fn() },
}));

import Login from "./Login";

function montar(url: string) {
  return render(<MemoryRouter initialEntries={[url]}><Login /></MemoryRouter>);
}

beforeEach(() => { verifyEmail.mockReset(); verifyEmail.mockResolvedValue(null); resendCode.mockReset(); });
afterEach(() => cleanup());

describe("confirmação de e-mail — o link do e-mail", () => {
  it("com e-mail e código na URL, confirma sozinho", async () => {
    montar("/login?verificar=alguem%40exemplo.com&codigo=778899");
    await waitFor(() =>
      expect(verifyEmail).toHaveBeenCalledWith("alguem@exemplo.com", "778899"));
  });

  it("não entra em laço quando o código do link é recusado", async () => {
    // Um código expirado no link não pode virar tentativa infinita.
    verifyEmail.mockRejectedValue({ code: "expired" });
    montar("/login?verificar=alguem%40exemplo.com&codigo=000000");
    await waitFor(() => expect(verifyEmail).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 250));
    expect(verifyEmail).toHaveBeenCalledTimes(1);
  });
});

describe("confirmação de e-mail — a tela deixa de ser volátil", () => {
  it("só com o e-mail na URL, devolve a tela do código sem confirmar nada", async () => {
    montar("/login?verificar=alguem%40exemplo.com");
    // A tela aparece (o e-mail é exibido nela)...
    await waitFor(() => expect(screen.getByText(/alguem@exemplo\.com/)).toBeTruthy());
    // ...e NÃO tenta confirmar, porque não veio código.
    expect(verifyEmail).not.toHaveBeenCalled();
  });
});

describe("confirmação de e-mail — a saída visível", () => {
  it("a tela de login oferece o caminho de quem não confirmou", () => {
    montar("/login");
    expect(screen.getByText("verify.recoverLink"), "sem saída visível na tela de login").toBeTruthy();
  });

  it("a copy dos caminhos novos existe nas 3 locales", () => {
    for (const loc of ["pt-BR", "en", "es"]) {
      const d = JSON.parse(readFileSync(`src/i18n/locales/${loc}/auth.json`, "utf-8"));
      expect(d.verify?.recoverLink, `${loc}: verify.recoverLink ausente`).toBeTruthy();
      expect(d.verify?.recoverNoEmail, `${loc}: verify.recoverNoEmail ausente`).toBeTruthy();
    }
  });

  it("o código sai da URL antes do envio, e o e-mail fica", () => {
    // O código não pode ficar no histórico do navegador nem vazar por Referer; o `verificar`
    // fica, porque é ele que devolve a tela num recarregamento.
    const src = readFileSync("src/pages/Login.tsx", "utf-8");
    expect(src).toMatch(/setSearchParams\(\{\s*verificar:\s*pendingEmail\s*\}/);
  });
});
