import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, X } from "lucide-react";
import { leaktrainer, type LeakTrainerSpot, type RangeGridGrade } from "@/lib/api";
import { cellHand, cellLabel, combosDeMaos } from "@/data/ranges";
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
export function RangeFamilyDrill({ spot, onDone }: {
  spot: LeakTrainerSpot;
  onDone: (acertou: boolean, xp: number) => void;
}) {
  const { t } = useTranslation("academy");
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [grade, setGrade] = useState<RangeGridGrade | null>(null);
  const [enviando, setEnviando] = useState(false);

  const hands = spot.hands ?? [];
  const { combos, pct } = combosDeMaos([...marcadas]);
  const totalFamilia = combosDeMaos(hands);

  const alterna = (h: string) => {
    if (grade) return;
    setMarcadas((s) => {
      const n = new Set(s);
      if (n.has(h)) n.delete(h); else n.add(h);
      return n;
    });
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

  const estadoDaCelula = (h: string) => {
    if (!grade) return marcadas.has(h) ? "marcada" : "livre";
    const certa = grade.certas.includes(h);
    if (certa && marcadas.has(h)) return "acerto";
    if (certa) return "faltou";
    if (marcadas.has(h)) return "sobrou";
    return "fora";
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5">
      <div className="text-center">
        <p className="font-mono text-[10px] uppercase tracking-widest text-amber-400">
          {t("leakTrainer.grid.eyebrow")}
        </p>
        <h2 className="mt-1.5 font-heading text-lg font-bold text-foreground">
          {t("leakTrainer.grid.question", {
            pos: spot.position, familia: spot.familia_label, stack: spot.stack_bb,
          })}
        </h2>
      </div>

      {/* A marcação acontece dentro da MATRIZ 13x13 de verdade, e não numa fileira de botões.
          A posição espacial é metade da memorização: quem treina numa lista aprende a sequência
          "A2s A3s A4s…", quem treina na matriz aprende ONDE a mão fica — e é a matriz que ele vai
          encontrar em toda ferramenta de poker, inclusive na tabela de ranges deste produto.
          As células fora da família ficam apagadas e inertes: mantêm a referência visual sem
          transformar o exercício em marcar 169 casas. */}
      <div className="mx-auto w-full max-w-[560px]">
        <div className="grid gap-[3px]" style={{ gridTemplateColumns: "repeat(13, minmax(0, 1fr))" }}>
          {Array.from({ length: 13 }, (_, row) =>
            Array.from({ length: 13 }, (_, col) => {
              const h = cellHand(row, col);
              const naFamilia = hands.includes(h);
              const rotulo = cellLabel(row, col);
              const sufixo = h.endsWith("s") ? "s" : h.endsWith("o") ? "o" : "";
              const e = naFamilia ? estadoDaCelula(h) : "inerte";
              return (
                <button key={`${row}-${col}`} onClick={() => naFamilia && alterna(h)}
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
      </div>

      {/* Contador ao vivo: combinações e fatia do BARALHO, não da família. */}
      <div className="flex items-center justify-center gap-6 rounded-xl border border-border bg-background/60 px-4 py-2.5 font-mono text-xs">
        <span className="text-muted-foreground">
          {t("leakTrainer.grid.marked")} <span className="text-foreground">{marcadas.size}</span>/{hands.length}
        </span>
        <span className="text-muted-foreground">
          <span className="text-foreground">{combos}</span> combos
        </span>
        <span className={cn(marcadas.size ? "text-amber-400" : "text-muted-foreground")}>
          {pct}% {t("leakTrainer.grid.ofDeck")}
        </span>
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
        </div>
      )}
    </div>
  );
}
