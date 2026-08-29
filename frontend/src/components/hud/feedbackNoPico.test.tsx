// @vitest-environment jsdom
import fs from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FeedbackNoPico } from "./FeedbackNoPico";

const contact = vi.fn().mockResolvedValue({});
vi.mock("@/lib/api", () => ({ support: { contact: (...a: unknown[]) => contact(...a) } }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

afterEach(() => { cleanup(); contact.mockClear(); });

/**
 * Feedback no PICO — os contratos que fazem ele funcionar onde o FAB falhou.
 *
 * ── O que originou (30/08) ────────────────────────────────────────────────────────────────
 *
 * O canal global de feedback mediu ZERO uso em um mês. A aposta aqui é o MOMENTO: fim do
 * boletim e fim da análise IA. Os contratos fixados:
 * um toque já registra (texto é bônus), tudo vai para o MESMO canal (support_tickets, com o
 * contexto no assunto), e falha de rede nunca vira erro na cara de quem acabou de treinar.
 */
describe("feedback no pico", () => {
  it("um TOQUE já registra, com o contexto no assunto", async () => {
    render(<FeedbackNoPico contexto="boletim" />);
    fireEvent.click(screen.getByLabelText("feedbackPico.sim"));
    await waitFor(() => expect(contact).toHaveBeenCalledTimes(1));
    const payload = contact.mock.calls[0][0] as { subject: string; category: string };
    expect(payload.subject).toContain("boletim");
    expect(payload.subject).toContain("👍");
    expect(payload.category).toBe("praise");
  });

  it("o texto opcional vira um segundo registro com o detalhe", async () => {
    render(<FeedbackNoPico contexto="analise-ia" />);
    fireEvent.click(screen.getByLabelText("feedbackPico.nao"));
    await waitFor(() => expect(contact).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByPlaceholderText("feedbackPico.detalheRuim"),
                     { target: { value: "faltou explicar o sizing" } });
    fireEvent.click(screen.getByText("feedbackPico.enviar"));
    await waitFor(() => expect(contact).toHaveBeenCalledTimes(2));
    const detalhe = contact.mock.calls[1][0] as { message: string; category: string };
    expect(detalhe.message).toBe("faltou explicar o sizing");
    expect(detalhe.category).toBe("problem");
    expect(await screen.findByText("feedbackPico.obrigado")).toBeTruthy();
  });

  it("falha de rede NUNCA vira erro na tela", async () => {
    contact.mockRejectedValueOnce(new Error("offline"));
    render(<FeedbackNoPico contexto="boletim" />);
    fireEvent.click(screen.getByLabelText("feedbackPico.sim"));
    await waitFor(() => expect(contact).toHaveBeenCalled());
    // a UI segue para o campo opcional, sem mensagem de erro nenhuma
    expect(screen.queryByText(/erro|error/i)).toBeNull();
    expect(screen.getByPlaceholderText("feedbackPico.detalheBom")).toBeTruthy();
  });

  it("usa o MESMO canal do FAB — nenhum endpoint novo de feedback", () => {
    // O admin olha UMA inbox. Um endpoint próprio aqui seria a segunda fonte de verdade
    // sobre feedback — o padrão que o projeto passou a semana removendo.
    const fonte = fs.readFileSync(path.join(__dirname, "FeedbackNoPico.tsx"), "utf-8");
    expect(fonte).toContain("support.contact");
    expect(/fetch\(|axios|request</.test(fonte), "chamada propria fora do client").toBe(false);
  });
});
