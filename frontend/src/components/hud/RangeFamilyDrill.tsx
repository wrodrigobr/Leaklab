import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Check, X } from "lucide-react";
import { leaktrainer, type LeakTrainerSpot, type RangeGridGrade } from "@/lib/api";
import { cellHand, cellLabel, combosDeMaos } from "@/data/ranges";
import { PositionMap } from "@/components/hud/PositionMap";
import { cn } from "@/lib/utils";

/**
 * Treino de FRONTEIRA: marcar quais mãos de uma família entram no open da posição.
 *
 * ── Por que uma família por vez, e não a grade inteira ────────────────────────────────────────
 *
 * Marcar 169 células é inviável na prática e, pior, dilui: umas 130 delas são fold óbvio em
 * qualquer posição. Uma família tem 12 ou 13 casas e a resposta É a fronteira — "o UTG abre Ás
 * suited até onde?" —, que é justamente o fato âncora que dá para memorizar. Reconhecer uma mão
 * servida é fácil; reconstruir onde a linha para é o que se leva para a mesa.
 *
 * ── O contador ao vivo ────────────────────────────────────────────────────────────────────────
 *
 * O percentual é sobre as 1326 combinações do baralho, e não sobre a família. É o que amarra este
 * exercício à noção de largura: o jogador aprende que "todos os Áses suited" são só 3,6% do
 * baralho, e entende por que uma range de 20% precisa de várias famílias. Percentual da família
 * diria "marquei metade dos Áses suited", que não se conecta a nada que ele use jogando.
 *
 * ── A correção não é porcentagem de acerto ────────────────────────────────────────────────────
 *
 * Numa família em que a posição abre 5 de 12, não marcar nada "acerta" 58% das células. Um placar
 * assim premiaria não responder. O servidor devolve o que FALTOU e o que SOBROU, que é o formato
 * em que o erro se corrige — e nomeia a fronteira, que é o que fica.
 */
