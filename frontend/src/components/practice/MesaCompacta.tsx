import type { DrillTableState } from "@/lib/api";
import type { Unidade } from "@/lib/pratica";
import { cn } from "@/lib/utils";

/**
 * A mesa do modo Prática: um trilho, assentos redondos e nada mais.
 *
 * ── Por que ela existe, se já temos a `PokerTableV3` ──────────────────────────────────────────
 *
 * O dono, vendo quatro mesas: "ja esta ficando pequeno enxergar as fichas...talvez fazer como o
 * gto wizard faz, com mesas simples, mas funcionais", e depois mandou a captura deles.
 *
 * A `PokerTableV3` é a mesa do replayer, e desenha o que o replayer precisa: duas cartas viradas
 * por vilão, nome do jogador, HUD, board, showdown e a marca d'água no feltro. A um quarto de tela
 * isso não encolhe bem, e pior: no preflop **nada disso informa**. O jogador nunca vê carta de
 * vilão, o nome é `V7` (anonimizado), não há board e não há HUD num spot sintético. O que decide a
 * jogada é posição, stack, o que está na mesa e as cartas DELE.
 *
 * ── O que o modelo do GTO Wizard faz, e por que cada escolha economiza espaço ─────────────────
 *
 * - **Sem feltro preenchido.** Só uma linha fina ligando os assentos. O oval verde não carrega
 *   informação e disputava contraste com as fichas, que carregam.
 * - **Assento é um círculo** com a posição em cima e o stack embaixo, dentro dele. Compacto e
 *   sempre no mesmo lugar, então o olho aprende onde procurar.
 * - **As cartas do herói ao LADO do assento dele**, e não embaixo da mesa: elas ficam onde o olho
 *   já está, e não competem com os botões.
 * - **O spot escrito no centro**, onde sobra espaço de graça.
 * - **Carta é rank grande em quadrado colorido por naipe**, no baralho de 4 cores. A imagem de
 *   carta do `PlayingCard` é o desenho certo no replayer, mas a um quarto de tela o naipe vira um
 *   borrão; a cor do quadrado lê de longe.
 *
 * ── E por que isto NÃO é uma segunda fonte de verdade ─────────────────────────────────────────
 *
 * A regra 5 da casa fala de REGRA, e aqui nenhuma é duplicada: quem está na mão, quem apostou
 * quanto, onde fica o botão e qual o pote vêm todos do MESMO `table` que o servidor monta em
 * `pratica_preflop.mesa_do_spot`. Isto é desenho, e desenho diferente para uso diferente é o
 * oposto de duplicar a verdade. A `PokerTableV3` do replayer não mudou uma linha.
 */

/** Os nove lugares SOBRE o trilho, em %, com o herói embaixo e a ordem de ação girando. */
const TRILHO = { cx: 50, cy: 50, rx: 46, ry: 41 };

/**
 * ── O defeito que o pedido do dono revelou ────────────────────────────────────────────────────
 *
 * "coloque as fichas dentro da mesa, e aproxima mais todos os jogadores para a borda da mesa".
 *
 * A primeira versão tinha as posições escritas A MÃO, e elas não ficavam sobre a elipse do
 * trilho: com o trilho indo de y=12 a y=88 e assentos em y=8 e y=92, eles ficavam FORA da linha
 * -- e as fichas, deslocadas a partir deles, ainda mais para fora. Eram duas listas de números
 * descrevendo a mesma elipse, que é como elas divergem.
 *
 * Agora o trilho é um objeto e as posições são DERIVADAS dele por ângulo: mudar o trilho move os
 * assentos e as fichas junto, e eles não podem sair da linha por descuido.
 */

/** Da borda do card ao trilho, em %, derivado do próprio trilho (o CSS precisa do inset). */
const INSET = {
  y: `${TRILHO.cy - TRILHO.ry}%`,
  x: `${TRILHO.cx - TRILHO.rx}%`,
};

/** Os ângulos dos nove lugares, com o herói embaixo (90) e a ordem de ação girando. */
const ANGULOS = [90, 130, 170, 210, 250, 290, 330, 10, 50] as const;

/** `(x, y)` em %, sobre a elipse do trilho. `escala < 1` traz para DENTRO da mesa. */
function naElipse(grau: number, escala = 1): [number, number] {
  const r = (grau * Math.PI) / 180;
  return [
    TRILHO.cx + TRILHO.rx * escala * Math.cos(r),
    TRILHO.cy + TRILHO.ry * escala * Math.sin(r),
  ];
}

