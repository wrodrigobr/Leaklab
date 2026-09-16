import { useTranslation } from "react-i18next";
import { RotateCw, SlidersHorizontal, X } from "lucide-react";
import {
  MAX_MESAS, NIVEIS, STACKS_DISPONIVEIS, type ConfigPratica, type Nivel, type Pausa,
  type StatsPratica,
} from "@/lib/pratica";
import { cn } from "@/lib/utils";

/**
 * O painel lateral: configura o treino SEM sair dele, e mostra o placar da sessão.
 *
 * ── A decisão que ele carrega ─────────────────────────────────────────────────────────────────
 *
 * Mexer em mesas, stack ou tipo de spot muda o SORTEIO, então entra na próxima rodada e o painel
 * diz isso onde a mudança acontece. No GTO Wizard trocar o número de mesas reinicia a sessão e
 * descarta o que o jogador já respondeu; aqui as mesas em jogo terminam com as regras com que
 * começaram. A régua de quem espera e quem aplica na hora é `mudaOSorteio`, em `lib/pratica`.
 *
 * ── Por que lateral, e recolhível ─────────────────────────────────────────────────────────────
 *
 * Mesmo motivo do painel do leak no replayer: com quatro mesas a largura é o recurso escasso.
 * Recolhido, sobra a aba de 36px e a grade recupera o espaço.
 */

const COR_DA_BARRA: Record<Nivel, string> = {
  melhor:     "bg-emerald-500",
  correta:    "bg-primary",
  imprecisao: "bg-amber-500",
  errada:     "bg-red-500",
  grave:      "bg-red-900",
};

