import { useState } from "react";
import { GitFork, Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import { cn } from "@/lib/utils";

export interface LeakNode {
  id: string;
  label: string;
  n: number;
  avg_score: number;
  severity: "critical" | "moderate" | "minor";
  degree: number;
}

export interface LeakEdge {
  source: string;
  target: string;
  co_occurrences: number;
  correlation: number;
}

interface Props {
  nodes: LeakNode[];
  edges: LeakEdge[];
  narrative?: string;
}

const SEVERITY_FILL: Record<string, string> = {
  critical: "#ef4444",
  moderate: "#f59e0b",
  minor:    "#10b981",
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: "text-red-400",
  moderate: "text-amber-400",
  minor:    "text-emerald-400",
};

function circularLayout(
  count: number,
  cx: number,
  cy: number,
  r: number
): { x: number; y: number }[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
}

export function LeakCausalMap({ nodes, edges, narrative }: Props) {
  const { t } = useTranslation("dashboard");
  const [selected, setSelected] = useState<string | null>(null);

  if (!nodes.length) return null;

  const W = 420;
  const H = 320;
  const cx = W / 2;
  const cy = H / 2;
  const layoutR = Math.min(cx, cy) - 52;

  const positions = circularLayout(nodes.length, cx, cy, layoutR);
  const posMap: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n, i) => { posMap[n.id] = positions[i]; });

  const selectedEdges = selected
    ? edges.filter((e) => e.source === selected || e.target === selected)
    : edges;

  const isHighlighted = (id: string) => {
    if (!selected) return true;
    if (id === selected) return true;
    return selectedEdges.some((e) => e.source === id || e.target === id);
  };

  return (
    <div className="rounded-xl border border-border bg-hud-surface overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          <GitFork className="size-3" aria-hidden />
          {t("leakCausalMap.title")}
          <HudTooltip content={t("leakCausalMap.tooltip")} />
        </h2>
        <span className="font-mono text-[10px] text-muted-foreground">90d</span>
      </div>

      <div className="p-4 space-y-3">
        {/* SVG Graph */}
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          style={{ maxHeight: 280 }}
          aria-label={t("leakCausalMap.aria")}
        >
          {/* Edges */}
          {edges.map((edge, i) => {
            const a = posMap[edge.source];
            const b = posMap[edge.target];
            if (!a || !b) return null;
            const active = !selected ||
              edge.source === selected || edge.target === selected;
            return (
              <line
                key={i}
                x1={a.x} y1={a.y}
                x2={b.x} y2={b.y}
                stroke="#10b981"
                strokeWidth={1 + edge.correlation * 2.5}
                strokeOpacity={active ? 0.15 + edge.correlation * 0.55 : 0.04}
                strokeLinecap="round"
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node, i) => {
            const pos = positions[i];
            const fill  = SEVERITY_FILL[node.severity] ?? "#10b981";
            const dimmed = !isHighlighted(node.id);
            const isSelected = node.id === selected;
            const r = 16 + Math.min(node.degree, 5) * 2;

            // Label placement: push outward from center
            const dx = pos.x - cx;
            const dy = pos.y - cy;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const lx = pos.x + (dx / dist) * (r + 10);
            const ly = pos.y + (dy / dist) * (r + 10);
            const anchor = dx > 5 ? "start" : dx < -5 ? "end" : "middle";
            const labelY = dy > 5 ? ly + 4 : dy < -5 ? ly - 2 : ly + 4;

            return (
              <g
                key={node.id}
                onClick={() => setSelected(isSelected ? null : node.id)}
                style={{ cursor: "pointer" }}
                opacity={dimmed ? 0.25 : 1}
              >
                <circle
                  cx={pos.x} cy={pos.y} r={r}
                  fill={fill}
                  fillOpacity={isSelected ? 0.35 : 0.15}
                  stroke={fill}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                />
                <text
                  x={pos.x} y={pos.y + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={9}
                  fontFamily="monospace"
                  fontWeight="bold"
                  fill={fill}
                >
                  {node.label}
                </text>
                <text
                  x={lx} y={labelY}
                  textAnchor={anchor}
                  fontSize={8}
                  fontFamily="monospace"
                  fill="#6b7280"
                >
                  {node.n}×
                </text>
              </g>
            );
          })}
        </svg>

        {/* Selected node detail */}
        {selected && (() => {
          const node = nodes.find((n) => n.id === selected);
          const connectedEdges = edges
            .filter((e) => e.source === selected || e.target === selected)
            .sort((a, b) => b.correlation - a.correlation);
          if (!node) return null;
          return (
            <div className="rounded-lg border border-border bg-background p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className={cn("font-mono text-xs font-bold", SEVERITY_LABEL[node.severity])}>
                  {node.id}
                </p>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {node.n}× · score {node.avg_score.toFixed(3)}
                </span>
              </div>
              {connectedEdges.length > 0 && (
                <ul className="space-y-1">
                  {connectedEdges.map((e, i) => {
                    const peer = e.source === selected ? e.target : e.source;
                    return (
                      <li key={i} className="flex items-center justify-between text-[11px]">
                        <span className="text-muted-foreground">
                          {t("leakCausalMap.coOccurs")} <span className="text-foreground font-semibold">{peer}</span>
                        </span>
                        <span className="font-mono text-primary">
                          {Math.round(e.correlation * 100)}%
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
              <button
                onClick={() => setSelected(null)}
                className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("leakCausalMap.clearSelection")}
              </button>
            </div>
          );
        })()}

        {/* LLM Narrative */}
        {narrative && (
          <div className="flex gap-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
            <Info className="size-3.5 shrink-0 text-primary mt-0.5" aria-hidden />
            <p className="text-[11px] leading-relaxed text-muted-foreground">{narrative}</p>
          </div>
        )}

        {/* Legend */}
        <div className="flex items-center gap-4 pt-1">
          {(["critical", "moderate", "minor"] as const).map((s) => (
            <span key={s} className="flex items-center gap-1.5 font-mono text-[9px] text-muted-foreground">
              <span
                className="inline-block size-2 rounded-full"
                style={{ background: SEVERITY_FILL[s] }}
              />
              {t(`leakCausalMap.severity.${s}`)}
            </span>
          ))}
          <span className="font-mono text-[9px] text-muted-foreground ml-auto">
            {t("leakCausalMap.thicknessCorr")}
          </span>
        </div>
      </div>
    </div>
  );
}
