import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Sparkles, Lock } from "lucide-react";

/**
 * V2AiInsightsCard — UX-2 onda 2. As narrativas de IA (Strategic Twin,
 * Cognitive, Career, Causal Map) consolidadas num carrossel premium — 1 slot
 * rotativo no lugar de 4 cards gigantes competindo por atenção. Free → lock
 * com CTA (é o bloco Pro). Os cards completos seguem disponíveis abaixo.
 */
export interface AiInsight {
  key: string;     // twin | cognitive | career | causal
  title: string;   // rótulo localizado (passado pelo caller)
  text: string;    // narrativa da IA
}

interface Props {
  insights: AiInsight[];
  locked: boolean;
}

export function V2AiInsightsCard({ insights, locked }: Props) {
  const { t } = useTranslation("dashboard");
  const [idx, setIdx] = useState(0);
  if (!locked && insights.length === 0) return null;

  const cur = insights[Math.min(idx, insights.length - 1)];
  const go = (d: number) =>
    setIdx((i) => (i + d + insights.length) % insights.length);

  return (
    <div className="rounded-xl ring-1 ring-blue-400/25 bg-gradient-to-br from-blue-500/10 to-card/60 p-4 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <span className="inline-flex items-center gap-1.5 rounded-full ring-1 ring-blue-400/40 px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-blue-300">
          <Sparkles className="size-3" /> {t("v2.aiTitle")}
        </span>
        {!locked && insights.length > 1 && (
          <div className="flex items-center gap-1">
            <button onClick={() => go(-1)} className="text-muted-foreground/60 hover:text-foreground transition-colors">
              <ChevronLeft className="size-3.5" />
            </button>
            <button onClick={() => go(1)} className="text-muted-foreground/60 hover:text-foreground transition-colors">
              <ChevronRight className="size-3.5" />
            </button>
          </div>
        )}
      </div>

      {locked ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6 text-center">
          <Lock className="size-5 text-blue-300/70" />
          <p className="text-[12px] text-muted-foreground max-w-[260px]">{t("v2.aiLocked")}</p>
        </div>
      ) : (
        <>
          <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-1">
            {cur.title}
          </div>
          <p className="text-[13px] leading-relaxed text-foreground/90 flex-1">
            “{cur.text}”
          </p>
          {insights.length > 1 && (
            <div className="flex items-center gap-1.5 mt-3">
              {insights.map((ins, i) => (
                <button
                  key={ins.key}
                  onClick={() => setIdx(i)}
                  className={`size-1.5 rounded-full transition-colors ${i === idx ? "bg-blue-300" : "bg-muted/40 hover:bg-muted/70"}`}
                  aria-label={ins.title}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
