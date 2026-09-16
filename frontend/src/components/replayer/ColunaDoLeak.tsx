import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { X, ListOrdered, ChevronRight, ChevronDown } from "lucide-react";
import { metrics, type EvLeak, type LeakHands } from "@/lib/api";
import { HeroHand } from "@/components/PlayingCard";
import { cn, formatAction } from "@/lib/utils";
import { chaveDoLeak, mesmoLeak, type LeakSpot } from "@/lib/playlistDoLeak";

/**
 * A coluna com as mãos do leak, ao lado da mesa do replayer.
 *
 * ── Por que ela pode existir, se tiramos o aside em 20/06 ─────────────────────────────────────
 *
 * Aquele aside era FIXO, de 288px, e reservava a largura mesmo sem nada a mostrar: a mesa
 * encolhia sempre, em toda mão, para um painel que às vezes estava vazio. O commit que o removeu
 * estava certo.
 *
 * Esta coluna é outra coisa: ela só existe quando há playlist de leak (`?leak=` na URL), fica
 * sobreposta no espaço que a mesa JÁ não usa, e a mesa não muda de tamanho. O dono mediu na tela
 * dele: a mesa é um oval centrado de ~1050px numa janela de 1900px, com ~400px ociosos de cada
 * lado. Eu tinha dito que não havia espaço, olhando o commit em vez da tela.
 *
 * `hidden lg:flex`: no telefone não existe espaço ocioso, então lá a coluna não aparece e a
 * navegação é pelas setas, que é o que a playlist já resolve.
 *
 * ── Painel lateral, e não janela flutuante (16/09, pedido do dono) ────────────────────────────
 *
 * A primeira versão era `absolute` sobre o feltro, para não repetir o aside de 288px que tiramos
 * em 20/06 — aquele reservava largura em TODA mão, mesmo sem nada a mostrar. O dono pediu menu
 * lateral com toggle, e a diferença que torna isso seguro é exatamente o toggle: recolhido, o
 * painel vira uma aba de 36px e devolve a largura para a mesa, e ele só existe com `?leak=`.
 * O guarda desta suíte protege isso, e não mais a flutuação.
 *
 * ── Dois níveis de navegação (16/09, pedido do dono) ──────────────────────────────────────────
 *
 * Dentro de um leak, as mãos; entre leaks, a lista do dashboard. O cabeçalho diz QUAL leak está
 * aberto e em que posição da lista ("leak 2 de 5"), e o botão avança para o próximo. A lista de
 * leaks é a MESMA do card (`evSummary().top_leaks`), com o mesmo recorte, então "2 de 5" aqui é
 * a mesma ordem que o jogador viu lá.
 *
 * Trocar de leak precisa de uma chamada extra: a playlist do próximo leak é outra lista de mãos,
 * e o replayer abre por MÃO. Então o botão busca a primeira mão daquele leak (a mais cara, que é
 * a ordem da lista) e navega para ela.
 */
