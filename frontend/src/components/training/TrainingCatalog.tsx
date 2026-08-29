import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, Brain, Flame, Shield, Sparkles, type LucideIcon } from "lucide-react";
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
  /* Redesenho 29/08: as barras sozinhas liam como "grafico qualquer". A MIRA sobre a barra
     mais alta e o que o drill faz: aponta o erro mais caro e treina ele primeiro. */
  return (
    <svg viewBox="0 0 56 56" className="h-full w-full" aria-hidden>
      {[
        { x: 6,  h: 34, alvo: true },
        { x: 20, h: 24, alvo: false },
        { x: 34, h: 16, alvo: false },
        { x: 48, h: 9,  alvo: false },
      ].map((b) => (
        <rect key={b.x} x={b.x - 4} y={50 - b.h} width="9" height={b.h} rx="1.5"
              fill="#F87171" opacity={b.alvo ? 0.9 : 0.45} />
      ))}
      <circle cx="7.5" cy="12" r="8" fill="none" stroke="#2DD4BF" strokeWidth="1.8" />
      <circle cx="7.5" cy="12" r="2" fill="#2DD4BF" />
      <line x1="7.5" y1="0.5" x2="7.5" y2="6.5" stroke="#2DD4BF" strokeWidth="1.8" />
      <line x1="7.5" y1="17.5" x2="7.5" y2="23.5" stroke="#2DD4BF" strokeWidth="1.8" />
      <line x1="-4" y1="12" x2="2" y2="12" stroke="#2DD4BF" strokeWidth="1.8" />
      <line x1="13" y1="12" x2="19" y2="12" stroke="#2DD4BF" strokeWidth="1.8" />
    </svg>
  );
}

/** Mesa com duas cartas: diz "mao completa" sem a frase "do preflop ao river". */
function IlustracaoMesa() {
  /* Redesenho 29/08 (pedido do dono: "mais criativos e profissionais"): a elipse chapada de
     traco fino sumia no card. Feltro com profundidade (gradiente radial + borda dupla), board
     de 3 cartas no meio e o ASSENTO DO HEROI aceso com as duas cartas -- a hierarquia visual
     conta a historia: voce, suas cartas, a mao inteira pela frente. */
  return (
    <svg viewBox="0 0 120 68" className="w-full" aria-hidden>
      <defs>
        <radialGradient id="feltro" cx="50%" cy="42%" r="70%">
          <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.16" />
          <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0.03" />
        </radialGradient>
      </defs>
      <ellipse cx="60" cy="32" rx="50" ry="26" fill="url(#feltro)"
               stroke="hsl(var(--primary))" strokeOpacity="0.5" strokeWidth="1.8" />
      <ellipse cx="60" cy="32" rx="43" ry="20.5" fill="none"
               stroke="hsl(var(--primary))" strokeOpacity="0.15" strokeWidth="1" />
      {[46, 56, 66].map((x) => (
        <rect key={x} x={x} y="25" width="8" height="11" rx="1.5"
              className="fill-card-face" opacity="0.9" />
      ))}
      <circle cx="60" cy="7"  r="4" className="fill-muted" opacity="0.7" />
      <circle cx="104" cy="32" r="4" className="fill-muted" opacity="0.7" />
      <circle cx="16" cy="32" r="4" className="fill-muted" opacity="0.7" />
      <circle cx="88" cy="12" r="3.2" className="fill-muted" opacity="0.5" />
      <circle cx="32" cy="12" r="3.2" className="fill-muted" opacity="0.5" />
      <circle cx="60" cy="57" r="5.5" fill="hsl(var(--primary))" />
      <circle cx="60" cy="57" r="8.5" fill="none" stroke="hsl(var(--primary))"
              strokeOpacity="0.35" strokeWidth="1.5" />
      <g transform="rotate(-8 53 46)">
        <rect x="49" y="41" width="9" height="12.5" rx="1.5" className="fill-card-face"
              stroke="hsl(var(--primary))" strokeOpacity="0.6" strokeWidth="0.8" />
      </g>
      <g transform="rotate(8 67 46)">
        <rect x="62" y="41" width="9" height="12.5" rx="1.5" className="fill-card-face"
              stroke="hsl(var(--primary))" strokeOpacity="0.6" strokeWidth="0.8" />
      </g>
    </svg>
  );
}

/** O selo que separa cards de matriz parecidos entre si: um glifo por INTENCAO do drill.
 *  As grades de range sao deliberadamente a MESMA linguagem (a imagem carrega a range real);
 *  o selo devolve a identidade sem inventar desenho -- abrir=seta, defender=escudo,
 *  3-bet=chama, memorizar=cerebro. */
const SELO_DO_DRILL: Record<string, { Icone: LucideIcon; cor: string }> = {
  fund_rfi:      { Icone: ArrowUpRight, cor: "#2DD4BF" },
  fund_vs_rfi:   { Icone: Shield,       cor: "#60A5FA" },
  pf_bb_defense: { Icone: Shield,       cor: "#60A5FA" },
  fund_vs_3bet:  { Icone: Flame,        cor: "#F87171" },
  pf_bb_3bet:    { Icone: Flame,        cor: "#F87171" },
  range_grid:    { Icone: Brain,        cor: "#C084FC" },
};

function SeloDoDrill({ id }: { id: string }) {
  const selo = SELO_DO_DRILL[id];
  if (!selo) return null;
  return (
    <span
      className="absolute -bottom-1 -right-1 flex size-5 items-center justify-center rounded-md border border-border bg-hud-surface shadow-sm"
      aria-hidden
    >
      <selo.Icone className="size-3" style={{ color: selo.cor }} />
    </span>
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
                <span className="relative flex size-[68px] shrink-0 items-center justify-center rounded-lg bg-background/50 p-1.5">
                  <span className="flex h-full w-full items-center justify-center overflow-hidden">
                    {d.destaque
                      ? <IlustracaoLeaks />
                      : d.ilustracao === "mesa"
                        ? <IlustracaoMesa />
                        : <MiniRange id={d.ilustracao ?? ""} />}
                  </span>
                  <SeloDoDrill id={d.id} />
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
