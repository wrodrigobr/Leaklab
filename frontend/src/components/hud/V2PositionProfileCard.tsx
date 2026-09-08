import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { metrics } from "@/lib/api";
import type { PlayerStatsResponse, PositionDetailResponse, PositionOpenMatrixResponse, PositionProfileResponse, PositionStatCell, StackBand } from "@/lib/api";
import { MatrizDeAbertura } from "./MatrizDeAbertura";

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
  wtsd: "WTSD",
  three_bet: "3Bet",
  w_at_sd: "W$SD",
};

/** Rótulo dos chips de stack. Jargão fica em inglês/numérico nos 3 idiomas. */
const ROTULO_DA_FAIXA: Record<string, string> = { "40+": "40bb+", "20-40": "20–40bb", "<20": "<20bb" };

/** Colunas que dependem de ABRIR o pote: a BB nunca abre, entao a celula e "n/a" por regra. */
const SEM_CHART_NA_BB = new Set(["rfi", "fold_to_3bet"]);

/** Colunas com o painel "contra quem". Sao as que misturam oponentes na media do assento. */
// "rfi" abre a MATRIZ das maos abertas (AY-15 c); 3-Bet e Fold abrem o "contra quem"
const COM_DETALHE = new Set(["rfi", "three_bet", "fold_to_3bet"]);

/** O painel "contra quem": uma linha por oponente, com oportunidades, o seu numero, a faixa
 *  do solver e a regua. Ocupa a largura da grade (col-span total), logo abaixo do assento. */