/** Os nove lugares, SOBRE o trilho. */
const LUGARES: [number, number][] = ANGULOS.map((a) => naElipse(a));

/** A ficha de cada assento: mesma direção, mais perto do centro -- dentro da mesa. `0.66` a
 *  deixa claramente dentro do trilho e ainda colada no assento dela, para não haver dúvida de
 *  quem apostou. */
const FICHAS: [number, number][] = ANGULOS.map((a) => naElipse(a, 0.8));

/**
 * As medidas, calibradas NA captura do GTO Wizard (o dono: "mantenha as mesmas proporcoes do gto
 * wizard, tamanho de carta, tamanho das fontes, fichas").
 *
 * Medido na tela de quatro mesas deles, onde cada mesa ocupa ~840x440: assento de 36px, carta de
 * 30x38, posicao em 9px e stack em 11px, ficha de 7px com o valor em 10px.
 *
 * Em `cqw` (a largura do CONTAINER, que e o card da mesa) e nao em px fixo: assim uma mesa so,
 * que tem celula maior, cresce na mesma proporcao em vez de ficar com elementos de miniatura no
 * meio de espaco vazio. O `clamp` poe piso e teto, para nem sumir numa tela estreita nem virar
 * cartaz num monitor largo.
 *
 * A primeira versao desta mesa usava px fixos com um degrau para "compacta", e ficou tudo pequeno
 * -- foi o que o dono viu. O GTO Wizard nao encolhe nada com quatro mesas: ele usa o mesmo
 * tamanho, e e a mesa inteira que e mais economica.
 */
const M = {
  assento: "clamp(30px, 4.3cqw, 52px)",
  cartaW:  "clamp(26px, 4.1cqw, 48px)",
  cartaH:  "clamp(36px, 5.6cqw, 64px)",
  fPos:    "clamp(7.5px, 1.07cqw, 13px)",
  fStack:  "clamp(9px, 1.31cqw, 16px)",
  // o rank cede um degrau para o simbolo caber embaixo dele, e a carta cresceu um pouco junto
  fCarta:  "clamp(13px, 2.2cqw, 27px)",
  // O naipe cresceu duas vezes: ele responde "e suited?", que e metade da decisao preflop, e
  // pequeno ele nao responde nada. Fica em ~80% do rank -- o rank identifica a carta, o naipe
  // identifica a MAO.
  fNaipe:  "clamp(11px, 1.8cqw, 22px)",
  fSpot:   "clamp(8.5px, 1.25cqw, 15px)",
  fPote:   "clamp(12px, 1.9cqw, 23px)",
  // A ficha e o valor sao o que o dono relatou duas vezes como pequeno demais, e eles carregam
  // a informacao que decide a jogada (quanto ha para pagar). Sao os MAIORES da mesa depois das
  // cartas dele e do pote, de proposito.
  fFicha:  "clamp(10px, 1.5cqw, 19px)",
  ficha:   "clamp(8px, 1.15cqw, 15px)",
  fHist:   "clamp(7.5px, 1.07cqw, 13px)",
} as const;

/**
 * Baralho de 4 cores: a cor do quadrado É o naipe, e ela lê de longe melhor que o símbolo.
 *
 * ── Por que os tons NÃO são os da paleta de ação ──────────────────────────────────────────────
 *
 * A primeira versão usou o verde do call e o azul do fold para clubs e diamonds, e o guarda de
 * `actionColors` acusou -- com razão. (Os hex não vão escritos aqui de propósito: aquele guarda
 * varre o arquivo inteiro sem distinguir prosa de código, e citar o valor numa explicação já o
 * fez acusar uma vez. É a quarta vez hoje que um guarda de varredura desta casa tropeça em
 * comentário.) Naipe e ação são dois vocabulários de cor no
 * mesmo produto, e nesta tela eles aparecem LADO A LADO: o botão verde ao lado de uma carta
 * verde ensinaria que aquela carta tem a ver com "call".
 *
 * Então os quatro naipes têm tons próprios, próximos o bastante para o jogador reconhecer o
 * baralho de 4 cores e distintos o bastante para nenhum deles ser o hex de uma ação.
 */
/** O simbolo, que e o que responde "qual o naipe?" de perto. A cor responde de longe. */
const SIMBOLO: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };

