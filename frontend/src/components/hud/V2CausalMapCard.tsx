import { GitFork, ArrowRight, Crosshair } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { LeakNode, LeakEdge } from "./LeakCausalMap";
import { formatAction } from "@/lib/utils";

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

/** Nome legível do spot a partir do node.id ("flop/fold" → "Fold no flop").
 *  O label do backend vem abreviado ("FL Fold") — ilegível pro jogador.
 *  Streets e ações ficam em inglês (termos de poker); só o conector é i18n. */
function spotLabel(node: LeakNode, t: (k: string, o?: object) => string): string {
  const parts = (node.id || "").split("/");
  if (parts.length === 2 && parts[0] && parts[1]) {
    return t("v2.causalSpot", { action: formatAction(parts[1]), street: parts[0] });
  }
  return node.label.replace(/[_-]+/g, " ");
}

function NodeChip({ node, t }: { node: LeakNode; t: (k: string, o?: object) => string }) {
  const name = spotLabel(node, t);
  return (
    <span
      className={`inline-flex max-w-full items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-bold tracking-wide truncate ${
        SEVERITY_BADGE[node.severity] ?? SEVERITY_BADGE.minor
      }`}
      title={`${name} · ${node.n}x`}
    >
      {name}
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
            <NodeChip node={epicenter} t={t} />
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
                <NodeChip node={byId[e.source]} t={t} />
                <ArrowRight className="size-3.5 shrink-0 text-muted-foreground/60" />
                <NodeChip node={byId[e.target]} t={t} />
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

      {/* Fallback — leaks isolados (sem co-ocorrência → sem arestas): em vez de um card
          vazio, mostra os spots como pontos de atenção + explica por que ainda não há mapa. */}
      {relations.length === 0 && (
        <div>
          <p className="mb-2 text-[11px] leading-relaxed text-muted-foreground">
            {t("v2.causalNoEdges")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {[...nodes]
              .sort((a, b) => sevRank[a.severity] - sevRank[b.severity] || b.n - a.n)
              .slice(0, 8)
              .map((n) => (
                <NodeChip key={n.id} node={n} t={t} />
              ))}
          </div>
        </div>
      )}

      {/* Conclusão determinística: o que esta análise significa, nos SEUS dados.
          (A narrativa de IA aprofundada vive no carrossel — isto é a síntese.) */}
      {relations.length > 0 && epicenter && (
        <p className="mt-3 pt-2.5 border-t border-border/30 text-[11px] leading-relaxed text-muted-foreground">
          {t("v2.causalConclusion", {
            a: spotLabel(byId[relations[0].source], t),
            b: spotLabel(byId[relations[0].target], t),
            n: relations[0].co_occurrences,
            epi: spotLabel(epicenter, t),
            deg: epicenter.degree,
          })}
        </p>
      )}
    </div>
  );
}
