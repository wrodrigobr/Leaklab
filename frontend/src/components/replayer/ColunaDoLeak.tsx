import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { X, ListOrdered } from "lucide-react";
import { metrics, type LeakHands } from "@/lib/api";
import { HeroHand } from "@/components/PlayingCard";
import { cn } from "@/lib/utils";
import type { LeakSpot } from "@/lib/playlistDoLeak";

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
 */
export function ColunaDoLeak({ spot, lastN, handId, hrefDaMao, aoIr }: {
  spot: LeakSpot;
  lastN?: number;
  /** a mão aberta agora, para destacar a linha e apagar as anteriores */
  handId: string;
  hrefDaMao: (h: string) => string;
  aoIr: (href: string) => void;
}) {
  const { t } = useTranslation("replayer");
  const [dados, setDados] = useState<LeakHands | null>(null);
  const [aberta, setAberta] = useState<boolean>(
    () => localStorage.getItem("replayer_coluna_leak") !== "false");

  useEffect(() => {
    let vivo = true;
    metrics.evLeakHands(spot.street, spot.actionTaken, spot.bestAction, lastN, 200)
      .then((d) => { if (vivo) setDados(d); })
      .catch(() => { /* a coluna simplesmente não aparece; as setas seguem funcionando */ });
    return () => { vivo = false; };
  }, [spot.street, spot.actionTaken, spot.bestAction, lastN]);

  const alterna = (v: boolean) => {
    setAberta(v);
    localStorage.setItem("replayer_coluna_leak", String(v));
  };

  if (!dados || !dados.hands.length) return null;

  const idx = dados.hands.findIndex((m) => m.hand_id === handId);

  if (!aberta) {
    return (
      <button
        type="button"
        onClick={() => alterna(true)}
        data-testid="leak-coluna-abrir"
        className="hidden lg:inline-flex absolute right-2 top-2 z-20 items-center gap-1.5 rounded-full bg-background/80 backdrop-blur px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary ring-1 ring-primary/40 transition-colors hover:bg-primary/10"
      >
        <ListOrdered className="size-3.5" aria-hidden />
        {t("navigation.leakColunaAbrir", { n: dados.total })}
      </button>
    );
  }

  return (
    <aside
      data-testid="leak-coluna"
      className="hidden lg:flex absolute right-0 top-0 z-20 w-[clamp(240px,22vw,300px)] max-h-full flex-col overflow-hidden rounded-xl border border-border bg-hud-surface/95 backdrop-blur"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
          {t("navigation.leakColuna", { n: dados.total })}
        </span>
        <button
          type="button"
          onClick={() => alterna(false)}
          aria-label={t("close")}
          className="text-muted-foreground transition-colors hover:text-foreground"
        >
          <X className="size-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {dados.hands.map((m, i) => {
          const atual = m.hand_id === handId;
          return (
            <button
              key={m.decision_id}
              type="button"
              onClick={() => aoIr(hrefDaMao(m.hand_id))}
              data-testid={`leak-coluna-mao-${m.decision_id}`}
              aria-current={atual ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-2.5 border-b border-border/50 px-3 py-2 text-left transition-colors last:border-b-0",
                atual ? "bg-primary/[0.09] shadow-[inset_2px_0_0_hsl(var(--primary))]" : "hover:bg-secondary/40",
                // apagado = já revisto. A ordem da lista é por custo, então "antes" é "mais caro
                // que este", e é essa a ordem em que o jogador desce.
                !atual && idx >= 0 && i < idx && "opacity-45",
              )}
            >
              <HeroHand cards={m.hero_cards} />
              <span className="min-w-0 flex-1 truncate font-mono text-[9px] text-muted-foreground">
                {m.position ?? "—"}
                {m.stack_bb != null ? ` · ${Math.round(m.stack_bb)}bb` : ""}
              </span>
              <span className="font-mono text-[10px] tabular-nums text-red-400">
                −{m.ev_loss_bb.toFixed(2)}
              </span>
            </button>
          );
        })}
      </div>

      <div className="border-t border-border px-3 py-1.5 font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">
        {t("navigation.leakColunaPe", {
          i: idx >= 0 ? idx + 1 : "—", n: dados.total, bb: dados.loss_bb.toFixed(1),
        })}
      </div>
    </aside>
  );
}
