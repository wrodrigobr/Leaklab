// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CheckoutModal } from "./CheckoutModal";

/**
 * A assinatura Stripe só nasce no clique de "Assinar" (03/09) ────────────────────────────────
 *
 * Até aqui, abrir o modal OU trocar mensal↔anual chamava subscription.checkout() — cada chamada
 * cria uma assinatura Stripe DE VERDADE ("Incompleto" no dashboard), mesmo que o jogador só
 * estivesse olhando o preço. O dono notou o ruído no Stripe e pediu: criar só ao confirmar.
 *
 * Depois (mesmo dia), um segundo pedido: escolher plano/ciclo é um passo separado do pagamento,
 * ANTES de o Stripe.js sequer carregar — não só a assinatura, o SDK inteiro só entra em cena
 * quando o jogador clica em "Assinar Pro" (o CTA vive dentro do card do Pro, ao lado do card
 * Free informativo — mesmo formato do card de planos da landing).
 */

const checkout = vi.fn().mockResolvedValue({
  client_secret: "cs_test_123_secret", subscription_id: "sub_test_123", billing: "annual",
});
const activate = vi.fn().mockResolvedValue({
  ok: true, plan: "pro", subscription_id: "sub_test_123", billing: "annual", expires_at: "2027-01-01",
});
const plans = vi.fn().mockResolvedValue({
  plans: [{
    id: "pro",
    price: 3990,
    billing: {
      monthly: { price: 3990 },
      annual: { price: 35880, monthly_equiv: 2990, full_price: 47880, discount_pct: 25, months_free: 2 },
    },
  }],
});
vi.mock("@/lib/api", () => ({ subscription: {
  plans: (...a: unknown[]) => plans(...a),
  checkout: (...a: unknown[]) => checkout(...a),
  activate: (...a: unknown[]) => activate(...a),
} }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ refreshUser: vi.fn().mockResolvedValue(undefined) }) }));
vi.mock("@/lib/analytics", () => ({ trackPurchase: vi.fn() }));
// t precisa ser uma referência ESTÁVEL entre renders (como no react-i18next de verdade) —
// senão o efeito que depende de `t` (carrega o Stripe.js) reroda a cada render por engano,
// e o teste mediria um bug do mock, não do componente.
const tEstavel = (k: string, opts?: { returnObjects?: boolean }) => (opts?.returnObjects ? [] : k);
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: tEstavel }),
}));

const paymentElementHandlers: Record<string, () => void> = {};
const fakePaymentElement = {
  on: (event: string, cb: () => void) => { paymentElementHandlers[event] = cb; },
  mount: () => { paymentElementHandlers.ready?.(); },
  unmount: vi.fn(),
};
const elementsSubmit = vi.fn().mockResolvedValue({ error: undefined });
const elementsCreate = vi.fn(() => fakePaymentElement);
const fakeElements = { create: elementsCreate, submit: elementsSubmit };
const confirmPayment = vi.fn().mockResolvedValue({
  paymentIntent: { status: "succeeded", id: "pi_test_123", amount: 35880, currency: "brl" },
});
const stripeElements = vi.fn(() => fakeElements);
const fakeStripe = { elements: stripeElements, confirmPayment };
const loadStripe = vi.fn((..._a: unknown[]) => Promise.resolve(fakeStripe));
vi.mock("@stripe/stripe-js", () => ({ loadStripe: (...a: unknown[]) => loadStripe(...a) }));

afterEach(() => {
  cleanup();
  checkout.mockClear();
  activate.mockClear();
  confirmPayment.mockClear();
  elementsSubmit.mockClear();
  elementsCreate.mockClear();
  stripeElements.mockClear();
  loadStripe.mockClear();
});

/** Abre o modal, espera o CTA do card Pro ("Assinar Pro") ficar disponível (preços carregados). */
async function abrirNoPassoDoPlano() {
  render(<CheckoutModal plan="pro" onClose={() => {}} />);
  const continuar = await screen.findByText("checkout.assinarCurto");
  await waitFor(() => {
    const btn = continuar.closest("button") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });
  return continuar;
}

/** Continua pro passo de pagamento e espera o PaymentElement montar. */
async function irParaPagamento() {
  const continuar = await abrirNoPassoDoPlano();
  fireEvent.click(continuar);
  await waitFor(() => expect(elementsCreate).toHaveBeenCalled());
  await screen.findByText("checkout.pagar");
}

describe("checkout — plano é um passo separado do pagamento", () => {
  it("abrir o modal NÃO carrega o Stripe.js e NÃO cria assinatura", async () => {
    await abrirNoPassoDoPlano();
    expect(loadStripe).not.toHaveBeenCalled();
    expect(checkout).not.toHaveBeenCalled();
  });

  it("trocar de ciclo (mensal ↔ anual) no passo do plano NÃO toca o Stripe", async () => {
    await abrirNoPassoDoPlano();
    fireEvent.click(screen.getByText("checkout.ciclo.mensal"));
    fireEvent.click(screen.getByText("checkout.ciclo.anual"));
    expect(loadStripe).not.toHaveBeenCalled();
    expect(checkout).not.toHaveBeenCalled();
  });

  it("Continuar carrega o Stripe.js (só agora) e AINDA não cria assinatura", async () => {
    await irParaPagamento();
    expect(loadStripe).toHaveBeenCalledTimes(1);
    expect(checkout).not.toHaveBeenCalled();
  });

  it("voltar pro passo do plano desmonta o formulário do cartão", async () => {
    await irParaPagamento();
    fireEvent.click(screen.getByText("checkout.trocarPlano"));
    await screen.findByText("checkout.assinarCurto");
    expect(screen.queryByText("checkout.pagar")).toBeNull();
  });
});

describe("checkout — assinatura só nasce ao confirmar", () => {
  it("confirmar cria a assinatura EXATAMENTE uma vez, com o ciclo escolhido no passo do plano", async () => {
    const continuar = await abrirNoPassoDoPlano();
    fireEvent.click(screen.getByText("checkout.ciclo.mensal")); // escolhe ANTES de continuar
    fireEvent.click(continuar);
    await waitFor(() => expect(elementsCreate).toHaveBeenCalled());
    await screen.findByText("checkout.pagar");

    fireEvent.click(screen.getByText("checkout.pagar"));

    await waitFor(() => expect(checkout).toHaveBeenCalledTimes(1));
    expect(checkout).toHaveBeenCalledWith("pro", "monthly");
    await waitFor(() => expect(activate).toHaveBeenCalledTimes(1));
    // o client_secret usado no confirmPayment vem da chamada de checkout feita AGORA,
    // não de um estado velho criado ao montar o modal.
    expect(confirmPayment).toHaveBeenCalledWith(
      expect.objectContaining({ clientSecret: "cs_test_123_secret" })
    );
  });
});