function Detalhe({ stat, position, dados, erro }: {
  stat: string; position: string; dados: PositionDetailResponse | null; erro: boolean;
}) {
  const { t } = useTranslation("dashboard");
  return (
    <div className="mt-2" data-testid={`detalhe-${stat}-${position}`}>
      {erro ? (
        <p className="text-[11px] text-muted-foreground">{t("posProfile.detail.error")}</p>
      ) : !dados ? (
        <p className="font-mono text-[10px] text-muted-foreground/60">…</p>
      ) : dados.rows.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">{t("posProfile.detail.empty")}</p>
      ) : (
        <div className="grid items-center gap-x-3 gap-y-2" style={{ gridTemplateColumns: "4rem 4rem 3.5rem 5.5rem" }}>
          <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">{t("posProfile.detail.vs")}</span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">{t("posProfile.detail.opps")}</span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">{t("posProfile.you")}</span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">{t("posProfile.detail.solver")}</span>
          {/* Total no topo: o numero da celula, para o leitor ver que as linhas o decompoem
              (dono, 07/09: clicou no 47,3 e o modal so mostrava 41,8, do unico oponente com amostra). */}
          {dados.total && dados.total.value != null && (() => {
            const ladoT = dados.total.ref ? foraDaFaixa(dados.total.value, dados.total.ref.lo, dados.total.ref.hi) : null;
            return (
              <div className="contents" data-testid="detalhe-linha-total">
                <span className="border-b border-border/60 pb-1.5 font-mono text-[10px] font-bold uppercase text-primary">{t("posProfile.detail.total")}</span>
                <span className="border-b border-border/60 pb-1.5 font-mono text-[9px] tabular-nums text-muted-foreground/70 text-right">{dados.total.n}</span>
                <span data-testid="detalhe-valor-total" data-fora={ladoT ?? undefined}
                      className={cn("border-b border-border/60 pb-1.5 font-mono text-[12px] font-bold tabular-nums",
                                    ladoT === "in" ? "text-emerald-400" : ladoT ? "text-red-400" : "text-foreground")}>
                  {dados.total.value}
                  {ladoT && ladoT !== "in" ? <span className="ml-0.5 align-top text-[9px]">{ladoT === "above" ? "▲" : "▼"}</span> : null}
                </span>
                <span className="border-b border-border/60 pb-1.5 font-mono text-[10px] tabular-nums text-muted-foreground">
                  {dados.total.ref ? `${dados.total.ref.lo}–${dados.total.ref.hi}` : "—"}
                </span>
              </div>
            );
          })()}
          {dados.rows.map((r) => {
            const baixa = r.band === "low_sample";
            const lado = r.ref && !baixa ? foraDaFaixa(r.value, r.ref.lo, r.ref.hi) : null;
            return (
              <div key={r.vs} className="contents" data-testid={`detalhe-linha-${r.vs}`}>
                <span className="font-mono text-[10px] font-bold uppercase text-foreground">{r.vs}</span>
                <span className="font-mono text-[9px] tabular-nums text-muted-foreground/70 text-right">{r.n}</span>
                <span
                  data-testid={`detalhe-valor-${r.vs}`}
                  data-fora={lado ?? undefined}
                  className={cn("font-mono text-[12px] font-bold tabular-nums",
                                baixa ? "text-muted-foreground/40" : lado === "in" ? "text-emerald-400" : lado ? "text-red-400" : "text-foreground")}
                >
                  {baixa ? "—" : r.value}
                  {lado && lado !== "in" ? <span className="ml-0.5 align-top text-[9px]">{lado === "above" ? "▲" : "▼"}</span> : null}
                </span>
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                  {r.ref ? `${r.ref.lo}–${r.ref.hi}` : "—"}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-2 font-mono text-[9px] text-muted-foreground/60">{t("posProfile.detail.note", { n: dados?.minimo ?? 30 })}</p>
    </div>
  );
}

/** Verbo do tooltip, por stat: "abre", "dá 3-bet", "folda ao 3-bet". A chave de i18n leva o
 *  stat; sem entrada, cai no genérico. */
const VERBO: Record<string, string> = { vpip: "vpip", pfr: "pfr", rfi: "rfi", three_bet: "threeBet", fold_to_3bet: "fold3bet" };

/** Direcao do desvio: "in" dentro da faixa do solver, "above"/"below" fora. */
function foraDaFaixa(valor: number, lo: number, hi: number): "in" | "above" | "below" {
  return valor < lo ? "below" : valor > hi ? "above" : "in";
}

/**
 * Uma célula: SO o numero, colorido (07/09, decisao do dono: a regua ocupava espaco e poluia).
 *
 * Verde = dentro do que o solver faria com as suas maos; vermelho = fora, com um glifo de
 * direcao (▲ acima, ▼ abaixo) para nao precisar abrir o tooltip so para saber o lado. Branco =
 * sem referencia; "—" = amostra baixa. O tamanho do desvio e a faixa do solver ficam no
 * tooltip. Sem regua desenhada a grade cabe sem rolagem e a coluna se le de uma vez.
 */
function Celula({ chave, cel, posicao, maos, ancora, destaque, stack, onDetalhe, aberto }: {
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
  /** abre/fecha o painel "contra quem"; so nas colunas que tem detalhe */
  onDetalhe?: () => void;
  aberto?: boolean;
}) {
  const { t } = useTranslation("dashboard");
  const baixa = cel.band === "low_sample";
  const unidade = chave === "af" ? "x" : "%";
  const delta = ancora != null ? cel.value - ancora : null;
  const ref = cel.ref;
  const foraDaRef = ref && !baixa ? (cel.value < ref.lo ? cel.value - ref.lo : cel.value > ref.hi ? cel.value - ref.hi : 0) : null;
  const lado = ref && !baixa && !destaque ? foraDaFaixa(cel.value, ref.lo, ref.hi) : null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {/* Numero + regua SO onde o backend manda `ref` (06/09). O trilho tinha saido em 05/09
            por nao ter referencia; voltou quando a referencia passou a vir do chart. Celula
            com detalhe ("contra quem") abre o painel no clique; o hover segue com o tooltip. */}
        <span
          className={cn("flex w-full flex-col pr-3 rounded-sm", onDetalhe ? "cursor-pointer hover:bg-primary/5" : "cursor-default")}
          onClick={onDetalhe}
          role={onDetalhe ? "button" : undefined}
          aria-expanded={onDetalhe ? aberto : undefined}
          data-testid={onDetalhe ? `celula-${chave}-${posicao}` : undefined}
        >
          {/* UMA tinta: a regua carrega a cor. Numero vermelho + ponto vermelho + trecho
              vermelho era a mesma informacao tres vezes. */}
          <span
            data-testid={`valor-${chave}-${posicao}`}
            data-fora={lado ?? undefined}
            className={cn(
              "font-mono text-[13px] font-bold tabular-nums leading-none",
              // clicavel = sublinhado pontilhado (a convencao de "tem mais" sem virar link)
              onDetalhe && !baixa && "underline decoration-dotted decoration-muted-foreground/50 underline-offset-4",
              baixa ? "text-muted-foreground/40"
                : destaque ? "text-primary"
                : lado === "in" ? "text-emerald-400"
                : lado ? "text-red-400"
                : "text-foreground"
            )}
          >
            {baixa ? "—" : cel.value}
            {lado && lado !== "in" && (
              <span className="ml-0.5 align-top text-[9px]" aria-label={t(lado === "above" ? "posProfile.above" : "posProfile.below")}>
                {lado === "above" ? "▲" : "▼"}
              </span>
            )}
            {onDetalhe && !baixa && (
              <span className={cn("ml-1 inline-block text-[9px] text-muted-foreground/60 transition-transform", aberto && "rotate-90")}>▸</span>
            )}
          </span>
        </span>
      </TooltipTrigger>

      {/* 260px (era 210): "Solver, nas suas profundidades" + "8,4–34%" quebravam em duas linhas (dono, 07/09). */}
      <TooltipContent side="top" className="w-[260px] p-3">
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
            <span className="whitespace-nowrap font-mono text-xs font-bold tabular-nums text-emerald-400">
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
        {/* A frase do veredito so quando ha DESVIO: dentro da faixa o ponto verde ja diz tudo, e
            "dentro do que o solver faz daqui" soava estranho (dono, 07/09). */}
        {ref && !baixa && foraDaRef === 0 ? null : (
        <p className="text-[11px] leading-snug text-muted-foreground">
          {baixa
            ? t("posProfile.lowSampleLong")
            : ref && foraDaRef != null
              ? foraDaRef > 0
                ? t(`posProfile.vsSolver.${VERBO[chave] ?? "generic"}.above`, { delta: foraDaRef.toFixed(1) })
                : t(`posProfile.vsSolver.${VERBO[chave] ?? "generic"}.below`, { delta: (-foraDaRef).toFixed(1) })
            : delta != null
              ? t("posProfile.vsYourGame", {
                  delta: `${delta > 0 ? "+" : ""}${delta.toFixed(1)}`,
                  unit: unidade,
                })
              : t("posProfile.descriptive")}
        </p>
        )}
        <p className="mt-1.5 font-mono text-[9px] text-muted-foreground/70">
          {t("posProfile.handsHere", { n: maos })}
        </p>
        {onDetalhe && !baixa && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDetalhe(); }}
            className="mt-2 w-full rounded-md border border-primary/40 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/10"
            data-testid={`ver-detalhes-${chave}-${posicao}`}
          >
            {chave === "rfi" ? t("posProfile.matrix.open") : t("posProfile.detail.open")}
          </button>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

export function V2PositionProfileCard({
  data,
  geral,
  stack = null,
  onStack,
  agrupado = false,
  onAgrupado,
  lastN = null,
}: {
  data?: PositionProfileResponse | null;
  /** faixa de stack em vigor (null = todos) e o setter, que mora no Index */
  stack?: StackBand | null;
  onStack?: (s: StackBand | null) => void;
  /** AY-21: grade agrupada (EP / MP / CO / BTN / SB / BB) em vez de assento a assento */
  agrupado?: boolean;
  onAgrupado?: (v: boolean) => void;
  /** o recorte de volume da tela, para o detalhe pedir o MESMO conjunto da grade */
  lastN?: number | null;
  /** O payload do HUD PRINCIPAL, para a linha TOTAL. Deliberadamente NAO recalculado aqui:
   *  a linha existe para o jogador conferir que a grade reconcilia com o numero grande da
   *  tela, e reconstruir a conta abriria a porta para as duas discordarem — foi exatamente
   *  isso (duas fontes para a mesma estatistica) que quebrou o HUD do torneio em 05/09.
   *  Vindo do mesmo payload, elas nao TEM como divergir. */
  geral?: PlayerStatsResponse | null;
}) {
  const { t } = useTranslation("dashboard");

  /** Painel "contra quem" (06/09): a faixa de 3-Bet e Fold 3-Bet e larga em "todos" por
   *  natureza (o solver da 3-bet 5% contra UTG e 20% contra BTN); aberta por oponente, a
   *  regua estreita e passa a acusar. Um painel por vez; o mesmo clique fecha. */
  const [detalhe, setDetalhe] = useState<{ position: string; stat: string } | null>(null);
  const [detalheDados, setDetalheDados] = useState<PositionDetailResponse | null>(null);
  const [matrizDados, setMatrizDados] = useState<PositionOpenMatrixResponse | null>(null);
  const [detalheErro, setDetalheErro] = useState(false);
  useEffect(() => {
    if (!detalhe) { setDetalheDados(null); setMatrizDados(null); return; }
    let vivo = true;
    setDetalheDados(null); setMatrizDados(null); setDetalheErro(false);
    // RFI abre a matriz das maos abertas (outro endpoint, mesmo recorte); os outros, o "contra quem"
    const pedido = detalhe.stat === "rfi"
      ? metrics.playerStatsByPositionHands(detalhe.position, 90, lastN ?? undefined, stack).then((d) => { if (vivo) setMatrizDados(d); })
      : metrics.playerStatsByPositionDetail(detalhe.position, detalhe.stat, 90, lastN ?? undefined, stack).then((d) => { if (vivo) setDetalheDados(d); });
    pedido.catch(() => { if (vivo) setDetalheErro(true); });
    return () => { vivo = false; };
  }, [detalhe, stack, lastN]);
  // trocar a faixa de stack fecha o painel: o detalhe e da faixa em que foi aberto
  useEffect(() => { setDetalhe(null); }, [stack]);
  const alternaDetalhe = (position: string, stat: string) =>
    setDetalhe((d) => (d && d.position === position && d.stat === stat ? null : { position, stat }));

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
  const trilhas = `3.5rem 3rem ${colunas.map(() => "minmax(4.5rem, 1fr)").join(" ")}`;

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

  /** Fonte da linha TOTAL: a propria grade quando o backend manda `total` (mesmas linhas e
   *  definicoes; o backend prova que e igual ao HUD), senao o payload do HUD principal. */
  const fonteDoTotal = (data?.total ?? geral) as unknown as Record<string, number | null> | null;
  const totalCels = useMemo(() => {
    if (!fonteDoTotal) return null;
    const out: Record<string, PositionStatCell> = {};
    for (const k of colunas) {
      const v = fonteDoTotal[k];
      if (v == null) continue;
      out[k] = { value: v, band: "ok" };
    }
    return Object.keys(out).length ? out : null;
  }, [fonteDoTotal, colunas]);

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
        {onAgrupado && (
          <div className="flex items-center gap-1" role="group" aria-label={t("posProfile.view")} data-testid="grade-visao">
            {([false, true] as const).map((v) => (
              <button
                key={String(v)}
                type="button"
                aria-pressed={agrupado === v}
                onClick={() => onAgrupado(v)}
                className={cn(
                  "rounded-md border px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors",
                  agrupado === v ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                {v ? t("posProfile.grouped") : t("posProfile.detailed")}
              </button>
            ))}
          </div>
        )}
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
        {t("posProfile.legend")} {t("posProfile.clickable")}
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
              <span key={k} className="whitespace-nowrap font-mono text-[9px] uppercase tracking-wider text-muted-foreground/70">
                {ROTULO[k] ?? k}
              </span>
            ))}
          </div>

          <div className="space-y-2">
            {linhas.map((linha) => (
              <div
                key={linha.position}
                className="grid items-start gap-x-2"
                style={{ gridTemplateColumns: trilhas }}
              >
                <span className="font-mono text-[10px] font-bold uppercase text-foreground">
                  {linha.position}
                  {linha.members && linha.members.length > 1 && (
                    <span className="ml-1 font-mono text-[8px] normal-case tracking-normal text-muted-foreground/60" data-testid={`membros-${linha.position}`}>
                      {linha.members.join(" · ")}
                    </span>
                  )}
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
                        <span className="inline-block cursor-default font-mono text-[10px] leading-[13px] text-muted-foreground/40">n/a</span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[200px] p-2 text-[11px]">{t("posProfile.rfiNaBB")}</TooltipContent>
                    </Tooltip>
                  ) : linha.stats[k] ? (
                    <Celula key={k} chave={k} cel={linha.stats[k]} posicao={linha.position}
                            maos={linha.hands} stack={stack}
                            ancora={(geral as unknown as Record<string, number | null>)?.[k] ?? null}
                            onDetalhe={COM_DETALHE.has(k) && linha.stats[k].band !== "low_sample" ? () => alternaDetalhe(linha.position, k) : undefined}
                            aberto={detalhe?.position === linha.position && detalhe?.stat === k} />
                  ) : (
                    <span key={k} className="font-mono text-[13px] leading-none text-muted-foreground/25">—</span>
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
                {fonteDoTotal?.total_hands ?? ""}
              </span>
              {colunas.map((k) =>
                totalCels[k] ? (
                  <Celula
                    key={k}
                    chave={k}
                    cel={totalCels[k]}
                    posicao={t("posProfile.total")}
                    maos={fonteDoTotal?.total_hands ?? 0}
                    destaque
                  />
                ) : (
                  <span key={k} className="font-mono text-[13px] leading-none text-muted-foreground/25">—</span>
                )
              )}
            </div>
          )}
        </div>
      </div>
      </TooltipProvider>

      {/* O detalhe "contra quem" e um MODAL (07/09): a linha inline empurrava a grade e sumia
          ao trocar a faixa. Um por vez; fechar pelo X, pelo Esc ou clicando fora. */}
      <Dialog open={!!detalhe} onOpenChange={(aberto) => { if (!aberto) setDetalhe(null); }}>
        <DialogContent className={detalhe?.stat === "rfi" ? "max-w-4xl" : "max-w-xl"}>
          {detalhe && detalhe.stat === "rfi" && (
            <>
              <DialogTitle className="font-mono text-[11px] uppercase tracking-widest text-primary">
                {t("posProfile.matrix.title", { pos: detalhe.position })}
              </DialogTitle>
              <DialogDescription className="sr-only">{t("posProfile.matrix.description")}</DialogDescription>
              <MatrizDeAbertura position={detalhe.position} stack={stack} dados={matrizDados} erro={detalheErro} />
            </>
          )}
          {detalhe && detalhe.stat !== "rfi" && (
            <>
              <DialogTitle className="font-mono text-[11px] uppercase tracking-widest text-primary">
                {t(`posProfile.detail.${detalhe.stat === "three_bet" ? "threeBet" : "fold3bet"}`, { pos: detalhe.position })}
              </DialogTitle>
              <DialogDescription className="sr-only">{t("posProfile.detail.description")}</DialogDescription>
              <Detalhe stat={detalhe.stat} position={detalhe.position} dados={detalheDados} erro={detalheErro} />
            </>
          )}
        </DialogContent>
      </Dialog>

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