export function PainelDePratica({
  aberto, config, pendente, stats, onConfig, onAlternar,
}: {
  aberto: boolean;
  /** o que está VALENDO nas mesas abertas */
  config: ConfigPratica;
  /** o que o jogador escolheu e entra na próxima rodada; `null` = nada pendente */
  pendente: ConfigPratica | null;
  stats: StatsPratica;
  onConfig: (c: ConfigPratica) => void;
  onAlternar: (v: boolean) => void;
}) {
  const { t } = useTranslation("practice");
  // O painel edita o PENDENTE quando há um, senão o que está valendo: sem isso, dois cliques
  // seguidos no painel fariam o segundo esquecer o primeiro.
  const atual = pendente ?? config;
  const muda = (p: Partial<ConfigPratica>) => onConfig({ ...atual, ...p });

  if (!aberto) {
    return (
      <aside data-testid="pratica-painel-fechado"
             className="hidden lg:flex w-9 shrink-0 flex-col items-center gap-2 border-r border-border bg-hud-surface/40 py-3">
        <button type="button" onClick={() => onAlternar(true)}
                data-testid="pratica-painel-abrir"
                aria-label={t("painel.abrir")} title={t("painel.abrir")}
                className="text-primary transition-colors hover:text-primary-glow">
          <SlidersHorizontal className="size-4" aria-hidden />
        </button>
        <span className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground"
              style={{ writingMode: "vertical-rl" }}>
          {t("painel.aba")}
        </span>
      </aside>
    );
  }

  return (
    <aside data-testid="pratica-painel"
           className="hidden lg:flex w-[clamp(180px,14vw,224px)] shrink-0 flex-col overflow-y-auto border-r border-border bg-hud-surface/60">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="font-mono text-[9.5px] uppercase tracking-widest-2 text-primary">
          {t("painel.titulo")}
        </span>
        <button type="button" onClick={() => onAlternar(false)} aria-label={t("painel.fechar")}
                className="text-muted-foreground transition-colors hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>

      {/* mesas */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.mesas")}</Rotulo>
        <div className="flex gap-1">
          {Array.from({ length: MAX_MESAS }, (_, i) => i + 1).map((n) => (
            <Seg key={n} on={atual.mesas === n} onClick={() => muda({ mesas: n })}
                 testid={`pratica-mesas-${n}`}>{n}</Seg>
          ))}
        </div>
        {pendente && (
          <div data-testid="pratica-pendente"
               className="mt-2 flex items-start gap-1.5 border-l-2 border-primary/50 bg-primary/[0.05] px-2 py-1.5">
            <RotateCw className="mt-px size-2.5 shrink-0 text-primary/80" aria-hidden />
            <span className="font-mono text-[9px] leading-relaxed text-primary/90">
              {t("painel.aplicaDepois")}
            </span>
          </div>
        )}
      </div>

      {/* stack efetivo */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.stack")}</Rotulo>
        <div className="flex flex-wrap gap-1">
          {STACKS_DISPONIVEIS.map((s) => {
            const on = atual.stacks.includes(s);
            return (
              <button key={s} type="button" data-testid={`pratica-stack-${s}`}
                      onClick={() => muda({
                        // Nunca deixa a lista vazia: sem stack nenhum o sorteio não tem de onde
                        // tirar mesa, e a tela ficaria pedindo mesas que nunca chegam.
                        stacks: on
                          ? (atual.stacks.length > 1 ? atual.stacks.filter((x) => x !== s) : atual.stacks)
                          : [...atual.stacks, s].sort((a, b) => a - b),
                      })}
                      className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors",
                        on ? "border-primary/45 bg-primary/10 text-primary"
                           : "border-border text-muted-foreground hover:text-foreground")}>
                {s}
              </button>
            );
          })}
        </div>
      </div>

      {/* tipo de spot */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.spot")}</Rotulo>
        <div className="flex flex-col gap-1">
          {(["mixed", "rfi", "vs_rfi", "vs_3bet"] as const).map((c) => (
            <Seg key={c} on={atual.cenario === c} onClick={() => muda({ cenario: c })}
                 testid={`pratica-cenario-${c}`} esquerda>{t(`cenario.${c}`)}</Seg>
          ))}
        </div>
      </div>

      {/* pausar depois de — aplica na HORA, porque só decide quando a tela espera */}
      <div className="border-b border-border/50 px-3 py-2.5">
        <Rotulo>{t("painel.pausa")}</Rotulo>
        <div className="flex gap-1">
          {(["nunca", "erro", "acao"] as Pausa[]).map((p) => (
            <Seg key={p} on={atual.pausa === p} onClick={() => muda({ pausa: p })}
                 testid={`pratica-pausa-${p}`}>{t(`pausa.${p}`)}</Seg>
          ))}
        </div>
      </div>

      {/* placar da sessão */}
      <div className="mt-auto border-t border-border px-3 py-2.5">
        <Rotulo>{t("painel.sessao")}</Rotulo>
        <div className="mb-2 flex gap-3">
          <div className="flex-1">
            <span className="block font-mono text-[17px] font-bold leading-none text-primary tabular-nums">
              {stats.maos ? Math.round((stats.acertos / stats.maos) * 100) : 0}%
            </span>
            <span className="font-mono text-[8.5px] uppercase tracking-widest-2 text-muted-foreground">
              {t("painel.acerto")}
            </span>
          </div>
          <div className="flex-1">
            <span className="block font-mono text-[17px] font-bold leading-none text-red-400 tabular-nums">
              {stats.bbPerdidos ? `−${stats.bbPerdidos.toFixed(1)}` : "0"}
            </span>
            <span className="font-mono text-[8.5px] uppercase tracking-widest-2 text-muted-foreground">
              {t("painel.bbPerdidos")}
            </span>
          </div>
        </div>
        <div className="grid gap-1">
          {NIVEIS.map((n) => {
            const q = stats.porNivel[n];
            const pct = stats.maos ? (q / stats.maos) * 100 : 0;
            return (
              <div key={n} data-testid={`pratica-nivel-${n}`}
                   className="grid grid-cols-[18px_1fr_auto] items-center gap-1.5 font-mono text-[9.5px] text-muted-foreground">
                <b className="font-bold text-foreground tabular-nums">{q}</b>
                <i className="block h-1 rounded-sm bg-border">
                  <span className={cn("block h-full rounded-sm", COR_DA_BARRA[n])}
                        style={{ width: `${pct}%` }} />
                </i>
                <span>{t(`nivel.${n}`)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1.5 block font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground/70">
      {children}
    </span>
  );
}

function Seg({ on, onClick, children, testid, esquerda = false }: {
  on: boolean; onClick: () => void; children: React.ReactNode;
  testid?: string; esquerda?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} data-testid={testid} aria-pressed={on}
            className={cn("flex-1 rounded border py-1 font-mono text-[10.5px] transition-colors",
              esquerda ? "px-2 text-left" : "text-center",
              on ? "border-primary bg-primary font-bold text-background"
                 : "border-border text-muted-foreground hover:text-foreground")}>
      {children}
    </button>
  );
}
