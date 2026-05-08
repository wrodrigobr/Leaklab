import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, CheckCircle2, Loader2, Scale } from "lucide-react";
import { cn } from "@/lib/utils";
import { gto } from "@/lib/api";
import type { GtoDecisionResult } from "@/lib/api";

interface GtoPanelProps {
  decisionId: number;
}

export function GtoPanel({ decisionId }: GtoPanelProps) {
  const { t } = useTranslation("sparring");
  const [data, setData]       = useState<GtoDecisionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(false);

    gto.decisionLookup(decisionId)
      .then((res) => { if (!cancelled) { setData(res); setLoading(false); } })
      .catch(() => { if (!cancelled) { setError(true); setLoading(false); } });

    return () => { cancelled = true; };
  }, [decisionId]);

  return (
    <div className="rounded-lg border border-border bg-hud-surface/60 p-3 space-y-2">
      <div className="flex items-center gap-1.5">
        <Scale className="size-3.5 text-muted-foreground shrink-0" aria-hidden />
        <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
          GTO Wizard
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin shrink-0" aria-hidden />
          <span className="font-mono text-[11px]">{t("gto.loading")}</span>
        </div>
      )}

      {!loading && (error || (data && !data.found)) && (
        <p className="font-mono text-[11px] text-muted-foreground/60 italic">
          {t("gto.notFound")}
        </p>
      )}

      {!loading && data?.found && (
        <div className="space-y-2">
          {/* Agreement badge */}
          <div className={cn(
            "flex items-center gap-2 rounded-md px-2.5 py-1.5",
            data.agreement === true
              ? "bg-emerald-500/10 border border-emerald-500/30"
              : "bg-amber-500/10 border border-amber-500/30"
          )}>
            {data.agreement === true
              ? <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" aria-hidden />
              : <AlertTriangle className="size-3.5 text-amber-400 shrink-0" aria-hidden />
            }
            <span className={cn(
              "font-mono text-[10px] font-semibold uppercase tracking-wide",
              data.agreement === true ? "text-emerald-400" : "text-amber-400"
            )}>
              {data.agreement === true ? t("gto.confirms") : t("gto.divergence")}
            </span>
          </div>

          {/* GTO recommendation row */}
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide">
                {t("gto.recommendsLabel")}
              </p>
              <p className="font-mono text-base font-bold text-foreground">
                {data.gto_action.toUpperCase()}
              </p>
            </div>
            {data.gto_freq != null && (
              <div className="text-right">
                <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wide">
                  {t("gto.freqLabel")}
                </p>
                <p className="font-mono text-base font-bold text-primary">
                  {Math.round(data.gto_freq * 100)}%
                </p>
              </div>
            )}
          </div>

          {/* EV diff */}
          {data.ev_diff != null && (
            <p className="font-mono text-[10px] text-muted-foreground">
              {t("gto.evDiff", { n: data.ev_diff.toFixed(2) })}
            </p>
          )}

          {/* Frequency bar */}
          {data.gto_freq != null && (
            <div className="h-1 w-full rounded-full bg-border overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${Math.round(data.gto_freq * 100)}%` }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
