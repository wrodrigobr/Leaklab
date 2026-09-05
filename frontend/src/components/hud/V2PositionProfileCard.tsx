import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Info, ChevronDown } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { PositionProfileResponse, PositionStatCell } from "@/lib/api";

/**
 * V2PositionProfileCard — o perfil do jogador em CADA assento.
 *
 * ── A pergunta que este card responde, e a que ele NÃO responde ──────────────────────────
 *
 * O `V2PositionCard` ao lado diz *de onde você erra mais* (alinhamento GTO por posição).
 * Este diz *qual é o seu perfil ali*: VPIP, PFR, 3bet, WTSD por assento. São perguntas
 * diferentes, e a segunda o produto não tinha.
 *
 * ── Por que não é a grade do PokerTracker ────────────────────────────────────────────────
 *
 * A ideia nasceu de um print do PT4 (04/09), mas copiar as 20 colunas de percentual cru
 * seria despejo de dado para quem já sabe o que procurar. Aqui **cada célula é uma régua**:
 * a faixa saudável aparece desenhada e o marcador mostra onde o jogador está nela. Quem não
 * decorou que "VPIP saudável de MTT é 18–24" lê a mesma informação na posição do ponto.
 *
 * ── Por que a grade é PROGRESSIVA ────────────────────────────────────────────────────────
 *
 * Medido em produção antes de desenhar: com o corte de amostra do produto, a grade completa
 * só funcionaria para 2 dos 9 jogadores com volume — `W$SD` pede 2.000 mãos, `WTSD` 1.000,
 * e dividir o acervo por 8 assentos derruba quase todo mundo. Baixar o corte para encher a
 * tela seria inventar leitura. Então VPIP e PFR aparecem para quase todos, e o resto **surge
 * por assento** conforme aquele assento ganha volume: a tela cresce com o jogador em vez de
 * nascer vazia.
 *
 * As linhas seguem a ORDEM DE FALA na mesa (UTG primeiro, BB por último), não a ordem
 * alfabética nem a de volume: a posição relativa é a informação, e ler de cima para baixo
 * é ler a mão acontecendo.
 */

/** Cor da banda. Mesma paleta do V2PositionCard, para as duas grades de posição falarem
 *  a mesma língua a três centímetros uma da outra. */
const COR_BANDA: Record<string, string> = {
  healthy: "#10b981",
  below:   "#f59e0b",
  above:   "#f59e0b",
  /** desvio de mais de ~1,2 largura de banda deixa de ser ajuste fino e vira leak */
  far:     "#ef4444",
};

/** Rótulo de cada coluna. Jargão de poker fica em INGLÊS nos 3 idiomas, por convenção do
 *  produto — é o que o `PlayerStatsCard` ao lado já faz. Criar chave de i18n para "VPIP"
 *  seria triplicar uma string que não se traduz. */
const ROTULO: Record<string, string> = {
  vpip: "VPIP",
  pfr: "PFR",
  three_bet: "3Bet",
  fold_to_3bet: "Fold 3Bet",
  af: "AF",
  cbet_pct: "C-Bet",
  steal_pct: "Steal",
  wtsd: "WTSD",
  w_at_sd: "W$SD",
};

/** Escala de cada stat, para a régua ter um domínio fixo por coluna. Sem isto, cada célula
 *  desenharia a própria escala e a comparação entre assentos deixaria de valer. */
const ESCALA: Record<string, [number, number]> = {
  vpip:         [0, 60],
  pfr:          [0, 45],
  three_bet:    [0, 20],
  fold_to_3bet: [0, 100],
  af:           [0, 8],
  cbet_pct:     [0, 100],
  steal_pct:    [0, 70],
  wtsd:         [0, 60],
  w_at_sd:      [0, 100],
};

function pct(v: number, [min, max]: [number, number]): number {
  return Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100));
}

/** Desvio em LARGURAS DE BANDA. 0 = dentro; 1 = uma faixa saudável inteira fora.
 *  Serve só para escolher a intensidade da cor: acima de ~1,2 o desvio deixa de ser ajuste
 *  fino e vira leak, e a célula passa de âmbar para vermelho. */
