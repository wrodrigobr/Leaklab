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
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, opts?: { returnObjects?: boolean }) => (opts?.returnObjects ? [] : k),
  }),
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
vi.mock("@stripe/stripe-js", () => ({ loadStripe: vi.fn(() => Promise.resolve(fakeStripe)) }));

afterEach(() => {
  cleanup();
  checkout.mockClear();
  activate.mockClear();
  confirmPayment.mockClear();
  elementsSubmit.mockClear();
  elementsCreate.mockClear();
  stripeElements.mockClear();
});

async function montarEEsperarForm() {
  render(<CheckoutModal plan="pro" onClose={() => {}} />);
  await waitFor(() => expect(elementsCreate).toHaveBeenCalled());
  await screen.findByText("checkout.assinar");
}

describe("checkout — assinatura só nasce ao confirmar", () => {
  it("abrir o modal NÃO cria assinatura no Stripe", async () => {
    await montarEEsperarForm();
    expect(checkout).not.toHaveBeenCalled();
  });

  it("trocar de ciclo (mensal ↔ anual) NÃO cria assinatura", async () => {
    await montarEEsperarForm();
    fireEvent.click(screen.getByText("checkout.ciclo.mensal"));
    await waitFor(() => expect(stripeElements).toHaveBeenCalledTimes(2)); // recriou o Elements local
    expect(checkout).not.toHaveBeenCalled();
  });

  it("confirmar cria a assinatura EXATAMENTE uma vez, com o ciclo escolhido", async () => {
    await montarEEsperarForm();
    fireEvent.click(screen.getByText("checkout.ciclo.mensal"));
    await waitFor(() => expect(stripeElements).toHaveBeenCalledTimes(2));
    await screen.findByText("checkout.assinar");

    fireEvent.click(screen.getByText("checkout.assinar"));

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
