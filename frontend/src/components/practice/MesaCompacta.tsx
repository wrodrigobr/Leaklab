import { useEffect, useRef, useState } from "react";
import type { DrillTableState } from "@/lib/api";
import type { Unidade } from "@/lib/pratica";
import { cn } from "@/lib/utils";
import { layoutDaMesa, px } from "./geometriaDaMesa";

/**
 * A mesa do modo Prática: um estádio, assentos redondos e nada mais.
 *
 * ── Por que ela existe, se já temos a `PokerTableV3` ──────────────────────────────────────────
 *
 * O dono, vendo quatro mesas: "ja esta ficando pequeno enxergar as fichas...talvez fazer como o
 * gto wizard faz, com mesas simples, mas funcionais", e depois mandou a captura deles.
 *
 * A `PokerTableV3` é a mesa do replayer, e desenha o que o replayer precisa: duas cartas viradas
 * por vilão, nome do jogador, HUD, board, showdown e a marca no feltro. A um quarto de tela isso
 * não encolhe bem, e pior: no preflop **nada disso informa**. O jogador nunca vê carta de vilão, o
 * nome é anonimizado, não há board e não há HUD num spot sintético. O que decide a jogada é
 * posição, stack, o que está na mesa e as cartas DELE.
 *
 * ── Como ela se posiciona (reescrita em 17/09) ────────────────────────────────────────────────
 *
 * Ela MEDE o próprio tamanho e chama `layoutDaMesa`, que devolve a caixa de cada elemento em px.
 * Antes as posições saíam em `%` com `calc()` e as medidas em `clamp()` com `cqw`/`cqh`, o que
 * obrigava cada regra do desenho a existir DUAS vezes: uma para o navegador e uma para o medidor
 * de colisão. A mesa passou por cinco desenhos num dia, e cada um custava as duas escritas mais um
 * teste provando que elas concordavam. Agora há uma conta só, e o medidor mede o que o jogador vê.
 *
 * ── E por que isto NÃO é uma segunda fonte de verdade ─────────────────────────────────────────
 *
 * A regra 5 da casa fala de REGRA, e aqui nenhuma é duplicada: quem está na mão, quem apostou
 * quanto, onde fica o botão e qual o pote vêm todos do MESMO `table` que o servidor monta em
 * `pratica_preflop.mesa_do_spot`. Isto é desenho, e desenho diferente para uso diferente é o
 * oposto de duplicar a verdade. A `PokerTableV3` do replayer não mudou uma linha.
 */

/**
 * Baralho de 4 cores: a cor do quadrado É o naipe, e ela lê de longe melhor que o símbolo.
 *
 * ── Por que os tons NÃO são os da paleta de ação ──────────────────────────────────────────────
 *
 * A primeira versão usou o verde do call e o azul do fold para clubs e diamonds, e o guarda de
 * `actionColors` acusou -- com razão. Naipe e ação são dois vocabulários de cor no mesmo produto,
 * e nesta tela eles aparecem LADO A LADO: o botão verde ao lado de uma carta verde ensinaria que
 * aquela carta tem a ver com "call".
 *
 * Então os quatro naipes têm tons próprios, próximos o bastante para o jogador reconhecer o
 * baralho de 4 cores e distintos o bastante para nenhum deles ser a cor de uma ação.
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

/**
 * ── Os três estados que o pod precisa distinguir ──────────────────────────────────────────────
 *
 * O dono, vendo a mesa: "falta deixar mais evidente quem ainda está na mão, de quem é a vez, e
 * quem já foldou", e depois, mais direto: "quem está na mão está parecendo tao oculto quanto quem
 * foldou".
 *
 * Ele está certo, e o número é contundente. Medido pela razão de contraste sobre o feltro: a borda
 * de quem estava na mão rendia **1,19** e a de quem saiu **1,10**. Diferença de 0,09 -- os dois
 * usavam o MESMO token (`border`, 14% de luminosidade sobre um fundo de 7%), e a única diferença
 * era a opacidade. Não era sutil, era invisível.
 *
 * Agora, medido: a borda de quem está na mão rende 3,85 (3,4x a de quem saiu), a posição 7,7 contra
 * 3,0, e o stack 14,8 contra 4,1. A borda escolhida é `muted-foreground` e não `prose-fg`, que
 * renderia 6,25 -- aí o pod de quem está na mão passaria a competir com o de quem tem a vez.
 *
 * ── O limite que este conserto tem de respeitar ───────────────────────────────────────────────
 *
 * Ele já reclamou do CONTRÁRIO: "quando os assentos nao estao na mao, estamos ocultando muito o
 * pod, e quase nao da pra ver". Então a diferença NÃO pode vir de apagar mais quem foldou -- isso
 * seria consertar um pedido reabrindo o outro. Ela vem de dar PESO a quem está na mão e a quem
 * joga: borda de 2px e fundo elevado para quem ficou, anel e tinta da cor da ação para a vez.
 * Quem saiu perde o peso, não a legibilidade: continua com fundo, borda, posição e stack.
 *
 * Neste modo o herói É quem tem a vez -- o servidor monta o spot na decisão dele. Se ele aparecer
 * fora da mão, "fora" manda: quem saiu não tem vez, e a ordem aqui diz isso.
 */
