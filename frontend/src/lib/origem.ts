/**
 * origem — o contrato "de onde vim, para onde volto" da jornada de treino.
 *
 * Auditoria 18/08 (P0): toda atividade recebe `?origem=` e todo fim de sessão navega DE
 * VOLTA à origem — nunca history.back() (frágil em reload/deep-link), nunca /dashboard por
 * acidente. Leitura repetida ad-hoc em 3+ telas vira esta função única (regra 5); `origem`
 * também é a métrica 1 da spec de cobrança, então quem a lê aqui a preserva no funil.
 */
export function destinoDaOrigem(origem: string | null | undefined): string {
  switch ((origem || "").toLowerCase()) {
    case "trilha": return "/training-v2";
    case "dashboard": return "/dashboard";
    default: return "/training";
  }
}
