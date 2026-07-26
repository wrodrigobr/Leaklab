import { useTranslation } from "react-i18next";
import { MasteryCriterion } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Os 5 critérios do gate de domínio, com progresso.
 *
 * Componente ÚNICO de propósito: o gate aparece no Leak Trainer, na tela de Treinos e (no
 * futuro) em qualquer lugar que fale de progressão. Renderizar isso inline em cada tela é
 * como o produto já criou contradições antes — o mesmo dado desenhado duas vezes derivando
 * em duas leituras diferentes.
 *
 * Regra de leitura que mora aqui: Precisão/Fronteira/Transferência são PORCENTAGEM. Mostrar
 * "60/85" nelas se lê como fração ("60 de 85 spots") e engana; vira "60% / 85%". Volume e
 * Amplitude são contagem e ficam como estão.
 */
const PCT_KEYS = new Set(["precisao", "fronteira", "transferencia"]);

export function MasteryGate({ criterios, className }: { criterios: MasteryCriterion[]; className?: string }) {
  const { t } = useTranslation("academy");
  return (
    <div className={cn("space-y-1.5", className)}>
      {criterios.map((c) => {
        const pct = Math.max(0, Math.min(100, c.alvo ? (c.atual / c.alvo) * 100 : 0));
        const semAmostra = c.amostra != null && c.amostra_min != null && c.amostra < c.amostra_min;
        const valorTxt = PCT_KEYS.has(c.key) ? `${c.atual}% / ${c.alvo}%` : `${c.atual}/${c.alvo}`;
        return (
          <div key={c.key} className="flex items-center gap-2" title={c.desc}>
            <span className={cn("w-24 shrink-0 font-mono text-[10px] uppercase tracking-wide",
              c.ok ? "text-emerald-400" : "text-muted-foreground")}>{c.label}</span>
            <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-border">
              <div className={cn("h-full rounded-full transition-all",
                c.ok ? "bg-emerald-500" : "bg-amber-500/70")} style={{ width: `${pct}%` }} />
            </div>
            <span className={cn("w-24 shrink-0 text-right font-mono text-[10px] tabular-nums",
              c.ok ? "text-emerald-400" : "text-muted-foreground")}>
              {semAmostra
                ? t("leakTrainer.protocol.needSample", "sem amostra")
                : c.ok ? "✓" : valorTxt}
            </span>
          </div>
        );
      })}
    </div>
  );
}