const NAIPE: Record<string, { bg: string; fg: string }> = {
  s: { bg: "#C9D1DB", fg: "#0A0E1A" },   // spades   — cinza
  h: { bg: "#D93B42", fg: "#FFFFFF" },   // hearts   — vermelho de naipe
  d: { bg: "#4A8FD4", fg: "#FFFFFF" },   // diamonds — azul de naipe
  c: { bg: "#3E9B54", fg: "#FFFFFF" },   // clubs    — verde de naipe
};

/** `"Ks7h"` → `[["K","s"],["7","h"]]`. Aceita o que o servidor manda e ignora o resto. */
export function lerCartas(raw: string | null | undefined): [string, string][] {
  return [...String(raw || "").matchAll(/([2-9TJQKA])([shdc])/gi)]
    .map((m) => [m[1].toUpperCase(), m[2].toLowerCase()] as [string, string])
    .slice(0, 2);
}

/** O histórico da mão, na ordem de ação: `[{pos, texto, fold, vez}]`.
 *
 *  Exportada para ter teste próprio: derivar ação a partir de `bet` tem um caso que engana, o
 *  BB, cujo `bet` de 1bb é o blind POSTADO e não um aumento. Tratar o blind como aposta faria a
 *  faixa dizer que o BB "apostou 1" em toda mão, e o jogador leria isso como agressão.
 */
export function historico(
  seats: DrillTableState["seats"],
  hero: string,
  fmt: (chips: number) => string,
  bbEmFichas: number,
): { pos: string; texto: string; fold: boolean; vez: boolean }[] {
  // O blind de referência vem de `bb_chips`, e NÃO do `bet` do próprio assento. A primeira
  // versão lia o blind do BB a partir do `bet` dele, que é exatamente o valor que muda quando ele
  // aumenta: num 3-bet do BB a conta comparava 800 com 800, dava falso, e o aumento dele
  // DESAPARECIA do histórico. Foi o teste do caso contrário que pegou.
  const blindDe = (pos: string) => {
    const p = (pos || "").toUpperCase();
    if (p === "BB") return bbEmFichas;
    if (p === "SB") return bbEmFichas / 2;
    return 0;
  };

  return seats
    .filter((s) => {
      const ehHeroi = s.hero || s.name === hero;
      if (ehHeroi) return true;
      if (s.folded) return true;
      // aumentou de verdade = pôs mais que o próprio blind
      return s.bet > blindDe(s.pos || "");
    })
    .map((s) => {
      const ehHeroi = s.hero || s.name === hero;
      if (ehHeroi) return { pos: s.pos || String(s.seat), texto: "sua vez", fold: false, vez: true };
      if (s.folded) return { pos: s.pos || String(s.seat), texto: "fold", fold: true, vez: false };
      return { pos: s.pos || String(s.seat), texto: fmt(s.bet), fold: false, vez: false };
    });
}

