import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
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
/* ── Ícones dos drills — decisão do dono em 30/08 ─────────────────────────────────────────
   Conjunto A ("objetos do jogo": ficha, escudo, torre, carta), escolhido sobre as propostas
   renderizadas; a EXCEÇÃO é Meus leaks, que mantém a mira da direção C já no ar. As matrizes
   de range saíram dos cards nomeados (a 68px viravam massa de cor); `bvb`/`short` seguem com
   a MiniRange até terem proposta própria. Cada ícone: um objeto, uma cor de intenção. */

function IlustracaoAbrir() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <circle cx="32" cy="40" r="13" fill="#2DD4BF" />
      <circle cx="32" cy="40" r="13" fill="none" stroke="#0A0E1A" strokeWidth="2" strokeDasharray="4 5" />
      <circle cx="32" cy="40" r="6" fill="#0A0E1A" opacity=".35" />
      <path d="M32 22 V8 M32 8 l-6 7 M32 8 l6 7" stroke="#2DD4BF" strokeWidth="3.4"
            fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M18 26 a18 18 0 0 1 28 0" stroke="#2DD4BF" strokeWidth="2" fill="none"
            opacity=".35" strokeLinecap="round" />
    </svg>
  );
}

/* 30/08, cartas PRETAS em prod: `fill-card-face` nao e utility Tailwind (a var existe
   no CSS, a classe nao) — SVG sem fill preenche PRETO por default. Fill explicito: sao
   ilustracoes de marca em tema unico escuro. */
function IlustracaoDefender() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <rect x="20" y="10" width="12" height="17" rx="2" fill="#E3E8EC" transform="rotate(-10 26 18)" />
      <rect x="32" y="10" width="12" height="17" rx="2" fill="#E3E8EC" transform="rotate(10 38 18)" />
      <path d="M32 20 L50 27 V40 C50 50 42 56 32 59 C22 56 14 50 14 40 V27 Z" fill="#60A5FA" />
      <path d="M32 26 L44 31 V40 C44 46 39 50 32 52 C25 50 20 46 20 40 V31 Z" fill="#0A0E1A" opacity=".3" />
      <path d="M26 40 l4.5 4.5 L39 36" stroke="#E3E8EC" strokeWidth="3.2" fill="none"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Ilustracao3Bet() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <g stroke="#0A0E1A" strokeWidth="1.6">
        <ellipse cx="32" cy="48" rx="16" ry="6" fill="#F87171" />
        <ellipse cx="32" cy="41" rx="16" ry="6" fill="#F87171" />
        <ellipse cx="32" cy="34" rx="16" ry="6" fill="#F87171" />
        <ellipse cx="32" cy="34" rx="16" ry="6" fill="none" strokeDasharray="5 6" />
      </g>
      <text x="32" y="21" textAnchor="middle" fill="#F87171"
            className="font-mono" fontSize="15" fontWeight="700">3×</text>
    </svg>
  );
}

function IlustracaoMemorizar() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <rect x="14" y="8" width="36" height="48" rx="5" fill="#E3E8EC" />
      <g fill="#C084FC">
        <rect x="20" y="14" width="7" height="7" rx="1.5" />
        <rect x="29" y="14" width="7" height="7" rx="1.5" />
        <rect x="38" y="14" width="7" height="7" rx="1.5" opacity=".55" />
        <rect x="20" y="23" width="7" height="7" rx="1.5" />
        <rect x="29" y="23" width="7" height="7" rx="1.5" opacity=".55" />
        <rect x="38" y="23" width="7" height="7" rx="1.5" opacity=".25" />
        <rect x="20" y="32" width="7" height="7" rx="1.5" opacity=".55" />
        <rect x="29" y="32" width="7" height="7" rx="1.5" opacity=".25" />
      </g>
      <text x="40" y="50" textAnchor="middle" fill="#C084FC"
            className="font-mono" fontSize="14" fontWeight="700">?</text>
    </svg>
  );
}

function IlustracaoMaoCompleta() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <rect x="14" y="14" width="16" height="23" rx="2.5" fill="#E3E8EC" transform="rotate(-14 22 25)" />
      <rect x="24" y="11" width="16" height="23" rx="2.5" fill="#E3E8EC" />
      <rect x="34" y="14" width="16" height="23" rx="2.5" fill="#E3E8EC" transform="rotate(14 42 25)" />
      {/* as 4 streets como pontos: preflop, flop, turn e o river ainda por vir */}
      <g fill="#2DD4BF">
        <circle cx="17" cy="50" r="3.4" /><circle cx="27" cy="50" r="3.4" />
        <circle cx="37" cy="50" r="3.4" /><circle cx="47" cy="50" r="3.4" opacity=".4" />
      </g>
      <path d="M20 50 h4 M30 50 h4 M40 50 h4" stroke="#2DD4BF" strokeWidth="1.6" opacity=".5" />
    </svg>
  );
}

/** id do drill → ícone. Fora do mapa: MiniRange (bvb/short, sem proposta ainda). */
/* Os ids vêm de backend/leaklab/trainer_catalog.py — NÃO do CATALOGO_TREINOS do
   leak_trainer, que é outro catálogo (30/08: mapeei o arquivo errado, o mapa nunca casava e
   os cards ficaram na matriz em prod; o guarda em trainingCatalogIcones.test.ts agora lê os
   ids do PRÓPRIO backend). */
const ILUSTRACAO_POR_DRILL: Record<string, () => JSX.Element> = {
  abrir:    IlustracaoAbrir,
  defender: IlustracaoDefender,
  vs_3bet:  Ilustracao3Bet,
  ranges:   IlustracaoMemorizar,
  grind:    IlustracaoMaoCompleta,
};

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
                  {(() => {
                    if (d.destaque) return <IlustracaoLeaks />;
                    const Icone = ILUSTRACAO_POR_DRILL[d.id];
                    return Icone ? <Icone /> : <MiniRange id={d.ilustracao ?? ""} />;
                  })()}
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
