import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

export interface TourStep {
  /** Nome da âncora: o alvo é `[data-tour="<target>"]`. */
  target: string;
  code: string;
  title: string;
  description: string;
}

interface Props {
  steps: TourStep[];
  open: boolean;
  onClose: () => void;
}

/** Distância do balão para o alvo, e respiro mínimo da borda da janela. */
const GAP = 14;
const MARGEM = 12;
const LARGURA = 320;

/**
 * Tour guiado por âncoras declarativas (`data-tour="nome"`).
 *
 * ── Duas regras que vêm de decisões, não de estilo ────────────────────────────────────────────
 *
 * **1. Passo sem alvo no DOM é PULADO, nunca apontado.** O dashboard mostra card conforme o
 * volume de dados: o mesmo tour roda sobre telas diferentes. Apontar para um alvo ausente ensina
 * que o produto é vazio — e essa é exatamente a razão de o tour não rodar sobre o dashboard de
 * quem acabou de se cadastrar.
 *
 * **2. A âncora é um NOME, não um seletor CSS.** Ideia aproveitada do protótipo. Seletor de
 * classe quebra calado quando alguém mexe no layout; `data-tour` some junto com o elemento e o
 * passo se auto-pula (regra 1).
 *
 * O recorte é feito com quatro painéis escuros ao redor do alvo, e não com máscara SVG: sobrevive
 * a qualquer fundo, e o buraco é o próprio elemento, com o hover e o texto legíveis.
 */
export function GuidedTour({ steps, open, onClose }: Props) {
  const { t } = useTranslation("dashboard");
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // Só os passos que TÊM alvo na tela. Recalculado a cada abertura: a mesma tela pode ganhar ou
  // perder card entre uma abertura e outra.
  const [vivos, setVivos] = useState<TourStep[]>([]);
  useEffect(() => {
    if (!open) return;
    setVivos(steps.filter((s) => document.querySelector(`[data-tour="${s.target}"]`)));
    setI(0);
  }, [open, steps]);

  const passo = vivos[i];

  const medir = useCallback(() => {
    if (!passo) return;
    const el = document.querySelector(`[data-tour="${passo.target}"]`);
    setRect(el ? el.getBoundingClientRect() : null);
  }, [passo]);

  // Rola o alvo para o meio da tela ANTES de medir, senão o balão nasce fora da janela.
  useLayoutEffect(() => {
    if (!open || !passo) return;
    const el = document.querySelector(`[data-tour="${passo.target}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    const t = window.setTimeout(medir, 420);
    return () => window.clearTimeout(t);
  }, [open, passo, medir]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", medir);
    window.addEventListener("scroll", medir, true);
    return () => {
      window.removeEventListener("resize", medir);
      window.removeEventListener("scroll", medir, true);
    };
  }, [open, medir]);

  const fechar = useCallback(() => { setI(0); onClose(); }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") fechar();
      if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, vivos.length - 1));
      if (e.key === "ArrowLeft")  setI((n) => Math.max(n - 1, 0));
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, vivos.length, fechar]);

  if (!open || !passo || !rect) return null;

  const ultimo = i === vivos.length - 1;
  const vh = window.innerHeight, vw = window.innerWidth;
  // Balão embaixo do alvo quando cabe; senão em cima. Sem terceira opção: alvo que não cabe em
  // nenhum dos dois lados é raro e o `clamp` abaixo resolve.
  const embaixo = rect.bottom + GAP + 200 < vh;
  const top  = embaixo ? rect.bottom + GAP : Math.max(MARGEM, rect.top - GAP - 200);
  const left = Math.min(Math.max(MARGEM, rect.left + rect.width / 2 - LARGURA / 2), vw - LARGURA - MARGEM);

  const escuro = "fixed bg-background/80 backdrop-blur-[2px] z-[80]";

  return (
    <>
      {/* Recorte: quatro painéis ao redor do alvo. Clicar em qualquer um fecha. */}
      <div className={escuro} style={{ top: 0, left: 0, right: 0, height: Math.max(0, rect.top) }} onClick={fechar} />
      <div className={escuro} style={{ top: rect.bottom, left: 0, right: 0, bottom: 0 }} onClick={fechar} />
      <div className={escuro} style={{ top: rect.top, left: 0, width: Math.max(0, rect.left), height: rect.height }} onClick={fechar} />
      <div className={escuro} style={{ top: rect.top, left: rect.right, right: 0, height: rect.height }} onClick={fechar} />

      {/* Anel do alvo — não intercepta clique, para o elemento seguir legível e utilizável. */}
      <div
        className="pointer-events-none fixed z-[81] rounded-xl ring-2 ring-primary shadow-glow"
        style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label={passo.title}
        className="fixed z-[82] rounded-xl border border-primary/30 bg-hud-surface p-4 shadow-elevated"
        style={{ top, left, width: LARGURA }}
      >
        <div className="mb-2 flex items-start justify-between gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
            {passo.code}
          </span>
          <button onClick={fechar} aria-label={t("tour.fechar")} className="text-muted-foreground transition-colors hover:text-foreground">
            <X className="size-3.5" />
          </button>
        </div>

        <h3 className="font-semibold text-foreground">{passo.title}</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{passo.description}</p>

        <div className="mt-4 flex items-center justify-between gap-3">
          <div className="flex gap-1.5" aria-hidden>
            {vivos.map((_, n) => (
              <span key={n} className={`h-1.5 rounded-full transition-all ${n === i ? "w-4 bg-primary" : "w-1.5 bg-border"}`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {i > 0 && (
              <button
                onClick={() => setI(i - 1)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                <ChevronLeft className="size-3.5" />
              </button>
            )}
            <button
              onClick={() => (ultimo ? fechar() : setI(i + 1))}
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary-foreground transition-colors hover:bg-primary-glow"
            >
              {ultimo ? t("tour.fim") : <>{t("tour.proximo")} <ChevronRight className="size-3.5" /></>}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
