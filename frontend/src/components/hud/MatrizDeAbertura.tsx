import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { RangeGrid } from "@/components/replayer/RangeGrid";
import type { RangeSet } from "@/data/ranges";
import type { PositionOpenMatrixResponse, StackBand } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Matriz 13x13 das maos que o jogador ABRIU de um assento, contra o que o solver abriria com
 * as mesmas maos nos mesmos stacks (AY-15 c, sugestao do Rullian). Abre pela celula RFI do
 * Perfil por posicao e herda o assento e a faixa de stack.
 *
 * Duas grades lado a lado, a MESMA `RangeGrid` de /ranges (nada de pintura nova): "Voce" com a
 * fracao em que abriu cada mao, "Solver" com a frequencia da carta. Embaixo, as maiores
 * divergencias. Por que aqui e nao um item de menu: a matriz so faz sentido com assento e stack
 * escolhidos, e o perfil ja tem os dois; e a leitura que importa e "o RFI total bate com o
 * solver, a composicao nao", que so aparece ao lado da celula.
 */
const ROTULO_DA_FAIXA: Record<string, string> = { "40+": "40+ bb", "20-40": "20–40 bb", "<20": "< 20 bb" };

function comoRange(cells: PositionOpenMatrixResponse["cells"], lado: "voce" | "solver", label: string): RangeSet {
  const raise = new Set<string>();
  const frequencies: RangeSet["frequencies"] = {};
  for (const [hand, c] of Object.entries(cells)) {
    const f = lado === "voce" ? c.voce : c.solver;
    if (f == null) continue;
    frequencies[hand] = { raise: f };
    if (f > 0.001) raise.add(hand);
  }
  return { raise, label, frequencies };
}

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);

export function MatrizDeAbertura({ position, stack, dados, erro }: {
  position: string; stack?: StackBand | null; dados: PositionOpenMatrixResponse | null; erro: boolean;
}) {
  const { t } = useTranslation("dashboard");
  const voce = useMemo(() => (dados ? comoRange(dados.cells, "voce", "voce") : null), [dados]);
  const solver = useMemo(() => (dados ? comoRange(dados.cells, "solver", "solver") : null), [dados]);
  if (erro) return <p className="text-[11px] text-muted-foreground">{t("posProfile.detail.error")}</p>;
  if (!dados || !voce || !solver) return <p className="font-mono text-[10px] text-muted-foreground/60">…</p>;
  if (dados.n === 0) return <p className="text-[11px] text-muted-foreground">{t("posProfile.detail.empty")}</p>;
  return (
    <div className="mt-1" data-testid={`matriz-${position}`}>
      <div className="mb-3 flex flex-wrap items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
        <span className="rounded-md border border-primary/40 px-2 py-0.5 text-primary">{position}</span>
        <span className="rounded-md border border-primary/40 px-2 py-0.5 text-primary">{stack ? ROTULO_DA_FAIXA[stack] ?? stack : t("posProfile.stackAll")}</span>
        <span className="rounded-md border border-border px-2 py-0.5">{t("posProfile.matrix.opps", { n: dados.n.toLocaleString() })}</span>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div data-testid="matriz-voce">
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("posProfile.you")}</span>
            <span className="font-heading text-sm font-bold text-foreground">{t("posProfile.matrix.opened", { pct: dados.voce_pct ?? "—" })}</span>
          </div>
          <RangeGrid range={voce} />
          <p className="mt-1.5 font-mono text-[9px] leading-snug text-muted-foreground/70">{t("posProfile.matrix.legendYou")}</p>
        </div>
        <div data-testid="matriz-solver">
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{t("posProfile.matrix.solver")}</span>
            <span className="font-heading text-sm font-bold text-foreground">
              {dados.solver_pct == null ? t("posProfile.matrix.noChart") : t("posProfile.matrix.wouldOpen", { pct: dados.solver_pct })}
            </span>
          </div>
          <RangeGrid range={solver} />
          <p className="mt-1.5 font-mono text-[9px] leading-snug text-muted-foreground/70">{t("posProfile.matrix.legendSolver", { pct: dados.cobertura })}</p>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-primary">
          {t("posProfile.matrix.divergences", { n: dados.minimo_maos })}
        </div>
        {dados.divergencias.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">{t("posProfile.matrix.noDivergence", { n: dados.minimo_maos, pp: Math.round(dados.divergencia_minima * 100) })}</p>
        ) : (
          <div className="grid items-center gap-x-3 gap-y-1" style={{ gridTemplateColumns: "3rem 3rem 3.5rem 3.5rem 4.5rem" }} data-testid="matriz-divergencias">
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">{t("posProfile.matrix.hand")}</span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">{t("posProfile.matrix.times")}</span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">{t("posProfile.you")}</span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">{t("posProfile.matrix.solver")}</span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 text-right">{t("posProfile.matrix.diff")}</span>
            {dados.divergencias.map((d) => (
              <div key={d.hand} className="contents" data-testid={`divergencia-${d.hand}`}>
                <span className="font-mono text-[11px] font-bold text-foreground">{d.hand}</span>
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground text-right">{d.n}</span>
                <span className="font-mono text-[11px] tabular-nums text-foreground text-right">{pct(d.voce)}</span>
                <span className="font-mono text-[11px] tabular-nums text-foreground text-right">{pct(d.solver)}</span>
                <span className={cn("font-mono text-[11px] font-bold tabular-nums text-right", "text-red-400")}>
                  {d.delta > 0 ? "+" : ""}{Math.round(d.delta * 100)} pp
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-[10px] leading-snug text-muted-foreground/80">{t("posProfile.matrix.note")}</p>
        <Link to="/ranges" className="shrink-0 rounded-md border border-primary/40 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary hover:bg-primary/10">
          {t("posProfile.matrix.study")}
        </Link>
      </div>
    </div>
  );
}
