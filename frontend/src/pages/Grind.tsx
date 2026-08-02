import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, Flame, Home, RotateCw, Trophy } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { grind, type GrindMao, type GrindPasso, type LeakTrainerGrade } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ReplayStep } from "@/lib/api";

const ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

/**
 * MODO GRIND — a mão real inteira, decisão por decisão.
 *
 * É REPLAY, não simulação, e a tela diz isso. O GTO Wizard reparte cartas novas porque tem a
 * árvore inteira pré-computada; aqui só existe nó onde alguém mandou solvar. O jogador percorre uma
 * mão que ACONTECEU, contra o que o vilão de fato fez — a linha do vilão é humana, não um robô
 * jogando GTO. Vender isso como simulação seria mentir, e o aviso no rodapé existe por isso.
 *
 * As mãos vêm do acervo de TODOS os jogadores. O que chega aqui já vem anonimizado do servidor:
 * posição e stack em BB, e nada mais. Esta tela não tem como vazar identificador porque ele nunca
 * chega — e é assim de propósito.
 */

/** Profundidade e pote para LEITURA: o acervo guarda float cru e ele chegava assim na tela. */
const bb = (v: number | null | undefined): string =>
  v == null ? "?" : (Math.round(v * 10) / 10).toString();

/** Passo → mesa. Mesmo formato que o Leak Trainer usa, com as MESMAS travas:
 *  `??` e não `||` (0 bb enfrentados é valor válido, não ausência de valor), e nada é desenhado
 *  quando a posição não está no vocabulário de 9 assentos. */
function montarMesa(p: GrindPasso) {
  const bbChips = 100;
  const heroIdx = ORDER.indexOf(p.position);
  const vsIdx = ORDER.indexOf(p.vs_position);
  const stackChips = Math.round((p.stack_bb ?? 40) * bbChips);
  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets: Record<string, number> = {};
  const folded: string[] = [];
  ORDER.forEach((pos, i) => {
    const isHero = pos === p.position;
    seats[String(i + 1)] = { player: isHero ? "Hero" : pos, stack: stackChips, pos };
    if (!isHero && pos !== p.vs_position) folded.push(pos);
  });
  const facing = p.facing_size_bb ?? 0;
  if (vsIdx >= 0 && facing > 0) bets[String(vsIdx + 1)] = Math.round(facing * bbChips);
  const potChips = Math.round((p.pot_bb ?? 0) * bbChips);
  const step = {
    type: "action", street: p.street, seats, bets, folded,
    pot_bb: potChips / bbChips, pot: potChips, bb: bbChips,
    button: ORDER.indexOf("BTN") + 1, board: p.board || [],
    player: "Hero", seat: heroIdx + 1, is_hero: true,
  } as unknown as ReplayStep;
  return { step, heroCards: p.hero_hand };
}

type Resultado = { acao: string; tier: string; correto: boolean; semVeredito: boolean };