export function ColunaDoLeak({ spot, lastN, handId, hrefDaMao, hrefEmOutroLeak, aoIr }: {
  spot: LeakSpot;
  lastN?: number;
  /** a mão aberta agora, para destacar a linha e apagar as anteriores */
  handId: string;
  hrefDaMao: (h: string) => string;
  /** o link para uma mão de OUTRO leak: quem monta é o Replayer, que tem o contexto (aluno,
   *  modo coach, filtro). Sem isso a coluna montaria URL por conta própria e seria a segunda
   *  forma de fazer a mesma coisa. */
  hrefEmOutroLeak: (mao: string, tournamentId: number, leakChave: string) => string;
  aoIr: (href: string) => void;
}) {
  const { t } = useTranslation("replayer");
  const [dados, setDados] = useState<LeakHands | null>(null);
  const [leaks, setLeaks] = useState<EvLeak[]>([]);
  const [menu, setMenu] = useState(false);
  const [trocando, setTrocando] = useState(false);
  const [aberta, setAberta] = useState<boolean>(
    () => localStorage.getItem("replayer_coluna_leak") !== "false");

  useEffect(() => {
    let vivo = true;
    metrics.evLeakHands(spot.street, spot.actionTaken, spot.bestAction, lastN, 200)
      .then((d) => { if (vivo) setDados(d); })
      .catch(() => { /* a coluna simplesmente não aparece; as setas seguem funcionando */ });
    return () => { vivo = false; };
  }, [spot.street, spot.actionTaken, spot.bestAction, lastN]);

  // A lista de leaks do CARD, com o mesmo recorte: é ela que dá o "2 de 5" e o próximo.
  useEffect(() => {
    let vivo = true;
    metrics.evSummary(lastN)
      .then((d) => { if (vivo) setLeaks(d.top_leaks ?? []); })
      .catch(() => { /* sem a lista, a coluna segue servindo as mãos deste leak */ });
    return () => { vivo = false; };
  }, [lastN]);

  const alterna = (v: boolean) => {
    setAberta(v);
    localStorage.setItem("replayer_coluna_leak", String(v));
  };

  /** Abre outro leak na sua PRIMEIRA mão (a mais cara, que é a ordem da lista). */
  const irParaLeak = async (l: EvLeak) => {
    setTrocando(true);
    try {
      const d = await metrics.evLeakHands(l.street, l.action_taken, l.best_action, lastN, 1);
      const primeira = d.hands?.[0];
      // Leak sem mão medida não navega para lugar nenhum: melhor não sair da tela do que cair
      // num replayer vazio. O menu continua aberto para o jogador escolher outro.
      if (primeira) {
        setMenu(false);
        aoIr(hrefEmOutroLeak(primeira.hand_id, primeira.tournament_id, chaveDoLeak(l)));
      }
    } catch {
      /* mantém a tela como está */
    } finally {
      setTrocando(false);
    }
  };

  if (!dados || !dados.hands.length) return null;

  const idx = dados.hands.findIndex((m) => m.hand_id === handId);
  // Onde este leak esta na lista do card, e qual e o proximo. `-1` quando a lista ainda nao
  // chegou ou quando o leak da URL nao esta entre os do recorte: ai o cabecalho cai no rotulo
  // simples em vez de dizer "leak 0 de 5".
  const iLeak = leaks.findIndex((l) => mesmoLeak(spot, l));
  const proximo = iLeak >= 0 && iLeak + 1 < leaks.length ? leaks[iLeak + 1] : null;

  if (!aberta) {
    // Recolhida, o painel NAO desaparece: sobra a aba de 36px, que devolve a largura para a mesa
    // e continua dizendo quantas mãos esperam. Pastilha flutuante sobre o feltro era o desenho
    // anterior, e o dono pediu menu lateral com toggle.
    return (
      <aside
        data-testid="leak-coluna-fechada"
        className="hidden lg:flex w-9 shrink-0 flex-col items-center gap-2 border-r border-border bg-hud-surface/40 py-3"
      >
        <button
          type="button"
          onClick={() => alterna(true)}
          data-testid="leak-coluna-abrir"
          title={t("navigation.leakColunaAbrir", { n: dados.total })}
          aria-label={t("navigation.leakColunaAbrir", { n: dados.total })}
          className="flex flex-col items-center gap-1.5 text-primary transition-colors hover:text-primary-glow"
        >
          <ListOrdered className="size-4" aria-hidden />
          <span className="font-mono text-[10px] font-bold tabular-nums">{dados.total}</span>
        </button>
        {/* o rótulo na vertical, para a aba dizer o que é sem roubar largura */}
        <span
          className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground"
          style={{ writingMode: "vertical-rl" }}
        >
          {t("navigation.leakColunaAba")}
        </span>
      </aside>
    );
  }

  return (
    <aside
      data-testid="leak-coluna"
      className="hidden lg:flex w-[clamp(150px,12vw,190px)] shrink-0 flex-col overflow-hidden border-r border-border bg-hud-surface/60"
    >
      {/* QUAL leak, e onde ele está na lista do dashboard */}
      <div className="flex items-start justify-between gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => setMenu((v) => !v)}
            disabled={leaks.length < 2}
            data-testid="leak-menu-toggle"
            className="flex w-full items-center gap-1.5 text-left disabled:cursor-default"
          >
            {/* Duas linhas, porque em 150px "CALL -> FOLD preflop" nao cabe numa: o nome do leak
                e a informacao que o dono pediu para ver, entao ele quebra em vez de ser cortado. */}
            <span className="min-w-0 flex-1 text-[11px] font-bold leading-tight">
              <span className="font-mono uppercase">{formatAction(spot.actionTaken)}</span>
              <span className="text-muted-foreground"> → </span>
              <span className="font-mono uppercase text-primary">{formatAction(spot.bestAction)}</span>
              <span className="block font-mono text-[9px] font-normal text-muted-foreground">{spot.street}</span>
            </span>
            {leaks.length >= 2 && (
              <ChevronDown className={cn("size-3 shrink-0 text-muted-foreground transition-transform",
                                        menu && "rotate-180")} aria-hidden />
            )}
          </button>
          <span className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
            {iLeak >= 0 && leaks.length
              ? t("navigation.leakDeN", { i: iLeak + 1, n: leaks.length, maos: dados.total })
              : t("navigation.leakColuna", { n: dados.total })}
          </span>
        </div>
        <button
          type="button"
          onClick={() => alterna(false)}
          aria-label={t("close")}
          className="mt-0.5 shrink-0 text-muted-foreground transition-colors hover:text-foreground"
        >
          <X className="size-3.5" />
        </button>
      </div>

      {/* O menu: a MESMA lista do card, na mesma ordem */}
      {menu && (
        <div className="border-b border-border bg-hud-elevated/40" data-testid="leak-menu">
          {leaks.map((l, i) => {
            const aberto = mesmoLeak(spot, l);
            return (
              <button
                key={`${l.street}:${l.action_taken}:${l.best_action}`}
                type="button"
                disabled={trocando || aberto}
                onClick={() => irParaLeak(l)}
                data-testid={`leak-menu-${i}`}
                className={cn(
                  "flex w-full items-center gap-2 border-b border-border/40 px-3 py-1.5 text-left text-[11px] transition-colors last:border-b-0",
                  aberto ? "bg-primary/[0.08] text-foreground" : "text-muted-foreground hover:bg-secondary/40",
                )}
              >
                <span className="w-3 shrink-0 font-mono text-[9px] text-muted-foreground/60">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[10px]"
                      title={`${formatAction(l.action_taken)} → ${formatAction(l.best_action)} · ${l.street} · ${l.count} spots`}>
                  {formatAction(l.action_taken)} → {formatAction(l.best_action)}
                </span>
                <span className="shrink-0 font-mono text-[10px] tabular-nums text-red-400">
                  −{l.loss_bb.toFixed(1)}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {dados.hands.map((m, i) => {
          const atual = m.hand_id === handId;
          return (
            <button
              key={m.decision_id}
              type="button"
              onClick={() => aoIr(hrefDaMao(m.hand_id))}
              data-testid={`leak-coluna-mao-${m.decision_id}`}
              title={`${m.hero_cards ?? "?"} · ${m.position ?? "?"}`
                     + (m.stack_bb != null ? ` · ${Math.round(m.stack_bb)}bb` : "")
                     + ` · −${m.ev_loss_bb.toFixed(2)}bb`}
              aria-current={atual ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-2.5 border-b border-border/50 px-3 py-2 text-left transition-colors last:border-b-0",
                atual ? "bg-primary/[0.09] shadow-[inset_2px_0_0_hsl(var(--primary))]" : "hover:bg-secondary/40",
                // apagado = já revisto. A ordem da lista é por custo, então "antes" é "mais caro
                // que este", e é essa a ordem em que o jogador desce.
                !atual && idx >= 0 && i < idx && "opacity-45",
              )}
            >
              {/* So CARTAS e CUSTO (16/09, decisao do dono): a coluna cobria o assento do BB na
                  mesa, e assento e stack ja estao NA MESA com a mao aberta -- na lista eram
                  repeticao ocupando a largura que faltava. Seguem no title. */}
              <HeroHand cards={m.hero_cards} />
              <span className="flex-1" />
              <span className="font-mono text-[10px] tabular-nums text-red-400">
                −{m.ev_loss_bb.toFixed(2)}
              </span>
            </button>
          );
        })}
      </div>

      {/* Empilhado, nao lado a lado: em 150px os dois na mesma linha se cortavam. */}
      <div className="flex flex-col gap-1 border-t border-border px-3 py-1.5">
        <span className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
          {t("navigation.leakColunaPe", {
            i: idx >= 0 ? idx + 1 : "—", n: dados.total, bb: dados.loss_bb.toFixed(1),
          })}
        </span>
        {/* Avancar para o PROXIMO leak da lista. Some no ultimo, em vez de ficar apagado: botao
            que nao faz nada ensina o jogador a nao confiar no botao. */}
        {proximo && (
          <button
            type="button"
            disabled={trocando}
            onClick={() => irParaLeak(proximo)}
            data-testid="leak-proximo"
            className="inline-flex shrink-0 items-center gap-1 font-mono text-[9px] font-bold uppercase tracking-widest-2 text-primary transition-colors hover:text-primary-glow disabled:opacity-40"
          >
            {t("navigation.leakProximo")}
            <ChevronRight className="size-3" aria-hidden />
          </button>
        )}
      </div>
    </aside>
  );
}
