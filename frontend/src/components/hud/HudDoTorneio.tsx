import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";
import type { HeroHudResponse } from "@/lib/api";

/**
 * O HUD do HERÓI neste torneio: como você jogou a sessão, com a amostra na cara.
 *
 * ── O que originou (29/08) ────────────────────────────────────────────────────────────────
 *
 * Pedido do dono: nos detalhes do torneio, os indicadores dele "mesmo que o número de
 * amostras seja baixo, apenas para o usuário ter ideia de como se comportou".
 *
 * ── A regra que decide o visual ───────────────────────────────────────────────────────────
 *
 * O número descreve a sessão; a COR compara com a referência de MTT. E comparação exige
 * amostra: com `low_sample` o valor aparece neutro (sem verde/vermelho), com o denominador do
 * lado — "31% em 42 mãos" informa; "31%" pintado de vermelho em 42 mãos acusa sem base
 * ([[project_opponent_hud]]: nenhum read sem amostra). `no_opportunity` mostra traço, nunca
 * zero: célula sem dado não vira 0 em superfície nenhuma deste produto.
 */

const ORDEM = ["vpip", "pfr", "threebet", "fold3bet", "cbet", "wtsd", "af"] as const;

function corDaBanda(band: string): string {
  if (band === "healthy") return "text-primary";
  if (band === "below" || band === "above") return "text-amber-400";
  return "text-foreground";           // low_sample / no_opportunity: neutro, sem veredito
}

export function HudDoTorneio({ hud }: { hud: HeroHudResponse }) {
  const { t } = useTranslation("tournaments");
  if (!hud.available || !hud.stats) return null;

  return (
    <section className="rounded-xl border border-border bg-hud-surface px-5 py-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {t("detail.hud.title")}
        </span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70">
          {t("detail.hud.hands", { n: hud.hands })}
        </span>
        {hud.archetype && (
          <span className="rounded-sm bg-primary/10 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-primary ring-1 ring-primary/20">
            {hud.archetype}
          </span>
        )}
        {/* A sessão típica fica abaixo dos gates de referência: o aviso vale para o card
            inteiro e evita repetir "amostra curta" em cada célula. */}
        <span className="ml-auto text-[10px] text-muted-foreground/70">
          {t("detail.hud.disclaimer")}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-4 lg:grid-cols-7">
        {ORDEM.map((k) => {
          const s = hud.stats?.[k];
          if (!s) return null;
          const semDado = s.value == null;
          return (
            <div key={k} className="bg-hud-surface px-2.5 py-2.5">
              <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                {t(`detail.hud.stat.${k}`)}
              </div>
              <div className={cn("font-mono text-lg font-light tabular-nums leading-none",
                                 semDado ? "text-muted-foreground/50" : corDaBanda(s.band))}>
                {semDado ? "—" : k === "af" ? s.value.toFixed(1) : `${s.value.toFixed(0)}%`}
              </div>
              <div className="mt-1 font-mono text-[9px] tabular-nums text-muted-foreground/70">
                {semDado ? t("detail.hud.noOpportunity") : `${s.num}/${s.den}`}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
