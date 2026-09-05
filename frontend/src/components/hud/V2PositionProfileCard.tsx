import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Info, ChevronDown } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { PlayerStatFlag, PlayerStatsResponse, PositionProfileResponse, PositionStatCell } from "@/lib/api";

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

/**
 * Uma célula. Só o EXCESSO ganha cor.
 *
 * A faixa saudável está sempre desenhada em verde; quando o valor sai dela, o trecho **entre
 * a borda da faixa e o valor** é pintado. Quem está dentro não gasta tinta nenhuma, então o
 * olho encontra o vazamento sem varrer célula por célula — e, ao mesmo tempo, a escala segue
 * absoluta, então dá para ver que um VPIP está no TOPO da faixa e não apenas dentro dela.
 */
/** A celula da linha TOTAL. **Esta** mantem a regua pintada, porque `STAT_REFERENCES` e a
 *  referencia do JOGO INTEIRO e e exatamente aqui que ela se aplica. E a mesma banda que o
 *  HUD principal ja usa, entao as duas superficies nao podem discordar. */
function CelulaTotal({ chave, valor, marcador, maos }: {
  chave: string; valor: number; marcador: PlayerStatFlag; maos: number;
}) {
  const { t } = useTranslation("dashboard");
  const escala = ESCALA[chave] ?? [0, 100];
  const faixa = marcador.healthy ?? [0, 0];
  const dentro = marcador.band === "healthy";
  const baixa = marcador.band === "low_sample";
  const acima = marcador.band === "above";
  const larg = Math.max(faixa[1] - faixa[0], 0.1);
  const d = dentro || baixa ? 0
    : acima ? (valor - faixa[1]) / larg : (faixa[0] - valor) / larg;
  const cor = baixa ? "#64748B" : dentro ? COR_BANDA.healthy : (d > 1.2 ? COR_BANDA.far : COR_BANDA.out);

  const ini = pct(faixa[0], escala);
  const fim = pct(faixa[1], escala);
  const marca = pct(valor, escala);
  const excInicio = acima ? fim : marca;
  const excFim = acima ? marca : ini;
  const unidade = chave === "af" ? "x" : "%";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex flex-col gap-1 cursor-default">
          <span className="font-mono text-[11px] font-bold tabular-nums leading-none" style={{ color: cor }}>
            {valor}
          </span>
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/15">
            <div className="absolute inset-y-0 rounded-full bg-emerald-500/25"
                 style={{ left: `${ini}%`, width: `${Math.max(3, fim - ini)}%`, opacity: baixa ? 0.4 : 1 }} />
            {!baixa && !dentro && (
              <div className="absolute inset-y-0 rounded-full"
                   style={{ left: `${excInicio}%`, width: `${Math.max(2, excFim - excInicio)}%`,
                            backgroundColor: cor, opacity: 0.85 }} />
            )}
            <div className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-1 ring-background"
                 style={{ left: `${marca}%`, backgroundColor: cor }} />
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="w-[210px] p-3">
        <div className="mb-2 font-mono text-[9px] uppercase tracking-widest text-primary">
          {ROTULO[chave] ?? chave} · {t("posProfile.total")}
        </div>
        <div className="flex items-baseline justify-between gap-3 py-0.5">
          <span className="text-[11px] text-muted-foreground">{t("posProfile.you")}</span>
          <span className="font-mono text-xs font-bold tabular-nums" style={{ color: cor }}>{valor}{unidade}</span>
        </div>
        <div className="flex items-baseline justify-between gap-3 py-0.5">
          <span className="text-[11px] text-muted-foreground">{t("posProfile.recommended")}</span>
          <span className="font-mono text-xs font-bold tabular-nums text-emerald-500">
            {faixa[0]}–{faixa[1]}{unidade}
          </span>
        </div>
        <div className="my-1.5 h-px bg-border" />
        <p className="text-[11px] leading-snug text-muted-foreground">
          {baixa ? t("posProfile.lowSampleLong")
                 : dentro ? t("posProfile.inBand")
                 : t(`posProfile.read.${chave}.${acima ? 1 : 0}`, { defaultValue: "" })}
        </p>
        <p className="mt-1.5 font-mono text-[9px] text-muted-foreground/70">
          {t("posProfile.handsHere", { n: maos })}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

function Celula({ chave, cel, posicao, maos, ancora }: {
  chave: string;
  cel: PositionStatCell;
  posicao: string;
  maos: number;
  /** O valor do jogador no JOGO TODO. Ancora honesta: nao e regua externa, e ele mesmo. */
  ancora?: number | null;
}) {
  const { t } = useTranslation("dashboard");
  const escala = ESCALA[chave] ?? [0, 100];
  const baixa = cel.band === "low_sample";
  const marca = pct(cel.value, escala);
  const marcaAncora = ancora != null ? pct(ancora, escala) : null;
  const unidade = chave === "af" ? "x" : "%";
  const delta = ancora != null ? cel.value - ancora : null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex flex-col gap-1 cursor-default">
          <span
            className={cn(
              "font-mono text-[11px] font-bold tabular-nums leading-none",
              baixa ? "text-muted-foreground/50" : "text-foreground"
            )}
          >
            {baixa ? "—" : cel.value}
          </span>
          {/* Sem banda pintada: a grade descreve, nao acusa. O tracinho e o SEU numero do
              jogo todo, entao o olho le a FORMA (de onde voce sobe e de onde voce desce)
              sem que nada precise virar vermelho. */}
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/15">
            {marcaAncora != null && (
              <div
                className="absolute inset-y-0 w-px bg-muted-foreground/40"
                style={{ left: `${marcaAncora}%` }}
                aria-hidden
              />
            )}
            {!baixa && (
              <div
                className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-1 ring-background"
                style={{ left: `${marca}%` }}
              />
            )}
          </div>
        </div>
      </TooltipTrigger>

      <TooltipContent side="top" className="w-[210px] p-3">
        <div className="mb-2 font-mono text-[9px] uppercase tracking-widest text-primary">
          {ROTULO[chave] ?? chave} · {posicao}
        </div>
        <div className="flex items-baseline justify-between gap-3 py-0.5">
          <span className="text-[11px] text-muted-foreground">{t("posProfile.you")}</span>
          <span className="font-mono text-xs font-bold tabular-nums text-foreground">
            {baixa ? "—" : `${cel.value}${unidade}`}
          </span>
        </div>
        {ancora != null && (
          <div className="flex items-baseline justify-between gap-3 py-0.5">
            <span className="text-[11px] text-muted-foreground">{t("posProfile.yourGame")}</span>
            <span className="font-mono text-xs tabular-nums text-muted-foreground">
              {ancora}{unidade}
            </span>
          </div>
        )}
        <div className="my-1.5 h-px bg-border" />
        <p className="text-[11px] leading-snug text-muted-foreground">
          {baixa
            ? t("posProfile.lowSampleLong")
            : delta != null
              ? t("posProfile.vsYourGame", {
                  delta: `${delta > 0 ? "+" : ""}${delta.toFixed(1)}`,
                  unit: unidade,
                })
              : t("posProfile.descriptive")}
        </p>
        <p className="mt-1.5 font-mono text-[9px] text-muted-foreground/70">
          {t("posProfile.handsHere", { n: maos })}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

export function V2PositionProfileCard({
  data,
  geral,
}: {
  data?: PositionProfileResponse | null;
  /** O payload do HUD PRINCIPAL, para a linha TOTAL. Deliberadamente NAO recalculado aqui:
   *  a linha existe para o jogador conferir que a grade reconcilia com o numero grande da
   *  tela, e reconstruir a conta abriria a porta para as duas discordarem — foi exatamente
   *  isso (duas fontes para a mesma estatistica) que quebrou o HUD do torneio em 05/09.
   *  Vindo do mesmo payload, elas nao TEM como divergir. */
  geral?: PlayerStatsResponse | null;
}) {
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

  /** Celulas do TOTAL, montadas do payload do HUD principal (valor + a flag que ele ja
   *  traz). Nao e a MEDIA das linhas: media simples de percentual entre assentos de volume
   *  diferente da outro numero, e ai a linha mentiria justamente onde deveria provar
   *  coerencia. E o agregado ponderado, que e o que o HUD grande mostra. */
  /** Maos que o backend contou mas que nao cairam em nenhum dos 8 assentos da grade
   *  (rotulos MP/MP1/MP2/LJ de alguns historicos). Diferenca declarada, nunca escondida. */
  const forasDaGrade = useMemo(() => {
    if (!geral?.total_hands || linhas.length === 0) return 0;
    const soma = linhas.reduce((acc, l) => acc + (l.hands || 0), 0);
    return Math.max(0, geral.total_hands - soma);
  }, [geral, linhas]);

  const totalCels = useMemo(() => {
    if (!geral) return null;
    const out: Record<string, { valor: number; marcador: PlayerStatFlag }> = {};
    for (const k of colunas) {
      const v = (geral as unknown as Record<string, number | null>)[k];
      const f = geral.flags?.[k];
      if (v == null || !f) continue;
      out[k] = { valor: v, marcador: f };
    }
    return Object.keys(out).length ? out : null;
  }, [geral, colunas]);
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
        {geral ? <> {t("posProfile.totalHint")}</> : null}
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
                    <Celula key={k} chave={k} cel={linha.stats[k]} posicao={linha.position}
                            maos={linha.hands}
                            ancora={(geral as unknown as Record<string, number | null>)?.[k] ?? null} />
                  ) : (
                    <span key={k} className="font-mono text-[11px] text-muted-foreground/25">—</span>
                  )
                )}
              </div>
            ))}
          </div>

          {/* TOTAL: o mesmo numero do HUD principal, na mesma regua. Serve de conferencia
              — o jogador ve a grade fechar com o numero grande da tela. Ponderado por
              volume, nao media das linhas (ver `totalCels`). */}
          {totalCels && (
            <div
              className="mt-2.5 grid items-center gap-x-3 border-t border-border/60 pt-2.5"
              style={{ gridTemplateColumns: `3.25rem 2.75rem repeat(${colunas.length}, minmax(3rem, 1fr))` }}
            >
              <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-primary">
                {t("posProfile.total")}
              </span>
              <span className="font-mono text-[9px] text-muted-foreground tabular-nums text-right">
                {geral?.total_hands ?? ""}
              </span>
              {colunas.map((k) =>
                totalCels[k] ? (
                  <CelulaTotal
                    key={k}
                    chave={k}
                    valor={totalCels[k].valor}
                    marcador={totalCels[k].marcador}
                    maos={geral?.total_hands ?? 0}
                  />
                ) : (
                  <span key={k} className="font-mono text-[11px] text-muted-foreground/25">—</span>
                )
              )}
            </div>
          )}
        </div>
      </div>
      </TooltipProvider>

      {/* A grade tem 8 assentos; o parser tambem emite MP/MP1/MP2/LJ em alguns historicos, e
          essas maos nao entram em linha nenhuma. Medido em 05/09: 13 de 26.588 no acervo do
          Rullian (0,05%). Some CALADO — e ausencia muda e o pior tipo, porque o jogador soma
          os assentos, nao fecha com o Total, e nao tem como saber por que. Declarada aqui. */}
      {forasDaGrade > 0 && (
        <p className="mt-2 font-mono text-[9px] text-muted-foreground/70">
          {t("posProfile.outsideGrid", { n: forasDaGrade.toLocaleString() })}
        </p>
      )}

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
