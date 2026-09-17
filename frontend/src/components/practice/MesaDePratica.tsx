import { useTranslation } from "react-i18next";
import { Star } from "lucide-react";
import { MesaCompacta } from "@/components/practice/MesaCompacta";
import { twFor, actionKey } from "@/lib/actionColors";
import { FREQ_MINIMA_PARA_EXISTIR, nivelDoGrade, normalizaAcao, SIMBOLO_DO_NIVEL, type Nivel, type Unidade } from "@/lib/pratica";
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

/**
 * O card de veredito, no CENTRO da mesa (pedido do dono: "podiamos mostrar no centro da mesa",
 * sobre o card de feedback do GTO Wizard).
 *
 * O modelo deles: um circulo com a pontuacao e, ao lado, a frase do nivel. Aqui a pontuacao e a
 * frequencia com que o GTO joga a acao ESCOLHIDA, que e o numero honesto para este produto --
 * "100%" quando a jogada e a unica que o solver faz, e a fracao quando ele mistura. Sem
 * `hand_freq` o circulo nao aparece: inventar uma pontuacao onde nao houve medida seria o
 * contrario do que o resto do veredito faz.
 */
function CardDeVeredito({ nivel, grade, acao }: {
  nivel: Nivel;
  grade: PracticeGrade | null;
  acao: string;
}) {
  const { t } = useTranslation("practice");
  const freq = grade?.hand_freq || null;
  const daEscolhida = freq
    ? Object.entries(freq).find(([a]) => normalizaAcao(a) === normalizaAcao(acao))?.[1]
    : undefined;
  const pct = typeof daEscolhida === "number" ? Math.round(daEscolhida * 100) : null;

  // as duas outras pernas da mistura, para ele ver o que o GTO faz com o resto do tempo
  const outras = freq
    ? Object.entries(freq)
        // `FREQ_MINIMA_PARA_EXISTIR` e a MESMA constante que a regua usa para decidir se "o GTO
        // faz" e verdade: uma perna que nao aparece aqui nao pode justificar um veredito.
        .filter(([a, v]) => typeof v === "number" && v >= FREQ_MINIMA_PARA_EXISTIR
                            && normalizaAcao(a) !== normalizaAcao(acao))
        .sort((a, b) => (b[1] as number) - (a[1] as number))
        .slice(0, 2)
    : [];

  return (
    <div data-testid="pratica-veredito" className="flex items-center justify-center gap-3">
      {pct != null && (
        <span className={cn("flex shrink-0 flex-col items-center justify-center rounded-full border-2 leading-none",
                            ANEL_DO_NIVEL[nivel])}
              style={{ width: "clamp(58px, 8cqw, 104px)", height: "clamp(58px, 8cqw, 104px)" }}>
          <b className="font-mono font-bold tabular-nums"
             style={{ fontSize: "clamp(17px, 2.5cqw, 32px)" }}>{pct}%</b>
          <span className="font-mono uppercase tracking-widest-2 opacity-70"
                style={{ fontSize: "clamp(7px, 0.95cqw, 12px)" }}>
            {/* "sua jogada", e não "GTO joga": o número É a frequência da jogada DELE, e o
                rótulo antigo lia-se "0% GTO joga", que deixava dúvida sobre de quem é o 0%. */}
            {t("veredito.suaJogada")}
          </span>
        </span>
      )}
      <span className="min-w-0 text-left">
        <b className={cn("block font-heading font-bold leading-tight", TEXTO_DO_NIVEL[nivel])}
           style={{ fontSize: "clamp(15px, 2.1cqw, 27px)" }}>
          {/* O simbolo ORDENA (pedido do dono: "VV, V, X, XX") e a palavra NOMEIA. Os dois,
              porque um sozinho nao faz o trabalho do outro: "imprecisao" e "errada" sao dois
              substantivos que nao dizem qual e pior, e o simbolo sozinho nao diz o que houve. */}
          <span className="mr-1.5 font-mono">{SIMBOLO_DO_NIVEL[nivel]}</span>
          {t(`nivel.${nivel}`)}
        </b>
        {outras.length > 0 && (
          <span className="block font-mono text-muted-foreground"
                style={{ fontSize: "clamp(10px, 1.4cqw, 17px)" }}>
            {/* "GTO TAMBEM" só quando a jogada DELE tem frequência: ali o GTO faz as duas
                coisas, e "também" é a palavra certa. Com 0%, o GTO não faz a dele -- e a frase
                virava "GTO também: fold 100%" ao lado de um raise que o solver nunca joga, que
                foi o que o dono estranhou. Sem frequência, a frase diz o que o GTO FAZ. */}
            {t(pct ? "veredito.oGtoTambem" : "veredito.oGtoJoga")} {outras.map(([a, v]) =>
              `${a} ${Math.round((v as number) * 100)}%`).join(" · ")}
          </span>
        )}
        {/* O buraco que sobrava: com frequencia ZERO e custo abaixo do piso de ruido, o nivel e
            "aceitavel" -- e o selo de check ao lado de "0% SUA JOGADA" e a MESMA contradicao que
            o dono fotografou, so num canto mais estreito. Aqui a frase diz as duas coisas: o GTO
            nao faz, e nao custa nada. */}
        {pct === 0 && nivel === "imprecisao" && (
          <span data-testid="veredito-fora-sem-custo"
                className="block leading-snug text-muted-foreground"
                style={{ fontSize: "clamp(10px, 1.4cqw, 17px)" }}>
            {t("veredito.foraSemCusto")}
          </span>
        )}
        {typeof grade?.ev_loss_bb === "number" && grade.ev_loss_bb !== 0 && (
          <span className="block font-mono font-bold tabular-nums text-red-400"
                style={{ fontSize: "clamp(11px, 1.5cqw, 18px)" }}>
            −{Math.abs(grade.ev_loss_bb).toFixed(2)}bb
          </span>
        )}
      </span>
    </div>
  );
}

