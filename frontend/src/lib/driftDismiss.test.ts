import { describe, it, expect } from "vitest";
import { shouldShowDrift } from "./driftDismiss";

/**
 * O que estes testes travam não é a fórmula: é a PROMESSA feita ao jogador. Ele fechou o aviso,
 * então o aviso fica fechado até existir algo novo. Um alerta que reabre sozinho ensina a
 * ignorá-lo, e aí o dia em que ele importa de verdade também passa batido.
 */
describe("shouldShowDrift", () => {
  it("não mostra nada quando não há drift", () => {
    expect(shouldShowDrift(false, 120, 0)).toBe(false);
    expect(shouldShowDrift(false, 120, 500)).toBe(false);
  });

  it("mostra na primeira detecção (nunca dispensou)", () => {
    expect(shouldShowDrift(true, 120, 0)).toBe(true);
  });

  it("fica fechado depois de dispensar a mesma detecção", () => {
    expect(shouldShowDrift(true, 120, 120)).toBe(false);
  });

  it("REGRESSÃO: janela deslizando não reabre o alerta", () => {
    // O torneio 120 envelheceu e saiu da janela de 30 dias; o maior marcado agora é o 118.
    // No modelo antigo (chave por fingerprint) isso gerava uma chave nova e o banner voltava.
    expect(shouldShowDrift(true, 118, 120)).toBe(false);
    expect(shouldShowDrift(true, 1, 120)).toBe(false);
  });

  it("reabre quando entra um torneio NOVO em drift", () => {
    expect(shouldShowDrift(true, 121, 120)).toBe(true);
  });

  it("sem id de sessão, prefere mostrar a engolir um aviso real", () => {
    // backend antigo (sem `latest_flagged_id`) — o alerta é ruidoso, mas nunca silencioso
    expect(shouldShowDrift(true, null, 120)).toBe(true);
    expect(shouldShowDrift(true, undefined, 120)).toBe(true);
    expect(shouldShowDrift(true, 0, 120)).toBe(true);
  });
});