export function MesaCompacta({ table, hero, unidade, spot, veredito }: {
  table: DrillTableState;
  /** o nome do herói no `table.seats` (o servidor manda "Hero") */
  hero: string;
  /** o spot em uma frase, do servidor. Vai no CENTRO do trilho, como no GTO Wizard: ali sobra
   *  espaço de graça, e no cabeçalho do card ele comia a linha do histórico. */
  spot?: string;
  /** O card de veredito, que OCUPA o centro depois da resposta e esconde o spot.
   *
   *  Quem monta é a `MesaDePratica`, e não esta mesa: o veredito nasce da correção do servidor,
   *  e a mesa não conhece nem a resposta nem a régua. Aqui ele é só um lugar na geometria. */
  veredito?: React.ReactNode;
  unidade: Unidade;
}) {
  const bb = table.bb_chips || 1;
  const seats = [...(table.seats ?? [])].sort((a, b) => a.seat - b.seat);
  const cartas = lerCartas(table.hero_cards);
  const naMao = seats.filter((s) => !s.folded && s.active).length;

  /** Fichas na unidade escolhida. UMA função para stack e aposta: dois formatadores é como a
   *  mesa acaba mostrando a mesma grandeza de dois jeitos (a cicatriz "fichas vs BB"). */
  const fmt = (chips: number) => {
    if (unidade === "bb") {
      // Uma decimal quando nao for inteiro, como o GTO Wizard faz ("39.5"): arredondar 17.8
      // para 18 apagava o desconto da aposta, e o stack DEPOIS de por fichas e o que decide o
      // proximo movimento.
      const v = Math.round((chips / bb) * 10) / 10;
      return Number.isInteger(v) ? String(v) : v.toFixed(1);
    }
    return Math.round(chips).toLocaleString("pt-BR");
  };

  return (
    // `containerType: inline-size` e o que faz os `cqw` acima medirem ESTE card, e nao a
    // viewport: com `vw`, quatro mesas e uma mesa dariam elementos do mesmo tamanho.
    // `container-mesa` liga o `container-type: inline-size`, que faz os `cqw` acima medirem
    // ESTE card e nao a viewport. Em CLASSE e nao inline porque o jsdom descarta a propriedade
    // inline e o guarda nao conseguia ve-la.
    <div className="relative h-full w-full container-mesa" data-testid="mesa-compacta">
      {/* ── O histórico, no topo (como o GTO Wizard) ─────────────────────────────────────────
          Quem já agiu e o quê, na ordem de ação, terminando em "você". Ele responde de cabeça a
          pergunta que o jogador faria olhando o trilho ("quem abriu? quanto?") sem obrigá-lo a
          varrer nove assentos procurando fichas.
          Derivado do MESMO `seats` do servidor: `folded` é fold, `bet` acima do blind é aumento,
          e o herói é sempre o último, porque a vez é dele. */}
      <div className="absolute inset-x-0 top-0 flex flex-wrap items-center justify-center gap-1"
           style={{ fontSize: M.fHist }} data-testid="historico-da-mao">
        {historico(seats, hero, fmt, bb).map((h, i) => (
          <span key={i}
                className={cn("inline-flex items-center gap-1 rounded px-1 py-0.5 font-mono uppercase tracking-wide",
                              h.vez
                                ? "bg-primary/15 text-primary ring-1 ring-primary/40"
                                : h.fold
                                  ? "bg-hud-surface text-muted-foreground/60"
                                  : "bg-hud-surface text-foreground/90")}>
            <span className="font-bold">{h.pos}</span>
            <span>{h.texto}</span>
          </span>
        ))}
      </div>

      {/* O trilho: linha fina, sem preenchimento. Os assentos ficam SOBRE ela. */}
      {/* O trilho e uma ELIPSE (`50%`), e nao um estadio (`rounded-full`), porque as posicoes
          dos assentos sao calculadas por `naElipse`: com o trilho em estadio e os assentos em
          elipse, os das pontas sairiam da linha. Uma forma, uma conta. */}
      {/* `border-2` e a cor cheia: a borda fina de 1px desaparecia contra o fundo escuro, e o
          dono pediu para engrossar. Ela e o unico tracco que define a mesa -- sem feltro
          preenchido, se ela nao le, nao ha mesa. */}
      <div className="absolute rounded-[50%] border-2 border-border"
           style={{ top: INSET.y, bottom: INSET.y, left: INSET.x, right: INSET.x }} />

      {/* ── O centro do trilho: o spot ANTES de responder, o veredito DEPOIS ────────────────
          O dono, sobre o card de feedback do GTO Wizard: "podiamos mostrar no centro da mesa".
          Ele está certo, e o motivo é geométrico: o centro é o único espaço grande e vazio que a
          mesa tem, e depois da resposta o spot já não precisa ser lido -- o jogador acabou de
          decidir sobre ele. Uma área, dois momentos.

          E o veredito aqui é melhor que o veredito no rodapé do card: o olho já está no centro,
          onde ele acabou de olhar o pote para decidir. */}
      <div className="absolute left-1/2 top-1/2 w-[52%] -translate-x-1/2 -translate-y-1/2 text-center">
        {veredito ?? (
          <>
            {spot && (
              <span className="mb-0.5 block leading-snug text-muted-foreground"
                    style={{ fontSize: M.fSpot }}>
                {spot}
              </span>
            )}
            <span className="block font-mono font-bold leading-tight tabular-nums text-foreground"
                  style={{ fontSize: M.fPote }}>
              {fmt(table.pot ?? 0)}
              <span className="ml-0.5 font-normal text-muted-foreground">
                {unidade === "bb" ? "bb" : ""}
              </span>
            </span>
            <span className="block font-mono uppercase tracking-widest-2 text-muted-foreground/60"
                  style={{ fontSize: M.fHist }}>
              {naMao} na mao
            </span>
          </>
        )}
      </div>

      {/* ── As fichas, DENTRO da mesa (pedido do dono) ─────────────────────────────────────
          Camada propria, e nao penduradas no assento: a posicao de cada uma sai de `FICHAS`, que
          e a MESMA elipse dos assentos com raio menor. Assim ela fica na direcao de quem apostou
          e claramente dentro do trilho, e mover o trilho move as duas coisas juntas. */}
      {seats.filter((s) => s.bet > 0).map((s) => {
        const [fx, fy] = FICHAS[(s.seat - 1) % 9];
        return (
          <span key={`ficha-${s.seat}`} data-testid={`aposta-${s.pos || s.seat}`}
                className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1 whitespace-nowrap"
                style={{ left: `${fx}%`, top: `${fy}%` }}>
            <i className="rounded-full bg-[#4A9BE8]"
               style={{ width: M.ficha, height: M.ficha }} />
            <span className="font-mono font-bold tabular-nums text-foreground"
                  style={{ fontSize: M.fFicha }}>
              {fmt(s.bet)}
            </span>
          </span>
        );
      })}

      {seats.map((s) => {
        const [x, y] = LUGARES[(s.seat - 1) % 9];
        const ehHeroi = s.hero || s.name === hero;
        const fora = s.folded || !s.active;
        return (
          <div key={s.seat} data-testid={`assento-${s.pos || s.seat}`}
               className="absolute -translate-x-1/2 -translate-y-1/2"
               style={{ left: `${x}%`, top: `${y}%` }}>
            <div className="relative flex items-center gap-1">
              {/* o assento: círculo com posição e stack DENTRO */}
              <div style={{ width: M.assento, height: M.assento }}
                   className={cn(
                     "flex flex-col items-center justify-center rounded-full border text-center leading-none",
                     fora
                       ? "border-border/40 bg-transparent opacity-35"
                       : ehHeroi
                         ? "border-primary bg-hud-surface"
                         : "border-border bg-hud-surface",
                   )}>
                <span className={cn("font-mono uppercase tracking-tight",
                                    ehHeroi ? "text-primary" : "text-muted-foreground")}
                      style={{ fontSize: M.fPos }}>
                  {s.pos || s.seat}
                </span>
                <span className="font-mono font-bold tabular-nums text-foreground"
                      style={{ fontSize: M.fStack }}>
                  {fora ? "\u2014" : fmt(s.stack)}
                </span>
              </div>

              {/* As cartas DELE, ao lado do assento: onde o olho já está. */}
              {ehHeroi && cartas.length === 2 && (
                <span className="flex gap-0.5" data-testid="cartas-do-heroi">
                  {/* Rank grande E o SÍMBOLO do naipe. O dono, vendo a versão só com cor: "as
                      cartas agora estao ruins, pq ja nao sei qual o naipe delas".
                      A cor sozinha é o que o GTO Wizard faz, e funciona lá porque o jogador
                      deles já decorou o código. Aqui ela seria um enigma -- e sem o naipe o
                      jogador não sabe se a mão é SUITED, que é metade da decisão preflop.
                      A cor fica (ela lê de longe) e o símbolo resolve de perto. */}
                  {cartas.map(([r, n], i) => (
                    <span key={i}
                          className="relative flex flex-col items-center justify-center rounded font-mono font-bold leading-none"
                          style={{ background: NAIPE[n]?.bg, color: NAIPE[n]?.fg,
                                   width: M.cartaW, height: M.cartaH }}>
                      <span style={{ fontSize: M.fCarta }}>{r}</span>
                      <span style={{ fontSize: M.fNaipe }} className="opacity-90">
                        {SIMBOLO[n]}
                      </span>
                    </span>
                  ))}
                </span>
              )}

              {/* o botão do dealer */}
              {table.button === s.seat && (
                <span data-testid="botao-dealer"
                      className="absolute -bottom-0.5 -left-1 flex size-3.5 items-center justify-center
                                 rounded-full bg-[#E3E8EC] font-mono text-[7px] font-bold text-[#0A0E1A]">
                  D
                </span>
              )}
            </div>

            {/* A ficha saiu daqui: ela tem posição PRÓPRIA na mesa, e não um deslocamento a
                partir do assento. Pendurada no assento, ela herdava a posição dele -- e como os
                assentos ficavam fora do trilho, ela ia para fora da mesa. */}
          </div>
        );
      })}
    </div>
  );
}
