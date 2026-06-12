import { GitFork, ArrowRight, Crosshair } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { LeakNode, LeakEdge } from "./LeakCausalMap";

/**
 * V2CausalMapCard — UX-2. Versão V2 do mapa causal SEM o grafo circular
 * (linguagem de engenheiro): fala a língua do jogador — "quando você erra A,
 * você também erra B", relações rankeadas por força + o EPICENTRO (leak mais
 * conectado: corrigi-lo derruba a cadeia). Clássico segue com o grafo SVG.
 */
const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-500/10 text-red-400 ring-1 ring-red-500/25",
  moderate: "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/25",
  minor:    "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/25",
};

function prettyLabel(label: string): string {
  return label.replace(/[_-]+/g, " ");
}

function NodeChip({ node }: { node: LeakNode }) {
  return (
    <span
      className={`inline-flex max-w-full items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide truncate ${
        SEVERITY_BADGE[node.severity] ?? SEVERITY_BADGE.minor
      }`}
      title={`${prettyLabel(node.label)} · ${node.n}x`}
    >
      {prettyLabel(node.label)}
    </span>
  );
}

export function V2CausalMapCard({ nodes, edges }: { nodes: LeakNode[]; edges: LeakEdge[] }) {
  const { t } = useTranslation("dashboard");
  if (!nodes.length) return null;

  const byId: Record<string, LeakNode> = {};
  for (const n of nodes) byId[n.id] = n;

  // Epicentro: o leak mais conectado (maior degree; empate: mais severo/frequente)
  const sevRank = { critical: 0, moderate: 1, minor: 2 } as const;
  const epicenter = [...nodes].sort(
    (a, b) => b.degree - a.degree || sevRank[a.severity] - sevRank[b.severity] || b.n - a.n
  )[0];

  // Relações mais fortes (com os dois nós presentes), da maior correlação pra menor
  const relations = edges
    .filter((e) => byId[e.source] && byId[e.target])
    .sort((a, b) => b.correlation - a.correlation)
    .slice(0, 5);

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center gap-2 mb-3">
        <GitFork className="size-4 text-primary" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {t("leakCausalMap.title")}
        </span>
        <HudTooltip content={t("leakCausalMap.tooltip")} />
      </div>

      {/* Epicentro — o leak que mais puxa os outros */}
      {epicenter && epicenter.degree > 0 && (
        <div className="mb-3 rounded-lg ring-1 ring-teal-400/25 bg-teal-400/5 px-3 py-2.5">
          <div className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-teal-300">
            <Crosshair className="size-3" /> {t("v2.causalEpicenter")}
          </div>
          <div className="mt-1 flex items-center gap-2 flex-wrap">
            <NodeChip node={epicenter} />
            <span className="text-[11px] text-muted-foreground">
              {t("v2.causalEpicenterDesc", { n: epicenter.degree })}
            </span>
          </div>
        </div>
      )}

      {/* Relações: quando A acontece, B vem junto */}
      <div className="space-y-2.5">
        {relations.map((e, i) => {
          const pct = Math.round(e.correlation * 100);
          return (
            <div key={i}>
              <div className="flex items-center gap-2 min-w-0">
                <NodeChip node={byId[e.source]} />
                <ArrowRight className="size-3.5 shrink-0 text-muted-foreground/60" />
                <NodeChip node={byId[e.target]} />
                <span className="ml-auto font-mono text-[11px] font-bold tabular-nums shrink-0 text-foreground/80">
                  {pct}%
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1 flex-1 rounded-full bg-muted/15 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.max(4, pct)}%`,
                      background: "linear-gradient(90deg, #2DD4BF66, #2DD4BF)",
                    }}
                  />
                </div>
                <span className="font-mono text-[9px] text-muted-foreground/60 shrink-0">
                  {t("v2.causalTogether", { n: e.co_occurrences })}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-3 pt-2 border-t border-border/30 font-mono text-[9px] text-muted-foreground/70">
        {t("v2.causalHint")}
      </p>
    </div>
  );
}