export type EstadoDoAssento = "vez" | "naMao" | "fora";

export function estadoDoAssento(
  s: { folded?: boolean; active?: boolean; hero?: boolean; name?: string },
  hero: string,
): EstadoDoAssento {
  if (s.folded || !s.active) return "fora";
  return s.hero || s.name === hero ? "vez" : "naMao";
}

/**
 * O peso de cada estado, em três degraus.
 *
 * `border-2` nos dois primeiros e `border` no terceiro é de propósito: a ESPESSURA lê num pod de
 * 47px onde a diferença de tom não lê. O anel do "vez" é `ring-1` e não `ring-2` porque o anel
 * cresce para fora da caixa que o medidor conhece, e a carta do herói encosta a 10px dali.
 */
export const PESO_DO_ASSENTO: Record<EstadoDoAssento, {
  caixa: string; pos: string; stack: string;
}> = {
  vez: {
    caixa: "border-2 border-primary bg-primary/15 ring-1 ring-primary/40",
    pos: "text-primary",
    stack: "text-foreground",
  },
  naMao: {
    caixa: "border-2 border-muted-foreground bg-hud-elevated",
    pos: "text-foreground/80",
    stack: "text-foreground",
  },
  // O texto de quem saiu ficou IGUAL ao que era: a separacao vem de subir o peso de quem esta na
  // mao, e nao de baixar o de quem saiu. Baixar reabriria o pedido anterior dele.
  fora: {
    caixa: "border border-border/70 bg-hud-surface/70",
    pos: "text-muted-foreground/80",
    stack: "text-muted-foreground",
  },
};

