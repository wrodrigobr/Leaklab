import { useTranslation } from "react-i18next";
import { Star } from "lucide-react";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { buildDrillStep } from "@/lib/mesaDoDrill";
import { twFor, actionKey } from "@/lib/actionColors";
import { nivelDoGrade, type Nivel, type Unidade } from "@/lib/pratica";
import type { PracticeGrade, PracticeTable } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Uma mesa do modo Prática: a mesa desenhada, os botões que o spot oferece, e o veredito.
 *
 * ── Por que o veredito é uma LINHA e não um modal ─────────────────────────────────────────────
 *
 * Com quatro mesas, um modal por resposta são quatro interrupções por rodada, e o treino de
 * quatro mesas fica mais lento que o de uma. A linha diz o essencial (qualidade, o que o GTO faz,
 * o custo) e o resto fica a um clique.
 *
 * ── Por que os botões vêm do spot ─────────────────────────────────────────────────────────────
 *
 * `table.options` nasce do StrategyProvider, que deriva o menu da estratégia: a 12bb existe
 * all-in, a 100bb não, e no RFI do SB existe o limp. Uma lista fixa aqui ofereceria ação que o
 * spot não tem, e o servidor recusaria a resposta sem o jogador entender.
 */

const COR_DO_NIVEL: Record<Nivel, string> = {
  melhor:     "bg-emerald-500/10 text-emerald-300",
  correta:    "bg-primary/10 text-primary",
  imprecisao: "bg-amber-500/10 text-amber-300",
  errada:     "bg-red-500/10 text-red-300",
  grave:      "bg-red-900/25 text-red-300",
};

