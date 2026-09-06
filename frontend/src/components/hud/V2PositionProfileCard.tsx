import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { PlayerStatsResponse, PositionProfileResponse, PositionStatCell, StackBand } from "@/lib/api";

/**
 * V2PositionProfileCard — o perfil do jogador em CADA assento.
 *
 * ── A pergunta que este card responde, e a que ele NÃO responde ──────────────────────────
 *
 * O `V2PositionCard` ao lado diz *de onde você erra mais* (alinhamento GTO por posição).
 * Este diz *qual é o seu perfil ali*: VPIP, PFR, 3bet, WTSD por assento. São perguntas
 * diferentes, e a segunda o produto não tinha.
 *
 * ── A régua: só onde há chart (06/09, AY-15) ─────────────────────────────────────────────
 *
 * A régua por assento saiu em 05/09 por não ter referência (a régua do jogo inteiro acusava
 * 5 de 6 jogadores no BB). Voltou em 06/09 SÓ na coluna que tem referência defensável: **RFI**,
 * com a faixa vinda do chart de abertura nas profundidades das mãos do jogador naquele assento
 * (`ref` no payload; o backend calcula, aqui só se desenha). O dono trouxe uma tabela de VPIP
 * por assento; medida contra os charts era mais tight que o solver em todo assento. Folclore
 * não vira régua. VPIP/PFR e o postflop ficam só com o número.
 *
 * E o filtro de stack: escolhida a faixa, os números são das mãos nela e a referência é o
 * chart daquela profundidade. O estado mora no `Index`, porque a linha TOTAL precisa do HUD na
 * MESMA faixa.
 *
 * ── As colunas são FIXAS; as células são progressivas ────────────────────────────────────
 *
 * A grade é o HUD principal aberto por assento: as MESMAS 12 colunas, na MESMA ordem, sempre
 * (decisão do dono, 06/09, ao ver 5 colunas: "deveríamos ter todos os indicadores que temos
 * no HUD"). Antes o card escondia toda coluna que nenhum assento atingia, e com isso a
 * linha TOTAL perdia WTSD/W$SD/3Bet mesmo tendo o número — o HUD grande mostrava o que a
 * grade dizia não existir. Agora a coluna existe, e o que continua progressivo é a CÉLULA:
 * medido em produção, `W$SD` pede 2.000 mãos e `WTSD` 1.000, e dividir o acervo por 9
 * assentos derruba quase todo mundo. Baixar o corte para encher a tela seria inventar
 * leitura (corte mantido pelo dono). Célula sem volume mostra "—" e explica no tooltip.
 *
 * As linhas seguem a ORDEM DE FALA na mesa (UTG primeiro, BB por último), não a ordem
 * alfabética nem a de volume: a posição relativa é a informação, e ler de cima para baixo
 * é ler a mão acontecendo.
 */

/** Rótulo de cada coluna. Jargão de poker fica em INGLÊS nos 3 idiomas, por convenção do
 *  produto — é o que o `PlayerStatsCard` ao lado já faz. Criar chave de i18n para "VPIP"
 *  seria triplicar uma string que não se traduz. */
const ROTULO: Record<string, string> = {
  vpip: "VPIP",
  pfr: "PFR",
  rfi: "RFI",
  af: "AF",
  cbet_pct: "C-Bet",
  fold_to_flop_bet: "Fold vs Bet",
  bb_defense: "BB Defense",
  steal_pct: "Steal",
  open_limp_pct: "Open Limp",
  fold_to_3bet: "Fold 3Bet",
  fold_to_3bet_open: "Fold 3Bet",
  wtsd: "WTSD",
  three_bet: "3Bet",
  w_at_sd: "W$SD",
};

/** Rótulo dos chips de stack. Jargão fica em inglês/numérico nos 3 idiomas. */
const ROTULO_DA_FAIXA: Record<string, string> = { "40+": "40bb+", "20-40": "20–40bb", "<20": "<20bb" };

/** Topo da escala da régua, por stat. Escala absoluta por coluna, para o ponto ser comparável
 *  entre assentos: BTN abre metade das mãos, UTG um sexto. Só tem régua quem está aqui. */
const ESCALA: Record<string, number> = { vpip: 60, pfr: 50, rfi: 60, three_bet: 30, fold_to_3bet_open: 100 };

