import { useState } from "react";
import { Lock, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { CheckoutModal } from "./CheckoutModal";
import { useAuth } from "@/lib/auth";

/**
 * Placeholder de card gateado pro plano Pro (insights avançados de IA). Mostra o nome da
 * feature bloqueada + CTA de upgrade que abre o CheckoutModal. Após o upgrade, refreshUser
 * atualiza o plano e o dashboard troca o lock pelo card real. Mantém o mesmo "shell" visual
 * dos outros cards (rounded-xl border bg-hud-surface) pra não quebrar o grid masonry.
 */
export function ProLockCard({ feature }: { feature: string }) {
  const { t } = useTranslation("common");
  const { refreshUser } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-primary/20 bg-hud-surface p-5 flex flex-col items-center justify-center text-center gap-3 min-h-[180px]">
      <span className="flex size-10 items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/25">
        <Lock className="size-4 text-primary" aria-hidden />
      </span>
      <div className="space-y-1">
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary/80">
          {t("proLock.badge")}
        </div>
        <div className="text-sm font-semibold text-foreground">{feature}</div>
        <p className="mx-auto max-w-[240px] text-[11px] leading-snug text-muted-foreground">
          {t("proLock.desc")}
        </p>
      </div>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <Sparkles className="size-3" aria-hidden />
        {t("proLock.cta")}
      </button>

      {open && (
        <CheckoutModal
          plan="pro"
          onClose={() => setOpen(false)}
          onSuccess={async () => {
            setOpen(false);
            await refreshUser();
          }}
        />
      )}
    </div>
  );
}
