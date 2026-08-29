/**
 * /ranges — consulta livre da carta de preflop.
 *
 * ── Por que esta página existe (27/08) ────────────────────────────────────────────────────
 *
 * A carta tem 14 profundidades (3, 4, 5, 6, 7, 10, 14, 17, 20, 30, 40, 50, 75 e 100bb) e até
 * hoje existiam ZERO formas de olhar qualquer spot: a matriz 13×13 só abria presa a um passo —
 * dentro do replayer, de um drill ou de uma aula. Para saber "como se abre do CO com 25bb?" era
 * preciso antes achar uma mão do próprio histórico em que isso aconteceu.
 *
 * ── O que esta tela AINDA não cobre, e por quê ────────────────────────────────────────────
 *
 * Quatro cenários, não seis. `vs_4bet` e `faces_squeeze` existem na carta e o endpoint
 * `/preflop-ranges` **não os serve** — a resposta tem `rfi`, `vs_rfi`, `vs_3bet` e `squeeze`.
 * Oferecer a pílula sem o dado entregaria tela vazia; prometer "todos os cenários" no texto seria
 * pior. A tela declara os quatro que tem, e a lacuna fica registrada aqui.
 *
 * A página não constrói motor nenhum: ela liga os seletores ao que já existe. `RangeGrid` pinta,
 * `buildRangeFromApi` monta o RangeSet (a MESMA função do replayer) e `resumoDoSpot` conta as
 * categorias. Nada aqui é uma segunda fonte.
 *
 * ── O que ela deliberadamente NÃO mostra ──────────────────────────────────────────────────
 *
 * EV por ação. A proposta original prometia isso, e a conferência derrubou: `hand_freqs` só tem
 * frequência e uma busca por qualquer chave de EV no JSON da carta devolve nenhuma. O EV que o
 * produto tem é por DECISÃO, vindo do solver, não por mão da carta. Prometer o número na tela
 * exigiria inventá-lo.
 */
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { HudHeader } from "@/components/hud/HudHeader";
import { RangeGrid } from "@/components/replayer/RangeGrid";
import { buildRangeFromApi, type PreflopRangesResp } from "@/components/replayer/RangePanel";
import { getPreflopRanges } from "@/lib/api";
import { resumoDoSpot, ROTULO_ACAO, type RangeSet, type RangeType, type AcaoDaCelula } from "@/data/ranges";
import { ACTION_COLORS } from "@/lib/actionColors";
import { cn } from "@/lib/utils";
import { JanelaFlutuante, suportaJanelaFlutuante } from "@/components/ranges/JanelaFlutuante";
import { ConsultaCompacta } from "@/components/ranges/ConsultaCompacta";

// As 14 profundidades que a carta REALMENTE tem. Lista fixa de propósito: um seletor que oferece
// profundidade sem carta manda o jogador para uma tela vazia sem dizer por quê.
const STACKS = [3, 4, 5, 6, 7, 10, 14, 17, 20, 30, 40, 50, 75, 100];

// A ponta rasa (3 a 7bb) só tem seção RFI — ver `_BALDES_RASOS` no backend. O seletor precisa
// saber disso para não oferecer "vs Abertura" a 4bb e entregar vazio.
const STACK_RASO_MAX = 7;

const POSICOES = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

interface Cenario {
  id: string;
  tipo: RangeType;
  scenario?: string;
  /** precisa de um vilão (o abridor ou o 3-bettor) */
  contra?: "abridor" | "3bettor";
  /** posições em que o herói pode estar neste cenário */
  posicoes: string[];
  /** existe na faixa rasa? */
  raso: boolean;
}

const CENARIOS: Cenario[] = [
  { id: "rfi", tipo: "open", posicoes: POSICOES.slice(0, 8), raso: true },
  { id: "vs_rfi", tipo: "call", contra: "abridor",
    posicoes: POSICOES.slice(1), raso: false },
  { id: "vs_3bet", tipo: "3bet", contra: "3bettor",
    posicoes: POSICOES.slice(0, 8), raso: false },
  { id: "squeeze", tipo: "3bet", scenario: "squeeze", contra: "abridor",
    posicoes: POSICOES.slice(1), raso: false },
];

