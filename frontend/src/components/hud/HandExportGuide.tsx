import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { X, FileDown } from "lucide-react";
import { SiteLogo } from "@/components/hud/SiteLogo";

const SITES = ["pokerstars", "ggpoker", "acr", "coinpoker"] as const;

interface Props {
  open: boolean;
  onClose: () => void;
  /** Quando presente, mostra um CTA que leva direto ao upload (contexto logado). */
  onOpenUpload?: () => void;
}

/**
 * Guia "Como exportar suas mãos" por sala. Remove o atrito nº1 de ativação (o jogador não saber
 * onde achar o .txt de hand history). Conteúdo conciso e verificado (alinhado ao /docs), lista
 * acessível com logo por sala. Acionado do dropzone, do OnboardingModal e da landing.
 */
export function HandExportGuide({ open, onClose, onOpenUpload }: Props) {
  const { t } = useTranslation("onboarding");
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Esc fecha + foco inicial no botão fechar (a11y). Sem trap pesado: painel simples, poucos focáveis.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-guide-title"
    >
      <div
        ref={panelRef}
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-border bg-hud-surface shadow-elevated"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 pt-5 pb-4">
          <div className="flex items-center gap-2">
            <FileDown className="size-4 text-primary" aria-hidden />
            <h2 id="export-guide-title" className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
              {t("exportGuide.title")}
            </h2>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label={t("exportGuide.close")}
            className="text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 overflow-y-auto px-6 py-5">
          <p className="text-sm leading-relaxed text-muted-foreground">{t("exportGuide.intro")}</p>

          <ul className="space-y-3">
            {SITES.map((s) => (
              <li key={s} className="flex items-start gap-3 rounded-lg border border-border bg-hud-elevated/40 p-3">
                <SiteLogo site={s} size={24} />
                <div className="min-w-0">
                  <p className="font-heading text-sm text-foreground">{t(`exportGuide.sites.${s}.name`)}</p>
                  <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{t(`exportGuide.sites.${s}.where`)}</p>
                  {/* O RESUMO do torneio e um arquivo SEPARADO das maos, e o guia so cobria isso na
                      ACR. Sem ele nao ha colocacao, premio, ROI nem field size — e, desde
                      2026-07-30, tambem nao ha deteccao de MESA FINAL, que e onde o ICM muda a
                      decisao certa. */}
                  <p className="mt-1.5 text-xs leading-snug text-primary/90">
                    <span className="font-medium">{t("exportGuide.summaryTitle")}: </span>
                    {t(`exportGuide.sites.${s}.summary`)}
                  </p>
                </div>
              </li>
            ))}
          </ul>

          <p className="border-t border-border/50 pt-3 text-[11px] leading-relaxed text-muted-foreground/70">
            {t("exportGuide.summaryWhy")}{" "}{t("exportGuide.note")}
          </p>
        </div>

        {/* Footer
            Quem abre este guia e, por definicao, quem AINDA NAO TEM o arquivo — o proximo passo
            real dele e sair daqui e exportar na sala. Por isso o botao de destaque e o de sair, e
            nao o de abrir upload. A inversao anterior era pior do que parecia: `onOpenUpload` so
            chega do EmptyDashboard (e la ele abre o seletor de arquivos, para quem acabou de ler
            que precisa exportar antes). Nos outros dois pontos de entrada (landing e modal de
            boas-vindas) o rodape tem UM botao so, e ele estava desenhado como secundario. */}
        {/* flex-wrap: medido a 375px, o rodape cabia com 1px de folga. A copy do primario tem
            tamanhos diferentes nas 3 locales, entao a folga nao e garantia — melhor quebrar a
            linha do que estourar a largura do painel. */}
        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border px-6 py-4">
          {onOpenUpload && (
            <button
              onClick={() => { onClose(); onOpenUpload(); }}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <FileDown className="size-3.5" aria-hidden />
              {t("exportGuide.openUpload")}
            </button>
          )}
          <button
            onClick={onClose}
            className="inline-flex h-10 items-center rounded-md bg-primary px-5 font-mono text-xs font-bold uppercase tracking-widest-2 text-primary-foreground transition-colors hover:bg-primary-glow"
          >
            {t("exportGuide.gotIt")}
          </button>
        </div>
      </div>
    </div>
  );
}
