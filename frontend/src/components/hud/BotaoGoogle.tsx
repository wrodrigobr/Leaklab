import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { auth } from "@/lib/api";

/**
 * O botão "Continuar com Google" (30/08): o GIS renderiza o botão oficial, o callback nos dá
 * o ID token, o backend valida e devolve o NOSSO JWT.
 *
 * ── As regras de honestidade do componente ────────────────────────────────────────────────
 *
 * 1. Sem `VITE_GOOGLE_CLIENT_ID` no build, o componente renderiza NADA — a feature liga por
 *    configuração, e um botão que falha ao clicar é pior que ausência.
 * 2. O script do Google carrega UMA vez (guarda no window), sob demanda desta tela — não no
 *    bundle de todo mundo.
 * 3. Nenhuma credencial passa por nós além do token de identidade: quem loga o usuário no
 *    Google é o Google, no popup dele.
 */

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: { client_id: string; callback: (r: { credential: string }) => void }) => void;
          renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
        };
      };
    };
    __gisCarregando?: Promise<void>;
  }
}

function carregarGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!window.__gisCarregando) {
    window.__gisCarregando = new Promise((ok, err) => {
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.async = true;
      s.onload = () => ok();
      s.onerror = () => err(new Error("gis"));
      document.head.appendChild(s);
    });
  }
  return window.__gisCarregando;
}

interface Props {
  /** ref de convite de coach, preservado como no cadastro por senha */
  refConvite?: string | null;
  /** recebe o payload do login (token já emitido) para o chamador fechar a sessão */
  aoEntrar: (r: { token: string; created: boolean }) => void | Promise<void>;
  aoFalhar?: (msg: string) => void;
}

export function BotaoGoogle({ refConvite, aoEntrar, aoFalhar }: Props) {
  const { t } = useTranslation("common");
  const alvo = useRef<HTMLDivElement>(null);
  const [pronto, setPronto] = useState(false);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  useEffect(() => {
    if (!clientId || !alvo.current) return;
    let ativo = true;
    carregarGis().then(() => {
      if (!ativo || !alvo.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (resp) => {
          try {
            const r = await auth.google(resp.credential, refConvite ?? undefined);
            await aoEntrar({ token: r.token, created: r.created });
          } catch (e: unknown) {
            aoFalhar?.(e instanceof Error ? e.message : t("googleLogin.erro"));
          }
        },
      });
      window.google.accounts.id.renderButton(alvo.current, {
        theme: "filled_black", size: "large", width: 320,
        text: "continue_with", locale: "pt-BR",
      });
      setPronto(true);
    }).catch(() => aoFalhar?.(t("googleLogin.erro")));
    return () => { ativo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  if (!clientId) return null;
  return (
    <div className="flex flex-col items-center gap-2">
      <div ref={alvo} className={pronto ? "" : "h-10"} />
      {pronto && (
        <p className="text-center text-[10px] text-muted-foreground/70">
          {t("googleLogin.nota")}
        </p>
      )}
    </div>
  );
}
