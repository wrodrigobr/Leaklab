/**
 * Preserva o destino através do login (deep link de e-mail, sino e link compartilhado).
 *
 * ── O problema medido ─────────────────────────────────────────────────────────────────────────
 *
 * Os guardas de rota faziam `<Navigate to="/login" replace />` e o destino era DESCARTADO. Somado
 * a duas outras coisas, isso quebrava toda a Fase 2:
 *
 *   1. O token vive em `sessionStorage`, que é POR ABA. Clique em link de e-mail abre aba nova,
 *      então nem quem está logado em outra aba chega autenticado.
 *   2. O login navegava sempre para `/dashboard`, com o destino hard-coded.
 *
 * Resultado: 100% dos CTAs de e-mail morriam no dashboard, e o e-mail existe justamente para
 * quem não está com o app aberto. A prescrição prometia "um clique e você está treinando" e
 * entregava "faça login e se vire".
 *
 * ── Por que `?next=` e não `state` do router ──────────────────────────────────────────────────
 *
 * `state` some num recarregamento e o e-mail é o caso em que o navegador MAIS recarrega (abrir
 * link, autenticar, voltar). A query sobrevive.
 *
 * ── Por que validar ───────────────────────────────────────────────────────────────────────────
 *
 * `?next=` sem validação é open redirect: alguém manda `grindlabpoker.com/login?next=https://
 * site-falso` e usa o NOSSO domínio para dar credibilidade ao phishing. Só caminho interno passa.
 */

/** Monta a URL de login preservando para onde a pessoa queria ir. */
export function urlDeLoginPara(pathname: string, search = ""): string {
  const destino = `${pathname}${search || ""}`;
  // Login para o próprio login seria um laço; e mandar de volta para "/" não preserva nada.
  if (!destino || destino === "/" || destino.startsWith("/login")) return "/login";
  return `/login?next=${encodeURIComponent(destino)}`;
}

/**
 * O destino, se for seguro. `null` quando não houver ou quando for externo.
 *
 * Aceita SÓ caminho interno: uma barra no início, sem esquema e sem `//` (que o navegador trata
 * como protocol-relative e sai do nosso domínio).
 */
export function destinoSeguro(next: string | null | undefined): string | null {
  if (!next) return null;
  let bruto = next;
  try {
    bruto = decodeURIComponent(next);
  } catch {
    return null;   // percent-encoding quebrado: não adivinha, descarta
  }
  const d = bruto.trim();
  if (!d.startsWith("/")) return null;        // externo ou relativo
  if (d.startsWith("//")) return null;        // protocol-relative: //site-falso
  if (/^\/[\\]/.test(d)) return null;         // /\site-falso, que alguns navegadores normalizam
  if (/[a-z][a-z0-9+.-]*:/i.test(d.split("?")[0])) return null;   // javascript:, data:, http:
  if (d.startsWith("/login")) return null;    // laço
  return d;
}
