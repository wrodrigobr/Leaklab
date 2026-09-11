import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { RangeGrid } from "@/components/replayer/RangeGrid";
import type { RangeSet } from "@/data/ranges";
import type { PositionOpenMatrixResponse, StackBand, TableSize } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Matriz 13x13 das maos que o jogador ABRIU de um assento, contra o que o solver abriria com
 * as mesmas maos nos mesmos stacks (AY-15 c, sugestao do Rullian). Abre pela celula RFI do
 * Perfil por posicao.
 *
 * ── O desenho de 09/09 (AY-34), nascido de uma duvida do mesmo fundador ──────────────────
 *
 * "Em relacao ao UTG, to achando essa porcentagem que o solver abriria um tanto quanto alta,
 * de onde vem esse valor?". Vinha da carta certa; a tela e que calava tres coisas.
 *
 * 1. A carta de abertura e funcao de ASSENTO, JOGADORES NA MESA e STACK. Os tres sao filtros
 *    aqui, e nenhum tem "todos": sem os tres fixos o numero do solver e uma media entre cartas,
 *    que muda com o VOLUME do jogador e nao com o jogo (a linha "UTG" dele somava cinco
 *    assentos, comparados com cartas de 15,8% a 28,0%). Cada filtro abre onde ha mais maos, e
 *    o backend DECLARA o que aplicou (`mesa`, `stack_band`, `*_auto`).
 * 2. A comparacao e UM par de numeros sobre AS MESMAS maos: "voce abriu X% das maos que
 *    recebeu; o solver abriria Y% com essas mesmas maos". O tamanho do range completo do
 *    solver (`solver_pct_todas`) NAO e comparavel com o do jogador (denominadores diferentes:
 *    56,4% "abrindo mais" que 54,6% era na verdade 56,4% contra 59,0%), entao ele vira legenda
 *    da grade — e so isso que ele e, o tamanho do desenho.
 * 3. A linha sob a grade do solver diz POR QUE o range e o que e: quantos jogadores ainda agem
 *    depois do assento naquela mesa. Sem o nome do assento no vocabulario 9-max ("UTG+2"),
 *    porque a tela chama esse mesmo assento de UTG e o nome trocaria uma duvida por outra.
 *
 * Abaixo do piso de amostra nenhum dos dois numeros sai (com 10 maos os dois lados sao ruido;
 * foi assim que "solver 7,2%" apareceu ao lado de uma grade cheia em 08/09). As grades e a
 * lista de divergencias continuam.
 *
 * Os assentos que EXISTEM na mesa em vigor vem do backend (`assentos`): mesa 8 tem UTG+1,
 * mesa 6 nao tem LJ. A BB aparece desligada, com o motivo: ela nao abre o pote.
 */
const ROTULO_DA_FAIXA: Record<string, string> = { "40+": "40+ bb", "20-40": "20–40 bb", "<20": "< 20 bb" };
/** rotulos crus de assento; um GRUPO da grade (EP, MP) nao esta aqui e nunca e redirecionado */
const ASSENTOS_CONHECIDOS = new Set(["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB"]);
/** abaixo disto a diferenca e "no alvo": e menor que o ruido de uma faixa de stack */
const FOLGA_PP = 3;

function comoRange(cells: PositionOpenMatrixResponse["cells"], lado: "voce" | "solver", label: string): RangeSet {
  const raise = new Set<string>();
  const frequencies: RangeSet["frequencies"] = {};
  for (const [hand, c] of Object.entries(cells)) {
    const f = lado === "voce" ? c.voce : c.solver;
    if (f == null) continue;
    // na SUA grade o limp aparece como call (azul), separado do fold: limpar AA nao e foldar AA
    frequencies[hand] = lado === "voce" && c.limp ? { raise: f, call: c.limp } : { raise: f };
    if (f > 0.001) raise.add(hand);
  }
  return { raise, label, frequencies };
}

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);
const CABECALHO = "border-b border-border/60 pb-1 font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60";
const CELULA = "border-b border-border/30 py-1";
const ROTULO_GRUPO = "font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60";