export function MesaCompacta({ table, hero, unidade, spot, veredito }: {
  table: DrillTableState;
  /** o nome do herói no `table.seats` (o servidor manda "Hero") */
  hero: string;
  /** o spot em uma frase, do servidor. Vai no CENTRO da mesa, como no GTO Wizard. */
  spot?: string;
  /** O card de veredito, que OCUPA o centro depois da resposta e esconde o spot. Quem monta é a
   *  `MesaDePratica`: o veredito nasce da correção do servidor, e a mesa não conhece a régua. */
  veredito?: React.ReactNode;
  unidade: Unidade;
}) {
  const bb = table.bb_chips || 1;
  const seats = [...(table.seats ?? [])].sort((a, b) => a.seat - b.seat);
  const cartas = lerCartas(table.hero_cards);
  const naMao = seats.filter((s) => !s.folded && s.active).length;

  /** Fichas na unidade escolhida. UMA função para stack e aposta: dois formatadores é como a mesa
   *  acaba mostrando a mesma grandeza de dois jeitos (a cicatriz "fichas vs BB"). */
  const fmt = (chips: number) => {
    if (unidade === "bb") {
      // Uma decimal quando não for inteiro, como o GTO Wizard faz ("39.5"): arredondar 17.8 para
      // 18 apagava o desconto da aposta, e o stack DEPOIS de pôr fichas é o que decide o próximo
      // movimento.
      const v = Math.round((chips / bb) * 10) / 10;
      return Number.isInteger(v) ? String(v) : v.toFixed(1);
    }
    return Math.round(chips).toLocaleString("pt-BR");
  };

  // ── A medição ─────────────────────────────────────────────────────────────────────────────
  //
  // O `ResizeObserver` existe porque o layout é calculado em px: sem medir, a mesa não sabe se
  // está num quarto de tela ou num celular em retrato -- e é o aspecto do espaço que decide se o
  // estádio fica horizontal ou vertical, que foi o que o dono pediu mandando a captura do GTO
  // Wizard em tela estreita ("e se reduzir muito, ele vira pra celular").
  //
  // O tamanho inicial NÃO é zero: com 0x0 o primeiro render posicionaria tudo no canto e a mesa
  // piscaria montada errada antes da primeira medição. O palpite é um quarto de tela cheia, o
  // caso mais comum, e ele é corrigido assim que o observer dispara.
  const caixaRef = useRef<HTMLDivElement | null>(null);
  const [tamanho, setTamanho] = useState({ w: 830, h: 440 });
  useEffect(() => {
    const el = caixaRef.current;
    if (!el) return;
    const medir = () => {
      const r = el.getBoundingClientRect();
      // O jsdom devolve 0x0 (ele não faz layout): manter o palpite deixa os testes medindo uma
      // mesa plausível em vez de uma de tamanho zero.
      if (r.width > 1 && r.height > 1) setTamanho({ w: r.width, h: r.height });
    };
    medir();
    if (typeof ResizeObserver === "undefined") return;
    const obs = new ResizeObserver(medir);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const indice = (seat: number) => (seat - 1) % 9;
  const heroiSeat = seats.find((s) => s.hero || s.name === hero);
  const L = layoutDaMesa({
    w: tamanho.w,
    h: tamanho.h,
    heroi: heroiSeat && cartas.length === 2 ? indice(heroiSeat.seat) : -1,
    botao: table.button ? indice(table.button) : -1,
    apostas: seats.filter((s) => s.bet > 0).map((s) => ({ i: indice(s.seat), texto: fmt(s.bet) })),
    centro: true,
  });
  const M = {
    fPos: px("fPos", tamanho.w, tamanho.h),
    fStack: px("fStack", tamanho.w, tamanho.h),
    fCarta: px("fCarta", tamanho.w, tamanho.h),
    fNaipe: px("fNaipe", tamanho.w, tamanho.h),
    fSpot: px("fSpot", tamanho.w, tamanho.h),
    fPote: px("fPote", tamanho.w, tamanho.h),
    fFicha: px("fFicha", tamanho.w, tamanho.h),
    ficha: px("ficha", tamanho.w, tamanho.h),
    fLegenda: px("fLegenda", tamanho.w, tamanho.h),
    fDealer: px("fDealer", tamanho.w, tamanho.h),
  };
  const caixa = (c: { x: number; y: number; w: number; h: number }): React.CSSProperties => ({
    position: "absolute",
    left: c.x,
    top: c.y,
    width: c.w,
    height: c.h,
  });

  return (
    <div ref={caixaRef} className="relative h-full w-full" data-testid="mesa-compacta">
      {/* ── O contorno: um ESTÁDIO ──────────────────────────────────────────────────────────
          O dono, com a captura deles: "ideal e que as bordas superiores e inferiores da mesa
          fiquem retas, e so curvemos as laterais...assim ganhamos espaco". Ganha porque os
          assentos de uma reta ficam todos na MESMA altura, em vez de descerem com a curva.

          `rounded-full` num retângulo é o estádio, e as retas caem no eixo maior -- então a mesma
          borda serve para a mesa horizontal (desktop) e para a vertical (celular). As posições dos
          assentos andam por ESTE contorno: uma forma, uma conta. */}
      <div className="rounded-full border-2 border-border" style={caixa(L.arena)}
           data-testid="arena-da-mesa" />

      {/* ── O centro: o spot ANTES de responder, o veredito DEPOIS ──────────────────────────
          O centro é o único espaço grande e vazio da mesa, e depois da resposta o spot já não
          precisa ser lido -- o jogador acabou de decidir sobre ele. Uma área, dois momentos. */}
      {L.centro && (
        <div className="flex flex-col items-center justify-center text-center"
             style={caixa(L.centro)}>
          {veredito ?? (
            <>
              {spot && (
                <span className="block leading-snug text-muted-foreground"
                      style={{ fontSize: M.fSpot }}>{spot}</span>
              )}
              <span className="block font-mono font-bold leading-tight tabular-nums text-foreground"
                    style={{ fontSize: M.fPote }}>
                {fmt(table.pot ?? 0)}
                <span className="ml-0.5 font-normal text-muted-foreground">
                  {unidade === "bb" ? "bb" : ""}
                </span>
              </span>
              <span className="block font-mono uppercase tracking-widest-2 text-muted-foreground/60"
                    style={{ fontSize: M.fLegenda }}>
                {naMao} na mao
              </span>
            </>
          )}
        </div>
      )}

      {/* ── As fichas de aposta, na frente de quem apostou ──────────────────────────────────
          Elas saem do pod pela NORMAL ao contorno: nas retas isso as deixa PARALELAS, cada uma na
          frente do seu dono. Pelo raio elas convergiam para o centro e se encostavam. */}
      {L.fichas.map(({ i, caixa: c }) => {
        const s = seats.find((x) => indice(x.seat) === i);
        if (!s) return null;
        return (
          <span key={`ficha-${s.seat}`} data-testid={`aposta-${s.pos || s.seat}`}
                className="flex items-center gap-1 whitespace-nowrap" style={caixa(c)}>
            <i className="shrink-0 rounded-full bg-[#4A9BE8]"
               style={{ width: M.ficha, height: M.ficha }} />
            <span className="font-mono font-bold leading-none tabular-nums text-foreground"
                  style={{ fontSize: M.fFicha }}>{fmt(s.bet)}</span>
          </span>
        );
      })}

      {/* ── As cartas DELE, para FORA do contorno ───────────────────────────────────────────
          Para fora, e não para dentro: o miolo já tem nove fichas e o texto do centro, e a margem
          da arena reserva a carta justamente para ela poder sair. Rank grande E o símbolo do
          naipe -- o dono, vendo a versão só com cor: "as cartas agora estao ruins, pq ja nao sei
          qual o naipe delas". A cor lê de longe, o símbolo resolve de perto. */}
      {L.cartas && cartas.length === 2 && (
        <span className="flex gap-0.5" style={caixa(L.cartas)} data-testid="cartas-do-heroi">
          {cartas.map(([r, n], i) => (
            <span key={i}
                  className="flex flex-1 flex-col items-center justify-center rounded font-mono font-bold leading-none"
                  style={{ background: NAIPE[n]?.bg, color: NAIPE[n]?.fg }}>
              <span style={{ fontSize: M.fCarta }}>{r}</span>
              <span style={{ fontSize: M.fNaipe }} className="opacity-90">{SIMBOLO[n]}</span>
            </span>
          ))}
        </span>
      )}

      {/* ── Os assentos ────────────────────────────────────────────────────────────────────
          Quem SAIU da mão continua legível: o dono relatou que "estamos ocultando muito o pod, e
          quase nao da pra ver...siga o mesmo padrao do gto wizard nisto tambem". No GTO Wizard o
          pod de quem saiu tem fundo, borda e stack legíveis, em cinza -- e não é estética: a
          posição que abriu antes de você e o stack que ela tinha ainda informam. */}
      {seats.map((s) => {
        const p = L.pods[indice(s.seat)];
        if (!p) return null;
        const estado = estadoDoAssento(s, hero);
        const peso = PESO_DO_ASSENTO[estado];
        return (
          <div key={s.seat} data-testid={`assento-${s.pos || s.seat}`}
               data-estado={estado}
               style={caixa(p.caixa)}
               className={cn(
                 "flex flex-col items-center justify-center rounded-full text-center leading-none",
                 peso.caixa,
               )}>
            <span className={cn("font-mono uppercase tracking-tight", peso.pos)}
                  style={{ fontSize: M.fPos }}>
              {s.pos || s.seat}
            </span>
            {/* O STACK de quem saiu APARECE, e não um traço: era o traço que fazia o pod parecer
                vazio. Só o peso muda. */}
            <span className={cn("font-mono font-bold tabular-nums", peso.stack)}
                  style={{ fontSize: M.fStack }}>
              {fmt(s.stack)}
            </span>
          </div>
        );
      })}

      {/* o botão do dealer, ENCOSTADO no pod (como no GTO Wizard) */}
      {L.dealer && (
        <span data-testid="botao-dealer" style={caixa(L.dealer)}
              className="flex items-center justify-center rounded-full bg-[#E3E8EC] font-mono font-bold text-[#0A0E1A]">
          <span style={{ fontSize: M.fDealer }}>D</span>
        </span>
      )}
    </div>
  );
}
