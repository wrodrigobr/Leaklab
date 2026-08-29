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
 * amostra. Revisada em 30/08 a pedido do dono ("indicar se está dentro do valor esperado"):
 * o valor é comparado com a FAIXA de MTT em qualquer amostra — valor×faixa são dois fatos; o
 * que amostra curta não sustenta é TENDÊNCIA, e o aviso do topo diz exatamente isso. A régua
 * aparece NA CÉLULA ("alvo 18–24%"): cor sem régua visível é acusação sem base. Stat sem
 * faixa declarada fica neutro, e `no_opportunity` mostra traço, nunca zero.
 */

const ORDEM = ["vpip", "pfr", "threebet", "fold3bet", "cbet", "wtsd", "af"] as const;

/* Dentro/fora da FAIXA de MTT (30/08, pedido do dono: "indicar se está dentro do valor
   esperado"). A comparação valor×faixa é entre dois FATOS e vale em qualquer amostra — o que
   a amostra curta não sustenta é TENDÊNCIA, e disso cuida o aviso no topo do card. Sem faixa
   declarada (ex.: fold to c-bet), o valor fica neutro: não se pinta sem régua. */
function dentroDaFaixa(valor: number | null, faixa?: [number, number] | null): boolean | null {
  if (valor == null || !faixa) return null;
  return valor >= faixa[0] && valor <= faixa[1];
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
          {t("detail.hud.legenda")} · {t("detail.hud.disclaimer")}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-4 lg:grid-cols-7">
        {ORDEM.map((k) => {
          const s = hud.stats?.[k];
          if (!s) return null;
          const semDado = s.value == null;
          const dentro = dentroDaFaixa(s.value, s.healthy);
          return (
            <div key={k} className="bg-hud-surface px-2.5 py-2.5">
              <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                {t(`detail.hud.stat.${k}`)}
              </div>
              <div className={cn("font-mono text-lg font-light tabular-nums leading-none",
                                 semDado ? "text-muted-foreground/50"
                                   : dentro === null ? "text-foreground"
                                   : dentro ? "text-primary" : "text-amber-400")}>
                {semDado ? "—" : k === "af" ? s.value.toFixed(1) : `${s.value.toFixed(0)}%`}
              </div>
              <div className="mt-1 font-mono text-[9px] tabular-nums text-muted-foreground/70">
                {semDado ? t("detail.hud.noOpportunity") : `${s.num}/${s.den}`}
              </div>
              {/* A régua na célula: sem ela a cor vira acusação sem base visível. */}
              {!semDado && s.healthy && (
                <div className="font-mono text-[8.5px] tabular-nums text-muted-foreground/50">
                  {t("detail.hud.alvo")} {s.healthy[0]}–{s.healthy[1]}{k === "af" ? "x" : "%"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