/** Colunas que dependem de ABRIR o pote: a BB nunca abre, entao a celula e "n/a" por regra. */
const SEM_CHART_NA_BB = new Set(["rfi", "fold_to_3bet_open"]);

/** Verbo do tooltip, por stat: "abre", "dá 3-bet", "folda ao 3-bet". A chave de i18n leva o
 *  stat; sem entrada, cai no genérico. */
const VERBO: Record<string, string> = { vpip: "vpip", pfr: "pfr", rfi: "rfi", three_bet: "threeBet", fold_to_3bet_open: "fold3bet" };

/** Régua de uma célula com `ref`: faixa verde do chart, ponto no valor, tinta só no excesso
 *  (entre a borda da faixa e o ponto). Quem está dentro não gasta tinta. */
function Regua({ chave, valor, lo, hi }: { chave: string; valor: number; lo: number; hi: number }) {
  const topo = ESCALA[chave] ?? 100;
  const pct = (v: number) => Math.max(0, Math.min(100, (v / topo) * 100));
  const fora = valor < lo ? "below" : valor > hi ? "above" : "in";
  const tinta = fora === "below" ? [pct(valor), pct(lo)] : fora === "above" ? [pct(hi), pct(valor)] : null;
  return (
    <div className="relative mt-2 h-1.5 w-full rounded-full bg-muted/25" data-testid={`regua-${chave}`} data-fora={fora}>
      <div className="absolute top-0 h-1.5 rounded-full bg-emerald-500/40" style={{ left: `${pct(lo)}%`, width: `${pct(hi) - pct(lo)}%` }} />
      {tinta && (
        <div className="absolute top-0 h-1.5 rounded-full bg-red-500/70" style={{ left: `${tinta[0]}%`, width: `${tinta[1] - tinta[0]}%` }} />
      )}
      <div
        className={cn("absolute -top-[3px] size-3 -translate-x-1/2 rounded-full ring-2 ring-card",
                      fora === "in" ? "bg-emerald-400" : "bg-red-400")}
        style={{ left: `${pct(valor)}%` }}
      />
    </div>
  );
}

/**
 * Uma célula. Só o EXCESSO ganha cor, e só onde há régua.
 *
 * Com `ref` (RFI): a faixa do chart está sempre desenhada em verde; quando o valor sai dela,
 * o trecho **entre a borda da faixa e o valor** é pintado. Sem `ref`: só o número, e a
 * comparação honesta (este assento contra o seu jogo todo) vive no tooltip, em frase.
 */
