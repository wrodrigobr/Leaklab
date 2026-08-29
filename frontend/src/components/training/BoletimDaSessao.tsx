import { Flame, Lock, Trophy } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

/**
 * O fim do treino grátis do dia: um boletim, e não uma parede.
 *
 * ── O que originou (28/08) ────────────────────────────────────────────────────────────────
 *
 * Ao abrir o treino de fundamentos no Free, eu DESLIGUEI o teto diário sem que ninguém pedisse.
 * O dono corrigiu mostrando o concorrente: eles limitam treino também — 20 por dia — e limitam o
 * tipo.
 *
 * Mas o que o print dele ensina não é o limite. É a EMBALAGEM. Onde nós mandávamos o jogador para
 * uma fase literalmente chamada `paywall`, eles fecham a sessão com um **boletim**: precisão,
 * melhor sequência, EV deixado na mesa, dias seguidos, acerto por cenário — e só então o convite,
 * com "volte amanhã para mais 20 grátis".
 *
 * A mesma restrição. Um lê como relatório de quem terminou o dever; o outro, como porta na cara.
 *
 * ── O número que eles não conseguem preencher ─────────────────────────────────────────────
 *
 * No print do concorrente, "EV DEIXADO NA MESA (BB)" aparece como **0.0**. Está zerado porque
 * eles treinam spots sintéticos e não têm de onde tirar o custo. Nós medimos bb perdidos nas mãos
 * REAIS do jogador — é a tese do produto inteira num número só.
 *
 * Por isso ele aparece aqui **apenas quando existe**: um `0.0` fixo, como o deles, seria pior que
 * não mostrar. Célula sem amostra não vira zero, nem aqui.
 */

export interface CategoriaDaSessao {
  label: string;
  hits: number;
  misses: number;
}

interface Props {
  totalFeito: number;
  totalCerto: number;
  melhorSequencia: number;
  diasSeguidos?: number | null;
  /** bb deixados na mesa, medidos nas mãos do jogador. `null` = não medido nesta sessão. */
  bbNaMesa?: number | null;
  categorias: CategoriaDaSessao[];
  /** o que o Pro destrava, vindo do backend — nunca uma lista escrita aqui */
  travados?: string[];
  cap?: number | null;
  aoTreinarDeNovo?: () => void;
}

function Numero({ valor, rotulo, tom }: { valor: string; rotulo: string; tom?: string }) {
  return (
    <div className="flex flex-1 flex-col items-center gap-0.5 rounded-lg border border-border bg-background/40 px-2 py-2.5">
      <span className={cn("font-heading text-xl font-bold leading-none", tom ?? "text-foreground")}>
        {valor}
      </span>
      <span className="text-center font-mono text-[8.5px] uppercase leading-tight tracking-wider text-muted-foreground">
        {rotulo}
      </span>
    </div>
  );
}

export function BoletimDaSessao({
  totalFeito, totalCerto, melhorSequencia, diasSeguidos, bbNaMesa,
  categorias, travados = [], cap, aoTreinarDeNovo,
}: Props) {
  const { t } = useTranslation("dashboard");
  const precisao = totalFeito > 0 ? Math.round((totalCerto / totalFeito) * 100) : null;

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-3 rounded-xl border border-border bg-hud-surface/60 p-4">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/10">
          <Trophy className="size-4 text-amber-400" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className="font-heading text-base font-bold leading-tight text-foreground">
            {t("boletim.titulo")}
          </h2>
          <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground">
            {t("boletim.sub")}
          </p>
        </div>
      </div>

      <div className="flex gap-2">
        {/* Precisão sem amostra fica de fora: "0%" numa sessão vazia afirma desempenho ruim onde
            não houve desempenho nenhum. É a mesma regra da célula cinza da evolução. */}
        {precisao !== null && (
          <Numero valor={`${precisao}%`} rotulo={t("boletim.precisao")}
                  tom={precisao >= 70 ? "text-primary" : undefined} />
        )}
        <Numero valor={String(melhorSequencia)} rotulo={t("boletim.sequencia")} tom="text-amber-400" />
        {/* O número que o concorrente mostra zerado. Só aparece quando foi medido de verdade. */}
        {bbNaMesa != null && (
          <Numero valor={bbNaMesa.toFixed(1)} rotulo={t("boletim.bbNaMesa")}
                  tom={bbNaMesa > 0 ? "text-destructive" : "text-primary"} />
        )}
      </div>

      {diasSeguidos != null && diasSeguidos > 1 && (
        <p className="flex items-center justify-center gap-1.5 font-mono text-[11px] text-amber-400">
          <Flame className="size-3" aria-hidden />
          {t("boletim.diasSeguidos", { n: diasSeguidos })}
        </p>
      )}

      {categorias.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
            {t("boletim.porCenario")}
          </span>
          {categorias.map((c) => {
            const total = c.hits + c.misses;
            const pct = total > 0 ? Math.round((c.hits / total) * 100) : 0;
            return (
              <div key={c.label} className="flex items-center gap-2">
                <span className="w-24 shrink-0 truncate text-[11px] text-muted-foreground">{c.label}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                </span>
                <span className="w-9 shrink-0 text-right font-mono text-[10px] tabular-nums text-foreground">
                  {pct}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      {travados.length > 0 && (
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.04] p-2.5">
          <p className="text-[11.5px] font-medium text-foreground">{t("boletim.noPro")}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {travados.map((x) => (
              <span key={x} className="flex items-center gap-1 rounded border border-border bg-background/50 px-1.5 py-0.5">
                <Lock className="size-2.5 text-muted-foreground" aria-hidden />
                <span className="font-mono text-[9.5px] text-muted-foreground">{x}</span>
              </span>
            ))}
          </div>
          <p className="mt-1.5 text-[10.5px] leading-snug text-primary">{t("boletim.proDiz")}</p>
        </div>
      )}

      <Link
        to="/subscription"
        className="rounded-lg bg-gradient-to-b from-amber-300 to-amber-500 px-4 py-2.5 text-center font-mono text-[12px] font-bold uppercase tracking-wider text-background transition-opacity hover:opacity-90"
      >
        {t("boletim.assinar")}
      </Link>

      {/* O gancho de RETORNO, que é metade do valor do limite: o jogador sai sabendo quando volta.
          Sem isto o teto vira só uma porta fechada. */}
      <p className="text-center text-[10.5px] text-muted-foreground">
        {cap ? t("boletim.volteAmanha", { n: cap }) : t("boletim.volteAmanhaSemNumero")}
      </p>

      {aoTreinarDeNovo && (
        <button
          type="button"
          onClick={aoTreinarDeNovo}
          className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
        >
          {t("boletim.voltar")}
        </button>
      )}
    </div>
  );
}