/**
 * Gradiente do chip da categoria.
 *
 * A 1ª versão deste comentário dizia "usa o MESMO gradiente da célula", e era falso em duas
 * coisas. A ORDEM eu consertei: agora segue a mesma de `buildGradient` (raise, call, allin,
 * fold). A PROPORÇÃO não tem conserto e não deveria: a categoria "Raise ou Fold" agrupa mãos que
 * sobem 15% e mãos que sobem 60%, então fatia igual é a representação honesta de um conjunto.
 * O chip diz QUAIS ações, a célula diz QUANTO.
 */
const ORDEM_PINTURA: AcaoDaCelula[] = ['raise', 'call', 'allin', 'fold'];

function gradienteDa(acoesFora: AcaoDaCelula[]): string {
  const acoes = ORDEM_PINTURA.filter((a) => acoesFora.includes(a));
  const cor: Record<AcaoDaCelula, string> = {
    raise: ACTION_COLORS.raise,
    call: ACTION_COLORS.call,
    allin: ACTION_COLORS.allin,
    fold: ACTION_COLORS.fold,
  };
  if (acoes.length === 1) return cor[acoes[0]];
  const fatia = 100 / acoes.length;
  return `linear-gradient(to right, ${acoes
    .map((a, i) => `${cor[a]} ${i * fatia}% ${(i + 1) * fatia}%`)
    .join(", ")})`;
}

