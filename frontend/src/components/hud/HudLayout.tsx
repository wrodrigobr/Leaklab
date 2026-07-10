import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { HudHeader } from "./HudHeader";

// Back contextual por rota: no hub da Academia (/academy) volta pros Treinos; dentro de uma aula
// (/academy/algo) volta pra Academia. Fica no layout p/ valer em todas as ~25 aulas sem editar
// cada página. Outras rotas não mostram back (destino null).
function useBackTarget(): { to: string; label: string } | null {
  const { pathname } = useLocation();
  const { t } = useTranslation("common");
  if (pathname === "/academy") return { to: "/training", label: t("nav.training") };
  if (pathname.startsWith("/academy/")) return { to: "/academy", label: t("nav.academy") };
  return null;
}

export function HudLayout({
  children,
  eyebrow,
  title,
  description,
}: {
  children: React.ReactNode;
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  const back = useBackTarget();
  return (
    <div className="min-h-dvh bg-background hud-scanline">
      <HudHeader />
      <main className="mx-auto max-w-[1440px] space-y-8 px-4 pt-8 pb-28 md:px-8 md:pb-8 animate-fade-in">
        {back && (
          <Link
            to={back.to}
            className="inline-flex items-center gap-1.5 -mb-2 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            {back.label}
          </Link>
        )}
        <header className="flex flex-col gap-3">
          {eyebrow && (
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest-2 text-primary">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
              {eyebrow}
            </div>
          )}
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl">{title}</h1>
          {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
        </header>
        {children}
      </main>
    </div>
  );
}
