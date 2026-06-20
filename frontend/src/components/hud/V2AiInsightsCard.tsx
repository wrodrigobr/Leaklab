import { useState, useRef } from "react";
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

  // Swipe lateral em telas touch: arrastar p/ a esquerda = próximo, direita = anterior.
  // Só dispara em gesto horizontal (|dx|>|dy|) → não atrapalha o scroll vertical.
  const touch = useRef<{ x: number; y: number } | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    touch.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    const start = touch.current;
    touch.current = null;
    if (!start || locked || insights.length < 2) return;
    const dx = e.changedTouches[0].clientX - start.x;
    const dy = e.changedTouches[0].clientY - start.y;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) go(dx < 0 ? 1 : -1);
  };

  return (
    <div
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      style={!locked && insights.length > 1 ? { touchAction: "pan-y" } : undefined}
      className="rounded-xl ring-1 ring-blue-400/25 bg-gradient-to-br from-blue-500/10 to-card/60 p-4 flex flex-col">
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
            <div className="flex items-center gap-2 mt-3">
              {insights.map((ins, i) => (
                <button
                  key={ins.key}
                  onClick={() => setIdx(i)}
                  title={ins.title}
                  className={`size-2 rounded-full transition-all ${
                    i === idx
                      ? "bg-blue-300 ring-2 ring-blue-300/40 scale-110"
                      : "bg-blue-200/25 ring-1 ring-blue-300/40 hover:bg-blue-200/60"
                  }`}
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