function Pilula({ ativo, onClick, children, desabilitado, titulo }: {
  ativo: boolean; onClick: () => void; children: React.ReactNode;
  desabilitado?: boolean; titulo?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={desabilitado}
      title={titulo}
      className={cn(
        "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
        // A convencao do projeto (ui/button.tsx) e `focus-visible:ring-2`; esta tela nasceu sem.
        // Sem isso, navegar por Tab entre 31 pilulas nao move nada visivel na tela.
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
        desabilitado
          ? "cursor-not-allowed border-border/60 text-muted-foreground/40"
          : ativo
            ? "border-primary/45 bg-primary/[0.13] text-primary"
            : "border-border text-muted-foreground hover:border-border/80 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function Linha({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-1.5">{children}</div>;
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <span className="min-w-[76px] font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-hud-muted">
      {children}
    </span>
  );
}

export default function Ranges() {
  const { t } = useTranslation("study");
  const [cenarioId, setCenarioId] = useState("rfi");
  const [stack, setStack] = useState(20);
  const [posicao, setPosicao] = useState("CO");
  const [contra, setContra] = useState<string | null>(null);
  const [resp, setResp] = useState<PreflopRangesResp | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const cenario = CENARIOS.find((c) => c.id === cenarioId) ?? CENARIOS[0];
  const rasoDemais = stack <= STACK_RASO_MAX && !cenario.raso;

  // A posicao efetiva e DERIVADA, nao corrigida por efeito. Com `useEffect` a correcao roda
  // depois do paint, entao trocar de cenario pintava um frame inteiro dizendo "nao temos carta
  // para vs abertura de UTG" — uma ausencia com a causa ERRADA — antes de cair em UTG+1.
  const posicaoValida = cenario.posicoes.includes(posicao) ? posicao : cenario.posicoes[0];
  useEffect(() => {
    if (posicao !== posicaoValida) setPosicao(posicaoValida);
  }, [posicao, posicaoValida]);

  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    setErro(null);
    // `setResp(null)` nao e zelo: sem ele o painel da direita seguia exibindo as categorias do
    // spot ANTERIOR enquanto o novo carregava, e PERMANENTEMENTE se o fetch falhasse. A coluna
    // da esquerda declarava o estado e a da direita mentia calada, com cara de resposta.
    setResp(null);
    getPreflopRanges(posicaoValida, stack)
      .then((d) => { if (vivo) setResp(d); })
      .catch((e) => { if (vivo) setErro(e?.message ?? t("ranges.erroCarregar")); })
      .finally(() => { if (vivo) setCarregando(false); });
    return () => { vivo = false; };
  }, [posicaoValida, stack, t]);

  /** Os vilões que o cenário oferece de fato, lidos da resposta — nunca uma lista inventada. */
  const viloes = useMemo(() => {
    if (!resp || !cenario.contra) return [];
    const fonte = cenario.id === "vs_rfi" ? resp.vs_rfi
      : cenario.id === "squeeze" ? resp.squeeze
      : resp.vs_3bet;
    return Object.keys(fonte ?? {}).map((k) => k.replace("_open", "")).sort();
  }, [resp, cenario]);

  const vilaoAtivo = contra && viloes.includes(contra) ? contra : viloes[0] ?? null;

  const range: RangeSet | null = useMemo(() => {
    if (!resp) return null;
    const chave = cenario.id === "vs_rfi" && vilaoAtivo
      ? (resp.vs_rfi?.[vilaoAtivo] ? vilaoAtivo : `${vilaoAtivo}_open`)
      : vilaoAtivo ?? undefined;
    return buildRangeFromApi(resp, cenario.tipo, chave, cenario.scenario);
  }, [resp, cenario, vilaoAtivo]);

  const categorias = useMemo(() => (range ? resumoDoSpot(range) : []), [range]);

  // De qual balde a secao exibida veio de fato. `rfi` e `vs_rfi` nunca caem em vizinho; so
  // `vs_3bet` e `squeeze` tem fallback, entao o aviso so pode aparecer neles.
  const substituida = resp?.substituicao?.[
    cenario.id === "squeeze" ? "squeeze" : cenario.id === "vs_3bet" ? "vs_3bet" : "__nenhum"
  ] ?? null;

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <HudHeader />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-heading text-2xl font-bold tracking-tight">{t("ranges.title")}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{t("ranges.subtitle")}</p>
          </div>
          {/* A janela flutuante e a UNICA parte deste produto que serve DURANTE a mao: tudo o mais
              e pos-sessao. Ela so aparece onde a API existe (Chrome); oferecer e falhar faria o
              jogador concluir que o produto esta quebrado. Ver `JanelaFlutuante`. */}
          {suportaJanelaFlutuante() && (
            <JanelaFlutuante
              rotulo={t("ranges.flutuante")}
              largura={380}
              altura={470}
              className="shrink-0 rounded-lg border border-primary/40 bg-primary/[0.07] px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-primary transition-colors hover:bg-primary/15"
            >
              <ConsultaCompacta
                range={range}
                carregando={carregando}
                cenarios={CENARIOS.map((c) => ({
                  id: c.id, rotulo: t(`ranges.cen.${c.id}`), posicoes: c.posicoes, raso: c.raso,
                }))}
                stacks={STACKS}
                stackRasoMax={STACK_RASO_MAX}
                cenarioId={cenarioId} setCenarioId={setCenarioId}
                stack={stack} setStack={setStack}
                posicao={posicao} setPosicao={setPosicao}
              />
            </JanelaFlutuante>
          )}
        </div>

        <div className="mt-5 flex flex-col gap-2.5 rounded-xl border border-border bg-hud-surface/40 p-3.5">
          <Linha>
            <Rotulo>{t("ranges.cenario")}</Rotulo>
            {CENARIOS.map((c) => (
              <Pilula key={c.id} ativo={c.id === cenarioId} onClick={() => setCenarioId(c.id)}>
                {t(`ranges.cen.${c.id}`)}
              </Pilula>
            ))}
          </Linha>
          <Linha>
            <Rotulo>{t("ranges.stack")}</Rotulo>
            {STACKS.map((s) => (
              <Pilula
                key={s}
                ativo={s === stack}
                onClick={() => setStack(s)}
                titulo={s <= STACK_RASO_MAX ? t("ranges.dicaRaso") : undefined}
              >
                {/* Largura estavel: antes a selecionada virava "7bb" e empurrava as
                    seguintes, reorganizando a fila debaixo do dedo no celular. */}
                <span className="font-mono tabular-nums">{s}</span>
              </Pilula>
            ))}
          </Linha>
          <Linha>
            <Rotulo>{t("ranges.posicao")}</Rotulo>
            {POSICOES.map((p) => (
              <Pilula
                key={p}
                ativo={p === posicaoValida}
                desabilitado={!cenario.posicoes.includes(p)}
                onClick={() => setPosicao(p)}
              >
                {p}
              </Pilula>
            ))}
            {cenario.posicoes.length < POSICOES.length && (
              // A causa vira TEXTO, nao tooltip de botao desabilitado: `title` em `disabled` nao
              // e focavel por teclado, nao abre no Firefox e nao existe em toque. No celular a
              // posicao apagada era so um rotulo sem motivo.
              <span className="w-full text-[11px] text-hud-muted">
                {t("ranges.posicoesForaDoCenario")}
              </span>
            )}
          </Linha>
          {cenario.contra && (
            <Linha>
              <Rotulo>{t(cenario.contra === "abridor" ? "ranges.contra" : "ranges.tresBetDe")}</Rotulo>
              {viloes.length === 0 && (
                <span className="text-xs text-muted-foreground">
                  {carregando ? "…" : t("ranges.semVilao")}
                </span>
              )}
              {viloes.map((v) => (
                <Pilula key={v} ativo={v === vilaoAtivo} onClick={() => setContra(v)}>
                  {v}
                </Pilula>
              ))}
            </Linha>
          )}
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <div className="rounded-xl border border-border bg-hud-surface/40 p-3.5">
            {carregando && (
              <p className="py-16 text-center text-sm text-muted-foreground">{t("ranges.carregando")}</p>
            )}
            {!carregando && erro && (
              <p className="py-16 text-center text-sm text-destructive">{erro}</p>
            )}
            {!carregando && !erro && !range && (
              // Ausência que DECLARA o motivo — a mesma regra do backend. Uma grade vazia sem
              // explicação faz o jogador achar que a range é fold 100%.
              <p className="py-16 text-center text-sm text-muted-foreground">
                {rasoDemais
                  ? t("ranges.rasoDemais", { stack })
                  : t("ranges.semCarta", {
                      cenario: t(`ranges.cen.${cenario.id}`).toLowerCase(), posicao, stack })}
              </p>
            )}
            {!carregando && !erro && range && (
              <>
                {substituida && (
                  // A carta veio de OUTRA profundidade. Dizer isso e o minimo: sem o aviso, a
                  // mesma grade aparece sob dois rotulos de stack diferentes, e o jogador conclui
                  // que a range nao muda entre 14 e 17bb.
                  <p className="mb-2 rounded-md border border-warning/30 bg-warning/[0.06] px-3 py-2 text-[11px] leading-relaxed text-warning">
                    {t("ranges.substituicao", { balde: substituida })}
                  </p>
                )}
                <div className="mb-2 flex items-baseline justify-between gap-3">
                  <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
                    {range.label}
                  </h2>
                </div>
                <RangeGrid range={range} />
              </>
            )}
          </div>

          <div className="rounded-xl border border-border bg-hud-surface/40 p-3.5">
            <h2 className="mb-2.5 flex items-baseline justify-between font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
              <span>{t("ranges.resumoTitulo")}</span>
              <span className="tracking-normal text-hud-muted">{t("ranges.resumoCombos")}</span>
            </h2>
            {categorias.length === 0 && (
              <p className="text-xs text-muted-foreground">{t("ranges.resumoVazio")}</p>
            )}
            <ul className="space-y-0">
              {categorias.map((c) => (
                <li
                  key={c.chave}
                  className="flex items-center gap-2 border-b border-border/60 py-1.5 text-sm last:border-b-0"
                >
                  <span
                    className="block size-2.5 flex-none rounded-[2px]"
                    style={{ background: gradienteDa(c.acoes) }}
                  />
                  <span className="flex-1 text-foreground">
                    {c.acoes.map((a) => ROTULO_ACAO[a]).join(t("ranges.ou"))}
                  </span>
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    <b className="font-medium text-foreground">{c.combos}</b> {t("ranges.combos")} · {c.pct}%
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[11px] leading-relaxed text-hud-muted">
              {t("ranges.resumoNota")}
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
