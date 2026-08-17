import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { leaktrainer } from "@/lib/api";
import type { LeakTrainerSpot, RangeClassesPanel, RangeClassRow } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Painel "range por classe de mão" (17/08): o que a RANGE INTEIRA faz neste board, agrupada
 *  por classe (trinca+, top pair, draw...) com barras empilhadas por ação. Complementa a mão
 *  do jogador — a pergunta que ele leva pra mesa é "quanto disso a range aguenta", não só "o
 *  que eu faço com esta mão". Display-only: o veredito nunca passa por aqui.
 *
 *  Sem dado o card SOME (return null), nunca renderiza vazio fingindo informação — a mesma
 *  régua do HUD de oponente ("nenhum read sem amostra"). */

// Cores por família de ação. check e fold nunca coexistem num menu (com aposta não há check;
// sem aposta não há fold), então os dois podem dividir o mesmo papel visual de "passivo".
const FAM_COLOR: Record<string, string> = {
  bet: "bg-emerald-500", raise: "bg-emerald-500", allin: "bg-violet-500",
  call: "bg-sky-500", check: "bg-slate-500/70", fold: "bg-slate-700/80",
};
const FAM_ORDER = ["bet", "raise", "allin", "call", "check", "fold"];

function Barra({ row, familias }: { row: RangeClassRow; familias: string[] }) {
  const ordenadas = FAM_ORDER.filter((f) => familias.includes(f) && (row.freqs[f] ?? 0) > 0.05);
  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-background/60 ring-1 ring-border/60">
      {ordenadas.map((f) => (
        <div key={f} className={cn("h-full", FAM_COLOR[f] ?? "bg-muted-foreground/40")}
          style={{ width: `${row.freqs[f]}%` }} title={`${f} ${row.freqs[f].toFixed(0)}%`} />
      ))}
    </div>
  );
}

export function RangeClassesCard({ spot }: { spot: LeakTrainerSpot }) {
  const { t } = useTranslation("academy");
  const [panel, setPanel] = useState<RangeClassesPanel | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let dead = false;
    setLoading(true);
    setPanel(null);
    leaktrainer.rangeClasses(spot)
      .then((p) => { if (!dead) setPanel(p); })
      .catch(() => { if (!dead) setPanel(null); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [spot]);

  if (loading) {
    return (
      <div className="mb-3 flex items-center justify-center gap-2 rounded-xl border border-border bg-hud-surface p-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        <Loader2 className="size-3 animate-spin" aria-hidden />
        {t("leakTrainer.rangeClasses.carregando")}
      </div>
    );
  }
  if (!panel?.found || !panel.classes?.length) return null;

  const familias = panel.familias ?? [];
  const famLabel = (f: string) =>
    f === "raise" ? t("leakTrainer.act.raisePost") : t(`leakTrainer.act.${f}`, f);

  const linha = (row: RangeClassRow) => (
    <div key={row.id} className="grid grid-cols-[7.5rem_3rem_1fr] items-center gap-2">
      <span className="truncate font-mono text-[10px] uppercase tracking-wider text-foreground">
        {t(`leakTrainer.rangeClasses.${row.id}`, row.id)}
      </span>
      <span className="text-right font-mono text-[10px] tabular-nums text-muted-foreground">
        {row.peso_pct.toFixed(0)}%
      </span>
      <Barra row={row} familias={familias} />
    </div>
  );

  return (
    <div className="mb-3 rounded-xl border border-border bg-hud-surface p-4">
      <div className="mb-1 font-mono text-[10px] font-bold uppercase tracking-widest text-amber-400">
        {t("leakTrainer.rangeClasses.titulo")}
      </div>
      <p className="mb-3 text-[11px] leading-snug text-muted-foreground">
        {t("leakTrainer.rangeClasses.desc")}
      </p>
      <div className="space-y-1.5">{panel.classes.map(linha)}</div>
      {(panel.draws?.length ?? 0) > 0 && (
        <>
          <div className="mb-1.5 mt-3 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
            {t("leakTrainer.rangeClasses.draws")}
          </div>
          <div className="space-y-1.5">{panel.draws!.map(linha)}</div>
        </>
      )}
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
        {FAM_ORDER.filter((f) => familias.includes(f)).map((f) => (
          <span key={f} className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
            <span className={cn("size-2 rounded-full", FAM_COLOR[f])} aria-hidden />
            {famLabel(f)}
          </span>
        ))}
      </div>
    </div>
  );
}
