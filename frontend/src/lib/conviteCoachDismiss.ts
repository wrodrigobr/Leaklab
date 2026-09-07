/**
 * O convite "Tem um coach? Vincule seu perfil" no topo do dashboard e FECHAVEL e lembrado
 * por usuario (dono, 07/09: "senao vai ficar no header sempre"). Mesmo padrao do aviso de
 * drift: localStorage por usuario, em try/catch porque o acessor pode nao existir.
 */
const chave = (userId: number | string) => `grindlab:convite-coach-fechado:${userId}`;

export function conviteCoachFechado(userId: number | string | undefined): boolean {
  if (userId == null) return false;
  try {
    return localStorage.getItem(chave(userId)) === "1";
  } catch {
    return false;
  }
}

export function fecharConviteCoach(userId: number | string | undefined): void {
  if (userId == null) return;
  try {
    localStorage.setItem(chave(userId), "1");
  } catch {
    /* sem storage: o convite volta na proxima visita, que e o comportamento antigo */
  }
}