function Celula({ chave, cel, posicao, maos, ancora, destaque, stack }: {
  chave: string;
  cel: PositionStatCell;
  posicao: string;
  maos: number;
  /** O valor do jogador no JOGO TODO. Ancora honesta: nao e regua externa, e ele mesmo. */
  ancora?: number | null;
  /** A linha TOTAL. So muda o peso visual: ela e a ANCORA de conferencia, nao um veredito. */
  destaque?: boolean;
  /** faixa de stack em vigor, para o tooltip dizer de qual chart a referencia veio */
  stack?: StackBand | null;
}) {
  const { t } = useTranslation("dashboard");
  const baixa = cel.band === "low_sample";
  const unidade = chave === "af" ? "x" : "%";
  const delta = ancora != null ? cel.value - ancora : null;
  const ref = cel.ref;
  const foraDaRef = ref && !baixa ? (cel.value < ref.lo ? cel.value - ref.lo : cel.value > ref.hi ? cel.value - ref.hi : 0) : null;
  /** Os 3 contextos com mais peso aparecem nomeados; o resto vira "outros N%". */
  const pesos = ref ? Object.entries(ref.pesos).slice(0, 3) : [];
  const outros = ref ? Object.values(ref.pesos).reduce((s, w) => s + w, 0) - pesos.reduce((s, [, w]) => s + w, 0) : 0;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {/* SO o numero (decisao do dono, 05/09). O trilho saiu junto com o veredito, e nao
            por economia de tinta: um trilho sem referencia tem a APARENCIA de instrumento de
            medida, entao o olho procura o alvo que nao existe — a mesma linguagem visual que
            acabamos de remover, convidando o leitor a inferir uma regua que decidimos nao
            ter. A escala tambem era arbitraria: VPIP desenhado em 0-60 e AF em 0-8 pareciam
            o mesmo widget sem serem comparaveis. A comparacao honesta (este assento contra o
            seu jogo todo) vive no tooltip, em frase, onde nao vira grafico sem eixo. */}
        <span className="flex min-h-[30px] w-full cursor-default flex-col pr-4">
          {/* UMA tinta: a regua carrega a cor. Numero vermelho + ponto vermelho + trecho
              vermelho era a mesma informacao tres vezes. */}
          <span
            className={cn(
              "font-mono text-[13px] font-bold tabular-nums leading-none",
              baixa ? "text-muted-foreground/40" : destaque ? "text-primary" : "text-foreground"
            )}
          >
            {baixa ? "—" : cel.value}
          </span>
          {ref && !baixa && !destaque && <Regua chave={chave} valor={cel.value} lo={ref.lo} hi={ref.hi} />}
        </span>
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
        {ref ? (
          <div className="flex items-baseline justify-between gap-3 py-0.5">
            <span className="text-[11px] text-muted-foreground">
              {ref.tipo === "media"
                ? t("posProfile.solverYourHands")
                : stack ? t("posProfile.solverBand", { band: ROTULO_DA_FAIXA[stack] ?? stack }) : t("posProfile.solverHere")}
            </span>
            <span className="font-mono text-xs font-bold tabular-nums text-emerald-400">
              {ref.lo}–{ref.hi}%
            </span>
          </div>
        ) : ancora != null && (
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
            : ref && foraDaRef != null
              ? foraDaRef > 0
                ? t(`posProfile.vsSolver.${VERBO[chave] ?? "generic"}.above`, { delta: foraDaRef.toFixed(1) })
                : foraDaRef < 0
                  ? t(`posProfile.vsSolver.${VERBO[chave] ?? "generic"}.below`, { delta: (-foraDaRef).toFixed(1) })
                  : t("posProfile.inSolver")
            : delta != null
              ? t("posProfile.vsYourGame", {
                  delta: `${delta > 0 ? "+" : ""}${delta.toFixed(1)}`,
                  unit: unidade,
                })
              : t("posProfile.descriptive")}
        </p>
        {ref && (
          <p className="mt-1.5 font-mono text-[9px] leading-snug text-muted-foreground/70">
            {t("posProfile.charts")}: {pesos.map(([b, w]) => `${b} ${w}%`).join(" · ")}
            {outros > 0 ? ` · ${t("posProfile.chartsOthers", { pct: outros })}` : ""}
            <br />
            {ref.tipo === "media" ? t("posProfile.bandMean", { pp: ref.folga }) : t("posProfile.band", { pp: ref.folga })}
            {ref.tipo === "media" && ref.valor_coberto != null && ref.cobertura != null && ref.cobertura < 100 && (
              <>
                <br />
                {t("posProfile.youCovered", { value: ref.valor_coberto })}
              </>
            )}
            {ref.cobertura != null && ref.cobertura < 100 && (
              <>
                <br />
                {t("posProfile.coverage", { pct: ref.cobertura })}
              </>
            )}
          </p>
        )}
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
  stack = null,
  onStack,
}: {
  data?: PositionProfileResponse | null;
  /** faixa de stack em vigor (null = todos) e o setter, que mora no Index */
  stack?: StackBand | null;
  onStack?: (s: StackBand | null) => void;
  /** O payload do HUD PRINCIPAL, para a linha TOTAL. Deliberadamente NAO recalculado aqui:
   *  a linha existe para o jogador conferir que a grade reconcilia com o numero grande da
   *  tela, e reconstruir a conta abriria a porta para as duas discordarem — foi exatamente
   *  isso (duas fontes para a mesma estatistica) que quebrou o HUD do torneio em 05/09.
   *  Vindo do mesmo payload, elas nao TEM como divergir. */
  geral?: PlayerStatsResponse | null;
}) {
  const { t } = useTranslation("dashboard");

  /** TODAS as colunas do payload, sempre, na ordem em que o backend as declara (a ordem do
   *  HUD principal). Filtrar pelas que "algum assento atinge" era o que escondia da linha
   *  TOTAL um numero que o HUD grande mostrava. */
  const colunas = useMemo(
    () => [...(data?.sempre ?? []), ...(data?.com_volume ?? [])],
    [data],
  );

  const linhas = data?.positions ?? [];

  /** Largura das colunas. A coluna com regua (RFI) precisa de trilho legivel; as outras cabem
   *  no rotulo mais longo sem quebrar ("Fold vs Bet"). A 1a versao dava 4rem a todas e a
   *  regua, com 78px fixos, invadia a coluna vizinha. */
  const trilhas = `3.5rem 3rem ${colunas.map((k) => (ESCALA[k] ? "minmax(8rem, 1.6fr)" : "minmax(4rem, 1fr)")).join(" ")}`;

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
    const out: Record<string, PositionStatCell> = {};
    for (const k of colunas) {
      const v = (geral as unknown as Record<string, number | null>)[k];
      if (v == null) continue;
      out[k] = { value: v, band: "ok" };
    }
    return Object.keys(out).length ? out : null;
  }, [geral, colunas]);

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
        {onStack && (
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={t("posProfile.stack")}>
            <span className="mr-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">
              {t("posProfile.stack")}
            </span>
            {[null, ...((data.faixas ?? []) as StackBand[])].map((f) => (
              <button
                key={f ?? "all"}
                type="button"
                aria-pressed={stack === f}
                onClick={() => onStack(f)}
                className={cn(
                  "rounded-md border px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors",
                  stack === f
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                {f ? ROTULO_DA_FAIXA[f] ?? f : t("posProfile.stackAll")}
              </button>
            ))}
          </div>
        )}
        <span className="font-mono text-[9px] text-muted-foreground/70 tabular-nums">
          {stack ? t("posProfile.stackHands", { n: data.total_hands }) : t("posProfile.hands", { n: data.total_hands })}
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
        <div className="w-full min-w-max">
          <div
            className="grid items-end gap-x-2 pb-1.5 mb-1.5 border-b border-border/50"
            style={{ gridTemplateColumns: trilhas }}
          >
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">
              {t("posProfile.seat")}
            </span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">
              {t("posProfile.handsShort")}
            </span>
            {colunas.map((k) => (
              <span key={k} className="whitespace-nowrap font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {ROTULO[k] ?? k}
              </span>
            ))}
          </div>

          <div className="space-y-2.5">
            {linhas.map((linha) => (
              <div
                key={linha.position}
                className="grid items-start gap-x-2"
                style={{ gridTemplateColumns: trilhas }}
              >
                <span className="font-mono text-[10px] font-bold uppercase text-foreground">
                  {linha.position}
                </span>
                <span className="font-mono text-[9px] text-muted-foreground/70 tabular-nums text-right">
                  {linha.hands}
                </span>
                {colunas.map((k) =>
                  SEM_CHART_NA_BB.has(k) && linha.position === "BB" ? (
                    // A BB nao abre pote: nem RFI nem fold ao 3-bet do open. "n/a" e nao "—":
                    // traco e amostra baixa, isto e regra.
                    <Tooltip key={k}>
                      <TooltipTrigger asChild>
                        <span className="inline-block min-h-[30px] cursor-default font-mono text-[10px] leading-[13px] text-muted-foreground/40">n/a</span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[200px] p-2 text-[11px]">{t("posProfile.rfiNaBB")}</TooltipContent>
                    </Tooltip>
                  ) : linha.stats[k] ? (
                    <Celula key={k} chave={k} cel={linha.stats[k]} posicao={linha.position}
                            maos={linha.hands} stack={stack}
                            ancora={(geral as unknown as Record<string, number | null>)?.[k] ?? null} />
                  ) : (
                    <span key={k} className="min-h-[30px] font-mono text-[13px] leading-none text-muted-foreground/25">—</span>
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
              className="mt-2.5 grid items-start gap-x-2 border-t border-border/60 pt-2.5"
              style={{ gridTemplateColumns: trilhas }}
            >
              <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-primary">
                {t("posProfile.total")}
              </span>
              <span className="font-mono text-[9px] text-muted-foreground tabular-nums text-right">
                {geral?.total_hands ?? ""}
              </span>
              {colunas.map((k) =>
                totalCels[k] ? (
                  <Celula
                    key={k}
                    chave={k}
                    cel={totalCels[k]}
                    posicao={t("posProfile.total")}
                    maos={geral?.total_hands ?? 0}
                    destaque
                  />
                ) : (
                  <span key={k} className="min-h-[30px] font-mono text-[13px] leading-none text-muted-foreground/25">—</span>
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
    </div>
  );
}