function desvio(cel: PositionStatCell): number {
  const [lo, hi] = cel.healthy;
  const largura = Math.max(hi - lo, 0.1);
  if (cel.value < lo) return (lo - cel.value) / largura;
  if (cel.value > hi) return (cel.value - hi) / largura;
  return 0;
}

/**
 * Uma célula. Só o EXCESSO ganha cor.
 *
 * A faixa saudável está sempre desenhada em verde; quando o valor sai dela, o trecho **entre
 * a borda da faixa e o valor** é pintado. Quem está dentro não gasta tinta nenhuma, então o
 * olho encontra o vazamento sem varrer célula por célula — e, ao mesmo tempo, a escala segue
 * absoluta, então dá para ver que um VPIP está no TOPO da faixa e não apenas dentro dela.
 */
function Celula({ chave, cel, posicao, maos }: {
  chave: string; cel: PositionStatCell; posicao: string; maos: number;
}) {
  const { t } = useTranslation("dashboard");
  const escala = ESCALA[chave] ?? [0, 100];
  const baixa = cel.band === "low_sample";
  const dentro = cel.band === "healthy";
  const d = desvio(cel);
  const cor = baixa ? "#64748B" : dentro ? COR_BANDA.healthy : (d > 1.2 ? COR_BANDA.far : COR_BANDA.out);

  const ini = pct(cel.healthy[0], escala);
  const fim = pct(cel.healthy[1], escala);
  const marca = pct(cel.value, escala);

  // o trecho pintado: da borda da faixa ate o valor, no lado em que ele saiu
  const acima = cel.band === "above";
  const excInicio = acima ? fim : marca;
  const excFim = acima ? marca : ini;

  const unidade = chave === "af" ? "x" : "%";
  const leitura = baixa
    ? t("posProfile.lowSampleLong")
    : dentro
      ? t("posProfile.inBand")
      : t(`posProfile.read.${chave}.${acima ? 1 : 0}`, { defaultValue: "" });

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex flex-col gap-1 cursor-default">
          <span className="font-mono text-[11px] font-bold tabular-nums leading-none"
                style={{ color: baixa ? "rgba(100,116,139,.55)" : cor }}>
            {baixa ? "—" : cel.value}
          </span>
          <div className="relative h-1.5 w-full rounded-full bg-muted/15 overflow-hidden">
            <div className="absolute inset-y-0 rounded-full bg-emerald-500/25"
                 style={{ left: `${ini}%`, width: `${Math.max(3, fim - ini)}%`,
                          opacity: baixa ? 0.4 : 1 }} />
            {!baixa && !dentro && (
              <div className="absolute inset-y-0 rounded-full"
                   style={{ left: `${excInicio}%`, width: `${Math.max(2, excFim - excInicio)}%`,
                            backgroundColor: cor, opacity: 0.85 }} />
            )}
            {!baixa && (
              <div className="absolute top-1/2 size-1.5 -translate-y-1/2 -translate-x-1/2 rounded-full ring-1 ring-background"
                   style={{ left: `${marca}%`, backgroundColor: cor }} />
            )}
          </div>
        </div>
      </TooltipTrigger>

      {/* O tooltip poe os dois numeros um debaixo do outro e traduz a diferenca em uma frase.
          "25,1 contra 18-24" exige que o jogador faca a conta; a frase entrega a leitura. */}
      <TooltipContent side="top" className="w-[210px] p-3">
        <div className="font-mono text-[9px] uppercase tracking-widest text-primary mb-2">
          {ROTULO[chave] ?? chave} · {posicao}
        </div>
        <div className="flex items-baseline justify-between gap-3 py-0.5">
          <span className="text-[11px] text-muted-foreground">{t("posProfile.you")}</span>
          <span className="font-mono text-xs font-bold tabular-nums" style={{ color: cor }}>
            {baixa ? "—" : `${cel.value}${unidade}`}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-3 py-0.5">
          <span className="text-[11px] text-muted-foreground">{t("posProfile.recommended")}</span>
          <span className="font-mono text-xs font-bold tabular-nums text-emerald-500">
            {cel.healthy[0]}–{cel.healthy[1]}{unidade}
          </span>
        </div>
        <div className="my-1.5 h-px bg-border" />
        <p className="text-[11px] leading-snug text-muted-foreground">
          {leitura}
          {cel.flag && !dentro && !baixa && (
            <> {t("posProfile.profile", { flag: t(`playerStats.flags.${cel.flag}`, { defaultValue: cel.flag }) })}</>
          )}
        </p>
        <p className="mt-1.5 font-mono text-[9px] text-muted-foreground/70">
          {t("posProfile.handsHere", { n: maos })}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

export function V2PositionProfileCard({ data }: { data?: PositionProfileResponse | null }) {
  const { t } = useTranslation("dashboard");
  const [aberto, setAberto] = useState(false);

  /** Colunas que valem a pena mostrar: só as que ALGUM assento consegue classificar. Uma
   *  coluna inteira de "—" ocupa espaço e não informa nada. */
  const { colunasBase, colunasExtra } = useMemo(() => {
    const linhas = data?.positions ?? [];
    const temDado = (k: string) =>
      linhas.some((l) => l.stats[k] && l.stats[k].band !== "low_sample");
    return {
      colunasBase: (data?.sempre ?? []).filter((k) => linhas.some((l) => l.stats[k])),
      colunasExtra: (data?.com_volume ?? []).filter(temDado),
    };
  }, [data]);

  const linhas = data?.positions ?? [];
  const colunas = aberto ? [...colunasBase, ...colunasExtra] : [...colunasBase, ...colunasExtra.slice(0, 3)];
  const escondidas = colunasExtra.length - Math.min(colunasExtra.length, 3);

  if (!data || linhas.length === 0) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {t("posProfile.title")}
          </span>
          <HudTooltip content={t("posProfile.tooltip")} />
        </div>
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {t("posProfile.title")}
          </span>
          <HudTooltip content={t("posProfile.tooltip")} />
        </div>
        <span className="font-mono text-[9px] text-muted-foreground/70 tabular-nums">
          {t("posProfile.hands", { n: data.total_hands })}
        </span>
      </div>

      {/* A legenda vem ANTES da grade: sem ela o verde no meio da régua é decoração. */}
      <p className="mb-3 font-mono text-[9px] leading-snug text-muted-foreground/70">
        {t("posProfile.legend")}
      </p>

      {/* overflow-x próprio: a grade é larga e o corpo da página não pode rolar de lado */}
      {/* UM provider para a grade toda: um por célula seriam dezenas de contextos. */}
      <TooltipProvider delayDuration={200}>
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="min-w-[520px]">
          <div
            className="grid items-end gap-x-3 pb-1.5 mb-1.5 border-b border-border/50"
            style={{ gridTemplateColumns: `3.25rem 2.75rem repeat(${colunas.length}, minmax(3rem, 1fr))` }}
          >
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">
              {t("posProfile.seat")}
            </span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">
              {t("posProfile.handsShort")}
            </span>
            {colunas.map((k) => (
              <span key={k} className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">
                {ROTULO[k] ?? k}
              </span>
            ))}
          </div>

          <div className="space-y-2.5">
            {linhas.map((linha) => (
              <div
                key={linha.position}
                className="grid items-center gap-x-3"
                style={{ gridTemplateColumns: `3.25rem 2.75rem repeat(${colunas.length}, minmax(3rem, 1fr))` }}
              >
                <span className="font-mono text-[10px] font-bold uppercase text-foreground">
                  {linha.position}
                </span>
                <span className="font-mono text-[9px] text-muted-foreground/70 tabular-nums text-right">
                  {linha.hands}
                </span>
                {colunas.map((k) =>
                  linha.stats[k] ? (
                    <Celula key={k} chave={k} cel={linha.stats[k]} posicao={linha.position} maos={linha.hands} />
                  ) : (
                    <span key={k} className="font-mono text-[11px] text-muted-foreground/25">—</span>
                  )
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      </TooltipProvider>

      {escondidas > 0 && (
        <button
          type="button"
          onClick={() => setAberto((v) => !v)}
          className="mt-3 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors"
        >
          <ChevronDown className={cn("size-3 transition-transform", aberto && "rotate-180")} />
          {aberto ? t("posProfile.showLess") : t("posProfile.showMore", { n: escondidas })}
        </button>
      )}
    </div>
  );
}