/** O anel do circulo, por nivel. Separado do texto para o circulo poder ser mais forte. */
const ANEL_DO_NIVEL: Record<Nivel, string> = {
  // `correta` herdou o verde que era da "melhor jogada": fundidos, o nivel bom fica com a cor
  // mais forte dos dois.
  correta:    "border-emerald-400 text-emerald-300",
  imprecisao: "border-amber-400 text-amber-300",
  errada:     "border-red-400 text-red-300",
  grave:      "border-red-600 text-red-400",
};

const TEXTO_DO_NIVEL: Record<Nivel, string> = {
  correta:    "text-emerald-300",
  imprecisao: "text-amber-300",
  errada:     "text-red-300",
  grave:      "text-red-400",
};

const COR_DO_NIVEL: Record<Nivel, string> = {
  correta:    "bg-emerald-500/10 text-emerald-300",
  imprecisao: "bg-amber-500/10 text-amber-300",
  errada:     "bg-red-500/10 text-red-300",
  grave:      "bg-red-900/25 text-red-300",
};

export function MesaDePratica({
  mesa, foco, respondida, grade, acaoEscolhida, leakDoJogador, compacta, unidade,
  avaliando, onAgir, onFocar, onDetalhe,
}: {
  mesa: PracticeTable;
  /** BB (padrão) ou fichas. Quem decide é o painel; aqui só chega a escolha. */
  unidade: Unidade;
  foco: boolean;
  respondida: boolean;
  grade: PracticeGrade | null;
  /** A resposta foi enviada e a avaliacao do servidor ainda nao voltou. */
  avaliando: boolean;
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
      {/* ── O cabeçalho SAIU da coluna (17/09) ─────────────────────────────────────────────
          O dono, duas coisas no mesmo recado: "se colocarmos as ações mais coladas no topo, a
          mesa consegue crescer verticalmente, pra cima e para baixo...ela pode ficar mais próxima
          dos botões de ação também" e "no canto inferior esquerdo de cada box, tem as cartas em
          texto...desnecessário".

          A mão em texto ("J6s") foi embora: ela dizia com letras o que as cartas do herói já
          mostram desenhadas na mesa, e custava uma linha inteira de altura em cada card.

          O stack ficou, porque ele é o titulo do spot -- mas FLUTUANDO no canto, e não numa linha
          própria. A linha era o que empurrava a mesa para baixo. */}
      <span className="pointer-events-none absolute right-2.5 top-1.5 z-10 font-mono text-[9.5px] font-bold tabular-nums text-muted-foreground">
        {/* a MESMA unidade da mesa: a mesma grandeza escrita de dois jeitos no mesmo card é como
            nasce o bug mais recorrente do projeto (fichas vs BB) */}
        {unidade === "bb"
          ? `${mesa.spot.stack_bb}bb`
          : Math.round(mesa.spot.stack_bb * (mesa.table.bb_chips || 1)).toLocaleString("pt-BR")}
      </span>

      {/* ── A mesa NO TOPO, e os botoes logo abaixo dela (pedido do dono, 16/09) ────────────
          A altura vem da LARGURA (`aspect-ratio`), e nao de `flex-1`: com `flex-1` a mesa
          absorvia a celula inteira e o feltro, que e um SVG centralizado, deixava um vao entre
          a mesa e os controles -- o jogador percorria a tela para clicar no que decide a mao.
          `max-h-full` e o que impede isso de trazer a barra de rolagem de volta: quando a
          celula e mais larga que 16/10, a altura para em 100% e a largura encolhe junto. */}
      {/* ── A mesa ocupa o que SOBRA, e nao uma altura que ela exige ────────────────────────
          Com `aspect-ratio: 16/10` e `shrink-0`, numa celula de 840px de largura ela pedia 525px
          de altura, estourava os ~440 disponiveis e EMPURRAVA OS BOTOES para fora do card (que e
          `overflow-hidden`) -- eles simplesmente desapareciam, e foi o que o dono viu.

          Agora: `flex-1 min-h-0` aqui e `shrink-0` nos botoes, entao os controles tem a vez na
          divisao da altura e a mesa fica com o resto. O trilho e definido em % da propria caixa,
          entao ele ACHATA junto e fica com a proporcao do GTO Wizard (bem mais largo que alto),
          que foi a direcao que o dono apontou com o exemplo deles. */}
      <div className="mx-auto min-h-0 w-full flex-1">
        {/* `compacta` NAO chega na mesa: ela escala pelo container (cqw), entao 1 ou 4 mesas
            usam a mesma proporcao e nada encolhe por degrau -- e o que o GTO Wizard faz. */}
        <MesaCompacta table={mesa.table} hero="Hero" unidade={unidade}
                      spot={mesa.resumo || mesa.context}
                      veredito={
                        // Tres estados, e nenhum deles inventa veredito. O "avaliando" existe
                        // porque o clique precisa de resposta imediata: sem ele o jogador clica e
                        // a mesa nao muda, o que parece travamento. O "sem avaliacao" existe
                        // porque falha do `/grade` nao e erro DELE -- antes deste conserto ela
                        // aparecia como "errada" e ficava parada assim.
                        respondida && nivel
                          ? <CardDeVeredito nivel={nivel} grade={grade}
                                            acao={acaoEscolhida || ""} />
                          : avaliando
                            ? <span data-testid="pratica-avaliando"
                                    className="block font-mono uppercase tracking-widest-2 text-muted-foreground animate-pulse"
                                    style={{ fontSize: "clamp(10px, 1.7cqw, 20px)" }}>
                                {t("avaliando")}
                              </span>
                            : respondida
                              ? <span data-testid="pratica-sem-avaliacao" className="block">
                                  <span className="block font-mono uppercase tracking-widest-2 text-muted-foreground"
                                        style={{ fontSize: "clamp(10px, 1.7cqw, 20px)" }}>
                                    {t("semAvaliacao")}
                                  </span>
                                  <span className="mt-0.5 block leading-snug text-muted-foreground/70"
                                        style={{ fontSize: "clamp(9px, 1.5cqw, 17px)" }}>
                                    {t("semAvaliacaoDica")}
                                  </span>
                                </span>
                              : undefined
                      } />
      </div>

      {/* Os botões que ESTE spot oferece, nas cores da casa (fold azul, call verde, raise
          vermelho, all-in vinho — a paleta única de `actionColors`). */}
      {/* logo abaixo do feltro, e nao no rodape do card */}
      <div className="mt-1 flex shrink-0 gap-1.5">
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
                // ── Botoes MAIORES (17/09) ──────────────────────────────────────────────────
                // O dono: "os botoes estão muito estreitos também, preciso ser maiores pra
                // facilitar a visualização". Eram `py-1.5` com fonte de 10px, e no celular isso
                // fica abaixo do alvo de toque confortavel (~44px).
                //
                // A altura minima e em px e nao em padding: com padding, a fonte menor no celular
                // encolhia o botao junto. E o espaco existe porque a mesa passou a ter aspecto com
                // faixa -- ela nao ocupa mais toda a altura do card, e o que sobra vem para ca.
                "flex-1 rounded font-mono text-[11px] font-bold uppercase tracking-widest-2 text-white sm:text-[12px]",
                "flex min-h-[44px] items-center justify-center py-2 transition-opacity disabled:cursor-default",
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

      {/* A linha de veredito do rodapé SAIU: ela e o card do centro renderizavam o mesmo
          veredito ao mesmo tempo (dois `pratica-veredito` no DOM, que o teste pegou). O dono
          pediu no centro, e lá é melhor -- o olho já está lá, onde ele leu o pote para decidir.

          O que a linha tinha e o centro não: a marca do leak dele e o clique para o detalhe.
          Os dois viraram uma faixa própria, fina, que não repete o veredito. */}
      {respondida && nivel && (leakDoJogador != null || grade?.explanation) && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDetalhe(); }}
          data-testid="pratica-detalhe"
          className="mt-1 flex w-full shrink-0 items-center gap-2 rounded px-2 py-0.5 text-left"
        >
          {grade?.explanation && (
            <span className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
              {t("veredito.verDetalhe")}
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

    </div>
  );
}

/** A letra de cada ação. Mora ao lado do botão porque é rótulo, não regra: a REGRA (que tecla
 *  vira que ação naquele spot) é `acaoDaTecla`, em `lib/pratica`. */
const ATALHO: Record<string, string> = {
  fold: "F", call: "C", check: "C", raise: "R", bet: "R", allin: "A",
};
