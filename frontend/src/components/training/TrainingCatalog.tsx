import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";
import { training } from "@/lib/api";
import { MiniRange } from "./MiniRange";
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
/**
 * A medalha por treino. Gamificacao que TAMBEM e informacao: da para varrer os seis cards num
 * olhar e ver onde nao ha medalha nenhuma, que e onde falta praticar.
 *
 * `null` (nunca praticado) NAO vira medalha vazia sozinha -- o texto "sem amostra" viaja ao lado.
 * Uma medalha apagada sem legenda leria como desempenho ruim, que e afirmacao que nao temos.
 */
function Medalha({ acerto }: { acerto: number | null }) {
  const faixa = acerto === null ? "vazia"
    : acerto >= 85 ? "ouro"
    : acerto >= 70 ? "prata"
    : acerto >= 55 ? "bronze"
    : "vazia";
  const fundo: Record<string, string> = {
    ouro:   "linear-gradient(135deg,#fde68a,#d4a017)",
    prata:  "linear-gradient(135deg,#e5e7eb,#9ca3af)",
    bronze: "linear-gradient(135deg,#e0a878,#a1663a)",
    vazia:  "transparent",
  };
  return (
    <span
      className={cn("block size-3 shrink-0 rounded-full",
                    faixa === "vazia" && "ring-1 ring-inset ring-border")}
      style={{ background: fundo[faixa] }}
      aria-hidden
    />
  );
}

/** Quatro barras decrescentes: a ideia de leaks priorizados, sem escrever "priorizados". */
function IlustracaoLeaks() {
  return (
    <span className="flex h-full items-end gap-1 pb-1" aria-hidden>
      {[74, 52, 38, 22].map((h) => (
        <span key={h} className="block w-2.5 rounded-t-sm bg-destructive/70"
              style={{ height: `${h}%` }} />
      ))}
    </span>
  );
}

/** Mesa com duas cartas: diz "mao completa" sem a frase "do preflop ao river". */
function IlustracaoMesa() {
  return (
    <svg viewBox="0 0 120 56" className="w-full" aria-hidden>
      <ellipse cx="60" cy="28" rx="46" ry="22" className="fill-background"
               stroke="hsl(var(--primary))" strokeOpacity="0.35" strokeWidth="1.5" />
      <circle cx="60" cy="8"  r="4.5" className="fill-muted" />
      <circle cx="97" cy="28" r="4.5" className="fill-muted" />
      <circle cx="23" cy="28" r="4.5" className="fill-muted" />
      <circle cx="60" cy="48" r="4.5" fill="hsl(var(--primary))" />
      <rect x="51" y="22" width="8" height="12" rx="1.5" className="fill-card-face" />
      <rect x="61" y="22" width="8" height="12" rx="1.5" className="fill-card-face" />
    </svg>
  );
}

export function TrainingCatalog() {
  const { t } = useTranslation("training");
  const { data, isPending } = useQuery({ queryKey: ["training-catalog"], queryFn: training.catalog });
  const drills = data?.drills ?? [];

  return (
    <section className="rounded-2xl border border-border bg-card/40 p-5">
      <h2 className="font-heading text-base font-bold text-foreground">{t("catalog.title")}</h2>
      <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{t("catalog.subtitle")}</p>

      <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3" aria-busy={isPending}>
        {isPending
          ? [0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-[124px] animate-pulse rounded-xl bg-muted/25" />
            ))
          : drills.map((d) => (
              <Link
                key={d.id}
                /* Item com ROTA propria (mao completa) vai para a tela dele; o resto abre o Leak
                   Trainer no foco. Sem honrar a rota, o cartao levaria o jogador ao treino de spot
                   solto anunciando "mao completa" -- rotulo que nao descreve o destino. */
                to={d.rota ? d.rota : `/leak-trainer?foco=${encodeURIComponent(d.foco)}`}
                className={cn(
                  "group flex items-center gap-3 rounded-xl border p-2.5 transition-colors",
                  d.destaque
                    ? "border-primary/40 bg-primary/[0.06] hover:border-primary/60"
                    : "border-border bg-background/40 hover:border-primary/40",
                )}
              >
                {/* ── Horizontal, e nao vertical (28/08) ──────────────────────────────────
                    A 1a versao centralizava a ilustracao num card de 600px de largura, com o
                    titulo encostado embaixo: o desenho ficava perdido num mar de vazio e a tela
                    parecia quebrada. So a captura da tela real mostrou -- no mockup, com cards
                    estreitos, o empilhado funcionava.

                    A ilustracao e a razao de o card existir: o formato da range diz o que o drill
                    e mais rapido que a descricao, e e o mesmo desenho que o jogador encontra
                    treinando. Ancorada a esquerda, ela vira a primeira coisa que o olho pega. */}
                <span className="flex size-[68px] shrink-0 items-center justify-center overflow-hidden rounded-lg bg-background/50 p-1.5">
                  {d.destaque
                    ? <IlustracaoLeaks />
                    : d.ilustracao === "mesa"
                      ? <IlustracaoMesa />
                      : <MiniRange id={d.ilustracao ?? ""} />}
                </span>

                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <h3 className="font-heading text-[13px] font-bold leading-tight text-foreground">
                    {t(`catalog.drills.${d.id}.name`)}
                  </h3>

                  {/* Nunca praticado diz "sem amostra", nunca "0%": zero afirma desempenho, e
                      ausencia de dado nao afirma nada. Ate 28/08 este comentario ja dizia isso e
                      a chave `catalog.never` valia "—", um travessao -- que nao diz nada ao
                      jogador E viola a regra de copy do projeto. Comentario nao e evidencia. */}
                  <span className="flex items-center gap-1.5">
                    <Medalha acerto={d.acerto} />
                    <span className="truncate font-mono text-[10px] tabular-nums text-foreground/70">
                      {d.acerto === null
                        ? t("catalog.never")
                        : `${d.acerto}% · ${d.maos}`}
                    </span>
                  </span>
                </span>
              </Link>
            ))}
      </div>
    </section>
  );
}
