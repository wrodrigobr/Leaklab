// Atribuição de aquisição (first-touch): captura ?utm_source da URL na 1ª carga e guarda na
// sessão até o cadastro. Ex.: link do Instagram "grindlabpoker.com/login?utm_source=instagram".
// Enviado em /auth/register → backend salva em users.acquisition_source → contagem no admin.
const KEY = "acq_source";

export function captureAcquisition(): void {
  try {
    const src = (new URLSearchParams(window.location.search).get("utm_source") || "")
      .trim().toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 40);
    // first-touch: não sobrescreve uma origem já capturada nesta sessão.
    if (src && !sessionStorage.getItem(KEY)) sessionStorage.setItem(KEY, src);
  } catch { /* sessionStorage indisponível — ignora */ }
}

export function getAcquisition(): string | null {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
}