export default function Grind() {
  const { t } = useTranslation("training");
  const [mao, setMao] = useState<GrindMao | null>(null);
  const [i, setI] = useState(0);
  const [vistas, setVistas] = useState<string[]>([]);
  const [resultados, setResultados] = useState<Resultado[]>([]);
  const [ultimo, setUltimo] = useState<LeakTrainerGrade | null>(null);
  const [fase, setFase] = useState<"carregando" | "decidindo" | "feedback" | "fim" | "vazio">("carregando");
  const [enviando, setEnviando] = useState(false);

  const passo = mao?.passos[i] ?? null;

  const buscar = useCallback(async (jaVistas: string[]) => {
    setFase("carregando");
    setUltimo(null);
    try {
      const r = await grind.hand(jaVistas);
      if (!r.mao) { setFase("vazio"); return; }
      setMao(r.mao);
      setI(0);
      setFase("decidindo");
    } catch {
      setFase("vazio");
    }
  }, []);

  useEffect(() => { void buscar([]); }, [buscar]);

  async function responder(acao: string) {
    if (!passo || enviando) return;
    setEnviando(true);
    try {
      const r = await grind.grade(passo, acao);
      // Sem veredito possível NÃO vira "errou": não pontua e diz que não pontuou. Inventar um
      // veredito aqui seria o defeito que o Ghost Table levou o dia inteiro para tirar.
      setUltimo(r.resultado);
      setResultados((v) => [...v, {
        acao,
        tier: r.resultado?.gto_tier ?? "—",
        correto: Boolean(r.resultado?.is_correct),
        semVeredito: r.sem_veredito,
      }]);
      setFase("feedback");
    } finally {
      setEnviando(false);
    }
  }

  function avancar() {
    if (!mao) return;
    if (i + 1 >= mao.passos.length) { setFase("fim"); return; }
    setI(i + 1);
    setUltimo(null);
    setFase("decidindo");
  }

  function proximaMao() {
    const novas = mao ? [...vistas, mao.token] : vistas;
    setVistas(novas);
    setResultados([]);
    void buscar(novas);
  }

  const acertos = resultados.filter((r) => r.correto).length;
  const contados = resultados.filter((r) => !r.semVeredito).length;
  const mesa = useMemo(() => (passo ? montarMesa(passo) : null), [passo]);

  return (
    <HudLayout eyebrow={t("grind.eyebrow")} title={t("grind.title")} description={t("grind.subtitle")}>
      <div className="mx-auto w-full max-w-5xl space-y-4">

        {fase === "vazio" && (
          <div className="rounded-2xl border border-border bg-card/40 p-6 text-center">
            <p className="text-sm text-foreground">{t("grind.empty.title")}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t("grind.empty.desc")}</p>
            <Link to="/training"
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground">
              <Home className="size-4" aria-hidden /> {t("grind.empty.back")}
            </Link>
          </div>
        )}

        {fase === "carregando" && (
          <div className="space-y-3" aria-busy="true">
            <div className="h-72 animate-pulse rounded-2xl bg-muted/25" />
            <div className="h-12 animate-pulse rounded-xl bg-muted/20" />
          </div>
        )}

        {mao && passo && (fase === "decidindo" || fase === "feedback") && (
          <>
            {/* linha da mão: onde estamos dentro dela */}
            <div className="flex flex-wrap items-center gap-1.5">
              {mao.passos.map((p, idx) => (
                <span key={idx}
                  className={cn("rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-wider",
                    idx < i ? "bg-primary/15 text-primary"
                      : idx === i ? "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40"
                        : "bg-muted/20 text-muted-foreground")}>
                  {t(`grind.street.${p.street}`, p.street)}
                </span>
              ))}
              <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {t("grind.step", { atual: i + 1, total: mao.passos.length })}
              </span>
            </div>

            {/* o que o vilão fez antes deste passo — sem isso o pote cresce sozinho na tela */}
            {passo.vilao_antes && (
              <p className="text-center font-mono text-xs text-amber-300">
                {passo.vilao_antes.tipo === "aposta"
                  ? t("grind.villainBet", { pos: passo.vs_position, bb: bb(passo.vilao_antes.bb) })
                  : t("grind.villainCheck", { pos: passo.vs_position })}
              </p>
            )}

            {mesa && (
              <div className="mx-auto aspect-[16/10] w-full max-w-3xl">
                <PokerTableV3 step={mesa.step} hero="Hero" heroCards={mesa.heroCards}
                  bb={100} betUnit="bb" transparentBg />
              </div>
            )}

            <div className="flex flex-wrap items-center justify-center gap-3 font-mono text-[11px] text-muted-foreground">
              <span>{passo.position} vs {passo.vs_position}</span>
              <span>{bb(passo.stack_bb)}bb</span>
              <span>{t("grind.pot")} {bb(passo.pot_bb)}bb</span>
              {passo.facing_size_bb > 0 && <span>{t("grind.facing")} {bb(passo.facing_size_bb)}bb</span>}
            </div>

            {fase === "decidindo" && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {passo.options.map((a) => (
                  <button key={a} type="button" disabled={enviando} onClick={() => void responder(a)}
                    className="rounded-xl border border-border bg-background/60 px-4 py-3 font-mono text-sm font-bold uppercase tracking-wider text-foreground transition-colors hover:border-primary/50 hover:text-primary disabled:opacity-40">
                    {t(`grind.act.${a}`, a)}
                  </button>
                ))}
              </div>
            )}

            {fase === "feedback" && (
              <div className={cn("space-y-2 rounded-2xl p-4 ring-1",
                resultados[resultados.length - 1]?.semVeredito ? "bg-muted/20 ring-border"
                  : resultados[resultados.length - 1]?.correto ? "bg-emerald-500/10 ring-emerald-500/30"
                    : "bg-amber-500/10 ring-amber-500/30")}>
                {resultados[resultados.length - 1]?.semVeredito ? (
                  /* Nunca vira "errou": sem gabarito não há veredito, e dizer isso é o honesto. */
                  <p className="text-sm text-muted-foreground">{t("grind.noVerdict")}</p>
                ) : (
                  <>
                    <p className="font-heading text-base font-bold text-foreground">
                      {resultados[resultados.length - 1]?.correto ? t("grind.right") : t("grind.wrong")}
                    </p>
                    {ultimo?.gto_strategy?.length ? (
                      <div className="space-y-1">
                        {ultimo.gto_strategy.map((d) => (
                          <div key={d.action} className="flex items-center gap-2">
                            <span className="w-14 shrink-0 font-mono text-[10px] uppercase text-muted-foreground">
                              {t(`grind.act.${d.action}`, d.action)}
                            </span>
                            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                              <div className="h-full rounded-full bg-primary"
                                style={{ width: `${Math.round(d.freq * 100)}%` }} />
                            </div>
                            <span className="w-10 shrink-0 text-right font-mono text-[10px] tabular-nums text-muted-foreground">
                              {Math.round(d.freq * 100)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                )}
                <button type="button" onClick={avancar}
                  className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground">
                  {i + 1 >= mao.passos.length ? t("grind.finishHand") : t("grind.next")}
                  <ArrowRight className="size-4" aria-hidden />
                </button>
              </div>
            )}
          </>
        )}

        {fase === "fim" && (
          <div className="mx-auto w-full max-w-md rounded-3xl border border-primary/30 bg-card p-6 text-center">
            <Trophy className="mx-auto size-10 text-primary" aria-hidden />
            <h2 className="mt-2 font-heading text-xl font-bold text-foreground">{t("grind.handDone")}</h2>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="rounded-2xl bg-background/60 px-2 py-3 ring-1 ring-border">
                <p className="font-mono text-2xl font-bold tabular-nums text-foreground">
                  {acertos}/{contados}
                </p>
                <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                  {t("grind.hits")}
                </p>
              </div>
              <div className="rounded-2xl bg-background/60 px-2 py-3 ring-1 ring-border">
                <p className="font-mono text-2xl font-bold tabular-nums text-primary">
                  {vistas.length + 1}
                </p>
                <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                  {t("grind.hands")}
                </p>
              </div>
            </div>
            {/* `contados` e não `resultados.length`: passo sem gabarito não entra no denominador,
                senão a nota pune o jogador por uma lacuna nossa. */}
            {contados < resultados.length && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                {t("grind.skipped", { n: resultados.length - contados })}
              </p>
            )}
            <button type="button" onClick={proximaMao}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 font-mono text-xs font-bold uppercase tracking-widest text-primary-foreground">
              <RotateCw className="size-4" aria-hidden /> {t("grind.nextHand")}
            </button>
            <Link to="/training"
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-widest text-muted-foreground">
              <Home className="size-4" aria-hidden /> {t("grind.finish")}
            </Link>
          </div>
        )}

        {/* É REPLAY, não simulação. O jogador não muda o rumo da mão: ele responde o que o GTO
            faria, e a mão segue o caminho que seguiu de verdade. Omitir isso seria vender
            simulação. */}
        <p className="pt-2 text-center text-[11px] leading-snug text-muted-foreground">
          <Flame className="mr-1 inline size-3 text-amber-400" aria-hidden />
          {t("grind.disclaimer")}
        </p>
      </div>
    </HudLayout>
  );
}