export function MesaDePratica({
  mesa, foco, respondida, grade, acaoEscolhida, leakDoJogador, compacta, unidade,
  onAgir, onFocar, onDetalhe,
}: {
  mesa: PracticeTable;
  /** BB (padrão) ou fichas. Quem decide é o painel; aqui só chega a escolha. */
  unidade: Unidade;
  foco: boolean;
  respondida: boolean;
  grade: PracticeGrade | null;
  acaoEscolhida: string | null;
  /** posição deste spot na lista de leaks DELE, quando calha de ser um. `null` = não é. */
  leakDoJogador: number | null;
  /** 3 ou 4 mesas: a mesa encolhe o CONTEÚDO, não só a escala. */
  compacta: boolean;
  onAgir: (acao: string) => void;
  onFocar: () => void;
  onDetalhe: () => void;
}) {
  const { t } = useTranslation("practice");

  // O caminho REAL do buildDrillStep: `table` vem do servidor com folds, botão e stacks certos.
  // O fallback dele põe a aposta enfrentada no assento anterior ao herói, que só por acaso é o
  // abridor -- e é por isso que a mesa do Prática é montada no servidor.
  const { step, hero, heroCards, bb } = buildDrillStep(
    { hero_cards: mesa.table.hero_cards, stack_bb: mesa.spot.stack_bb, street: "preflop" },
    mesa.table,
  );

  const nivel = respondida ? nivelDoGrade(grade, acaoEscolhida || "") : null;
  const freq = grade?.hand_freq || null;
  const melhores = freq
    ? Object.entries(freq).filter(([, v]) => typeof v === "number" && v >= 0.01)
        .sort((a, b) => b[1] - a[1]).slice(0, 2)
    : [];

  return (
    <div
      onClick={onFocar}
      data-testid={`pratica-mesa-${mesa.id}`}
      data-foco={foco ? "1" : "0"}
      className={cn(
        // `h-full min-h-0 flex-col`: a mesa cabe na celula do grid, que ja divide a altura da
        // tela. `min-h-0` e o que permite o filho encolher -- sem ele o flex usa a altura do
        // conteudo e a grade estoura a faixa, trazendo de volta a barra de rolagem.
        "relative flex h-full min-h-0 flex-col rounded-lg border bg-hud-surface p-2.5 transition-colors",
        foco ? "border-primary ring-1 ring-inset ring-primary/25" : "border-border",
      )}
    >
      {/* O spot escrito: sem isto a mesa exige que o jogador reconstrua a história dos assentos */}
      <div className="flex items-baseline gap-2 min-w-0">
        <span className={cn("truncate font-mono text-[9.5px] uppercase tracking-widest-2",
                            foco ? "text-primary" : "text-muted-foreground")}>
          {mesa.context}
        </span>
        <span className="ml-auto shrink-0 font-mono text-[9.5px] font-bold tabular-nums text-muted-foreground">
          {/* o cabeçalho segue a MESMA unidade da mesa: a mesma grandeza escrita de dois jeitos
              no mesmo card é como nasce o bug mais recorrente do projeto (fichas vs BB) */}
          {unidade === "bb"
            ? `${mesa.spot.stack_bb}bb`
            : Math.round(mesa.spot.stack_bb * (mesa.table.bb_chips || 1)).toLocaleString("pt-BR")}
        </span>
      </div>

      {/* ── A mesa NO TOPO, e os botoes logo abaixo dela (pedido do dono, 16/09) ────────────
          A altura vem da LARGURA (`aspect-ratio`), e nao de `flex-1`: com `flex-1` a mesa
          absorvia a celula inteira e o feltro, que e um SVG centralizado, deixava um vao entre
          a mesa e os controles -- o jogador percorria a tela para clicar no que decide a mao.
          `max-h-full` e o que impede isso de trazer a barra de rolagem de volta: quando a
          celula e mais larga que 16/10, a altura para em 100% e a largura encolhe junto. */}
      <div className="mx-auto mt-1.5 max-h-full w-full shrink-0" style={{ aspectRatio: "16 / 10" }}>
        <PokerTableV3
          step={step} hero={hero} heroCards={heroCards} bb={bb}
          // a mesa mostra BB por padrão: é a régua do resto do produto (solver, leaks, EV, ELO)
          betUnit={unidade === "bb" ? "bb" : "chips"} transparentBg
          // compacta = 3 ou 4 mesas na tela: o HUD e o nome do vilão competem pelo espaço que
          // decide a jogada (posição, stack, fichas na mesa), então saem.
          showHud={!compacta}
          fill
        />
      </div>

      {/* Os botões que ESTE spot oferece, nas cores da casa (fold azul, call verde, raise
          vermelho, all-in vinho — a paleta única de `actionColors`). */}
      {/* logo abaixo do feltro, e nao no rodape do card */}
      <div className="mt-1 flex shrink-0 gap-1">
        {mesa.options.map((o) => {
          const k = actionKey(o.action);
          const escolhida = acaoEscolhida === o.action;
          return (
            <button
              key={o.action}
              type="button"
              disabled={respondida}
              data-testid={`pratica-acao-${o.action}`}
              onClick={(e) => { e.stopPropagation(); onAgir(o.action); }}
              className={cn(
                "flex-1 rounded font-mono text-[10px] font-bold uppercase tracking-widest-2 text-white",
                "py-1.5 transition-opacity disabled:cursor-default",
                twFor(o.action).bg,   // `twFor` devolve {bg,text,ring}: aqui o fundo do botão
                respondida && !escolhida && "opacity-25",
                escolhida && "ring-2 ring-inset ring-white/60",
              )}
            >
              {o.label}
              {/* a tecla, só quando a mesa tem o foco: em quatro mesas a mesma letra em todas
                  ensinaria que ela age em qualquer uma */}
              {foco && <span className="ml-1 font-normal opacity-55">{ATALHO[k] ?? ""}</span>}
            </button>
          );
        })}
      </div>

      {/* O veredito em UMA linha. Clicar abre o detalhe. */}
      {respondida && nivel && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDetalhe(); }}
          data-testid="pratica-veredito"
          className={cn("mt-1 flex w-full shrink-0 items-center gap-2 rounded px-2 py-1 text-left",
                        COR_DO_NIVEL[nivel])}
        >
          <span className="font-mono text-[9.5px] font-bold uppercase tracking-widest-2">
            {t(`nivel.${nivel}`)}
          </span>
          {melhores.length > 0 && (
            <span className="min-w-0 truncate font-mono text-[9.5px] opacity-80">
              {t("gtoFaz")} {melhores.map(([a, v]) => `${a} ${Math.round(v * 100)}%`).join(" · ")}
            </span>
          )}
          {typeof grade?.ev_loss_bb === "number" && grade.ev_loss_bb !== 0 && (
            <span className="shrink-0 font-mono text-[9.5px] font-bold tabular-nums">
              −{Math.abs(grade.ev_loss_bb).toFixed(2)}bb
            </span>
          )}
          {/* O que nenhum concorrente copia sem ter o histórico do jogador. */}
          {leakDoJogador != null && (
            <span className="ml-auto inline-flex shrink-0 items-center gap-1 font-mono text-[9px] text-primary">
              <Star className="size-2.5" aria-hidden />
              {t("seuLeak", { n: leakDoJogador })}
            </span>
          )}
        </button>
      )}

      {/* A sobra fica AQUI, no fim: mesa e controles ancorados no topo do card. Sem este
          espaçador, o `justify` do flex distribuiria o vão entre os blocos e os botões
          voltariam a flutuar longe do feltro. */}
      <div className="min-h-0 flex-1" aria-hidden />
    </div>
  );
}

/** A letra de cada ação. Mora ao lado do botão porque é rótulo, não regra: a REGRA (que tecla
 *  vira que ação naquele spot) é `acaoDaTecla`, em `lib/pratica`. */
const ATALHO: Record<string, string> = {
  fold: "F", call: "C", check: "C", raise: "R", bet: "R", allin: "A",
};