export function RangeFamilyDrill({ spot, onDone, rodape }: {
  spot: LeakTrainerSpot;
  onDone: (acertou: boolean, xp: number) => void;
  /** Ação de avançar, renderizada abaixo do resultado (o botão de próximo exercício). */
  rodape?: ReactNode;
}) {
  const { t } = useTranslation("academy");
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [grade, setGrade] = useState<RangeGridGrade | null>(null);
  const [enviando, setEnviando] = useState(false);

  const hands = spot.hands ?? [];
  const { combos, pct } = combosDeMaos([...marcadas]);
  const totalFamilia = combosDeMaos(hands);

  const familia = useMemo(() => new Set(hands), [hands]);

  const alterna = (h: string) => {
    if (grade || !familia.has(h)) return;
    setMarcadas((s) => {
      const n = new Set(s);
      if (n.has(h)) n.delete(h); else n.add(h);
      return n;
    });
  };

  // ── Marcação por ARRASTO ──────────────────────────────────────────────────────────────────────
  //
  // Uma família tem 12 ou 13 casas em fileira. Clicar uma a uma transforma um exercício de
  // memória num exercício de mira: o jogador passa mais tempo acertando o alvo do que pensando
  // até onde vai a range, e desiste de corrigir a marcação porque refazer custa 13 cliques.
  //
  // O modo é decidido no PRIMEIRO toque e vale para o arrasto inteiro: se ele começou numa
  // célula vazia, o arrasto marca; se começou numa marcada, desmarca. Sem isso o dedo passando
  // sobre a própria marcação a apagaria de volta, e a fileira ficaria piscando.
  const arrasto = useRef<"marcar" | "desmarcar" | null>(null);

  const aplica = (h: string) => {
    const modo = arrasto.current;
    if (!modo || grade || !familia.has(h)) return;
    setMarcadas((s) => {
      // Idempotente de propósito: o ponteiro reentra na mesma célula dezenas de vezes durante um
      // arrasto, e um toggle aqui a faria oscilar.
      if (modo === "marcar" ? s.has(h) : !s.has(h)) return s;
      const n = new Set(s);
      if (modo === "marcar") n.add(h); else n.delete(h);
      return n;
    });
  };

  const inicia = (h: string) => {
    if (grade || !familia.has(h)) return;
    arrasto.current = marcadas.has(h) ? "desmarcar" : "marcar";
    aplica(h);
  };

  // O fim do arrasto é ouvido na JANELA, e não na grade: soltar o botão fora dela é comum
  // (a fileira acaba na borda) e deixaria o arrasto preso, marcando ao simples passar do mouse.
  useEffect(() => {
    const fim = () => { arrasto.current = null; };
    window.addEventListener("pointerup", fim);
    window.addEventListener("pointercancel", fim);
    return () => {
      window.removeEventListener("pointerup", fim);
      window.removeEventListener("pointercancel", fim);
    };
  }, []);

  // No touch o ponteiro fica CAPTURADO pelo elemento do primeiro toque, então `pointerenter` não
  // dispara nas células vizinhas. Descobrir a célula pela coordenada funciona nos dois casos.
  const arrastaSobre = (x: number, y: number) => {
    if (!arrasto.current) return;
    const alvo = (document.elementFromPoint(x, y) as HTMLElement | null)?.closest<HTMLElement>("[data-mao]");
    if (alvo?.dataset.mao) aplica(alvo.dataset.mao);
  };

  const corrigir = async () => {
    setEnviando(true);
    try {
      const g = await leaktrainer.gradeGrid(spot, [...marcadas]);
      setGrade(g);
      onDone(g.acertou, g.xp);
    } finally {
      setEnviando(false);
    }
  };

  // As mistas têm COR PRÓPRIA. Pintar de verde ou vermelho seria mentir nas duas direções: o
  // GTO abre 87s 31% das vezes, então nem marcar nem deixar em branco é erro, e nenhuma das
  // duas é "a resposta". É a única célula em que o número, e não o veredito, é o ensinamento.
  const freqMista = new Map((grade?.mistas ?? []).map((m) => [m.hand, m.freq]));

  const estadoDaCelula = (h: string) => {
    if (!grade) return marcadas.has(h) ? "marcada" : "livre";
    if (freqMista.has(h)) return "mista";
    const certa = grade.certas.includes(h);
    if (certa && marcadas.has(h)) return "acerto";
    if (certa) return "faltou";
    if (marcadas.has(h)) return "sobrou";
    return "fora";
  };

  return (
    /* Duas colunas: matriz à esquerda, comandos à direita.
       Empilhado, a matriz empurrava contador e botão para fora da dobra e a página ganhava
       rolagem vertical — o jogador marcava as células e precisava rolar para conferir, perdendo
       a grade de vista justamente no momento do veredito. Em coluna, tudo cabe junto.

       O corte é `md` e não `lg` porque o Leak Trainer EXIGE paisagem: o celular deitado dá
       ~812px, ficaria de fora do `lg` e voltaria a empilhar — justamente no aparelho onde a
       altura é mais curta e o painel cairia abaixo da dobra.

       `justify-center` com as duas colunas de largura FIXA (e não a matriz em `flex-1`): com
       `flex-1` a coluna esquerda esticava até o limite do container e a matriz, presa em 560px,
       ficava encostada à esquerda dela — sobrava um vão à direita e o conjunto nascia torto. */
    <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-6 md:flex-row md:items-start md:justify-center">

      {/* A marcação acontece dentro da MATRIZ 13x13 de verdade, e não numa fileira de botões.
          A posição espacial é metade da memorização: quem treina numa lista aprende a sequência
          "A2s A3s A4s…", quem treina na matriz aprende ONDE a mão fica — e é a matriz que ele vai
          encontrar em toda ferramenta de poker, inclusive na tabela de ranges deste produto.
          As células fora da família ficam apagadas e inertes: mantêm a referência visual sem
          transformar o exercício em marcar 169 casas. */}
      {/* Encolhe (sem `shrink-0`): em paisagem de celular as duas colunas somam mais que a tela e
          a matriz vazava pela borda esquerda, cortando a coluna dos Áses. O `max-w` já a segura
          no desktop, então deixar encolher só ajuda. */}
      <div className="w-full min-w-0 max-w-[560px]">
        <div className="grid touch-none select-none gap-[3px]"
             style={{ gridTemplateColumns: "repeat(13, minmax(0, 1fr))" }}
             onPointerMove={(e) => arrastaSobre(e.clientX, e.clientY)}>
          {Array.from({ length: 13 }, (_, row) =>
            Array.from({ length: 13 }, (_, col) => {
              const h = cellHand(row, col);
              const naFamilia = hands.includes(h);
              const rotulo = cellLabel(row, col);
              const sufixo = h.endsWith("s") ? "s" : h.endsWith("o") ? "o" : "";
              const e = naFamilia ? estadoDaCelula(h) : "inerte";
              return (
                <button key={`${row}-${col}`}
                  data-mao={naFamilia ? h : undefined}
                  onPointerDown={() => inicia(h)}
                  // Teclado continua funcionando: `onPointerDown` não é acionado por Enter/Espaço.
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); alterna(h); }
                  }}
                  disabled={!naFamilia || !!grade}
                  title={naFamilia ? h : undefined}
                  className={cn(
                    "relative flex aspect-square items-center justify-center rounded-[3px] border font-mono leading-none transition-colors",
                    "text-[8px] sm:text-[10px]",
                    row === col && "ring-1 ring-inset ring-white/15",
                    // Inativa, mas VISÍVEL. Com borda transparente e texto a 25%, a matriz
                    // sumia e sobrava só a diagonal — o exercício perdia justamente o que ele
                    // deveria ensinar, que é a geometria da grade.
                    e === "inerte"  && "cursor-default border-border/25 bg-muted/[0.04] text-muted-foreground/45",
                    e === "livre"   && "border-amber-500/40 bg-amber-500/[0.06] text-foreground hover:border-amber-500/80 hover:bg-amber-500/15",
                    e === "marcada" && "border-amber-500/70 bg-amber-500/20 text-amber-200",
                    e === "acerto"  && "border-emerald-500/70 bg-emerald-500/20 text-emerald-200",
                    e === "faltou"  && "border-dashed border-emerald-500/70 bg-emerald-500/5 text-emerald-400/80",
                    e === "sobrou"  && "border-red-500/70 bg-red-500/20 text-red-200",
                    e === "mista"   && "border-sky-500/60 bg-sky-500/15 text-sky-200",
                  )}>
                  {rotulo}
                  {sufixo && <span className="ml-[0.5px] text-[0.72em] opacity-70">{sufixo}</span>}
                  {e === "faltou" && <Check className="absolute -right-0.5 -top-0.5 size-2.5 text-emerald-400" aria-hidden />}
                  {e === "sobrou" && <X className="absolute -right-0.5 -top-0.5 size-2.5 text-red-400" aria-hidden />}
                </button>
              );
            })
          )}
        </div>
        <p className="mt-2 text-center font-mono text-[10px] text-muted-foreground">
          {t("leakTrainer.grid.onlyFamily", { familia: spot.familia_label })}
        </p>
        {!grade && (
          <p className="mt-1 text-center font-mono text-[10px] text-amber-400/70">
            {t("leakTrainer.grid.dragHint")}
          </p>
        )}
      </div>

      <aside className="w-full shrink-0 space-y-4 md:w-[240px] lg:w-[260px]">
        <div className="text-center md:text-left">
          <p className={cn("font-mono text-[10px] uppercase tracking-widest",
            spot.srs?.revisao ? "text-sky-400" : "text-amber-400")}>
            {spot.srs?.revisao
              ? t("leakTrainer.grid.reviewEyebrow", "Revisão")
              : t("leakTrainer.grid.eyebrow")}
          </p>
          <h2 className="mt-1.5 font-heading text-[15px] font-bold leading-snug text-foreground">
            {t("leakTrainer.grid.question", {
              pos: spot.position, familia: spot.familia_label, stack: spot.stack_bb,
            })}
          </h2>
        </div>

        {/* Onde essa posição SENTA. "LJ abre" não diz nada a quem ainda não sabe onde o LJ fica,
            e sem a referência espacial a sigla vira decoreba: não dá para entender por que ela
            abre mais estreito que o CO sem ver que ela age antes. */}
        <PositionMap destaque={spot.position} className="mx-auto" />

        {/* Contador ao vivo: combinações e fatia do BARALHO, não da família. */}
        <div className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-background/60 px-3 py-2.5 text-center font-mono text-[11px]">
          <div>
            <div className="text-foreground">{marcadas.size}/{hands.length}</div>
            <div className="text-[9px] text-muted-foreground">{t("leakTrainer.grid.marked")}</div>
          </div>
          <div>
            <div className="text-foreground">{combos}</div>
            <div className="text-[9px] text-muted-foreground">combos</div>
          </div>
          <div>
            <div className={cn(marcadas.size ? "text-amber-400" : "text-muted-foreground")}>{pct}%</div>
            <div className="text-[9px] text-muted-foreground">{t("leakTrainer.grid.ofDeck")}</div>
          </div>
        </div>

      {!grade ? (
        <button onClick={corrigir} disabled={enviando}
          className="w-full rounded-xl bg-amber-500/15 px-4 py-3 font-mono text-xs font-bold uppercase tracking-wider text-amber-400 ring-1 ring-amber-500/40 transition-colors hover:bg-amber-500/25 disabled:opacity-40">
          {t("leakTrainer.grid.check")}
        </button>
      ) : (
        <div className="space-y-3 animate-fade-in">
          <p className={cn("text-center font-heading text-base font-bold",
            grade.acertou ? "text-emerald-400" : "text-amber-400")}>
            {grade.acertou ? t("leakTrainer.grid.right") : t("leakTrainer.grid.almost")}
          </p>
          <p className="text-center text-[13px] leading-snug text-muted-foreground">
            {t("leakTrainer.grid.boundary", {
              pos: spot.position, familia: spot.familia_label,
              hand: grade.fronteira ?? "—",
              combos: combosDeMaos(grade.certas).combos,
              pct: combosDeMaos(grade.certas).pct,
              total: totalFamilia.combos,
            })}
          </p>
          {/* Onde o GTO mistura, dito em número. Sem isto o jogador vê células azuis e conclui
              que errou — quando o fato a aprender é justamente que ali não há resposta única. */}
          {grade.mistas?.length > 0 && (
            <p className="rounded-lg border border-sky-500/25 bg-sky-500/[0.06] px-2.5 py-2 text-center text-[11px] leading-snug text-sky-200/90">
              {t("leakTrainer.grid.mixedNote", { n: grade.mistas.length,
                  maos: grade.mistas.map((m) => `${m.hand} ${Math.round(m.freq * 100)}%`).join(" · "),
                  defaultValue: `Em azul, o GTO mistura: ${grade.mistas.map((m) => `${m.hand} ${Math.round(m.freq * 100)}%`).join(" · ")}. Marcar ou não, as duas passam.` })}
            </p>
          )}
          {grade.srs && (
            <p className="text-center font-mono text-[10px] text-muted-foreground/70">
              {t("leakTrainer.grid.nextReview", { dias: grade.srs.interval_days,
                  defaultValue: `Volta em ${grade.srs.interval_days} dias` })}
            </p>
          )}
          {rodape}
        </div>
      )}
      </aside>
    </div>
  );
}
