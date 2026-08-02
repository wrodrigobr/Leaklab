import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";
import { training } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * O catálogo de treinos NOMEADOS.
 *
 * O motor sempre soube receber um foco e a tela sempre soube abrir num foco. O que faltava era
 * AGÊNCIA: quem chega sabendo o que quer treinar hoje não tinha como pedir, porque a chave interna
 * é `vs_3bet:HJ:BTN:50` e ninguém pede isso em voz alta.
 *
 * "Meus leaks" fica em DESTAQUE e é o primeiro de propósito. O catálogo é a porta para quem já
 * sabe o que quer; a prescrição pelo leak medido é o que ele encontra quando não sabe — e é o que
 * separa isto de uma academia com as máquinas etiquetadas.
 */
export function TrainingCatalog() {
  const { t } = useTranslation("training");
  const { data, isPending } = useQuery({ queryKey: ["training-catalog"], queryFn: training.catalog });
  const drills = data?.drills ?? [];

  return (
    <section className="rounded-2xl border border-border bg-card/40 p-5">
      <h2 className="font-heading text-base font-bold text-foreground">{t("catalog.title")}</h2>
      <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{t("catalog.subtitle")}</p>

      <div className="mt-4 space-y-2" aria-busy={isPending}>
        {isPending
          ? [0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-muted/25" />
            ))
          : drills.map((d) => (
              <Link
                key={d.id}
                /* Item com ROTA própria (mão completa) vai para a tela dele; o resto abre o Leak
                   Trainer no foco. Sem honrar a rota, o cartão levaria o jogador ao treino de spot
                   solto anunciando "mão completa" — rótulo que não descreve o destino. */
                to={d.rota ? d.rota : `/leak-trainer?foco=${encodeURIComponent(d.foco)}`}
                className={cn(
                  "group flex items-center gap-3 rounded-xl border p-3 transition-colors",
                  d.destaque
                    ? "border-primary/40 bg-primary/[0.06] hover:border-primary/60"
                    : "border-border bg-background/40 hover:border-primary/40",
                )}
              >
                {d.destaque && (
                  <Sparkles className="size-4 shrink-0 text-primary" aria-hidden />
                )}
                <div className="min-w-0 flex-1">
                  <h3 className="font-heading text-sm font-bold text-foreground">
                    {t(`catalog.drills.${d.id}.name`)}
                  </h3>
                  <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">
                    {t(`catalog.drills.${d.id}.desc`)}
                  </p>
                </div>

                {/* Nunca praticado mostra "—", nunca "0%". Zero afirma desempenho; ausência de
                    dado não afirma nada, e a tela não pode inventar a diferença. */}
                <div className="shrink-0 text-right">
                  <p className="font-mono text-sm font-bold tabular-nums text-foreground">
                    {d.acerto === null ? t("catalog.never") : `${d.acerto}%`}
                  </p>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {d.maos === null ? t("catalog.never") : `${d.maos} ${t("catalog.hands")}`}
                  </p>
                </div>
                <ArrowRight
                  className="size-4 shrink-0 text-primary transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              </Link>
            ))}
      </div>
    </section>
  );
}