export function MatrizDeAbertura({ position, stack, mesa, dados, erro, faixas, mesas, onMudar }: {
  position: string;
  /** faixa e mesa PEDIDAS; enquanto o backend nao responde, `dados` e que diz as em vigor */
  stack?: StackBand | null;
  mesa?: TableSize | null;
  dados: PositionOpenMatrixResponse | null;
  erro: boolean;
  /** faixas e tamanhos de mesa que o backend aceita; os chips trocam os tres filtros sem sair do modal */
  faixas?: StackBand[];
  mesas?: Array<{ mesa: TableSize; n: number; pct: number }>;
  onMudar?: (position: string, stack: StackBand | null, mesa: TableSize | null) => void;
}) {
  const { t } = useTranslation("dashboard");
  const voce = useMemo(() => (dados ? comoRange(dados.cells, "voce", "voce") : null), [dados]);
  // maos que o jogador nunca recebeu deste assento: apagadas na grade dele (nao e fold)
  const nuncaRecebidas = useMemo(() => new Set(dados ? Object.entries(dados.cells).filter(([, c]) => c.n === 0).map(([h]) => h) : []), [dados]);
  const solver = useMemo(() => (dados ? comoRange(dados.cells, "solver", "solver") : null), [dados]);

  // O que VALE e o que o backend declarou ter aplicado (sem `?stack=`/`?mesa=` ele escolhe
  // onde ha mais maos). O pedido so prevalece enquanto a resposta nao chega.
  const stackEmVigor: StackBand | null = (stack ?? (dados?.stack_band as StackBand | null) ?? null);
  const mesaEmVigor: TableSize | null = mesa ?? dados?.mesa ?? null;
  const assentos = dados?.assentos ?? [position];
  // A distribuicao do PROPRIO modal vem primeiro, e ela conta o ASSENTO em vigor (dono,
  // 09/09: o chip dizia 114 maos e o recorte de BTN entregou 1 — os 114 eram de todos os
  // assentos com 9 jogadores). As props sao so fallback para quem monta o modal sem elas.
  const faixasProprias = (dados?.distribuicao_de_stacks?.faixas ?? []).map((f) => f.faixa);
  const faixasChips = (faixasProprias.length ? faixasProprias : (faixas ?? [])) as StackBand[];
  const maosNaFaixa = (f: StackBand) => (dados?.distribuicao_de_stacks?.faixas ?? []).find((x) => x.faixa === f)?.n ?? null;

  // O assento pedido pode NAO existir na mesa que passou a valer (UTG+1 some com 7 na mao, LJ
  // some com 6): o modal volta para o UTG em vez de mostrar um recorte vazio.
  useEffect(() => {
    if (!dados || !onMudar || !dados.assentos) return;
    if (ASSENTOS_CONHECIDOS.has(position) && !dados.assentos.includes(position)) {
      onMudar("UTG", stackEmVigor, mesaEmVigor);
    }
  }, [dados, position, onMudar, stackEmVigor, mesaEmVigor]);

  const chip = (ativo: boolean, onClick: (() => void) | undefined, rotulo: React.ReactNode, testid: string, extra?: { title?: string; desligado?: boolean }) => (
    <button type="button" key={testid} data-testid={testid} aria-pressed={ativo} onClick={onClick} disabled={!onClick} title={extra?.title}
            className={cn("rounded-md border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider transition-colors",
                          ativo ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground",
                          !onClick && !extra?.desligado && "cursor-default",
                          extra?.desligado && "cursor-help border-dashed text-muted-foreground/40 hover:text-muted-foreground/60")}>
      {rotulo}
    </button>
  );
  const seletores = (
    <div className="mb-2 flex flex-wrap items-start gap-x-5 gap-y-2" data-testid="matriz-seletores">
      <div className="flex flex-col gap-1">
        <span className={ROTULO_GRUPO}>{t("posProfile.matrix.seat")}</span>
        <div className="flex flex-wrap gap-1.5">
          {assentos.map((p) => chip(p === position, onMudar ? () => onMudar(p, stackEmVigor, mesaEmVigor) : undefined, p, `matriz-pos-${p}`))}
          {/* a BB nao abre o pote: quando todos foldam ela leva os blinds sem agir. Desligada e nao
              ausente: a ausencia parecia esquecimento. */}
          {chip(false, undefined, "BB", "matriz-pos-BB", { title: t("posProfile.matrix.bbNoRfi"), desligado: true })}
        </div>
      </div>
      {/* Sem chip de jogadores (Rullian, 10/09: "essa parte de selecionar numero de jogadores e
          estranha... o PokerTracker nao tem essa separacao"). Medido antes de tirar, no acervo
          dele: somar os tamanhos custa mediana 0,6 pp no numero do solver e multiplica a amostra
          por 2,3. O custo real e SO do UTG, o unico assento que existe em toda mesa — e ali a
          linha abaixo da grade declara a faixa em vez de pedir um filtro. */}
      {faixasChips.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className={ROTULO_GRUPO}>{t("posProfile.stack")}</span>
          <div className="flex flex-wrap gap-1.5">
            {/* "Todas" e o PADRAO desde 11/09: a matriz abre no mesmo recorte da grade, senao a
                tela seguinte contradiz a porta de entrada (Rullian: 17,2% na grade, 19,8% aqui,
                os dois certos, recortes diferentes). Estreitar por profundidade e escolha. */}
            {chip(stackEmVigor == null, onMudar ? () => onMudar(position, null, mesaEmVigor) : undefined,
              <>{t("posProfile.matrix.stackWords.todas")}
                {dados?.distribuicao_de_stacks?.n != null && (
                  <span className="ml-1 normal-case tracking-normal opacity-60">{dados.distribuicao_de_stacks.n.toLocaleString()}</span>
                )}</>, "matriz-stack-todas")}
            {faixasChips.map((f) => {
              const n = maosNaFaixa(f);
              return chip(f === stackEmVigor, onMudar ? () => onMudar(position, f, mesaEmVigor) : undefined,
                <>{ROTULO_DA_FAIXA[f] ?? f}{n != null && <span className="ml-1 normal-case tracking-normal opacity-60">{n.toLocaleString()}</span>}</>, `matriz-stack-${f}`);
            })}
          </div>
        </div>
      )}
    </div>
  );
  if (erro) return <div>{seletores}<p className="text-[11px] text-muted-foreground">{t("posProfile.detail.error")}</p></div>;
  if (!dados || !voce || !solver) return <div>{seletores}<p className="font-mono text-[10px] text-muted-foreground/60">…</p></div>;
  if (dados.n === 0) return <div>{seletores}<p className="text-[11px] text-muted-foreground">{t("posProfile.detail.empty")}</p></div>;

  // SEM tamanho de mesa (10/09): o recorte soma todos os tamanhos desde que o filtro de
  // jogadores saiu, e a frase continuava pedindo `mesa` — sem filtro em vigor, a tela mostrava
  // "em mesas de ? jogadores". Quem declara a variacao de assento e a linha da grade do solver
  // (`composicao_da_carta`), que diz a FAIXA de jogadores por agir e o peso de cada uma.
  // Sem faixa em vigor a frase NAO mostra "?": ela diz que soma as profundidades, que e o
  // recorte de onde o jogador veio (a grade).
  const recorte = stackEmVigor
    ? t("posProfile.matrix.recorte", {
        pos: position,
        stack: t(`posProfile.matrix.stackWords.${stackEmVigor}`),
        n: dados.n.toLocaleString(),
      })
    : t("posProfile.matrix.recorteTodas", { pos: position, n: dados.n.toLocaleString() });
  const delta = dados.voce_pct != null && dados.solver_pct != null ? dados.voce_pct - dados.solver_pct : null;
  const deltaClasse = delta == null ? "" : Math.abs(delta) < FOLGA_PP ? "border-primary/40 text-primary" : delta < 0 ? "border-amber-400/40 text-amber-400" : "border-red-400/40 text-red-400";
  const deltaTexto = delta == null ? "" : Math.abs(delta) < FOLGA_PP ? t("posProfile.matrix.deltaOk")
    : delta < 0 ? t("posProfile.matrix.deltaLess", { pp: Math.abs(delta).toFixed(1) }) : t("posProfile.matrix.deltaMore", { pp: delta.toFixed(1) });

  return (
    <div className="mt-1" data-testid={`matriz-${position}`}>
      {seletores}
      <p className="mb-2 rounded-r-md border-l-2 border-primary/60 bg-muted/20 px-2.5 py-1.5 text-[11px] text-muted-foreground" data-testid="matriz-recorte">
        {recorte}
      </p>

      {/* A comparacao: UM par de numeros, sobre AS MESMAS maos. Abaixo do piso, nenhum dos dois. */}
      <div className="mb-3 flex flex-wrap items-baseline gap-x-5 gap-y-1 rounded-lg border border-border/60 bg-card/40 px-3 py-2" data-testid="matriz-comparacao">
        {dados.voce_pct == null ? (
          <p className="font-mono text-[10px] leading-snug text-muted-foreground" data-testid="matriz-amostra">
            {t("posProfile.matrix.smallSample", { n: dados.amostra_minima ?? 30 })}
          </p>
        ) : (
          <>
            <span className="flex items-baseline gap-2">
              <span className={ROTULO_GRUPO}>{t("posProfile.matrix.youOpened")}</span>
              <span className="font-heading text-lg font-bold text-foreground" data-testid="matriz-voce-pct">{dados.voce_pct.toFixed(1)}%</span>
            </span>
            {dados.solver_pct == null ? (
              <span className="font-mono text-[10px] text-muted-foreground">{t("posProfile.matrix.noChartCompare")}</span>
            ) : (
              <>
                <span className="flex items-baseline gap-2">
                  <span className={ROTULO_GRUPO}>{t("posProfile.matrix.solverWouldOpen")}</span>
                  <span className="font-heading text-lg font-bold text-primary" data-testid="matriz-solver-pct">{dados.solver_pct.toFixed(1)}%</span>
                </span>
                <span className={cn("rounded-md border px-2 py-0.5 font-mono text-[10px]", deltaClasse)} data-testid="matriz-delta">{deltaTexto}</span>
                <p className="basis-full font-mono text-[9px] leading-snug text-muted-foreground/70">
                  {dados.cobertura < 100
                    ? t("posProfile.matrix.sameHandsCovered", { n: dados.n.toLocaleString(), pct: dados.cobertura })
                    : t("posProfile.matrix.sameHands", { n: dados.n.toLocaleString() })}
                </p>
              </>
            )}
          </>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-[1fr_1fr_17rem]">
        <div data-testid="matriz-voce">
          <div className="mb-1.5 flex items-baseline justify-between gap-2">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("posProfile.matrix.yourHands")}</span>
          </div>
          <RangeGrid range={voce} compacta semDado={nuncaRecebidas} rotuloSemDado={t("posProfile.matrix.neverDealt")} />
        </div>

        <div data-testid="matriz-solver">
          <div className="mb-1.5 flex items-baseline justify-between gap-2">
            <span className="truncate whitespace-nowrap font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("posProfile.matrix.solverRange")}</span>
            {/* o tamanho do DESENHO, nao um numero comparavel com o do jogador: legenda, nao cabecalho */}
            <span className="whitespace-nowrap font-mono text-[9px] text-muted-foreground/70" data-testid="matriz-range-size">
              {dados.solver_pct_todas == null ? t("posProfile.matrix.noChart") : t("posProfile.matrix.rangeSize", { pct: dados.solver_pct_todas.toFixed(1) })}
            </span>
          </div>
          <RangeGrid range={solver} compacta />
          {dados.solver_pct_todas != null && (
            <p className="mt-1.5 font-mono text-[9px] leading-snug text-muted-foreground/70" data-testid="matriz-referencia">
              {(() => {
                if (dados.jogadores_atras != null) return t("posProfile.matrix.behindOne", { count: dados.jogadores_atras });
                // `Math.min()` de lista vazia e Infinity, e a tela mostrava "de Infinity a
                // -Infinity". Sem composicao nao ha o que declarar: cala em vez de inventar.
                const atras = (dados.composicao_da_carta ?? []).map((x) => x.atras).filter((x): x is number => x != null);
                if (!atras.length) return t("posProfile.matrix.behindUnknown");
                return t("posProfile.matrix.behindRange", {
                  min: Math.min(...atras), max: Math.max(...atras),
                  pct: dados.composicao_da_carta?.[0]?.pct ?? 0,
                  top: dados.composicao_da_carta?.[0]?.atras ?? 0,
                });
              })()}
            </p>
          )}
          {/* A MISTURA de profundidades, declarada. Com "Todas" em vigor a referencia e media
              entre cartas de 10bb, 30bb e 100bb; calar sobre isso seria o mesmo defeito que o
              filtro obrigatorio evitava, so que silencioso. Uma carta so: nada a dizer. */}
          {(dados.profundidades_da_carta?.length ?? 0) > 1 && (
            <p className="mt-1 font-mono text-[9px] leading-snug text-amber-400/80" data-testid="matriz-mistura-de-profundidade">
              {t("posProfile.matrix.depthMix", {
                lista: (dados.profundidades_da_carta ?? [])
                  .map((x) => `${x.profundidade} ${x.pct}%`).join(", "),
              })}
            </p>
          )}
        </div>

        <div className="min-w-0 overflow-x-hidden rounded-lg border border-border/50 bg-card/40 p-3">
          <div className="mb-1.5 font-mono text-[9px] uppercase tracking-widest text-primary">
            {t("posProfile.matrix.divergences")}
          </div>
          {dados.divergencias.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">{t("posProfile.matrix.noDivergence", { n: dados.minimo_maos, pp: Math.round(dados.divergencia_minima * 100) })}</p>
          ) : (
            // rola so na vertical: as colunas somam menos que a caixa (dono, 08/09: "rolagem horizontal e inaceitavel")
            <div className="max-h-[19rem] overflow-y-auto overflow-x-hidden">
              <div className="grid items-center gap-x-1.5" style={{ gridTemplateColumns: "2.2rem 1.8rem 2.5rem 2.6rem 3.4rem" }} data-testid="matriz-divergencias">
                <span className={CABECALHO}>{t("posProfile.matrix.hand")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.matrix.times")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.you")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.matrix.solverShort")}</span>
                <span className={`${CABECALHO} text-right`}>{t("posProfile.matrix.diff")}</span>
                {dados.divergencias.map((d) => (
                  <div key={d.hand} className="contents" data-testid={`divergencia-${d.hand}`}>
                    <span className={`${CELULA} font-mono text-[11px] font-bold text-foreground`}>{d.hand}</span>
                    <span className={`${CELULA} font-mono text-[10px] tabular-nums text-muted-foreground text-right`}>{d.n}</span>
                    <span className={`${CELULA} font-mono text-[11px] tabular-nums text-foreground text-right`}>{pct(d.voce)}</span>
                    <span className={`${CELULA} font-mono text-[11px] tabular-nums text-foreground text-right`}>{pct(d.solver)}</span>
                    <span className={`${CELULA} whitespace-nowrap font-mono text-[11px] font-bold tabular-nums text-right text-red-400`}>
                      {d.delta > 0 ? "+" : ""}{Math.round(d.delta * 100)} pp
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <p className="mt-2 font-mono text-[9px] leading-snug text-muted-foreground/60">
            {t("posProfile.matrix.divergencesNote", { n: dados.minimo_maos, pp: Math.round(dados.divergencia_minima * 100) })}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end gap-3">
        <Link to="/ranges" className="shrink-0 rounded-md border border-primary/40 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/10">
          {t("posProfile.matrix.study")}
        </Link>
      </div>
    </div>
  );
}
