import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";
import type { EvolutionPoint } from "@/lib/api";

interface Props {
  evolution?: EvolutionPoint[];
}

function scoreDot(score: number) {
  if (score <= 0.08) return { bg: "bg-primary",     ring: "ring-primary/40",     label: "Standard" };
  if (score <= 0.18) return { bg: "bg-yellow-500",  ring: "ring-yellow-500/40",  label: "Marginal" };
  if (score <= 0.36) return { bg: "bg-orange-500",  ring: "ring-orange-500/40",  label: "Erro pequeno" };
  return              { bg: "bg-destructive",   ring: "ring-destructive/40", label: "Erro claro" };
}

export function RecentForm({ evolution }: Props) {
  const recent = (evolution ?? []).slice(-10).reverse();

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            Forma Recente
          </span>
          <HudTooltip content="Qualidade média das decisões nos últimos torneios. Verde = sessão standard, amarelo = marginal, laranja/vermelho = sessão com erros significativos. Leitura da esquerda (mais recente) para direita (mais antigo)." />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{recent.length} torneios</span>
      </div>

      {recent.length === 0 ? (
        <p className="text-xs text-muted-foreground">Sem dados suficientes.</p>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          {recent.map((pt, i) => {
            const score = pt.avg_score ?? 0;
            const { bg, ring, label } = scoreDot(score);
            const id = pt.tournament_id ?? i;
            return (
              <div key={id} className="flex flex-col items-center gap-1" title={`Score: ${score.toFixed(3)} · ${label}`}>
                <div className={cn("size-4 rounded-full ring-2 transition-transform hover:scale-125 cursor-default", bg, ring)} />
                {i === 0 && (
                  <span className="font-mono text-[8px] text-muted-foreground/60">agora</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {recent.length > 0 && (
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          {[
            { label: "Standard",    bg: "bg-primary" },
            { label: "Marginal",    bg: "bg-yellow-500" },
            { label: "Erro",        bg: "bg-orange-500" },
            { label: "Erro claro",  bg: "bg-destructive" },
          ].map(({ label, bg }) => (
            <div key={label} className="flex items-center gap-1">
              <span className={cn("size-2 rounded-full", bg)} />
              <span className="font-mono text-[9px] text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
