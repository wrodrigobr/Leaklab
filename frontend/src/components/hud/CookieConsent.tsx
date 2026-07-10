import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Cookie } from "lucide-react";
import { analyticsEnabled, getStoredConsent, setConsent } from "@/lib/analytics";

/**
 * Aviso de cookies (LGPD) + Consent Mode v2. Só aparece quando há tracking configurado
 * (`analyticsEnabled`) e o usuário ainda não decidiu. Aceitar/recusar grava a escolha e avisa o
 * gtag. Sem decisão, o Consent Mode mantém tudo NEGADO (nenhum cookie de análise/anúncio).
 */
export function CookieConsent() {
  const { t } = useTranslation("common");
  const [visible, setVisible] = useState(() => analyticsEnabled() && getStoredConsent() === null);
  if (!visible) return null;

  const decide = (granted: boolean) => {
    setConsent(granted);
    setVisible(false);
  };

  return (
    <div className="fixed inset-x-0 bottom-0 z-[100] p-3 sm:p-4" role="dialog" aria-label={t("cookies.title")}>
      <div className="mx-auto flex max-w-3xl flex-col gap-3 rounded-xl border border-border bg-hud-surface/95 p-4 shadow-elevated backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          <Cookie className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t("cookies.text")}{" "}
            <Link to="/privacidade" className="text-primary underline-offset-2 hover:underline">
              {t("cookies.more")}
            </Link>
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => decide(false)}
            className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("cookies.reject")}
          </button>
          <button
            onClick={() => decide(true)}
            className="rounded-md bg-primary px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-primary-foreground transition-colors hover:bg-primary-glow"
          >
            {t("cookies.accept")}
          </button>
        </div>
      </div>
    </div>
  );
}
